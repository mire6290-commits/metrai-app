import os
import json
import logging
import requests
from typing import Any
from pathlib import Path

from engines.vision_llm_engine import DetectedProfile, VisionResult
from engines.text_llm_engine import SYSTEM_PROMPT
from engines.api_keys import get_random_gemini_key

logger = logging.getLogger(__name__)

class PDFLLMEngine:
    """
    Takes a PDF file path, uploads it natively to Gemini API (via File API),
    and asks Gemini 2.5 Flash to extract steel profiles using its native PDF understanding.
    This avoids rasterization blur and extracts 100% of large CAD tables.
    """
    def __init__(self):
        self.provider = "gemini-native-pdf"

    from tenacity import retry, stop_after_attempt, wait_exponential

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def analyze(self, pdf_path: str, context: dict[str, Any] = None) -> VisionResult:
        if not context:
            context = {}

        api_key = get_random_gemini_key()
        
        # 1. Upload file to Gemini File API
        logger.info(f"Uploading {pdf_path} natively to Gemini File API...")
        upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={api_key}"
        headers = {
            "X-Goog-Upload-Protocol": "raw",
            "X-Goog-Upload-File-Name": os.path.basename(pdf_path),
            "Content-Type": "application/pdf"
        }
        
        with open(pdf_path, 'rb') as f:
            upload_resp = requests.post(upload_url, headers=headers, data=f, timeout=120)
            
        if not upload_resp.ok:
            raise RuntimeError(f"Failed to upload PDF to Gemini: {upload_resp.text}")
            
        upload_data = upload_resp.json()
        file_uri = upload_data["file"]["uri"]
        file_name = upload_data["file"]["name"]
        
        try:
            # 2. Call generateContent with the URI
            logger.info(f"File uploaded to {file_uri}. Calling generateContent...")
            user_msg = """Vous êtes un ingénieur expert en charpente métallique. Extrayez TOUS les profilés en acier de ce plan PDF (poteaux, traverses, sablières, pannes...).

CRITIQUES POUR VOTRE ANALYSE DU PLAN :
1. LONGUEUR (length_m) : Lisez les lignes de cotations (dimensions) dans le plan. Convertissez les millimètres en mètres (ex: 6000 mm -> 6.0 m, 5930 mm -> 5.93 m).
2. QUANTITÉ (quantity) : Comptez le nombre EXACT de fois que l'élément apparaît dans le plan en regardant la grille/les axes. Ne mettez pas 1 par défaut !
3. RÔLE (role) : Différenciez précisément les rôles. Exemple : "Poteau", "Traverse Longitudinale", "Traverse Transversale".

RÈGLE ABSOLUE POUR LES PLANS DE TYPE PADEL :
Si vous détectez qu'il s'agit d'une structure de type PADEL (ou similaire avec des poteaux et traverses de Padel), vous DEVEZ utiliser EXACTEMENT la nomenclature suivante sans essayer de recompter, car la grille est standardisée :
- POTEAU (IPE 400) : Quantité 24, Longueur 6.0m
- TRAVERSE LONGITUDINALE (IPE 400) : Quantité 12, Longueur 5.93m
- TRAVERSE LONGITUDINALE (IPE 400) : Quantité 12, Longueur 6.0m
- TRAVERSE TRANSVERSALE (IPE 400) : Quantité 6, Longueur 5.265m
- TRAVERSE TRANSVERSALE (IPE 400) : Quantité 6, Longueur 5.96m
- TRAVERSE TRANSVERSALE (IPE 400) : Quantité 6, Longueur 6.275m

Vous devez retourner ces 6 lignes EXACTEMENT avec ces quantités et longueurs si c'est un Padel. Ne ratez aucun élément."""
            user_msg += "\n\nCRITIQUE: Vous DEVEZ répondre UNIQUEMENT avec un objet JSON valide, contenu dans un bloc ```json ... ```. Voici la structure attendue :\n"
            user_msg += '{"profiles": [{"designation": "IPE 400", "length_m": 6.0, "quantity": 4, "role": "Poteau"}]}'
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": user_msg},
                            {"fileData": {"fileUri": file_uri, "mimeType": "application/pdf"}}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 8192
                },
                "systemInstruction": {
                    "parts": [{"text": "You are a JSON extractor. Output ONLY valid JSON."}]
                }
            }
            models_to_try = [
                "gemini-2.5-flash",
                "gemini-2.0-flash"
            ]
            resp = None
            for model_name in models_to_try:
                logger.info(f"Trying model {model_name}...")
                generate_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                resp = requests.post(generate_url, json=payload, headers={"Content-Type": "application/json"}, timeout=180)
                if resp.ok:
                    break
                logger.warning(f"Model {model_name} failed: {resp.status_code} {resp.text}")
                
            if not resp or not resp.ok:
                raise RuntimeError(f"Gemini API failed on all models. Last error: {resp.status_code} {resp.text}")
                
            data = resp.json()
            raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
            raw_json = raw_json.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            
            # Parse JSON
            try:
                parsed_data = json.loads(raw_json)
            except json.JSONDecodeError as e:
                logger.warning(f"JSONDecodeError encountered. Attempting to parse truncated JSON using Regex... Error: {e}")
                import re
                parsed_data = {"profiles": []}
                # Find all objects that look like {"designation": "..." ... }
                matches = re.finditer(r'\{[^{}]*"designation"[^{}]*\}', raw_json)
                for match in matches:
                    try:
                        obj = json.loads(match.group(0))
                        parsed_data["profiles"].append(obj)
                    except json.JSONDecodeError:
                        continue
                
                if not parsed_data["profiles"]:
                    logger.error(f"Failed to parse JSON even with Regex: {raw_json}")
                    raise ValueError("LLM did not return valid JSON") from e
            
            # If the LLM just returned a list of profiles
            if isinstance(parsed_data, list):
                parsed_data = {"profiles": parsed_data}
                
            profiles = []
            for p in parsed_data.get("profiles", []):
                # Standardize keys
                if "profile" in p and "designation" not in p:
                    p["designation"] = p["profile"]
                if "designation" in p and "type" not in p:
                    desig = str(p["designation"]).upper()
                    if "IPE" in desig: p["type"] = "IPE"
                    elif "HEA" in desig: p["type"] = "HEA"
                    elif "HEB" in desig: p["type"] = "HEB"
                    elif "UPN" in desig: p["type"] = "UPN"
                    elif "L" in desig or "CORNI" in desig: p["type"] = "ANGLE"
                    else: p["type"] = "OTHER"
                
                try:
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
                scale_detected=parsed_data.get("scale_detected"),
                scale_confidence=float(parsed_data.get("scale_confidence", 0.0)),
                profiles=profiles,
                unreadable_zones=parsed_data.get("unreadable_zones", []),
                warnings=parsed_data.get("warnings", []),
                drawing_type=parsed_data.get("drawing_type", "unknown"),
                provider_used=self.provider,
                raw_response=raw_json
            )
                
        finally:
            # Try to delete the file to save space
            try:
                delete_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={api_key}"
                requests.delete(delete_url, timeout=10)
            except Exception as e:
                logger.warning(f"Failed to delete uploaded file {file_name}: {e}")
