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
API_KEY = "f7ks56hsee94BkBwuiNUqiXey4fwb6Ti".strip()
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# --- 2. DATABASE PRO (EUROPEAN STANDARDS) ---
# جبنا هاد الأرقام من الكتالوجات اللي صيفطتي دابا [cite: 30, 64, 73, 966]
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 240": 30.7, "IPE 270": 36.1, "IPE 300": 42.2,
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5, "HEA 200": 42.3,
    "L 40X40X4": 2.42, "L 50X50X5": 3.77, "L 60X60X6": 5.42, "L 70X70X7": 7.38, "L 80X80X8": 9.63,
    "UPN 80": 8.64, "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8,
    "RO 48.3X3.2": 3.56, "RO 60.3X3.2": 4.51, "RO 88.9X3.2": 6.76,
    "SQ 40X40X3": 3.41, "SQ 50X50X4": 5.64, "SQ 80X80X5": 11.6, "SQ 100X100X6": 17.4
}

# --- 3. EXCEL ENGINE (PRO STYLE) ---
def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Metrai_Final_Report', startrow=1)
        workbook, worksheet = writer.book, writer.sheets['Metrai_Final_Report']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1})
        total_fmt = workbook.add_format({'bold': True, 'bg_color': '#222222', 'font_color': 'white', 'border': 1, 'num_format': '#,##0.00'})
        
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
            worksheet.set_column(col_num, col_num, 18)
        
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GÉNÉRAL", total_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), total_fmt)
    return output.getvalue()

# --- 4. INTERFACE UI ---
st.set_page_config(page_title="Metrai AI Ultra v4", layout="wide")
st.markdown("""<style>.stApp { background-color: #0c0c0c; color: white; }
.scan-card { background: #111; padding: 30px; border-radius: 20px; border: 1px solid #ed7d31; text-align: center; }
.loader { border: 4px solid #333; border-top: 4px solid #ed7d31; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: auto; }
@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>""", unsafe_allow_html=True)

if 'results' not in st.session_state: st.session_state.results = []
if 'step' not in st.session_state: st.session_state.step = 'upload'

if st.session_state.step == 'upload':
    st.markdown("<h1 style='text-align:center;'>🏗️ METRAI AI <span style='color:#ed7d31'>ULTRA PRO V4</span></h1>", unsafe_allow_html=True)
    file = st.file_uploader("Upload PDF Structural Plan", type="pdf")
    if file and st.button("LANCER L'ANALYSE EXPERTE"):
        st.session_state.file = file
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    st.markdown('<div class="scan-card"><div class="loader"></div><h3>Intelligence Visionnaire en action...</h3></div>', unsafe_allow_html=True)
    doc = fitz.open(stream=st.session_state.file.read(), filetype="pdf")
    final_list = []
    
    # كيقرا كاع الصفحات وبدقة عالية
    for p_num in range(len(doc)):
        st.write(f"🔍 Scan Page {p_num+1}...")
        pix = doc[p_num].get_pixmap(matrix=fitz.Matrix(3.5, 3.5)) # High Res
        b64 = base64.b64encode(pix.tobytes("png")).decode('utf-8')
        
        prompt = """Expert Steel Take-off: Extract EVERY member. Fields: profile (IPE, HEA, L, SQ, RO), quantity, length_m, type, location.
        JSON format: {"members": [{"profile": "IPE 200", "quantity": 10, "length_m": 6.0, "type": "Beam", "location": "Main Frame"}]}"""
        
        res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
            "model": "pixtral-12b-2409", "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
            "response_format": {"type": "json_object"}
        })
        if res.status_code == 200:
            final_list.extend(json.loads(res.json()['choices'][0]['message']['content'])['members'])
        time.sleep(1)

    st.session_state.results = final_list
    st.session_state.step = 'results'
    st.rerun()

elif st.session_state.step == 'results':
    df = pd.DataFrame(st.session_state.results)
    for c in ['quantity', 'length_m']: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
    df['profile'] = df['profile'].astype(str).str.upper().str.strip()
    df['Poids Unit'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Poids Total (kg)'] = df['Poids Unit'] * df['length_m'] * df['quantity']
    
    st.header("📊 Résultats du Métré Automatisé")
    c1, c2 = st.columns(2)
    with c1: st.download_button("📥 EXCEL PRO", generate_excel_pro(df), "Metrai_Report_V4.xlsx")
    with c2: 
        if st.button("🔄 NOUVEAU SCAN"): st.session_state.step = 'upload'; st.rerun()
    
    st.metric("TONNAGE TOTAL", f"{df['Poids Total (kg)'].sum()/1000:.3f} T")
    st.dataframe(df, use_container_width=True)