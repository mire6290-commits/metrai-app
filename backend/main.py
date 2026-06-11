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
from pydantic import BaseModel

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

from engines.pdf_parser import PDFParser
from engines.vision_llm_engine import VisionLLMEngine, VisionResult, merge_tile_results, DetectedProfile
from engines.llamaparse_engine import LlamaParseEngine
from engines.text_llm_engine import TextLLMEngine


# ---------------------------------------------------------------------------
# FILES = VIEWS — Python-level deduplication (safety net over LLM PASS 3)
# ---------------------------------------------------------------------------

def _deduplicate_profiles(profiles: list[DetectedProfile]) -> list[DetectedProfile]:
    """
    In Moroccan charpente plans, the same physical element appears in multiple
    views (File 1 = long-pan, File 2 = adjacent bay, File .1 = pignon).
    Rule: same designation + category + role + length → ONE entry, MAX quantity.
    If repere is set and identical → always merge.
    """
    from collections import defaultdict
    groups: dict[str, list[DetectedProfile]] = defaultdict(list)

    for p in profiles:
        desig  = (p.designation  or "").strip().upper()
        cat    = (p.type         or "").strip().lower()   # 'type' holds category
        role   = (p.role         or "").strip().upper()
        length = round(p.length_m, 2) if p.length_m is not None else None

        if p.id and not p.id.startswith("P0"):           # repere is meaningful
            key = f"REPERE:{p.id.strip().upper()}"
        else:
            key = f"{desig}|{cat}|{role}|{length}"

        groups[key].append(p)

    result: list[DetectedProfile] = []
    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
        else:
            # FILES = VIEWS: same element seen in N views → MAX quantity, not SUM
            best = max(group, key=lambda p: (p.quantity, p.confidence))
            best.confidence = max(p.confidence for p in group)
            logger.info(
                f"[DEDUP] Merged {len(group)}x '{best.designation}' "
                f"(role={best.role}) → qty={best.quantity}"
            )
            result.append(best)

    return result

def _is_non_warehouse(project: str, filename: str) -> bool:
    project_lower = str(project).lower()
    fn_lower = str(filename).lower()
    keywords = ["escabeau", "escalier", "stair", "ladder", "plateforme", "passerelle", "rampe", "platform", "support", "assemblage", "detail"]
    return any(kw in project_lower or kw in fn_lower for kw in keywords)

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
    provider = os.getenv("VISION_PROVIDER", "openai")
    _vision = VisionLLMEngine(fallback=True)
    _llamaparse = LlamaParseEngine()
    _text_llm = TextLLMEngine(provider=provider)
    logger.info("Engines ready — provider: %s", provider)

from fastapi.responses import JSONResponse
from fastapi.requests import Request

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
    id: str = "P00"
    designation: str = ""
    type: str = "unknown"
    role: str = ""
    length_m: float | None = None
    quantity: int = 1
    zone: str = ""
    confidence: float = 0.5
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
    return {"status": "ok", "provider": os.getenv("VISION_PROVIDER", "openai")}


