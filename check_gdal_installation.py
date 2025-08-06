#!/usr/bin/env python3
"""
GDAL Installation Checker

This script performs a comprehensive check of your GDAL installation,
including version information, available drivers, and dependencies.
It helps diagnose issues with GDAL on macOS, especially on M1/M2 systems.
"""

import os
import sys
import subprocess
import platform
from pathlib import Path
import importlib.util

def print_section(title):
    """Print a section title"""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)

def run_command(command):
    """Run a shell command and return the output"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            check=True, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        return f"Error: {e.stderr.strip()}"

def check_package_installed(package_name):
    """Check if a Python package is installed"""
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def check_system_info():
    """Check system information"""
    print_section("System Information")
    print(f"Platform: {platform.platform()}")
    print(f"Python Version: {platform.python_version()}")
    print(f"Python Executable: {sys.executable}")
    
    # Check if running in a virtual environment
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        print(f"Virtual Environment: Yes ({sys.prefix})")
    else:
        print("Virtual Environment: No")
    
    # Check if running on Apple Silicon
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        print("Processor: Apple Silicon (M1/M2)")
    else:
        print(f"Processor: {platform.processor()}")

def check_homebrew_gdal():
    """Check Homebrew GDAL installation"""
    print_section("Homebrew GDAL Installation")
    
    # Check if Homebrew is installed
    brew_path = run_command("which brew")
    if "Error" in brew_path:
        print("Homebrew: Not installed")
        return
    
    print(f"Homebrew: Installed at {brew_path}")
    
    # Check GDAL installation
    gdal_info = run_command("brew info gdal")
    if "Not installed" in gdal_info:
        print("GDAL: Not installed via Homebrew")
        return
    
    # Extract GDAL version from brew info
    for line in gdal_info.split("\n"):
        if line.startswith("==> gdal:"):
            version = line.split("stable")[1].split("(")[0].strip()
            print(f"GDAL Version: {version}")
            break
    
    # Check GDAL installation path
    gdal_path = run_command("brew --prefix gdal")
    print(f"GDAL Installation Path: {gdal_path}")
    
    # Check gdal-config
    gdal_config_path = run_command("which gdal-config")
    if "Error" not in gdal_config_path:
        gdal_config_version = run_command("gdal-config --version")
        print(f"gdal-config Version: {gdal_config_version}")
    else:
        print("gdal-config: Not found")

def check_python_gdal():
    """Check Python GDAL installation"""
    print_section("Python GDAL Installation")
    
    # Check if GDAL Python package is installed
    if not check_package_installed("osgeo"):
        print("GDAL Python Package: Not installed")
        return
    
    print("GDAL Python Package: Installed")
    
    # Import GDAL and check version
    try:
        from osgeo import gdal, ogr, osr
        print(f"GDAL Python Version: {gdal.VersionInfo()}")
        print(f"GDAL Raster Driver Count: {gdal.GetDriverCount()}")
        print(f"OGR Vector Driver Count: {ogr.GetDriverCount()}")
        
        # Test coordinate transformation
        try:
            source = osr.SpatialReference()
            source.ImportFromEPSG(4326)
            target = osr.SpatialReference()
            target.ImportFromEPSG(3857)
            transform = osr.CoordinateTransformation(source, target)
            x, y, z = transform.TransformPoint(-74.0060, 40.7128)
            print(f"Coordinate Transformation Test: Successful ({x:.2f}, {y:.2f})")
        except Exception as e:
            print(f"Coordinate Transformation Test: Failed ({e})")
    except Exception as e:
        print(f"Error importing GDAL: {e}")

def check_gdal_dependencies():
    """Check GDAL dependencies"""
    print_section("GDAL Dependencies")
    
    # Check if otool is available (macOS only)
    if platform.system() != "Darwin":
        print("Dependency checking is only available on macOS")
        return
    
    # Find GDAL library
    gdal_lib_path = run_command("find /opt/homebrew -name 'libgdal.dylib' | head -n 1")
    if "Error" in gdal_lib_path or not gdal_lib_path:
        print("GDAL library not found")
        return
    
    print(f"GDAL Library: {gdal_lib_path}")
    
    # Check dependencies
    dependencies = run_command(f"otool -L {gdal_lib_path}")
    print("\nDependencies:")
    for line in dependencies.split("\n")[1:]:  # Skip the first line (the library itself)
        dep = line.strip().split(" ")[0]
        if dep.startswith("/opt/homebrew"):
            # Check if the dependency exists
            if os.path.exists(dep):
                print(f"  ✅ {dep}")
            else:
                print(f"  ❌ {dep} (missing)")
        else:
            print(f"  ✓ {dep}")

def check_library_paths():
    """Check library paths"""
    print_section("Library Paths")
    
    # Check GDAL libraries
    print("GDAL Libraries:")
    gdal_libs = run_command("find /opt/homebrew -name 'libgdal*.dylib' | sort")
    for lib in gdal_libs.split("\n"):
        if lib:
            print(f"  {lib}")
    
    # Check poppler libraries (common dependency)
    print("\nPoppler Libraries:")
    poppler_libs = run_command("find /opt/homebrew -name 'libpoppler*.dylib' | grep -v 'cpp\\|glib' | sort")
    for lib in poppler_libs.split("\n"):
        if lib:
            print(f"  {lib}")
    
    # Check symbolic links
    print("\nSymbolic Links:")
    gdal_links = run_command("find /opt/homebrew/opt/gdal -type l -name 'libgdal*.dylib' 2>/dev/null || echo 'None found'")
    for link in gdal_links.split("\n"):
        if link and "None found" not in link:
            target = os.path.realpath(link)
            print(f"  {link} -> {target}")
    
    poppler_links = run_command("find /opt/homebrew/opt/poppler -type l -name 'libpoppler*.dylib' 2>/dev/null || echo 'None found'")
    for link in poppler_links.split("\n"):
        if link and "None found" not in link:
            target = os.path.realpath(link)
            print(f"  {link} -> {target}")

def check_environment_variables():
    """Check environment variables"""
    print_section("Environment Variables")
    
    # Check GDAL_DATA
    gdal_data = os.environ.get("GDAL_DATA", "Not set")
    print(f"GDAL_DATA: {gdal_data}")
    
    # Check PROJ_LIB
    proj_lib = os.environ.get("PROJ_LIB", "Not set")
    print(f"PROJ_LIB: {proj_lib}")
    
    # Check PATH
    path = os.environ.get("PATH", "Not set")
    print(f"PATH includes /opt/homebrew/bin: {'Yes' if '/opt/homebrew/bin' in path else 'No'}")
    
    # Check DYLD_LIBRARY_PATH
    dyld_library_path = os.environ.get("DYLD_LIBRARY_PATH", "Not set")
    print(f"DYLD_LIBRARY_PATH: {dyld_library_path}")

def main():
    """Main function"""
    print("GDAL Installation Checker")
    print("This script checks your GDAL installation and helps diagnose issues.")
    
    check_system_info()
    check_homebrew_gdal()
    check_python_gdal()
    check_gdal_dependencies()
    check_library_paths()
    check_environment_variables()
    
    print_section("Summary")
    
    # Check if GDAL is working
    try:
        from osgeo import gdal
        print("✅ GDAL is working correctly!")
    except Exception as e:
        print(f"❌ GDAL is not working: {e}")
        print("\nRecommended actions:")
        print("1. Run the fix_gdal.sh script")
        print("2. Reinstall the Python GDAL package")
        print("3. Check for missing dependencies")

if __name__ == "__main__":
    main()
