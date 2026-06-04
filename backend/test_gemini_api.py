import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv("C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/backend/.env")

api_key = os.getenv("GEMINI_API_KEY")
print(f"Key loaded: {api_key[:5]}...{api_key[-5:]}")
genai.configure(api_key=api_key)

try:
    print("Testing gemini-1.5-pro...")
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content("Say Hello")
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
