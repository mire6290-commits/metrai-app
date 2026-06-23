import os
import io
import pandas as pd
import requests
from flask import Flask, render_template, request, send_file

app = Flask(__name__)

# إعداد المجلدات المؤقتة
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# مفتاح API الخاص بك لـ Mistral (مفعل وصحيح)
API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"

def generate_expert_excel(df):
    """توليد ملف إكسيل احترافي بتنسيق مكاتب الدراسات الهندسية"""
    output = io.BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    
    # نضع البيانات ابتداءً من السطر 10 لترك مساحة للترويسة
    df.to_excel(writer, index=False, sheet_name='Métré_Détaillé', startrow=9)
    
    workbook = writer.book
    worksheet = writer.sheets['Métré_Détaillé']

    # --- تعريف التنسيقات (Formatting) ---
    header_fmt = workbook.add_format({
        'bold': True, 'bg_color': '#D9D9D9', 'border': 1, 'align': 'center', 'valign': 'vcenter', 'font_name': 'Arial'
    })
    title_fmt = workbook.add_format({
        'bold': True, 'font_size': 16, 'font_color': '#C00000', 'font_name': 'Arial'
    })
    company_fmt = workbook.add_format({
        'bold': True, 'font_size': 12, 'font_name': 'Arial'
    })
    num_fmt = workbook.add_format({
        'num_format': '#,##0.00', 'border': 1, 'align': 'center', 'font_name': 'Arial'
    })
    text_fmt = workbook.add_format({
        'border': 1, 'align': 'center', 'font_name': 'Arial'
    })
    total_fmt = workbook.add_format({
        'bold': True, 'bg_color': '#FDE9D9', 'border': 1, 'num_format': '#,##0.00', 'align': 'center'
    })
    total_label_fmt = workbook.add_format({
        'bold': True, 'bg_color': '#FDE9D9', 'border': 1, 'align': 'right'
    })

    # --- كتابة الترويسة (Header) كما في ملف metres_expert ---
    worksheet.write('A2', 'AFFAIRE: USINE TRUST (EXTRACTION IA)', title_fmt)
    worksheet.write('A5', '- SINERTECH -', company_fmt)
    worksheet.write('G5', 'Le: 14 / 05 / 2026', company_fmt)
    worksheet.write('A8', '1- Ossature métallique :', workbook.add_format({'bold': True, 'underline': True, 'font_size': 12}))

    # --- تنسيق عناوين الجدول (Headers) ---
    headers = ["Pos", "Nomenclatures", "Quantité", "Designation", "Long (mm)", "Poids Kg/(m)", "Poids Kg/Unt", "Poids Tot Kg"]
    for col_num, value in enumerate(headers):
        worksheet.write(9, col_num, value, header_fmt)

    # --- كتابة البيانات وتطبيق التنسيقات على الخلايا ---
    for row_idx in range(len(df)):
        current_row = 10 + row_idx
        worksheet.write(current_row, 0, df.iloc[row_idx]['Pos'], text_fmt)
        worksheet.write(current_row, 1, df.iloc[row_idx]['Nomenclatures'], text_fmt)
        worksheet.write(current_row, 2, df.iloc[row_idx]['Quantité'], num_fmt)
        worksheet.write(current_row, 3, df.iloc[row_idx]['Designation'], text_fmt)
        worksheet.write(current_row, 4, df.iloc[row_idx]['Long (mm)'], num_fmt)
        worksheet.write(current_row, 5, df.iloc[row_idx]['Poids Kg/(m)'], num_fmt)
        worksheet.write(current_row, 6, df.iloc[row_idx]['Poids Kg/Unt'], num_fmt)
        worksheet.write(current_row, 7, df.iloc[row_idx]['Poids Tot Kg'], num_fmt)

    # --- إضافة سطر المجموع الكلي (Total General) ---
    total_row_idx = 10 + len(df)
    worksheet.write(total_row_idx, 6, 'TOTAL GENERAL (Kg):', total_label_fmt)
    # استخدام صيغة Excel SUM لعمود Poids Tot Kg (العمود الثامن H)
    worksheet.write_formula(total_row_idx, 7, f'=SUM(H11:H{total_row_idx})', total_fmt)

    # --- ضبط قياسات الأعمدة لتناسب المحتوى ---
    worksheet.set_column('A:A', 6)   # Pos
    worksheet.set_column('B:B', 30)  # Nomenclatures
    worksheet.set_column('C:C', 10)  # Quantité
    worksheet.set_column('D:D', 25)  # Designation
    worksheet.set_column('E:H', 15)  # Values

    writer.close()
    output.seek(0)
    return output

def extract_from_mistral(pdf_path):
    """استخراج البيانات من الـ PDF عبر طلب مباشر لـ API Mistral"""
    import pdfplumber
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t: text += t + "\n"

    # التواصل المباشر مع API لتجاوز مشاكل التثبيت
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    
    prompt = f"""
    Analyse ce document de charpente métallique. 
    Extrais les éléments sous forme de CSV avec virgule.
    Colonnes obligatoires: Pos, Nomenclatures, Quantité, Designation, Long (mm), Poids Kg/(m)
    Texte:
    {text}
    """

    payload = {
        "model": "mistral-large-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0
    }

    response = requests.post(url, json=payload, headers=headers).json()
    csv_raw = response['choices'][0]['message']['content'].strip()
    
    # تنظيف مخرجات CSV من Markdown
    if "```csv" in csv_raw:
        csv_raw = csv_raw.split("```csv")[1].split("```")[0].strip()
    elif "```" in csv_raw:
        csv_raw = csv_raw.split("```")[1].split("```")[0].strip()

    # تحويل النص إلى DataFrame
    df = pd.read_csv(io.StringIO(csv_raw))
    df.columns = [c.strip() for c in df.columns]

    # تحويل القيم لحساب الأوزان أوتوماتيكياً
    for c in ['Quantité', 'Long (mm)', 'Poids Kg/(m)']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)

    # حسابات المتري الهندسية
    df['Poids Kg/Unt'] = (df['Long (mm)'] / 1000) * df['Poids Kg/(m)']
    df['Poids Tot Kg'] = df['Poids Kg/Unt'] * df['Quantité']
    
    return df

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return "Aucun fichier"
    file = request.files['file']
    if file.filename == '': return "Fichier vide"
    
    path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(path)
    
    try:
        data_frame = extract_from_mistral(path)
        final_excel = generate_expert_excel(data_frame)
        os.remove(path)
        return send_file(
            final_excel, 
            as_attachment=True, 
            download_name="Metre_Expert_Sinertech.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        if os.path.exists(path): os.remove(path)
        return f"Erreur : {str(e)}"

if __name__ == '__main__':
    # تشغيل السيرفر على بورت 5000
    print("Démarrage sur http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True)