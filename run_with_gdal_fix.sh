#!/bin/bash
# Script to run the application with GDAL fix

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Run the GDAL fix script
echo "Checking GDAL library links..."
"$SCRIPT_DIR/fix_gdal.sh"

# Activate the virtual environment if it exists
if [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Run the application
echo "Starting application..."
python "$SCRIPT_DIR/dropmap.py"
