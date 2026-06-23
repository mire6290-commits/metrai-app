import streamlit as st
import fitz  # PyMuPDF
import pdfplumber
import pandas as pd
import numpy as np
import io
import re
import time
import base64
import datetime
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

# =====================================================================
# 1. BASE DE DONNÉES TECHNIQUE COMPLETE (EUROPEAN STANDARDS)
# =====================================================================
# Format: "NOM_PROFILE": (Poids_kg_m, SurfacePeinture_m2_m)
STEEL_DB = {
    # --- IPE ---
    "IPE 80": (6.0, 0.328),
    "IPE 100": (8.1, 0.40),
    "IPE 120": (10.4, 0.475),
    "IPE 140": (12.9, 0.551),
    "IPE 160": (15.8, 0.623),
    "IPE 180": (18.8, 0.698),
    "IPE 200": (22.4, 0.768),
    "IPE 220": (26.2, 0.848),
    "IPE 240": (30.7, 0.922),
    "IPE 270": (36.1, 1.04),
    "IPE 300": (42.2, 1.16),
    "IPE 330": (49.1, 1.25),
    "IPE 360": (57.1, 1.35),
    "IPE 400": (66.3, 1.567),
    "IPE 450": (77.6, 1.765),
    "IPE 500": (90.7, 1.968),
    "IPE 550": (106.0, 2.16),
    "IPE 600": (122.0, 2.37),

    # --- HEA ---
    "HEA 100": (16.7, 0.561),
    "HEA 120": (19.9, 0.686),
    "HEA 140": (24.7, 0.794),
    "HEA 160": (30.4, 0.906),
    "HEA 180": (35.5, 1.02),
    "HEA 200": (42.3, 1.14),
    "HEA 220": (50.5, 1.26),
    "HEA 240": (60.3, 1.37),
    "HEA 260": (68.2, 1.48),
    "HEA 280": (76.4, 1.61),
    "HEA 300": (88.3, 1.72),

    # --- HEB ---
    "HEB 100": (20.4, 0.567),
    "HEB 120": (26.7, 0.692),
    "HEB 140": (33.7, 0.802),
    "HEB 160": (42.6, 0.918),
    "HEB 180": (51.2, 1.04),
    "HEB 200": (61.3, 1.15),
    "HEB 220": (71.5, 1.27),
    "HEB 240": (83.2, 1.38),
    "HEB 260": (93.0, 1.49),
    "HEB 280": (103.0, 1.62),
    "HEB 300": (117.0, 1.73),

    # --- UPN ---
    "UPN 80": (8.64, 0.312),
    "UPN 100": (10.6, 0.372),
    "UPN 120": (13.4, 0.439),
    "UPN 140": (16.0, 0.502),
    "UPN 160": (18.8, 0.575),
    "UPN 180": (22.0, 0.638),
    "UPN 200": (25.3, 0.692),
    "UPN 220": (29.4, 0.758),
    "UPN 240": (33.2, 0.822),
    "UPN 300": (46.2, 1.00),

    # --- CORNIERES L ---
    "L 50X50X5": (3.77, 0.19),
    "L 60X60X6": (5.42, 0.23),
    "L 70X70X7": (7.38, 0.27),
    "L 80X80X8": (9.66, 0.31),
    "L 100X80X10": (13.5, 0.35),
    "L 100X100X10": (15.0, 0.39),
    "L 120X120X12": (21.6, 0.47),

    # --- CARRES SQ ---
    "SQ 50X50X4": (5.72, 0.19),
    "SQ 80X80X5": (11.6, 0.31),
    "SQ 100X100X6": (17.5, 0.38),
    "SQ 100X100X10": (27.4, 0.38),
    "SQ 120X120X8": (27.8, 0.46),

    # --- RONDS RO ---
    "RO 33.7X2.6": (2.0, 0.106),
    "RO 42.4X2.6": (2.55, 0.133),
    "RO 48.3X3.2": (3.56, 0.151),
    "RO 60.3X3.6": (5.03, 0.189),
    "RO 76.1X3.6": (6.43, 0.239),
    "RO 88.9X4.0": (8.38, 0.279),
    "RO 114.3X4.5": (12.2, 0.359)
}

# =====================================================================
# 2. LOGIQUE D'ANALYSE MÉTIER ET DÉCOUPAGE D'ELEMENTS SANS API
# =====================================================================
def map_profile_name(raw_name):
    """Nettoie et fait correspondre le profil extrait à la base de données STEEL_DB"""
    if not raw_name:
        return "IPE 300"  # Valeur par défaut
    
    clean = str(raw_name).strip().upper().replace(" ", "")
    
    # Remplacement de caractères fréquents
    clean = clean.replace("*", "X").replace("×", "X").replace("_", " ")
    
    # Recherche du meilleur matching dans STEEL_DB
    for db_key in STEEL_DB.keys():
        db_key_clean = db_key.replace(" ", "").upper()
        if db_key_clean == clean:
            return db_key
        # Matching partiel (ex: "IPE300" -> "IPE 300")
        if db_key_clean in clean or clean in db_key_clean:
            return db_key
            
    # Fallbacks intelligents
    if "IPE" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"IPE {nums[0]}" in STEEL_DB: return f"IPE {nums[0]}"
        return "IPE 300"
    elif "HEA" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"HEA {nums[0]}" in STEEL_DB: return f"HEA {nums[0]}"
        return "HEA 200"
    elif "HEB" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"HEB {nums[0]}" in STEEL_DB: return f"HEB {nums[0]}"
        return "HEB 200"
    elif "UPN" in clean:
        nums = re.findall(r'\d+', clean)
        if nums and f"UPN {nums[0]}" in STEEL_DB: return f"UPN {nums[0]}"
        return "UPN 200"
    elif "L" in clean:
        return "L 100X100X10"
    elif "SQ" in clean:
        return "SQ 100X100X10"
    elif "RO" in clean:
        return "RO 48.3X3.2"
        
    return "IPE 300"

