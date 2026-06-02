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

# --- 2. DATABASE PRO (FULL EUROPEAN STANDARDS) ---
STEEL_DB = {
    "IPE 600": 122.0, "IPE 550": 106.0, "IPE 500": 90.7, "IPE 450": 77.6, "IPE 400": 66.3,
    "IPE 360": 57.1, "IPE 330": 49.1, "IPE 300": 42.2, "IPE 270": 36.1, "IPE 240": 30.7,
    "IPE 220": 26.2, "IPE 200": 22.4, "IPE 180": 18.8, "IPE 160": 15.8, "IPE 140": 12.9,
    "HEA 100": 16.7, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5, "HEA 200": 42.3, "HEA 220": 50.5,
    "UPN 80": 8.64, "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8, "UPN 200": 25.3,
    "L 120X120X12": 21.6, "L 100X80X10": 13.5, "L 60X60X6": 5.42, "L 50X50X5": 3.77,
    "SQ 100X100X10": 27.4, "SQ 80X80X5": 11.6, "RO 48.3X3.2": 3.56
}

# --- 3. EXCEL PRO ENGINE ---
def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Metrai_Final', startrow=1)
        workbook = writer.book
        worksheet = writer.sheets['Metrai_Final']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#222222', 'font_color': 'white', 'border': 1, 'num_format': '#,##0.00'})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 20)
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 1, df['Quantité'].sum(), total_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), total_fmt)
    return output.getvalue()

# --- 4. INTERFACE ---
st.set_page_config(page_title="Metrai AI Ultra Pro", layout="wide")
st.markdown("""<style>.stApp { background-color: #0c0c0c; color: white; }
.stButton>button { width: 100%; background: linear-gradient(135deg, #ed7d31 0%, #ff9a44 100%) !important; color: white !important; font-weight: 800 !important; border-radius: 12px !important; padding: 1rem !important; border: none !important; }
.metric-box { background: #1a1a1a; padding: 20px; border-radius: 15px; border-bottom: 4px solid #ed7d31; text-align: center; }</style>""", unsafe_allow_html=True)

if 'step' not in st.session_state: st.session_state.step = 'upload'

if st.session_state.step == 'upload':
    st.markdown("<h1 style='text-align:center;'>🏗️ METRAI AI <span style='color:#ed7d31'>ULTRA PRO</span></h1>", unsafe_allow_html=True)
    file = st.file_uploader("Charger n'importe quel plan structural PDF", type="pdf")
    if file and st.button("LANCER L'ANALYSE TECHNIQUE"):
        st.session_state.file_bytes = file.read()
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    doc = fitz.open(stream=st.session_state.file_bytes, filetype="pdf")
    all_members = []
    status = st.empty()
    
    for i in range(len(doc)):
        status.info(f"🔍 Analyse de la Page {i+1}/{len(doc)}...")
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(3.5, 3.5)) 
        b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
        
        prompt = """As a Structural Takeoff Expert, extract EVERY steel member. 
        Return JSON STRICT: {"members": [{"profile": "IPE 400", "quantity": 5, "length_m": 12.0, "type": "Poutre", "location": "Niveau 1"}]}"""

        try:
            res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
                "model": "pixtral-12b-2409", "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
                "response_format": {"type": "json_object"}
            }, timeout=90)
            if res.status_code == 200:
                all_members.extend(json.loads(res.json()['choices'][0]['message']['content']).get('members', []))
        except: pass
    
    st.session_state.results = all_members
    st.session_state.step = 'results'
    st.rerun()

elif st.session_state.step == 'results':
    if not st.session_state.results:
        st.error("Aucune donnée détectée. Vérifiez la netteté du PDF.")
        if st.button("RETOUR"): st.session_state.step = 'upload'; st.rerun()
    else:
        df = pd.DataFrame(st.session_state.results)
        
        # Mapping colonnes flexible
        mapping = {'profil': 'profile', 'quantite': 'quantity', 'longueur': 'length_m', 'qty': 'quantity', 'len': 'length_m'}
        df.columns = [mapping.get(c.lower(), c.lower()) for c in df.columns]

        # Nettoyage strict
        for col in ['quantity', 'length_m']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(1)
            else:
                df[col] = 1

        df['profile'] = df.get('profile', "---").astype(str).str.upper().str.strip()
        df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
        df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
        
        # Renommage pour Excel o Table
        df.columns = ['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation', 'Poids Unit (kg/m)', 'Poids Total (kg)']

        st.markdown("## 📊 RÉSUMÉ GÉNÉRAL")
        m1, m2, m3 = st.columns(3)
        m1.markdown(f'<div class="metric-box">POIDS TOTAL<br><h2>{df["Poids Total (kg)"].sum():,.2f} kg</h2></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-box">TONNAGE<br><h2>{df["Poids Total (kg)"].sum()/1000:.3f} T</h2></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-box">ARTICLES<br><h2>{int(df["Quantité"].sum())} Pcs</h2></div>', unsafe_allow_html=True)
        
        st.write("---")
        b1, b2 = st.columns(2)
        with b1: st.download_button("📥 TÉLÉCHARGER LE RAPPORT EXCEL PRO", generate_excel_pro(df), "Rapport_Metrai_Final.xlsx")
        with b2: 
            if st.button("🔄 NOUVELLE ANALYSE"): st.session_state.step = 'upload'; st.rerun()
            
        st.write("### 📋 DÉTAILS DE L'EXTRACTION")
        st.dataframe(df, use_container_width=True)