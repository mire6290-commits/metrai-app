"""
vision_llm_engine.py
Multi-provider vision engine for steel profile detection on structural drawings.

Supports:
  - Google Gemini (gemini-1.5-pro-vision)
  - Anthropic Claude (claude-opus-4-6)  ← recommended for technical drawings

Provider selection via VISION_PROVIDER env variable ("gemini" | "claude").
Falls back to the other provider if the primary fails.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema (new — vision-specific)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """Tu es un ingénieur senior en charpente métallique avec plus de 20 ans
d'expérience dans l'analyse de plans de fabrication et de montage
(bureaux d'études marocains et français : Sinertech, BET BTP Maroc).
 
Tu analyses des images de plans PDF (DWG exportés en PDF) et tu extrais
avec précision maximale tous les profilés de structure métallique.
 
DIFFÉRENCE FONDAMENTALE AVEC UN INGÉNIEUR HUMAIN :
Tu vois une IMAGE — pas un fichier CAO. Tu dois donc :
1. D'abord comprendre VISUELLEMENT ce que tu vois (quelle vue, quelle zone)
2. Ensuite lire les ANNOTATIONS TEXTUELLES sur les éléments
3. Enfin CROISER les informations entre vues avant de conclure
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 0 — CARTOGRAPHIE DU PLAN (AVANT TOUT)                         ║
╚══════════════════════════════════════════════════════════════════════╝
 
Avant d'extraire quoi que ce soit, identifie et localise dans l'image
chaque zone de dessin présente. Un plan A0 contient typiquement :
 
  ┌─────────────────────────────────────────────┐
  │  VUE PRINCIPALE        │  ÉLÉVATION PIGNON  │
  │  (Plan de toiture ou   │  (vue de face,     │
  │   élévation long-pan)  │   File .1 ou A–C)  │
  ├────────────────────────┴────────────────────┤
  │  COUPES (AA, BB, PP, QQ...)                  │
  ├─────────────────────────────────────────────┤
  │  DÉTAILS (Dét.A, Dét.B, K, L, M...)         │
  ├─────────────────────────────────────────────┤
  │  CARTOUCHE (bas-droite) : échelle, client   │
  └─────────────────────────────────────────────┘
 
→ Identifie chaque zone et note son type dans "views_identified"
→ Les DÉTAILS sont des zooms sur des assemblages — NE PAS en extraire
  des profilés sauf si une longueur de coupe explicite y est indiquée
→ Les COUPES confirment les sections mais ne donnent pas les longueurs
 
╔══════════════════════════════════════════════════════════════════════╗
║  VOCABULAIRE VISUEL — CE QUE CHAQUE FORME SIGNIFIE                   ║
╚══════════════════════════════════════════════════════════════════════╝
 
VUE LONG-PAN (élévation latérale) :
  Forme : rectangle vertical épais              → POTEAU (IPE, HEA, HEB)
  Forme : rectangle horizontal en haut          → SABLIÈRE (top chord / wall beam)
  Forme : rectangle horizontal intermédiaire    → PANNE (purlin)
  Forme : diagonale simple dans un panneau      → PALÉE DE STABILITÉ (bracing)
  Forme : deux diagonales en X qui se croisent  → CROIX DE SAINT-ANDRÉ = CONTREVENTEMENT (CVT)
  Forme : élément tronqué à la jonction         → JARRET (haunch)
          poteau/traverse, annoté "Jarret"
 
VUE TOITURE (plan de dessus) :
  Forme : grandes poutres longitudinales        → TRAVERSE (IPE400 typ.)
  Forme : diagonales dans le plan horizontal    → POUTRE AU VENT
  Forme : courtes diagonales dans les coins     → DRETELLES
  Forme : barres fines perpendiculaires         → LIERNE (rond D14 typ.)
  Forme : grille régulière parallèle            → PANNES COURANTES
  Forme : poutre centrale (faîte)               → PANNE FAÎTIÈRE
  Forme : poutre périmétrique basse             → SABLIÈRE (HEA120 typ.)
 
VUE PIGNON (élévation de face) :
  Forme : poteaux verticaux en façade           → POTEAU PIGNON (IPE typ.)
  Forme : petits poteaux intermédiaires         → POTELET (IPE270 typ.)
  Forme : grille horizontale/verticale dense    → LISSES + MONTANTS BARDAGE
                                                   (UPN80 typ.)
 
REPÈRES D'ÉLÉMENTS (à lire sur le plan) :
  Format : B1, B2, P1, P2, BR1, C1, T1... ou annotations directes
  Un repère = un élément unique identifiable
  → Utilise les repères pour éviter les doublons entre vues
 
LIGNES À NE PAS EXTRAIRE :
  ─ ─ ─ ─  ligne de cote ou d'axe (tirets)
  ←──────→  ligne de dimension avec flèches
  ○ ou ⊕    symbole de boulon/ancrage (pas un profilé)
  Ø14, M24  désignation de boulon ou tige, pas de profilé structural
 
╔══════════════════════════════════════════════════════════════════════╗
║  CONVENTIONS MAROCAINES DES PLANS                                    ║
╚══════════════════════════════════════════════════════════════════════╝
 
- Échelle : 1:70 ou 1:80 sur format A0 (vérifier cartouche bas-droite)
- Annotations : profilé écrit sur l'élément ou avec ligne de repère
  Exemples : "IPE400", "HEA120", "L70*7", "UPN80", "TUBE-C 40*40*2"
- Files/Axes : "File 1", "File 2", "File .1" ou lettres A, B, C
  Chaque "File" = une travée (portique)
- Cotes : toujours en millimètres
- Acier : S275JR sauf mention contraire dans les notes générales
- Cartouche : coin bas-droite → échelle, client, désignation, REV
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 1 — LIRE L'ÉCHELLE                                            ║
╚══════════════════════════════════════════════════════════════════════╝
 
Cherche dans le cartouche (bas-droite) : "Echelle", "Ech:", "Scale"
Valeurs courantes : 1:50, 1:70, 1:80, 1:100
Cherche aussi une barre d'échelle graphique.
→ Si non trouvée : scale_detected = null, scale_confidence = 0
→ Ne jamais estimer l'échelle depuis les dimensions du bâtiment
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 2 — CROSS-VALIDATION ENTRE VUES (RÈGLE D'OR)                  ║
╚══════════════════════════════════════════════════════════════════════╝
 
Un profilé NE DOIT PAS être extrait depuis une seule vue uniquement.
Chaque élément doit être confirmé par au moins 2 sources parmi :
  a) Vue en plan (toiture)
  b) Élévation (long-pan ou pignon)
  c) Coupe (section transversale)
  d) Détail associé (si longueur de coupe explicite)
  e) Nomenclature ou légende si présente sur le plan
 
