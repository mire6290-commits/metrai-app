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
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent.parent / "03_prompts" / "system_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}")
        return "You are an expert structural engineer."

SYSTEM_PROMPT = load_system_prompt()



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
    length_source: str = ""
    quantity_note: str = ""
    bbox_normalized: list[float] = field(default_factory=list)


@dataclass
class VisionResult:
    scale_detected: str | None
    scale_confidence: float
    metadata: dict | None
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
    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OLLAMA = "ollama"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class VisionLLMEngine:
    """
    Detects steel profiles in structural drawing images using vision LLMs.
    """

    def __init__(
        self,
        provider: VisionProvider | str | None = None,
        fallback: bool = True,
    ):
        # Priority: explicit arg > env var > default (ollama)
        env_provider = os.getenv("VISION_PROVIDER", "ollama").lower()
        self.primary = VisionProvider(provider or env_provider)
        self.fallback_enabled = fallback
        # Fallback chain based on what keys are available
        fallback_map = {
            VisionProvider.OLLAMA:      VisionProvider.OPENROUTER,
            VisionProvider.OPENROUTER:  VisionProvider.GEMINI,
            VisionProvider.GEMINI:      VisionProvider.OPENROUTER,
            VisionProvider.CLAUDE:      VisionProvider.OPENROUTER,
            VisionProvider.OPENAI:      VisionProvider.OPENROUTER,
        }
        self.fallback_provider = fallback_map.get(self.primary, VisionProvider.OPENROUTER)
        logger.info(f"VisionLLMEngine: primary={self.primary}, fallback={self.fallback_provider if fallback else 'disabled'}")

    def analyze(
        self,
        image: Image.Image,
        page_number: int = 1,
        tile_index: int | None = None,
        context: dict[str, Any] | None = None,
        pass_mode: str = "PASS1"
    ) -> VisionResult:
        context = context or {}
        context["pass_mode"] = pass_mode
        user_msg = self._build_user_message(context)

        try:
            raw = self._call_provider(self.primary, image, user_msg)
            provider_used = self.primary.value
        except Exception as primary_e:
            p_err = primary_e.last_attempt.exception() if hasattr(primary_e, "last_attempt") and primary_e.last_attempt else primary_e
            logger.warning(f"Primary provider {self.primary} failed: {p_err}")
            if not self.fallback_enabled:
                raise RuntimeError(f"Primary provider ({self.primary}) failed and fallback is disabled. Error: {p_err}")
            logger.info(f"Falling back to {self.fallback_provider}")
            try:
                raw = self._call_provider(self.fallback_provider, image, user_msg)
                provider_used = self.fallback_provider.value
            except Exception as fallback_e:
                f_err = fallback_e.last_attempt.exception() if hasattr(fallback_e, "last_attempt") and fallback_e.last_attempt else fallback_e
                raise RuntimeError(f"BOTH providers failed! Primary ({self.primary}) Error: {p_err} | Fallback ({self.fallback_provider}) Error: {f_err}")

        return self._parse_response(raw, provider_used, page_number, tile_index)

    def detect_zones(self, image: Image.Image) -> list[dict]:
        prompt = """
        You are an AI assistant analyzing a structural steel drawing.
        Identify the distinct drawing zones (e.g., "plan de toiture", "élévation pignon", "détail assemblage", "coupe transversale").
        For each zone, provide its type and a normalized bounding box [ymin, xmin, ymax, xmax] where values are floats between 0.0 and 1.0.
        Return ONLY a JSON array of objects, e.g.:
        [
            {"zone_type": "plan de toiture", "bbox_normalized": [0.0, 0.0, 0.5, 1.0]},
            {"zone_type": "élévation pignon", "bbox_normalized": [0.5, 0.0, 1.0, 0.5]},
            {"zone_type": "détail assemblage", "bbox_normalized": [0.5, 0.5, 1.0, 1.0]}
        ]
        If the entire page is a single drawing or you cannot segment it clearly, return a single zone with [0.0, 0.0, 1.0, 1.0].
        """
        try:
            raw = self._call_provider(self.primary, image, prompt)
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            zones = json.loads(clean)
            if not isinstance(zones, list) or len(zones) == 0:
                zones = [{"zone_type": "full_page", "bbox_normalized": [0.0, 0.0, 1.0, 1.0]}]
            return zones
        except Exception as e:
            logger.warning(f"Failed to detect zones: {e}")
            return [{"zone_type": "full_page", "bbox_normalized": [0.0, 0.0, 1.0, 1.0]}]

    def _call_provider(
        self,
        provider: VisionProvider,
        image: Image.Image,
        prompt: str,
    ) -> str:
        if provider == VisionProvider.CLAUDE:
            return self._call_claude(image, prompt)
        elif provider == VisionProvider.GEMINI:
            return self._call_gemini(image, prompt)
        elif provider == VisionProvider.OPENAI:
            return self._call_openai(image, prompt)
        elif provider == VisionProvider.OPENROUTER:
            return self._call_openrouter(image, prompt)
        elif provider == VisionProvider.OLLAMA:
            return self._call_ollama(image, prompt)
        else:
            raise ValueError(f"Unknown provider: {provider}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_claude(self, image: Image.Image, user_message: str) -> str:
        import anthropic
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=api_key)
        img_copy = image.copy()
        img_copy.thumbnail((6000, 6000))
        img_b64 = _pil_to_base64(img_copy)
        response = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}}, {"type": "text", "text": user_message}]}],
        )
        return response.content[0].text

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=4, max=20))
    def _call_gemini(self, image: Image.Image, user_message: str) -> str:
        import requests
        from engines.api_keys import get_random_gemini_key
        api_key = get_random_gemini_key()
        img_copy = image.copy()
        img_copy.thumbnail((6000, 6000))
        buf = io.BytesIO()
        if img_copy.mode in ('RGBA', 'P'): img_copy = img_copy.convert('RGB')
        img_copy.save(buf, format="JPEG", quality=80)
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": user_message}, {"inline_data": {"mime_type": "image/jpeg", "data": b64_data}}]}], "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"}, "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]}}
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=300)
        if not resp.ok:
            error_msg = f"Gemini API failed: {resp.status_code} - {resp.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        data = resp.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            raise ValueError(f"Unexpected Gemini response format: {data}") from e
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openrouter(self, image: Image.Image, user_message: str) -> str:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        api_key = api_key.strip()  # Strip newlines or spaces to prevent header errors
        
        import requests
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-11b-vision-instruct:free")
        img_copy = image.copy()
        img_copy.thumbnail((6000, 6000))
        img_b64 = _pil_to_base64(img_copy)
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "max_tokens": 3000, "messages": [{"role": "user", "content": [{"type": "text", "text": SYSTEM_PROMPT + "\n\n" + user_message}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}]}]}
        logger.info(f"Sending request to OpenRouter API (model: {model})...")
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=300)
        if not resp.ok:
            error_msg = f"OpenRouter API failed: {resp.status_code} - {resp.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"OpenRouter returned empty choices: {data}")
        return data["choices"][0]["message"]["content"]

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=4, max=15))
    def _call_ollama(self, image: Image.Image, user_message: str) -> str:
        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY not set")
        api_key = api_key.strip()

        import requests
        model = os.getenv("OLLAMA_MODEL", "llama3.2-vision")

        # Small image = faster inference = less timeout
        img_copy = image.copy()
        img_copy.thumbnail((768, 768))
        img_b64 = _pil_to_base64(img_copy)

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        # Native Ollama format (original working endpoint)
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": SYSTEM_PROMPT + "\n\n" + user_message,
                    "images": [img_b64]
                }
            ]
        }

        logger.info(f"Sending request to Ollama API (model: {model})...")
        resp = requests.post(
            "https://ollama.com/api/chat",
            headers=headers,
            json=payload,
            timeout=(30, 240)
        )

        if not resp.ok:
            raise ValueError(f"Ollama API error: {resp.status_code} - {resp.text[:300]}")

        try:
            data = resp.json()
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"]
            raise ValueError(f"Unexpected Ollama response format: {data}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Ollama JSON parse error: {e}")


    def _parse_response(
        self,
        raw: str,
        provider_used: str,
        page_number: int,
        tile_index: int | None,
    ) -> VisionResult:
        # ── Robust JSON extractor ──────────────────────────────────────────
        # Handles: <think>…</think>, ```json … ```, plain text before/after
        import re as _re
        text = raw

        # 1. Strip <think>…</think> blocks (Ollama / DeepSeek chain-of-thought)
        text = _re.sub(r'<think>.*?</think>', '', text, flags=_re.DOTALL).strip()

        # 2. Strip markdown fences
        text = text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        # 3. Extract from first '{' to last '}'
        start = text.find('{')
        end   = text.rfind('}')
        if start != -1 and end != -1 and end > start:
            clean = text[start:end+1]
        else:
            clean = text
        # ──────────────────────────────────────────────────────────────────

        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nRaw (first 600): {raw[:600]}")
            return VisionResult(
                scale_detected=None,
                scale_confidence=0.0,
                metadata={},
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
            profiles.append(DetectedProfile(
                id=p.get("repere") or p.get("id", f"P{i:03d}"),
                type=p.get("category", p.get("type", "unknown")),
                designation=p.get("designation", ""),
                role=p.get("role", ""),
                length_m=p.get("length_m"),
                length_source=p.get("length_source", ""),
                quantity=int(p.get("quantity") or 1),
                quantity_note=p.get("quantity_note", ""),
                zone=", ".join(p.get("views_confirmed", [])) if "views_confirmed" in p else p.get("zone", ""),
                confidence=float(p.get("confidence", 0.5)),
                bbox_normalized=p.get("bbox_normalized", [])
            ))

        verif = data.get("verification", {})
        warns = []
        if isinstance(verif, dict):
            for w in verif.get("warnings", []):
                if isinstance(w, dict):
                    warns.append(f"{w.get('code', '')}: {w.get('message', '')} ({w.get('affected_repere', '')})")
                else:
                    warns.append(str(w))
            for a in verif.get("a_valider", []):
                if isinstance(a, dict):
                    warns.append(f"A_VALIDER: {a.get('element', '')} - {a.get('reason', '')}")
        else:
            warns = data.get("warnings", [])

        return VisionResult(
            scale_detected=data.get("scale_detected"),
            scale_confidence=float(data.get("scale_confidence", 0.0)),
            metadata=data.get("metadata", {}),
            profiles=profiles,
            unreadable_zones=data.get("unreadable_zones", []),
            warnings=warns,
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
        lines = []
        pass_mode = context.get("pass_mode", "PASS1")
        lines.append(f"YOU ARE IN {pass_mode}.")
        
        if context:
            lines.append("\nContext:")
            if "project" in context:
                lines.append(f"- Project: {context['project']}")
            if "ref" in context:
                lines.append(f"- Drawing ref: {context['ref']}")
            if "scale_hint" in context:
                lines.append(f"- Expected scale: {context['scale_hint']}")
            
        lines.append("\nExtract ALL steel profiles visible in this drawing image. Return ONLY valid JSON as specified for this PASS. No explanation, no markdown, just JSON.")
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
            # Include length_m in the key so we don't merge profiles of different lengths!
            # Use rounding to avoid float precision issues.
            l_str = f"{profile.length_m:.3f}" if profile.length_m else "None"
            key = f"{profile.designation}|{l_str}|{profile.zone}"
            
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
        metadata=results[0].metadata if results else {},
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
    if image.mode in ('RGBA', 'P'):
        image = image.convert('RGB')
    image.save(buf, format="JPEG", quality=85)
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
