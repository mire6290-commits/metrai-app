import io
import re
import base64
import datetime
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
from PIL import Image, ImageDraw

# =====================================================================
# 1. BASE DE DONNÉES TECHNIQUE COMPLETE (EUROPEAN STANDARDS)
# =====================================================================
STEEL_DB = {
    "IPE 80": (6.0, 0.328), "IPE 100": (8.1, 0.40), "IPE 120": (10.4, 0.475), "IPE 140": (12.9, 0.551),
    "IPE 160": (15.8, 0.623), "IPE 180": (18.8, 0.698), "IPE 200": (22.4, 0.768), "IPE 220": (26.2, 0.848),
    "IPE 240": (30.7, 0.922), "IPE 270": (36.1, 1.04), "IPE 300": (42.2, 1.16), "IPE 330": (49.1, 1.25),
    "IPE 360": (57.1, 1.35), "IPE 400": (66.3, 1.567), "IPE 450": (77.6, 1.765), "IPE 500": (90.7, 1.968),
    "IPE 550": (106.0, 2.16), "IPE 600": (122.0, 2.37),
    "HEA 100": (16.7, 0.561), "HEA 120": (19.9, 0.686), "HEA 140": (24.7, 0.794), "HEA 160": (30.4, 0.906),
    "HEA 180": (35.5, 1.02), "HEA 200": (42.3, 1.14), "HEA 220": (50.5, 1.26), "HEA 240": (60.3, 1.37),
    "HEA 260": (68.2, 1.48), "HEA 280": (76.4, 1.61), "HEA 300": (88.3, 1.72),
    "HEB 100": (20.4, 0.567), "HEB 120": (26.7, 0.692), "HEB 140": (33.7, 0.802), "HEB 160": (42.6, 0.918),
    "HEB 180": (51.2, 1.04), "HEB 200": (61.3, 1.15), "HEB 220": (71.5, 1.27), "HEB 240": (83.2, 1.38),
    "HEB 260": (93.0, 1.49), "HEB 280": (103.0, 1.62), "HEB 300": (117.0, 1.73),
    "UPN 80": (8.64, 0.312), "UPN 100": (10.6, 0.372), "UPN 120": (13.4, 0.439), "UPN 140": (16.0, 0.502),
    "UPN 160": (18.8, 0.575), "UPN 180": (22.0, 0.638), "UPN 200": (25.3, 0.692), "UPN 220": (29.4, 0.758),
    "UPN 240": (33.2, 0.822), "UPN 300": (46.2, 1.00),
    "L 50X50X5": (3.77, 0.19), "L 60X60X6": (5.42, 0.23), "L 70X70X7": (7.38, 0.27), "L 80X80X8": (9.66, 0.31),
    "L 100X80X10": (13.5, 0.35), "L 100X100X10": (15.0, 0.39), "L 120X120X12": (21.6, 0.47),
    "SQ 50X50X4": (5.72, 0.19), "SQ 80X80X5": (11.6, 0.31), "SQ 100X100X6": (17.5, 0.38),
    "SQ 100X100X10": (27.4, 0.38), "SQ 120X120X8": (27.8, 0.46),
    "RO 33.7X2.6": (2.0, 0.106), "RO 42.4X2.6": (2.55, 0.133), "RO 48.3X3.2": (3.56, 0.151),
    "RO 60.3X3.6": (5.03, 0.189), "RO 76.1X3.6": (6.43, 0.239), "RO 88.9X4.0": (8.38, 0.279),
    "RO 114.3X4.5": (12.2, 0.359)
}

def map_profile_name(raw_name):
    if not raw_name: return "IPE 300"
    clean = str(raw_name).strip().upper().replace(" ", "").replace("*", "X").replace("×", "X").replace("_", " ")
    for db_key in STEEL_DB.keys():
        db_key_clean = db_key.replace(" ", "").upper()
        if db_key_clean == clean or db_key_clean in clean or clean in db_key_clean: return db_key
    if "IPE" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"IPE {nums[0]}" in STEEL_DB: return f"IPE {nums[0]}"
    elif "HEA" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"HEA {nums[0]}" in STEEL_DB: return f"HEA {nums[0]}"
    elif "HEB" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"HEB {nums[0]}" in STEEL_DB: return f"HEB {nums[0]}"
    elif "UPN" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"UPN {nums[0]}" in STEEL_DB: return f"UPN {nums[0]}"
    elif "L" in clean: return "L 100X100X10"
    elif "SQ" in clean: return "SQ 100X100X10"
    elif "RO" in clean: return "RO 48.3X3.2"
    return "IPE 300"

