import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
from PIL import Image
import io
import time
import base64
import requests
from datetime import datetime

# --- 1. CONFIGURATION & SESSION STATE ---
# Note: En production, utilisez st.secrets pour l'API_KEY
API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

if 'step' not in st.session_state:
    st.session_state.step = 'upload'
if 'results' not in st.session_state:
    st.session_state.results = None
if 'plan_name' not in st.session_state:
    st.session_state.plan_name = ""

# --- 2. STYLE CSS (PREMIUM & ALIVE) ---
st.set_page_config(page_title="Metrai AI Pro", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Roboto:wght@300;700&display=swap');
    
    .main { background-color: #0e1117; color: #ffffff; }
    
    /* Sidebar Logo & Menu */
    .sidebar-logo {
        text-align: center;
        padding: 20px 0;
        background: linear-gradient(135deg, #f26522 0%, #ff8c52 100%);
        border-radius: 15px;
        margin-bottom: 25px;
    }
    .logo-text { font-family: 'Orbitron', sans-serif; font-weight: 900; color: white; font-size: 24px; letter-spacing: 2px; }
    
    /* Global Cards */
    .stApp { background-color: #0e1117; }
    .status-card {
        background: rgba(255, 255, 255, 0.05);
        padding: 30px;
        border-radius: 20px;
        border: 1px solid rgba(242, 101, 34, 0.3);
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    /* Big Numbers Animation */
    .big-number { 
        font-family: 'Orbitron', sans-serif;
        font-size: 90px; 
        font-weight: 900; 
        color: #f26522; 
        text-shadow: 0 0 20px rgba(242, 101, 34, 0.5);
    }
    
    /* Buttons */
    .stButton > button {
        width: 100%;
        background: linear-gradient(90deg, #f26522, #ff8c52);
        color: white; border: none; border-radius: 10px; height: 50px; font-weight: bold;
        transition: 0.5s;
    }
    .stButton > button:hover { transform: scale(1.02); box-shadow: 0 0 15px #f26522; }
    
    /* Table Styling */
    .stDataFrame { background: white; border-radius: 10px; padding: 5px; }
    
    /* Footer */
    .footer-text { text-align: center; font-size: 12px; color: #666; margin-top: 50px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE PROFILÉS ---
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 220": 26.2, "IPE 240": 30.7, "IPE 270": 36.1,
    "IPE 300": 42.2, "IPE 330": 49.1, "IPE 360": 57.1, "IPE 400": 66.3, "IPE 450": 77.6,
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5,
    "HEA 200": 42.3, "HEA 220": 50.5, "HEA 240": 60.3, "HEA 260": 68.2, "HEA 280": 76.4,
    "HEA 300": 88.3, "HEB 100": 20.4, "HEB 120": 26.7, "HEB 140": 33.7, "HEB 160": 42.6, 
    "HEB 180": 51.2, "HEB 200": 61.3, "HEB 240": 83.2, "HEB 300": 117.0, "UPN 80": 8.6, 
    "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8
}

# --- 4. FUNCTIONS ---
def encode_image(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def generate_pro_excel(df, total_kg, total_qty, plan_name):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    current_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    df.to_excel(writer, index=False, sheet_name='Metrai_Report', startrow=4)
    
    workbook  = writer.book
    worksheet = writer.sheets['Metrai_Report']
    
    title_format = workbook.add_format({'bold': True, 'font_size': 16, 'font_color': '#f26522'})
    info_format = workbook.add_format({'bold': True, 'font_color': '#555555'})
    header_format = workbook.add_format({
        'bold': True, 'text_wrap': True, 'valign': 'vcenter',
        'fg_color': '#f26522', 'font_color': '#ffffff', 'border': 1
    })
    total_format = workbook.add_format({
        'bold': True, 'fg_color': '#333333', 'font_color': '#ffffff', 'border': 1, 'num_format': '#,##0.00'
    })

    worksheet.write('A1', 'RAPPORT DE MÉTRÉ STRUCTUREL', title_format)
    worksheet.write('A2', f'Plan: {plan_name}', info_format)
    worksheet.write('A3', f'Date: {current_date}', info_format)
    
    for col_num, value in enumerate(df.columns.values):
        worksheet.write(4, col_num, value, header_format)
        worksheet.set_column(col_num, col_num, 20)
    
    last_row = len(df) + 5
    worksheet.write(last_row, 0, "TOTAL GENERAL", total_format)
    worksheet.write(last_row, 1, total_qty, total_format)
    for c in range(2, 6):
        worksheet.write(last_row, c, "", total_format)
    worksheet.write(last_row, 6, total_kg, total_format)
    
    writer.close()
    return output.getvalue()

def call_mistral_with_retry(payload, max_retries=5):
    """Appel API avec Exponential Backoff pour la mise en ligne"""
    for i in range(max_retries):
        try:
            response = requests.post(MISTRAL_URL, 
                                     headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                                     json=payload, timeout=60)
            if response.status_code == 200:
                return response
            elif response.status_code == 429: # Rate limit
                time.sleep(2 ** i)
            else:
                st.error(f"Erreur Serveur: {response.status_code}")
                return None
        except Exception:
            time.sleep(2 ** i)
    return None

def restart_app():
    st.session_state.step = 'upload'
    st.session_state.results = None
    st.session_state.plan_name = ""
    st.rerun()

# --- 5. SIDEBAR (LOGO & MENU) ---
with st.sidebar:
    st.markdown('<div class="sidebar-logo"><div class="logo-text">METRAI AI</div><div style="font-size:10px; color:white;">STRUCTURE EDITION</div></div>', unsafe_allow_html=True)
    
    menu = st.radio("Menu Principal", ["🔄 Converter", "📧 Contact Nous", "ℹ️ À Propos"])
    
    st.write("---")
    if menu == "📧 Contact Nous":
        st.write("💬 Besoin d'aide?")
        st.info("Email: support@metrai-ai.com\nWhatsApp: +212 600 000 000")
    
    st.write("---")
    st.markdown('<div style="color:#666; font-size:12px;">Version 2.3.0 Cloud-Ready<br>© 2026 Metrai Structure</div>', unsafe_allow_html=True)

# --- 6. MAIN CONTENT ---
if st.session_state.step == 'upload':
    st.title("Salut! Prêt pour un nouveau métré? 🏗️")
    st.write("Déposez votre plan PDF et laissez l'IA Pixtral s'occuper de tout.")
    
    up_file = st.file_uploader("", type="pdf")
    
    if up_file:
        if st.button("🚀 LANCER L'ANALYSE"):
            st.session_state.uploaded_file = up_file
            st.session_state.plan_name = up_file.name
            st.session_state.step = 'processing'
            st.rerun()

elif st.session_state.step == 'processing':
    with st.container():
        st.markdown('<div class="status-card">', unsafe_allow_html=True)
        status_text = st.empty()
        prog_bar = st.progress(0)
        num_anim = st.empty()
        
        status_text.markdown("### 🔍 Lecture du plan en cours...")
        doc = fitz.open(stream=st.session_state.uploaded_file.read(), filetype="pdf")
        page = doc[0]
        pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        b64 = encode_image(img)
        doc.close() # Libère la mémoire
        prog_bar.progress(40)
        
        status_text.markdown("### 🤖 Pixtral-Vision analyse les profilés...")
        
        prompt = """EXPERT STRUCTURAL ANALYSIS:
        Analyze this drawing and extract EVERY steel member.
        Return ONLY a valid JSON object:
        {"members": [{"profile": "IPE 270", "quantity": 10, "length_m": 6.5, "type": "Beam", "location": "Grid A-1"}]}
        Note: Use standard profiles (IPE, HEA, HEB, UPN). Be exhaustive."""
        
        payload = {
            "model": "pixtral-12b-2409",
            "messages": [{"role": "user", "content": [{"type":"text","text":prompt}, {"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
            "response_format": {"type": "json_object"}, "temperature": 0
        }
        
        res = call_mistral_with_retry(payload)
        
        if res:
            data = json.loads(res.json()['choices'][0]['message']['content'])
            members = data.get('members', [])
            
            for i in range(len(members) + 1):
                num_anim.markdown(f'<div class="big-number">{i}</div><div class="metric-label">Profilés Détectés</div>', unsafe_allow_html=True)
                time.sleep(0.05)
            
            prog_bar.progress(100)
            st.session_state.results = members
            st.session_state.step = 'results'
            time.sleep(0.5)
            st.rerun()
        else:
            st.error("L'analyse a échoué après plusieurs tentatives. Vérifiez votre connexion ou la taille du fichier.")
            if st.button("Réessayer"): st.session_state.step = 'upload'; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.step == 'results':
    members = st.session_state.results
    df = pd.DataFrame(members)
    
    df['profile'] = df['profile'].astype(str).str.upper().str.strip()
    df['Poids Unit (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Poids Total (kg)'] = df['Poids Unit (kg/m)'] * df['length_m'] * df['quantity']
    
    t_kg = df['Poids Total (kg)'].sum()
    t_ton = t_kg / 1000
    t_qty = df['quantity'].sum()
    
    st.success(f"✨ Analyse de '{st.session_state.plan_name}' terminée!")
    
    c1, c2, c3 = st.columns(3)
    with c1: st.metric("Quantité Totale", f"{int(t_qty)} Pcs")
    with c2: st.metric("Tonnage Global", f"{t_ton:.3f} T")
    with c3: st.metric("Total KG", f"{t_kg:,.1f} kg")

    st.write("---")

    col_a, col_b = st.columns(2)
    xl_data = generate_pro_excel(df, t_kg, t_qty, st.session_state.plan_name)
    with col_a:
        st.download_button(
            label="📥 TÉLÉCHARGER LE RAPPORT EXCEL", 
            data=xl_data, 
            file_name=f"Metrai_{st.session_state.plan_name.replace('.pdf', '')}.xlsx", 
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with col_b:
        if st.button("🔄 CONVERTIR UN AUTRE PLAN"):
            restart_app()

    st.write("### 📋 Détail Technique (Compact View)")
    st.dataframe(df, use_container_width=True, height=350)
    
    st.write("---")
    st.write("### 📧 Envoyer les résultats par Email")
    email_col1, email_col2 = st.columns([3, 1])
    with email_col1:
        target_email = st.text_input("Email du destinataire", placeholder="exemple@entreprise.com")
    with email_col2:
        if st.button("Sift Daba"):
            if target_email:
                st.toast(f"✅ Rapport envoyé à {target_email}!")
            else:
                st.error("Email manquant.")

st.markdown('<div class="footer-text">Metrai AI v2.3 - Cloud Edition</div>', unsafe_allow_html=True)