from typing import List, Dict, Any

class RulesDB:
    def __init__(self):
        # Base de données simple des poids linéiques (kg/m) et surfaces de peinture (m²/m)
        # Chaque profil contient une liste : [poids_kg_m, surface_m2_m]
        self.profiles_db = {
            # IPE
            "IPE100": [8.1, 0.40],
            "IPE120": [10.4, 0.47],
            "IPE140": [12.9, 0.55],
            "IPE160": [15.8, 0.62],
            "IPE180": [18.8, 0.70],
            "IPE200": [22.4, 0.77],
            "IPE220": [26.2, 0.85],
            "IPE240": [30.7, 0.92],
            "IPE270": [36.1, 1.04],
            "IPE300": [42.2, 1.16],
            "IPE330": [49.1, 1.25],
            "IPE360": [57.1, 1.35],
            "IPE400": [66.3, 1.47],
            # HEA
            "HEA100": [16.7, 0.56],
            "HEA120": [19.9, 0.68],
            "HEA140": [24.7, 0.80],
            "HEA160": [30.4, 0.92],
            "HEA180": [35.5, 1.04],
            "HEA200": [42.3, 1.15],
            "HEA220": [50.5, 1.26],
            "HEA240": [60.3, 1.37],
            # HEB
            "HEB100": [20.4, 0.57],
            "HEB120": [26.7, 0.69],
            "HEB140": [33.7, 0.81],
            "HEB160": [42.6, 0.93],
            "HEB180": [51.2, 1.05],
            "HEB200": [61.3, 1.17],
            "HEB220": [71.5, 1.28],
            "HEB240": [83.2, 1.40],
            # UPN
            "UPN100": [10.6, 0.37],
            "UPN120": [13.4, 0.44],
            "UPN140": [16.0, 0.50],
            "UPN160": [18.8, 0.57],
            "UPN200": [25.3, 0.70],
            # Cornières (COR) standards
            "COR50X50X5": [3.77, 0.20],
            "COR60X60X6": [5.42, 0.24],
            "COR70X70X7": [7.38, 0.28],
            "COR80X80X8": [9.66, 0.32],
            "COR100X100X10": [15.10, 0.40]
        }

    def get_profile_data(self, profil: str) -> tuple:
        """Retourne le (poids, surface_peinture) au mètre pour un profil donné, ou (0.0, 0.0) si inconnu"""
        # Nettoyage supplémentaire pour matcher les clés (ex: COR 50x50x5 -> COR50X50X5)
        clean_profil = profil.replace(" ", "").upper()
        return self.profiles_db.get(clean_profil, [0.0, 0.0])

    def enrich_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Prend la liste d'éléments extraits et calcule les poids théoriques et les surfaces de peinture.
        - Poids = (Longueur en mm) / 1000 * Poids Linéique * Quantité
        - Surface Peinture = (Longueur en mm) / 1000 * Surface Linéique * Quantité
        """
        enriched = []
        for i, item in enumerate(data):
            profil = item.get("profil", "")
            longueur_mm = item.get("longueur", 0.0)
            quantite = item.get("quantite", 1)
            
            poids_lineique, surface_lineique = self.get_profile_data(profil)
            
            # Si le profilé est inconnu mais que la chaîne ressemble à un profilé, on donne des estimations minimales
            if poids_lineique == 0.0 and len(profil) > 3:
                # Approximation basée sur les chiffres dans le nom (ex: IPE150 -> approx 15 kg/m)
                nums = re.findall(r'\d+', profil)
                if nums:
                    approx_size = int(nums[0])
                    poids_lineique = approx_size * 0.15 # IPE300 -> 45
                    surface_lineique = approx_size * 0.0035 # IPE300 -> 1.05
            
            poids_unitaire = (longueur_mm / 1000.0) * poids_lineique
            poids_total = poids_unitaire * quantite
            
            surface_unitaire = (longueur_mm / 1000.0) * surface_lineique
            surface_total = surface_unitaire * quantite
            
            # Créer le nouvel item
            new_item = item.copy()
            new_item["id"] = i + 1 # Assurer un ID unique pour le tableau frontend
            new_item["poids_lineique"] = poids_lineique
            new_item["poids_unitaire"] = round(poids_unitaire, 2)
            new_item["poids_total"] = round(poids_total, 2)
            new_item["surface_lineique"] = surface_lineique
            new_item["surface_unitaire"] = round(surface_unitaire, 2)
            new_item["surface_total"] = round(surface_total, 2)
            
            enriched.append(new_item)
            
        return enriched
