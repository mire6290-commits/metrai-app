import re
from typing import List, Dict, Any

class AIEngine:
    def __init__(self):
        # Profilés supportés: IPE, HEA, HEB, HEM, UPN, UPE, IPN, COR (Cornières), etc.
        self.profil_regex = re.compile(
            r'\b(?P<profil>(?:IPE|HEA|HEB|HEM|UPN|UPE|IPN|COR)\s*\d+(?:\s*[xX]\s*\d+(?:\s*[xX]\s*\d+)?)?)\b',
            re.IGNORECASE
        )
        # Repère (ex: F01, P12, C03, S05, R10)
        self.repere_regex = re.compile(
            r'\b(?P<repere>[A-Z]\d{2,3})\b',
            re.IGNORECASE
        )
        # Longueur (ex: L=6250, L=6.25, L 6250, L: 6250)
        self.longueur_regex = re.compile(
            r'\bL\s*(?:=|\:|)\s*(?P<longueur>\d+(?:[\.,]\d+)?)\s*(?:mm|m)?\b',
            re.IGNORECASE
        )
        # Quantité (ex: x2, 2x, Qte: 2, Qty: 2, 2 U, (2))
        self.qty_regexes = [
            re.compile(r'\b(?:QTÉ|QTE|QTY|QUANTITE|QUANTITÉ)\s*(?::|=|\s)\s*(?P<qty>\d+)\b', re.IGNORECASE),
            re.compile(r'\bx\s*(?P<qty>\d+)\b', re.IGNORECASE),
            re.compile(r'\b(?P<qty>\d+)\s*x\b', re.IGNORECASE),
            re.compile(r'\((?P<qty>\d+)\)'),
        ]

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Analyse le texte extrait et retourne une liste d'entités structurées.
        Applique des règles métier intelligentes pour détecter les profilés, longueurs,
        repères, quantités et éventuels assemblages.
        """
        results = []
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 1. Recherche du profilé
            profil_match = self.profil_regex.search(line)
            if not profil_match:
                continue # Si pas de profilé, ce n'est probablement pas une ligne de métré utile
                
            profil = profil_match.group('profil').replace(" ", "").upper()
            
            # 2. Recherche du repère
            repere_match = self.repere_regex.search(line)
            repere = repere_match.group('repere').upper() if repere_match else "N/A"
            
            # 3. Recherche de la longueur
            longueur_match = self.longueur_regex.search(line)
            longueur = 0.0
            if longueur_match:
                lon_str = longueur_match.group('longueur').replace(",", ".")
                try:
                    longueur = float(lon_str)
                    # Règle métier : si la longueur est < 100, c'est probablement exprimé en mètres (ex: 6.25)
                    # On convertit en mm (standard en charpente métallique)
                    if longueur < 100.0:
                        longueur = longueur * 1000.0
                except ValueError:
                    pass
            
            # Si pas de longueur explicite via "L=", on cherche un nombre à 4 chiffres après le profilé
            if longueur == 0.0:
                fallback_longueur = re.search(r'\b' + re.escape(profil_match.group('profil')) + r'\s+(?P<longueur>\d{3,5})\b', line, re.IGNORECASE)
                if fallback_longueur:
                    try:
                        longueur = float(fallback_longueur.group('longueur'))
                    except ValueError:
                        pass
                        
            # 4. Recherche de la quantité
            quantite = 1
            for regex in self.qty_regexes:
                qty_match = regex.search(line)
                if qty_match:
                    try:
                        quantite = int(qty_match.group('qty'))
                        break # Premier match trouvé
                    except ValueError:
                        pass
            
            # 5. Détection des assemblages simples / remarques
            assemblage = "Boulonné" # Standard par défaut
            if any(kw in line.lower() for kw in ["platine", "gousset", "soudé", "welded", "soudure"]):
                assemblage = "Soudé (avec platine)"
            elif "gousset" in line.lower():
                assemblage = "Gousset d'attache"
                
            results.append({
                "repere": repere,
                "profil": profil,
                "longueur": longueur,
                "quantite": quantite,
                "assemblage": assemblage
            })
            
        return results

    def extract_text_ocr(self, filepath: str) -> str:
        """
        Méthode conservée pour compatibilité mais l'OCR est maintenant géré de façon
        plus élégante et intégrée au niveau de PDFParser.
        """
        from engines.pdf_parser import PDFParser
        parser = PDFParser()
        return parser.extract_text(filepath)
