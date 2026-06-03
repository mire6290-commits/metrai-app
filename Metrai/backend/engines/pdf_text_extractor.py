"""
pdf_text_extractor.py
Module for extracting raw text and tabular data from structural PDF drawings.
Uses PyMuPDF (fitz) to extract text elements with their layout intact.
"""
from __future__ import annotations

import pdfplumber
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PDFPageText:
    page_number: int
    text_content: str

class PDFTextExtractor:
    """
    Extracts selectable text and perfectly aligned tables from vector-based PDF files using pdfplumber.
    """
    
    def extract_all_pages(self, pdf_path: str) -> list[PDFPageText]:
        """
        Reads the PDF and returns text content + tables for each page.
        """
        logger.info(f"Extracting tables and text from PDF: {pdf_path}")
        results = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_idx, page in enumerate(pdf.pages):
                    text_content = ""
                    
                    # 1. Extract tables as structured Markdown grids
                    tables = page.extract_tables()
                    for t_idx, table in enumerate(tables):
                        text_content += f"\n--- EXTRACTED TABLE {t_idx + 1} ---\n"
                        for row in table:
                            if row: # Skip completely empty rows
                                clean_row = [str(cell).replace('\n', ' ').strip() if cell else "" for cell in row]
                                text_content += " | ".join(clean_row) + "\n"
                        text_content += "--- END TABLE ---\n\n"
                    
                    # 2. Extract remaining text preserving layout (for titles, notes, etc.)
                    layout_text = page.extract_text(layout=True)
                    if layout_text:
                        text_content += "\n--- RAW PAGE TEXT ---\n"
                        text_content += layout_text

                    results.append(PDFPageText(
                        page_number=page_idx + 1,
                        text_content=text_content.strip()
                    ))
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        
        return results

