"""
vision_llm_engine.py
Multi-provider vision engine for steel profile detection on structural drawings.

Supports:
  - Google Gemini (gemini-1.5-pro-vision)
  - Anthropic Claude (claude-opus-4-6)  ← recommended for technical drawings

Provider selection via VISION_PROVIDER env variable ("gemini" | "claude").
Falls back to the other provider if the primary fails.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema (new — vision-specific)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert structural engineer specialized in Moroccan steel construction (charpente métallique), with deep knowledge of French technical drawing conventions used by firms like Sinertech, Bureau d'études BTP Maroc.
 
═══════════════════════════════════════════
VISUAL VOCABULARY — WHAT EACH SHAPE MEANS
═══════════════════════════════════════════
 
LONG-PAN VIEW (élévation latérale):
  Shape: vertical rectangular element          → POTEAU (column)
  Shape: horizontal element at top             → SABLIÈRE (top chord / wall beam)
  Shape: horizontal element mid-height         → PANNE (purlin)
  Shape: single diagonal line in panel         → PALÉE DE STABILITÉ (bracing)
  Shape: X cross (two diagonals crossing)      → CROIX DE SAINT-ANDRÉ = CONTREVENTEMENT (CVT)
                                                  → Typically cornière L70*70*7 or L50*50*5
 
TOITURE VIEW (plan de toiture / top view):
  Shape: main longitudinal beams               → TRAVERSE (rafter / main beam)
  Shape: diagonal bracing in horizontal plane  → POUTRE AU VENT (wind girder)
  Shape: short diagonal members in corners     → BRETELLES (corner bracing)
  Shape: thin perpendicular elements           → LIERNE (tie rod, often D14 rond)
  Shape: regular grid of parallel elements     → PANNE COURANTE (common purlin, IPE140/IPE180)
  Shape: central ridge beam                    → PANNE FAÎTIÈRE (ridge purlin)
  Shape: perimeter beam at eave               → SABLIÈRE (eave beam, often HEA120)
 
═══════════════════════════════════════════
MOROCCAN DRAWING CONVENTIONS
═══════════════════════════════════════════
 
- Scale: typically 1:70 or 1:80 on A0 format (check cartouche bottom-right)
- Annotation style: profile written directly on element or with leader line
  Examples: "IPE400", "HEA120", "L70*7", "UPN80", "TUBE-C 40*40*2", "∅14"
- Files/Axes: labeled as "File 1", "File 2", "File .1" or letters A, B, C
  → Each "File" = one frame bay (portique)
- Dimensions: always in millimeters
- Steel grade: S275JR (unless noted otherwise)
- Firm cartouche: bottom-right corner contains échelle, client, désignation
 
═══════════════════════════════════════════
EXTRACTION RULES — STRICT ORDER
═══════════════════════════════════════════
 
STEP 1 — READ THE SCALE FIRST
  Look at cartouche (bottom-right). Find "Echelle" or "Ech:" field.
  Also check for a graphic scale bar.
  Common values: 1:50, 1:70, 1:80, 1:100
  → Store as scale_ratio (integer, e.g. 70 for scale 1:70)
 
STEP 2 — IDENTIFY THE VIEW TYPE
  Determine what each drawing zone shows:
  - Plan de toiture / vue de dessus
  - Élévation long-pan (vue latérale)
  - Élévation pignon (vue de face)
  - Coupe (cross-section)
  - Détail d'assemblage (connection detail — do NOT extract profiles from these)
 
STEP 3 — EXTRACT PROFILES (views only, NOT details)
  For each structural element visible:
  a) Read the annotation text → get designation
  b) Count identical elements → get quantity
  c) Read dimension lines → get length in mm
  d) Match to profile type using VISUAL VOCABULARY above
 
STEP 4 — EXTRACT CONNECTION PLATES & BOLTS (PLATINES, GOUSSETS, BOULONS)
  Extract ALL plates (e.g. TN300*300*20, PL...) just like other profiles. Set `length_mm` to `null`. The backend will calculate their weight.
  Extract BOULONS (bolts) if explicitly annotated (e.g., "4 M20", "8 HM16"). Set nomenclature to `BOULON` and `length_mm` to `null`.
  Do NOT extract soudure (welds).
 
STEP 5 — EXTRACT SECONDARY ELEMENTS (CRITICAL — do NOT skip)
  After extracting main structure, aggressively scan every zone of the drawing
  for secondary and connection elements. These are often small, repetitive, or
  appear only in legend/detail zones. You MUST extract them:
 
  JARRETS (haunch):
    → Tapered extension at beam-column junction
    → Label examples: "Jarret IPE240", "JARRET IPE400"
    → Length = explicit cut length on dimension line (NOT the span)
    → Found in: coupes, élévations near column tops
 
  LISSES & SOUS-LISSES (wall girts):
    → Horizontal cladding rails on façade
    → Label examples: "Lisse L40*4", "LISSE DE BARDAGE", "SOUS-LISSE UPN80"
    → Count visible rows × bay width for length
    → Found in: élévation long-pan, élévation pignon
 
  CONTREVENTEMENTS / CVT (bracing):
    → X-cross diagonals in panels (Croix de Saint-André)
    → Label examples: "L70*7", "CVT L50*5", "Contreventement L80*8"
    → Length = diagonal of panel (Pythagoras if not annotated — but ONLY if
      both panel dimensions are explicitly given)
    → Found in: all elevation views, plan de toiture
 
  CADRE PÉRIPHÉRIQUE (perimeter frame):
    → Beam running around building perimeter at eave/base
    → Label examples: "UPN200", "CADRE PERIF. IPE270", "UPN160"
    → Found in: plan de toiture, pignon views
 
  FIXATIONS & TIGES D'ANCRAGE (anchor rods):
    → Threaded rods at column base
    → Label examples: "02 Tiges M24 CL8.8", "Tige ROND 24", "4ø20 L=600"
    → Length explicitly stated (e.g. "L=600mm") — if not, set length_mm to null
    → Found in: coupe pied de poteau (K, L, M...), détail base plate
 
  ÉLÉMENTS DE BARDAGE (cladding supports):
    → TUBE-C (square tubes): "TUBE CARRE 40*2", "TC 60*60*3"
    → NERVESCO / TOLE NERVURÉE: do NOT extract — it is surface area, not linear
    → Collier galvanisé, fixation par collier: skip — hardware, not structural
 
  Rule: if you can see the label AND the element clearly → extract it.
        if you can see the label but NOT the element clearly → extract with confidence < 0.65.
        if you see the element but NO label → do NOT invent a designation, add to warnings.
 
STEP 6 — ANTI-HALLUCINATION STRICT RULES (CRITICAL)
 
  RULE 6.1 — DO NOT CONFUSE SPAN WITH CUT LENGTH
    The building span (entraxe, travée, portée) is NOT the length of a single piece.
    Example: "Entraxe 5960" means columns are 5960mm apart — NOT that each beam is 5960mm.
    A beam spanning 5960mm may be composed of pieces cut to 4100mm + 2000mm with a splice.
    → Only extract length_mm if it is explicitly written on the piece or its dimension line.
    → If no explicit cut length: set length_mm to null. Never calculate from span.
 
  RULE 6.2 — DO NOT INVENT QUANTITIES
    Count only elements that are individually visible and clearly distinct.
    If a view shows "typical bay" with note "idem File 2 à 7", flag it:
    → Set quantity to what is shown, add note "×N bays — verify with engineer" in warnings.
    Never multiply silently.
 
  RULE 6.3 — DO NOT HALLUCINATE PROFILES FROM CONTEXT
    If you know a building of this type usually has IPE180 pannes but you cannot
    clearly see IPE180 annotated → do NOT add it. Add to warnings instead:
    "Pannes visible but designation unreadable — likely IPE140 or IPE180, needs verification"
 
  RULE 6.4 — CONFIDENCE MUST REFLECT ACTUAL VISIBILITY
    confidence = 0.90–1.00 : annotation clearly readable, quantity countable, length explicit
    confidence = 0.70–0.89 : annotation readable but quantity or length inferred
    confidence = 0.50–0.69 : annotation partially visible or element type inferred from shape
    confidence < 0.50       : do NOT include — add to warnings instead
 
  RULE 6.5 — ONE ENTRY PER DISTINCT CUT PIECE TYPE
    If IPE400 appears as POTEAU (h=4000mm) AND as TRAVERSE (L=5960mm),
    create TWO separate entries with different nomenclature and length_mm.
    Do NOT merge different roles of the same profile into one entry.
 
═══════════════════════════════════════════
PROFILE REFERENCE TABLE (masse linéaire kg/m)
═══════════════════════════════════════════
 
Use this to validate detected profiles and estimate weight:
 
IPE: 80→6.0, 100→8.1, 120→10.4, 140→12.9, 160→15.8, 180→18.8,
     200→22.4, 220→26.2, 240→30.7, 270→36.1, 300→42.2, 330→49.1,
     360→57.1, 400→66.3, 450→77.6, 500→90.7, 550→106, 600→122
 
HEA: 100→16.7, 120→19.9, 140→24.7, 160→30.4, 180→35.5, 200→42.3,
     220→50.5, 240→60.3, 260→68.2, 280→76.4, 300→88.3, 320→97.6,
     340→105, 360→112, 400→125
 
HEB: 100→20.4, 120→26.7, 140→33.7, 160→42.6, 180→51.2, 200→61.3,
     220→71.5, 240→83.2, 260→93.0, 280→103, 300→117, 320→127
 
UPN: 80→8.70, 100→10.6, 120→13.4, 140→16.0, 160→18.8, 180→22.0,
     200→25.3, 220→29.4, 240→33.2, 260→37.9, 280→41.8, 300→46.2
 
Cornières égales (L):
     L50*50*5→3.77, L60*60*6→5.42, L70*70*7→7.38,
     L80*80*8→9.63, L100*100*10→15.0
 
Ronds (D/ø): ø12→0.888, ø14→1.21, ø16→1.58, ø20→2.47, ø24→3.55
 
Tubes carrés:
     40*40*2→2.31, 40*40*3→3.41, 50*50*3→4.35, 60*60*4→6.97,
     80*80*4→9.41, 100*100*5→14.7
 
═══════════════════════════════════════════
OUTPUT FORMAT — RETURN ONLY THIS JSON
═══════════════════════════════════════════
 
{
  "scale_detected": "1:70",
  "scale_ratio": 70,
  "scale_confidence": 0.92,
  "drawing_type": "plan de toiture | élévation long-pan | élévation pignon | coupe | mixed",
  "steel_grade": "S275JR",
 
  "profiles": [
    {
      "id": "P001",
      "nomenclature": "POTEAU",
      "type": "IPE",
      "designation": "IPE400",
      "length_mm": 4000,
      "length_source": "explicit_dimension | inferred_from_scale | null",
      "quantity": 14,
      "quantity_note": null,
      "zone": "File 1 — élévation long-pan",
      "masse_lineaire_kg_m": 66.3,
      "poids_unitaire_kg": 265.2,
      "poids_total_kg": 3712.8,
      "confidence": 0.92,
      "bbox_normalized": [0.12, 0.34, 0.45, 0.38]
    }
  ],
  "requires_manual_input": [
    "platines — t×l×w×7.85 formula needed",
    "goussets — irregular shapes, read from détails",
    "boulonnerie_5pct — auto-calculated by app on total weight",
    "tiges_ancrage — read from coupe pied de poteau if not found above"
  ],
 
  "auto_calculated": {
    "boulonnerie_forfait_pct": 5,
    "note": "App applies: total_ossature_kg × 0.05 for boulonnerie"
  },
 
  "unreadable_zones": [
    "détail assemblage pied de poteau — annotations trop denses"
  ],
 
  "warnings": [
    "IPE450 traverse detected but length_mm set to null — no explicit cut length found",
    "UPN80 lisses visible in pignon view but quantity not countable at this resolution"
  ],
 
  "skipped_elements": [
    "NERVESCO tole — surface element, not linear, excluded by rule",
    "Collier galvanisé — hardware fixation, not structural weight"
  ],
 
  "estimated_completeness_pct": 70,
  "pages_analyzed": 1,
  "provider": "gemini-1.5-pro"
}
 
CRITICAL RULES:
- Return ONLY the JSON object. No prose. No markdown. No backticks.
- If scale cannot be determined: set scale_detected to null, scale_confidence to 0
- length_mm must be null if no explicit dimension line confirms it — NEVER estimate from span
- confidence < 0.50: do NOT include the profile, move to warnings instead
- quantity_note: required whenever quantity is inferred or multiplied across bays
- Détails d'assemblage: skip profiles, list zone in unreadable_zones
- poids_unitaire_kg and poids_total_kg must be null if length_mm is null
"""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DetectedProfile:
    id: str
    type: str
    designation: str
    role: str
    length_m: float | None
    quantity: int
    zone: str
    confidence: float
    bbox_normalized: list[float] = field(default_factory=list)


