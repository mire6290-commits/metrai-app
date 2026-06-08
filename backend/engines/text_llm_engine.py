import os
import json
import logging
from typing import Any
from pathlib import Path
from pydantic import BaseModel, ValidationError

# We keep the same data schema
from engines.vision_llm_engine import DetectedProfile, VisionResult

logger = logging.getLogger(__name__)

def load_system_prompt() -> str:
    prompt_path = Path(__file__).parent.parent.parent / "03_prompts" / "system_prompt.txt"
    try:
        return prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to load system prompt: {e}")
        return "You are an expert structural engineer extracting steel profiles..."

SYSTEM_PROMPT = load_system_prompt()

class TextLLMEngine:
    """
    Takes Markdown text (e.g. from LlamaParse) and extracts steel profiles.
    """
    def __init__(self, provider: str = "gemini"):
        self.provider = provider.lower()
        self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-latest")
        if self.provider not in ["gemini", "claude", "openrouter"]:
            self.provider = "gemini"

    def analyze(self, text_content: str, context: dict[str, Any] = None, pass_mode: str = "PASS3") -> VisionResult:
        if not context:
            context = {}

        user_msg = f"YOU ARE IN {pass_mode}.\\n\\n"
        if pass_mode == "PASS3":
            user_msg += "Please execute PASS 3 — MERGE & DEDUPLICATE on the following JSON outputs from previous passes.\\n"
        else:
            user_msg += "Please extract the steel profiles from the following drawing text data.\\n"

        if context.get("project"):
            user_msg += f"Project: {context['project']}\\n"
        if context.get("ref"):
            user_msg += f"Ref: {context['ref']}\\n"
        
        user_msg += f"\\nData:\\n{text_content}"
        user_msg += "\\n\\nCRITICAL: DO NOT STOP EARLY. Return the final unified JSON schema required by the prompt."

        if self.provider == "openrouter":
            raw_json = self._call_openrouter_text(user_msg)
        else:
            raw_json = self._call_gemini_text(user_msg)
            
        # Parse JSON
        try:
            data = json.loads(raw_json)
            
            # If the LLM just returned a list of profiles instead of the root object
            if isinstance(data, list):
                data = {"profiles": data}
                
            profiles = []
            for p in data.get("profiles", []):
                # Standardize keys if LLM used "profile" instead of "designation"
                if "profile" in p and "designation" not in p:
                    p["designation"] = p["profile"]
                if "designation" in p and "type" not in p:
                    # Very simple type inference
                    desig = str(p["designation"]).upper()
                    if "IPE" in desig: p["type"] = "IPE"
                    elif "HEA" in desig: p["type"] = "HEA"
                    elif "HEB" in desig: p["type"] = "HEB"
                    elif "UPN" in desig: p["type"] = "UPN"
                    elif "L" in desig or "CORNI" in desig: p["type"] = "ANGLE"
                    else: p["type"] = "OTHER"
                
                try:
                    # DetectedProfile is a dataclass, so we pass kwargs
                    profiles.append(DetectedProfile(
                        repere=p.get("repere") or p.get("id", "P000"),
                        category=p.get("category", p.get("type", "unknown")),
                        designation=p.get("designation", ""),
                        role=p.get("role", ""),
                        length_m=p.get("length_m"),
                        length_source=p.get("length_source", ""),
                        dims_mm=p.get("dims_mm"),
                        quantity=int(p.get("quantity") or 1),
                        quantity_note=p.get("quantity_note", ""),
                        poids_lineaire_kg_m=p.get("poids_lineaire_kg_m"),
                        poids_total_kg=p.get("poids_total_kg"),
                        views_confirmed=p.get("views_confirmed", []),
                        detail_ref=p.get("detail_ref"),
                        notes=p.get("notes"),
                        confidence=float(p.get("confidence", 0.8)),
                        bbox_normalized=p.get("bbox_normalized", [])
                    ))
                except Exception as e:
                    logger.warning(f"Skipping invalid profile: {e}")
                    
            verif = data.get("verification", {})
            warns = []
            if isinstance(verif, dict):
                for w in verif.get("warnings", []):
                    if isinstance(w, dict):
                        warns.append(f"{w.get('code', '')}: {w.get('message', '')} ({w.get('affected_repere', '')})")
                    else:
                        warns.append(str(w))
            else:
                warns = data.get("warnings", [])

            return VisionResult(
                scale_detected=data.get("scale_detected"),
                scale_confidence=float(data.get("scale_confidence", 0.0)),
                metadata=data.get("metadata", {}),
                building_dimensions=data.get("building_dimensions"),
                profiles=profiles,
                verification=data.get("verification"),
                summary=data.get("summary"),
                raw_response=raw_json,
                provider_used=self.provider
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {raw_json}")
            raise ValueError("LLM did not return valid JSON") from e

    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_gemini_text(self, user_msg: str) -> str:
        import requests
        from engines.api_keys import get_random_gemini_key
        api_key = get_random_gemini_key()
            
        logger.info(f"Sending text to Gemini (raw REST)... Using key ending in {api_key[-4:]}")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": user_msg}]}],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 8192,
                "responseMimeType": "application/json"
            },
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            }
        }
        
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=300)
        if not resp.ok:
            logger.error(f"Gemini API failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()
            
        data = resp.json()
        raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
        raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return raw_json


    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_openrouter_text(self, user_msg: str) -> str:
        import requests, os
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        api_key = api_key.strip()
        model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
        logger.info(f"Sending text to OpenRouter API (model: {model})...")
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {"model": model, "max_tokens": 3000, "messages": [{"role": "user", "content": [{"type": "text", "text": SYSTEM_PROMPT + "\n\n" + user_msg}]}]}
        resp = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=300)
        if not resp.ok:
            error_msg = f"OpenRouter API failed: {resp.status_code} - {resp.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"OpenRouter returned empty choices: {data}")
        raw_json = data["choices"][0]["message"]["content"]
        raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return raw_json
