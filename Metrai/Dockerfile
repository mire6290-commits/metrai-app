FROM python:3.10-slim

WORKDIR /app

# Upgrade pip and install build dependencies
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements and install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create a non-root user for Hugging Face Spaces security requirements
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy the backend code
COPY --chown=user backend/ .

# Hugging Face Spaces exposes port 7860 by default
EXPOSE 7860

# Run FastAPI with uvicorn on port 7860
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
