from engines.export_engine import ExportEngine

data = [
  {'repere': 'P1', 'nomenclature': 'Portique File 1 à 6', 'role': 'Poteau', 'quantite': 12, 'profil': 'IPE 300', 'longueur': 6000, 'poids_lineique': 42.2},
  {'repere': 'T1', 'nomenclature': 'Portique File 1 à 6', 'role': 'Traverse', 'quantite': 12, 'profil': 'IPE 270', 'longueur': 5930, 'poids_lineique': 36.1},
  {'repere': 'PA1', 'nomenclature': 'Toiture Entraxe 5m', 'role': 'Panne', 'quantite': 48, 'profil': 'UPN 140', 'longueur': 5000, 'poids_lineique': 16.0},
  {'repere': 'C1', 'nomenclature': 'Long Pan', 'role': 'Contreventement', 'quantite': 8, 'profil': 'Tube Carré 80x80', 'longueur': 7200, 'poids_lineique': 10.5},
]

excel_bytes = ExportEngine.to_excel(data)
with open('output_mock_padel.xlsx', 'wb') as f:
    f.write(excel_bytes)
print("Mock Excel created at output_mock_padel.xlsx!")