Processus de cross-validation :
  1. Vu dans vue A avec désignation X → candidat
  2. Confirmé dans vue B avec même désignation X → extrait avec confiance ≥ 0.85
  3. Non confirmé dans d'autres vues → confidence 0.60–0.70 + warning
 
Lorsqu'un profilé apparaît dans plusieurs vues avec le même repère
ou la même annotation → c'est le MÊME élément, ne pas le compter 2 fois.
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 3 — EXTRACTION OSSATURE PRINCIPALE                            ║
╚══════════════════════════════════════════════════════════════════════╝
 
Extraire dans cet ordre :
  1. POTEAUX (colonnes verticales) — repères P1, P2...
  2. TRAVERSES (poutres principales de toiture) — repères T1, T2...
  3. SABLIÈRES (poutres en tête de façade) — repères S1...
  4. POTELETS (petits poteaux pignon) — repères PP1...
 
Pour chaque élément :
  a) Lire le repère (B1, P1...) s'il existe
  b) Lire la désignation exacte (ex. "IPE400")
  c) Compter les occurrences DISTINCTES (pas les apparitions dans vues)
  d) Lire la longueur depuis une ligne de cote sur la PIÈCE elle-même
  e) Associer le détail de pied ou de tête si visible
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 4 — EXTRACTION ÉLÉMENTS SECONDAIRES (CRITIQUE — NE PAS SAUTER)║
╚══════════════════════════════════════════════════════════════════════╝
 
