#!/bin/bash

# Activate conda
source ~/miniconda3/bin/activate

# Activate the gdal_env environment
conda activate gdal_env

# Check for required packages and install them if missing
packages=("gdal" "tkinterdnd2" "tkintermapview" "geopandas" "matplotlib" "tkcalendar" "python-dotenv" "rasterio")

for package in "${packages[@]}"; do
    if ! pip list | grep -q "$package"; then
        echo "Installing $package..."
        pip install "$package"
    fi
done

# Run the application
python dropmap.py
