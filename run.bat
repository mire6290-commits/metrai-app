@echo off
echo Starting Metrai Backend (FastAPI)...
start "Metrai Backend" cmd /k "cd backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000"

echo Waiting for backend to start...
timeout /t 3 /nobreak > NUL

echo Starting Metrai Frontend (Streamlit)...
start "Metrai Frontend" cmd /k "python -m streamlit run app.py"

echo All services started! Close the terminal windows to stop the servers.
