# Metrai Calculus - Self-Hosted Mathematics & AI Engine Platform

Welcome to **Metrai Calculus**, an ultra-premium, full-stack, production-ready mathematical resolution platform and local AI-style assistant built with Python, FastAPI, and Jinja templates. 

Everything runs completely locally on your server without expensive third-party paid API keys (such as OpenAI, Gemini, or Claude). 

---

## 🚀 Key Feature Workspaces

1. **AI Math Solver & Calculator**: Tab-based advanced environment supporting general scientific calculations, polynomial equations solving, algebraic simplifications, derivatives, indefinite/definite integrals with boundaries, limit points, and statistics.
2. **Matrix Algebra**: Add, subtract, multiply, transpose, determine invertibility, and calculate eigenvalues.
3. **Interactive Graphing**: Plots fluid 2D Cartesian curves ($y = f(x)$) and beautiful 3D spatial surfaces ($z = f(x, y)$) in dark glassmorphic layouts powered by Plotly, with base64 static fallback support for downloads and printing.
4. **Local Mathematical OCR**: Drag & drop equation photos or draw equations directly using your mouse/stylus on the HTML5 sketch board. The Otsu-preprocessor and Tesseract OCR engine convert images into editable mathematical terms and solve them in real-time.
5. **Secure Authentication & Workspace Dashboards**: Encrypted JWT authentication stored in secure HTTP-Only session cookies. Custom workspace history dashboard with calculation bookmarking (pinning), and administrative support ticket submissions.
6. **Telemetry Admin Panel**: System administration dashboard containing server telemetry histograms, user registrars suspension controls, and open ticket support resolving.

---

## 📁 File Structure

```text
aaa/awrb/
│
├── app/
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py          # API Auth, registration, reset flow
│   │   ├── math.py          # REST endpoints for algebra, calculus, matrices, stats
│   │   ├── ocr.py           # OpenCV Otsu image parsing & solve automation
│   │   ├── dashboard.py     # Bookmark pins, support ticket submission
│   │   ├── admin.py         # System telemetry, audit logging, user edits
│   │   └── views.py         # Jinja HTML views pre-renderer
│   │
│   ├── static/
│   │   └── css/
│   │       └── style.css    # Curated HSL Dark-theme & Glassmorphism styles
│   │
│   ├── templates/
│   │   ├── base.html        # Shared structure with Plotly, KaTeX and toaster notifications
│   │   ├── home.html        # Stunning landing page with live miniature sandbox
│   │   ├── login.html       # Sign-in panel
│   │   ├── register.html    # Member signup panel (Primary Admin bootstrap)
│   │   ├── dashboard.html   # Workspace dashboard, pins, modals solution details
│   │   ├── calculator.html  # Interactive math tabs solvers and graphing
│   │   ├── ocr.html         # Image snapshots OCR & HTML5 Sketch board solver
│   │   ├── admin.html       # Server logs stream, feedback resolution, user tables
│   │   ├── profile.html     # Security credentials editor & ticket submitter
│   │   └── error.html       # Graceful glassmorphic 404 & 500 pages
│   │
│   ├── __init__.py
│   ├── config.py            # Pydantic Settings and .env config validator
│   ├── database.py          # Engine sessions base mapping
│   ├── models.py            # Users, history, logs, reports SQL tables
│   ├── schemas.py           # Strong validation schemas
│   ├── auth.py              # CryptContext BCrypt & JWT token injection
│   ├── math_engine.py       # SymPy algebra solvers & step compilers
│   ├── graph_engine.py      # Plotly interactive JSON generators
│   └── ocr_engine.py        # OpenCV binarizer & pytesseract character filters
│
├── Dockerfile               # Multi-stage image optimizer for Tesseract/OpenCV
├── docker-compose.yml       # DB Volume persistence and network binding
├── gunicorn.conf.py         # Production worker processes and scaling
├── nginx.conf               # TLS Nginx gateway with rate limiting and upload bounds
├── requirements.txt         # Root Python package dependencies
├── .env.example             # Base configuration keys
├── .env                     # Local runnable configuration keys
├── installation_guide.md    # Windows / Linux local installation guide
├── deployment_guide.md      # VPS Cloud Gunicorn / Nginx / Certbot / Docker guide
└── README.md                # System Overview (This document)
```

---

## 🛠️ Quick Start Checklist

To run Metrai Calculus locally in under 3 minutes:

1. **Install Python 3.10+** and check **"Add Python to PATH"**.
2. **Install Tesseract OCR** and configure the path inside your local `.env` file (See [installation_guide.md](file:///c:/Users/Lenovo/Downloads/txt/metrai/Metrai_structure/Metrai/aaa/awrb/installation_guide.md)).
3. **Configure virtual environment**:
   ```bash
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   ```
4. **Install modules & execute**:
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```
5. Open your browser to [http://127.0.0.1:8000](http://127.0.0.1:8000). The **first registered user account** automatically becomes the system **Administrator**!
