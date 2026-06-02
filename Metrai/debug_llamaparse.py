import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))
from backend.engines.llamaparse_engine import LlamaParseEngine

def main():
    engine = LlamaParseEngine()
    pdf_path = "C:/Users/Lenovo/Downloads/txt/metrai/01_data_raw/projet_02_PADEL/PLAN.pdf"
    
    print("Uploading to LlamaParse...")
    markdown = engine.parse_to_markdown(pdf_path)
    
    with open("C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/llamaparse_debug.md", "w", encoding="utf-8") as f:
        f.write(markdown)
        
    print("Saved to llamaparse_debug.md")

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "backend", ".env"))
    main()
