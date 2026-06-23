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
    Extracts text from vector-based PDF files. Fast extraction to measure text density.
    """
    
    def extract_all_pages(self, pdf_path: str) -> list[PDFPageText]:
        logger.info(f"Extracting raw text from PDF: {pdf_path}")
        results = []
        try:
            doc = fitz.open(pdf_path)
            for page_idx in range(len(doc)):
                page = doc[page_idx]
                text = page.get_text("text", sort=True)
                results.append(PDFPageText(
                    page_number=page_idx + 1,
                    text_content=text.strip()
                ))
            doc.close()
        except Exception as e:
            logger.error(f"Error extracting text from PDF {pdf_path}: {e}")
        
        return results

