import os
import sys
from PIL import Image
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv("C:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/backend/.env")
api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

print("Creating a dummy image...")
img = Image.new('RGB', (100, 100), color = 'red')

print("Sending to Gemini...")
model = genai.GenerativeModel("gemini-2.5-flash")
try:
    response = model.generate_content(["What color is this image?", img])
    print(response.text)
except Exception as e:
    print(f"Error: {e}")
