with open('backend/engines/export_engine.py', 'r', encoding='utf-8') as f:
    code = f.read()

with open('patch.py', 'r', encoding='utf-8') as f:
    patch_code = f.read()

new_func = patch_code.split("new_func = r'''")[1].split("'''")[0]

start_idx = code.find('    def to_excel_advanced(')
end_idx = code.find('    @staticmethod\n    def to_pdf(')

if start_idx != -1 and end_idx != -1:
    final_code = code[:start_idx] + new_func + '\n' + code[end_idx:]
    with open('backend/engines/export_engine.py', 'w', encoding='utf-8') as f:
        f.write(final_code)
    print("Patched successfully.")
else:
    print("Could not find start or end index.")
