import os
import io
import re
import pandas as pd
import requests
import pdfplumber
from flask import Flask, render_template_string, request, send_file

app = Flask(__name__)

# --- 1. الإعدادات وقاعدة البيانات ---
MISTRAL_API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

STEEL_DB = {
    'IPE500': 90.7, 'IPE450': 77.6, 'IPE270': 36.1, 'IPE240': 30.7, 
    'HEA120': 19.9, 'IPE120': 10.4, 'IPE140': 12.9, 'UPN200': 25.3,
    'L60*60*6': 5.42, 'D12': 0.888, 'ROND_30': 5.55
}

def clean_num(v):
    if pd.isna(v) or str(v).strip() == '': return 0.0
    res = re.sub(r'[^\d.]', '', str(v).replace(',', '.'))
    try: return float(res)
    except: return 0.0

# --- 2. استخراج البيانات من Mistral ---
def get_mistral_data(text):
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {MISTRAL_API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Expert SINERTECH. Extrais le métré en CSV STRICT. 
    Colonnes: Pos, Nomenclatures, Quantite, Long
    Interdiction d'ajouter des textes explicatifs.
    Texte: {text}
    """
    payload = {"model": "mistral-large-latest", "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    
    try:
        resp = requests.post(url, json=payload, headers=headers).json()
        raw = resp['choices'][0]['message']['content'].strip()
        csv_clean = re.sub(r'```csv|```', '', raw).strip()
        return csv_clean
    except:
        return "Pos,Nomenclatures,Quantite,Long\n1,Error,0,0"

# --- 3. توليد الإكسيل مع نظام "التوحيد الذكي" (Column Unification) ---
def generate_pro_excel(df):
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # --- نظام الخرائط (Mapping) لحل مشاكل KeyError ---
    # هاد الدالة كاتقلب على أي سمية قريبة للسمية الأصلية وكايصححها
    mapping = {
        'Nomenclatures': ['Nomenclature', 'Nomenclatures', 'Profile', 'Profile', 'Type', 'Designation'],
        'Quantite': ['Quantite', 'Quantité', 'Qty', 'Qty.', 'Quant', 'Qte'],
        'Long': ['Long', 'Longueur', 'Length', 'L', 'L (mm)', 'Long (mm)']
    }
    
    new_cols = {}
    for official_name, aliases in mapping.items():
        for col in df.columns:
            if col.strip() in aliases:
                new_cols[col] = official_name
    
    df.rename(columns=new_cols, inplace=True)

    # التأكد من وجود الأعمدة الأساسية
    for essential in ['Nomenclatures', 'Quantite', 'Long']:
        if essential not in df.columns:
            df[essential] = 0 if essential != 'Nomenclatures' else "Inconnu"

    # تنظيف الأرقام
    df['Quantite'] = df['Quantite'].apply(clean_num)
    df['Long'] = df['Long'].apply(clean_num)

    # الحسابات برمجياً
    df['Poids_m'] = df['Nomenclatures'].apply(lambda x: STEEL_DB.get(str(x).upper().replace(" ", ""), 0))
    df['Poids_Unit'] = (df['Long'] / 1000) * df['Poids_m']
    df['Total_Weight'] = df['Poids_Unit'] * df['Quantite']

    # فرض الترتيب النهائي
    cols = ['Pos', 'Nomenclatures', 'Quantite', 'Long', 'Poids_m', 'Poids_Unit', 'Total_Weight']
    df = df.reindex(columns=cols).fillna(0)

    df.to_excel(writer, index=False, sheet_name='METRE', startrow=9)
    workbook, worksheet = writer.book, writer.sheets['METRE']
    
    # تنسيقات SINERTECH
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#1E293B', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_total = workbook.add_format({'bold': True, 'bg_color': '#F59E0B', 'border': 1, 'num_format': '#,##0.00'})

    for i, col in enumerate(df.columns):
        worksheet.write(9, i, col, fmt_head)

    total_row = 10 + len(df)
    worksheet.write(total_row, 5, 'TOTAL GÉNÉRAL (Kg):', workbook.add_format({'bold': True}))
    worksheet.write_formula(total_row, 6, f'=SUM(G11:G{total_row})', fmt_total)

    writer.close()
    output.seek(0)
    return output

@app.route('/')
def index():
    return """
    <body style="background:#020617; color:white; font-family:sans-serif; text-align:center; padding-top:100px;">
        <h1 style="color:#f59e0b">SINERTECH IA FIX V3</h1>
        <p>Correction automatique des noms de colonnes</p>
        <form action="/upload" method="post" enctype="multipart/form-data">
            <input type="file" name="file" onchange="this.form.submit()" style="padding:20px; border:2px dashed #444; border-radius:15px; cursor:pointer;">
        </form>
    </body>
    """

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
        from io import StringIO
        # قراءة الـ CSV بمرونة عالية
        df = pd.read_csv(StringIO(csv_data), on_bad_lines='skip', sep=None, engine='python')
        
        # تنظيف الفراغات من أسماء الأعمدة قبل البدء
        df.columns = [c.strip() for c in df.columns]

        excel = generate_pro_excel(df)
        os.remove(path)
        return send_file(excel, as_attachment=True, download_name=f"Metre_Final_M9ad.xlsx")
    except Exception as e:
        if os.path.exists(path): os.remove(path)
        return f"Erreur : {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)