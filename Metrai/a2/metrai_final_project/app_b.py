import streamlit as st
import fitz  # PyMuPDF
import json
import pandas as pd
from PIL import Image
import io
import time
import base64
import requests

# --- 1. CONFIGURATION MISTRAL API ---
API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"

# --- 2. STYLE L-INTERFACE (MODERN PRO) ---
st.set_page_config(page_title="Metrai Structure Steel", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stProgress > div > div > div > div { background-color: #f26522; }
    
    .big-number { 
        font-size: 80px; 
        font-weight: 900; 
        color: #f26522; 
        text-align: center; 
        margin: 0;
        line-height: 1;
    }
    .metric-label {
        font-size: 20px;
        text-align: center;
        color: #5f6368;
        margin-bottom: 20px;
    }
    
    .stDownloadButton > button {
        width: 100%;
        background-color: #1e1e1e;
        color: white;
        border-radius: 8px;
        height: 50px;
        font-weight: bold;
        border: none;
    }
    .stDownloadButton > button:hover {
        background-color: #333333;
        border: 1px solid #f26522;
    }
    
    .total-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 15px;
        border-left: 5px solid #f26522;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: center;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. DATABASE PROFILÉS (EXTENDED) ---
STEEL_DB = {
    # IPE
    "IPE 80": 6.0, "IPE 100": 8.1, "IPE 120": 10.4, "IPE 140": 12.9, "IPE 160": 15.8,
    "IPE 180": 18.8, "IPE 200": 22.4, "IPE 220": 26.2, "IPE 240": 30.7, "IPE 270": 36.1,
    "IPE 300": 42.2, "IPE 330": 49.1, "IPE 360": 57.1, "IPE 400": 66.3, "IPE 450": 77.6,
    # HEA
    "HEA 100": 16.7, "HEA 120": 19.9, "HEA 140": 24.7, "HEA 160": 30.4, "HEA 180": 35.5,
    "HEA 200": 42.3, "HEA 220": 50.5, "HEA 240": 60.3, "HEA 260": 68.2, "HEA 280": 76.4,
    "HEA 300": 88.3, "HEA 320": 97.6, "HEA 340": 105.0, "HEA 360": 112.0,
    # HEB
    "HEB 100": 20.4, "HEB 120": 26.7, "HEB 140": 33.7, "HEB 160": 42.6, "HEB 180": 51.2,
    "HEB 200": 61.3, "HEB 220": 71.5, "HEB 240": 83.2, "HEB 260": 93.0, "HEB 280": 103.0,
    "HEB 300": 117.0,
    # UPN
    "UPN 80": 8.6, "UPN 100": 10.6, "UPN 120": 13.4, "UPN 140": 16.0, "UPN 160": 18.8
}

def encode_image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# --- 4. UI LAYOUT ---
st.title("🏗️ Metrai Structure AI (Pro)")
st.write("Analyse exhaustive et calcul de métré automatique.")

uploaded_file = st.file_uploader("", type="pdf")

if uploaded_file:
    # Conteneurs pour les animations
    status_placeholder = st.empty()
    progress_bar = st.progress(0)
    count_placeholder = st.empty()

    # 4.1 Process PDF
    doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    progress_bar.progress(10)
    
    # Render page 1 at high resolution
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(4, 4))
    img = Image.open(io.BytesIO(pix.tobytes("png")))
    base64_image = encode_image_to_base64(img)
    progress_bar.progress(30)

    with status_placeholder:
        st.info("🔍 Extraction des données en cours avec Pixtral-Vision...")

    # 4.2 AI Prompt
    prompt_text = """EXPERT STRUCTURAL ANALYSIS:
    Analyze this engineering drawing and extract EVERY single steel member.
    Required format: Return ONLY a valid JSON object:
    {"members": [{"profile": "IPE 270", "quantity": 10, "length_m": 6.5, "type": "Beam", "location": "Grid A-1"}]}
    
    Rules:
    1. Be exhaustive: find every beam, column, and rafter.
    2. Exact profiles: IPE, HEA, HEB, UPN.
    3. Return ONLY the JSON."""

    payload = {
        "model": "pixtral-12b-2409",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt_text},
                    {"type": "image_url", "image_url": f"data:image/png;base64,{base64_image}"}
                ]
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0
    }

    try:
        response = requests.post(MISTRAL_URL, headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}, json=payload)
        
        if response.status_code == 200:
            res_json = response.json()
            members_raw = json.loads(res_json['choices'][0]['message']['content']).get('members', [])
            
            # Animation du compteur
            for i in range(len(members_raw) + 1):
                count_placeholder.markdown(f'<div class="big-number">{i}</div><div class="metric-label">Éléments détectés</div>', unsafe_allow_html=True)
                time.sleep(0.04)

            progress_bar.progress(100)
            status_placeholder.empty()

            if members_raw:
                df = pd.DataFrame(members_raw)
                
                # NETTOYAGE DES DONNEES (Correction de l'erreur .strip())
                df['profile'] = df['profile'].astype(str).str.upper().str.strip()
                
                # CALCULS
                df['Unit Weight (kg/m)'] = df['profile'].map(STEEL_DB).fillna(0)
                df['Total Weight (kg)'] = df['Unit Weight (kg/m)'] * df['length_m'] * df['quantity']
                
                # TOTALS
                total_kg = df['Total Weight (kg)'].sum()
                total_tonnes = total_kg / 1000
                total_qty = df['quantity'].sum()

                # Dashboard Recap
                st.write("---")
                m_col1, m_col2, m_col3 = st.columns(3)
                with m_col1:
                    st.markdown(f'<div class="total-card"><h3>Quantité Totale</h3><h2 style="color:#f26522;">{int(total_qty)}</h2><p>Profilés</p></div>', unsafe_allow_html=True)
                with m_col2:
                    st.markdown(f'<div class="total-card"><h3>Poids Total</h3><h2 style="color:#f26522;">{total_tonnes:.3f}</h2><p>Tonnes</p></div>', unsafe_allow_html=True)
                with m_col3:
                    st.markdown(f'<div class="total-card"><h3>Poids en KG</h3><h2 style="color:#f26522;">{total_kg:.1f}</h2><p>Kilogrammes</p></div>', unsafe_allow_html=True)

                st.write("### 📋 Détail du Métré Technique")
                # Affichage stylisé du tableau
                st.dataframe(df, use_container_width=True)

                # Export Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Metrai_Steel_Report')
                
                st.write("---")
                st.download_button(
                    label="📥 Télécharger le Métré Professionnel (Excel .xlsx)",
                    data=output.getvalue(),
                    file_name=f"Metrai_Pro_{uploaded_file.name.split('.')[0]}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("Aucun élément détecté.")
        else:
            st.error(f"Erreur API: {response.status_code}")

    except Exception as e:
        st.error(f"Erreur d'exécution: {str(e)}")
else:
    st.info("Uploadez votre plan de structure pour générer le métré détaillé.")