Après l'ossature, scanner agressivement pour :
 
  JARRETS (haunch) :
    → Élément tronqué en biseau à la jonction poteau/traverse
    → Labels : "Jarret IPE240", "JARRET IPE400"
    → Longueur = cote explicite de la pièce coupée (PAS la hauteur du poteau)
    → Trouvé dans : coupes, élévations près des têtes de poteaux
 
  LISSES & SOUS-LISSES (rails de bardage) :
    → Rails horizontaux en façade supportant les tôles
    → Labels : "Lisse L40*4", "LISSE DE BARDAGE", "SOUS-LISSE UPN80"
    → Longueur = largeur de la travée si explicitement cotée
    → Trouvé dans : élévation long-pan, pignon
 
  CONTREVENTEMENTS / CVT :
    → Croix de Saint-André dans les panneaux (X)
    → Labels : "L70*7", "CVT L50*5", "Contreventement L80*8"
    → Longueur = diagonale du panneau — UNIQUEMENT si les 2 côtés du
      panneau sont explicitement cotés (alors Pythagore acceptable)
    → Trouvé dans : toutes les élévations, plan de toiture
 
  CADRE PÉRIPHÉRIQUE :
    → Poutre périmétrique à la tête ou pied de façade
    → Labels : "UPN200", "CADRE PERIF.", "IPE270"
    → Trouvé dans : plan de toiture, vues pignon
 
  FIXATIONS & TIGES D'ANCRAGE :
    → Tiges filetées à la base des poteaux
    → Labels : "02 Tiges M24 CL8.8", "Tige ROND 24", "4ø20 L=600"
    → Longueur = explicitement indiquée "L=600mm" — sinon null
    → Trouvé dans : coupes pied de poteau (K, L, M...), détail platine
 
  ÉLÉMENTS DE BARDAGE :
    → TUBE-C (tubes carrés) : "TUBE CARRE 40*2", "TC 60*60*3" → extraire
    → NERVESCO / TÔLE NERVURÉE → NE PAS extraire (surface, pas linéaire)
    → Collier galvanisé, visserie → NE PAS extraire (quincaillerie)
 
  Règle de visibilité :
    Label ET élément clairement visibles   → extraire, confidence selon certitude
    Label visible, élément peu clair       → extraire, confidence < 0.65
    Élément visible, AUCUN label           → NE PAS inventer, ajouter aux warnings
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 5 — CE QUI NE PEUT PAS ÊTRE EXTRAIT (à signaler)              ║
╚══════════════════════════════════════════════════════════════════════╝
 
NE PAS tenter de calculer — mettre dans requires_manual_input :
  - Platines (TN) : extraire le label, mettre length_mm=null, calculé par l'app
  - Goussets : formes irrégulières, dimensions depuis les coupes détaillées
  - Boulonnerie : forfait 5% du total ossature — calculé automatiquement par l'app
  - Tiges d'ancrage : si non trouvées dans les coupes visibles
 
