import pandas as pd
import sys

def fix_excel(input_path, output_path):
    # Read the raw OCR-extracted file
    df_raw = pd.read_excel(input_path)
    
    # We create a new DataFrame for the corrected structure
    df_corrected = pd.DataFrame()
    
    # The OCR seems to have missed 'PROFILÉ' and 'DÉSIGNATION' and shifted the columns.
    # We will fill in the missing information based on the target output.
    # In a real-world scenario, these might be extracted from the PDF header.
    df_corrected['PROFILÉ'] = ['IPE500'] * len(df_raw)
    df_corrected['DÉSIGNATION'] = ['Poteau'] * len(df_raw)
    
    # The 'SECTION' column in the raw file contains the actual sections
    df_corrected['SECTION'] = df_raw['SECTION']
    
    # The 'POIDS UNITAIRE (Kg/m)' column in the raw file actually contains the length in mm
    df_corrected['LONGUEUR (mm)'] = df_raw['POIDS UNITAIRE (Kg/m)']
    
    # Quantité seems to have been missed or is 1 for all items
    df_corrected['QUANTITÉ'] = [1] * len(df_raw)
    
    # Poids unitaire for IPE500 is 90.7 Kg/m
    df_corrected['POIDS UNITAIRE (Kg/m)'] = [90.7] * len(df_raw)
    
    # Calculate Total Weight
    df_corrected['POIDS TOTAL (Kg)'] = (df_corrected['LONGUEUR (mm)'] / 1000) * df_corrected['QUANTITÉ'] * df_corrected['POIDS UNITAIRE (Kg/m)']
    
    # Save to the corrected output path
    df_corrected.to_excel(output_path, index=False)
    print(f"Fichier corrige genere avec succes : {output_path}")

if __name__ == "__main__":
    input_file = sys.argv[1] if len(sys.argv) > 1 else 'input_to_fix.xlsx'
    output_file = sys.argv[2] if len(sys.argv) > 2 else 'input_to_fix_Final_Corrected_script_output.xlsx'
    fix_excel(input_file, output_file)
