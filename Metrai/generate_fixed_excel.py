import sys
import os
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from backend.engines.export_engine import ExportEngine
from backend.engines.vision_llm_engine import DetectedProfile
from backend.main import _enrich_profile

json_data = [
  {"profile": "UPN80", "quantity": 88},
  {"profile": "L50*5", "quantity": 53},
  {"profile": "IPE400", "quantity": 40},
  {"profile": "HEA120", "quantity": 20},
  {"profile": "IPE270", "quantity": 8},
  {"profile": "IPE180", "quantity": 4},
  {"profile": "IPE140", "quantity": 14},
  {"profile": "L70*7", "quantity": 20},
  {"profile": "IPE450", "quantity": 2},
  {"profile": "UPN200", "quantity": 1}
]

def main():
    profiles = []
    for p in json_data:
        # Standardize keys if LLM used "profile" instead of "designation"
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
        
        # We assume 1 meter length if length is not provided by LLM to calculate weight
        length_m = 1.0
        
        profiles.append(DetectedProfile(
            id=p.get("id", "P000"),
            type=p.get("type", "unknown"),
            designation=p.get("designation", ""),
            length_m=length_m,
            quantity=int(p.get("quantity", 1)),
            zone=p.get("zone", "File Principale"),
            confidence=0.9,
            bbox_normalized=[]
        ))

    profiles_out = [_enrich_profile(p) for p in profiles]
    data_for_excel = [p.model_dump() for p in profiles_out]
    
    excel_bytes = ExportEngine.to_excel(data_for_excel)
    
    output_path = "C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/output_test_padel_llamaparse_v2.xlsx"
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
        
    print(f"Test run complete! Excel saved to {output_path}")

if __name__ == "__main__":
    main()
