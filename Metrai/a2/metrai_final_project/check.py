import requests
API_KEY = "hona_dir_l_key_dyalk"
res = requests.get("https://api.mistral.ai/v1/models", headers={"Authorization": f"Bearer {API_KEY}"})
print(f"Status: {res.status_code}") # Ila 200 = ✅ | Ila 401 = ❌