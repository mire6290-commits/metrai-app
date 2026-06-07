import re

with open('backend/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

def patch_enrich(match):
    return '''    out = ProfileOut(
        id=getattr(p, 'repere', None) or getattr(p, 'id', 'P00'),
        designation=designation, # Return the formatted one
        type=getattr(p, 'category', getattr(p, 'type', 'unknown')),
        role=getattr(p, 'role', ''),
        length_m=length_val,
        quantity=qty_val,
        zone=getattr(p, 'zone', getattr(p, 'views_confirmed', [''])[0] if getattr(p, 'views_confirmed', None) else ''),
        confidence=p.confidence,
        masse_lineaire_kg_m=masse,
        poids_unitaire=poids_unitaire,
        poids_total_kg=poids,
        surface_peinture_m2=surface_peinture,
    )'''

content = re.sub(r'    out = ProfileOut\([\s\S]*?surface_peinture_m2=surface_peinture,\n    \)', patch_enrich, content)

with open('backend/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Patched main.py successfully!')
