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

## Projets : 30 au total (01 → 30)
