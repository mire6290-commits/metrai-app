import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from engines.pdf_parser import PDFParser
from engines.vision_llm_engine import VisionLLMEngine
from engines.export_engine import ExportEngine
from main import _enrich_profile

def main():
    pdf_path = "C:/Users/Lenovo/Downloads/txt/metrai/01_data_raw/projet_02_PADEL/PLAN.pdf"
    
    print("Initializing PDFParser and VisionLLMEngine...", flush=True)
    parser = PDFParser(dpi=150)
    vision_engine = VisionLLMEngine(provider="gemini")
    
    print(f"Rendering pages from {pdf_path}...", flush=True)
    pages = parser.render_pages(pdf_path)
    
    if not pages:
        print("No pages found.", flush=True)
        return
        
    img = pages[0].image
    # Resize to max 2000px to avoid hanging the Gemini API
    max_size = 2000
    if max(img.width, img.height) > max_size:
        ratio = max_size / max(img.width, img.height)
        new_size = (int(img.width * ratio), int(img.height * ratio))
        print(f"Resizing image from {img.size} to {new_size} to avoid API hang...", flush=True)
        img = img.resize(new_size)

    print(f"Analyzing {len(pages)} page(s) using Vision LLM...", flush=True)
    result = vision_engine.analyze(img, page_number=1, context={"project": "PADEL"})
    
    all_profiles_raw = result.profiles
    print(f"Raw profiles extracted: {len(all_profiles_raw)}")
    
    profiles_out = [_enrich_profile(p) for p in all_profiles_raw]
    data_for_excel = [p.model_dump() for p in profiles_out]
    
    print("Generating Excel...")
    excel_bytes = ExportEngine.to_excel(data_for_excel)
    
    output_path = "C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/output_test_padel_vision.xlsx"
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
        
    print(f"Test run complete! Excel saved to {output_path}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    main()
