import re

file_path = 'backend/main.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# For extract
extract_replacement = '''                # 3-PASS Agentic Zoning Architecture
                logger.info(f"Applying 3-Pass Architecture for page {page_img.page_number}...")
                
                # --- PASS 1: Main Structure (Full Page) ---
                logger.info(f"Executing PASS 1 on full page...")
                ctx1 = context.copy()
                ctx1["zone_type"] = "full_page"
                res1 = _vision.analyze(page_img.image, page_number=page_img.page_number, tile_index=0, context=ctx1, pass_mode="PASS1")
                
                # --- PASS 2: Accessories (Quadrants) ---
                zones = [
                    {"zone_type": "quadrant_top_left", "bbox_normalized": [0.0, 0.0, 0.55, 0.55]},
                    {"zone_type": "quadrant_top_right", "bbox_normalized": [0.0, 0.45, 0.55, 1.0]},
                    {"zone_type": "quadrant_bottom_left", "bbox_normalized": [0.45, 0.0, 1.0, 0.55]},
                    {"zone_type": "quadrant_bottom_right", "bbox_normalized": [0.45, 0.45, 1.0, 1.0]},
                ]
                
                pass2_jsons = []
                img_w, img_h = page_img.image.size
                
                for z_idx, zone in enumerate(zones):
                    zt = zone.get("zone_type", "unknown")
                    y_min, x_min, y_max, x_max = zone.get("bbox_normalized", [0.0, 0.0, 1.0, 1.0])
                    
                    left, right = min(x_min, x_max) * img_w, max(x_min, x_max) * img_w
                    top, bottom = min(y_min, y_max) * img_h, max(y_min, y_max) * img_h
                    
                    padding_x, padding_y = int(img_w * 0.05), int(img_h * 0.05)
                    box_px = (
                        max(0, int(left) - padding_x), max(0, int(top) - padding_y),
                        min(img_w, int(right) + padding_x), min(img_h, int(bottom) + padding_y)
                    )
                    
                    logger.info(f"Executing PASS 2 on {zt}...")
                    crop_img = page_img.image.crop(box_px)
                    ctx2 = context.copy()
                    ctx2["zone_type"] = zt
                    
                    await asyncio.sleep(4.5) # Prevent rate limits
                    res2 = _vision.analyze(crop_img, page_number=page_img.page_number, tile_index=z_idx+1, context=ctx2, pass_mode="PASS2")
                    pass2_jsons.append(res2.raw_response)
                
                # --- PASS 3: Merge & Deduplicate ---
                logger.info(f"Executing PASS 3 (Merge & Deduplicate) for page {page_img.page_number}...")
                pass3_payload = f"PASS1_JSON:\\n{res1.raw_response}\\n\\nPASS2_JSONS:\\n{'\\n---\\n'.join(pass2_jsons)}"
                
                ctx3 = context.copy()
                ctx3["zone_type"] = "merge"
                
                try:
                    await asyncio.sleep(4.5)
                    merged_res = _text_llm.analyze(pass3_payload, context=ctx3, pass_mode="PASS3")
                    all_results.append(merged_res)
                except Exception as e:
                    logger.error(f"PASS 3 Failed: {e}. Falling back to Python merge.")
                    # Fallback to Python merge if PASS 3 fails
                    zone_results = [res1]
                    # We don't have the parsed pass2 objects here easily, so we just use res1
                    all_results.append(res1)
'''

content = re.sub(
    r'                # Pass 1: Mathematical Grid Tiling \(Full Page \+ 4 Quadrants\)[\s\S]*?if zone_results:\n                    merged = merge_tile_results\(zone_results\)\n                    all_results\.append\(merged\)',
    extract_replacement,
    content
)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Patched main.py successfully.")
