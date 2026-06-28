# ==============================================================================
# METRAI CALCULUS - GUNICORN PRODUCTION CONFIGURATION
# Runs ASGI FastAPI application using high-performance Uvicorn workers.
# ==============================================================================

import multiprocessing
import os

# Server socket binding
bind = f"0.0.0.0:{os.getenv('PORT', '8000')}"

# Worker processes calculation (Standard formula: cores * 2 + 1)
# Ensures maximum utilization of CPU cores under traffic load
workers = (multiprocessing.cpu_count() * 2) + 1

# Uvicorn high-performance worker class for ASGI apps
worker_class = "uvicorn.workers.UvicornWorker"

# Increase timeout limit to accommodate complex SymPy integrations and OCR scans
timeout = 120

# Keepalive socket connections
keepalive = 5

# Process naming tag for system monitoring
proc_name = "metrai_calculus"

# Standard logs streams
accesslog = "-"
errorlog = "-"
loglevel = "info"
