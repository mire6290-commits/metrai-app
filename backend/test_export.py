import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from engines.export_engine import ExportEngine

def main():
    dummy_data = [
        {"id": "P001", "designation": "IPE 200", "type": "IPE", "length_m": 4.5, "quantity": 3, "zone": "File A", "confidence": 0.95, "masse_lineaire_kg_m": 22.4, "poids_total_kg": 302.4},
        {"id": "P002", "designation": "HEA 160", "type": "HEA", "length_m": 2.0, "quantity": 10, "zone": "Poteaux", "confidence": 0.9, "masse_lineaire_kg_m": 30.4, "poids_total_kg": 608.0},
        {"id": "P003", "designation": "TUBE 80x80x5", "type": "TUBE", "length_m": 1.5, "quantity": 4, "zone": "Contreventement", "confidence": 0.85, "masse_lineaire_kg_m": 11.3, "poids_total_kg": 67.8},
    ]

    print("Generating Excel with dummy data...")
    excel_bytes = ExportEngine.to_excel(dummy_data)
    
    output_path = "C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/output_test_padel_dummy.xlsx"
    with open(output_path, "wb") as f:
        f.write(excel_bytes)
        
    print(f"Excel saved to {output_path}")

if __name__ == "__main__":
    main()
