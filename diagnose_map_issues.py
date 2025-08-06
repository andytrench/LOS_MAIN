#!/usr/bin/env python3
"""
Diagnostic script for map view issues
"""

import os
import sys
import json
import logging
import subprocess
import importlib.util

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies():
    """Check if all required dependencies are installed"""
    required_packages = ['osmium', 'psycopg2', 'shapely', 'requests']
    missing_packages = []
    
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
        else:
            logger.info(f"✅ {package} is installed")
    
    if missing_packages:
        logger.warning(f"❌ Missing packages: {missing_packages}")
        logger.info("Install missing packages with:")
        for package in missing_packages:
            if package == 'psycopg2':
                logger.info(f"  pip install psycopg2-binary")
            else:
                logger.info(f"  pip install {package}")
    else:
        logger.info("✅ All required packages are installed")
    
    return len(missing_packages) == 0

def check_files():
    """Check if required files exist"""
    required_files = [
        'tower_parameters.json',
        'templates/map.html',
        'static/js/map_client.js',
        'static/js/map_providers.js',
        'map_server.py',
        'LOS_map_view.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            logger.info(f"✅ {file_path} exists")
        else:
            missing_files.append(file_path)
            logger.error(f"❌ {file_path} missing")
    
    return len(missing_files) == 0

def check_tower_parameters():
    """Check tower_parameters.json structure"""
    try:
        with open('tower_parameters.json', 'r') as f:
            data = json.load(f)
        
        required_sections = ['site_A', 'site_B', 'general_parameters']
        missing_sections = []
        
        for section in required_sections:
            if section in data:
                logger.info(f"✅ {section} section exists")
            else:
                missing_sections.append(section)
                logger.error(f"❌ {section} section missing")
        
        # Check frequency
        if 'general_parameters' in data and 'frequency_ghz' in data['general_parameters']:
            freq = data['general_parameters']['frequency_ghz']
            logger.info(f"✅ Frequency: {freq} GHz")
        else:
            logger.warning("❌ frequency_ghz missing from general_parameters")
        
        # Check coordinates
        for site_name, site_key in [('Donor', 'site_A'), ('Recipient', 'site_B')]:
            if site_key in data:
                site = data[site_key]
                if 'adjusted_latitude' in site and 'adjusted_longitude' in site:
                    lat = site['adjusted_latitude']
                    lng = site['adjusted_longitude']
                    logger.info(f"✅ {site_name} coordinates: {lat}, {lng}")
                else:
                    logger.warning(f"❌ {site_name} missing adjusted coordinates")
        
        return len(missing_sections) == 0
        
    except FileNotFoundError:
        logger.error("❌ tower_parameters.json not found")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"❌ tower_parameters.json has invalid JSON: {e}")
        return False

def check_environment():
    """Check environment variables"""
    api_key = os.getenv('GOOGLE_MAPS_API_KEY')
    mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN')
    
    if api_key:
        logger.info(f"✅ Google Maps API key found (length: {len(api_key)})")
    else:
        logger.warning("⚠️ Google Maps API key not set (optional for Leaflet)")
    
    if mapbox_token:
        logger.info(f"✅ Mapbox token found (length: {len(mapbox_token)})")
    else:
        logger.warning("⚠️ Mapbox token not set (optional)")

def check_port_availability():
    """Check if default port 9000 is available"""
    import socket
    
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 9000))
        logger.info("✅ Port 9000 is available")
        return True
    except OSError:
        logger.warning("⚠️ Port 9000 is in use, server will find alternative port")
        return False

def run_diagnostics():
    """Run all diagnostic checks"""
    logger.info("=" * 50)
    logger.info("Map View Diagnostic Tool")
    logger.info("=" * 50)
    
    logger.info("\n1. Checking Dependencies...")
    deps_ok = check_dependencies()
    
    logger.info("\n2. Checking Required Files...")
    files_ok = check_files()
    
    logger.info("\n3. Checking tower_parameters.json...")
    params_ok = check_tower_parameters()
    
    logger.info("\n4. Checking Environment Variables...")
    check_environment()
    
    logger.info("\n5. Checking Port Availability...")
    check_port_availability()
    
    logger.info("\n" + "=" * 50)
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info("=" * 50)
    
    if deps_ok and files_ok and params_ok:
        logger.info("✅ All critical checks passed! Map view should work.")
    else:
        logger.error("❌ Some issues found. Please fix the errors above.")
    
    logger.info("\nIf issues persist, check browser console for JavaScript errors.")
    logger.info("Map server typically runs at: http://127.0.0.1:9000/map")

if __name__ == "__main__":
    run_diagnostics() 