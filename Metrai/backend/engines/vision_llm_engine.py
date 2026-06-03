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

SYSTEM_PROMPT = """You are an expert structural engineer specialized in steel construction (charpente métallique). You analyze technical drawings — plans, elevations, sections — and extract steel profiles and connection elements with maximum precision.

When given an image of a structural drawing, you MUST:
1. Identify ALL steel elements visible, including the main structure (IPE, HEA, HEB, UPN, tubes, cornières) AND connection pieces (Platines, Raidisseurs, Goussets, Jarrets, Liernes, Bracons, Tiges d'ancrage, Echantignoles). Look for designations starting with PL or TN (e.g. TN300*300*20).
2. Read the exact profile/plate designation from annotations (e.g. "IPE 400", "HEA 300", "L70*70*7", "D14", "TN120*100*8").
3. Determine the ROLE (Famille) of each element. This must be a single UPPERCASE word (in French) chosen from this list: POTEAU, POTELET, TRAVERSE, PANNE, SABLIERE, CONTREVENTEMENT, LIERNE, SUPPORT, BRACON, PLATINE, RAIDISSEUR, GOUSSET, JARRET, ECHANTIGNOLE, TIGE.
4. Set the `role` field exactly to this UPPERCASE family name. Do not invent names like "LONGITUDINAL BAY".
5. CRITICAL LENGTH: Read the EXACT length (longueur) in millimeters from the dimension lines (cotations). Convert to meters for length_m (e.g. 5930 -> 5.93). If it's a plate (e.g., TN300*300*20), extract length from the designation or assume no length_m if inapplicable.
6. Return ONLY valid JSON — absolutely no prose, no markdown, no backticks.

Output format (strict):
{
  "scale_detected": "1:50",
  "scale_confidence": 0.95,
  "profiles": [
    {
      "id": "P001",
      "type": "IPE",
      "designation": "IPE 400",
      "role": "POTEAU",
      "length_m": 4.0,
      "quantity": 14,
      "zone": "File A",
      "confidence": 0.92,
      "bbox_normalized": [0.12, 0.34, 0.45, 0.38]
    }
  ],
  "unreadable_zones": [],
  "warnings": [],
  "drawing_type": "plan de charpente | coupe | détail | unknown"
}

Rules:
- CRITICAL QUANTITY RULE: Calculate the GLOBAL quantity for the entire structure shown. If a view says "Portique File 1 à 7", multiply the visible elements by 7. Pay attention to symmetrical parts and labels like "14 IPE400". Output the TOTAL final quantity.
- Do NOT output English terms. Use strict French terminology.
- `role` must be the generic Family name (POTEAU, TRAVERSE, PLATINE...). Do NOT use specific locations like "Files A1-A7" for the role.
- Platines/Tôles (TN/PL): Put the full size (e.g. TN300*300*20) in `designation`.
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
            model="claude-opus-4-6",
            max_tokens=2000,
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

        profiles = [
            DetectedProfile(
                id=p.get("id", f"P{i:03d}"),
                type=p.get("type", "unknown"),
                designation=p.get("designation", ""),
                role=p.get("role", ""),
                length_m=p.get("length_m"),
                quantity=int(p.get("quantity", 1)),
                zone=p.get("zone", ""),
                confidence=float(p.get("confidence", 0.5)),
                bbox_normalized=p.get("bbox_normalized", []),
            )
            for i, p in enumerate(data.get("profiles", []))
        ]

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
