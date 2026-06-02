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
        if self.provider not in ["gemini", "claude"]:
            self.provider = "gemini"

    def analyze(self, text_content: str, context: dict[str, Any] = None) -> VisionResult:
        if not context:
            context = {}

        user_msg = "Please extract the steel profiles from the following drawing text data.\n\n"
        if context.get("project"):
            user_msg += f"Project: {context['project']}\n"
        if context.get("ref"):
            user_msg += f"Ref: {context['ref']}\n"
        
        user_msg += f"\nData:\n{text_content}"

        if self.provider == "claude":
            import anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise EnvironmentError("ANTHROPIC_API_KEY not set")
            client = anthropic.Anthropic(api_key=api_key)
            logger.info("Sending text to Claude...")
            
            # For JSON mode in Anthropic, we ask it to return JSON
            sys_prompt = SYSTEM_PROMPT + "\n\nYou must return ONLY a JSON object."
            response = client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=4096,
                temperature=0.0,
                system=sys_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_msg
                    }
                ]
            )
            raw_json = response.content[0].text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        else:
            import google.generativeai as genai
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise EnvironmentError("GEMINI_API_KEY not set")
                
            genai.configure(api_key=api_key)
            generation_config = genai.types.GenerationConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
            model = genai.GenerativeModel(
                model_name="gemini-flash-latest",
                generation_config=generation_config,
                system_instruction=SYSTEM_PROMPT,
            )
            
            logger.info("Sending text to Gemini...")
            response = model.generate_content(user_msg)
            raw_json = response.text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            logger.info(f"Raw JSON from LLM: {raw_json}")
        
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
                        id=p.get("id", "P000"),
                        type=p.get("type", "unknown"),
                        designation=p.get("designation", ""),
                        role=p.get("role", ""),
                        length_m=p.get("length_m"),
                        quantity=int(p.get("quantity", 1)),
                        zone=p.get("zone", ""),
                        confidence=float(p.get("confidence", 0.8)),
                        bbox_normalized=p.get("bbox_normalized", [])
                    ))
                except Exception as e:
                    logger.warning(f"Skipping invalid profile: {e}")
                    
            return VisionResult(
                scale_detected=data.get("scale_detected"),
                scale_confidence=float(data.get("scale_confidence", 0.0)),
                profiles=profiles,
                unreadable_zones=data.get("unreadable_zones", []),
                warnings=data.get("warnings", []),
                drawing_type=data.get("drawing_type", "unknown"),
                provider_used=self.provider,
                raw_response=raw_json
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {raw_json}")
            raise ValueError("LLM did not return valid JSON") from e
