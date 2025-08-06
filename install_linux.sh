#!/bin/bash
# LOS_MAIN Automated Installation Script for Linux
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

# Detect Linux distribution
detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        DISTRO=$ID
        VERSION=$VERSION_ID
    elif [ -f /etc/redhat-release ]; then
        DISTRO="rhel"
    elif [ -f /etc/debian_version ]; then
        DISTRO="debian"
    else
        DISTRO="unknown"
    fi
    
    log "Detected Linux distribution: $DISTRO"
}

# Check if running on Linux
if [[ "$OSTYPE" != "linux"* ]]; then
    error "This script is designed for Linux only."
fi

echo "=============================================="
echo "  LOS_MAIN Installation Script for Linux"
echo "=============================================="
echo ""

# Detect distribution
detect_distro

# Check for sudo privileges
if ! sudo -n true 2>/dev/null; then
    warn "This script requires sudo privileges for system package installation."
    echo "Please enter your password when prompted."
fi

# Update package repositories
log "Updating package repositories..."
case $DISTRO in
    ubuntu|debian)
        sudo apt-get update
        PACKAGE_MANAGER="apt-get"
        ;;
    fedora)
        sudo dnf update -y
        PACKAGE_MANAGER="dnf"
        ;;
    centos|rhel)
        sudo yum update -y
        PACKAGE_MANAGER="yum"
        ;;
    arch)
        sudo pacman -Sy
        PACKAGE_MANAGER="pacman"
        ;;
    *)
        warn "Unknown distribution. Assuming apt-get package manager."
        sudo apt-get update || true
        PACKAGE_MANAGER="apt-get"
        ;;
esac

# Install system dependencies based on distribution
log "Installing system dependencies..."

case $DISTRO in
    ubuntu|debian)
        # Essential build tools
        sudo apt-get install -y build-essential git curl wget software-properties-common
        
        # Python development
        sudo apt-get install -y python3 python3-pip python3-dev python3-venv
        
        # Geospatial libraries
        sudo apt-get install -y gdal-bin libgdal-dev libproj-dev libgeos-dev
        sudo apt-get install -y libspatialindex-dev libffi-dev
        
        # PostgreSQL and PostGIS
        sudo apt-get install -y postgresql postgresql-contrib postgis postgresql-*-postgis-*
        
        # Tesseract OCR
        sudo apt-get install -y tesseract-ocr tesseract-ocr-eng
        
        # Additional libraries
        sudo apt-get install -y libjpeg-dev libpng-dev libtiff-dev
        sudo apt-get install -y libxml2-dev libxslt1-dev
        sudo apt-get install -y tk-dev
        ;;
        
    fedora)
        # Essential build tools
        sudo dnf install -y gcc gcc-c++ git curl wget
        
        # Python development
        sudo dnf install -y python3 python3-pip python3-devel
        
        # Geospatial libraries
        sudo dnf install -y gdal gdal-devel proj proj-devel geos geos-devel
        sudo dnf install -y spatialindex-devel libffi-devel
        
        # PostgreSQL and PostGIS
        sudo dnf install -y postgresql postgresql-server postgresql-contrib postgis
        
        # Tesseract OCR
        sudo dnf install -y tesseract tesseract-langpack-eng
        
        # Additional libraries
        sudo dnf install -y libjpeg-devel libpng-devel libtiff-devel
        sudo dnf install -y libxml2-devel libxslt-devel
        sudo dnf install -y tkinter
        ;;
        
    centos|rhel)
        # Enable EPEL repository
        sudo yum install -y epel-release
        
        # Essential build tools
        sudo yum groupinstall -y "Development Tools"
        sudo yum install -y git curl wget
        
        # Python development
        sudo yum install -y python3 python3-pip python3-devel
        
        # Geospatial libraries (may need additional repositories)
        sudo yum install -y gdal gdal-devel proj proj-devel geos geos-devel
        
        # PostgreSQL
        sudo yum install -y postgresql postgresql-server postgresql-contrib
        
        # Tesseract OCR
        sudo yum install -y tesseract tesseract-langpack-eng
        ;;
        
    arch)
        # Essential tools
        sudo pacman -S --noconfirm base-devel git curl wget
        
        # Python
        sudo pacman -S --noconfirm python python-pip
        
        # Geospatial libraries
        sudo pacman -S --noconfirm gdal proj geos spatialindex
        
        # PostgreSQL and PostGIS
        sudo pacman -S --noconfirm postgresql postgis
        
        # Tesseract OCR
        sudo pacman -S --noconfirm tesseract tesseract-data-eng
        
        # Additional libraries
        sudo pacman -S --noconfirm tk
        ;;
