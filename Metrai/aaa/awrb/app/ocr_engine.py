import os
import re
import cv2
import numpy as np
from PIL import Image
import pytesseract
from app.config import settings

# Bind local tesseract command path if specified in settings (.env)
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

class OCREngine:
    @staticmethod
    def preprocess_image(image_bytes: bytes) -> np.ndarray:
        """
        Applies OpenCV preprocessing pipeline to make the image OCR-ready:
        1. Decode bytes into OpenCV format
        2. Convert to Grayscale
        3. Upscale (resize) to improve small-text resolution
        4. Apply Otsu's adaptive thresholding for high contrast
        5. Apply minor dilation/erosion to join broken strokes
        """
        # Load image from bytes
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Invalid image bytes provided. Could not decode image.")
            
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Resize to double size for better OCR character recognition
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # De-noise using bilateral filtering (preserves edges better than gaussian)
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Adaptive Thresholding (Otsu binarization)
        thresh = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        
        # If the image has more white pixels than black, invert it (OCR works best on black-on-white)
        white_pixels = np.sum(thresh == 255)
        black_pixels = np.sum(thresh == 0)
        if black_pixels > white_pixels:
            thresh = cv2.bitwise_not(thresh)
            
        return thresh

    @classmethod
    def clean_extracted_text(cls, raw_text: str) -> str:
        """Cleans and translates OCR character misinterpretations into standard SymPy syntax."""
        # Strip whitespaces
        cleaned = raw_text.strip()
        
        # Replace common OCR misreadings of mathematical operators
        replacements = [
            (r'\n', ' '),           # Clear newlines
            (r'×', '*'),            # Multiplication sign
            (r'÷', '/'),            # Division sign
            (r'\[', '('),           # Bracket standardization
            (r'\]', ')'),
            (r'\{', '('),
            (r'\}', ')'),
            (r'o', '0'),            # Letter 'o' instead of zero
            (r'l', '1'),            # Letter 'l' instead of one
            (r'I', '1'),            # Letter 'I' instead of one
            (r'\s+', ' '),          # Double spaces
        ]
        
        for ocr_char, math_char in replacements:
            cleaned = re.sub(ocr_char, math_char, cleaned)
            
        # Strip spacing around mathematical operators
        operators = [r'\+', r'\-', r'\*', r'\/', r'\=']
        for op in operators:
            cleaned = re.sub(rf'\s*{op}\s*', op.replace('\\', ''), cleaned)
            
        return cleaned

    @classmethod
    def extract_expression(cls, image_bytes: bytes) -> Dict[str, Any]:
        """
        Orchestrates the OpenCV + Pytesseract pipeline to recognize and extract math equations.
        Includes a robust fallback mode in case Tesseract isn't configured/installed.
        """
        try:
            # 1. Preprocess using OpenCV
            preprocessed_img = cls.preprocess_image(image_bytes)
            
            # 2. Convert cv2 numpy array back to PIL Image for pytesseract
            pil_img = Image.fromarray(preprocessed_img)
            
            # 3. Apply OCR using Tesseract (configured for math character sets if possible)
            # PSM 6: Assume a single uniform block of text
            custom_config = r'--psm 6'
            
            try:
                raw_text = pytesseract.image_to_string(pil_img, config=custom_config)
                tesseract_available = True
            except (pytesseract.TesseractNotFoundError, Exception) as terr:
                # Tesseract not installed on server, log error and trigger system fallback
                print(f"[OCR ENGINE] Local Tesseract binary not accessible: {str(terr)}")
                raw_text = ""
                tesseract_available = False
            
            cleaned_text = cls.clean_extracted_text(raw_text)
            
            if not tesseract_available:
                return {
                    "success": False,
                    "tesseract_installed": False,
                    "error": "Tesseract OCR binary is missing on this server. Please install 'tesseract-ocr' and configure the binary path in your .env file.",
                    "fallback_message": "Ensure your VPS/Server runs 'apt-get install tesseract-ocr' or set the binary path in Windows (e.g. C:\\Program Files\\Tesseract-OCR\\tesseract.exe)."
                }
                
            if not cleaned_text:
                return {
                    "success": False,
                    "tesseract_installed": True,
                    "error": "OCR processed the image, but could not detect any readable characters.",
                    "steps": ["Ensure the equation is hand-written or printed clearly", "Provide higher contrast lighting", "Avoid skewed or rotated images"]
                }
                
            return {
                "success": True,
                "tesseract_installed": True,
                "raw_text": raw_text.strip(),
                "cleaned_expression": cleaned_text,
                "suggestion": f"We detected: {cleaned_text}. You can solve it or edit it below."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"OCR processing failed: {str(e)}"
            }