@app.post("/extract")
async def extract(
    file: UploadFile = File(..., description="PDF of the structural drawing"),
    project: str = Form(default="unknown", description="Project name"),
    scale_hint: str = Form(default="", description="Expected scale e.g. '1:50' (optional)"),
    pages: str = Form(default="all", description="'all' or comma-separated page numbers e.g. '1,2,3'"),
    mode: str = Form(default="vision", description="'vision' | 'regex' | 'hybrid'"),
    provider: str = Form(default=None, description="Vision/Text provider e.g. 'openai', 'ollama'"),
    detailed_mode: bool = Form(default=False, description="Force extraction of all details and ignore warehouse constraints"),
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
        # Determine provider to use (default to env var if not specified)
        req_provider = provider or os.getenv("VISION_PROVIDER", "openai")
        vision_engine = VisionLLMEngine(provider=req_provider, fallback=True)
        text_engine = TextLLMEngine(provider=req_provider)

        # Determine pages to process
        import fitz
        doc = fitz.open(str(tmp_path))
        total_pages_pdf = len(doc)
        doc.close()
        
        if total_pages_pdf == 0:
            raise HTTPException(status_code=400, detail="No valid pages found")

        is_stairs = detailed_mode or _is_non_warehouse(project, file.filename)
        context = {
            "project": project,
            "ref": file.filename,
            "scale_hint": scale_hint or "unknown",
            "is_stairs": is_stairs
        }

        all_results: list[VisionResult] = []

        if mode == 'text':
            logger.info(f"Using LlamaParse + TextLLMEngine ({req_provider}) for direct PDF text extraction.")
            md_text = _llamaparse.parse_to_markdown(str(tmp_path))
            res = text_engine.analyze(md_text, context, pass_mode="TEXT_EXTRACTION")
            all_results.append(res)
        else:
            # Agentic Zoning Architecture
            logger.info(f"Using VisionLLMEngine ({req_provider}) with Agentic Zoning.")
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
                res1 = vision_engine.analyze(page_img.image, page_number=page_img.page_number, tile_index=0, context=ctx1, pass_mode="PASS1")
                
                # --- PASS 2: Accessories (Quadrants) ---
                zones = [
                    {"zone_type": "quadrant_top_left", "bbox_normalized": [0.0, 0.0, 0.55, 0.55]},
                    {"zone_type": "quadrant_top_right", "bbox_normalized": [0.0, 0.45, 0.55, 1.0]},
                    {"zone_type": "quadrant_bottom_left", "bbox_normalized": [0.45, 0.0, 1.0, 0.55]},
                    {"zone_type": "quadrant_bottom_right", "bbox_normalized": [0.45, 0.45, 1.0, 1.0]},
                ]
                
                pass2_jsons = []
                import fitz
                page_doc = fitz.open(str(tmp_path))
                page_obj = page_doc[page_num - 1]
                page_rect = page_obj.rect
                page_w, page_h = page_rect.width, page_rect.height
                from PIL import Image
                
                for z_idx, zone in enumerate(zones):
                    zt = zone.get("zone_type", "unknown")
                    y_min, x_min, y_max, x_max = zone.get("bbox_normalized", [0.0, 0.0, 1.0, 1.0])
                    
                    padding_x = page_w * 0.05
                    padding_y = page_h * 0.05
                    x0 = max(0.0, min(x_min, x_max) * page_w - padding_x)
                    y0 = max(0.0, min(y_min, y_max) * page_h - padding_y)
                    x1 = min(page_w, max(x_min, x_max) * page_w + padding_x)
                    y1 = min(page_h, max(y_min, y_max) * page_h + padding_y)
                    
                    clip_rect = fitz.Rect(x0, y0, x1, y1)
                    
                    logger.info(f"Executing PASS 2 on {zt} (Direct PDF 300 DPI Render)...")
                    zoom = 300.0 / 72.0
                    mat = fitz.Matrix(zoom, zoom)
                    pix = page_obj.get_pixmap(matrix=mat, clip=clip_rect, alpha=False)
                    crop_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    
                    ctx2 = context.copy()
                    ctx2["zone_type"] = zt
                    
                    sleep_time = 15.0 if req_provider == "openai" else 4.5
                    await asyncio.sleep(sleep_time) # Prevent rate limits
                    res2 = vision_engine.analyze(crop_img, page_number=page_img.page_number, tile_index=z_idx+1, context=ctx2, pass_mode="PASS2")
                    pass2_jsons.append(res2.raw_response)
                
                page_doc.close()
                
                # --- PASS 3: Merge & Deduplicate ---
                logger.info(f"Executing PASS 3 (Merge & Deduplicate) for page {page_img.page_number}...")
                pass3_payload = f"PASS1_JSON:\n{res1.raw_response}\n\nPASS2_JSONS:\n" + "\n---\n".join(pass2_jsons)
                
                ctx3 = context.copy()
                ctx3["zone_type"] = "merge"
                
                try:
                    sleep_time = 15.0 if req_provider == "openai" else 4.5
                    await asyncio.sleep(sleep_time)
                    merged_res = text_engine.analyze(pass3_payload, context=ctx3, pass_mode="PASS3")
                    all_results.append(merged_res)
                except Exception as e:
                    logger.error(f"PASS 3 Failed: {e}. Falling back to Python merge.")
                    # Fallback to Python merge if PASS 3 fails
                    [res1]
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

        # FILES=VIEWS deduplication (Python safety net)
        all_profiles_raw = _deduplicate_profiles(all_profiles_raw)

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
    ref: str = Form(''),
    provider: str = Form(default=None),
    detailed_mode: bool = Form(default=False),
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
                # Determine provider to use (default to env var if not specified)
                req_provider = provider or os.getenv("VISION_PROVIDER", "openai")
                vision_engine = VisionLLMEngine(provider=req_provider, fallback=True)
                text_engine = TextLLMEngine(provider=req_provider)

                is_stairs = detailed_mode or _is_non_warehouse(project, filename)
                context = {
                    'project': project,
                    'ref': filename,
                    'scale_hint': scale_hint or 'unknown',
                    'is_stairs': is_stairs
                }

                all_results = []
                
                if mode == 'text':
                    logger.info(f"Using LlamaParse + TextLLMEngine ({req_provider}) for direct PDF text extraction (Async).")
                    md_text = _llamaparse.parse_to_markdown(str(tmp_path))
                    res = text_engine.analyze(md_text, context, pass_mode="TEXT_EXTRACTION")
                    all_results.append(res)
                else:
                    logger.info(f"Using VisionLLMEngine ({req_provider}) with Agentic Zoning (Async).")
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
                            
                            sleep_time = 15.0 if req_provider == "openai" else 4.5
                            await asyncio.sleep(sleep_time)
                            res = vision_engine.analyze(crop_img, page_number=page_img.page_number, tile_index=z_idx, context=ctx)
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

                # FILES=VIEWS deduplication (Python safety net)
                all_profiles_raw = _deduplicate_profiles(all_profiles_raw)

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
    from catalogue import CATALOGUE_PROFILS
    return {"profiles": CATALOGUE_PROFILS}


# ---------------------------------------------------------------------------
# RulesDB — Catalogue et Règles de calcul
# ---------------------------------------------------------------------------
from catalogue import CATALOGUE_PROFILS, CATALOGUE_BOULONNERIE
import re
import math

def _enrich_profile(p: Any) -> ProfileOut:
    """Look up masse linéaire and compute poids total from RulesDB."""

    # ── Build a normalized catalogue index once ───────────────────────────
    # Key: stripped of spaces, uppercase, * separator
    # Value: (original_key, masse_kg_m)
    _NORM_CATALOGUE: dict[str, tuple[str, float]] = {}
    for k, v in CATALOGUE_PROFILS.items():
        norm = k.upper().replace(" ", "").replace("X", "*")
        _NORM_CATALOGUE[norm] = (k, v)

    def _lookup(raw: str, _depth: int = 0) -> float | None:
        """Try every reasonable variant of a designation against the catalogue."""
        if _depth > 1:
            return None  # Guard against infinite recursion
        attempts = set()
        s = raw.upper().strip()

        # Direct
        attempts.add(s)
        attempts.add(s.replace(" ", ""))

        # Normalise separators → *
        s_star = re.sub(r'[\sXx]+', '*', s)
        s_star = re.sub(r'\*+', '*', s_star).strip('*')
        attempts.add(s_star)
        attempts.add(s_star.replace("*", " ").strip())

        # Add space after leading letters (IPE400 → IPE 400, L50 → L 50)
        s_spaced = re.sub(r'^([A-Z]+)(\d)', r'\1 \2', s)
        attempts.add(s_spaced)
        attempts.add(s_spaced.replace(" ", ""))

        # L profiles: L50*50*5 → L 50*50*5  and  L50*5 → L 50*50*5
        l_full = re.match(r'L\s*(\d+)\*(\d+)\*(\d+)$', s.replace(" ", ""))
        if l_full:
            a, b, e = l_full.groups()
            attempts.add(f"L {a}*{b}*{e}")
            attempts.add(f"L{a}*{b}*{e}")

        l_short = re.match(r'L\s*(\d+)\*(\d+)$', s.replace(" ", ""))
        if l_short:
            a, e = l_short.groups()
            attempts.add(f"L {a}*{a}*{e}")   # equal leg
            attempts.add(f"L{a}*{a}*{e}")

        for attempt in attempts:
            # 1. Direct match
            v = CATALOGUE_PROFILS.get(attempt)
            if v is not None:
                return v
            # 2. Normalised match (ignore spaces, X vs *)
            norm = attempt.upper().replace(" ", "").replace("X", "*")
            hit = _NORM_CATALOGUE.get(norm)
            if hit:
                return hit[1]

        # ── Extract embedded profile code from full designation ──────────────
        # e.g. "CONTREVENTEMENT CVT L70*70*7" → try "L70*70*7" as last token
        # e.g. "PANNE IPE140" → try "IPE140"
        tokens = s.split()
        if len(tokens) > 1:  # Only if there are multiple tokens
            for tok in reversed(tokens):
                v = _lookup(tok, _depth=_depth + 1)
                if v is not None:
                    return v

        return None

    # ─────────────────────────────────────────────────────────────────────
    p_desig = getattr(p, 'designation', '')
    if p_desig is None:
        p_desig = ''
    raw_designation = str(p_desig).upper().strip()
    # Strip noise words
    raw_designation = raw_designation.replace("CORNIÈRE", "").replace("CORNIERE", "").strip()

    masse    = _lookup(raw_designation)
    methode  = "Catalogue" if masse is not None else None

    # ── Cornière formula fallback ─────────────────────────────────────────
    if masse is None:
        # Search for L profile pattern anywhere in the designation
        l_full  = re.search(r'L\s*(\d+)[*Xx](\d+)[*Xx](\d+)', raw_designation)
        l_short = re.search(r'(?<![A-Z])L\s*(\d+)[*Xx](\d+)(?![*Xx\d])', raw_designation)
        if l_full:
            a, b, e = map(float, l_full.groups())
            masse = round(((a + b - e) * e) * 0.00785, 3)
            methode = "Calcul"
        elif l_short:
            a, e = map(float, l_short.groups())
            masse = round((2 * a - e) * e * 0.00785, 3)
            methode = "Calcul"

    # ── JARRET (haunch) — assembled piece, estimate from base profile ─────
    # JARRET has no linear length — compute poids directly from base IPE masse
    if 'JARRET' in raw_designation:
        ipe_m = re.search(r'IPE\s*(\d+)', raw_designation)
        if ipe_m:
            base_masse = _lookup(f"IPE{ipe_m.group(1)}") or 0.0
            # Jarret ≈ haunch plate + 2 stiffeners, roughly 20% of beam linear mass
            # Set as fixed poids per unit (not linear × length)
            poids_jarret = round(base_masse * 0.20, 3)
            methode = "Estimation"
            masse = None
            length_val = None  # No linear length for a haunch
            # Will be handled below — store for later override
            _jarret_poids_unitaire = poids_jarret
        else:
            _jarret_poids_unitaire = None
    else:
        _jarret_poids_unitaire = None

    # Keep enriched designation for downstream (normalized with space)
    designation = re.sub(r'^([A-Z]+)(\d)', r'\1 \2', raw_designation)


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
        d_boulon = int(boulon_match.group(1))
        l_boulon = float(boulon_match.group(2))
        boulon_key = f"M{d_boulon}*{int(l_boulon)}"
        pu_boulon = CATALOGUE_BOULONNERIE.get(boulon_key)
        if not pu_boulon:
            prefix = f"M{d_boulon}*"
            same_d = {}
            for k, v in CATALOGUE_BOULONNERIE.items():
                if k.startswith(prefix):
                    try:
                        l_val = int(k.split("*")[1])
                        same_d[l_val] = v
                    except:
                        pass
            if same_d:
                sorted_lens = sorted(same_d.keys())
                if l_boulon <= sorted_lens[0]:
                    if len(sorted_lens) >= 2:
                        l1, l2 = sorted_lens[0], sorted_lens[1]
                        w1, w2 = same_d[l1], same_d[l2]
                        rate = (w2 - w1) / (l2 - l1)
                        pu_boulon = max(0.01, round(w1 - rate * (l1 - l_boulon), 3))
                    else:
                        pu_boulon = same_d[sorted_lens[0]]
                elif l_boulon >= sorted_lens[-1]:
                    if len(sorted_lens) >= 2:
                        l1, l2 = sorted_lens[-2], sorted_lens[-1]
                        w1, w2 = same_d[l1], same_d[l2]
                        rate = (w2 - w1) / (l2 - l1)
                        pu_boulon = round(w2 + rate * (l_boulon - l2), 3)
                    else:
                        pu_boulon = same_d[sorted_lens[-1]]
                else:
                    for i in range(len(sorted_lens) - 1):
                        l1, l2 = sorted_lens[i], sorted_lens[i+1]
                        if l1 <= l_boulon <= l2:
                            w1, w2 = same_d[l1], same_d[l2]
                            rate = (w2 - w1) / (l2 - l1)
                            pu_boulon = round(w1 + rate * (l_boulon - l1), 3)
                            break
            else:
                vol_mm3 = 0.7854 * (d_boulon**2) * l_boulon + 1.2 * (d_boulon**3)
                pu_boulon = round(vol_mm3 * 7.85e-6, 3)
        if pu_boulon:
            poids_unitaire = pu_boulon
            methode = "Catalogue" if boulon_key in CATALOGUE_BOULONNERIE else "Calcul (Extrapolé)"
            poids = round(poids_unitaire * qty_val, 2)
            masse = None
            length_val = None

    # TÔLES PLQ / TL
    tole_match = re.search(r'(?:PLQ|TL|TOLE).*?(\d+)\s*[xX\*]\s*(\d+)\s*[xX\*]\s*(\d+)', designation, re.IGNORECASE)
    if tole_match and not methode:
        vals = sorted([float(tole_match.group(1)), float(tole_match.group(2)), float(tole_match.group(3))])
        ep_plq, larg_plq, long_plq = vals[0], vals[1], vals[2]  # ep = min toujours
        poids_unitaire = round((long_plq/1000) * (larg_plq/1000) * (ep_plq/1000) * 7850, 2)
        poids = round(poids_unitaire * qty_val, 2)
        methode = "Calcul"
        masse = None
        length_val = None

    if masse is not None and not boulon_match and not tole_match:
        if length_val is not None and length_val > 0:
            poids = round(masse * length_val * qty_val, 2)
        else:
            poids = None  # No length → no weight computable

    # JARRET override: poids direct (no length)
    if _jarret_poids_unitaire is not None:
        poids_unitaire = _jarret_poids_unitaire
        poids = round(_jarret_poids_unitaire * qty_val, 2)
        methode = "Estimation"
        masse = None
        length_val = None


    # Check for PL, TN, PLATINE, GOUSSET, RAIDISSEUR A*B*C
    pl_match = re.search(r'(?:PLT|TN|PLAT|GOUSSET|RAID|PLATE|GUSSET|STIFFENER|FLANGE).*?(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)', designation, re.IGNORECASE)
    fer_plat_match = re.search(r'(?:FER\s*PLAT|PL).*?(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)', designation, re.IGNORECASE)
    marche_match = re.search(r'(?:MARCHE|TREAD|STEP).*?(\d+)\s*[xX\*]\s*(\d+)', designation, re.IGNORECASE)
    role_val = getattr(p, 'role', '')
    if role_val is None:
        role_val = ''
    role_upper = str(role_val).upper()
    if not marche_match and any(w in role_upper or w in designation for w in ['MARCHE', 'TREAD', 'STEP']):
        marche_match = re.search(r'(\d+)\s*[xX\*]\s*(\d+)', designation)
    
    if pl_match and not boulon_match and not tole_match:
        vals = sorted([float(pl_match.group(1)), float(pl_match.group(2)), float(pl_match.group(3))])
        # ep = smallest dim, larg & long = the two larger dims
        ep, larg, long_ = vals[0], vals[1], vals[2]
        # Volume × density (kg/m³) — reference uses 7850
        poids_unitaire = round((ep/1000) * (larg/1000) * (long_/1000) * 7850, 3)
        poids = round(poids_unitaire * qty_val, 2)
        methode = "Calcul"
        # Paint surface = 2 main faces (larg × long)
        surface_peinture = round(2 * (larg * long_) / 1_000_000 * qty_val, 3)
        length_val = None  # plates have no linear length
        masse = None
    elif fer_plat_match and not masse and not boulon_match and not tole_match:
        # Fer Plat: Width x Thickness (e.g. PL 150x6)
        width, thickness = map(float, fer_plat_match.groups())
        # If length is missing or 0, check if it's a Platine (which is usually square)
        # Or if it's a plate, we can assume length = width (square plate)
        if (length_val is None or length_val == 0.0) and (
            any(word in designation for word in ['PLATINE', 'PLT', 'GOUSSET', 'RAIDISSEUR', 'FIXATION', 'PALIER', 'PLATE', 'BASEPLATE', 'STIFFENER', 'GUSSET', 'FLANGE']) or
            any(word in role_upper for word in ['PLATINE', 'PLT', 'GOUSSET', 'RAIDISSEUR', 'FIXATION', 'PALIER', 'PLATE', 'BASEPLATE', 'STIFFENER', 'GUSSET', 'FLANGE'])
        ):
            poids_unitaire = round((width/1000) * (width/1000) * (thickness/1000) * 7850, 3)
            poids = round(poids_unitaire * qty_val, 2)
            methode = "Calcul (Carré)"
            surface_peinture = round(2 * (width * width) / 1_000_000 * qty_val, 3)
            masse = None
            length_val = None
        else:
            masse_val = width * thickness * 0.00785
            masse = round(masse_val, 3)
            poids = round(masse * length_val * qty_val, 2) if (length_val is not None and length_val > 0) else None
            methode = "Calcul"
            perimeter_m = 2 * (width + thickness) / 1000.0
            if length_val is not None and length_val > 0:
                surface_peinture = round(perimeter_m * length_val * qty_val, 2)
    elif marche_match and not methode and not boulon_match and not tole_match:
        a_dim = float(marche_match.group(1))
        b_dim = float(marche_match.group(2))
        area_m2 = (a_dim / 1000.0) * (b_dim / 1000.0)
        poids_unitaire = round(area_m2 * 40.0, 2)  # 40 kg/m²
        poids = round(poids_unitaire * qty_val, 2)
        methode = "Estimation (40 kg/m²)"
        masse = None
        length_val = None

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
        id=getattr(p, 'repere', None) or getattr(p, 'id', 'P00') or 'P00',
        designation=(getattr(p, 'designation', '') or '').strip().upper(),
        type=getattr(p, 'category', None) or getattr(p, 'type', None) or 'unknown',
        role=getattr(p, 'role', '') or '',
        length_m=length_val,
        quantity=qty_val,
        zone=getattr(p, 'zone', None) or (getattr(p, 'views_confirmed', [''])[0] if getattr(p, 'views_confirmed', None) else '') or '',
        confidence=p.confidence if p.confidence is not None else 0.5,
        masse_lineaire_kg_m=masse,
        poids_unitaire=poids_unitaire,
        poids_total_kg=poids,
        surface_peinture_m2=surface_peinture,
        methode=methode if methode else "Inconnu",
    )
    return out