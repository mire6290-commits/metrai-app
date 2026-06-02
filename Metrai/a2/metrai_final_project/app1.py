from flask import Flask, render_template, request, send_file
import pdfplumber
import pandas as pd
import io
import os
import re

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Base de données complète des poids pour tous les types de profilés
POIDS_REFERENTIAL = {
    'IPE500': 90.7, 'IPE450': 77.6, 'IPE400': 66.3, 'IPE360': 57.1, 'IPE330': 49.1, 'IPE300': 42.2, 
    'IPE270': 36.1, 'IPE240': 30.7, 'IPE220': 26.2, 'IPE200': 22.4, 'IPE180': 18.8, 'IPE160': 15.8,
    'HEB600': 212, 'HEB550': 199, 'HEB500': 187, 'HEB450': 171, 'HEB400': 155, 'HEB300': 117,
    'HEA120': 19.9, 'HEA140': 24.7, 'HEA160': 30.4, 'HEA180': 35.5, 'HEA200': 42.3,
    'UPN140': 16.0, 'UPN160': 18.8, 'UPN200': 25.3, 'L70x7': 7.38, 'L80x8': 9.66, 'L100x10': 15.0
}

def extract_all_structural_data(pdf_path):
    extracted_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    # Nettoyage de la ligne
                    clean_row = [str(c).strip().upper() for c in row if c is not None and str(c).strip() != ""]
                    if len(clean_row) < 2: continue

                    row_text = "".join(clean_row).replace(" ", "")
                    
                    # Identification de la désignation et du poids unitaire
                    found_desig = "Non identifié"
                    p_m = 0
                    for key in POIDS_REFERENTIAL:
                        if key in row_text:
                            found_desig = key
                            p_m = POIDS_REFERENTIAL[key]
                            break
                    
                    # Extraction des valeurs numériques pour Quantité et Longueur
                    nums = []
                    for item in clean_row:
                        val = item.replace(",", ".").replace(" ", "")
                        match = re.search(r"(\d+(\.\d+)?)", val)
                        if match:
                            nums.append(float(match.group(1)))
                    
                    if len(nums) >= 2 and p_m > 0:
                        # Logique : La plus grande valeur est la longueur (en mm), la plus petite est la quantité
                        qty = min(nums)
                        long_mm = max(nums)
                        
                        # Correction si la longueur est en mètres
                        if long_mm < 100: long_mm *= 1000 
                        
                        p_unt = (long_mm / 1000) * p_m
                        p_tot = p_unt * qty

                        extracted_data.append({
                            'Élément': 'Structure',
                            'Désignation': found_desig,
                            'Quantité': int(qty),
                            'Longueur (mm)': long_mm,
                            'Poids (Kg/m)': p_m,
                            'Poids Unit (Kg)': round(p_unt, 2),
                            'Poids Total (Kg)': round(p_tot, 2)
                        })
    return pd.DataFrame(extracted_data)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files: return "Aucun fichier"
    file = request.files['file']
    if file.filename == '': return "Fichier vide"
    
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    try:
        df = extract_all_structural_data(path)
        if df.empty: return "Aucune donnée de structure détectée dans ce PDF."

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Metrai Global')
            workbook = writer.book
            worksheet = writer.sheets['Metrai Global']
            
            # Styles Excel
            header_fmt = workbook.add_format({'bold': True, 'bg_color': '#00d2ff', 'border': 1, 'font_color': 'white', 'align': 'center'})
            cell_fmt = workbook.add_format({'border': 1, 'align': 'center'})
            total_fmt = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'border': 1, 'align': 'center'})

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column(col_num, col_num, 15)
            
            for r in range(len(df)):
                for c in range(len(df.columns)):
                    worksheet.write(r+1, c, df.iloc[r, c], cell_fmt)

            last_row = len(df) + 1
            worksheet.merge_range(last_row, 0, last_row, 5, "TOTAL GÉNÉRAL STRUCTURE (Kg)", header_fmt)
            worksheet.write(last_row, 6, df['Poids Total (Kg)'].sum(), total_fmt)

        output.seek(0)
        os.remove(path)
        return send_file(output, as_attachment=True, download_name="Metrai_Structure_Complet.xlsx")
    except Exception as e:
        return f"Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(debug=False)
