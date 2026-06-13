FROM python:3.10-slim

WORKDIR /app

# Upgrade pip and install build dependencies
RUN pip install --no-cache-dir --upgrade pip

# Copy backend requirements and install
COPY backend/requirements.txt ./backend_requirements.txt
RUN pip install --no-cache-dir -r backend_requirements.txt

# Install frontend requirements
RUN pip install --no-cache-dir streamlit requests pandas openpyxl

# Create a non-root user for Hugging Face Spaces security requirements
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user \
	PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Copy the whole project
COPY --chown=user . .

# Hugging Face Spaces exposes port 7860 by default
EXPOSE 7860
EXPOSE 8000

# Create a startup script
RUN echo '#!/bin/bash\n\
uvicorn backend.main:app --host 0.0.0.0 --port 8000 &\n\
sleep 3\n\
streamlit run app.py --server.port 7860 --server.address 0.0.0.0\n\
' > start.sh && chmod +x start.sh

# Run the startup script
CMD ["./start.sh"]
