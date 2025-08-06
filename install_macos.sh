#!/bin/bash
# LOS_MAIN Automated Installation Script for macOS
# This script will install all dependencies and set up the LOS application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

info() {
    echo -e "${BLUE}[INFO] $1${NC}"
}

# Check if running on macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    error "This script is designed for macOS only."
fi

# Check architecture
ARCH=$(uname -m)
log "Detected architecture: $ARCH"

echo "=============================================="
echo "  LOS_MAIN Installation Script for macOS"
echo "=============================================="
echo ""

# Check for Xcode Command Line Tools
log "Checking for Xcode Command Line Tools..."
if ! xcode-select -p &> /dev/null; then
    warn "Xcode Command Line Tools not found. Installing..."
    xcode-select --install
    echo "Please complete the Xcode Command Line Tools installation and run this script again."
    exit 1
else
    info "Xcode Command Line Tools: ✓"
fi

# Check/Install Homebrew
log "Checking for Homebrew..."
if ! command -v brew &> /dev/null; then
    warn "Homebrew not found. Installing..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon
    if [[ "$ARCH" == "arm64" ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    info "Homebrew: ✓"
fi

# Update Homebrew
log "Updating Homebrew..."
brew update

# Install system dependencies
log "Installing system dependencies..."

# PostgreSQL and PostGIS
log "Installing PostgreSQL and PostGIS..."
brew install postgresql postgis
brew services start postgresql

# GDAL and geospatial libraries
log "Installing GDAL and geospatial libraries..."
brew install gdal

# Tesseract OCR
log "Installing Tesseract OCR..."
brew install tesseract

# Check/Install Python 3.8+
log "Checking Python installation..."
if ! command -v python3 &> /dev/null; then
    warn "Python3 not found. Installing..."
    brew install python@3.11
else
    PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    REQUIRED_VERSION="3.8"
    if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" = "$REQUIRED_VERSION" ]; then
        info "Python $PYTHON_VERSION: ✓"
    else
        warn "Python version $PYTHON_VERSION is below required $REQUIRED_VERSION. Installing Python 3.11..."
        brew install python@3.11
    fi
fi

# Install pip if not available
if ! command -v pip3 &> /dev/null; then
    log "Installing pip..."
    python3 -m ensurepip --upgrade
fi

# Check/Install Miniconda for better geospatial package management
log "Checking for Conda..."
if ! command -v conda &> /dev/null; then
    warn "Conda not found. Installing Miniconda..."
    if [[ "$ARCH" == "arm64" ]]; then
        curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh
        bash Miniconda3-latest-MacOSX-arm64.sh -b -p $HOME/miniconda3
    else
        curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh
        bash Miniconda3-latest-MacOSX-x86_64.sh -b -p $HOME/miniconda3
    fi
    
    # Initialize conda
    source $HOME/miniconda3/bin/activate
    conda init zsh bash
    
    # Clean up installer
    rm -f Miniconda3-latest-MacOSX-*.sh
else
    info "Conda: ✓"
    source $HOME/miniconda3/bin/activate
fi

# Create conda environment for LOS application
log "Creating conda environment 'lostool'..."
if conda env list | grep -q lostool; then
    warn "Environment 'lostool' already exists. Removing and recreating..."
    conda env remove -n lostool -y
fi

conda create -n lostool python=3.11 -y
conda activate lostool

# Install geospatial packages via conda-forge (better for macOS)
log "Installing geospatial packages via conda-forge..."
conda install -c conda-forge gdal geopandas rasterio fiona shapely pyproj laspy pdal earthengine-api -y

# Install remaining Python packages via pip
log "Installing additional Python packages..."
pip install --upgrade pip
pip install anthropic tkinterdnd2 tkintermapview tkcalendar
pip install reportlab PyMuPDF pytesseract pillow opencv-python
pip install boto3 aiohttp beautifulsoup4 requests scipy numpy pandas
pip install psycopg2-binary python-dotenv tqdm typing-extensions
pip install matplotlib folium lxml rtree simplekml

# Create desktop application launcher
log "Creating application launcher..."
cat > ~/Desktop/LOS_Tool.command << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source $HOME/miniconda3/bin/activate
conda activate lostool
python dropmap.py
EOF

chmod +x ~/Desktop/LOS_Tool.command

# Set up environment template
log "Creating environment configuration template..."
cat > .env.template << 'EOF'
# LOS Tool Configuration
# Copy this file to .env and fill in your actual values

# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_MAPS_API_KEY=your_google_maps_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
MAPBOX_ACCESS_TOKEN=your_mapbox_token_here

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key_here
AWS_SECRET_ACCESS_KEY=your_aws_secret_key_here
AWS_REGION=us-west-2

# Earth Engine Configuration
EE_SERVICE_ACCOUNT=your_earth_engine_service_account@your_project.iam.gserviceaccount.com
EE_PRIVATE_KEY_PATH=path_to_your_credentials.json
EE_API_KEY=your_earth_engine_api_key_here

# Application Settings
APP_NAME=LOS Tool
APP_VERSION=1.0.0
FLASK_SECRET_KEY=your-secret-key-here
FLASK_ENV=development

# File System Settings
USE_TEMP_DIRS=true
CLEANUP_ON_EXIT=true
IGNORE_DS_STORE=false

# Performance Settings
LOWER_PROCESS_PRIORITY=true
MAX_CONCURRENT_DOWNLOADS=3

# Finder Interaction Settings
DISABLE_FINDER_OPEN=true
EOF

# Set up PostgreSQL database
log "Setting up PostgreSQL database..."
# Start PostgreSQL if not running
if ! brew services list | grep postgresql | grep -q started; then
    brew services start postgresql
fi

# Wait for PostgreSQL to start
sleep 3

# Create database and user
psql postgres -c "CREATE DATABASE lostool;" 2>/dev/null || info "Database 'lostool' already exists"
psql postgres -c "CREATE USER lostool WITH PASSWORD 'lostool';" 2>/dev/null || info "User 'lostool' already exists"
psql postgres -c "GRANT ALL PRIVILEGES ON DATABASE lostool TO lostool;" 2>/dev/null

# Enable PostGIS extension
psql lostool -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null

# Create activation script
log "Creating activation script..."
cat > activate_lostool.sh << 'EOF'
#!/bin/bash
# Activate LOS Tool environment
source $HOME/miniconda3/bin/activate
conda activate lostool
echo "LOS Tool environment activated. You can now run:"
echo "  python dropmap.py"
EOF

chmod +x activate_lostool.sh

# Final verification
log "Verifying installation..."

# Test imports
conda activate lostool
python3 -c "
import sys
print(f'Python version: {sys.version}')

try:
    import gdal
    print(f'GDAL version: {gdal.__version__}')
except ImportError as e:
    print(f'GDAL import error: {e}')

try:
    import geopandas
    print(f'GeoPandas version: {geopandas.__version__}')
except ImportError as e:
    print(f'GeoPandas import error: {e}')

try:
    import tkinter
    print('Tkinter: ✓')
except ImportError as e:
    print(f'Tkinter import error: {e}')

try:
    import psycopg2
    print('PostgreSQL connector: ✓')
except ImportError as e:
    print(f'PostgreSQL connector error: {e}')
"

echo ""
echo "=============================================="
echo "  Installation Complete!"
echo "=============================================="
echo ""
info "To run the LOS Tool:"
echo "  1. Run: source activate_lostool.sh"
echo "  2. Run: python dropmap.py"
echo ""
info "Or double-click the 'LOS_Tool.command' file on your Desktop"
echo ""
warn "Don't forget to:"
echo "  1. Copy .env.template to .env and add your API keys"
echo "  2. Add your Google Earth Engine credentials JSON file"
echo ""
echo "For support, contact: andytrench@gmail.com"