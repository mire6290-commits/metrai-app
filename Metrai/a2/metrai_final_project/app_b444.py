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
# API Key jdida li t-f33lat
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

# --- 3. EXCEL PRO GENERATOR (IMAGE 2 STYLE) ---
def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Metrai_Analysis', startrow=1)
        workbook = writer.book
        worksheet = writer.sheets['Metrai_Analysis']

        # Formats dial l-orange o l-ghzi
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1, 'align': 'center'})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#222222', 'font_color': 'white', 'border': 1, 'num_format': '#,##0.00'})
        date_fmt = workbook.add_format({'italic': True, 'font_size': 10})

        # Date Header
        worksheet.write(0, 0, f"Date: {time.strftime('%d/%m/%Y %H:%M')}", date_fmt)
        
        # Apply Header Style
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 18)

        # TOTAL Row f'lkher
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GENERAL", total_fmt)
        worksheet.write(last_row, 1, df['quantity'].sum(), total_fmt)
        for c in range(2, 6): worksheet.write(last_row, c, "", total_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), total_fmt)

    return output.getvalue()

# --- 4. STYLE ULTRA MODERN ---
st.set_page_config(page_title="Metrai AI Ultra Pro", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0c0c0c; color: white; font-family: 'Inter', sans-serif; }
    .glass-card { 
        background: #151515; padding: 30px; border-radius: 20px; 
        border: 1px solid #ed7d31; text-align: center; margin-bottom: 20px;
    }
    .scanner-line { 
        height: 3px; background: #ed7d31; box-shadow: 0 0 20px #ed7d31; 
        width: 100%; animation: scan 2s infinite alternate; 
    }
    @keyframes scan { from { opacity: 0.1; transform: scaleX(0.1); } to { opacity: 1; transform: scaleX(1); } }
    .log-text { color: #ed7d31; font-family: 'Courier New', monospace; font-size: 14px; text-align: left; }
    </style>
""", unsafe_allow_html=True)

# --- 5. APP LOGIC ---
if 'step' not in st.session_state: st.session_state.step = 'upload'

if st.session_state.step == 'upload':
    st.markdown("<h1 style='text-align:center; color:#ed7d31;'>METRAI AI ULTRA PRO</h1>", unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.write("Sift l-plan PDF dyalk bach n-khrej lik l-métré m-fini.")
    file = st.file_uploader("", type="pdf", label_visibility="collapsed")
    if file and st.button("🚀 DÉMARRER L'EXTRACTION"):
        st.session_state.file = file
        st.session_state.step = 'processing'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.step == 'processing':
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.markdown("### 🧬 Analyse des calques structuraux...")
    st.markdown('<div class="scanner-line"></div>', unsafe_allow_html=True)
    
    log_area = st.empty()
    logs = ["> Initialisation du moteur...", "> Lecture des fichiers PDF...", "> Identification des profilés (IPE, HEA, UPN)...", "> Calcul des poids volumiques...", "> Génération du rapport final..."]
    
    # PDF Conversion
    doc = fitz.open(stream=st.session_state.file.read(), filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
    
    # Haraka dial l-logs
    current_logs = ""
    for log in logs:
        current_logs += f"{log}<br>"
        log_area.markdown(f'<div class="log-text">{current_logs}</div>', unsafe_allow_html=True)
        time.sleep(0.7)
    
    prompt = """EXPERT TASK: Extract steel members. Fields: profile, quantity, length_m, type, location.
    JSON Output: {"members": [{"profile": "IPE 300", "quantity": 12, "length_m": 6.0, "type": "Beam", "location": "Main Frame"}]}"""

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
        st.error(f"Error {res.status_code}. Key issue or API Limit.")
        if st.button("Restart"): st.session_state.step = 'upload'; st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.step == 'results':
    df = pd.DataFrame(st.session_state.results)
    
    # Data Cleaning o Calculations
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['length_m'] = pd.to_numeric(df['length_m'], errors='coerce').fillna(0)
    df['profile'] = df['profile'].astype(str).str.upper().str.strip()
    df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
    
    st.markdown("<h2 style='color:#ed7d31;'>📊 RAPPORT D'ANALYSE</h2>", unsafe_allow_html=True)
    
    c1, c2 = st.columns(2)
    with c1:
        xlsx_pro = generate_excel_pro(df)
        st.download_button("📥 TÉLÉCHARGER EXCEL PRO", xlsx_pro, "Metrai_Pro_Report.xlsx")
    with c2:
        if st.button("🔄 ANALYSER UN AUTRE PLAN"):
            st.session_state.step = 'upload'
            st.rerun()

    st.write("---")
    st.metric("TOTAL GÉNÉRAL", f"{df['Poids Total (kg)'].sum():,.2f} kg")
    
    # Tableau bla matplotlib background_gradient bach may-3tikch erreur
    st.dataframe(df, use_container_width=True)