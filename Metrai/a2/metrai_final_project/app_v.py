import os
import io
import re
import pandas as pd
import requests
import pdfplumber
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# --- CONFIGURATION ---
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
MISTRAL_API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"

# قاعدة بيانات الأوزان المستخرجة من ملفك (MÉTRÉ_MODÈLE)
STEEL_DATABASE = {
    'IPE500': 90.7, 'IPE450': 77.6, 'IPE270': 36.1, 'IPE240': 30.7, 
    'HEA120': 19.9, 'IPE120': 10.4, 'IPE140': 12.9, 'UPN200': 25.3,
    'L60*60*6': 5.42, 'D12': 0.888, 'ROND_30': 5.55
}

def get_mistral_pro(text):
    """Extraction avec typage strict pour éviter les erreurs de colonnes"""
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    En tant qu'expert SINERTECH. Extrais le métré avec une précision chirurgicale.
    Pour chaque profilé (POTEAU, POUTRE, etc.), extrais :
    1. Nomenclature (ex: IPE270)
    2. Quantité (ex: 20)
    3. Longueur en mm (ex: 12000)
    
    Format CSV: Pos,Nomenclatures,Quantite,Long
    Règle : Ne mets JAMAIS 0 pour la longueur si elle est présente.
    Texte : {text}
    """
    payload = {"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    
    try:
        response = requests.post(url, json=payload, headers=headers).json()
        csv_raw = response['choices'][0]['message']['content'].strip()
        return csv_raw.split("```")[1].replace("csv", "").strip() if "```" in csv_raw else csv_raw
    except: return "Pos,Nomenclatures,Quantite,Long\n1,Error,0,0"

def generate_ultimate_excel(df):
    """توليد ملف مطابق للموديل الاحترافي 100%"""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # تحضير البيانات والحسابات البرمجية الصارمة
    df['Poids_m'] = df['Nomenclatures'].apply(lambda x: STEEL_DATABASE.get(str(x).replace(" ", ""), 0))
    df['Poids_Unit'] = (df['Long'] / 1000) * df['Poids_m']
    df['Total_Weight'] = df['Poids_Unit'] * df['Quantite']

    df.to_excel(writer, index=False, sheet_name='METRE_SINERTECH', startrow=9)
    
    workbook = writer.book
    worksheet = writer.sheets['METRE_SINERTECH']
    
    # التنسيقات (Branding Pro)
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#0F172A', 'font_color': 'white', 'border': 1, 'align': 'center'})
    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#F59E0B', 'border': 1, 'num_format': '#,##0.00'})

    # الترويسة
    worksheet.write('A2', 'SINERTECH IA - MÉTRÉ DE STRUCTURE', workbook.add_format({'bold': True, 'font_size': 20}))
    worksheet.write('A8', '1- Ossature métallique (Calcul Automatisé) :', workbook.add_format({'bold': True, 'bg_color': '#00FFFF'}))

    # إضافة المجموع النهائي مع نسبة 5% للبراغي كما في ملفك
    total_row = 10 + len(df)
    worksheet.write(total_row, 5, 'POIDS TOTAL NET (Kg):', workbook.add_format({'bold': True}))
    worksheet.write_formula(total_row, 7, f'=SUM(H11:H{total_row})', total_fmt)
    
    worksheet.write(total_row + 1, 5, 'BOULONNERIE + SOUDAGE (5%):', workbook.add_format({'italic': True}))
    worksheet.write_formula(total_row + 1, 7, f'=H{total_row + 1}*0.05', total_fmt)

    writer.close()
    output.seek(0)
    return output

# --- Interface "Lharba" (Design Pro) ---
INDEX_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8"><title>SINERTECH IA | Final</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-900 text-white flex items-center justify-center min-h-screen">
    <div class="bg-slate-800 p-16 rounded-[3rem] shadow-2xl text-center border border-slate-700">
        <h1 class="text-5xl font-black mb-4">SINERTECH <span class="text-amber-500 italic">IA</span></h1>
        <p class="text-slate-400 mb-10 tracking-widest uppercase text-xs font-bold">Métré Structural Certifié</p>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <label class="cursor-pointer group">
                <div class="border-4 border-dashed border-slate-600 p-12 rounded-3xl group-hover:border-amber-500 transition-all">
                    <input type="file" name="file" class="hidden" onchange="this.form.submit()">
                    <span class="text-2xl font-bold block mb-2">UPLOADER LE PLAN PDF</span>
                    <span class="text-slate-500 text-sm">Analyse et calcul automatique selon MÉTRÉ_MODÈLE</span>
                </div>
            </label>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(INDEX_HTML)

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    try:
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages: text += (page.extract_text() or "") + "\n"
        
        csv_data = get_mistral_pro(text)
        df = pd.read_csv(io.StringIO(csv_data), on_bad_lines='skip', sep=None, engine='python')
        
        # تنظيف الأعمدة
        df.columns = [str(c).strip().replace('é', 'e') for c in df.columns]
        
        # تحويل الأرقام
        for c in ['Quantite', 'Long']:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

        excel = generate_ultimate_excel(df)
        os.remove(path)
        return send_file(excel, as_attachment=True, download_name=f"METRE_CERTIFIE_{file.filename}.xlsx")
    except Exception as e: return f"Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(debug=True)