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

# --- 2. STEEL DATABASE ---
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 240": 30.7, "IPE 270": 36.1, "IPE 300": 42.2,
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5, "HEA 200": 42.3,
    "UPN 80": 8.64, "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8, "UPN 200": 25.3,
    "L 40X40X4": 2.42, "L 50X50X5": 3.77, "L 60X60X6": 5.42, "SQ 80X80X5": 11.6, "RO 48.3X3.2": 3.56
}

def generate_excel_pro(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Analysis', startrow=1)
        workbook, worksheet = writer.book, writer.sheets['Analysis']
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#ED7D31', 'font_color': 'white', 'border': 1})
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(1, col_num, value, header_fmt)
        last_row = len(df) + 2
        worksheet.write(last_row, 0, "TOTAL GENERAL", header_fmt)
        worksheet.write(last_row, 6, df['Poids Total (kg)'].sum(), header_fmt)
    return output.getvalue()

st.set_page_config(page_title="Metrai AI Expert", layout="wide")

if 'results' not in st.session_state: st.session_state.results = []
if 'step' not in st.session_state: st.session_state.step = 'upload'

if st.session_state.step == 'upload':
    st.title("🏗️ Metrai AI : Structural Engine")
    file = st.file_uploader("Upload Plan (PDF)", type="pdf")
    if file and st.button("LANCER L'ANALYSE"):
        st.session_state.file = file
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    st.info("🔍 Intelligence Visionnaire en cours... (Multi-grid scanning)")
    doc = fitz.open(stream=st.session_state.file.read(), filetype="pdf")
    all_members = []
    
    for p_num in range(len(doc)):
        # Resolution mat-fouch 3.0 bach l-API may-t-bloquach
        pix = doc[p_num].get_pixmap(matrix=fitz.Matrix(3, 3)) 
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # PROMPT J-D-I-D (Detailed Instruction)
        prompt = """You are a structural engineer takeoff expert. 
        Look closely at the technical annotations, labels, and schedules in this drawing.
        Identify ALL steel members. Search for profile names like IPE, HEA, UPN, L (Angle), RO (Round Tube), SQ (Square Tube).
        
        Return a JSON object with this exact structure:
        {"members": [{"profile": "IPE 200", "quantity": 1, "length_m": 6.5, "type": "Column", "location": "Grid A1"}]}
        
        Note: If no members are found, return {"members": []}. Be exhaustive!"""

        try:
            res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
                "model": "pixtral-12b-2409",
                "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
                "response_format": {"type": "json_object"}
            }, timeout=90)
            
            if res.status_code == 200:
                data = json.loads(res.json()['choices'][0]['message']['content'])
                all_members.extend(data.get('members', []))
        except Exception as e:
            st.warning(f"Skipped page {p_num+1}")
            
    st.session_state.results = all_members
    st.session_state.step = 'results'
    st.rerun()

elif st.session_state.step == 'results':
    if not st.session_state.results:
        st.error("⚠️ Hta chi profilé ma-t-detected. Jrb t-sift PDF kiy-ban fih l-ketba (Text) mzyan.")
        if st.button("REESSAYER"): st.session_state.step = 'upload'; st.rerun()
    else:
        df = pd.DataFrame(st.session_state.results)
        # Ensure columns exist
        for c in ['quantity', 'length_m', 'profile']:
            if c not in df.columns: df[c] = 0 if c != 'profile' else "UNKNOWN"
            
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        df['length_m'] = pd.to_numeric(df['length_m'], errors='coerce').fillna(0)
        df['profile'] = df['profile'].astype(str).str.upper().str.strip()
        df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
        df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
        
        st.success("✅ Analyse Terminée!")
        st.metric("POIDS TOTAL", f"{df['Poids Total (kg)'].sum():,.2f} kg")
        st.dataframe(df, use_container_width=True)
        st.download_button("📥 DOWNLOAD EXCEL", generate_excel_pro(df), "Metrai_Report.xlsx")
        if st.button("NEW SCAN"): st.session_state.step = 'upload'; st.rerun()