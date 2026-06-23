import os
import io
import re
import pandas as pd
import requests
import pdfplumber
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# --- CONFIG ---
MISTRAL_API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# قاعدة بيانات الأوزان الصارمة
STEEL_DB = {
    'IPE500': 90.7, 'IPE450': 77.6, 'IPE270': 36.1, 'IPE240': 30.7, 
    'HEA120': 19.9, 'IPE120': 10.4, 'IPE140': 12.9, 'UPN200': 25.3,
    'L60*60*6': 5.42, 'D12': 0.888, 'ROND_30': 5.55
}

def force_numeric(value):
    """تنظيف شامل: كايحيد mm، kg، الفواصل، والخوى باش يبقى غير الرقم"""
    if pd.isna(value) or str(value).strip() == '': return 0.0
    # تبديل الفاصلة بنقطة وحذف أي حاجة ماشي رقم
    text = str(value).replace(',', '.').replace(' ', '')
    clean = re.sub(r'[^\d.]', '', text)
    try:
        return float(clean)
    except:
        return 0.0

def get_mistral_data(text):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    prompt = f"Expert SINERTECH. Extrais en CSV STRICT (Pos,Nomenclatures,Quantite,Long). Interdit d'ajouter des unités (mm, kg) dans les colonnes. Texte: {text}"
    payload = {"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    try:
        resp = requests.post(url, json=payload, headers=headers).json()
        raw = resp['choices'][0]['message']['content'].strip()
        return raw.split("```")[1].replace("csv", "").strip() if "```" in raw else raw
    except: return "Pos,Nomenclatures,Quantite,Long\n1,Error,0,0"

def generate_pro_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # --- التنظيف القاتل للأخطاء ---
    for col in ['Quantite', 'Long']:
        if col in df.columns:
            df[col] = df[col].apply(force_numeric) # تنظيف كل خانة بوحدها

    # ربط الوزن وحساب النتيجة
    df['Poids_m'] = df['Nomenclatures'].apply(lambda x: STEEL_DB.get(str(x).upper().replace(" ", ""), 0))
    df['Poids_Unit'] = (df['Long'] / 1000) * df['Poids_m']
    df['Total_Weight'] = df['Poids_Unit'] * df['Quantite']

    df.to_excel(writer, index=False, sheet_name='METRE', startrow=9)
    workbook, worksheet = writer.book, writer.sheets['METRE']
    
    # التنسيق والمجموع
    fmt_total = workbook.add_format({'bold': True, 'bg_color': '#F59E0B', 'num_format': '#,##0.00', 'border': 1})
    total_row = 10 + len(df)
    
    worksheet.write(total_row, 6, 'TOTAL CALCULÉ (Kg):', workbook.add_format({'bold': True}))
    # استخدام معادلة إكسيل حقيقية هي الضمان الوحيد
    worksheet.write_formula(total_row, 7, f'=SUM(H11:H{total_row})', fmt_total)
    
    writer.close()
    output.seek(0)
    return output

INDEX_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-slate-950 text-white min-h-screen flex items-center justify-center">
    <div class="bg-slate-900 p-16 rounded-[3rem] shadow-2xl text-center border border-slate-800">
        <h1 class="text-4xl font-black mb-8 text-amber-500">SINERTECH <span class="text-white italic">ULTIMATE</span></h1>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" onchange="this.form.submit()" class="hidden" id="f">
            <label for="f" class="cursor-pointer border-2 border-dashed border-slate-700 p-10 block rounded-3xl hover:border-amber-500 transition">
                CLIQUEZ POUR RÉPARER LE MÉTRÉ (FIX TOTAL 0)
            </label>
        </form>
    </div>
</body>
</html>
"""

@app.route('/')
def index(): return render_template_string(INDEX_HTML)

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['file']
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    try:
        text = ""
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages: text += (page.extract_text() or "") + "\n"
        
        csv_data = get_mistral_data(text)
        df = pd.read_csv(io.StringIO(csv_data), on_bad_lines='skip', sep=None, engine='python')
        
        # توحيد أسماء الأعمدة
        df.columns = [str(c).strip().replace('é', 'e') for c in df.columns]
        
        excel = generate_pro_excel(df)
        os.remove(path)
        return send_file(excel, as_attachment=True, download_name="Metre_Final_Sinertech.xlsx")
    except Exception as e: return f"Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)