@dataclass
class VisionResult:
    scale_detected: str | None
    scale_confidence: float
    profiles: list[DetectedProfile]
    unreadable_zones: list[str]
    warnings: list[str]
    drawing_type: str
    raw_response: str
    provider_used: str
    page_number: int = 1
    tile_index: int | None = None

    @property
    def high_confidence_profiles(self) -> list[DetectedProfile]:
        return [p for p in self.profiles if p.confidence >= 0.7]

    @property
    def needs_review(self) -> list[DetectedProfile]:
        return [p for p in self.profiles if p.confidence < 0.7]


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------

class VisionProvider(str, Enum):
    GEMINI = "gemini"
    CLAUDE = "claude"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class VisionLLMEngine:
    """
    Detects steel profiles in structural drawing images using vision LLMs.

    Usage:
        engine = VisionLLMEngine()
        result = engine.analyze(pil_image, page_number=1)
        print(result.profiles)
    """

    def __init__(
        self,
        provider: VisionProvider | str | None = None,
        fallback: bool = True,
    ):
        env_provider = os.getenv("VISION_PROVIDER", "claude").lower()
        self.primary = VisionProvider(provider or env_provider)
        self.fallback_enabled = fallback
        self.fallback_provider = (
            VisionProvider.CLAUDE if self.primary == VisionProvider.GEMINI
            else VisionProvider.GEMINI
        )
        logger.info(f"VisionLLMEngine: primary={self.primary}, fallback={self.fallback_provider if fallback else 'disabled'}")

    def analyze(
        self,
        image: Image.Image,
        page_number: int = 1,
        tile_index: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> VisionResult:
        """
        Send an image to the vision model and return structured detections.

        context: optional metadata {"project": "...", "ref": "...", "scale_hint": "1:50"}
        """
        context = context or {}
        user_msg = self._build_user_message(context)

        try:
            raw = self._call_provider(self.primary, image, user_msg)
            provider_used = self.primary.value
        except Exception as e:
            logger.warning(f"Primary provider {self.primary} failed: {e}")
            if not self.fallback_enabled:
                raise
            logger.info(f"Falling back to {self.fallback_provider}")
            raw = self._call_provider(self.fallback_provider, image, user_msg)
            provider_used = self.fallback_provider.value

        return self._parse_response(raw, provider_used, page_number, tile_index)

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------

    def _call_provider(
        self,
        provider: VisionProvider,
        image: Image.Image,
        user_message: str,
    ) -> str:
        if provider == VisionProvider.CLAUDE:
            return self._call_claude(image, user_message)
        elif provider == VisionProvider.GEMINI:
            return self._call_gemini(image, user_message)
        raise ValueError(f"Unknown provider: {provider}")

    # ------------------------------------------------------------------
    # Claude (Anthropic)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_claude(self, image: Image.Image, user_message: str) -> str:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)
        img_b64 = _pil_to_base64(image)

        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4000,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": user_message},
                    ],
                }
            ],
        )
        return response.content[0].text

    # ------------------------------------------------------------------
    # Gemini (Google)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_gemini(self, image: Image.Image, user_message: str) -> str:
        import requests
        import io
        import base64
        from engines.api_keys import get_random_gemini_key

        api_key = get_random_gemini_key()

        logger.info("Converting image to JPEG for Gemini API...")
        buf = io.BytesIO()
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image.save(buf, format="JPEG", quality=80)
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": user_message},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json"
            },
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            }
        }

        logger.info("Sending request to Gemini API (raw REST)...")
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
        
        if not resp.ok:
            logger.error(f"Gemini API failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw: str,
        provider_used: str,
        page_number: int,
        tile_index: int | None,
    ) -> VisionResult:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nRaw: {raw[:500]}")
            return VisionResult(
                scale_detected=None,
                scale_confidence=0.0,
                profiles=[],
                unreadable_zones=["entire page — JSON parse failed"],
                warnings=[f"JSON parse error: {e}"],
                drawing_type="unknown",
                raw_response=raw,
                provider_used=provider_used,
                page_number=page_number,
                tile_index=tile_index,
            )

        profiles = []
        for i, p in enumerate(data.get("profiles", [])):
            length_m = p.get("length_m")
            if length_m is None and p.get("length_mm") is not None:
                try:
                    length_m = float(p.get("length_mm")) / 1000.0
                except (ValueError, TypeError):
                    length_m = None
                    
            profiles.append(
                DetectedProfile(
                    id=p.get("id", f"P{i:03d}"),
                    type=p.get("type", "unknown"),
                    designation=p.get("designation", ""),
                    role=p.get("nomenclature", p.get("role", "")),
                    length_m=length_m,
                    quantity=int(p.get("quantity", 1)) if str(p.get("quantity", 1)).isdigit() else 1,
                    zone=p.get("zone", ""),
                    confidence=float(p.get("confidence", 0.5)),
                    bbox_normalized=p.get("bbox_normalized", []),
                )
            )

        return VisionResult(
            scale_detected=data.get("scale_detected"),
            scale_confidence=float(data.get("scale_confidence", 0.0)),
            profiles=profiles,
            unreadable_zones=data.get("unreadable_zones", []),
            warnings=data.get("warnings", []),
            drawing_type=data.get("drawing_type", "unknown"),
            raw_response=raw,
            provider_used=provider_used,
            page_number=page_number,
            tile_index=tile_index,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(context: dict) -> str:
        lines = ["Analyze this structural steel drawing."]
        if context:
            lines.append("\nContext:")
            if "project" in context:
                lines.append(f"- Project: {context['project']}")
            if "ref" in context:
                lines.append(f"- Drawing ref: {context['ref']}")
            if "scale_hint" in context:
                lines.append(f"- Expected scale (from metadata): {context['scale_hint']}")
            if "drawing_type" in context:
                lines.append(f"- Drawing type: {context['drawing_type']}")
        lines.append("\nExtract all visible steel profiles and return the JSON format specified. Nothing else.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Merging tiles
# ---------------------------------------------------------------------------

def merge_tile_results(results: list[VisionResult]) -> VisionResult:
    """
    Consolidate results from multiple tiles of the same page.
    Deduplicates profiles by designation + zone, keeps highest confidence.
    """
    if not results:
        raise ValueError("No results to merge")
    if len(results) == 1:
        return results[0]

    # Use scale from the tile with highest scale_confidence
    best_scale = max(results, key=lambda r: r.scale_confidence)

    all_profiles: list[DetectedProfile] = []
    seen: dict[str, DetectedProfile] = {}

    for result in results:
        for profile in result.profiles:
            key = f"{profile.designation}|{profile.zone}"
            if key not in seen or profile.confidence > seen[key].confidence:
                seen[key] = profile

    all_profiles = list(seen.values())

    all_warnings = []
    all_unreadable = []
    for r in results:
        all_warnings.extend(r.warnings)
        all_unreadable.extend(r.unreadable_zones)

    return VisionResult(
        scale_detected=best_scale.scale_detected,
        scale_confidence=best_scale.scale_confidence,
        profiles=all_profiles,
        unreadable_zones=list(set(all_unreadable)),
        warnings=list(set(all_warnings)),
        drawing_type=results[0].drawing_type,
        raw_response="[merged from tiles]",
        provider_used=results[0].provider_used,
        page_number=results[0].page_number,
        tile_index=None,
    )


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------

def _pil_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
