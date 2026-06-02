"""
pdf_text_extractor.py
Module for extracting raw text and tabular data from structural PDF drawings.
Uses PyMuPDF (fitz) to extract text elements with their layout intact.
"""
from __future__ import annotations

import fitz  # PyMuPDF
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class PDFPageText:
    page_number: int
    text_content: str

class PDFTextExtractor:
    """
    Extracts selectable text from vector-based PDF files.
    """
    
    def extract_all_pages(self, pdf_path: str) -> list[PDFPageText]:
        """
        Reads the PDF and returns text content for each page.
        """
        logger.info(f"Extracting raw text from PDF: {pdf_path}")
        results = []
        try:
            doc = fitz.open(pdf_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                # Extract text preserving physical layout as much as possible
                text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES)
                results.append(PDFPageText(
                    page_number=page_idx + 1,
                    text_content=text.strip()
                ))
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        
        return results

