"""
convert.py — Convertit tous les metres_expert.xlsx en metres.json
Usage : python convert.py
"""
import os, json
from pathlib import Path

BASE = Path(__file__).parent
RAW  = BASE / "01_data_raw"
PROC = BASE / "02_data_processed"

def convert_projet(projet_dir: Path):
    xlsx = projet_dir / "metres_expert.xlsx"
    if not xlsx.exists():
        print(f"  ⚠  Pas de metres_expert.xlsx dans {projet_dir.name}")
        return
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx, data_only=True)
        ws = wb["📋 MÉTRÉ_MODÈLE"]
    except Exception as e:
        print(f"  ✗  Erreur lecture {projet_dir.name} : {e}")
        return

    projet_name = projet_dir.name.split("_", 2)[-1] if "_" in projet_dir.name else projet_dir.name
    lots = {}

    for row in ws.iter_rows(min_row=9, max_row=38, values_only=True):
        row = (list(row) + [None]*10)[:10]
        pos, nom, qte, section, long_mm, kgm, kgu, kg_tot, cat, rem = row
        if not nom or not qte:
            continue
        cat_id = (cat or "autre").lower().replace("é","e").replace("è","e").replace("ê","e").replace(" ","_")
        if cat_id not in lots:
            lots[cat_id] = {"id":cat_id,"nom":cat or "Autre","categorie":cat_id,"elements":[],"sous_total_kg":0,"sous_total_ml":0}
        long_m   = round(long_mm/1000,3) if long_mm else None
        total_ml = round(long_m*qte,2)   if long_m  else None
        lots[cat_id]["elements"].append({
            "repere": str(pos) if pos else "",
            "section": str(section) if section else "",
            "longueur_m": long_m,
            "quantite": int(qte),
            "total_ml": total_ml,
            "poids_kg_m": float(kgm) if kgm else None,
            "poids_total_kg": round(float(kg_tot),2) if kg_tot else None,
            "remarque": str(rem) if rem else ""
        })
        lots[cat_id]["sous_total_kg"] += float(kg_tot or 0)
        lots[cat_id]["sous_total_ml"] += float(total_ml or 0)

    sous_total  = sum(l["sous_total_kg"] for l in lots.values())
    boulonnerie = round(sous_total*0.05,2)
    total_net   = round(sous_total+boulonnerie,2)

    result = {
        "projet": projet_name,
        "bureau_etudes": "",
        "date": "",
        "lots": list(lots.values()),
        "assemblages": {"platines":[],"raidisseurs":[]},
        "boulonnerie": [{"designation":"BOULONNERIE + SOUDAGE 5%","total_kg":boulonnerie}],
        "ancrages": [],
        "recapitulatif": {
            "sous_total_kg": round(sous_total,2),
            "boulonnerie_kg": boulonnerie,
            "total_acier_kg": total_net,
            "observations": ""
        }
    }
    out_dir = PROC / projet_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)
    out_json = out_dir / "metres.json"
    with open(out_json,"w",encoding="utf-8") as f:
        json.dump(result,f,ensure_ascii=False,indent=2)
    print(f"  ✓  {projet_dir.name} → {total_net:,.2f} kg")

if __name__ == "__main__":
    print("═"*55)
    print("  METRAI — Conversion Excel → JSON")
    print("═"*55)
    projets = sorted(RAW.glob("projet_*"))
    print(f"  {len(projets)} projets trouvés\n")
    for p in projets:
        convert_projet(p)
    print("\n✅ JSON disponibles dans 02_data_processed/")
