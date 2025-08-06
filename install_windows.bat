@echo off
REM LOS_MAIN Automated Installation Script for Windows
REM This script will install all dependencies and set up the LOS application

setlocal enabledelayedexpansion

echo ==============================================
echo   LOS_MAIN Installation Script for Windows
echo ==============================================
echo.

REM Check if running as administrator
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Running with administrator privileges: OK
) else (
    echo [WARNING] Not running as administrator. Some installations may require elevation.
    echo Please run this script as administrator if you encounter permission errors.
    pause
)

REM Check if Python is installed
echo [INFO] Checking Python installation...
python --version >nul 2>&1
if %errorLevel% == 0 (
    for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
    echo [INFO] Python !PYTHON_VERSION! found
) else (
    echo [ERROR] Python not found. Please install Python 3.8+ from https://python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

REM Check if pip is available
echo [INFO] Checking pip...
pip --version >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] pip: OK
) else (
    echo [ERROR] pip not found. Please ensure Python was installed correctly.
    pause
    exit /b 1
)

REM Check if Git is installed
echo [INFO] Checking Git...
git --version >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Git: OK
) else (
    echo [WARNING] Git not found. Please install Git from https://git-scm.com/downloads
    echo Git is required to clone the repository.
    pause
)

REM Install/Check Chocolatey for package management
echo [INFO] Checking Chocolatey package manager...
choco version >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Chocolatey: OK
) else (
    echo [WARNING] Chocolatey not found. Installing...
    powershell -Command "Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))"
    if !errorLevel! == 0 (
        echo [INFO] Chocolatey installed successfully
    ) else (
        echo [WARNING] Chocolatey installation failed. You may need to install some dependencies manually.
    )
)

REM Install system dependencies via Chocolatey
echo [INFO] Installing system dependencies...

REM PostgreSQL
echo [INFO] Installing PostgreSQL...
choco install postgresql --confirm >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] PostgreSQL: Installed
) else (
    echo [WARNING] PostgreSQL installation may have failed. Please install manually if needed.
)

REM Tesseract OCR
echo [INFO] Installing Tesseract OCR...
choco install tesseract --confirm >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Tesseract OCR: Installed
) else (
    echo [WARNING] Tesseract installation may have failed. Please download from GitHub releases.
)

REM Check/Install Miniconda
echo [INFO] Checking for Conda...
conda --version >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Conda: OK
) else (
    echo [WARNING] Conda not found. Installing Miniconda...
    
    REM Download and install Miniconda
    powershell -Command "Invoke-WebRequest -Uri 'https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe' -OutFile 'Miniconda3-latest-Windows-x86_64.exe'"
    
    echo [INFO] Running Miniconda installer...
    start /wait Miniconda3-latest-Windows-x86_64.exe /InstallationType=JustMe /RegisterPython=1 /S /D=%UserProfile%\Miniconda3
    
    REM Add conda to PATH
    set PATH=%UserProfile%\Miniconda3;%UserProfile%\Miniconda3\Scripts;%PATH%
    
    REM Clean up installer
    del Miniconda3-latest-Windows-x86_64.exe
)

REM Initialize conda for command prompt
call %UserProfile%\Miniconda3\Scripts\activate.bat

REM Create conda environment
echo [INFO] Creating conda environment 'lostool'...
conda env list | findstr lostool >nul 2>&1
if %errorLevel% == 0 (
    echo [WARNING] Environment 'lostool' already exists. Removing and recreating...
    conda env remove -n lostool -y >nul 2>&1
)

conda create -n lostool python=3.11 -y
call conda activate lostool

REM Install geospatial packages via conda-forge
echo [INFO] Installing geospatial packages via conda-forge...
conda install -c conda-forge gdal geopandas rasterio fiona shapely pyproj -y

