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
# L-API Key jdida li t-f33lat
API_KEY = "f7ks56hsee94BkBwuiNUqiXey4fwb6Ti".strip() 
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# --- 2. DATABASE STEEL (EUROPEAN STANDARDS) ---
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 220": 26.2, "IPE 240": 30.7, "IPE 270": 36.1,
    "IPE 300": 42.2, "IPE 330": 49.1, "IPE 360": 57.1, "IPE 400": 66.3, "IPE 450": 77.6,
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5,
    "HEA 200": 42.3, "HEA 220": 50.5, "HEA 240": 60.3, "HEA 260": 68.2, "HEA 280": 76.4,
    "HEA 300": 88.3, "HEB 100": 20.4, "HEB 120": 26.7, "HEB 140": 33.7, "HEB 160": 42.6, 
    "HEB 180": 51.2, "HEB 200": 61.3, "HEB 240": 83.2, "HEB 300": 117.0, "UPN 80": 8.6, 
    "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8, "UPN 200": 25.3
}

# --- 3. EXCEL PRO GENERATOR (ORANGE & BLACK STYLE) ---
def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Metrai_Analysis', startrow=1)
        workbook = writer.book
        worksheet = writer.sheets['Metrai_Analysis']

        # Formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#222222', 'font_color': 'white', 'border': 1, 'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'italic': True, 'font_size': 10})

        # Set Header
        worksheet.write(0, 0, f"Date: {time.strftime('%d/%m/%Y %H:%M')}", date_fmt)
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 18)

        # TOTAL GENERAL Row
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GENERAL", total_fmt)
        worksheet.write(last_row, 1, df['quantity'].sum(), total_fmt)
        for c in range(2, 6): worksheet.write(last_row, c, "", total_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), total_fmt)

    return output.getvalue()

# --- 4. INTERFACE UI ---
st.set_page_config(page_title="Metrai AI Ultra Pro", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0c0c0c; color: white; font-family: sans-serif; }
    .status-card { background: #1a1a1a; padding: 25px; border-radius: 15px; border: 1px solid #ed7d31; text-align: center; }
    .scan-anim { 
        height: 4px; background: #ed7d31; box-shadow: 0 0 15px #ed7d31; 
        width: 100%; animation: scan 2s infinite alternate; 
    }
    @keyframes scan { from { opacity: 0.2; transform: scaleX(0.1); } to { opacity: 1; transform: scaleX(1); } }
    .typing { color: #ed7d31; font-family: monospace; font-size: 1.2em; }
    </style>
""", unsafe_allow_html=True)

if 'step' not in st.session_state: st.session_state.step = 'upload'

if st.session_state.step == 'upload':
    st.title("🏗️ Metrai AI : Expert Analysis")
    st.write("Analyse automatique des profilés métalliques.")
    file = st.file_uploader("", type="pdf")
    if file and st.button("LANCER L'EXTRACTION"):
        st.session_state.file = file
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    # Sh-sh-na l-mouchkil dyal single quotes hna
    st.markdown('<div class="status-card"><h3>Analyse en cours...</h3><div class="scan-anim"></div></div>', unsafe_allow_html=True)
    
    log_area = st.empty()
    logs = ["Lectures des calques PDF...", "Identification des profilés...", "Calcul des masses...", "Génération du rapport..."]
    
    # PDF Conversion
    doc = fitz.open(stream=st.session_state.file.read(), filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
    
    for log in logs:
        log_area.markdown(f'<p class="typing">> {log}</p>', unsafe_allow_html=True)
        time.sleep(0.8)
    
    prompt = """Extract all steel members from plan. 
    Required Fields: profile, quantity, length_m, type, location.
    JSON Output: {"members": [{"profile": "IPE 400", "quantity": 1, "length_m": 12.0, "type": "Main Beam", "location": "Roof"}]}"""

    res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
        "model": "pixtral-12b-2409",
        "messages": [{"role": "user", "content": [{"type":"text","text":prompt}, {"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
        "response_format": {"type": "json_object"}
    })
    
    if res.status_code == 200:
        st.session_state.results = json.loads(res.json()['choices'][0]['message']['content'])['members']
        st.session_state.step = 'results'
        st.rerun()
    else:
        st.error(f"Error {res.status_code}. Key or Limit issue.")
        if st.button("Restart"): st.session_state.step = 'upload'; st.rerun()

elif st.session_state.step == 'results':
    df = pd.DataFrame(st.session_state.results)
    
    # Technical Calculations
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['length_m'] = pd.to_numeric(df['length_m'], errors='coerce').fillna(0)
    df['profile'] = df['profile'].astype(str).str.upper().str.strip()
    df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
    
    st.header("📊 Natija dyal l-Métré")
    
    # Professional Buttons
    c1, c2 = st.columns(2)
    with c1:
        excel_pro = generate_excel_pro(df)
        st.download_button("📥 TÉLÉCHARGER EXCEL PRO (Style Pro)", excel_pro, "Rapport_Metrai_Final.xlsx")
    with c2:
        if st.button("🔄 ANALYSER NOUVEAU PLAN"):
            st.session_state.step = 'upload'
            st.rerun()

    st.write("---")
    # Result Display
    st.metric("TOTAL GÉNÉRAL", f"{df['Poids Total (kg)'].sum():,.2f} kg")
    st.dataframe(df.style.format(precision=2).background_gradient(cmap='Oranges'), use_container_width=True)