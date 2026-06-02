import streamlit as st
import pandas as pd

st.set_page_config(page_title="Metrai AI Dashboard", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: white; }
    .title-text { color: #f26522; font-family: 'Orbitron', sans-serif; font-size: 30px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.markdown('<div class="title-text">🏗️ METRAI AI SYSTEM</div>', unsafe_allow_html=True)

up_file = st.file_uploader("Upload Drawing (PDF)", type="pdf")

if up_file:
    if st.button("🚀 ANALYZE"):
        st.success("Analysis complete!")
        data = {"Profile": ["IPE 270", "HEA 200"], "Quantity": [10, 5], "Length (m)": [6.0, 4.5]}
        st.table(pd.DataFrame(data))
