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

# --- 1. CONFIGURATION & SECRETS ---
API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
MISTRAL_URL = "[https://api.mistral.ai/v1/chat/completions](https://api.mistral.ai/v1/chat/completions)"

if 'step' not in st.session_state:
    st.session_state.step = 'upload'
if 'results' not in st.session_state:
    st.session_state.results = None

# --- 2. PREMIUM UI CSS (Matched to image_cb059f.png) ---
st.set_page_config(page_title="Metrai AI - Mistral Steel Takeoff", layout="wide")

st.markdown("""
    <style>
    @import url('[https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Inter:wght@300;400;700&display=swap](https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Inter:wght@300;400;700&display=swap)');
    
    body, .main, .stApp {
        background-color: #0e1117;
        color: white;
        font-family: 'Inter', sans-serif;
    }
    
    /* Header Style */
    .header-container {
        display: flex;
        align-items: center;
        gap: 15px;
        padding-top: 20px;
    }
    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 38px;
        font-weight: 900;
        color: white;
    }
    .sub-text {
        color: #94a3b8;
        font-size: 16px;
        margin-bottom: 40px;
        margin-top: -10px;
    }
    
    /* Status Box (Green) */
    .status-box {
        background-color: rgba(21, 128, 61, 0.2);
        border: 1px solid #15803d;
        padding: 12px 20px;
        border-radius: 6px;
        color: #4ade80;
        margin: 20px 0;
        font-weight: 500;
    }
    
    /* Table Styling */
    .stDataFrame {
        border: 1px solid #334155;
        border-radius: 8px;
    }
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(90deg, #f26522, #ff8c52);
        color: white;
        border-radius: 6px;
        font-weight: 700;
        border: none;
        padding: 10px 25px;
        transition: 0.3s;
    }
    .stButton > button:hover {
        opacity: 0.9;
        transform: translateY(-1px);
    }
    
    /* File Uploader Customization */
    [data-testid="stFileUploader"] {
        background-color: #1e293b;
        border: 1px dashed #475569;
        border-radius: 10px;
        padding: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE & LOGIC ---
STEEL_DB = {
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 220": 26.2, "IPE 240": 30.7, "IPE 270": 36.1,
    "IPE 300": 42.2, "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4,
    "HEA 180": 35.5, "HEA 200": 42.3, "HEA 220": 50.5, "HEB 160": 42.6, "HEB 200": 61.3
}

def call_pixtral_api(base64_image):
    prompt = "EXPERT STRUCTURAL ANALYSIS: Extract all steel members into JSON: {'members': [{'profile': 'IPE 270', 'quantity': 10, 'length_m': 3, 'type': 'Beam', 'location': 'Main Grid'}]}"
    payload = {
        "model": "pixtral-12b-2409",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0
    }
    try:
        response = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, json=payload, timeout=60)
        return response.json()['choices'][0]['message']['content']
    except:
        return None

# --- 4. APP INTERFACE ---
st.markdown('<div class="header-container"><span style="font-size:40px;">🏗️</span><span class="main-title">Mistral Steel Takeoff</span></div>', unsafe_allow_html=True)
st.markdown('<p class="sub-text">Detection of European Steel Members (IPE, HEA, HEB) powered by Pixtral Vision.</p>', unsafe_allow_html=True)

if st.session_state.step == 'upload':
    up_file = st.file_uploader("", type="pdf")
    if up_file:
        if st.button("🚀 ANALYZE PLAN"):
            with st.status("Reading drawing and contacting Pixtral...", expanded=True) as status:
                doc = fitz.open(stream=up_file.read(), filetype="pdf")
                pix = doc[0].get_pixmap(matrix=fitz.Matrix(3, 3))
                img_bytes = pix.tobytes("png")
                b64_img = base64.b64encode(img_bytes).decode('utf-8')
                doc.close()
                
                res_text = call_pixtral_api(b64_img)
                if res_text:
                    data = json.loads(res_text)
                    st.session_state.results = data.get('members', [])
                    st.session_state.plan_name = up_file.name
                    st.session_state.step = 'results'
                    st.rerun()
                else:
                    st.error("API Connection Error. Please try again.")

elif st.session_state.step == 'results':
    st.markdown(f'<div class="status-box">Analysis Complete: {len(st.session_state.results)} steel profiles identified.</div>', unsafe_allow_html=True)
    
    st.markdown('### 📋 Structural Takeoff Report (Mistral AI)')
    df = pd.DataFrame(st.session_state.results)
    
    # Matching logic for weights
    df['profile'] = df['profile'].str.upper()
    df['Unit Weight (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
    df['Total Weight (kg)'] = df['Unit Weight (kg/m)'] * df['length_m'] * df['quantity']
    
    st.dataframe(df, use_container_width=True)
    
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 ANALYZE ANOTHER"):
            st.session_state.step = 'upload'
            st.rerun()
