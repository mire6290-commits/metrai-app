import streamlit as st
import requests
import time
import pandas as pd
import io
import sys
import os
import threading
import socket

sys.path.insert(0, os.path.abspath('backend'))

def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def run_uvicorn():
    import uvicorn
    from backend import main
    uvicorn.run(main.app, host="127.0.0.1", port=8000, log_level="error")

def start_backend():
    if not is_port_in_use(8000):
        print("Starting FastAPI backend in a background thread...")
        t = threading.Thread(target=run_uvicorn, daemon=True)
        t.start()
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

if 'extraction_result' not in st.session_state:
    st.session_state.extraction_result = None
if 'is_extracting' not in st.session_state:
    st.session_state.is_extracting = False

def reset_state():
    st.session_state.extraction_result = None
    st.session_state.is_extracting = False

if uploaded_file is not None:
    if st.session_state.extraction_result is None:
        if st.button("🚀 Start Extraction", type="primary", disabled=st.session_state.is_extracting):
            st.session_state.is_extracting = True
            
            # Afficher l'animation Wireframe
            import sys
            import os
            sys.path.append(os.path.join(os.path.dirname(__file__), "utils"))
            from ui_components import get_wireframe_animation_html
            import streamlit.components.v1 as components
            
            anim_placeholder = st.empty()
            with anim_placeholder:
                components.html(get_wireframe_animation_html(), height=450)
            
            with st.spinner("Analyzing PDF with Agentic Zoning (this may take a few minutes for maximum precision)..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
                data = {
                    "project": project_name,
                    "scale_hint": scale_hint,
                    "pages": pages,
                    "mode": mode
                }
                
                try:
                    response = requests.post("http://127.0.0.1:8000/extract", files=files, data=data, timeout=600)
                    
                    if response.status_code == 200:
                        st.session_state.extraction_result = response.json()
                        st.session_state.is_extracting = False
                        st.rerun()
                    else:
                        st.error(f"Error {response.status_code}: {response.text}")
                        st.session_state.is_extracting = False
                except Exception as e:
                    st.error(f"Connection Error: Is the Backend running? Details: {str(e)}")
                    st.session_state.is_extracting = False

    if st.session_state.extraction_result is not None:
        result = st.session_state.extraction_result
        st.success(f"✅ Extraction Complete! Analyzed {result['pages_processed']} pages.")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Weight", f"{result['total_weight_kg']} kg")
        col2.metric("Profiles Found", len(result['profiles']))
        col3.metric("Detected Scale", result.get('scale_detected', 'Unknown'))
        col4.metric("Provider", result.get('provider_used', 'N/A'))
        
        if result.get('warnings'):
            with st.expander("⚠️ Warnings"):
                for w in result['warnings']:
                    st.warning(w)
        
        st.markdown("### 📋 Informations du Projet (Cartouche)")
        meta = result.get('metadata') or {}
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            meta_entreprise = st.text_input("Entreprise / Bureau d'étude", value=meta.get("entreprise") or "")
            meta_projet = st.text_input("Projet / Affaire", value=meta.get("projet") or project_name)
        with col_m2:
            meta_dessinateur = st.text_input("Dessinateur", value=meta.get("dessinateur") or "")
            meta_date = st.text_input("Date du Plan", value=meta.get("date_plan") or "")
        with col_m3:
            meta_indice = st.text_input("Indice", value=meta.get("indice") or "A")
            
        edited_metadata = {
            "entreprise": meta_entreprise,
            "projet": meta_projet,
            "dessinateur": meta_dessinateur,
            "date_plan": meta_date,
            "indice": meta_indice
        }
        
        if result['profiles']:
            df = pd.DataFrame(result['profiles'])
            
            st.markdown("### 📝 Vérification et Complétion (Human-in-the-loop)")
            st.info("💡 **Instructions** : Les longueurs vides ou suspectes s'affichent avec une icône 📏. Double-cliquez sur une case pour la modifier. Les poids seront recalculés automatiquement à l'export.")
            
            # Columns configuration for st.data_editor
            column_config = {
                "designation": st.column_config.TextColumn("Profil (Désignation)", disabled=True),
                "length_m": st.column_config.NumberColumn("📏 Longueur (m) [À VÉRIFIER]", help="Complétez les longueurs manquantes", min_value=0.0, format="%.3f"),
                "quantity": st.column_config.NumberColumn("🔢 Quantité", min_value=1, step=1),
                "poids_total_kg": st.column_config.NumberColumn("⚖️ Poids Total (Kg)", disabled=True, format="%.2f"),
                "zone": st.column_config.TextColumn("Zone", disabled=True),
                "confidence": st.column_config.ProgressColumn("Confiance IA", min_value=0.0, max_value=1.0, format="%.2f"),
                "role": st.column_config.TextColumn("Nomenclature", disabled=False),
                "masse_lineaire_kg_m": None, # Hide
                "poids_unitaire": None # Hide
            }
            
            cols = ['role', 'designation', 'length_m', 'quantity', 'poids_total_kg', 'zone', 'confidence', 'masse_lineaire_kg_m', 'poids_unitaire']
            df_display = df[[c for c in cols if c in df.columns]]
            
            # Show editable dataframe
            edited_df = st.data_editor(
                df_display,
                column_config=column_config,
                use_container_width=True,
                num_rows="dynamic",
                key="editor"
            )
            
            # Recalculate weights locally based on edited lengths/quantities
            def recalc_row(row):
                qty = row.get('quantity', 1)
                l_m = row.get('length_m', 0.0)
                if pd.isna(l_m): l_m = 0.0
                if pd.isna(qty): qty = 1
                
                # Use pre-calculated static unit weight if present (for plates with 3 dims)
                p_unt = row.get('poids_unitaire')
                if pd.isna(p_unt) or p_unt is None:
                    # Otherwise use masse_lineaire * length
                    m_lin = row.get('masse_lineaire_kg_m', 0.0)
                    if pd.isna(m_lin): m_lin = 0.0
                    p_unt = m_lin * l_m
                    
                ptot = p_unt * qty
                return round(ptot, 2)
                
            edited_df['poids_total_kg'] = edited_df.apply(recalc_row, axis=1)
            
            st.markdown("### 📊 Récapitulatif Net")
            tot_brut = edited_df['poids_total_kg'].sum()
            
            has_bolts = edited_df['designation'].str.upper().str.contains('BOULON').any() or ('role' in edited_df.columns and edited_df['role'].str.upper().str.contains('BOULON').any())
            pourcentage = 0.02 if has_bolts else 0.05
            boul_label = "SOUDAGE (2%)" if has_bolts else "BOULONNERIE + SOUDAGE (5%)"
            boul_val = round(tot_brut * pourcentage, 3)
            tot_net = round(tot_brut + boul_val, 3)
            
            colA, colB, colC = st.columns(3)
            colA.metric("Poids Brut Recalculé", f"{round(tot_brut, 2)} kg")
            colB.metric(boul_label, f"{boul_val} kg")
            colC.metric("Poids Tot Net en Kg", f"{tot_net} kg")
            st.divider()
            
            col_dl, col_reset = st.columns([1, 1])
            
            with col_dl:
                # Prepare data for export
                export_data = edited_df.copy()
                
                import json
                export_json_str = export_data.to_json(orient='records')
                export_list = json.loads(export_json_str)
                
                excel_response = requests.post("http://127.0.0.1:8000/export/excel", json={"data": export_list, "project_name": project_name})
                excel_adv_response = requests.post("http://127.0.0.1:8000/export/excel/advanced", json={"data": export_list, "project_name": meta_projet, "metadata": edited_metadata})
                
                col_btn1, col_btn2 = st.columns(2)
                
                with col_btn1:
                    if excel_response.status_code == 200:
                        st.download_button(
                            label="📥 Télécharger Excel (Standard)",
                            data=excel_response.content,
                            file_name=f"Metre_{project_name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                with col_btn2:
                    if excel_adv_response.status_code == 200:
                        st.download_button(
                            label="📊 Télécharger Excel (Avancé & Synthèse)",
                            data=excel_adv_response.content,
                            file_name=f"Metre_Avance_{project_name}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )
            
            with col_reset:
                st.button("🔄 Analyser un autre plan", on_click=reset_state)