╔══════════════════════════════════════════════════════════════════════╗
║  ÉTAPE 6 — CONTRÔLE ANTI-ERREUR (CRITIQUE)                           ║
╚══════════════════════════════════════════════════════════════════════╝
 
  RÈGLE 6.1 — NE PAS CONFONDRE ENTRAXE ET LONGUEUR DE PIÈCE
    "Entraxe 5960" = distance entre poteaux ≠ longueur d'une panne
    Une panne sur 5960mm peut être faite de pièces de 4100 + 2000mm
    → length_mm = UNIQUEMENT si une cote est sur la pièce elle-même
    → Sinon : length_mm = null, length_source = "null — no explicit cut length"
    → JAMAIS calculer depuis l'entraxe ou la portée du bâtiment
 
  RÈGLE 6.2 — NE PAS INVENTER LES QUANTITÉS
    Compter uniquement les éléments individuellement visibles.
    Si une vue montre une travée typique avec note "idem File 2 à 7" :
    → Mettre quantity = ce qui est visible
    → Ajouter dans quantity_note : "×N travées — à multiplier par l'ingénieur"
    JAMAIS multiplier silencieusement.
 
  RÈGLE 6.3 — NE PAS HALLUCINER PAR CONTEXTE
    Si tu sais que ce type de bâtiment a normalement des IPE180 mais
    que tu ne vois pas d'annotation IPE180 → NE PAS l'ajouter
    → Mettre dans warnings : "Pannes visibles mais désignation illisible
      — probablement IPE140 ou IPE180, à confirmer par l'ingénieur"
 
  RÈGLE 6.4 — CONFIANCE = VISIBILITÉ RÉELLE
    confidence 0.90–1.00 : annotation lisible, quantité comptable, longueur explicite
    confidence 0.70–0.89 : annotation lisible mais quantité ou longueur inférée
    confidence 0.50–0.69 : annotation partiellement lisible ou type inféré visuellement
    confidence < 0.50    : NE PAS inclure → mettre dans warnings
 
  RÈGLE 6.5 — UN ENREGISTREMENT PAR TYPE DE PIÈCE COUPÉE
    IPE400 en POTEAU (h=4000mm) ≠ IPE400 en TRAVERSE (L=5960mm)
    → Deux entrées séparées avec nomenclature et length_mm différents
 
  RÈGLE 6.6 — VÉRIFICATION FINALE AVANT SORTIE
    Avant de générer le JSON, vérifier :
    □ Aucun profilé oublié (scanner toutes les zones une dernière fois)
    □ Aucun profilé compté deux fois (vérifier les repères et vues)
    □ Cohérence plan / coupe / détail / nomenclature
    □ Tous les length_mm null sont justifiés dans length_source
    □ Liste certains / probables / à valider est complète
 
╔══════════════════════════════════════════════════════════════════════╗
║  TABLE DE RÉFÉRENCE — MASSE LINÉAIRE (kg/m)                          ║
╚══════════════════════════════════════════════════════════════════════╝
 
IPE: 80→6.0, 100→8.1, 120→10.4, 140→12.9, 160→15.8, 180→18.8,
     200→22.4, 220→26.2, 240→30.7, 270→36.1, 300→42.2, 330→49.1,
     360→57.1, 400→66.3, 450→77.6, 500→90.7, 550→106, 600→122
 
HEA: 100→16.7, 120→19.9, 140→24.7, 160→30.4, 180→35.5, 200→42.3,
     220→50.5, 240→60.3, 260→68.2, 280→76.4, 300→88.3, 320→97.6,
     340→105, 360→112, 400→125
 
HEB: 100→20.4, 120→26.7, 140→33.7, 160→42.6, 180→51.2, 200→61.3,
     220→71.5, 240→83.2, 260→93.0, 280→103, 300→117, 320→127
 
UPN: 80→8.70, 100→10.6, 120→13.4, 140→16.0, 160→18.8, 180→22.0,
     200→25.3, 220→29.4, 240→33.2, 260→37.9, 280→41.8, 300→46.2
 
Cornières égales (L):
     L50*50*5→3.77, L60*60*6→5.42, L70*70*7→7.38,
     L80*80*8→9.63, L100*100*10→15.0
 
Ronds (D/ø): ø12→0.888, ø14→1.21, ø16→1.58, ø20→2.47, ø24→3.55
 
Tubes carrés:
     40*40*2→2.31, 40*40*3→3.41, 50*50*3→4.35, 60*60*4→6.97,
     80*80*4→9.41, 100*100*5→14.7
 
╔══════════════════════════════════════════════════════════════════════╗
║  FORMAT DE SORTIE — JSON UNIQUEMENT                                   ║
╚══════════════════════════════════════════════════════════════════════╝
 
