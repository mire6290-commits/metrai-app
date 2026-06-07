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
from typing import Any, Optional, Dict
import uuid
import asyncio

TASKS_STORE: Dict[str, dict] = {}

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
    _parser = PDFParser(dpi=int(os.getenv("RENDER_DPI", "300")))
    provider = os.getenv("VISION_PROVIDER", "claude")
    _vision = VisionLLMEngine(fallback=True)
    _llamaparse = LlamaParseEngine()
    _text_llm = TextLLMEngine(provider=provider)
    logger.info("Engines ready — provider: %s", provider)

from fastapi.responses import JSONResponse
from fastapi.requests import Request
import traceback

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    from tenacity import RetryError
    
    error_msg = str(exc)
    if isinstance(exc, RetryError):
        underlying = exc.last_attempt.exception() if exc.last_attempt else None
        error_msg = f"RetryError -> {type(underlying).__name__}: {str(underlying)}"
        
    logger.error(f"Global error: {error_msg}\n{traceback.format_exc()}")
    return JSONResponse(
        status_code=400,
        content={"detail": error_msg},
        headers={"Access-Control-Allow-Origin": "*"}
    )



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
    surface_peinture_m2: float | None = None
    methode: str | None = None


class ExtractionResponse(BaseModel):
    project: str
    filename: str
    pages_processed: int
    scale_detected: str | None
    drawing_type: str
    metadata: dict | None = None
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
        import fitz
        doc = fitz.open(str(tmp_path))
        total_pages_pdf = len(doc)
        doc.close()
        
        if total_pages_pdf == 0:
            raise HTTPException(status_code=400, detail="No valid pages found")

        context = {
            "project": project,
            "ref": file.filename,
            "scale_hint": scale_hint or "unknown",
        }

        all_results: list[VisionResult] = []

        if mode == 'text':
            logger.info("Using LlamaParse + TextLLMEngine for direct PDF text extraction.")
            md_text = _llamaparse.parse_to_markdown(str(tmp_path))
            res = _text_llm.analyze(md_text, context)
            all_results.append(res)
        else:
            # Agentic Zoning Architecture
            logger.info("Using VisionLLMEngine with Agentic Zoning.")
            _parser.dpi = 150 # Prevent Streamlit Cloud OOM crash on large drawings
            
            import fitz
            doc = fitz.open(str(tmp_path))
            num_pages = len(doc)
            doc.close()
            
            if pages != "all":
                requested = {int(p.strip()) for p in pages.split(",")}
            else:
                requested = set(range(1, num_pages + 1))
                
            for page_num in sorted(list(requested)):
                if page_num < 1 or page_num > num_pages:
                    continue
                page_img = _parser.render_page(str(tmp_path), page_num)
                # 3-PASS Agentic Zoning Architecture
                logger.info(f"Applying 3-Pass Architecture for page {page_img.page_number}...")
                
                # --- PASS 1: Main Structure (Full Page) ---
                logger.info(f"Executing PASS 1 on full page...")
                ctx1 = context.copy()
                ctx1["zone_type"] = "full_page"
                res1 = _vision.analyze(page_img.image, page_number=page_img.page_number, tile_index=0, context=ctx1, pass_mode="PASS1")
                
                # --- PASS 2: Accessories (Quadrants) ---
                zones = [
                    {"zone_type": "quadrant_top_left", "bbox_normalized": [0.0, 0.0, 0.55, 0.55]},
                    {"zone_type": "quadrant_top_right", "bbox_normalized": [0.0, 0.45, 0.55, 1.0]},
                    {"zone_type": "quadrant_bottom_left", "bbox_normalized": [0.45, 0.0, 1.0, 0.55]},
                    {"zone_type": "quadrant_bottom_right", "bbox_normalized": [0.45, 0.45, 1.0, 1.0]},
                ]
                
                pass2_jsons = []
                img_w, img_h = page_img.image.size
                
                for z_idx, zone in enumerate(zones):
                    zt = zone.get("zone_type", "unknown")
                    y_min, x_min, y_max, x_max = zone.get("bbox_normalized", [0.0, 0.0, 1.0, 1.0])
                    
                    left, right = min(x_min, x_max) * img_w, max(x_min, x_max) * img_w
                    top, bottom = min(y_min, y_max) * img_h, max(y_min, y_max) * img_h
                    
                    padding_x, padding_y = int(img_w * 0.05), int(img_h * 0.05)
                    box_px = (
                        max(0, int(left) - padding_x), max(0, int(top) - padding_y),
                        min(img_w, int(right) + padding_x), min(img_h, int(bottom) + padding_y)
                    )
                    
                    logger.info(f"Executing PASS 2 on {zt}...")
                    crop_img = page_img.image.crop(box_px)
                    ctx2 = context.copy()
                    ctx2["zone_type"] = zt
                    
                    await asyncio.sleep(4.5) # Prevent rate limits
                    res2 = _vision.analyze(crop_img, page_number=page_img.page_number, tile_index=z_idx+1, context=ctx2, pass_mode="PASS2")
                    pass2_jsons.append(res2.raw_response)
                
                # --- PASS 3: Merge & Deduplicate ---
                logger.info(f"Executing PASS 3 (Merge & Deduplicate) for page {page_img.page_number}...")
                pass3_payload = f"PASS1_JSON:\\n{res1.raw_response}\\n\\nPASS2_JSONS:\\n" + "\\n---\\n".join(pass2_jsons)
                
                ctx3 = context.copy()
                ctx3["zone_type"] = "merge"
                
                try:
                    await asyncio.sleep(4.5)
                    merged_res = _text_llm.analyze(pass3_payload, context=ctx3, pass_mode="PASS3")
                    all_results.append(merged_res)
                except Exception as e:
                    logger.error(f"PASS 3 Failed: {e}. Falling back to Python merge.")
                    # Fallback to Python merge if PASS 3 fails
                    zone_results = [res1]
                    # We don't have the parsed pass2 objects here easily, so we just use res1
                    all_results.append(res1)


        if not all_results:
            raise HTTPException(status_code=422, detail="No profiles extracted — check PDF and API keys")

        # Merge across pages
        all_profiles_raw = []
        all_warnings = []
        all_unreadable = []
        scale_detected = None
        drawing_type = "unknown"
        provider_used = "none"
        final_metadata = {}

        for r in all_results:
            if hasattr(r, 'metadata') and r.metadata:
                final_metadata.update(r.metadata)
            all_profiles_raw.extend(r.profiles)
            all_warnings.extend(r.warnings)
            all_unreadable.extend(r.unreadable_zones)
            if r.scale_detected and not scale_detected:
                scale_detected = r.scale_detected
            if r.drawing_type != "unknown":
                drawing_type = r.drawing_type
            provider_used = r.provider_used

        # Cross-page deduplication by explicit Repère
        deduped_profiles_raw = []
        seen_reperes = {}
        for p in all_profiles_raw:
            rep = (p.repere or "").strip().upper()
            # P000 or unknown are placeholders from LLM, don't dedup them purely by repere
            if rep and rep not in ["", "P000", "UNKNOWN", "NONE", "N/A"]:
                if rep in seen_reperes:
                    existing = seen_reperes[rep]
                    existing.views_confirmed = list(set(existing.views_confirmed + p.views_confirmed))
                    # Take the max quantity in case different pages saw partial quantities or one saw the total multiplier
                    existing.quantity = max(existing.quantity, p.quantity)
                else:
                    seen_reperes[rep] = p
                    deduped_profiles_raw.append(p)
            else:
                # Without a strict repère, we rely on the LLM's per-page PASS3 deduplication
                deduped_profiles_raw.append(p)

        # Enrich with RulesDB (masse linéaire from EN tables)
        profiles_out = [_enrich_profile(p) for p in deduped_profiles_raw]

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
            metadata=final_metadata,
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


