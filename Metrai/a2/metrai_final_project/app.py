import os
import io
import pandas as pd
import requests
import re
from flask import Flask, render_template, request, send_file
import pdfplumber

app = Flask(__name__)

# Config dyal folders
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# API Key dyal Mistral
API_KEY = "Cb5KKORadtIzkd9ZilvY1FOWy3oX2lZR"

def clean_csv_content(raw_content):
    """
    Hadi katakhod l-content li raj3 mn AI o katjbd mno ghir l-جدول (CSV).
    Katqleb bin ```csv o ``` bach t7yed ay ktaba zayda.
    """
    # Fix: Added the complete regex pattern and closed the function properly
    match = re.search(r"