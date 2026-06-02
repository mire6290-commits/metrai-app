"""
main.py
FastAPI backend for SaaS Métré Automatisé.

Extraction pipeline (hybrid):
  1. Rule-based / Regex on DXF text entities (fast, free, ~70% of cases)
  2. Vision LLM on PDF page images (accurate, ~$0.01–0.05 per page)
  3. RulesDB enrichment: merge kimiya, poids/ml from EN profile tables
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from engines.pdf_parser import PDFParser
from engines.vision_llm_engine import VisionLLMEngine, VisionResult, merge_tile_results
from engines.llamaparse_engine import LlamaParseEngine
from engines.text_llm_engine import TextLLMEngine

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Métré Automatisé API",
    description="Extract steel profiles from structural drawings using Vision AI",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singletons (initialized once at startup)
_parser: PDFParser | None = None
_vision: VisionLLMEngine | None = None
_llamaparse: LlamaParseEngine | None = None
_text_llm: TextLLMEngine | None = None


@app.on_event("startup")
async def startup():
    global _parser, _vision, _llamaparse, _text_llm
    _parser = PDFParser(dpi=int(os.getenv("RENDER_DPI", "200")))
    provider = os.getenv("VISION_PROVIDER", "claude")
    _vision = VisionLLMEngine(fallback=True)
    _llamaparse = LlamaParseEngine()
    _text_llm = TextLLMEngine(provider=provider)
    logger.info("Engines ready — provider: %s", provider)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class ProfileOut(BaseModel):
    id: str
    designation: str
    type: str
    role: str
    length_m: float | None
    quantity: int
    zone: str
    confidence: float
    # Enriched from RulesDB
    masse_lineaire_kg_m: float | None = None
    poids_unitaire: Optional[float] = None
    poids_total_kg: float | None = None


class ExtractionResponse(BaseModel):
    project: str
    filename: str
    pages_processed: int
    scale_detected: str | None
    drawing_type: str
    profiles: list[ProfileOut]
    unreadable_zones: list[str]
    warnings: list[str]
    provider_used: str
    total_weight_kg: float
    needs_review_count: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "provider": os.getenv("VISION_PROVIDER", "claude")}


@app.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(..., description="PDF of the structural drawing"),
    project: str = Form(default="unknown", description="Project name"),
    scale_hint: str = Form(default="", description="Expected scale e.g. '1:50' (optional)"),
    pages: str = Form(default="all", description="'all' or comma-separated page numbers e.g. '1,2,3'"),
    mode: str = Form(default="vision", description="'vision' | 'regex' | 'hybrid'"),
):
    """
    Extract steel profiles from a structural drawing PDF.

    Modes
    -----
    - vision  : Vision LLM only (most accurate, higher cost)
    - regex   : Rule-based only (fast, free, lower accuracy on complex drawings)
    - hybrid  : Regex first; Vision LLM for low-confidence or missing results (recommended)
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Save upload to temp file
    tmp_path = Path(f"/tmp/{file.filename}")
    content = await file.read()
    tmp_path.write_bytes(content)

    try:
        # Determine pages to process
        page_images = _parser.render_pages(str(tmp_path))
        if pages != "all":
            requested = {int(p.strip()) for p in pages.split(",")}
            page_images = [p for p in page_images if p.page_number in requested]

        if not page_images:
            raise HTTPException(status_code=400, detail="No valid pages found")

        context = {
            "project": project,
            "ref": file.filename,
            "scale_hint": scale_hint or "unknown",
        }

        all_results: list[VisionResult] = []

        if mode == "llamaparse" or mode == "hybrid":
            logger.info("Parsing PDF with LlamaParse...")
            markdown_content = _llamaparse.parse_to_markdown(str(tmp_path))
            # Pass markdown to Text LLM (Gemini 2.5)
            result = _text_llm.analyze(markdown_content, context=context)
            all_results.append(result)
        else:
            for page_img in page_images:
                if mode == "regex":
                    # Regex-only: use existing AIEngine (not shown, kept as-is)
                    logger.info("Regex mode — page %d", page_img.page_number)
                    continue

                # Vision path
                if _parser.should_tile(page_img):
                    logger.info("Page %d is large — tiling", page_img.page_number)
                    tiles = _parser.tile_page(page_img)
                    tile_results = [
                        _vision.analyze(
                            t.image,
                            page_number=t.page_number,
                            tile_index=t.tile_index,
                            context={**context, "tile": t.tile_index},
                        )
                        for t in tiles
                    ]
                    merged = merge_tile_results(tile_results)
                    all_results.append(merged)
                else:
                    result = _vision.analyze(
                        page_img.image,
                        page_number=page_img.page_number,
                        context=context,
                    )
                    all_results.append(result)

        if not all_results:
            raise HTTPException(status_code=422, detail="No profiles extracted — check PDF and API keys")

        # Merge across pages
        all_profiles_raw = []
        all_warnings = []
        all_unreadable = []
        scale_detected = None
        drawing_type = "unknown"
        provider_used = "none"

        for r in all_results:
            all_profiles_raw.extend(r.profiles)
            all_warnings.extend(r.warnings)
            all_unreadable.extend(r.unreadable_zones)
            if r.scale_detected and not scale_detected:
                scale_detected = r.scale_detected
            if r.drawing_type != "unknown":
                drawing_type = r.drawing_type
            provider_used = r.provider_used

        # Enrich with RulesDB (masse linéaire from EN tables)
        profiles_out = [_enrich_profile(p) for p in all_profiles_raw]

        total_weight = sum(
            p.poids_total_kg for p in profiles_out if p.poids_total_kg is not None
        )
        needs_review = sum(1 for p in profiles_out if p.confidence < 0.7)

        return ExtractionResponse(
            project=project,
            filename=file.filename,
            pages_processed=len(all_results),
            scale_detected=scale_detected,
            drawing_type=drawing_type,
            profiles=profiles_out,
            unreadable_zones=list(set(all_unreadable)),
            warnings=list(set(all_warnings)),
            provider_used=provider_used,
            total_weight_kg=round(total_weight, 2),
            needs_review_count=needs_review,
        )

    finally:
        tmp_path.unlink(missing_ok=True)


