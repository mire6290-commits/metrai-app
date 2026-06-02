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

if 'step' not in st.session_state:
    st.session_state.step = 'upload'
if 'results' not in st.session_state:
    st.session_state.results = None

# --- 2. STYLE "ULTRA DARK PREMIUM" ---
st.set_page_config(page_title="Metrai AI Ultra", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syncopate:wght@400;700&family=Inter:wght@300;600&display=swap');
    .stApp { background: #050505; color: #e0e0e0; font-family: 'Inter', sans-serif; }
    .premium-card {
        background: #0f0f0f; padding: 40px; border-radius: 30px;
        border: 1px solid #1f1f1f; box-shadow: 0 10px 30px rgba(0,0,0,0.8);
        text-align: center; margin-top: 20px;
    }
    .glitch-title {
        font-family: 'Syncopate', sans-serif; font-size: 45px; font-weight: 700;
        background: linear-gradient(90deg, #ff4b2b, #ff416c);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        letter-spacing: 4px; margin-bottom: 10px;
    }
    .metric-box {
        background: #111111; border-bottom: 3px solid #ff416c;
        padding: 25px; border-radius: 20px; text-align: center;
    }
    .stButton > button {
        background: linear-gradient(45deg, #ff4b2b, #ff416c) !important;
        color: white !important; border: none !important; border-radius: 12px !important;
        padding: 20px !important; font-family: 'Syncopate', sans-serif;
        font-weight: 700 !important; width: 100%; transition: 0.4s all ease;
    }
    .stButton > button:hover { transform: translateY(-3px); box-shadow: 0 5px 20px rgba(255, 75, 43, 0.5); }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE STEEL ---
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

def encode_image(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 4. APP LOGIC ---
if st.session_state.step == 'upload':
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.markdown('<div class="glitch-title">METRAI AI ULTRA</div>', unsafe_allow_html=True)
    up_file = st.file_uploader("", type="pdf", label_visibility="collapsed")
    if up_file and st.button("LANCER L'ANALYSE"):
        st.session_state.file_bytes = up_file.read()
        st.session_state.step = 'processing'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.step == 'processing':
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    status_text = st.empty()
    status_text.markdown("### 🧬 EXTRACTION EN COURS...")
    
    doc = fitz.open(stream=st.session_state.file_bytes, filetype="pdf")
    pix = doc[0].get_pixmap(matrix=fitz.Matrix(2, 2))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    b64 = encode_image(img)
    
    prompt = """Analyze drawing. Extract steel profiles. Output JSON: {"members": [{"profile": "IPE 270", "quantity": 5, "length_m": 6.0}]}"""

    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    try:
        res = requests.post(MISTRAL_URL, headers=headers, json={
            "model": "pixtral-12b-2409",
            "messages": [{"role": "user", "content": [{"type":"text","text":prompt}, {"type":"image_url","image_url":f"data:image/png;base64,{b64}"}]}],
            "response_format": {"type": "json_object"}
        }, timeout=60)
        
        if res.status_code == 200:
            st.session_state.results = json.loads(res.json()['choices'][0]['message']['content']).get('members', [])
            st.session_state.step = 'results'
            st.rerun()
        else:
            st.error(f"Erreur {res.status_code}. Vérifie ta console Mistral.")
            if st.button("Retour"): st.session_state.step = 'upload'; st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

elif st.session_state.step == 'results':
    st.markdown('<h2 style="font-family:Syncopate; color:#ff416c;">RÉSULTATS D\'ANALYSE</h2>', unsafe_allow_html=True)
    
    df = pd.DataFrame(st.session_state.results)
    
    # --- ISLAH L-GHALAT DYAL TYPE ---
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
    df['length_m'] = pd.to_numeric(df['length_m'], errors='coerce').fillna(0)
    df['profile'] = df['profile'].astype(str).str.upper().str.strip()
    df['Poids Unit'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Poids Total (kg)'] = df['Poids Unit'] * df['length_m'] * df['quantity']
    
    m1, m2, m3 = st.columns(3)
    m1.markdown(f'<div class="metric-box">POIDS TOTAL<br><h2>{df["Poids Total (kg)"].sum():,.1f} kg</h2></div>', unsafe_allow_html=True)
    m2.markdown(f'<div class="metric-box">TONNAGE<br><h2>{df["Poids Total (kg)"].sum()/1000:.3f} T</h2></div>', unsafe_allow_html=True)
    m3.markdown(f'<div class="metric-box">ITEMS<br><h2>{int(df["quantity"].sum())}</h2></div>', unsafe_allow_html=True)
    
    st.dataframe(df, use_container_width=True)
    if st.button("NOUVEAU PLAN"):
        st.session_state.step = 'upload'
        st.rerun()