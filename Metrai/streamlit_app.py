import streamlit as st
import requests
import pandas as pd
import io

st.set_page_config(page_title="Metrai AI - Charpente", page_icon="🏗️", layout="wide")

API_URL = "https://amira221-metrai-backend.hf.space"

st.title("🏗️ Metrai AI - Métré Charpente Métallique")
st.markdown("Uploadez votre plan PDF pour générer automatiquement la nomenclature complète.")

uploaded_file = st.file_uploader("Choisissez un plan PDF", type="pdf")

if uploaded_file is not None:
    if st.button("Lancer l'analyse AI 🚀"):
        with st.spinner("Analyse du plan en cours par l'IA... (Ceci peut prendre 30 à 60 secondes)"):
            try:
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                # CHANGED: Use /extract instead of /upload
                response = requests.post(f"{API_URL}/extract", files=files, timeout=120)
                
                if response.status_code == 200:
                    data = response.json()
                    st.success("Analyse terminée avec succès !")
                    
                    profiles = data.get("profiles", [])
                    if profiles:
                        # Convert to DataFrame for display
                        df = pd.DataFrame(profiles)
                        
                        st.subheader("Résultats de l'extraction")
                        st.dataframe(df, use_container_width=True)
                        
                        st.subheader("Exporter les résultats")
                        
                        # Excel Export
                        export_res = requests.post(f"{API_URL}/export/excel", json={"data": profiles})
                        if export_res.status_code == 200:
                            st.download_button(
                                label="📥 Télécharger l'Excel (Format Expert)",
                                data=export_res.content,
                                file_name="metrai_expert_export.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                        else:
                            st.error("Erreur lors de la génération de l'Excel.")
                    else:
                        st.warning("Aucun profil n'a été trouvé dans ce plan.")
                else:
                    st.error(f"Erreur du serveur: {response.text}")
            except Exception as e:
                st.error(f"Une erreur est survenue: {str(e)}")