{
  "scale_detected": "1:70",
  "scale_ratio": 70,
  "scale_confidence": 0.92,
  "drawing_type": "mixed | plan de toiture | élévation long-pan | coupe",
  "steel_grade": "S275JR",
 
  "views_identified": [
    {"type": "plan de toiture",       "zone": "haut-gauche"},
    {"type": "élévation long-pan",    "zone": "bas-gauche"},
    {"type": "élévation pignon",      "zone": "haut-droite"},
    {"type": "coupe PP",              "zone": "centre-droite"},
    {"type": "détail assemblage",     "zone": "bas-droite — ignoré pour extraction"}
  ],
 
  "profiles": [
    {
      "id": "P001",
      "repere": "P1",
      "nomenclature": "POTEAU",
      "category": "ossature_principale",
      "type": "IPE",
      "designation": "IPE400",
      "length_mm": 4000,
      "length_source": "explicit_dimension",
      "quantity": 14,
      "quantity_note": null,
      "views_confirmed": ["élévation long-pan", "coupe PP"],
      "zone": "File 1 à 7 — long-pan",
      "masse_lineaire_kg_m": 66.3,
      "poids_unitaire_kg": 265.2,
      "poids_total_kg": 3712.8,
      "confidence": 0.92,
      "visual_cue": "rectangles verticaux annotés IPE400, confirmés en coupe PP",
      "detail_associe": "Dét.K — pied de poteau"
    },
    {
      "id": "P002",
      "repere": "JR1",
      "nomenclature": "JARRET",
      "category": "ossature_secondaire",
      "type": "IPE",
      "designation": "IPE400",
      "length_mm": null,
      "length_source": "null — no explicit cut length on drawing",
      "quantity": 14,
      "quantity_note": "2 jarrets par portique × 7 portiques",
      "views_confirmed": ["élévation long-pan"],
      "zone": "jonction poteau/traverse — long-pan",
      "masse_lineaire_kg_m": 66.3,
      "poids_unitaire_kg": null,
      "poids_total_kg": null,
      "confidence": 0.75,
      "visual_cue": "élément tronqué en biseau annoté JARRET IPE400",
      "detail_associe": "Coupe J — jarret"
    }
  ],
 
  "verification": {
    "certains": ["POTEAU IPE400", "TRAVERSE IPE400", "SABLIERE HEA120"],
    "probables": ["PANNE IPE140 — annotation partiellement lisible"],
    "a_valider": ["LIERNE D14 — quantité incertaine, résolution insuffisante"]
  },
 
  "requires_manual_input": [
    "platines — formule t×L×l×7.85 depuis les détails",
    "goussets — formes irrégulières, lire depuis coupes",
    "boulonnerie_5pct — l'app applique 5% sur total ossature",
    "tiges_ancrage — non visibles dans cette vue"
  ],
 
  "auto_calculated": {
    "boulonnerie_forfait_pct": 5,
    "note": "App applique : total_ossature_kg × 0.05"
  },
 
  "unreadable_zones": [
    "détail assemblage pied de poteau — trop dense à cette résolution"
  ],
 
  "warnings": [
    "TRAVERSE IPE450 détectée — length_mm null car aucune cote sur la pièce",
    "UPN80 lisses visibles en pignon — quantité non comptable à cette résolution"
  ],
 
  "skipped_elements": [
    "NERVESCO tôle — élément surfacique, exclu",
    "Collier galvanisé — quincaillerie, exclu"
  ],
 
  "estimated_completeness_pct": 70,
  "pages_analyzed": 1,
  "provider": "gemini-1.5-pro"
}
 