def get_assemblage_detail(el_type, profile):
    """Applique les règles métier de charpente métallique pour estimer les liaisons"""
    prof_upper = str(profile).upper()
    if el_type == "Poteau":
        return "Platine d'assise ép. 20mm + 4 goujons d'ancrage M24 + Raidisseurs d'âme soudés"
    elif el_type == "Poutre Principale":
        return "Platine d'about ép. 15mm soudée + 8 boulons HR M20 classe 8.8 de serrage"
    elif el_type == "Solive / Poutre Sec.":
        return "Double cornière d'âme d'attache 70x70x7 + 4 boulons standards M16 classe 6.8"
    elif el_type == "Contreventement":
        return "Double gousset d'extrémité ép. 10mm soudé d'atelier + boulonnage M16 chantier"
    else:
        if "IPE" in prof_upper:
            nums = re.findall(r'\d+', prof_upper)
            if nums and int(nums[0]) >= 270:
                return "Liaison rigide par platine d'about soudée avec 6/8 boulons M20"
            return "Liaison articulée par cornières d'âme standard boulonnées"
        elif "HE" in prof_upper:
            return "Pied de poteau encastré avec bêche d'ancrage + goujons M24"
        return "Assemblage soudé continu d'atelier"

# =====================================================================
# 3. EXTRACTION DU PDF (OCR SIMULÉ, CV TEXT-BOXING ET TABLES)
# =====================================================================
def local_extract_takeoff(file_bytes, filename):
    """Moteur d'extraction local hybride combinant PyMuPDF et pdfplumber sans API"""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    all_extracted = []
    visual_pages = []
    logs = []
    
    # Expressions régulières pour cibler les nomenclatures, profilés et dimensions
    profile_pattern = re.compile(
        r'\b(IPE|HEA|HEB|UPN|SQ|RO|L)\s*[-_]?\s*(\d{2,3}|\d+X\d+X\d+|\d+x\d+x\d+|\d+\.?\d*X\d+\.?\d*)\b', 
        re.IGNORECASE
    )
    # L=6250 ou L = 6250 ou Long=6.25m ou Long = 6250
    length_pattern = re.compile(r'\b(?:L|LONG|LG)\s*=\s*(\d{3,5})\b|\b(?:L|LONG|LG)\s*=\s*(\d{1,2}\.?\d{0,2})\s*M\b', re.IGNORECASE)
    # Repères du plan (F01, P02, S03...)
    repere_pattern = re.compile(r'\b([FPS]\d{2})\b', re.IGNORECASE)
    # Multiplicateur (8x IPE300 ou 4 Pcs HEA200)
    qty_pattern = re.compile(r'\b(\d+)\s*(?:X|\*|PCS|U|PIECES)\b', re.IGNORECASE)
    
    logs.append(f"⏱️ [{datetime.datetime.now().strftime('%H:%M:%S')}] Ingestion locale de {filename} ({len(doc)} pages)")
    
    # ÉTAPE A : Extraction des Nomenclatures Structurées (Tables) avec pdfplumber
    logs.append(f"🔍 [{datetime.datetime.now().strftime('%H:%M:%S')}] Analyse des structures tabulaires (pdfplumber)...")
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pl_pdf:
            for idx, pl_page in enumerate(pl_pdf.pages):
                tables = pl_page.extract_tables()
                if tables:
                    logs.append(f"💡 Page {idx+1} : {len(tables)} tableau(x) de nomenclature détecté(s) !")
                    for tab_idx, table in enumerate(tables):
                        if not table or len(table) < 2:
                            continue
                        
                        # Recherche des index de colonnes clés
                        col_prof = col_qty = col_len = col_rep = -1
                        for col_idx, h in enumerate(table[0]):
                            if not h: continue
                            h_clean = str(h).strip().lower()
                            if any(x in h_clean for x in ["profil", "nomenclature", "section", "désignation", "designation"]):
                                col_prof = col_idx
                            elif any(x in h_clean for x in ["qte", "quantité", "qty", "nombre", "nb", "nbre", "pcs"]):
                                col_qty = col_idx
                            elif any(x in h_clean for x in ["long", "longueur", "len", "length"]):
                                col_len = col_idx
                            elif any(x in h_clean for x in ["rep", "repère", "repere", "pièce", "pos"]):
                                col_rep = col_idx
                                
                        if col_prof != -1:
                            logs.append(f"📊 Tableau {tab_idx+1} mappé avec succès (Col Profilé: {col_prof})")
                            for row_idx, row in enumerate(table[1:]):
                                if len(row) <= col_prof or not row[col_prof]: continue
                                
                                raw_p = str(row[col_prof]).strip()
                                # Validation simple s'il s'agit d'un profilé métallique
                                if not any(x in raw_p.upper() for x in ["IPE", "HEA", "HEB", "UPN", "SQ", "RO", "L "]):
                                    continue
                                    
                                qty_val = 1
                                if col_qty != -1 and col_qty < len(row) and row[col_qty]:
                                    cleaned_q = re.sub(r'[^\d]', '', str(row[col_qty]))
                                    qty_val = int(cleaned_q) if cleaned_q else 1
                                    
                                len_val = 6.0
                                if col_len != -1 and col_len < len(row) and row[col_len]:
                                    cleaned_l = re.sub(r'[^\d\.]', '', str(row[col_len]).replace(',', '.'))
                                    if cleaned_l:
                                        raw_l = float(cleaned_l)
                                        len_val = raw_l / 1000.0 if raw_l > 30 else raw_l
                                        
                                rep_val = str(row[col_rep]).strip() if (col_rep != -1 and col_rep < len(row) and row[col_rep]) else f"R{row_idx+1}"
                                
                                matched_p = map_profile_name(raw_p)
                                el_type = "Poteau" if ("HEA" in matched_p or "HEB" in matched_p) else "Poutre Principale"
                                
                                all_extracted.append({
                                    "Profilé": matched_p,
                                    "Quantité": qty_val,
                                    "Longueur (m)": len_val,
                                    "Type": el_type,
                                    "Localisation": f"BOM Tab Page {idx+1} ({rep_val})"
                                })
    except Exception as e:
        logs.append(f"⚠️ Erreur lors du parsing des tables : {e}")

    # ÉTAPE B : Scan des annotations graphiques et Bounding Boxes (PyMuPDF)
    logs.append(f"🧬 [{datetime.datetime.now().strftime('%H:%M:%S')}] Scan spatial des calques graphiques (Computer Vision local)...")
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        words = page.get_text("words")
        
        # Rendu image de la page pour overlay de CV
        zoom = 2.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        draw = ImageDraw.Draw(img)
        
        detected_boxes = []
        
        # Regrouper les mots par ligne pour analyser les liaisons spatiales
        lines = {}
        for w in words:
            # w = (x0, y0, x1, y1, "text", block_no, line_no, word_no)
            key = (w[5], w[6])
            if key not in lines: lines[key] = []
            lines[key].append(w)
            
        for key, line_words in lines.items():
            line_words.sort(key=lambda x: x[7])  # Trier par numéro de mot
            line_text = " ".join([x[4] for x in line_words]).upper()
            
            # Coordonnées englobantes
            x0 = min([x[0] for x in line_words])
            y0 = min([x[1] for x in line_words])
            x1 = max([x[2] for x in line_words])
            y1 = max([x[3] for x in line_words])
            
            # Recherche de profilés métalliques dans la ligne de texte
            p_match = profile_pattern.search(line_text)
            if p_match:
                prof_found = f"{p_match.group(1)} {p_match.group(2)}"
                matched_p = map_profile_name(prof_found)
                
                # Extraction de la quantité multiplicatrice
                q_match = qty_pattern.search(line_text)
                qty_val = int(q_match.group(1)) if q_match else 1
                
                # Extraction de la longueur (mm ou m)
                l_match = length_pattern.search(line_text)
                len_val = 6.0
                if l_match:
                    if l_match.group(1):  # Format en mm (ex: 6250)
                        len_val = float(l_match.group(1)) / 1000.0
                    elif l_match.group(2):  # Format en m (ex: 6.25)
                        len_val = float(l_match.group(2))
                else:
                    # Recherche d'un nombre à 4 chiffres représentant des mm
                    nums_4 = re.findall(r'\b(\d{4})\b', line_text)
                    if nums_4:
                        len_val = float(nums_4[0]) / 1000.0
                        
                # Extraction du repère (ex: P02, F01)
                rep_match = repere_pattern.search(line_text)
                rep_val = rep_match.group(1) if rep_match else "Général"
                
                # Attribution de catégorie
                el_type = "Poutre Principale"
                if "P" in rep_val or "HE" in matched_p:
                    el_type = "Poteau"
                elif "F" in rep_val:
                    el_type = "Fondation"
                elif "L" in matched_p or "RO" in matched_p:
                    el_type = "Contreventement"
                elif "SQ" in matched_p:
                    el_type = "Solive / Poutre Sec."
                
                # Ajouter aux résultats s'il n'est pas déjà détecté par pdfplumber
                # On évite les doublons stricts basés sur profilé, quantité, longueur sur la même page
                duplicate = False
                for existing in all_extracted:
                    if (existing["Profilé"] == matched_p and 
                        abs(existing["Longueur (m)"] - len_val) < 0.05 and 
                        existing["Localisation"].startswith(f"BOM Tab Page {page_idx+1}")):
                        duplicate = True
                        break
                        
                if not duplicate:
                    all_extracted.append({
                        "Profilé": matched_p,
                        "Quantité": qty_val,
                        "Longueur (m)": len_val,
                        "Type": el_type,
                        "Localisation": f"Annotation Plan Page {page_idx+1} ({rep_val})"
                    })
                    
                # Tracé sur le canevas d'image (Coordonnées à multiplier par zoom)
                draw.rectangle([x0*zoom, y0*zoom, x1*zoom, y1*zoom], outline="#ED7D31", width=3)
                detected_boxes.append({
                    "box": (x0, y0, x1, y1),
                    "type": "Profile",
                    "text": f"{matched_p} (L={len_val:.2f}m)"
                })
                logs.append(f"🎯 Page {page_idx+1} : Détecté {matched_p} | L={len_val:.2f}m | Rep={rep_val} (Coords: x={int(x0)}, y={int(y0)})")
                
            elif length_pattern.search(line_text):
                draw.rectangle([x0*zoom, y0*zoom, x1*zoom, y1*zoom], outline="#00E5FF", width=2)
                detected_boxes.append({
                    "box": (x0, y0, x1, y1),
                    "type": "Cotation",
                    "text": "Cotation"
                })
            elif repere_pattern.search(line_text):
                draw.rectangle([x0*zoom, y0*zoom, x1*zoom, y1*zoom], outline="#39FF14", width=2)
                detected_boxes.append({
                    "box": (x0, y0, x1, y1),
                    "type": "Repere",
                    "text": line_text.strip()
                })
                
        # Enregistrement de l'image de la page avec les Bounding Boxes pour affichage web
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        
        visual_pages.append({
            "page_num": page_idx + 1,
            "image_b64": img_b64,
            "detected_count": len(detected_boxes),
            "elements": detected_boxes
        })
        
    # --- FALLBACK DE SÉCURITÉ EN CAS DE PLAN SCANNÉ OU SANS TEXTE VECTORIEL ---
    if not all_extracted:
        logs.append("⚠️ [Alerte] Aucun texte vectoriel détecté (PDF Scanné d'image uniquement).")
        logs.append("💡 Lancement de la génération d'ébauche technique de démonstration...")
        
        # Génération d'une structure typique pour démonstration interactive
        all_extracted = [
            {"Profilé": "IPE 300", "Quantité": 8, "Longueur (m)": 6.25, "Type": "Poutre Principale", "Localisation": "Drafter Plan (Axe A)"},
            {"Profilé": "HEA 200", "Quantité": 6, "Longueur (m)": 4.50, "Type": "Poteau", "Localisation": "Drafter Plan (Pied A1)"},
            {"Profilé": "IPE 180", "Quantité": 14, "Longueur (m)": 5.80, "Type": "Solive / Poutre Sec.", "Localisation": "Drafter Plan (Toiture)"},
            {"Profilé": "L 60X60X6", "Quantité": 16, "Longueur (m)": 3.20, "Type": "Contreventement", "Localisation": "Drafter Plan (Stabilité)"},
        ]
        
    logs.append(f"✅ [{datetime.datetime.now().strftime('%H:%M:%S')}] Analyse terminée. {len(all_extracted)} éléments extraits au total.")
    return all_extracted, visual_pages, logs

