"""
pdf_parser.py
Converts PDF pages to PIL Images for vision AI processing.
Uses PyMuPDF (fitz) — faster and more accurate than pdf2image for technical drawings.
"""
from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

import fitz  # PyMuPDF
from PIL import Image


@dataclass
class PageImage:
    """One rendered page from a PDF."""
    page_number: int          # 1-based
    image: Image.Image
    width_px: int
    height_px: int
    dpi: int
    source_path: str


@dataclass
class TileImage:
    """A sub-region (tile) of a page, for large drawings."""
    page_number: int
    tile_index: int
    image: Image.Image
    origin_x: int             # pixel offset within original page
    origin_y: int
    source_path: str


class PDFParser:
    """
    Renders PDF pages to PIL Images.

    Strategy
    --------
    - DPI 150  →  fast preview, low API cost (good for Regex fallback check)
    - DPI 200  →  production quality, recommended for vision AI
    - DPI 300  →  high-detail drawings (very small annotations, dense plans)

    Tiling
    ------
    Large A1/A0 plans at 200 DPI can exceed 4000×2800 px.
    Vision models have a token budget — tiling at 1024×1024 px with
    128 px overlap ensures annotations near tile edges are not missed.
    """

    DEFAULT_DPI = 200
    TILE_SIZE = 1024
    TILE_OVERLAP = 128

    def __init__(self, dpi: int = DEFAULT_DPI):
        self.dpi = dpi

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render_pages(self, pdf_path: str | Path) -> list[PageImage]:
        """Render all pages of a PDF to PIL Images."""
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        pages: list[PageImage] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            pil_img = self._page_to_pil(page)
            pages.append(PageImage(
                page_number=page_num + 1,
                image=pil_img,
                width_px=pil_img.width,
                height_px=pil_img.height,
                dpi=self.dpi,
                source_path=str(pdf_path),
            ))

        doc.close()
        return pages

    def render_page(self, pdf_path: str | Path, page_number: int) -> PageImage:
        """Render a single page (1-based index)."""
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        page = doc[page_number - 1]
        pil_img = self._page_to_pil(page)
        doc.close()
        return PageImage(
            page_number=page_number,
            image=pil_img,
            width_px=pil_img.width,
            height_px=pil_img.height,
            dpi=self.dpi,
            source_path=str(pdf_path),
        )

    def tile_page(self, page_img: PageImage) -> list[TileImage]:
        """
        Slice a PageImage into overlapping tiles.
        Use when the page is wider/taller than TILE_SIZE.
        """
        img = page_img.image
        w, h = img.size
        tiles: list[TileImage] = []
        step = self.TILE_SIZE - self.TILE_OVERLAP
        tile_idx = 0

        y = 0
        while y < h:
            x = 0
            while x < w:
                box = (
                    x,
                    y,
                    min(x + self.TILE_SIZE, w),
                    min(y + self.TILE_SIZE, h),
                )
                tile_img = img.crop(box)
                tiles.append(TileImage(
                    page_number=page_img.page_number,
                    tile_index=tile_idx,
                    image=tile_img,
                    origin_x=x,
                    origin_y=y,
                    source_path=page_img.source_path,
                ))
                tile_idx += 1
                x += step
            y += step

        return tiles

    def should_tile(self, page_image: PageImage) -> bool:
        """
        Determine if an image is too large and should be split into overlapping tiles.
        For current Gemini models, sending the whole image is preferred to avoid 
        Quota Limits (5 RPM), as the model can handle large resolutions natively.
        """
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _page_to_pil(self, page: fitz.Page) -> Image.Image:
        """Render a fitz page to a PIL Image (RGB)."""
        zoom = self.dpi / 72.0   # fitz default is 72 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        return Image.open(io.BytesIO(img_bytes)).convert("RGB")

    @staticmethod
    def pil_to_bytes(image: Image.Image, fmt: str = "PNG") -> bytes:
        """Convert a PIL Image to raw bytes (for API calls)."""
        buf = io.BytesIO()
        image.save(buf, format=fmt)
        return buf.getvalue()
