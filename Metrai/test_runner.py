import os
import asyncio
from pathlib import Path
from backend.engines.export_engine import ExportEngine
from backend.engines.vision_llm_engine import VisionLLMEngine
from backend.engines.pdf_parser import PDFParser
from backend.main import _enrich_profile

async def main():
    pdf_path = "C:/Users/Lenovo/Downloads/txt/metrai/01_data_raw/projet_02_PADEL/PLAN.pdf"
    
    # Init engines
    parser = PDFParser(dpi=150)
    vision = VisionLLMEngine(fallback=True)
    
    print(f"Rendering pages from {pdf_path}...")
    page_images = parser.render_pages(pdf_path)
    if not page_images:
        print("No pages found!")
        return

    all_results = []
    context = {"project": "PADEL", "ref": "PLAN.pdf", "scale_hint": "unknown"}

    # Process first page only for the test to save time and API costs
    page_img = page_images[0]
    print(f"Processing page {page_img.page_number}...")
    
    if parser.should_tile(page_img):
        print("Tiling large page...")
        tiles = parser.tile_page(page_img)
        tile_results = []
        for t in tiles:
            res = vision.analyze(
                t.image,
                page_number=t.page_number,
                tile_index=t.tile_index,
                context={**context, "tile": t.tile_index}
            )
            tile_results.append(res)
        
        from backend.engines.vision_llm_engine import merge_tile_results
        merged = merge_tile_results(tile_results)
        all_results.append(merged)
    else:
        res = vision.analyze(page_img.image, page_number=page_img.page_number, context=context)
        all_results.append(res)

    all_profiles_raw = []
    for r in all_results:
        all_profiles_raw.extend(r.profiles)

    # Enrich profiles
    profiles_out = [_enrich_profile(p) for p in all_profiles_raw]
    
    # Convert models to dict for Excel export
    data_for_excel = [p.dict() for p in profiles_out]
    
    print(f"Extracted {len(data_for_excel)} profiles. Generating Excel...")
    
    # Generate Excel
    excel_bytes = ExportEngine.to_excel(data_for_excel)
    
    output_path = "C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/output_test_padel.xlsx"
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
        
    print(f"Test run complete! Excel saved to {output_path}")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv("C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/backend/.env")
    asyncio.run(main())