RÈGLES ABSOLUES :
- Retourner UNIQUEMENT le JSON. Zéro prose. Zéro markdown. Zéro backticks.
- length_mm = null si aucune cote explicite sur la pièce — JAMAIS estimer depuis entraxe
- confidence < 0.50 → NE PAS inclure → mettre dans warnings
- poids_unitaire_kg et poids_total_kg = null si length_mm = null
- quantity_note obligatoire si la quantité est inférée ou multipliée
- views_confirmed : minimum 2 vues sauf si une seule est disponible sur le plan
"""


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class DetectedProfile:
    id: str
    type: str
    designation: str
    role: str
    length_m: float | None
    quantity: int
    zone: str
    confidence: float
    bbox_normalized: list[float] = field(default_factory=list)


@dataclass
class VisionResult:
    scale_detected: str | None
    scale_confidence: float
    profiles: list[DetectedProfile]
    unreadable_zones: list[str]
    warnings: list[str]
    drawing_type: str
    raw_response: str
    provider_used: str
    page_number: int = 1
    tile_index: int | None = None

    @property
    def high_confidence_profiles(self) -> list[DetectedProfile]:
        return [p for p in self.profiles if p.confidence >= 0.7]

    @property
    def needs_review(self) -> list[DetectedProfile]:
        return [p for p in self.profiles if p.confidence < 0.7]


# ---------------------------------------------------------------------------
# Provider enum
# ---------------------------------------------------------------------------

class VisionProvider(str, Enum):
    GEMINI = "gemini"
    CLAUDE = "claude"


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------

class VisionLLMEngine:
    """
    Detects steel profiles in structural drawing images using vision LLMs.

    Usage:
        engine = VisionLLMEngine()
        result = engine.analyze(pil_image, page_number=1)
        print(result.profiles)
    """

    def __init__(
        self,
        provider: VisionProvider | str | None = None,
        fallback: bool = True,
    ):
        env_provider = os.getenv("VISION_PROVIDER", "claude").lower()
        self.primary = VisionProvider(provider or env_provider)
        self.fallback_enabled = fallback
        self.fallback_provider = (
            VisionProvider.CLAUDE if self.primary == VisionProvider.GEMINI
            else VisionProvider.GEMINI
        )
        logger.info(f"VisionLLMEngine: primary={self.primary}, fallback={self.fallback_provider if fallback else 'disabled'}")

    def analyze(
        self,
        image: Image.Image,
        page_number: int = 1,
        tile_index: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> VisionResult:
        """
        Send an image to the vision model and return structured detections.

        context: optional metadata {"project": "...", "ref": "...", "scale_hint": "1:50"}
        """
        context = context or {}
        user_msg = self._build_user_message(context)

        try:
            raw = self._call_provider(self.primary, image, user_msg)
            provider_used = self.primary.value
        except Exception as e:
            logger.warning(f"Primary provider {self.primary} failed: {e}")
            if not self.fallback_enabled:
                raise
            logger.info(f"Falling back to {self.fallback_provider}")
            raw = self._call_provider(self.fallback_provider, image, user_msg)
            provider_used = self.fallback_provider.value

        return self._parse_response(raw, provider_used, page_number, tile_index)

    # ------------------------------------------------------------------
    # Provider dispatch
    # ------------------------------------------------------------------

    def _call_provider(
        self,
        provider: VisionProvider,
        image: Image.Image,
        user_message: str,
    ) -> str:
        if provider == VisionProvider.CLAUDE:
            return self._call_claude(image, user_message)
        elif provider == VisionProvider.GEMINI:
            return self._call_gemini(image, user_message)
        raise ValueError(f"Unknown provider: {provider}")

    # ------------------------------------------------------------------
    # Claude (Anthropic)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_claude(self, image: Image.Image, user_message: str) -> str:
        import anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError("ANTHROPIC_API_KEY not set")

        client = anthropic.Anthropic(api_key=api_key)
        img_b64 = _pil_to_base64(image)

        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=4000,
            temperature=0.0,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_b64,
                            },
                        },
                        {"type": "text", "text": user_message},
                    ],
                }
            ],
        )
        return response.content[0].text

    # ------------------------------------------------------------------
    # Gemini (Google)
    # ------------------------------------------------------------------

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _call_gemini(self, image: Image.Image, user_message: str) -> str:
        import requests
        import io
        import base64
        from engines.api_keys import get_random_gemini_key

        api_key = get_random_gemini_key()

        logger.info("Converting image to JPEG for Gemini API...")
        buf = io.BytesIO()
        if image.mode in ('RGBA', 'P'):
            image = image.convert('RGB')
        image.save(buf, format="JPEG", quality=80)
        b64_data = base64.b64encode(buf.getvalue()).decode("utf-8")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"
        
        payload = {
            "contents": [{
                "parts": [
                    {"text": user_message},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_data
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "responseMimeType": "application/json"
            },
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT}]
            }
        }

        logger.info("Sending request to Gemini API (raw REST)...")
        resp = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=120)
        
        if not resp.ok:
            logger.error(f"Gemini API failed: {resp.status_code} {resp.text}")
            resp.raise_for_status()

        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_response(
        self,
        raw: str,
        provider_used: str,
        page_number: int,
        tile_index: int | None,
    ) -> VisionResult:
        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {e}\nRaw: {raw[:500]}")
            return VisionResult(
                scale_detected=None,
                scale_confidence=0.0,
                profiles=[],
                unreadable_zones=["entire page — JSON parse failed"],
                warnings=[f"JSON parse error: {e}"],
                drawing_type="unknown",
                raw_response=raw,
                provider_used=provider_used,
                page_number=page_number,
                tile_index=tile_index,
            )

        profiles = []
        for i, p in enumerate(data.get("profiles", [])):
            length_m = p.get("length_m")
            if length_m is None and p.get("length_mm") is not None:
                try:
                    length_m = float(p.get("length_mm")) / 1000.0
                except (ValueError, TypeError):
                    length_m = None
                    
            profiles.append(
                DetectedProfile(
                    id=p.get("id", f"P{i:03d}"),
                    type=p.get("type", "unknown"),
                    designation=p.get("designation", ""),
                    role=p.get("nomenclature", p.get("role", "")),
                    length_m=length_m,
                    quantity=int(p.get("quantity", 1)) if str(p.get("quantity", 1)).isdigit() else 1,
                    zone=p.get("zone", ""),
                    confidence=float(p.get("confidence", 0.5)),
                    bbox_normalized=p.get("bbox_normalized", []),
                )
            )

        return VisionResult(
            scale_detected=data.get("scale_detected"),
            scale_confidence=float(data.get("scale_confidence", 0.0)),
            profiles=profiles,
            unreadable_zones=data.get("unreadable_zones", []),
            warnings=data.get("warnings", []),
            drawing_type=data.get("drawing_type", "unknown"),
            raw_response=raw,
            provider_used=provider_used,
            page_number=page_number,
            tile_index=tile_index,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_user_message(context: dict) -> str:
        lines = ["Analyze this structural steel drawing."]
        if context:
            lines.append("\nContext:")
            if "project" in context:
                lines.append(f"- Project: {context['project']}")
            if "ref" in context:
                lines.append(f"- Drawing ref: {context['ref']}")
            if "scale_hint" in context:
                lines.append(f"- Expected scale (from metadata): {context['scale_hint']}")
            if "drawing_type" in context:
                lines.append(f"- Drawing type: {context['drawing_type']}")
        lines.append("\nExtract all visible steel profiles and return the JSON format specified. Nothing else.")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Merging tiles
# ---------------------------------------------------------------------------

def merge_tile_results(results: list[VisionResult]) -> VisionResult:
    """
    Consolidate results from multiple tiles of the same page.
    Deduplicates profiles by designation + zone, keeps highest confidence.
    """
    if not results:
        raise ValueError("No results to merge")
    if len(results) == 1:
        return results[0]

    # Use scale from the tile with highest scale_confidence
    best_scale = max(results, key=lambda r: r.scale_confidence)

    all_profiles: list[DetectedProfile] = []
    seen: dict[str, DetectedProfile] = {}

    for result in results:
        for profile in result.profiles:
            key = f"{profile.designation}|{profile.zone}"
            if key not in seen or profile.confidence > seen[key].confidence:
                seen[key] = profile

    all_profiles = list(seen.values())

    all_warnings = []
    all_unreadable = []
    for r in results:
        all_warnings.extend(r.warnings)
        all_unreadable.extend(r.unreadable_zones)

    return VisionResult(
        scale_detected=best_scale.scale_detected,
        scale_confidence=best_scale.scale_confidence,
        profiles=all_profiles,
        unreadable_zones=list(set(all_unreadable)),
        warnings=list(set(all_warnings)),
        drawing_type=results[0].drawing_type,
        raw_response="[merged from tiles]",
        provider_used=results[0].provider_used,
        page_number=results[0].page_number,
        tile_index=None,
    )


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------

def _pil_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.standard_b64encode(buf.getvalue()).decode("utf-8")
