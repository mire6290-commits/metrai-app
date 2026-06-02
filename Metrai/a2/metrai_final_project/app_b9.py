import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
from PIL import Image, ImageEnhance
import io
import base64
import requests
import time

# --- 1. CONFIGURATION ---
API_KEY = "tkpq3wSOfVMoWLXee7wP3vHyEgJGm87m".strip()
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# --- 2. BASE DE DONNÉES TECHNIQUE COMPLETE (EUROPEAN STANDARDS) ---
# Format: "NOM_PROFILE": (Poids_kg_m, SurfacePeinture_m2_m)
STEEL_DB = {
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
    
    "HEB 100": (20.4, 0.567),
    "HEB 120": (26.7, 0.692),
    "HEB 140": (33.7, 0.802),
    "HEB 160": (42.6, 0.918),
    "HEB 180": (51.2, 1.04),
    "HEB 200": (61.3, 1.15),
    "HEB 220": (71.5, 1.27),
    "HEB 240": (83.2, 1.38),
    "HEB 300": (117.0, 1.73),
    
    "UPN 80": (8.64, 0.312),
    "UPN 100": (10.6, 0.372),
    "UPN 120": (13.4, 0.439),
    "UPN 140": (16.0, 0.502),
    "UPN 160": (18.8, 0.575),
    "UPN 180": (22.0, 0.638),
    "UPN 200": (25.3, 0.692),
    
    "L 50X50X5": (3.77, 0.19),
    "L 60X60X6": (5.42, 0.23),
    "L 100X80X10": (13.5, 0.35),
    "L 100X100X10": (15.0, 0.39),
    "L 120X120X12": (21.6, 0.47),
    
    "SQ 80X80X5": (11.6, 0.31),
    "SQ 100X100X10": (27.4, 0.38),
    
    "RO 48.3X3.2": (3.56, 0.15)
}

# --- 3. AMÉLIORATION IMAGE HAUTE DÉFINITION ---
def enhance_image(pix):
    """Améliore drastiquement le contraste et la lisibilité du texte sur le plan pour l'OCR/AI"""
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # Niveaux de gris
    img = img.convert('L')
    # Augmenter le contraste de 2.5x
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.5)
    # Augmenter la netteté
    sharpness = ImageEnhance.Sharpness(img)
    img = sharpness.enhance(2.0)
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 4. ENGINE D'EXPORT EXCEL HAUT DE GAMME ---
def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='METRE_DE_STRUCTURE', startrow=1)
        workbook, worksheet = writer.book, writer.sheets['METRE_DE_STRUCTURE']
        
        # Formats stylisés HSL Corporate
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 
            'border': 1, 'align': 'center', 'valign': 'vcenter'
        })
        total_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#111111', 'font_color': '#ED7D31', 
            'border': 1, 'num_format': '#,##0.00', 'align': 'center'
        })
        cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
        num_fmt = workbook.add_format({'border': 1, 'align': 'center', 'num_format': '#,##0.00'})
        
        # Largeur des colonnes
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 20)
            
        # Formater les cellules de données
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = df.iloc[r, c]
                if isinstance(val, (int, float)):
                    worksheet.write(r + 2, c, val, num_fmt)
                else:
                    worksheet.write(r + 2, c, str(val), cell_fmt)
                    
        # Ligne de TOTAL automatique
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 1, df['Quantité'].sum(), total_fmt)
        worksheet.write(last_row, 2, "", total_fmt)
        worksheet.write(last_row, 3, "", total_fmt)
        worksheet.write(last_row, 4, "", total_fmt)
        worksheet.write(last_row, 5, "", total_fmt)
        worksheet.write(last_row, 6, "", total_fmt)
        worksheet.write(last_row, 7, df['Poids Total (kg)'].sum(), total_fmt)
        worksheet.write(last_row, 8, df['Surface Totale (m²)'].sum(), total_fmt)
        
    return output.getvalue()

