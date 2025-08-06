#!/usr/bin/env python3
"""
Otsego Specific Indexer - A specialized script to index LiDAR files in the FEMA_2019/Otsego directory
"""

import os
import json
import time
import ftplib
import logging
import argparse
import re
from datetime import datetime
import socket
import io

try:
    import laspy
except ImportError:
    print("Installing laspy library...")
    import subprocess
    subprocess.check_call(["pip", "install", "laspy"])
    import laspy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("otsego_specific_indexer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

# Constants
FTP_HOST = "ftp.gis.ny.gov"
FTP_PATH = "/elevation/LIDAR/FEMA_2019/Otsego"
HEADER_CACHE_DIR = "header_cache"
OUTPUT_DIR = "lidar_index/FEMA_2019_Otsego"
TEMP_DIR = "temp_downloads"
BATCH_SIZE = 1  # Process one file at a time
DELAY_BETWEEN_FILES = 5  # 5 seconds between files
MAX_RETRIES = 5
RETRY_DELAY = 5
CONNECT_TIMEOUT = 30
DOWNLOAD_TIMEOUT = 60
VERBOSE = True

# Create output directories
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(HEADER_CACHE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

def get_ftp_connection():
    """Establish a connection to the FTP server with appropriate timeout settings."""
    logger.debug("FTP connection attempt...")
    if VERBOSE:
        print("  🔄 FTP connection attempt...")
    
    # Set socket timeout
    socket.setdefaulttimeout(CONNECT_TIMEOUT)
    
    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=CONNECT_TIMEOUT)
        ftp.login()
        ftp.set_pasv(True)  # Use passive mode for better firewall compatibility
        logger.debug("FTP connection established")
        if VERBOSE:
            print("  ✅ FTP connection established")
        return ftp
    except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
        logger.error(f"FTP connection error: {str(e)}")
        if VERBOSE:
            print(f"  ❌ FTP connection error: {str(e)}")
        return None

def download_file(file_path, local_path):
    """Download a file from FTP server to local path."""
    for attempt in range(MAX_RETRIES):
        try:
            ftp = get_ftp_connection()
            if not ftp:
                logger.error(f"Failed to establish FTP connection on attempt {attempt+1}")
                time.sleep(RETRY_DELAY)
                continue
            
            # Set a timeout for the data connection
            ftp.sock.settimeout(DOWNLOAD_TIMEOUT)
            
            # Start a timer to track download time
            start_time = time.time()
            
            # Download the file
            with open(local_path, 'wb') as f:
                ftp.retrbinary(f'RETR {file_path}', f.write, blocksize=8192)
            
            download_time = time.time() - start_time
            logger.info(f"Downloaded file in {download_time:.2f}s: {os.path.basename(file_path)}")
            if VERBOSE:
                print(f"  ⬇️ Downloaded file in {download_time:.2f}s: {os.path.basename(file_path)}")
            
            ftp.quit()
            return True
            
        except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
            logger.error(f"Error downloading file {file_path} (attempt {attempt+1}): {str(e)}")
            if VERBOSE:
                print(f"  ❌ Error downloading file (attempt {attempt+1}): {str(e)}")
            
            # Clean up any partial downloads
            if os.path.exists(local_path):
                os.remove(local_path)
            
            time.sleep(RETRY_DELAY)
            
            # Try to close the connection
            try:
                if ftp:
                    ftp.quit()
            except:
                pass
    
    logger.error(f"Failed to download file after {MAX_RETRIES} attempts: {file_path}")
    if VERBOSE:
        print(f"  ❌ Failed to download file after {MAX_RETRIES} attempts")
    return False

def extract_las_header(file_path):
    """Extract header information from a LAS file."""
    basename = os.path.basename(file_path)
    
    # Check if we have a cached header
    cache_file = os.path.join(HEADER_CACHE_DIR, f"{basename}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r') as f:
                cached_header = json.load(f)
            logger.debug(f"Using cached header for: {basename}")
            if VERBOSE:
                print(f"  📂 Using cached header for: {basename}")
            return cached_header
        except Exception as e:
            logger.warning(f"Error reading cached header for {basename}: {e}")
    
    # Download the file to a temporary location
    temp_file = os.path.join(TEMP_DIR, basename)
    if download_file(file_path, temp_file):
        try:
            # Extract header information using laspy
            with laspy.open(temp_file) as las:
                header = las.header
                result = {
                    "bounds": {
                        "min_x": float(header.x_min),
                        "min_y": float(header.y_min),
                        "min_z": float(header.z_min),
                        "max_x": float(header.x_max),
                        "max_y": float(header.y_max),
                        "max_z": float(header.z_max)
                    },
                    "point_count": int(header.point_count),
                    "version": f"{header.version.major}.{header.version.minor}"
                }
                
                # Try to extract UTM zone from filename pattern like 18TWM580935.las
                utm_match = re.match(r'(\d{2})T[A-Z]{2}', basename)
                if utm_match:
                    result["utm_zone"] = int(utm_match.group(1))
                
                # Cache the result
                with open(cache_file, 'w') as f:
                    json.dump(result, f)
                
                logger.info(f"Successfully extracted header for: {basename}")
                if VERBOSE:
                    print(f"  ✅ Successfully extracted header for: {basename}")
                
                # Remove the temporary file
                os.remove(temp_file)
                
                return result
                
        except Exception as e:
            logger.error(f"Error extracting header from {basename}: {str(e)}")
            if VERBOSE:
                print(f"  ❌ Error extracting header: {str(e)}")
            
            # Clean up
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    return None

def list_las_files():
    """List all LAS files in the FEMA_2019/Otsego directory."""
    las_files = []
    
    for attempt in range(MAX_RETRIES):
        try:
            ftp = get_ftp_connection()
            if not ftp:
                logger.error(f"Failed to establish FTP connection on attempt {attempt+1}")
                time.sleep(RETRY_DELAY)
                continue
            
            # Navigate to the directory
            ftp.cwd(FTP_PATH)
            
            # List all files
            files = ftp.nlst()
            
            # Filter for LAS files
            las_files = [f for f in files if f.lower().endswith('.las')]
            
            ftp.quit()
            logger.info(f"Found {len(las_files)} LAS files in {FTP_PATH}")
            print(f"📋 Found {len(las_files)} LAS files in {FTP_PATH}")
            return las_files
            
        except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
            logger.error(f"Error listing files (attempt {attempt+1}): {str(e)}")
            print(f"❌ Error listing files (attempt {attempt+1}): {str(e)}")
            time.sleep(RETRY_DELAY)
            
            # Try to close the connection
            try:
                if ftp:
                    ftp.quit()
            except:
                pass
    
    logger.error(f"Failed to list files after {MAX_RETRIES} attempts")
    print(f"❌ Failed to list files after {MAX_RETRIES} attempts")
    return []

def get_file_info(filename):
    """Get file information from FTP server."""
    file_path = f"{FTP_PATH}/{filename}"
    
    for attempt in range(MAX_RETRIES):
        try:
            ftp = get_ftp_connection()
            if not ftp:
                logger.error(f"Failed to establish FTP connection on attempt {attempt+1}")
                time.sleep(RETRY_DELAY)
                continue
            
            # Get file size
            ftp.voidcmd('TYPE I')  # Binary mode
            size = ftp.size(file_path)
            
            # Get modification time
            ftp.voidcmd('TYPE A')  # ASCII mode
            try:
                mdtm_resp = ftp.sendcmd(f'MDTM {file_path}')
                date_str = mdtm_resp[4:]  # Remove the response code
            except:
                date_str = ""  # If MDTM command fails
            
            ftp.quit()
            
            return {
                "size": size,
                "date": date_str
            }
            
        except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
            logger.error(f"Error getting file info for {filename} (attempt {attempt+1}): {str(e)}")
            if VERBOSE:
                print(f"  ❌ Error getting file info (attempt {attempt+1}): {str(e)}")
            time.sleep(RETRY_DELAY)
            
            # Try to close the connection
            try:
                if ftp:
                    ftp.quit()
            except:
                pass
    
    logger.error(f"Failed to get file info after {MAX_RETRIES} attempts: {filename}")
    if VERBOSE:
        print(f"  ❌ Failed to get file info after {MAX_RETRIES} attempts")
    return None

def process_las_files(las_files, max_files=None):
    """Process LAS files one at a time."""
    results = []
    
    # Limit the number of files if specified
    if max_files and max_files > 0:
        las_files = las_files[:max_files]
    
    total_files = len(las_files)
    logger.info(f"Processing {total_files} LAS files...")
    print(f"🔄 Processing {total_files} LAS files...")
    
    for i, filename in enumerate(las_files):
        file_path = f"{FTP_PATH}/{filename}"
        logger.info(f"Processing file {i+1}/{total_files}: {filename}")
        print(f"📄 Processing file {i+1}/{total_files}: {filename}")
        
        # Get file info
        file_info = get_file_info(filename)
        if not file_info:
            logger.warning(f"Skipping file due to file info retrieval failure: {filename}")
            print(f"  ⚠️ Skipping file due to file info retrieval failure: {filename}")
            continue
        
        # Extract header information
        header_info = extract_las_header(file_path)
        
        if header_info:
            file_data = {
                "path": f"ftp://{FTP_HOST}{file_path}",
                "size": file_info["size"],
                "date": file_info["date"],
                "bounds": header_info["bounds"],
                "version": header_info["version"],
                "point_count": header_info.get("point_count", 0)
            }
            
            # Add UTM zone if available
            if "utm_zone" in header_info:
                file_data["utm_zone"] = header_info["utm_zone"]
                
            results.append(file_data)
            logger.info(f"Successfully processed: {filename}")
            print(f"  ✅ Successfully processed: {filename}")
        else:
            logger.warning(f"Skipping file due to header extraction failure: {filename}")
            print(f"  ⚠️ Skipping file due to header extraction failure: {filename}")
        
        # Save intermediate results every 10 files
        if (i + 1) % 10 == 0 or i == total_files - 1:
            save_results(results)
        
        # Add delay between files to prevent FTP lockups
        time.sleep(DELAY_BETWEEN_FILES)
    
    return results

def save_results(results):
    """Save the results to a JSON file."""
    output_data = {
        "name": "FEMA_2019_Otsego",
        "date": datetime.now().strftime("%b %d %Y"),
        "files": results,
        "coordinate_system": {
            "projection": "NAD_1983_UTM_Zone_18N",  # Assuming same as other datasets
            "datum": "D_North_American_1983",
            "utm_zone": "18N"
        }
    }
    
    output_file = os.path.join(OUTPUT_DIR, "index.json")
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    logger.info(f"Saved results to {output_file}")
    print(f"💾 Saved results to {output_file}")

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='Index LiDAR files in FEMA_2019/Otsego directory')
    parser.add_argument('--max-files', type=int, default=None, help='Maximum number of files to process')
    parser.add_argument('--delay', type=float, default=DELAY_BETWEEN_FILES, help='Delay between file processing in seconds')
    args = parser.parse_args()
    
    # Update global settings from arguments
    global DELAY_BETWEEN_FILES
    DELAY_BETWEEN_FILES = args.delay
    
    print("================================================================================")
    print("🚀 Starting Otsego LiDAR indexing...")
    print("================================================================================")
    logger.info("Starting Otsego LiDAR indexing...")
    
    # List LAS files
    las_files = list_las_files()
    
    if not las_files:
        logger.error("No LAS files found. Exiting.")
        print("❌ No LAS files found. Exiting.")
        return
    
    # Process files
    results = process_las_files(las_files, args.max_files)
    
    # Save final results
    save_results(results)
    
    logger.info("Indexing complete!")
    print("================================================================================")
    print("✅ Indexing complete!")
    print("================================================================================")

if __name__ == "__main__":
    main()
