# METRAI CALCULUS - LOCAL INSTALLATION & DEVELOPMENT GUIDE

This document details step-by-step instructions to configure, install, and execute the **Metrai Calculus** local mathematics platform on both Windows and Linux hosts.

---

## 1. System Requirements

* **Operating System**: Windows 10/11, Ubuntu 20.04+, or macOS Big Sur+.
* **Python**: Python `3.10` or `3.11` (Recommended).
* **System Packages**:
  * **Tesseract OCR** (Required for OCR Mathematical Image Recognition).
  * **C++ Build Tools / Build Essential** (Required by Passlib / BCrypt / NumPy).

---

## 2. Installation on Windows 10/11

### Step 1: Install Python
Ensure Python 3.10+ is installed on your workstation. Ensure you check **"Add Python to PATH"** during installation.

### Step 2: Install Tesseract OCR
Because Metrai Calculus runs image mathematical OCR completely locally without paid APIs, you must install the Tesseract binary:
1. Download the Windows installer from: [UB Mannheim Tesseract Installer](https://github.com/UB-Mannheim/tesseract/wiki).
2. Run the installer. By default, it installs to: `C:\Program Files\Tesseract-OCR\tesseract.exe`.
3. Open your `.env` file at the root of the project and ensure the path is set correctly:
   ```env
   TESSERACT_CMD="C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
   ```

### Step 3: Install C++ Build Tools (If required)
If pip fails when building the `bcrypt` package:
1. Download [Visual Studio Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/).
2. Select **"Desktop development with C++"** and click install.

### Step 4: Clone and Setup Workspace
Open PowerShell in the project directory (`aaa\awrb`):
```powershell
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\activate

# Install the Python packages
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 5: Start Server
Run the local dev command:
```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser and navigate to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 3. Installation on Linux (Ubuntu/Debian)

### Step 1: Install System Dependencies
Open a terminal and install Tesseract and OpenCV-headless packages:
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-venv build-essential \
    tesseract-ocr tesseract-ocr-eng libgl1-mesa-glx libglib2.0-0
```

### Step 2: Configure virtual Environment
```bash
# Generate env
python3 -m venv venv

# Activate env
source venv/bin/activate

# Install packages
pip3 install --upgrade pip
pip3 install -r requirements.txt
```

### Step 3: Configure Environments
In Linux/Ubuntu, Tesseract is registered globally in the system bin path. Open `.env` and set `TESSERACT_CMD` to empty, or specify standard path:
```env
TESSERACT_CMD=""
```

### Step 4: Start Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 4. Initial System Administrator Setup

1. Launch the server and click **"Join Free"** or navigate to `/register`.
2. Register the **first account** in the system. The application detects a user count of `0` and elevates the **first registered user** to the **Administrator** role automatically.
3. Access your admin workspace at [http://127.0.0.1:8000/admin](http://127.0.0.1:8000/admin) to monitor calculations velocity, adjust users role elevated, and manage open support feedback reports!
