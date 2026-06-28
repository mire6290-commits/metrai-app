import os
import io
import re
import pandas as pd
import requests
import pdfplumber
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# --- 1. الإعدادات (نخدمو بـ Mistral حيت Gemini فيه مشكل 404) ---
MISTRAL_API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# قاعدة بيانات الأوزان باش ما يغلطش فالحساب
STEEL_DB = {
    'IPE500': 90.7, 'IPE450': 77.6, 'IPE270': 36.1, 'IPE240': 30.7, 
    'HEA120': 19.9, 'IPE120': 10.4, 'IPE140': 12.9, 'UPN200': 25.3,
    'L60*60*6': 5.42, 'D12': 0.888, 'ROND_30': 5.55
}

def clean_and_extract_num(text):
    """دالة باش نجبدو غير الأرقام ونصلحو الفواصل"""
    if not text: return 0
    cleaned = re.sub(r'[^\d.]', '', str(text).replace(',', '.'))
    try:
        return float(cleaned)
    except:
        return 0

def get_mistral_data(text):
    """إرسال النص لـ Mistral مع أوامر صارمة باش ما يخليش الأصفار"""
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Expert SINERTECH. Extrais le métré en CSV STRICT.
    IMPORTANT: Ne laisse JAMAIS la colonne 'Long' à 0. 
    Cherche bien les dimensions (ex: 12000, 600, L=...) dans le texte.
    
    Colonnes: Nomenclatures,Quantite,Long
    Format: CSV uniquement, pas de texte autour.
    Texte: {text}
    """
    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }
    
    response = requests.post(url, json=payload, headers=headers).json()
    csv_raw = response['choices'][0]['message']['content'].strip()
    return csv_raw.replace('```csv', '').replace('```', '').strip()

def generate_pro_excel(df):
    """توليد ملف إكسيل احترافي فيه الحسابات صحيحة"""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # نربطو الأوزان ونحسبو كل سطر
    df['Poids_m'] = df['Nomenclatures'].apply(lambda x: STEEL_DB.get(str(x).replace(" ", "").upper(), 0))
    df['Poids_Unit'] = (df['Long'] / 1000) * df['Poids_m']
    df['Total_Weight'] = df['Poids_Unit'] * df['Quantite']

    df.to_excel(writer, index=False, sheet_name='METRE_SINERTECH', startrow=9)
    workbook = writer.book
    worksheet = writer.sheets['METRE_SINERTECH']
    
    # الستايل "الهارب"
    header_fmt = workbook.add_format({'bold': True, 'bg_color': '#1E293B', 'font_color': 'white', 'border': 1})
    total_fmt = workbook.add_format({'bold': True, 'bg_color': '#F59E0B', 'border': 1, 'num_format': '#,##0.00'})

    worksheet.write('A2', 'SINERTECH IA - MÉTRÉ AUTOMATISÉ', workbook.add_format({'bold': True, 'font_size': 20}))
    
    # المجموع الكلي
    total_row = 10 + len(df)
    worksheet.write(total_row, 6, 'TOTAL GÉNÉRAL (Kg):', workbook.add_format({'bold': True}))
    worksheet.write_formula(total_row, 7, f'=SUM(H11:H{total_row})', total_fmt)
    
    writer.close()
    output.seek(0)
    return output

# --- الواجهة الفرنسية (Modern UI) ---
INDEX_HTML = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8"><title>Sinertech IA | Mistral Pro</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-white min-h-screen flex items-center justify-center font-sans">
    <div class="max-w-xl w-full p-12 bg-slate-900 rounded-[3rem] border border-slate-800 shadow-2xl text-center">
        <h1 class="text-5xl font-black mb-4 uppercase tracking-tighter">Sinertech <span class="text-amber-500 italic">IA</span></h1>
        <p class="text-slate-500 text-sm mb-12">SYSTÈME D'EXTRACTION DE MÉTRÉ HAUTE PRÉCISION</p>
        
        <form action="/upload" method="post" enctype="multipart/form-data" id="upForm">
            <label class="group block border-2 border-dashed border-slate-700 p-16 rounded-[2rem] hover:border-amber-500 transition-all cursor-pointer hover:bg-white/5">
                <input type="file" name="file" class="hidden" onchange="document.getElementById('ld').style.display='block'; this.form.submit()">
                <span class="text-xl font-bold uppercase tracking-widest block mb-2">Choisir Plan PDF</span>
                <span class="text-slate-600 text-xs">Propulsé par Mistral AI Engine</span>
            </label>
            <div id="ld" class="hidden mt-8 animate-pulse text-amber-500 font-bold uppercase text-xs">Analyse et Calcul en cours...</div>
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
        
        # تنظيف البيانات باش الحساب يخدم
        df.columns = [str(c).strip() for c in df.columns]
        for col in ['Quantite', 'Long']:
            if col in df.columns:
                df[col] = df[col].apply(clean_and_extract_num)
            else: df[col] = 0
            
        excel = generate_pro_excel(df)
        os.remove(path)
        return send_file(excel, as_attachment=True, download_name=f"Metre_Sinertech_{file.filename}.xlsx")
    except Exception as e: return f"Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)