@app.post('/extract_async')
async def extract_async(
    file: UploadFile = File(...),
    mode: str = Form('vision'),
    pages: str = Form('all'),
    scale_hint: str = Form(''),
    project: str = Form(''),
    ref: str = Form('')
):
    task_id = str(uuid.uuid4())
    TASKS_STORE[task_id] = {'status': 'processing'}
    
    file_bytes = await file.read()
    filename = file.filename
    
    async def process_task():
        import tempfile
        from pathlib import Path
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file_bytes)
                tmp_path = Path(tmp.name)
            
            try:
                context = {
                    'project': project,
                    'ref': filename,
                    'scale_hint': scale_hint or 'unknown',
                }

                all_results = []
                
                if mode == 'text':
                    logger.info("Using LlamaParse + TextLLMEngine for direct PDF text extraction (Async).")
                    md_text = _llamaparse.parse_to_markdown(str(tmp_path))
                    res = _text_llm.analyze(md_text, context)
                    all_results.append(res)
                else:
                    logger.info("Using VisionLLMEngine with Agentic Zoning (Async).")
                    _parser.dpi = 300
                    page_images = _parser.render_pages(str(tmp_path))
                    if pages != "all":
                        requested = {int(p.strip()) for p in pages.split(",")}
                        page_images = [p for p in page_images if p.page_number in requested]

                    for page_img in page_images:
                        logger.info(f"Applying mathematical grid tiling for page {page_img.page_number}...")
                        zones = [
                            {"zone_type": "full_page", "bbox_normalized": [0.0, 0.0, 1.0, 1.0]},
                            {"zone_type": "quadrant_top_left", "bbox_normalized": [0.0, 0.0, 0.55, 0.55]},
                            {"zone_type": "quadrant_top_right", "bbox_normalized": [0.0, 0.45, 0.55, 1.0]},
                            {"zone_type": "quadrant_bottom_left", "bbox_normalized": [0.45, 0.0, 1.0, 0.55]},
                            {"zone_type": "quadrant_bottom_right", "bbox_normalized": [0.45, 0.45, 1.0, 1.0]},
                        ]
                        
                        zone_results = []
                        img_w, img_h = page_img.image.size
                        
                        for z_idx, zone in enumerate(zones):
                            zt = zone.get("zone_type", "unknown")
                            bbox = zone.get("bbox_normalized", [0.0, 0.0, 1.0, 1.0])
                            if not isinstance(bbox, list) or len(bbox) != 4:
                                bbox = [0.0, 0.0, 1.0, 1.0]
                            
                            y_min, x_min, y_max, x_max = bbox
                            
                            # Defensive check against hallucinated coordinates
                            left = min(x_min, x_max) * img_w
                            right = max(x_min, x_max) * img_w
                            top = min(y_min, y_max) * img_h
                            bottom = max(y_min, y_max) * img_h
                            
                            box_px = (
                                int(left),
                                int(top),
                                int(right),
                                int(bottom)
                            )
                            padding_x = int(img_w * 0.05)
                            padding_y = int(img_h * 0.05)
                            box_px = (
                                max(0, box_px[0] - padding_x),
                                max(0, box_px[1] - padding_y),
                                min(img_w, box_px[2] + padding_x),
                                min(img_h, box_px[3] + padding_y)
                            )
                            
                            crop_img = page_img.image.crop(box_px)
                            ctx = context.copy()
                            ctx["zone_type"] = zt
                            
                            res = _vision.analyze(crop_img, page_number=page_img.page_number, tile_index=z_idx, context=ctx)
                            zone_results.append(res)
    
                        if zone_results:
                            merged = merge_tile_results(zone_results)
                            all_results.append(merged)
    
                    if not all_results:
                        TASKS_STORE[task_id] = {'status': 'error', 'detail': 'No profiles extracted'}
                        return
    
                    all_profiles_raw = []
                    all_warnings = []
                    all_unreadable = []
                    scale_detected = None
                    drawing_type = 'unknown'
                    provider_used = 'none'
    
                    for r in all_results:
                        all_profiles_raw.extend(r.profiles)
                        all_warnings.extend(r.warnings)
                        all_unreadable.extend(r.unreadable_zones)
                    if r.scale_detected and not scale_detected:
                        scale_detected = r.scale_detected
                    if r.drawing_type != 'unknown':
                        drawing_type = r.drawing_type
                    provider_used = r.provider_used

                profiles_out = [_enrich_profile(p) for p in all_profiles_raw]
                total_weight = sum(p.poids_total_kg for p in profiles_out if p.poids_total_kg is not None)
                needs_review = sum(1 for p in profiles_out if p.confidence < 0.7)

                final_res = ExtractionResponse(
                    project=project,
                    filename=filename,
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
                TASKS_STORE[task_id] = {'status': 'done', 'result': final_res.model_dump()}

            finally:
                tmp_path.unlink(missing_ok=True)
                
        except Exception as e:
            import traceback
            logger.error(f"Task {task_id} failed: {e}")
            TASKS_STORE[task_id] = {"status": "error", "detail": traceback.format_exc()}

    asyncio.create_task(process_task())
    return {'task_id': task_id}

@app.get('/extract_status/{task_id}')
async def extract_status(task_id: str):
    if task_id not in TASKS_STORE:
        raise HTTPException(status_code=404, detail='Task not found')
    return TASKS_STORE[task_id]


class ExportRequest(BaseModel):
    data: list[dict]
    project_name: str = "METRAI EXPERT"
    metadata: dict | None = None

@app.post("/export/excel")
async def export_excel(req: ExportRequest):
    from engines.export_engine import ExportEngine
    excel_bytes = ExportEngine.to_excel(req.data)
    headers = {
        'Content-Disposition': 'attachment; filename="Metre_Automatique.xlsx"'
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.post("/export/excel/advanced")
async def export_excel_advanced(req: ExportRequest):
    from engines.export_engine import ExportEngine
    excel_bytes = ExportEngine.to_excel_advanced(req.data, req.project_name, metadata=req.metadata)
    headers = {
        'Content-Disposition': 'attachment; filename="Metre_Avance.xlsx"'
    }
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.get("/profiles/catalog")
async def profile_catalog():
    """Return the EN profile table (masse linéaire kg/m) for reference."""
    return {"profiles": _RULES_DB}


# ---------------------------------------------------------------------------
# RulesDB — Catalogue et Règles de calcul
# ---------------------------------------------------------------------------
from catalogue import CATALOGUE_PROFILS, CATALOGUE_BOULONNERIE, CATALOGUE_TOLES_KG_M2
import re
import math

def _enrich_profile(p: Any) -> ProfileOut:
    """Look up masse linéaire and compute poids total from RulesDB."""
    designation = p.designation.upper().strip()
    designation = designation.replace("CORNIÈRE", "").replace("CORNIERE", "").replace("RONDELLE", "RON").replace("ECROU", "ECR").strip()
    
    # Format "IPE400" to "IPE 400" to match RulesDB
    designation = re.sub(r'^([A-Z]+)(\d+)', r'\1 \2', designation)
    
    # Fix 'X' or 'x' instead of '*' in L or 2L profiles (e.g. "L 60X6" -> "L 60*6")
    designation = re.sub(r'(L|2L)\s*(\d+)\s*[X]\s*(\d+)', r'\1 \2*\3', designation)
    
    masse = CATALOGUE_PROFILS.get(designation)
    methode = "Catalogue" if masse is not None else None
    
    # Fallback to check if it's L A*A*T
    if not masse and designation.startswith('L '):
        masse = CATALOGUE_PROFILS.get(designation.replace(' ', ''))
        if masse:
            methode = "Catalogue"
        else:
            # handle L 60*6
            l_match = re.match(r'L\s*(\d+)\*(\d+)', designation)
            if l_match:
                masse = CATALOGUE_PROFILS.get(f"L {l_match.group(1)}*{l_match.group(1)}*{l_match.group(2)}")
                if masse:
                    methode = "Catalogue"
                else:
                    # Calcul Cornière
                    a = float(l_match.group(1))
                    e = float(l_match.group(2))
                    masse = round((2 * a - e) * e * 0.00785, 2)
                    methode = "Calcul"
            
            # handle L 80*40*6
            l_ineg_match = re.match(r'L\s*(\d+)\*(\d+)\*(\d+)', designation)
            if l_ineg_match and not methode:
                a, b, e = map(float, l_ineg_match.groups())
                if a == b:
                    masse = round((2 * a - e) * e * 0.00785, 2)
                else:
                    masse = round((a + b - e) * e * 0.00785, 2)
                methode = "Calcul"

    # RONDS PLEINS (RD)
    d_match = re.search(r'(?:RD|R|ROND|⌀)\s*(\d+)', designation, re.IGNORECASE)
    if d_match and not masse:
        d = float(d_match.group(1))
        masse_cat = CATALOGUE_PROFILS.get(f"RD {int(d)}")
        if masse_cat:
            masse = masse_cat
            methode = "Catalogue"
        else:
            masse = round((d**2) * 0.006165, 3)
            methode = "Calcul"

    # TUBES Ronds et Carrés/Rectangulaires
    tube_match = re.search(r'(?:SHS|RHS|CHS|TUBE|TU|TR|□|⌀).*?(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)(?:\s*[xX\*]\s*(\d+(?:\.\d+)?))?', designation, re.IGNORECASE)
    perimeter_m = None  # Pour la peinture
    
    if tube_match and not masse:
        val1 = float(tube_match.group(1))
        val2 = float(tube_match.group(2))
        val3 = tube_match.group(3)
        
        is_carre = bool(re.search(r'(C|CARR|TC|SHS|□)', designation, re.IGNORECASE))
        is_rond = bool(re.search(r'(R|ROND|TR|CHS|⌀)', designation, re.IGNORECASE))
        
        if val3 and not is_rond:
            # Tube Rect / Carré: A x B x E
            a, b, e = val1, val2, float(val3)
            masse = round(2 * (a + b - 2*e) * e * 0.00785, 2)
            perimeter_m = 2 * (a + b) / 1000.0
            methode = "Calcul"
        elif is_carre or (val1 == val2 and not val3): # if only 2 values and it's square
            # Tube Carré (A x E): A x A x E
            a, e = val1, val2
            masse = round(4 * (a - e) * e * 0.00785, 2)
            perimeter_m = 4 * a / 1000.0
            methode = "Calcul"
        else:
            # Tube Rond: Dia x E
            d, e = val1, val2
            masse = round(math.pi * (d - e) * e * 0.00785, 2)
            perimeter_m = (math.pi * d) / 1000.0
            methode = "Calcul"

    try:
        l_float = float(p.length_m) if p.length_m is not None else 0.0
    except:
        l_float = 0.0
        
    length_val = l_float # Do not fallback to 1.0! If length is missing, keep it 0.0 so Excel shows ----
    try:
        q_int = int(p.quantity) if getattr(p, 'quantity', None) is not None else 0
    except:
        q_int = 0
    qty_val = q_int if q_int > 0 else 1

    poids = None
    poids_unitaire = None
    surface_peinture = None
    
    # BOULONNERIE
    boulon_match = re.search(r'(?:BOU|BOULON|M)\s*(\d+)\s*[xX\*]\s*(\d+)', designation, re.IGNORECASE)
    if boulon_match:
        d_boulon = boulon_match.group(1)
        l_boulon = boulon_match.group(2)
        boulon_key = f"M{d_boulon}*{l_boulon}"
        pu_boulon = CATALOGUE_BOULONNERIE.get(boulon_key)
        if pu_boulon:
            poids_unitaire = pu_boulon
            methode = "Catalogue"
            poids = round(poids_unitaire * qty_val, 2)
            masse = None
            length_val = None

    # TÔLES PLQ / TL
    tole_match = re.search(r'(?:PLQ|TL|TOLE).*?(\d+)\s*[xX\*]\s*(\d+)\s*[xX\*]\s*(\d+)', designation, re.IGNORECASE)
    if tole_match and not methode:
        long_plq, larg_plq, ep_plq = map(float, tole_match.groups())
        poids_unitaire = round((long_plq/1000) * (larg_plq/1000) * ep_plq * 7.85, 2)
        poids = round(poids_unitaire * qty_val, 2)
        methode = "Calcul"
        masse = None
        length_val = None

    if masse is not None and not boulon_match and not tole_match:
        poids = round(masse * length_val * qty_val, 2)
        
    # Check for PL, TN, PLATINE, GOUSSET, RAIDISSEUR A*B*C
    pl_match = re.search(r'(?:PLT|TN|PLAT|GOUSSET|RAID).*?(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)', designation, re.IGNORECASE)
    fer_plat_match = re.search(r'(?:FER\s*PLAT|PL).*?(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)', designation, re.IGNORECASE)
    
    if pl_match and not boulon_match and not tole_match:
        a, b, c = map(float, pl_match.groups())
        # Volume en m3 * 7850 kg/m3 (Densité exacte acier)
        poids_unitaire = round((a/1000) * (b/1000) * (c/1000) * 7850, 3)
        poids = round(poids_unitaire * qty_val, 2)
        methode = "Calcul"
        # Peinture pour les platines (les 2 faces principales)
        surface_peinture = round(2 * (a * b) / 1000000.0 * qty_val, 2)
        length_val = None # Ensure length is hidden for plates
        masse = None
    elif fer_plat_match and not masse and not boulon_match and not tole_match:
        # Fer Plat: Width x Thickness (e.g. PL 150x6)
        width, thickness = map(float, fer_plat_match.groups())
        # masse linéaire kg/m
        masse_val = width * thickness * 0.00785
        masse = round(masse_val, 3)
        poids = round(masse * length_val * qty_val, 2)
        methode = "Calcul"
        # Surface peinture: perimeter of cross section * length
        perimeter_m = 2 * (width + thickness) / 1000.0
        if length_val > 0:
            surface_peinture = round(perimeter_m * length_val * qty_val, 2)

    # Calcul de la surface de peinture pour les profilés (formules approchées Mémotech)
    if not perimeter_m and not pl_match and not boulon_match and not tole_match:
        if "IPE" in designation:
            m = re.search(r'IPE\s*(\d+)', designation)
            if m:
                h = float(m.group(1))
                perimeter_m = (4 * h) / 1000.0 * 0.95
        elif "HE" in designation:
            m = re.search(r'HE[ABM]\s*(\d+)', designation)
            if m:
                h = float(m.group(1))
                b_val = min(h, 300.0)
                perimeter_m = (2 * h + 4 * b_val) / 1000.0 * 0.95
        elif "UPN" in designation or "UPE" in designation:
            m = re.search(r'UP[NE]\s*(\d+)', designation)
            if m:
                h = float(m.group(1))
                b_val = h / 3.0 + 10
                perimeter_m = (2 * h + 4 * b_val) / 1000.0 * 0.9
        elif "L " in designation:
            m = re.search(r'L\s*(\d+)\s*\*\s*(\d+)', designation)
            if m:
                perimeter_m = 2 * (float(m.group(1)) + float(m.group(2))) / 1000.0
                
    if perimeter_m and length_val is not None and length_val > 0:
        surface_peinture = round(perimeter_m * length_val * qty_val, 2)

    out = ProfileOut(
        id=getattr(p, 'repere', None) or getattr(p, 'id', 'P00'),
        designation=getattr(p, 'designation', '').strip().upper(), # Keep original designation from AI (e.g. IPE160 instead of IPE 160)
        type=getattr(p, 'category', getattr(p, 'type', 'unknown')),
        role=getattr(p, 'role', ''),
        length_m=length_val,
        quantity=qty_val,
        zone=getattr(p, 'zone', getattr(p, 'views_confirmed', [''])[0] if getattr(p, 'views_confirmed', None) else ''),
        confidence=p.confidence,
        masse_lineaire_kg_m=masse,
        poids_unitaire=poids_unitaire,
        poids_total_kg=poids,
        surface_peinture_m2=surface_peinture,
        methode=methode if methode else "Inconnu",
    )
    return out