# GDAL and Homebrew: Best Practices Guide

## Overview

This document provides guidance on using GDAL with Homebrew on macOS, with a focus on avoiding common issues, particularly on Apple Silicon (M1/M2) machines. It covers installation, environment setup, version management, and troubleshooting.

## Table of Contents

1. [Understanding the Architecture](#understanding-the-architecture)
2. [Installation Best Practices](#installation-best-practices)
3. [Python Environment Setup](#python-environment-setup)
4. [Version Management](#version-management)
5. [Common Issues and Solutions](#common-issues-and-solutions)
6. [Homebrew Update Procedures](#homebrew-update-procedures)
7. [Testing GDAL Functionality](#testing-gdal-functionality)
8. [Appendix: GDAL in Our Application](#appendix-gdal-in-our-application)

## Understanding the Architecture

### How GDAL Works with Python

GDAL consists of two main components:
1. **Core C/C++ libraries**: Installed via Homebrew in `/opt/homebrew/Cellar/gdal/[version]/`
2. **Python bindings**: Installed via pip as the `gdal` package

The Python bindings need to find and load the core libraries at runtime. This is where most issues occur, especially on Apple Silicon Macs.

### Library Loading Process

When you import GDAL in Python:
1. Python loads the GDAL Python package
2. The package tries to load the native GDAL libraries using dynamic linking
3. The dynamic linker searches for libraries in specific paths
4. If the libraries aren't found or version mismatches occur, import fails

## Installation Best Practices

### Installing GDAL with Homebrew

```bash
# Install GDAL
brew install gdal

# Verify installation
brew info gdal
```

### Installing Python GDAL Package

**Important**: Always install the Python GDAL package that matches your Homebrew GDAL version.

```bash
# Check Homebrew GDAL version
gdal-config --version

# Install matching Python GDAL package
pip install gdal==$(gdal-config --version)
```

### Avoiding Version Conflicts

1. **Install GDAL first**: Always install the Homebrew GDAL package before the Python package
2. **Match versions**: Ensure Python GDAL version matches Homebrew GDAL version
3. **Use virtual environments**: Isolate your project dependencies

## Python Environment Setup

### Virtual Environment Setup

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install GDAL with matching version
pip install gdal==$(gdal-config --version)
```

### Environment Variables

Set these environment variables in your `.env` file or activation script:

```bash
# GDAL configuration
export GDAL_DATA=/opt/homebrew/Cellar/gdal/$(gdal-config --version)/share/gdal
export PROJ_LIB=/opt/homebrew/Cellar/proj/$(proj --version | awk '{print $2}')/share/proj
```

## Version Management

### Checking Versions

```bash
# Check Homebrew GDAL version
gdal-config --version

# Check Python GDAL version
python -c "from osgeo import gdal; print(gdal.VersionInfo())"
```

### Handling Homebrew Updates

When updating Homebrew packages:

1. Update Homebrew: `brew update`
2. Upgrade GDAL: `brew upgrade gdal`
3. Check new GDAL version: `gdal-config --version`
4. Reinstall Python GDAL package: `pip install --force-reinstall gdal==$(gdal-config --version)`
5. Run the GDAL fix script if needed: `./fix_gdal.sh`

## Common Issues and Solutions

### Library Not Found Errors

**Issue**: `ImportError: dlopen(...): Library not loaded: /opt/homebrew/opt/gdal/lib/libgdal.XX.dylib`

**Solution**:
1. Create symbolic links from actual library locations to expected locations
2. Use the provided `fix_gdal.sh` script

### Version Mismatch Errors

**Issue**: Python GDAL package expects a different version than what's installed

**Solution**:
1. Reinstall Python GDAL package with matching version
2. Create symbolic links for backward compatibility

### Dependency Issues

**Issue**: GDAL depends on other libraries (poppler, proj, etc.) that may also have version mismatches

**Solution**:
1. Check for missing dependencies: `otool -L /opt/homebrew/Cellar/gdal/*/lib/libgdal.dylib`
2. Create symbolic links for dependencies using `fix_gdal.sh`

## Homebrew Update Procedures

Follow these steps when updating Homebrew packages:

1. **Before updating**:
   - Document current GDAL version: `gdal-config --version`
   - Check if GDAL is working: `python -c "from osgeo import gdal; print('GDAL OK')"`

2. **Update process**:
   ```bash
   # Update Homebrew
   brew update
   
   # Upgrade packages
   brew upgrade
   
   # Check new GDAL version
   gdal-config --version
   
   # Fix GDAL links
   ./fix_gdal.sh
   
   # Reinstall Python GDAL package if needed
   pip install --force-reinstall gdal==$(gdal-config --version)
   ```

3. **After updating**:
   - Verify GDAL functionality: `python test_gdal_full.py`
   - Update documentation if version changed

## Testing GDAL Functionality

Use the provided `test_gdal_full.py` script to verify GDAL functionality:

```bash
python test_gdal_full.py
```

This script tests:
- Basic GDAL imports
- GDAL version information
- Available drivers
- Coordinate transformation

## Appendix: GDAL in Our Application

### How We Use GDAL

In our application, GDAL is used for:

1. **Geospatial data processing**: Reading and writing various geospatial file formats
2. **Coordinate transformations**: Converting between different coordinate systems
3. **Raster operations**: Processing LIDAR and elevation data
4. **Vector operations**: Working with shapefiles and other vector formats

### Critical GDAL Dependencies

Our application relies on these GDAL-related dependencies:
- `gdal`: Core GDAL Python bindings
- `geopandas`: For geospatial data analysis (depends on GDAL)
- `rasterio`: For raster data processing (depends on GDAL)
- `fiona`: For vector data processing (depends on GDAL)

### Maintaining Compatibility

To ensure compatibility across different environments:

1. **Specify exact versions** in `requirements.txt`:
   ```
   gdal==3.10.2
   geopandas==0.10.0
   rasterio==1.3.0
   ```

2. **Document GDAL version** in project documentation

3. **Include the GDAL fix scripts** in the repository

4. **Test GDAL functionality** after environment changes
