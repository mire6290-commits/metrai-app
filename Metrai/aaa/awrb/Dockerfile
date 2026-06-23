# ==============================================================================
# METRAI CALCULUS - MULTI-STAGE PRODUCTION DOCKERFILE
# Handles system packages for OpenCV (cv2) and Tesseract OCR locally.
# ==============================================================================

FROM python:3.11-slim as builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install compiler dependencies for passlib/bcrypt/numpy
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into a wheels directory
RUN pip install --no-cache-dir --user -r requirements.txt

# --- FINAL STAGE ---
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV and Tesseract OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy python packages from builder stage
COPY --from=builder /root/.local /root/.local
COPY . /app

ENV PATH=/root/.local/bin:$PATH
ENV PORT=8000

EXPOSE 8000

# Run using Gunicorn with Uvicorn workers for production performance
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app.main:app"]
