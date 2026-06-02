# METRAI CALCULUS - VPS PRODUCTION DEPLOYMENT GUIDE

This document provides step-by-step instructions to deploy **Metrai Calculus** to a production cloud server (Ubuntu VPS, AWS EC2, DigitalOcean Droplet, Linode) with real domain integration, SSL encryption, Nginx gateway, Gunicorn daemon processes, and Docker containerization.

---

## METHOD A: DOCKER CONTAINERIZED DEPLOYMENT (RECOMMENDED)

Docker isolates our OpenCV, Tesseract, and Python dependencies, making deployments incredibly safe and fast.

### Step 1: Install Docker & Docker-Compose on your VPS
```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose
sudo systemctl enable docker
sudo systemctl start docker
```

### Step 2: Configure Environment Variables
Create a production `.env` file inside the deployment workspace:
```bash
nano .env
```
Ensure you provide secure production tokens:
```env
PROJECT_NAME="Metrai Calculus"
ENVIRONMENT="production"
DEBUG=false
SECRET_KEY="generate-a-highly-secure-64-character-cryptographic-hash-here"
ALGORITHM="HS256"
DATABASE_URL="sqlite:////app/data/metrai_calculus.db"
ALLOWED_HOSTS="yourdomain.com,www.yourdomain.com"
CSRF_COOKIE_SECURE=true
SESSION_COOKIE_SECURE=true
TESSERACT_CMD=""
```

### Step 3: Run the Application Containers
```bash
# Build and run containers in the background (detached daemon mode)
docker-compose up -d --build
```
This builds our multi-stage image, downloads Tesseract OCR binaries internally, maps network port `8000`, and starts the production Gunicorn server automatically.

### Step 4: Verify Deployment Container States
```bash
docker ps
docker logs metrai_calculus_app
```

---

## METHOD B: VPS SYSTEMD SERVICE DEPLOYMENT (NON-DOCKER)

If you prefer to run directly on the host OS:

### Step 1: Create systemd Service Unit
Create a gunicorn daemon service configuration file:
```bash
sudo nano /etc/systemd/system/metrai-calculus.service
```

Paste the following configurations (adjust user path strings):
```ini
[Unit]
Description=Metrai Calculus FastAPI Gunicorn Daemon
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/metrai-calculus
ExecStart=/home/ubuntu/metrai-calculus/venv/bin/gunicorn -c gunicorn.conf.py app.main:app
Restart=always
EnvironmentFile=/home/ubuntu/metrai-calculus/.env

[Install]
WantedBy=multi-user.target
```

### Step 2: Reload systemd and Start Gunicorn
```bash
sudo systemctl daemon-reload
sudo systemctl start metrai-calculus
sudo systemctl enable metrai-calculus
```
Verify state via `sudo systemctl status metrai-calculus`.

---

## DOMAIN INTEGRATION, NGINX GATEWAY & SSL ENCRYPTION

Regardless of using Method A or Method B, reverse-proxying using Nginx and encrypting with Certbot is required for public DNS access.

### Step 1: Install Nginx & Let's Encrypt Certbot
```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### Step 2: Copy Nginx Site Configurations
```bash
sudo cp nginx.conf /etc/nginx/sites-available/metrai-calculus
# Create soft link to enable site config
sudo ln -s /etc/nginx/sites-available/metrai-calculus /etc/nginx/sites-enabled/
# Remove default site
sudo rm /etc/nginx/sites-enabled/default
```

### Step 3: Issue SSL Certificates via Certbot
Verify your DNS record is propagated, then execute:
```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```
Follow prompts. Certbot automatically hooks SSL files, edits `nginx.conf`, and schedules certificate auto-renewals in cron!

### Step 4: Test Nginx Configurations and Restart
```bash
sudo nginx -t
sudo systemctl restart nginx
```

Now, your production-ready mathematical platform **Metrai Calculus** is fully active, secure (HTTPS), and accessible on your domain!
