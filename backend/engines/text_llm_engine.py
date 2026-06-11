import os
import json
import logging
from typing import Any
from pathlib import Path

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
        if self.provider not in ["gemini", "claude", "openrouter", "ollama", "openai"]:
            self.provider = "gemini"

    def analyze(self, text_content: str, context: dict[str, Any] = None, pass_mode: str = "PASS3") -> VisionResult:
        if not context:
            context = {}

        user_msg = f"YOU ARE IN {pass_mode}.\n\n"
        if pass_mode == "PASS3":
            user_msg += "Please execute PASS 3 — MERGE & DEDUPLICATE on the following JSON outputs from previous passes.\n"
        else:
            user_msg += "Please extract the steel profiles from the following drawing text data.\n"

        if context.get("project"):
            user_msg += f"Project: {context['project']}\n"
        if context.get("ref"):
            user_msg += f"Ref: {context['ref']}\n"
        
        user_msg += f"\nData:\n{text_content}"
        
        if context.get("is_stairs"):
            user_msg += "\n\n⚠️ REMEMBER: This is a STAIRS / NON-WAREHOUSE drawing. Merge and preserve all extracted profiles (such as IPE160, UPN160, L50*5, PL150*6, TN platines, etc.) and their quantities. Keep them in the final JSON profiles list."
            
        user_msg += "\n\nCRITICAL: DO NOT STOP EARLY. Return the final unified JSON schema required by the prompt."

        # Fallback chain based on the primary provider
        primary = self.provider
        providers_to_try = [primary]
        
        if primary == "ollama":
            providers_to_try.extend(["openrouter", "gemini"])
        elif primary == "openrouter":
            providers_to_try.extend(["gemini", "openrouter"]) # Try gemini first if openrouter fails
        elif primary == "gemini":
            providers_to_try.extend(["openrouter", "gemini"])
        elif primary == "openai":
            providers_to_try.extend(["gemini", "openrouter"])
            
        raw_json = None
        last_error = None
        used_provider = None

        for prov in providers_to_try:
            try:
                logger.info(f"TextLLMEngine: Trying provider {prov}...")
                if prov == "ollama":
                    raw_json = self._call_ollama_text(user_msg)
                elif prov == "openrouter":
                    raw_json = self._call_openrouter_text(user_msg)
                elif prov == "gemini":
                    raw_json = self._call_gemini_text(user_msg)
                elif prov == "openai":
                    raw_json = self._call_openai_text(user_msg)
                used_provider = prov
                logger.info(f"TextLLMEngine: Successfully extracted using {prov}")
                break
            except Exception as e:
                logger.warning(f"TextLLMEngine: Provider {prov} failed: {e}")
                last_error = e

        if raw_json is None:
            raise RuntimeError(f"All text LLM providers failed! Last error: {last_error}")
            
        # Parse JSON
        if not raw_json or not isinstance(raw_json, str):
            logger.error(f"Invalid raw response from text LLM provider: {raw_json}")
            return VisionResult(
                scale_detected=None,
                scale_confidence=0.0,
                metadata={},
                profiles=[],
                unreadable_zones=["entire page — Text LLM returned empty or invalid response"],
                warnings=[f"Text LLM returned empty or invalid response"],
                drawing_type="unknown",
                raw_response=str(raw_json),
                provider_used=used_provider or "none"
            )

        try:
            data = json.loads(raw_json)
            
            # If the LLM just returned a list of profiles instead of the root object
            if isinstance(data, list):
                data = {"profiles": data}
                
            profiles = []
            for p in data.get("profiles", []):
                if not isinstance(p, dict):
                    continue
                # Standardize keys if LLM used "profile" instead of "designation"
                if "profile" in p and "designation" not in p:
                    p["designation"] = p["profile"]
                if "designation" in p and "type" not in p:
                    # Very simple type inference
                    desig = str(p.get("designation") or "").upper()
                    if "IPE" in desig: p["type"] = "IPE"
                    elif "HEA" in desig: p["type"] = "HEA"
                    elif "HEB" in desig: p["type"] = "HEB"
                    elif "UPN" in desig: p["type"] = "UPN"
                    elif "L" in desig or "CORNI" in desig: p["type"] = "ANGLE"
                    else: p["type"] = "OTHER"
                
                # Robust type parsing
                qty_val = p.get("quantity")
                try:
                    if qty_val is None:
                        qty = 1
                    else:
                        qty = int(float(str(qty_val)))
                except Exception:
                    qty = 1

                conf_val = p.get("confidence")
                try:
                    if conf_val is None:
                        conf = 0.8
                    else:
                        conf = float(conf_val)
                except Exception:
                    conf = 0.8

                len_val = p.get("length_m")
                try:
                    if len_val is not None:
                        len_val = float(len_val)
                except Exception:
                    len_val = None
                
                try:
                    # DetectedProfile is a dataclass, so we pass correct kwargs
                    profiles.append(DetectedProfile(
                        id=p.get("repere") or p.get("id", "P000"),
                        type=p.get("category", p.get("type", "unknown")),
                        designation=p.get("designation") or "",
                        role=p.get("role") or "",
                        length_m=len_val,
                        length_source=p.get("length_source") or "",
                        quantity=qty,
                        quantity_note=p.get("quantity_note") or "",
                        zone=", ".join(p.get("views_confirmed", [])) if "views_confirmed" in p else (p.get("zone") or ""),
                        confidence=conf,
                        bbox_normalized=p.get("bbox_normalized") or []
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
                warns = data.get("warnings", []) or []

            return VisionResult(
                scale_detected=data.get("scale_detected"),
                scale_confidence=float(data.get("scale_confidence", 0.0)),
                metadata=data.get("metadata", {}),
                profiles=profiles,
                unreadable_zones=data.get("unreadable_zones", []),
                warnings=warns,
                drawing_type=data.get("drawing_type", "unknown"),
                raw_response=raw_json,
                provider_used=used_provider
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {raw_json}")
            raise ValueError("LLM did not return valid JSON") from e

    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=6))
    def _call_ollama_text(self, user_msg: str) -> str:
        api_key = os.getenv("OLLAMA_API_KEY")
        if not api_key:
            raise ValueError("OLLAMA_API_KEY not set")
        api_key = api_key.strip()

        import requests
        model = os.getenv("OLLAMA_MODEL", "qwen3-vl:235b-instruct")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": SYSTEM_PROMPT + "\n\n" + user_msg
                }
            ]
        }

        logger.info(f"Sending text request to Ollama API (model: {model})...")
        resp = requests.post(
            "https://ollama.com/api/chat",
            headers=headers,
            json=payload,
            timeout=(30, 240)
        )

        if not resp.ok:
            raise ValueError(f"Ollama API error: {resp.status_code} - {resp.text[:300]}")

        data = resp.json()
        raw_json = data["message"]["content"]
        raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return raw_json

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
        model = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.2-11b-vision-instruct")
        if model and model.endswith(":free"):
            model = model[:-5]
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

    @retry(stop=stop_after_attempt(6), wait=wait_exponential(multiplier=3, min=5, max=30))
    def _call_openai_text(self, user_msg: str) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set")
        api_key = api_key.strip()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        import requests
        logger.info(f"Sending text to OpenAI API (model: {model})...")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_msg
                }
            ]
        }
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=300
        )
        if not resp.ok:
            error_msg = f"OpenAI API failed: {resp.status_code} - {resp.text}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            raise ValueError(f"OpenAI returned empty choices: {data}")
            
        raw_json = data["choices"][0]["message"]["content"]
        raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return raw_json
