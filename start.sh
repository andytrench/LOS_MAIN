#!/bin/bash

# LOS Tool - Startup Script
# This script activates the correct Python environment and launches the LOS application

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[LOS TOOL]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're on macOS, Linux, or Windows (Git Bash)
if [[ "$OSTYPE" == "darwin"* ]]; then
    PLATFORM="macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="Linux"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    PLATFORM="Windows"
else
    PLATFORM="Unknown"
fi

print_status "Starting LOS Tool on $PLATFORM..."

# Check if .venv directory exists
if [ -d ".venv" ]; then
    print_success "Found .venv virtual environment"
    
    # Activate the virtual environment
    print_status "Activating .venv virtual environment..."
    source .venv/bin/activate
    
    if [ $? -eq 0 ]; then
        print_success "Virtual environment activated successfully"
    else
        print_error "Failed to activate .venv virtual environment"
        exit 1
    fi
else
    print_error ".venv directory not found"
    print_status "Please create a virtual environment first:"
    print_status "  python3 -m venv .venv"
    print_status "  source .venv/bin/activate"
    print_status "  pip install -r requirements.txt"
    print_status ""
    print_status "Or run the automated installer:"
    print_status "  macOS:   bash install_macos.sh"
    print_status "  Linux:   bash install_linux.sh"
    print_status "  Windows: install_windows.bat"
    exit 1
fi

# Verify Python environment
print_status "Verifying Python environment..."
python_version=$(python --version 2>&1)
print_status "Using: $python_version"

# Check for critical dependencies
print_status "Checking critical dependencies..."

critical_deps=("gdal" "tkinter" "tkinterdnd2" "tkintermapview" "geopandas")
missing_deps=()

for dep in "${critical_deps[@]}"; do
    if [ "$dep" = "tkinter" ]; then
        # Special check for tkinter since it's built-in
        python -c "import tkinter" 2>/dev/null
    else
        python -c "import $dep" 2>/dev/null
    fi
    
    if [ $? -ne 0 ]; then
        missing_deps+=("$dep")
        print_warning "Missing dependency: $dep"
    fi
done

# Install missing dependencies
if [ ${#missing_deps[@]} -gt 0 ]; then
    print_status "Installing missing dependencies..."
    for dep in "${missing_deps[@]}"; do
        print_status "Installing $dep via pip..."
        pip install "$dep"
    done
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    print_warning ".env file not found"
    if [ -f "env.template" ]; then
        print_status "Found env.template - you'll need to configure API keys"
        print_status "Copy env.template to .env and add your API keys before using all features"
    else
        print_warning "No environment template found"
    fi
fi

# Check if dropmap.py exists
if [ ! -f "dropmap.py" ]; then
    print_error "dropmap.py not found in current directory"
    print_status "Please run this script from the LOS Tool project directory"
    exit 1
fi

# Launch the application
print_status "Launching LOS Tool application..."
print_status "═══════════════════════════════════════"

# Run dropmap.py and capture any errors
python dropmap.py

# Check if the application exited with an error
exit_code=$?
if [ $exit_code -ne 0 ]; then
    print_error "Application exited with error code: $exit_code"
    print_status "Check the console output above for error details"
    print_status "Common issues:"
    print_status "  1. Missing API keys in .env file"
    print_status "  2. Database connection issues"
    print_status "  3. Missing system dependencies"
    print_status ""
    print_status "For help, check README.md or run the appropriate installer:"
    print_status "  macOS:   bash install_macos.sh"
    print_status "  Linux:   bash install_linux.sh"
    print_status "  Windows: install_windows.bat"
else
    print_success "Application closed normally"
fi

print_status "═══════════════════════════════════════"