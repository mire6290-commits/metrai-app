import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
from PIL import Image
import io
import time
import base64
import requests

# --- 1. CONFIGURATION ---
API_KEY = "tkpq3wSOfVMoWLXee7wP3vHyEgJGm87m".strip()
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# Database Pro (European Standards)
STEEL_DB = {
    "IPE 600": 122.0, "IPE 400": 66.3, "IPE 300": 42.2, "IPE 200": 22.4,
    "HEA 220": 50.5, "HEA 200": 42.3, "UPN 200": 25.3, "UPN 180": 22.0,
    "L 120X120X12": 21.6, "L 100X80X10": 13.5, "SQ 100X100X10": 27.4, "RO 48.3X3.2": 3.56
}

# --- 2. FONCTIONS TECHNIQUES ---
def process_image(pix):
    """Optimise l'image pour l'API Mistral (Max 2000px)"""
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # Redimensionner si trop grand pour éviter le blocage API
    max_size = 2000
    if max(img.size) > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='METRE_ACIER', startrow=1)
        workbook, worksheet = writer.book, writer.sheets['METRE_ACIER']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#000000', 'font_color': '#FFFFFF', 'border': 1, 'num_format': '#,##0.00'})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 20)
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), total_fmt)
    return output.getvalue()

# --- 3. UI STYLE ---
st.set_page_config(page_title="Metrai AI Structural Pro", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, #ed7d31 0%, #ffb366 100%) !important;
        color: white !important;
        font-weight: bold !important;
        border-radius: 10px !important;
        border: none !important;
        padding: 0.7rem !important;
    }
    .metric-card {
        background: #1c2128;
        padding: 20px;
        border-radius: 12px;
        border-top: 3px solid #ed7d31;
        text-align: center;
    }
    </style>
""", unsafe_allow_html=True)

if 'results' not in st.session_state: st.session_state.results = []
if 'step' not in st.session_state: st.session_state.step = 'upload'

# --- 4. LOGIQUE ---
if st.session_state.step == 'upload':
    st.markdown("<h1 style='text-align:center;'>🏗️ METRAI AI <span style='color:#ed7d31'>STRUCTURAL</span></h1>", unsafe_allow_html=True)
    file = st.file_uploader("Charger un plan structural (PDF)", type="pdf")
    if file and st.button("LANCER L'EXTRACTION"):
        st.session_state.file_bytes = file.read()
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    doc = fitz.open(stream=st.session_state.file_bytes, filetype="pdf")
    all_members = []
    
    progress_bar = st.progress(0)
    for i in range(len(doc)):
        st.write(f"Analyse de la page {i+1}...")
        # Resolution équilibrée
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(2.5, 2.5)) 
        b64 = process_image(pix)
        
        prompt = """Identify ALL structural steel members. Look for: IPE, HEA, HEB, UPN, L, SQ, RO.
        Extract: profile, quantity, length_m, type, location.
        JSON format: {"members": [{"profile": "IPE 400", "quantity": 1, "length_m": 12.0, "type": "Poutre", "location": "Toiture"}]}"""

        try:
            res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
                "model": "pixtral-12b-2409",
                "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
                "response_format": {"type": "json_object"}
            }, timeout=60)
            
            if res.status_code == 200:
                data = json.loads(res.json()['choices'][0]['message']['content'])
                all_members.extend(data.get('members', []))
        except Exception as e:
            st.error(f"Erreur Page {i+1}")
        
        progress_bar.progress((i + 1) / len(doc))
    
    st.session_state.results = all_members
    st.session_state.step = 'results'
    st.rerun()

elif st.session_state.step == 'results':
    if not st.session_state.results:
        st.error("Aucune donnée n'a pu être extraite. Vérifiez que le PDF contient bien des annotations de profilés.")
        if st.button("RÉESSAYER"): st.session_state.step = 'upload'; st.rerun()
    else:
        df = pd.DataFrame(st.session_state.results)
        
        # Nettoyage et Calculs
        df['quantity'] = pd.to_numeric(df.get('quantity', 0), errors='coerce').fillna(1)
        df['length_m'] = pd.to_numeric(df.get('length_m', 0), errors='coerce').fillna(1)
        df['profile'] = df.get('profile', "INCONNU").astype(str).str.upper().str.strip()
        
        df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
        df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
        
        # Renommage en Français
        df.columns = ['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation', 'Poids Unit (kg/m)', 'Poids Total (kg)']

        st.markdown("## 📊 RÉSUMÉ DU MÉTRÉ")
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f'<div class="metric-card">POIDS TOTAL<br><h2>{df["Poids Total (kg)"].sum():,.2f} kg</h2></div>', unsafe_allow_html=True)
        with c2: st.markdown(f'<div class="metric-card">TONNAGE<br><h2>{df["Poids Total (kg)"].sum()/1000:.3f} T</h2></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="metric-card">PIÈCES<br><h2>{int(df["Quantité"].sum())}</h2></div>', unsafe_allow_html=True)
        
        st.write("---")
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            st.download_button("📥 TÉLÉCHARGER LE RAPPORT EXCEL", generate_excel_pro(df), "Rapport_Metre_Expert.xlsx")
        with col_b2:
            if st.button("🔄 ANALYSER UN AUTRE PLAN"):
                st.session_state.step = 'upload'
                st.rerun()

        st.write("### 📋 DÉTAILS DE L'EXTRACTION")
        st.dataframe(df.style.format(precision=2), width='stretch')