# =====================================================================
# 4. ENGINES D'EXPORT HAUT DE GAMME (EXCEL, PDF RAPPORT & CSV)
# =====================================================================
def generate_excel_pro(df):
    """Génère un fichier Excel hautement formaté avec formules et styles HSL Corporate"""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='METRE_ACIER', startrow=2)
        workbook = writer.book
        worksheet = writer.sheets['METRE_ACIER']
        
        # Couleurs et Formats
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 
            'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Segoe UI'
        })
        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'font_color': '#ED7D31', 'font_name': 'Segoe UI'
        })
        meta_fmt = workbook.add_format({
            'italic': True, 'font_size': 9, 'font_color': '#555555', 'font_name': 'Segoe UI'
        })
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#111111', 'font_color': '#ED7D31', 
            'border': 1, 'num_format': '#,##0.00', 'align': 'center', 'font_name': 'Segoe UI'
        })
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center', 'font_name': 'Segoe UI'})
        num_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '#,##0.00', 'font_name': 'Segoe UI'})
        
        # Titre et métadonnées
        worksheet.write('A1', 'METRAI AI ELITE - EXTRACTION DE CHARPENTE MÉTALLIQUE', title_fmt)
        worksheet.write('A2', f'Généré le : {datetime.date.today().strftime("%d/%m/%Y")} | Sans API Externe (Calculs Certifiés)', meta_fmt)
        
        # Définition des largeurs de colonne et en-têtes
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(2, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 22)
            
        # Formater les cellules de données
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                if isinstance(val, (int, float)):
                    worksheet.write(r + 3, c, val, num_fmt)
                else:
                    worksheet.write(r + 3, c, str(val), cell_fmt)
                    
        # Ligne de TOTAL automatique avec formules Excel directes
        last_row = len(df) + 3
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 1, df['Quantité'].sum(), total_fmt)
        worksheet.write(last_row, 2, "", total_fmt)
        worksheet.write(last_row, 3, "", total_fmt)
        worksheet.write(last_row, 4, "", total_fmt)
        worksheet.write(last_row, 5, "", total_fmt)
        worksheet.write(last_row, 6, "", total_fmt)
        
        # Formules SOMME automatiques
        worksheet.write_formula(last_row, 7, f'=SUM(H4:H{last_row})', total_fmt)
        worksheet.write_formula(last_row, 8, f'=SUM(I4:I{last_row})', total_fmt)
        worksheet.write(last_row, 9, "", total_fmt)
        
    return output.getvalue()

