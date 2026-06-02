import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
from PIL import Image
import io
import time
import base64
import requests

# --- 1. CONFIGURATION API ---
API_KEY = "UlDghRzTjVDhufJTyFVO2auuPhd0j8AJ"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# --- 2. STYLE L-INTERFACE ---
st.set_page_config(page_title="Metrai Structure Pro", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f6; }
    .stProgress > div > div > div > div { background-color: #f26522; }
    
    .big-number { 
        font-size: 85px; 
        font-weight: 900; 
        color: #f26522; 
        text-align: center; 
        margin: 0;
        line-height: 1;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .metric-label {
        font-size: 22px;
        text-align: center;
        color: #444;
        font-weight: 600;
        margin-bottom: 20px;
    }
    
    .total-card {
        background: linear-gradient(135deg, #ffffff 0%, #f9f9f9 100%);
        padding: 25px;
        border-radius: 20px;
        border-bottom: 6px solid #f26522;
        box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        text-align: center;
        transition: transform 0.3s ease;
    }
    .total-card:hover { transform: translateY(-5px); }
    
    .stDownloadButton > button {
        width: 100%;
        background-color: #f26522;
        color: white;
        border-radius: 15px;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
        border: none;
        box-shadow: 0 4px 15px rgba(242, 101, 34, 0.3);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE ---
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 220": 26.2, "IPE 240": 30.7, "IPE 270": 36.1,
    "IPE 300": 42.2, "IPE 330": 49.1, "IPE 360": 57.1, "IPE 400": 66.3, "IPE 450": 77.6,
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5,
    "HEA 200": 42.3, "HEA 220": 50.5, "HEA 240": 60.3, "HEB 160": 42.6, "HEB 200": 61.3,
    "HEB 240": 83.2, "HEB 300": 117.0, "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0
}

def encode_image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def generate_pro_excel(df, total_kg, total_qty):
    output = io.BytesIO()
    # Utilisation de XlsxWriter pour un design pro
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Metrai_Report')
    
    workbook  = writer.book
    worksheet = writer.sheets['Metrai_Report']
    
    # Formats
    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'vcenter',
        'fg_color': '#f26522', 'font_color': '#ffffff', 'border': 1
    })
    num_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
    total_format = workbook.add_format({'bold': True, 'fg_color': '#333333', 'font_color': '#ffffff', 'border': 1})
    
    # Appliquer le header
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(0, col_num, value, header_format)
        worksheet.set_column(col_num, col_num, 15)
    
    # Ajouter la ligne de TOTAL à la fin
    last_row = len(df) + 1
    worksheet.write(last_row, 0, "TOTAL GENERAL", total_format)
    worksheet.write(last_row, 1, total_qty, total_format) # Qty total
    worksheet.write(last_row, 6, total_kg, total_format) # Poids total (colonne 6)
    
    writer.close()
    return output.getvalue()

# --- 4. APP LOGIC ---
st.title("🏗️ Metrai Structure AI — Premium Edition")

uploaded_file = st.file_uploader("Charger le plan PDF", type="pdf")

if uploaded_file:
    status_p = st.empty()
    prog_p = st.progress(0)
    num_p = st.empty()

    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    prog_p.progress(15)
    
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    base64_image = encode_image_to_base64(img)
    prog_p.progress(40)

    status_p.info("🚀 Pixtral-Vision is analyzing all sections...")

    prompt = """EXPERT ANALYSIS: Extract all steel members from this drawing.
    Return JSON: {"members": [{"profile": "IPE 270", "quantity": 10, "length_m": 6.5, "type": "Beam", "location": "Grid 1-5"}]}
    Rules: Be 100% exhaustive. Return ONLY JSON."""

    try:
        response = requests.post(MISTRAL_URL, 
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "pixtral-12b-2409",
                "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}]}],
                "response_format": {"type": "json_object"}, "temperature": 0
            })
        
        if response.status_code == 200:
            data = json.loads(response.json()['choices'][0]['message']['content'])
            members = data.get('members', [])
            
            for i in range(len(members) + 1):
                num_p.markdown(f'<div class="big-number">{i}</div><div class="metric-label">Éléments Identifiés</div>', unsafe_allow_html=True)
                time.sleep(0.03)

            prog_p.progress(100)
            status_p.empty()

            if members:
                df = pd.DataFrame(members)
                df['profile'] = df['profile'].astype(str).str.upper().str.strip()
                df['Unit Weight (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
                df['Total Weight (kg)'] = df['Unit Weight (kg/m)'] * df['length_m'] * df['quantity']
                
                total_kg = df['Total Weight (kg)'].sum()
                total_ton = total_kg / 1000
                total_qty = df['quantity'].sum()

                # Dashboard
                st.write("### 📊 Récapitulatif du Projet")
                c1, c2, c3 = st.columns(3)
                with c1: st.markdown(f'<div class="total-card"><h3>TOTAL PIÈCES</h3><h2 style="color:#f26522;">{int(total_qty)}</h2><p>Profilés</p></div>', unsafe_allow_html=True)
                with c2: st.markdown(f'<div class="total-card"><h3>TOTAL TONNAGE</h3><h2 style="color:#f26522;">{total_ton:.3f}</h2><p>Tonnes</p></div>', unsafe_allow_html=True)
                with c3: st.markdown(f'<div class="total-card"><h3>POIDS GLOBAL</h3><h2 style="color:#f26522;">{total_kg:,.1f}</h2><p>Kilogrammes</p></div>', unsafe_allow_html=True)

                st.write("### 📋 Détails des Profilés")
                st.dataframe(df, use_container_width=True)

                # Excel Generation
                excel_data = generate_pro_excel(df, total_kg, total_qty)
                
                st.write("---")
                st.download_button(
                    label="📥 TÉLÉCHARGER LE MÉTRÉ PROFESSIONNEL (EXCEL PRO)",
                    data=excel_data,
                    file_name=f"Metrai_Report_{uploaded_file.name.split('.')[0]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Aucun élément détecté.")
        else:
            st.error("API Error")
    except Exception as e:
        st.error(f"Error: {str(e)}")
else:
    st.info("Glissez votre plan ici pour commencer.")