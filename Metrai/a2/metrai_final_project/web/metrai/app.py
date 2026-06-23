import os
import sys
import subprocess
import time

# --- FIX WORKING DIRECTORY ---
current_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(current_dir)

# --- PASSENGER INTERFACE ---
def application(environ, start_response):
    # Redirection direct vers Streamlit pour éviter les erreurs de path 404
    status = '302 Found'
    response_headers = [('Location', '[http://3rdeyephotographs.com:8501/](http://3rdeyephotographs.com:8501/)')]
    start_response(status, response_headers)
    return [b"Redirecting to Metrai AI..."]

# --- START STREAMLIT ---
try:
    # On lance Streamlit sur le port 8501
    subprocess.Popen([
        "streamlit", "run", "main_logic.py", 
        "--server.port", "8501", 
        "--server.address", "0.0.0.0", 
        "--server.headless", "true",
        "--server.enableCORS", "false",
        "--server.enableXsrfProtection", "false"
    ])
except Exception as e:
    with open("error_log.txt", "a") as f:
        f.write(f"Error: {str(e)}\n")