esac

# Check/Install Miniconda
log "Checking for Conda..."
if ! command -v conda &> /dev/null; then
    warn "Conda not found. Installing Miniconda..."
    
    # Detect architecture
    ARCH=$(uname -m)
    if [[ "$ARCH" == "x86_64" ]]; then
        CONDA_INSTALLER="Miniconda3-latest-Linux-x86_64.sh"
    elif [[ "$ARCH" == "aarch64" ]]; then
        CONDA_INSTALLER="Miniconda3-latest-Linux-aarch64.sh"
    else
        CONDA_INSTALLER="Miniconda3-latest-Linux-x86_64.sh"
    fi
    
    wget https://repo.anaconda.com/miniconda/$CONDA_INSTALLER
    bash $CONDA_INSTALLER -b -p $HOME/miniconda3
    
    # Initialize conda
    source $HOME/miniconda3/bin/activate
    conda init bash
    
    # Add to current session
    export PATH="$HOME/miniconda3/bin:$PATH"
    
    # Clean up installer
    rm -f $CONDA_INSTALLER
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

# Install geospatial packages via conda-forge
log "Installing geospatial packages via conda-forge..."
conda install -c conda-forge gdal geopandas rasterio fiona shapely pyproj laspy pdal earthengine-api -y

# Install remaining Python packages via pip
log "Installing additional Python packages..."
pip install --upgrade pip
pip install anthropic
pip install reportlab PyMuPDF pytesseract pillow opencv-python
pip install boto3 aiohttp beautifulsoup4 requests scipy numpy pandas
pip install psycopg2-binary python-dotenv tqdm typing-extensions
pip install matplotlib folium lxml rtree simplekml

# Install GUI packages (may require X11)
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    log "Installing GUI packages..."
    pip install tkinterdnd2 tkintermapview tkcalendar
else
    warn "No display detected. Skipping GUI packages. You may need to install them later if running in a desktop environment."
fi

# Set up PostgreSQL database
log "Setting up PostgreSQL..."

# Initialize PostgreSQL if needed
case $DISTRO in
    fedora|centos|rhel)
        if [ ! -d "/var/lib/pgsql/data" ]; then
            sudo postgresql-setup --initdb
        fi
        sudo systemctl enable postgresql
        sudo systemctl start postgresql
        ;;
    *)
        sudo systemctl enable postgresql
        sudo systemctl start postgresql
        ;;
esac

# Wait for PostgreSQL to start
sleep 3

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE lostool;" 2>/dev/null || info "Database 'lostool' already exists"
sudo -u postgres psql -c "CREATE USER lostool WITH PASSWORD 'lostool';" 2>/dev/null || info "User 'lostool' already exists"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE lostool TO lostool;" 2>/dev/null

# Enable PostGIS extension
sudo -u postgres psql lostool -c "CREATE EXTENSION IF NOT EXISTS postgis;" 2>/dev/null

# Create environment configuration template
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

# Create desktop launcher (if in desktop environment)
if [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
    log "Creating desktop launcher..."
    mkdir -p ~/.local/share/applications
    
    cat > ~/.local/share/applications/lostool.desktop << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=LOS Tool
Comment=Line of Sight Analysis Tool
Exec=bash -c "cd $(pwd) && source $HOME/miniconda3/bin/activate && conda activate lostool && python dropmap.py"
Icon=utilities-terminal
Terminal=false
Categories=Science;Engineering;
EOF
    
    chmod +x ~/.local/share/applications/lostool.desktop
fi

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
if [ -f ~/.local/share/applications/lostool.desktop ]; then
    info "Or look for 'LOS Tool' in your applications menu"
fi
echo ""
warn "Don't forget to:"
echo "  1. Copy .env.template to .env and add your API keys"
echo "  2. Add your Google Earth Engine credentials JSON file"
echo ""
echo "For support, contact: andytrench@gmail.com"