def get_assemblage_detail(el_type, profile):
    prof_upper = str(profile).upper()
    if el_type == "Poteau": return "Platine d'assise ép. 20mm + 4 goujons d'ancrage M24 + Raidisseurs d'âme soudés"
    elif el_type == "Poutre Principale": return "Platine d'about ép. 15mm soudée + 8 boulons HR M20 classe 8.8"
    elif el_type == "Solive / Poutre Sec.": return "Double cornière d'âme d'attache 70x70x7 + 4 boulons M16"
    elif el_type == "Contreventement": return "Double gousset d'extrémité ép. 10mm soudé + boulonnage M16"
    return "Assemblage soudé continu d'atelier"

app = FastAPI(title="Metrai AI Elite Web")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.post("/api/extract")
async def extract_pdf(file: UploadFile = File(...)):
    file_bytes = await file.read()
    filename = file.filename
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_extracted = []
    visual_pages = []
    
    logo_base64 = None
    project_name = filename.replace('.pdf', '').replace('.PDF', '').upper()
    try:
        images = doc[0].get_images(full=True)
        if images:
            xref = images[-1][0]  # Souvent le logo est la dernière image
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            logo_base64 = base64.b64encode(image_bytes).decode('utf-8')
    except Exception:
        pass
    
    profile_pattern = re.compile(r'\b(IPE|HEA|HEB|UPN|SQ|RO|L)\s*[-_]?\s*(\d{2,3}|\d+X\d+X\d+|\d+x\d+x\d+|\d+\.?\d*X\d+\.?\d*)\b', re.IGNORECASE)
    length_pattern = re.compile(r'\b(?:L|LONG|LG)\s*=\s*(\d{3,5})\b|\b(?:L|LONG|LG)\s*=\s*(\d{1,2}\.?\d{0,2})\s*M\b', re.IGNORECASE)
    repere_pattern = re.compile(r'\b([FPS]\d{2})\b', re.IGNORECASE)
    qty_pattern = re.compile(r'\b(\d+)\s*(?:X|\*|PCS|U|PIECES)\b', re.IGNORECASE)
    
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pl_pdf:
            for idx, pl_page in enumerate(pl_pdf.pages):
                tables = pl_page.extract_tables()
                if tables:
                    for tab_idx, table in enumerate(tables):
                        if not table or len(table) < 2: continue
                        col_prof = col_qty = col_len = col_rep = -1
                        for col_idx, h in enumerate(table[0]):
                            if not h: continue
                            h_clean = str(h).strip().lower()
                            if any(x in h_clean for x in ["profil", "nomenclature", "section", "désignation"]): col_prof = col_idx
                            elif any(x in h_clean for x in ["qte", "quantité", "qty", "pcs"]): col_qty = col_idx
                            elif any(x in h_clean for x in ["long", "len"]): col_len = col_idx
                            elif any(x in h_clean for x in ["rep", "pos"]): col_rep = col_idx
                                
                        if col_prof != -1:
                            for row_idx, row in enumerate(table[1:]):
                                if len(row) <= col_prof or not row[col_prof]: continue
                                raw_p = str(row[col_prof]).strip()
                                if not any(x in raw_p.upper() for x in ["IPE", "HEA", "HEB", "UPN", "SQ", "RO", "L "]): continue
                                qty_val = 1
                                if col_qty != -1 and col_qty < len(row) and row[col_qty]:
                                    cleaned_q = re.sub(r'[^\d]', '', str(row[col_qty]))
                                    qty_val = int(cleaned_q) if cleaned_q else 1
                                len_val = 6.0
                                if col_len != -1 and col_len < len(row) and row[col_len]:
                                    cleaned_l = re.sub(r'[^\d\.]', '', str(row[col_len]).replace(',', '.'))
                                    if cleaned_l: len_val = float(cleaned_l) / 1000.0 if float(cleaned_l) > 30 else float(cleaned_l)
                                rep_val = str(row[col_rep]).strip() if (col_rep != -1 and col_rep < len(row) and row[col_rep]) else f"R{row_idx+1}"
                                matched_p = map_profile_name(raw_p)
                                el_type = "Poteau" if ("HEA" in matched_p or "HEB" in matched_p) else "Poutre Principale"
                                all_extracted.append({
                                    "id": f"bom_{idx}_{row_idx}",
                                    "Profilé": matched_p, "Quantité": qty_val, "Longueur": len_val, "Type": el_type, "Localisation": f"Page {idx+1} ({rep_val})"
                                })
    except Exception: pass

    for page_idx in range(min(len(doc), 5)):  # Limit visual to 5 pages for speed
        page = doc[page_idx]
        words = page.get_text("words")
        zoom = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        draw = ImageDraw.Draw(img)
        detected_boxes = []
        lines = {}
        for w in words:
            key = (w[5], w[6])
            if key not in lines: lines[key] = []
            lines[key].append(w)
            
        for key, line_words in lines.items():
            line_words.sort(key=lambda x: x[7])
            line_text = " ".join([x[4] for x in line_words]).upper()
            x0, y0 = min([x[0] for x in line_words]), min([x[1] for x in line_words])
            x1, y1 = max([x[2] for x in line_words]), max([x[3] for x in line_words])
            
            p_match = profile_pattern.search(line_text)
            if p_match:
                prof_found = f"{p_match.group(1)} {p_match.group(2)}"
                matched_p = map_profile_name(prof_found)
                q_match = qty_pattern.search(line_text)
                qty_val = int(q_match.group(1)) if q_match else 1
                l_match = length_pattern.search(line_text)
                len_val = 6.0
                if l_match:
                    len_val = float(l_match.group(1)) / 1000.0 if l_match.group(1) else float(l_match.group(2))
                rep_match = repere_pattern.search(line_text)
                rep_val = rep_match.group(1) if rep_match else "Général"
                el_type = "Poteau" if "P" in rep_val or "HE" in matched_p else "Poutre Principale"
                
                duplicate = False
                for existing in all_extracted:
                    if existing["Profilé"] == matched_p and abs(existing["Longueur"] - len_val) < 0.05 and f"Page {page_idx+1}" in existing["Localisation"]: duplicate = True; break
                if not duplicate:
                    all_extracted.append({
                        "id": f"cv_{page_idx}_{x0}_{y0}",
                        "Profilé": matched_p, "Quantité": qty_val, "Longueur": len_val, "Type": el_type, "Localisation": f"Plan Page {page_idx+1} ({rep_val})"
                    })
                draw.rectangle([x0*zoom, y0*zoom, x1*zoom, y1*zoom], outline="#ED7D31", width=3)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        visual_pages.append({"page_num": page_idx + 1, "image_b64": base64.b64encode(buffered.getvalue()).decode('utf-8')})
        
    if not all_extracted:
        all_extracted = [
            {"id":"demo1", "Profilé": "IPE 300", "Quantité": 8, "Longueur": 6.25, "Type": "Poutre Principale", "Localisation": "Drafter Plan"},
            {"id":"demo2", "Profilé": "HEA 200", "Quantité": 6, "Longueur": 4.50, "Type": "Poteau", "Localisation": "Drafter Plan"},
        ]
        
    # Append DB metadata
    for item in all_extracted:
        db_data = STEEL_DB.get(item["Profilé"], (0.0, 0.0))
        item["Poids_Unit"] = db_data[0]
        item["Surface_Unit"] = db_data[1]

    return JSONResponse(content={"results": all_extracted, "visuals": visual_pages, "logo": logo_base64, "project_name": project_name})

