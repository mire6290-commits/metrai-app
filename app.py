import streamlit as st
import requests
import time
import pandas as pd
import io
import subprocess
import socket
import threading

import sys

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

def start_backend():
    if not is_port_in_use(8000):
        print("Starting FastAPI backend...")
        subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"])
        time.sleep(3) # Wait for startup

# Start backend if not running
start_backend()

st.set_page_config(page_title="Métré Automatisé 🏗️", layout="wide", page_icon="🏗️")

st.title("🏗️ Métré Automatisé - Charpente Métallique")
st.markdown("Extract structural steel profiles from your drawings with 100% precision using Agentic Zoning.")

# Sidebar Configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    project_name = st.text_input("Project Name", value="Mon Projet")
    scale_hint = st.text_input("Scale Hint (Optional)", value="1:50")
    pages = st.text_input("Pages to Analyze", value="all", help="'all' or '1,2,3'")
    mode = st.selectbox("Extraction Mode", ["vision", "text", "hybrid"])
    
uploaded_file = st.file_uploader("Upload Structural PDF Drawing 📄", type=['pdf'])

if uploaded_file is not None:
    if st.button("🚀 Start Extraction", type="primary"):
        with st.spinner("Analyzing PDF with Agentic Zoning (this may take a few minutes for maximum precision)..."):
            # Prepare files and data for FastAPI
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            data = {
                "project": project_name,
                "scale_hint": scale_hint,
                "pages": pages,
                "mode": mode
            }
            
            try:
                # Call local FastAPI backend
                response = requests.post("http://localhost:8000/extract", files=files, data=data, timeout=600)
                
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"✅ Extraction Complete! Analyzed {result['pages_processed']} pages.")
                    
                    # Display Metadata
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Weight", f"{result['total_weight_kg']} kg")
                    col2.metric("Profiles Found", len(result['profiles']))
                    col3.metric("Detected Scale", result.get('scale_detected', 'Unknown'))
                    col4.metric("Provider", result.get('provider_used', 'N/A'))
                    
                    if result.get('warnings'):
                        with st.expander("⚠️ Warnings"):
                            for w in result['warnings']:
                                st.warning(w)
                    
                    # Display Table
                    if result['profiles']:
                        df = pd.DataFrame(result['profiles'])
                        # Reorder columns for better UI
                        cols = ['designation', 'length_m', 'quantity', 'poids_total_kg', 'zone', 'confidence', 'role']
                        df_display = df[[c for c in cols if c in df.columns]]
                        st.dataframe(df_display, use_container_width=True)
                        
                        # Calculate and Display final Net Totals like the Excel file
                        st.markdown("### 📊 Récapitulatif Net")
                        tot_brut = result['total_weight_kg']
                        
                        # SOUDAGE/BOULONNERIE logic (same as Excel export)
                        has_bolts = df_display['designation'].str.upper().str.contains('BOULON').any() or ('role' in df_display.columns and df_display['role'].str.upper().str.contains('BOULON').any())
                        pourcentage = 0.02 if has_bolts else 0.05
                        boul_label = "SOUDAGE (2%)" if has_bolts else "BOULONNERIE + SOUDAGE (5%)"
                        boul_val = round(tot_brut * pourcentage, 3)
                        tot_net = round(tot_brut + boul_val, 3)
                        
                        colA, colB, colC = st.columns(3)
                        colA.metric("Poids Brut", f"{tot_brut} kg")
                        colB.metric(boul_label, f"{boul_val} kg")
                        colC.metric("Poids Tot Net en Kg", f"{tot_net} kg")
                        st.divider()
                        
                        # Export Excel
                        excel_response = requests.post("http://localhost:8000/export/excel", json={"data": result['profiles']})
                        if excel_response.status_code == 200:
                            st.download_button(
                                label="📥 Download Excel File (.xlsx)",
                                data=excel_response.content,
                                file_name=f"Metre_{project_name}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                type="primary"
                            )
                else:
                    st.error(f"Error {response.status_code}: {response.text}")
            except Exception as e:
                st.error(f"Connection Error: Is the Backend running? Details: {str(e)}")