REM Install additional packages via pip
echo [INFO] Installing additional Python packages...
pip install --upgrade pip
pip install anthropic tkinterdnd2 tkintermapview tkcalendar
pip install reportlab PyMuPDF pytesseract pillow opencv-python
pip install boto3 aiohttp beautifulsoup4 requests scipy numpy pandas
pip install psycopg2-binary python-dotenv tqdm typing-extensions
pip install matplotlib folium lxml rtree simplekml laspy pdal earthengine-api

REM Create environment configuration template
echo [INFO] Creating environment configuration template...
(
echo # LOS Tool Configuration
echo # Copy this file to .env and fill in your actual values
echo.
echo # API Keys
echo ANTHROPIC_API_KEY=your_anthropic_api_key_here
echo GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
echo GOOGLE_API_KEY=your_google_api_key_here
echo MAPBOX_ACCESS_TOKEN=your_mapbox_token_here
echo.
echo # AWS Configuration
echo AWS_ACCESS_KEY_ID=your_aws_access_key_here
echo AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
echo AWS_REGION=us-west-2
echo.
echo # Earth Engine Configuration
echo EE_SERVICE_ACCOUNT=your_earth_engine_service_account@your_project.iam.gserviceaccount.com
echo EE_PRIVATE_KEY_PATH=path_to_your_credentials.json
echo EE_API_KEY=your_earth_engine_api_key_here
echo.
echo # Application Settings
echo APP_NAME=LOS Tool
echo APP_VERSION=1.0.0
echo FLASK_SECRET_KEY=your-secret-key-here
echo FLASK_ENV=development
echo.
echo # File System Settings
echo USE_TEMP_DIRS=true
echo CLEANUP_ON_EXIT=true
echo IGNORE_DS_STORE=false
echo.
echo # Performance Settings
echo LOWER_PROCESS_PRIORITY=true
echo MAX_CONCURRENT_DOWNLOADS=3
echo.
echo # Finder Interaction Settings
echo DISABLE_FINDER_OPEN=true
) > .env.template

REM Create batch file to run the application
echo [INFO] Creating application launcher...
(
echo @echo off
echo call %UserProfile%\Miniconda3\Scripts\activate.bat
echo call conda activate lostool
echo python dropmap.py
echo pause
) > "Run_LOS_Tool.bat"

REM Create desktop shortcut
echo [INFO] Creating desktop shortcut...
powershell -Command "$WshShell = New-Object -comObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%UserProfile%\Desktop\LOS Tool.lnk'); $Shortcut.TargetPath = '%CD%\Run_LOS_Tool.bat'; $Shortcut.WorkingDirectory = '%CD%'; $Shortcut.Save()"

REM Set up PostgreSQL (if installed successfully)
echo [INFO] Setting up PostgreSQL database...
net start postgresql-x64-* >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] PostgreSQL service started
    
    REM Wait for service to be ready
    timeout /t 5 /nobreak >nul
    
    REM Create database and user (requires psql to be in PATH)
    psql -U postgres -c "CREATE DATABASE lostool;" >nul 2>&1
    psql -U postgres -c "CREATE USER lostool WITH PASSWORD 'lostool';" >nul 2>&1
    psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE lostool TO lostool;" >nul 2>&1
    psql -U postgres -d lostool -c "CREATE EXTENSION IF NOT EXISTS postgis;" >nul 2>&1
    
    echo [INFO] PostgreSQL database setup complete
) else (
    echo [WARNING] PostgreSQL service not started. You may need to configure it manually.
)

REM Final verification
echo [INFO] Verifying installation...
call conda activate lostool
python -c "import sys; print(f'Python version: {sys.version}')"

echo.
echo ==============================================
echo   Installation Complete!
echo ==============================================
echo.
echo [INFO] To run the LOS Tool:
echo   1. Double-click "Run_LOS_Tool.bat" or
echo   2. Double-click the "LOS Tool" shortcut on your Desktop
echo.
echo [WARNING] Don't forget to:
echo   1. Copy .env.template to .env and add your API keys
echo   2. Add your Google Earth Engine credentials JSON file
echo.
echo For support, contact: andytrench@gmail.com
echo.
pause