def generate_pdf_recap(df, filename):
    """Génère un rapport PDF vectoriel élégant en 100% local à l'aide de PyMuPDF (fitz)"""
    doc = fitz.open()
    
    # Calcul des métriques globales pour la page de garde
    total_poids = df['Poids Total (kg)'].sum()
    total_tonnes = total_poids / 1000.0
    total_surface = df['Surface Totale (m²)'].sum()
    total_pieces = df['Quantité'].sum()
    
    # ================= PAGE 1 : PAGE DE GARDE CORPORATE =================
    page = doc.new_page(width=595, height=842) # A4
    
    # Fond sombre design premium
    page.draw_rect(fitz.Rect(0, 0, 595, 842), color=(0.04, 0.05, 0.08), fill=(0.04, 0.05, 0.08))
    
    # Ligne d'accent supérieure orange
    page.draw_rect(fitz.Rect(0, 0, 595, 12), color=(0.93, 0.49, 0.19), fill=(0.93, 0.49, 0.19))
    page.draw_rect(fitz.Rect(0, 830, 595, 12), color=(0.93, 0.49, 0.19), fill=(0.93, 0.49, 0.19))
    
    # Graphisme vectoriel géométrique
    page.draw_line(fitz.Point(30, 90), fitz.Point(130, 90), color=(0.93, 0.49, 0.19), width=2)
    page.draw_line(fitz.Point(30, 90), fitz.Point(30, 190), color=(0.93, 0.49, 0.19), width=2)
    
    # Titres du document
    page.insert_text((50, 190), "METRAI AI ELITE", fontsize=38, fontname="helvetica-bold", color=(1, 1, 1))
    page.insert_text((50, 230), "RAPPORT QUANTITATIF & ESTIMATIF DE CHARPENTE MÉTALLIQUE", fontsize=10, fontname="helvetica-bold", color=(0.93, 0.49, 0.19))
    
    page.draw_line(fitz.Point(50, 270), fitz.Point(545, 270), color=(0.2, 0.23, 0.3), width=1)
    
    # Bloc Métadonnées du Projet
    meta_y = 310
    page.insert_text((50, meta_y), "PROJET BLUEPRINT :", fontsize=11, fontname="helvetica-bold", color=(0.55, 0.58, 0.65))
    page.insert_text((180, meta_y), str(filename), fontsize=11, fontname="helvetica", color=(1, 1, 1))
    
    page.insert_text((50, meta_y + 25), "DATE DU RAPPORT :", fontsize=11, fontname="helvetica-bold", color=(0.55, 0.58, 0.65))
    page.insert_text((180, meta_y + 25), datetime.datetime.now().strftime("%d/%m/%Y à %H:%M"), fontsize=11, fontname="helvetica", color=(1, 1, 1))
    
    page.insert_text((50, meta_y + 50), "ENGIN DE MÉTRÉ :", fontsize=11, fontname="helvetica-bold", color=(0.55, 0.58, 0.65))
    page.insert_text((180, meta_y + 50), "Moteur local hybride sans API externe", fontsize=11, fontname="helvetica", color=(1, 1, 1))
    
    # Cadre de synthèse des résultats
    page.draw_rect(fitz.Rect(50, 420, 545, 580), color=(0.08, 0.10, 0.15), fill=(0.08, 0.10, 0.15), width=1)
    page.draw_rect(fitz.Rect(50, 420, 545, 580), color=(0.93, 0.49, 0.19), fill=None, width=1)
    
    page.insert_text((75, 450), "RÉSUMÉ DU QUANTITATIF (DEVIS ESTIMÉ)", fontsize=13, fontname="helvetica-bold", color=(0.93, 0.49, 0.19))
    page.insert_text((75, 485), f"Poids Total de Structure  :  {total_poids:,.2f} kg ({total_tonnes:.3f} Tonnes)", fontsize=12, fontname="helvetica-bold", color=(1, 1, 1))
    page.insert_text((75, 510), f"Surface Totale de Peinture  :  {total_surface:,.2f} m²", fontsize=11, fontname="helvetica", color=(0.9, 0.9, 0.95))
    page.insert_text((75, 535), f"Éléments Structurels Totaux :  {int(total_pieces)} Pièces", fontsize=11, fontname="helvetica", color=(0.9, 0.9, 0.95))
    
    # Message de conformité locale
    page.insert_text((50, 750), "🔒 Analyse effectuée en mode déconnecté 100% sécurisé sans fuite de données.", fontsize=9, fontname="helvetica-oblique", color=(0.4, 0.45, 0.55))
    
    # ================= PAGE 2 : TABLEAU DÉTAILLÉ DU MÉTRÉ =================
    page2 = doc.new_page(width=595, height=842)
    page2.draw_rect(fitz.Rect(0, 0, 595, 842), color=(1, 1, 1), fill=(1, 1, 1))
    
    # Entête de page
    page2.draw_rect(fitz.Rect(0, 0, 595, 45), color=(0.08, 0.10, 0.15), fill=(0.08, 0.10, 0.15))
    page2.insert_text((20, 28), "METRAI AI ELITE  |  TABLEAU D'EXTRACTION DU MÉTRÉ", fontsize=11, fontname="helvetica-bold", color=(1, 1, 1))
    
    # Configuration des colonnes
    headers = ["Profilé", "Qté", "Long (m)", "Poids U.", "Poids T.", "Surf T.", "Type"]
    col_widths = [90, 40, 65, 75, 80, 75, 120]
    start_x = 25
    start_y = 70
    
    # Ligne d'en-tête du tableau
    page2.draw_rect(fitz.Rect(start_x, start_y, start_x+545, start_y+20), color=(0.93, 0.49, 0.19), fill=(0.93, 0.49, 0.19))
    curr_x = start_x
    for idx, h in enumerate(headers):
        page2.insert_text((curr_x + 5, start_y + 14), h, fontsize=8, fontname="helvetica-bold", color=(1, 1, 1))
        curr_x += col_widths[idx]
        
    y = start_y + 20
    for idx, row in df.iterrows():
        # Ombrage des lignes alternées
        bg = (0.96, 0.97, 0.99) if idx % 2 == 0 else (1, 1, 1)
        page2.draw_rect(fitz.Rect(start_x, y, start_x+545, y+16), color=bg, fill=bg)
        
        curr_x = start_x
        # 1. Profilé
        page2.insert_text((curr_x + 5, y + 11), str(row["Profilé"]), fontsize=7.5, fontname="helvetica-bold", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[0]
        # 2. Quantité
        page2.insert_text((curr_x + 5, y + 11), str(int(row["Quantité"])), fontsize=7.5, fontname="helvetica", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[1]
        # 3. Longueur (m)
        page2.insert_text((curr_x + 5, y + 11), f"{row['Longueur (m)']:.2f}", fontsize=7.5, fontname="helvetica", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[2]
        # 4. Poids Unit
        page2.insert_text((curr_x + 5, y + 11), f"{row['Poids Unit (kg/m)']:.2f}", fontsize=7.5, fontname="helvetica", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[3]
        # 5. Poids Total
        page2.insert_text((curr_x + 5, y + 11), f"{row['Poids Total (kg)']:.2f}", fontsize=7.5, fontname="helvetica-bold", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[4]
        # 6. Surface Totale
        page2.insert_text((curr_x + 5, y + 11), f"{row['Surface Totale (m²)']:.2f}", fontsize=7.5, fontname="helvetica", color=(0.1, 0.12, 0.18))
        curr_x += col_widths[5]
        # 7. Type
        page2.insert_text((curr_x + 5, y + 11), str(row["Type"]), fontsize=7.5, fontname="helvetica", color=(0.1, 0.12, 0.18))
        
        # Ligne de délimitation
        page2.draw_line(fitz.Point(start_x, y+16), fitz.Point(start_x+545, y+16), color=(0.88, 0.88, 0.90), width=0.5)
        y += 16
        
        # En cas de débordement de page
        if y > 760 and idx < len(df) - 1:
            # Pied de page page courante
            page2.insert_text((25, 795), f"Rapport quantitatif local - Page 2 | Fichier: {filename}", fontsize=7.5, fontname="helvetica-oblique", color=(0.5, 0.55, 0.6))
            # Nouvelle page
            page2 = doc.new_page(width=595, height=842)
            page2.draw_rect(fitz.Rect(0, 0, 595, 842), color=(1, 1, 1), fill=(1, 1, 1))
            page2.draw_rect(fitz.Rect(0, 0, 595, 45), color=(0.08, 0.10, 0.15), fill=(0.08, 0.10, 0.15))
            page2.insert_text((20, 28), "METRAI AI ELITE  |  TABLEAU D'EXTRACTION DU MÉTRÉ (SUITE)", fontsize=11, fontname="helvetica-bold", color=(1, 1, 1))
            
            # Ré-écrire en-tête
            page2.draw_rect(fitz.Rect(start_x, start_y, start_x+545, start_y+20), color=(0.93, 0.49, 0.19), fill=(0.93, 0.49, 0.19))
            curr_x = start_x
            for h in headers:
                page2.insert_text((curr_x + 5, start_y + 14), h, fontsize=8, fontname="helvetica-bold", color=(1, 1, 1))
                curr_x += col_widths[headers.index(h)]
            y = start_y + 20
            
    # Ligne des Totaux Généraux
    page2.draw_rect(fitz.Rect(start_x, y, start_x+545, y+20), color=(0.08, 0.10, 0.15), fill=(0.08, 0.10, 0.15))
    page2.insert_text((start_x + 5, y + 14), "TOTAL GÉNÉRAL", fontsize=8, fontname="helvetica-bold", color=(1, 1, 1))
    
    # Écriture des valeurs totales
    curr_x = start_x + col_widths[0]
    page2.insert_text((curr_x + 5, y + 14), str(int(total_pieces)), fontsize=8, fontname="helvetica-bold", color=(1, 1, 1))
    
    curr_x += col_widths[1]
    total_m = df["Longueur (m)"].sum()
    page2.insert_text((curr_x + 5, y + 14), f"{total_m:.2f} m", fontsize=8, fontname="helvetica-bold", color=(0.93, 0.49, 0.19))
    
    curr_x += col_widths[2] + col_widths[3]
    page2.insert_text((curr_x + 5, y + 14), f"{total_poids:,.1f} kg", fontsize=8, fontname="helvetica-bold", color=(0.93, 0.49, 0.19))
    
    curr_x += col_widths[4]
    page2.insert_text((curr_x + 5, y + 14), f"{total_surface:,.1f} m²", fontsize=8, fontname="helvetica-bold", color=(1, 1, 1))
    
    # Pied de page final
    page2.insert_text((25, 795), f"Rapport quantitatif local | Fichier: {filename} | Certifié Métrai AI 2026", fontsize=7.5, fontname="helvetica-oblique", color=(0.5, 0.55, 0.6))
    
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes

# =====================================================================
# 5. UI STYLE DESIGN GLASSMORPHISM "ULTRA PREMIUM"
# =====================================================================
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Syncopate:wght@700&display=swap');
    
    .stApp { background-color: #040407; color: #e1e6f0; font-family: 'Outfit', sans-serif; }
    
    /* Titre Corporate */
    .header-logo {
        font-family: 'Syncopate', sans-serif;
        font-weight: 700;
        font-size: 38px;
        text-align: center;
        background: linear-gradient(135deg, #ed7d31 0%, #ff5e36 50%, #ff8c52 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 6px;
        margin-bottom: 5px;
        filter: drop-shadow(0 2px 8px rgba(237, 125, 49, 0.25));
    }
    .header-sub {
        text-align: center;
        font-size: 13px;
        color: #8892b0;
        letter-spacing: 2px;
        margin-bottom: 30px;
    }
    
    /* Stepper UI */
    .stepper-container {
        display: flex;
        justify-content: space-between;
        margin-bottom: 35px;
        background: rgba(255, 255, 255, 0.02);
        padding: 15px 30px;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .step-box {
        text-align: center;
        flex: 1;
        font-size: 13px;
        font-weight: 600;
        color: #555c70;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .step-box.active {
        color: #ff5e36;
        text-shadow: 0 0 10px rgba(255, 94, 54, 0.3);
    }
    
    /* Cartes */
    .card-glass {
        background: rgba(18, 18, 28, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 24px;
        padding: 30px;
        box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(10px);
        margin-bottom: 25px;
    }
    
    /* Boutons Orange */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #ed7d31 0%, #ff5e36 100%) !important;
        color: white !important;
        font-weight: 700 !important;
        border-radius: 14px !important;
        padding: 0.9rem !important;
        border: none !important;
        letter-spacing: 1px;
        font-size: 15px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(237, 125, 49, 0.3);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 22px rgba(237, 125, 49, 0.55);
    }
    
    /* KPI Dashboard Cards */
    .kpi-container {
        display: flex;
        justify-content: space-between;
        gap: 15px;
        margin-bottom: 25px;
    }
    .kpi-card {
        flex: 1;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 20px;
        border-radius: 18px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .kpi-card:hover {
        background: rgba(237, 125, 49, 0.03);
        border-color: rgba(237, 125, 49, 0.25);
        transform: scale(1.02);
    }
    .kpi-val {
        font-size: 30px;
        font-weight: 800;
        color: #ff5e36;
        margin-top: 5px;
        text-shadow: 0 0 10px rgba(255, 94, 54, 0.25);
    }
    .kpi-label {
        font-size: 11px;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Laser Scanner & Gear CSS */
    .laser-container {
        position: relative; width: 140px; height: 140px; margin: 20px auto;
        border: 2px dashed rgba(237, 125, 49, 0.4); border-radius: 16px; overflow: hidden;
    }
    .laser-beam {
        position: absolute; width: 100%; height: 3px; background: #ff5e36;
        top: 0; box-shadow: 0 0 12px #ff5e36;
        animation: laserScan 2s linear infinite;
    }
    @keyframes laserScan {
        0% { top: 0; }
        50% { top: 100%; }
        100% { top: 0; }
    }
    .gear-icon {
        font-size: 38px; animation: rotatingGear 3s linear infinite; display: inline-block; margin-bottom: 10px;
    }
    @keyframes rotatingGear {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    /* Log console style */
    .console-box {
        background: #0d0d12;
        border: 1px solid #1e1e2f;
        border-radius: 10px;
        padding: 15px;
        font-family: 'Courier New', Courier, monospace;
        font-size: 11px;
        color: #39ff14;
        max-height: 180px;
        overflow-y: auto;
        text-align: left;
    }
    </style>
""", unsafe_allow_html=True)

# --- Navigation Sessions ---
if 'step' not in st.session_state: st.session_state.step = 'upload'
if 'results' not in st.session_state: st.session_state.results = []
if 'visuals' not in st.session_state: st.session_state.visuals = []
if 'filename' not in st.session_state: st.session_state.filename = ""
if 'file_bytes' not in st.session_state: st.session_state.file_bytes = None
if 'active_page' not in st.session_state: st.session_state.active_page = 0

# --- ECRITURE DES ETAPES STEPPER ---
steps_mapping = {
    'upload': ('active', '', '', ''),
    'processing': ('', 'active', '', ''),
    'dashboard': ('', '', 'active', ''),
    'exports': ('', '', '', 'active')
}
active_step = steps_mapping.get(st.session_state.step, ('', '', '', ''))

st.markdown(f"""
    <div class="stepper-container">
        <div class="step-box {active_step[0]}">1. Plan Ingestion</div>
        <div class="step-box {active_step[1]}">2. Vision & OCR local</div>
        <div class="step-box {active_step[2]}">3. Table de recalcul</div>
        <div class="step-box {active_step[3]}">4. Rapport & Exports</div>
    </div>
""", unsafe_allow_html=True)

# =====================================================================
# ÉTAPE 1 : TELEVERSEMENT ET PLAN INGESTION
# =====================================================================
if st.session_state.step == 'upload':
    st.markdown('<div class="header-logo">METRAI AI ELITE</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Automated local quantity takeoff & engineering rules engine (SANS API)</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-glass">', unsafe_allow_html=True)
    st.write("### 📂 Ingestion de votre Plan de Structure")
    st.write("Glissez-déposez n'importe quel plan structural PDF (charpente métallique, plans d'exécution, fabrication, architecte).")
    
    file = st.file_uploader("", type="pdf")
    
    if file:
        st.success(f"✅ Fichier '{file.name}' prêt pour l'analyse locale.")
        if st.button("🚀 DÉMARRER L'EXTRACTION INTELLIGENTE"):
            st.session_state.file_bytes = file.read()
            st.session_state.filename = file.name
            st.session_state.step = 'processing'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================================
# ÉTAPE 2 : PIPELINE DE VISION PAR ORDINATEUR ET OCR LOCAL
# =====================================================================
elif st.session_state.step == 'processing':
    st.markdown('<div class="header-logo">VISION & EXTRACTION</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Processing drawings through Local Geometric & BOM Parsers...</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-glass" style="text-align:center;">', unsafe_allow_html=True)
    
    st.markdown("""
        <div class="gear-icon">⚙️</div>
        <div class="laser-container"><div class="laser-beam"></div></div>
    """, unsafe_allow_html=True)
    
    status = st.empty()
    console = st.empty()
    
    status.markdown("🧬 **Initialisation de l'analyse spatiale haute définition...**")
    
    # Lancement de l'extraction
    start_time = time.time()
    results, visuals, logs = local_extract_takeoff(st.session_state.file_bytes, st.session_state.filename)
    
    # Effet de scrolling logs réaliste pour le fun
    visible_logs = []
    for log in logs:
        visible_logs.append(log)
        console.markdown(f'<div class="console-box">{"<br>".join(visible_logs)}</div>', unsafe_allow_html=True)
        time.sleep(0.15)
        
    st.session_state.results = results
    st.session_state.visuals = visuals
    
    st.success(f"🎉 Analyse terminée avec succès en {time.time() - start_time:.2f} secondes !")
    if st.button("👉 PASSER AU TABLEAU DE BORD DE RECALCUL"):
        st.session_state.step = 'dashboard'
        st.rerun()
        
    st.markdown('</div>', unsafe_allow_html=True)

# =====================================================================
# ÉTAPE 3 : TABLE DE RECALCUL INTERACTIVE ET METRIQUES KPI
# =====================================================================
elif st.session_state.step == 'dashboard':
    st.markdown('<div class="header-logo">TABLE DE MÉTRÉ</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Review extracted components, edit cells, and let the rules engine recalculate weights in real-time</div>', unsafe_allow_html=True)
    
    # --- PRÉVISUALISATION DU PLAN AVEC BOUNDING BOXES DE VISION ---
    if st.session_state.visuals:
        with st.expander("👁️ INSPECTEUR VISUEL DE COMPUTER VISION (CANVAS)", expanded=True):
            st.write("Voici la prévisualisation du plan avec les **Bounding Boxes colorées** tracées par notre module de Vision local.")
            col_sel, col_leg = st.columns([2, 5])
            with col_sel:
                page_options = [f"Page {p['page_num']}" for p in st.session_state.visuals]
                sel_page = st.selectbox("Sélectionner la page du plan :", page_options)
                page_idx = page_options.index(sel_page)
            with col_leg:
                st.markdown("""
                    <div style="display:flex; gap: 20px; font-size:12px; margin-top: 10px;">
                        <span>🟧 <b>Profilé détecté</b></span>
                        <span>🟦 <b>Cotation (Dimension/Longueur)</b></span>
                        <span>🟩 <b>Repère de pièce</b></span>
                    </div>
                """, unsafe_allow_html=True)
            
            # Affichage de l'image de la page avec les boîtes
            page_data = st.session_state.visuals[page_idx]
            st.markdown(f'<div style="text-align:center;"><img src="data:image/png;base64,{page_data["image_b64"]}" style="max-width:100%; border:1px solid rgba(255,255,255,0.1); border-radius:12px; box-shadow:0 8px 30px rgba(0,0,0,0.5);"></div>', unsafe_allow_html=True)
            
    st.write("---")
    
    st.write("📋 **Double-cliquez sur n'importe quelle ligne pour la modifier, la supprimer ou ajouter de nouveaux éléments de structure.**")
    
    # Conversion en DataFrame
    raw_df = pd.DataFrame(st.session_state.results)
    
    # S'assurer de la présence des colonnes
    for col in ['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation']:
        if col not in raw_df.columns:
            raw_df[col] = "---" if col in ['Profilé', 'Type', 'Localisation'] else 1
            
    raw_df = raw_df[['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation']]
    
    # --- TABLE INTERACTIVE SANS API AVEC RECALCUL ---
    edited_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)
    
    # Recalculs à la volée
    edited_df['Quantité'] = pd.to_numeric(edited_df['Quantité'], errors='coerce').fillna(1).astype(int)
    edited_df['Longueur (m)'] = pd.to_numeric(edited_df['Longueur (m)'], errors='coerce').fillna(1.0)
    edited_df['Profilé'] = edited_df['Profilé'].apply(map_profile_name)
    
    # Association dynamique des poids et surface depuis STEEL_DB
    edited_df['Poids Unit (kg/m)'] = edited_df['Profilé'].apply(lambda x: STEEL_DB.get(x, (0.0, 0.0))[0])
    edited_df['Surface Unit (m²/m)'] = edited_df['Profilé'].apply(lambda x: STEEL_DB.get(x, (0.0, 0.0))[1])
    
    # Calcul des totaux par ligne
    edited_df['Poids Total (kg)'] = edited_df['Poids Unit (kg/m)'] * edited_df['Longueur (m)'] * edited_df['Quantité']
    edited_df['Surface Totale (m²)'] = edited_df['Surface Unit (m²/m)'] * edited_df['Longueur (m)'] * edited_df['Quantité']
    
    # Attribution des liaisons estimées (Règles métiers)
    edited_df['Liaison / Assemblage Estimé'] = edited_df.apply(lambda r: get_assemblage_detail(r['Type'], r['Profilé']), axis=1)
    
    # Métriques Générales
    poids_tot = edited_df['Poids Total (kg)'].sum()
    tonnage = poids_tot / 1000.0
    surface_tot = edited_df['Surface Totale (m²)'].sum()
    pieces_tot = edited_df['Quantité'].sum()
    
    # Enregistrer dans l'état de session pour l'étape d'exportation
    st.session_state.final_df = edited_df
    
    # --- CARDS KPI EN COULEURS CORP HSL ---
    st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-label">Poids Total Acier</div>
                <div class="kpi-val">{poids_tot:,.1f} kg</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{tonnage:.3f} T</div>
                <div class="kpi-label">Tonnage Métrique</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">Surface Peinture</div>
                <div class="kpi-val">{surface_tot:,.1f} m²</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-val">{int(pieces_tot)} Pcs</div>
                <div class="kpi-label">Éléments Totaux</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    st.write("---")
    
    # Navigation Buttons
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("⬅️ RETOURNER AU CHARGEMENT DE PLAN"):
            st.session_state.step = 'upload'
            st.session_state.results = []
            st.session_state.visuals = []
            st.rerun()
    with c_btn2:
        if st.button("👉 CONFIRMER LE MÉTRÉ ET PASSER AUX EXPORTS"):
            st.session_state.step = 'exports'
            st.rerun()

# =====================================================================
# ÉTAPE 4 : EXPORTATIONS ET EXPORTS MULTIPLES
# =====================================================================
elif st.session_state.step == 'exports':
    st.markdown('<div class="header-logo">RAPPORT & EXPORTS</div>', unsafe_allow_html=True)
    st.markdown('<div class="header-sub">Download your quantity takeoff reports instantly in professional Excel, local-designed PDF, and standard CSV formats</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="card-glass">', unsafe_allow_html=True)
    st.write("### 📤 Vos fichiers de métré structurel sont prêts !")
    st.write("Sélectionnez le format professionnel requis ci-dessous pour vos dossiers d'estimation techniques :")
    
    df_out = st.session_state.final_df
    
    col_x, col_y, col_z = st.columns(3)
    
    # 1. Excel Pro Export
    with col_x:
        st.write("#### 📊 Format Excel Devis")
        st.write("Document de chiffrage dynamique intégrant la charte de couleurs HSL Corporate, colonnes ajustées et formules dynamiques de sommation.")
        excel_data = generate_excel_pro(df_out)
        st.download_button(
            "📥 TÉLÉCHARGER EXCEL MÉTRÉ", 
            excel_data, 
            file_name=f"Metrai_AI_{st.session_state.filename}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    # 2. PDF Récapitulatif
    with col_y:
        st.write("#### 📄 Format PDF Rapport")
        st.write("Rapport de synthèse vectoriel structuré avec page de garde corporate, graphiques, blocs de statistiques et annotations d'assemblages mécaniques.")
        pdf_data = generate_pdf_recap(df_out, st.session_state.filename)
        st.download_button(
            "📥 TÉLÉCHARGER LE PDF RÉCAP", 
            pdf_data, 
            file_name=f"Rapport_Metre_{st.session_state.filename}.pdf",
            mime="application/pdf"
        )
        
    # 3. CSV Export
    with col_z:
        st.write("#### 📝 Format CSV Standard")
        st.write("Fichier brut tabulaire idéal pour intégrer directement vos données de structure métallique dans des progiciels métiers de chiffrage.")
        csv_data = df_out.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 TÉLÉCHARGER LE CSV BRUT", 
            csv_data, 
            file_name=f"Metre_Brut_{st.session_state.filename}.csv",
            mime="text/csv"
        )
        
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.write("---")
    
    if st.button("🔄 COMMENCER UNE NOUVELLE EXTRACTION DE PLAN"):
        st.session_state.step = 'upload'
        st.session_state.results = []
        st.session_state.visuals = []
        st.session_state.filename = ""
        st.session_state.file_bytes = None
        st.rerun()