# --- 5. INTERFACE DESIGN "GLASSMORPHIC ULTRA" ---
st.set_page_config(page_title="Metrai AI Elite V12", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Syncopate:wght@700&display=swap');
    
    .stApp { background-color: #050508; color: #e0e6ed; font-family: 'Outfit', sans-serif; }
    
    /* Titre Glitch Moderne */
    .brand-title {
        font-family: 'Syncopate', sans-serif;
        font-weight: 700;
        font-size: 42px;
        text-align: center;
        background: linear-gradient(135deg, #ed7d31 0%, #ff5e36 50%, #ff8c52 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: 5px;
        margin-bottom: 5px;
        filter: drop-shadow(0 2px 10px rgba(237, 125, 49, 0.3));
    }
    .brand-subtitle {
        text-align: center;
        font-size: 14px;
        color: #8892b0;
        letter-spacing: 2px;
        margin-bottom: 40px;
    }
    
    /* Cartes Glassmorphism */
    .glass-card {
        background: rgba(20, 20, 30, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 30px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        backdrop-filter: blur(8px);
        margin-bottom: 25px;
    }
    
    /* Boutons Orange Dégradé */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #ed7d31 0%, #ff5e36 100%) !important;
        color: white !important;
        font-weight: 800 !important;
        border-radius: 12px !important;
        padding: 1rem !important;
        border: none !important;
        letter-spacing: 2px;
        font-family: 'Outfit', sans-serif;
        font-size: 16px;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(237, 125, 49, 0.4);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(237, 125, 49, 0.6);
    }
    
    /* Blocs de Métriques Lumineux */
    .metric-container {
        display: flex;
        justify-content: space-between;
        gap: 15px;
        margin-bottom: 30px;
    }
    .metric-box {
        flex: 1;
        background: rgba(255, 255, 255, 0.02);
        border: 1px solid rgba(255, 255, 255, 0.05);
        padding: 22px;
        border-radius: 16px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .metric-box:hover {
        background: rgba(237, 125, 49, 0.05);
        border-color: rgba(237, 125, 49, 0.3);
        transform: scale(1.02);
    }
    .metric-value {
        font-size: 32px;
        font-weight: 800;
        color: #ff5e36;
        margin-top: 5px;
        text-shadow: 0 0 10px rgba(255, 94, 54, 0.3);
    }
    .metric-label {
        font-size: 12px;
        color: #8892b0;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 6. LOGIQUE DE NAVIGATION DE L'APPLICATION ---
if 'step' not in st.session_state: st.session_state.step = 'upload'
if 'results' not in st.session_state: st.session_state.results = []
if 'file_bytes' not in st.session_state: st.session_state.file_bytes = None

# --- ETAPE 1 : TELEVERSEMENT ---
if st.session_state.step == 'upload':
    st.markdown('<div class="brand-title">METRAI AI ELITE</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-subtitle">Automated structural quantity takeoff with real-time reactive recalculations</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    file = st.file_uploader("Glissez-déposez votre plan de structure métallique (PDF)", type="pdf")
    
    if file:
        st.success("✅ Fichier PDF chargé avec succès ! Prêt pour l'analyse structurelle.")
        if st.button("🚀 LANCER L'EXTRACTION INTELLIGENTE"):
            st.session_state.file_bytes = file.read()
            st.session_state.step = 'processing'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- ETAPE 2 : PIPELINE DE TRAITEMENT (OCR + AI) ---
elif st.session_state.step == 'processing':
    st.markdown('<div class="brand-title">EXTRACTION EN COURS</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-subtitle">Processing PDF plans with High-Definition Vision and Pixtral...</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="glass-card" style="text-align: center;">', unsafe_allow_html=True)
    status = st.empty()
    progress = st.progress(0)
    
    try:
        doc = fitz.open(stream=st.session_state.file_bytes, filetype="pdf")
        all_members = []
        
        for i in range(len(doc)):
            status.markdown(f"🧬 **Analyse HD en cours : Page {i+1} sur {len(doc)}...**")
            # Pixmap haute résolution 3.5x
            pix = doc[i].get_pixmap(matrix=fitz.Matrix(3.5, 3.5))
            b64_image = enhance_image(pix)
            
            prompt = """As a Structural Takeoff Expert, extract EVERY steel member. 
            Profiles to look for: IPE, HEA, HEB, UPN, L, SQ, RO.
            Extract: profile, quantity, length_m, type, location.
            Return JSON STRICT: {"members": [{"profile": "IPE 300", "quantity": 5, "length_m": 12.0, "type": "Poutre", "location": "Niveau 1"}]}"""
            
            res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
                "model": "pixtral-12b-2409",
                "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64_image}"}]}],
                "response_format": {"type": "json_object"}
            }, timeout=120)
            
            if res.status_code == 200:
                data = json.loads(res.json()['choices'][0]['message']['content'])
                all_members.extend(data.get('members', []))
            
            progress.progress((i + 1) / len(doc))
            time.sleep(0.5)
            
        st.session_state.results = all_members
        st.session_state.step = 'results'
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Erreur lors de l'analyse : {e}")
        if st.button("⬅️ RETOURNER AU TÉLÉCHARGEMENT"):
            st.session_state.step = 'upload'
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# --- ETAPE 3 : TABLEAU DE BORD REACTIF & EXPORT ---
elif st.session_state.step == 'results':
    st.markdown('<div class="brand-title">RÉSULTATS DE MÉTRÉ</div>', unsafe_allow_html=True)
    st.markdown('<div class="brand-subtitle">Inspect, modify, and export your structural data in real-time</div>', unsafe_allow_html=True)
    
    if not st.session_state.results:
        st.error("⚠️ Aucune donnée n'a été détectée dans le document.")
        if st.button("⬅️ RETOURNER AU TÉLÉCHARGEMENT"):
            st.session_state.step = 'upload'
            st.rerun()
    else:
        # Création du DataFrame initial
        raw_df = pd.DataFrame(st.session_state.results)
        
        # Mappings flexibles pour supporter les clés en Anglais / Français retournées par l'IA
        mappings = {
            'profil': 'Profilé', 'profile': 'Profilé',
            'quantite': 'Quantité', 'quantity': 'Quantité',
            'longueur': 'Longueur (m)', 'length_m': 'Longueur (m)',
            'type': 'Type', 'location': 'Localisation', 'localisation': 'Localisation'
        }
        raw_df.columns = [mappings.get(c.lower(), c) for c in raw_df.columns]
        
        # S'assurer que toutes les colonnes requises existent
        for col in ['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation']:
            if col not in raw_df.columns:
                raw_df[col] = "" if col in ['Profilé', 'Type', 'Localisation'] else 1.0
                
        # Re-ordonner et typer proprement
        raw_df = raw_df[['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation']]
        raw_df['Quantité'] = pd.to_numeric(raw_df['Quantité'], errors='coerce').fillna(1).astype(int)
        raw_df['Longueur (m)'] = pd.to_numeric(raw_df['Longueur (m)'], errors='coerce').fillna(1.0)
        raw_df['Profilé'] = raw_df['Profilé'].astype(str).str.upper().str.strip()
        
        st.write("📋 **Tableau interactif : double-cliquez sur n'importe quelle cellule pour éditer et recalculer instantanément.**")
        
        # --- EDITEUR INTERACTIF REACTIF (MICRO-SECONDES RECALCULATIONS) ---
        edited_df = st.data_editor(raw_df, num_rows="dynamic", use_container_width=True)
        
        # Processus de recalcul dynamique après l'édition
        edited_df['Quantité'] = pd.to_numeric(edited_df['Quantité'], errors='coerce').fillna(1).astype(int)
        edited_df['Longueur (m)'] = pd.to_numeric(edited_df['Longueur (m)'], errors='coerce').fillna(1.0)
        edited_df['Profilé'] = edited_df['Profilé'].astype(str).str.upper().str.strip()
        
        # Récupération dynamique depuis la STEEL_DB (Poids & Peinture)
        edited_df['Poids Unit (kg/m)'] = edited_df['Profilé'].apply(lambda x: STEEL_DB.get(x, (0.0, 0.0))[0])
        edited_df['Surface Unit (m²/m)'] = edited_df['Profilé'].apply(lambda x: STEEL_DB.get(x, (0.0, 0.0))[1])
        
        # Calcul des totaux par ligne
        edited_df['Poids Total (kg)'] = edited_df['Poids Unit (kg/m)'] * edited_df['Longueur (m)'] * edited_df['Quantité']
        edited_df['Surface Totale (m²)'] = edited_df['Surface Unit (m²/m)'] * edited_df['Longueur (m)'] * edited_df['Quantité']
        
        # Réorganisation finale pour l'affichage et l'export
        final_df = edited_df[[
            'Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation', 
            'Poids Unit (kg/m)', 'Surface Unit (m²/m)', 'Poids Total (kg)', 'Surface Totale (m²)'
        ]]
        
        # Totaux généraux
        total_poids = final_df['Poids Total (kg)'].sum()
        total_tonnes = total_poids / 1000
        total_surface = final_df['Surface Totale (m²)'].sum()
        total_pieces = final_df['Quantité'].sum()
        
        # --- CARDS KPI EN HSL DÉGRADÉ ---
        st.markdown(f"""
            <div class="metric-container">
                <div class="metric-box">
                    <div class="metric-label">Poids Total</div>
                    <div class="metric-value">{total_poids:,.2f} kg</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Tonnage Métrique</div>
                    <div class="metric-value">{total_tonnes:.3f} Tons</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Surface de Peinture</div>
                    <div class="metric-value">{total_surface:,.2f} m²</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">Éléments Totaux</div>
                    <div class="metric-value">{int(total_pieces)} Pcs</div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.write("---")
        
        # Boutons d'export et nouvelle analyse
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            st.download_button(
                "📥 TÉLÉCHARGER LE RAPPORT EXCEL CORPORATE", 
                generate_excel_pro(final_df), 
                "Metrai_Elite_Rapport.xlsx"
            )
        with col_btn2:
            if st.button("🔄 NOUVELLE ANALYSE DE DE PLAN"):
                st.session_state.step = 'upload'
                st.session_state.results = []
                st.session_state.file_bytes = None
                st.rerun()
                
        st.write("### 📋 Détail complet du métré calculé")
        st.dataframe(final_df.style.format({
            'Longueur (m)': '{:.2f}',
            'Poids Unit (kg/m)': '{:.2f}',
            'Surface Unit (m²/m)': '{:.3f}',
            'Poids Total (kg)': '{:.2f}',
            'Surface Totale (m²)': '{:.2f}'
        }), use_container_width=True)
