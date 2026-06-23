# Metrai — Dossier d'entraînement IA
## Structure

```
Metrai/
├── 01_data_raw/          ← Vos fichiers originaux (PDF + Excel)
├── 02_data_processed/    ← Fichiers convertis (images + JSON)
├── 03_prompts/           ← Exemples few-shot pour l'IA
└── 04_evaluation/        ← Plans de test (non utilisés en entraînement)
```

## Comment remplir

1. Pour chaque projet : renommez `projet_XX_NOM_AFFAIRE` avec le vrai nom
2. Déposez `plan.pdf` et `metres_expert.xlsx` dans `01_data_raw/projet_XX/`
3. Le script de conversion génère automatiquement `02_data_processed/`

> **Note :** Si vous avez un fichier extrait par OCR avec un format décalé (`input_to_fix.xlsx`), vous pouvez utiliser le script `fix_excel.py` pour le corriger avant conversion. Le script `convert.py` supporte désormais à la fois l'ancien format (`MÉTRÉ_MODÈLE`) et le nouveau format corrigé.

## Projets : 30 au total (01 → 30)