from fastapi import Response

class ExportRequest(BaseModel):
    data: list[dict]

@app.post("/export/excel")
async def export_excel(req: ExportRequest):
    from engines.export_engine import ExportEngine
    excel_bytes = ExportEngine.to_excel(req.data)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=metrai_export.xlsx"}
    )

@app.get("/profiles/catalog")
async def profile_catalog():
    """Return the EN profile table (masse linéaire kg/m) for reference."""
    return {"profiles": _RULES_DB}


# ---------------------------------------------------------------------------
# RulesDB — EN 10034 / EN 10279 masse linéaire (kg/m)
# ---------------------------------------------------------------------------
# Extend this dict with all profiles from the EN tables.
# Source: ArcelorMittal sections catalogue.

_RULES_DB: dict[str, float] = {
    # IPE
    "IPE 80": 6.00, "IPE 100": 8.10, "IPE 120": 10.40, "IPE 140": 12.90,
    "IPE 160": 15.80, "IPE 180": 18.80, "IPE 200": 22.40, "IPE 220": 26.20,
    "IPE 240": 30.70, "IPE 270": 36.10, "IPE 300": 42.20, "IPE 330": 49.10,
    "IPE 360": 57.10, "IPE 400": 66.30, "IPE 450": 77.60, "IPE 500": 90.70,
    "IPE 550": 106.0, "IPE 600": 122.0,
    # HEA
    "HEA 100": 16.70, "HEA 120": 19.90, "HEA 140": 24.70, "HEA 160": 30.40,
    "HEA 180": 35.50, "HEA 200": 42.30, "HEA 220": 50.50, "HEA 240": 60.30,
    "HEA 260": 68.20, "HEA 280": 76.40, "HEA 300": 88.30, "HEA 320": 97.60,
    "HEA 340": 105.0, "HEA 360": 112.0, "HEA 400": 125.0, "HEA 450": 140.0,
    "HEA 500": 155.0, "HEA 600": 178.0,
    # HEB
    "HEB 100": 20.40, "HEB 120": 26.70, "HEB 140": 33.70, "HEB 160": 42.60,
    "HEB 180": 51.20, "HEB 200": 61.30, "HEB 220": 71.50, "HEB 240": 83.20,
    "HEB 260": 93.00, "HEB 280": 103.0, "HEB 300": 117.0, "HEB 320": 127.0,
    "HEB 340": 134.0, "HEB 360": 142.0, "HEB 400": 155.0, "HEB 500": 187.0,
    # UPN
    "UPN 80": 8.64, "UPN 100": 10.60, "UPN 120": 13.40, "UPN 140": 16.00,
    "UPN 160": 18.80, "UPN 180": 22.00, "UPN 200": 25.30, "UPN 220": 29.40,
    "UPN 240": 33.20, "UPN 260": 37.90, "UPN 280": 41.80, "UPN 300": 46.20,
    "UPN 320": 59.50, "UPN 350": 60.60, "UPN 380": 63.10, "UPN 400": 71.80,
    # COR / L
    "L 50*50*5": 3.77, "L 60*60*6": 5.42, "L 70*70*7": 7.38, "L 80*80*8": 9.66,
}


import re

def _enrich_profile(p: Any) -> ProfileOut:
    """Look up masse linéaire and compute poids total from RulesDB."""
    designation = p.designation.upper().strip()
    
    # Format "IPE400" to "IPE 400" to match RulesDB
    designation = re.sub(r'^([A-Z]+)(\d+)', r'\1 \2', designation)
    
    masse = _RULES_DB.get(designation)
    
    # Fallback to check if it's L A*A*T
    if not masse and designation.startswith('L '):
        masse = _RULES_DB.get(designation.replace(' ', ''))

    import math
    d_match = re.match(r'D\s*(\d+)', designation)
    if d_match and not masse:
        d = float(d_match.group(1))
        masse = round(math.pi * (d**2) / 4000000 * 7850, 2)

    poids = None
    if masse is not None and p.length_m is not None:
        poids = round(masse * p.length_m * p.quantity, 2)
        
    # Check for PL A*B*C
    pl_match = re.match(r'PL\s*(\d+)\*(\d+)\*(\d+)', designation)
    poids_unitaire = None
    if pl_match:
        a, b, c = map(float, pl_match.groups())
        # Volume en m3 * 7850 kg/m3
        poids_unitaire = round((a * b * c / 1e9) * 7850, 2)
        if p.quantity:
            poids = round(poids_unitaire * p.quantity, 2)

    out = ProfileOut(
        id=p.id,
        designation=designation, # Return the formatted one
        type=p.type,
        role=getattr(p, 'role', ''),
        length_m=p.length_m,
        quantity=p.quantity,
        zone=p.zone,
        confidence=p.confidence,
        masse_lineaire_kg_m=masse,
        poids_unitaire=poids_unitaire,
        poids_total_kg=poids,
    )
    return out
