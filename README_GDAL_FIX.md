# GDAL Fix for macOS M1/M2

This document provides instructions for fixing GDAL library issues on macOS M1/M2 machines.

## Problem

On macOS with Apple Silicon (M1/M2), the Python GDAL package often has issues finding the correct library files due to version mismatches between the Python package and the Homebrew-installed GDAL libraries.

Common errors include:
```
ImportError: dlopen(...): Library not loaded: /opt/homebrew/opt/gdal/lib/libgdal.36.dylib
```

## Solution

This directory contains scripts to fix the GDAL library issues:

1. `fix_gdal.sh` - Creates symbolic links for GDAL and its dependencies
2. `run_with_gdal_fix.sh` - Runs the application with the GDAL fix applied

Additionally, the virtual environment's activation script has been modified to automatically check and fix GDAL when you activate the environment.

## Usage

### Option 1: Run the application with GDAL fix

```bash
./run_with_gdal_fix.sh
```

This script will:
1. Run the GDAL fix script to create necessary symbolic links
2. Activate the virtual environment
3. Start the application

### Option 2: Fix GDAL manually

```bash
./fix_gdal.sh
```

This script will create symbolic links for GDAL and its dependencies. You can run this script whenever you update your Homebrew packages or if you encounter GDAL library issues.

### Option 3: Activate the virtual environment

```bash
source .venv/bin/activate
```

The virtual environment's activation script has been modified to automatically check and fix GDAL when you activate the environment.

## After Homebrew Updates

If you update your Homebrew packages, you may need to run the GDAL fix script again:

```bash
./fix_gdal.sh
```

## Troubleshooting

If you still encounter GDAL issues after running the fix scripts, try the following:

1. Check if GDAL is installed in Homebrew:
   ```bash
   brew info gdal
   ```

2. Check if the Python GDAL package is installed:
   ```bash
   pip list | grep gdal
   ```

3. Reinstall the Python GDAL package:
   ```bash
   pip uninstall gdal
   pip install gdal
   ```

4. Run the test script to verify GDAL functionality:
   ```bash
   python test_gdal_full.py
   ```

## Technical Details

The fix works by creating symbolic links from the Homebrew-installed GDAL libraries to the locations where the Python GDAL package expects to find them.

For example:
- `/opt/homebrew/Cellar/gdal/3.10.3/lib/libgdal.36.dylib` → `/opt/homebrew/opt/gdal/lib/libgdal.36.dylib`
- `/opt/homebrew/Cellar/poppler/25.04.0/lib/libpoppler.148.dylib` → `/opt/homebrew/opt/poppler/lib/libpoppler.148.dylib`

The script automatically detects the installed versions and creates the appropriate symbolic links.
