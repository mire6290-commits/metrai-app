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

# Steel Database Pro
STEEL_DB = {
    "IPE 600": 122.0, "IPE 400": 66.3, "IPE 300": 42.2, "HEA 220": 50.5,
    "UPN 200": 25.3, "UPN 180": 22.0, "L 120X120X12": 21.6, "L 100X80X10": 13.5,
    "SQ 100X100X10": 27.4, "RO 48.3X3.2": 3.56, "RO (TUYAU ROND)": 3.56, "IPE 200": 22.4
}

# --- 2. TRAITEMENT D'IMAGE AVANCÉ ---
def enhance_image(pix):
    """Améliore la lisibilité du texte sur le plan"""
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    # Convertir en niveaux de gris et booster le contraste
    img = img.convert('L')
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)
    
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
st.set_page_config(page_title="Metrai AI Ultra Pro V11", layout="wide")
st.markdown("""<style>.stApp { background-color: #0c0c0c; color: white; }
.stButton>button { width: 100%; background: linear-gradient(135deg, #ed7d31 0%, #ff9a44 100%) !important; color: white !important; font-weight: 800 !important; border-radius: 12px !important; padding: 1rem !important; border: none !important; }
.metric-box { background: #1a1a1a; padding: 20px; border-radius: 15px; border-bottom: 4px solid #ed7d31; text-align: center; }</style>""", unsafe_allow_html=True)

if 'results' not in st.session_state: st.session_state.results = []
if 'step' not in st.session_state: st.session_state.step = 'upload'

# --- 4. LOGIQUE PRINCIPALE ---
if st.session_state.step == 'upload':
    st.markdown("<h1 style='text-align:center;'>🏗️ METRAI AI <span style='color:#ed7d31'>ELITE V11</span></h1>", unsafe_allow_html=True)
    file = st.file_uploader("Upload PLAN.pdf", type="pdf")
    if file and st.button("LANCER L'ANALYSE DE STRUCTURE"):
        st.session_state.file_bytes = file.read()
        st.session_state.step = 'processing'
        st.rerun()

elif st.session_state.step == 'processing':
    doc = fitz.open(stream=st.session_state.file_bytes, filetype="pdf")
    all_members = []
    status = st.empty()
    
    for i in range(len(doc)):
        status.info(f"🔍 Analyse Haute Définition Page {i+1}/{len(doc)}...")
        # On utilise une résolution de 3.0 (suffisant avec le contraste boosté)
        pix = doc[i].get_pixmap(matrix=fitz.Matrix(3.0, 3.0)) 
        b64 = enhance_image(pix)
        
        prompt = """As a Structural Engineering expert, perform a full takeoff of this drawing.
        List every steel profile (IPE, HEA, UPN, L, SQ, RO). 
        You must return a valid JSON object only: {"members": [{"profile": "IPE 600", "quantity": 10, "length_m": 23.6, "type": "Poutre", "location": "Toiture"}]}"""

        try:
            res = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}"}, json={
                "model": "pixtral-12b-2409", 
                "messages": [{"role":"user","content":[{"type":"text","text":prompt},{"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
                "response_format": {"type": "json_object"}
            }, timeout=120)
            
            if res.status_code == 200:
                data = json.loads(res.json()['choices'][0]['message']['content'])
                all_members.extend(data.get('members', []))
            else:
                st.error(f"API Error {res.status_code}: {res.text}")
        except Exception as e:
            st.error(f"Connection Error: {e}")
        time.sleep(1)

    st.session_state.results = all_members
    st.session_state.step = 'results'
    st.rerun()

elif st.session_state.step == 'results':
    if not st.session_state.results:
        st.error("Aucune donnée détectée. Vérifiez vos crédits Mistral ou la clarté du PDF.")
        if st.button("REESSAYER"): st.session_state.step = 'upload'; st.rerun()
    else:
        df = pd.DataFrame(st.session_state.results)
        # Nettoyage et Calculs Pro
        df['quantity'] = pd.to_numeric(df.get('quantity', 1), errors='coerce').fillna(1)
        df['length_m'] = pd.to_numeric(df.get('length_m', 1), errors='coerce').fillna(1)
        df['profile'] = df.get('profile', "---").astype(str).str.upper().str.strip()
        
        df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
        df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
        
        df.columns = ['Profilé', 'Quantité', 'Longueur (m)', 'Type', 'Localisation', 'Poids Unit (kg/m)', 'Poids Total (kg)']

        st.markdown("## 📊 RÉSULTATS DU MÉTRÉ")
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div class="metric-box">POIDS TOTAL<br><h2>{df["Poids Total (kg)"].sum():,.2f} kg</h2></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="metric-box">TONNAGE<br><h2>{df["Poids Total (kg)"].sum()/1000:.3f} T</h2></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="metric-box">TOTAL ÉLÉMENTS<br><h2>{int(df["Quantité"].sum())}</h2></div>', unsafe_allow_html=True)
        
        st.write("---")
        btn_a, btn_b = st.columns(2)
        with btn_a: st.download_button("📥 TÉLÉCHARGER LE MÉTRÉ EXCEL", generate_excel_pro(df), "Metre_Expert_Elite.xlsx")
        with btn_b: 
            if st.button("🔄 NOUVEAU PROJET"): st.session_state.step = 'upload'; st.rerun()
            
        st.dataframe(df.style.format(precision=2), width='stretch')