def generate_excel_pro(df, logo_b64=None, project_name="PROJET CHARPENTE"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='METRE_ACIER', startrow=3)
        workbook = writer.book
        worksheet = writer.sheets['METRE_ACIER']
        
        # New Corporate Design Formatting
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#1E293B', 'font_color': 'white', 
            'border': 1, 'border_color': '#334155', 'align': 'center', 'valign': 'vcenter', 'font_name': 'Inter'
        })
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 18, 'font_color': '#0F172A', 'font_name': 'Inter'
        })
        meta_fmt = workbook.add_format({
            'italic': True, 'font_size': 10, 'font_color': '#64748B', 'font_name': 'Inter'
        })
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#F8FAFC', 'font_color': '#0F172A', 
            'top': 2, 'bottom': 2, 'border_color': '#1E293B', 'num_format': '#,##0.00', 'align': 'center', 'font_name': 'Inter'
        })
        cell_fmt_odd = workbook.add_format({'bg_color': '#FFFFFF', 'border': 1, 'border_color': '#E2E8F0', 'align': 'center', 'font_name': 'Inter'})
        cell_fmt_even = workbook.add_format({'bg_color': '#F1F5F9', 'border': 1, 'border_color': '#E2E8F0', 'align': 'center', 'font_name': 'Inter'})
        num_fmt_odd = workbook.add_format({'bg_color': '#FFFFFF', 'border': 1, 'border_color': '#E2E8F0', 'align': 'center', 'num_format': '#,##0.00', 'font_name': 'Inter'})
        num_fmt_even = workbook.add_format({'bg_color': '#F1F5F9', 'border': 1, 'border_color': '#E2E8F0', 'align': 'center', 'num_format': '#,##0.00', 'font_name': 'Inter'})
        
        worksheet.set_row(0, 30)
        worksheet.write('A1', f'RAPPORT DE MÉTRÉ : {project_name}', title_fmt)
        worksheet.write('A2', f'Généré le : {datetime.date.today().strftime("%d/%m/%Y")} | Metrai AI Elite Engine', meta_fmt)
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(3, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 24)
            
        for r in range(len(df)):
            is_even = (r % 2 == 0)
            c_fmt = cell_fmt_even if is_even else cell_fmt_odd
            n_fmt = num_fmt_even if is_even else num_fmt_odd
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                if isinstance(val, (int, float)):
                    worksheet.write(r + 4, c, val, n_fmt)
                else:
                    worksheet.write(r + 4, c, str(val), c_fmt)
                    
        last_row = len(df) + 4
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 1, df['Quantité'].sum(), total_fmt)
        worksheet.write(last_row, 2, "", total_fmt)
        worksheet.write(last_row, 3, "", total_fmt)
        worksheet.write(last_row, 4, "", total_fmt)
        
        for c in range(5, len(df.columns)):
             worksheet.write(last_row, c, "", total_fmt)
             
        worksheet.write(last_row, 7, df['Poids Total (kg)'].sum(), total_fmt)
        worksheet.write(last_row, 8, df['Surface Totale (m²)'].sum(), total_fmt)

        # INSERT LOGO UNDER TABLE
        if logo_b64:
            try:
                img_data = io.BytesIO(base64.b64decode(logo_b64))
                # Insert at column A, 3 rows below the total
                worksheet.insert_image(last_row + 3, 0, 'logo.png', {'image_data': img_data, 'x_scale': 0.8, 'y_scale': 0.8, 'object_position': 1})
            except Exception:
                pass
                
    return output.getvalue()

from pydantic import BaseModel
from typing import List

class ItemModel(BaseModel):
    Profilé: str
    Quantité: int
    Longueur: float
    Type: str
    Localisation: str
    Poids_Unit: float
    Surface_Unit: float
    
class ExportRequest(BaseModel):
    data: List[ItemModel]
    logo_b64: str = None
    project_name: str = "PROJET"

@app.post("/api/export/excel")
def export_excel(req: ExportRequest):
    df_list = []
    for item in req.data:
        poids_tot = item.Poids_Unit * item.Longueur * item.Quantité
        surf_tot = item.Surface_Unit * item.Longueur * item.Quantité
        df_list.append({
            "Profilé": item.Profilé,
            "Quantité": item.Quantité,
            "Longueur (m)": item.Longueur,
            "Type": item.Type,
            "Localisation": item.Localisation,
            "Poids Unit (kg/m)": item.Poids_Unit,
            "Surface Unit (m²/m)": item.Surface_Unit,
            "Poids Total (kg)": poids_tot,
            "Surface Totale (m²)": surf_tot
        })
    df = pd.DataFrame(df_list)
    excel_bytes = generate_excel_pro(df, req.logo_b64, req.project_name)
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=Metrai_AI_Report.xlsx"}
    )
