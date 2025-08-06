# GDAL in LOSTool: Implementation and Maintenance Guide

## Overview

This document details how GDAL is used in the LOSTool application, potential issues that may arise (especially on macOS M1/M2 systems), and best practices for maintaining GDAL functionality.

## GDAL Usage in LOSTool

### Core Functionality

LOSTool uses GDAL for several critical functions:

1. **LIDAR Data Processing**
   - Reading and processing LAZ/LAS files
   - Converting between different coordinate systems
   - Generating elevation profiles

2. **Geospatial Analysis**
   - Working with shapefiles and GeoJSON
   - Spatial queries and operations
   - Coordinate transformations

3. **Map Visualization**
   - Rendering geospatial data
   - Coordinate system conversions for display

### Key Files Using GDAL

The following files in our codebase make direct use of GDAL:

- `utilities/elevation.py`: Uses GDAL for elevation data processing
- `utilities/lidar_map_visualization.py`: Uses GDAL for map visualization
- `utilities/point_search.py`: Uses GDAL for LIDAR point search
- `vegetation_profile.py`: Uses GDAL for vegetation analysis
- `state_boundaries.py`: Uses GDAL for state boundary processing

## macOS M1/M2 Specific Issues

### Known Issues

On macOS with Apple Silicon (M1/M2), the following GDAL-related issues are common:

1. **Library Path Mismatches**
   - Python GDAL package looks for libraries in `/opt/homebrew/opt/gdal/lib/`
   - Homebrew installs libraries in `/opt/homebrew/Cellar/gdal/[version]/lib/`

2. **Version Mismatches**
   - Python GDAL package may expect a specific library version (e.g., `libgdal.36.dylib`)
   - Homebrew may install a newer version (e.g., `libgdal.37.dylib`)

3. **Dependency Issues**
   - GDAL depends on other libraries like poppler, proj, etc.
   - These dependencies may also have version mismatches

### Solution: Symbolic Links

We use symbolic links to resolve these issues:

```bash
# For GDAL
sudo ln -sf /opt/homebrew/Cellar/gdal/3.10.3/lib/libgdal.36.dylib /opt/homebrew/opt/gdal/lib/libgdal.36.dylib

# For dependencies like poppler
sudo ln -sf /opt/homebrew/Cellar/poppler/25.04.0/lib/libpoppler.148.dylib /opt/homebrew/opt/poppler/lib/libpoppler.148.dylib
```

The `fix_gdal.sh` script automates this process.

## Maintaining GDAL in LOSTool

### Version Management

1. **Current GDAL Version**
   - Homebrew GDAL: 3.10.3 / 3.11.0
   - Python GDAL package: 3.10.2

2. **Version Compatibility**
   - The Python GDAL package should be compatible with the Homebrew GDAL version
   - Minor version differences (e.g., 3.10.2 vs 3.10.3) are usually acceptable
   - Major version differences (e.g., 3.10.x vs 3.11.x) may require updates

### Updating GDAL

When updating GDAL:

1. **Update Homebrew GDAL**
   ```bash
   brew update
   brew upgrade gdal
   ```

2. **Check New Version**
   ```bash
   gdal-config --version
   ```

3. **Update Python GDAL Package**
   ```bash
   pip install --force-reinstall gdal==$(gdal-config --version)
   ```

4. **Fix Library Links**
   ```bash
   ./fix_gdal.sh
   ```

5. **Test GDAL Functionality**
   ```bash
   python test_gdal_full.py
   ```

6. **Update Documentation**
   - Update this document with new version information
   - Note any changes in behavior or requirements

### Automated Fixes

We've implemented several automated fixes to handle GDAL issues:

1. **fix_gdal.sh**
   - Creates symbolic links for GDAL and its dependencies
   - Automatically detects installed versions
   - Should be run after Homebrew updates

2. **run_with_gdal_fix.sh**
   - Runs the GDAL fix before starting the application
   - Ensures GDAL works correctly every time

3. **Virtual Environment Activation Hook**
   - Checks GDAL functionality when activating the virtual environment
   - Automatically runs the fix if needed

## Best Practices for Developers

### Setting Up a Development Environment

1. **Install Homebrew GDAL First**
   ```bash
   brew install gdal
   ```

2. **Create a Virtual Environment**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. **Install Python GDAL Package**
   ```bash
   pip install gdal==$(gdal-config --version)
   ```

4. **Run the GDAL Fix Script**
   ```bash
   ./fix_gdal.sh
   ```

5. **Install Other Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

### Testing GDAL Functionality

Always test GDAL functionality after environment changes:

```bash
# Basic test
python -c "from osgeo import gdal; print(f'GDAL version: {gdal.VersionInfo()}')"

# Comprehensive test
python test_gdal_full.py
```

### Troubleshooting

If GDAL issues occur:

1. **Check Library Paths**
   ```bash
   otool -L /opt/homebrew/Cellar/gdal/*/lib/libgdal.dylib
   ```

2. **Check for Missing Libraries**
   ```bash
   find /opt/homebrew -name "libgdal*.dylib" | sort
   find /opt/homebrew -name "libpoppler*.dylib" | sort
   ```

3. **Run the Fix Script**
   ```bash
   ./fix_gdal.sh
   ```

4. **Reinstall Python GDAL Package**
   ```bash
   pip uninstall gdal
   pip install gdal==$(gdal-config --version)
   ```

## Conclusion

GDAL is a critical component of LOSTool, especially for geospatial data processing and visualization. By following the guidelines in this document, you can avoid common GDAL issues and ensure the application works correctly, particularly on macOS M1/M2 systems.

Remember to run the GDAL fix script after Homebrew updates and test GDAL functionality regularly to catch issues early.
