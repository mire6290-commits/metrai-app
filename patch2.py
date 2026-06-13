import re

with open('backend/engines/text_llm_engine.py', 'r', encoding='utf-8') as f:
    content = f.read()

def patch_profiles(match):
    return '''                    profiles.append(DetectedProfile(
                        repere=p.get("repere") or p.get("id", "P000"),
                        category=p.get("category", p.get("type", "unknown")),
                        designation=p.get("designation", ""),
                        role=p.get("role", ""),
                        length_m=p.get("length_m"),
                        length_source=p.get("length_source", ""),
                        dims_mm=p.get("dims_mm"),
                        quantity=int(p.get("quantity") or 1),
                        quantity_note=p.get("quantity_note", ""),
                        poids_lineaire_kg_m=p.get("poids_lineaire_kg_m"),
                        poids_total_kg=p.get("poids_total_kg"),
                        views_confirmed=p.get("views_confirmed", []),
                        detail_ref=p.get("detail_ref"),
                        notes=p.get("notes"),
                        confidence=float(p.get("confidence", 0.8)),
                        bbox_normalized=p.get("bbox_normalized", [])
                    ))'''

content = re.sub(r'                    profiles\.append\(DetectedProfile\([\s\S]*?bbox_normalized=p\.get\("bbox_normalized", \[\]\)\n                    \)\)', patch_profiles, content)

def patch_visionresult(match):
    return '''            verif = data.get("verification", {})
            warns = []
            if isinstance(verif, dict):
                for w in verif.get("warnings", []):
                    if isinstance(w, dict):
                        warns.append(f"{w.get('code', '')}: {w.get('message', '')} ({w.get('affected_repere', '')})")
                    else:
                        warns.append(str(w))
            else:
                warns = data.get("warnings", [])

            return VisionResult(
                scale_detected=data.get("scale_detected"),
                scale_confidence=float(data.get("scale_confidence", 0.0)),
                building_dimensions=data.get("building_dimensions"),
                profiles=profiles,
                verification=data.get("verification"),
                summary=data.get("summary"),
                raw_response=raw_json,
                provider_used=self.provider
            )'''

content = re.sub(r'            return VisionResult\([\s\S]*?raw_response=raw_json\n            \)', patch_visionresult, content)

with open('backend/engines/text_llm_engine.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched text_llm_engine.py successfully!')
