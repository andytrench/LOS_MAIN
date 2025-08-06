#!/usr/bin/env python3
"""
Otsego LiDAR Indexer - A specialized script to index LiDAR files in the FEMA_2019/Otsego directory
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
        logging.FileHandler("otsego_indexer.log"),
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
LAS_HEADER_SIZE = 375  # Size of LAS header in bytes
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5  # seconds
CONNECT_TIMEOUT = 30  # seconds
DOWNLOAD_TIMEOUT = 60  # seconds
DELAY_BETWEEN_FILES = 2  # seconds
BATCH_SIZE = 5  # Process files in batches of 5
USE_HEADER_CACHE = True
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

def extract_las_header(file_path):
    """Extract header information from a LAS file using laspy."""
    basename = os.path.basename(file_path)
    
    # Check cache first if enabled
    if USE_HEADER_CACHE:
        cache_file = os.path.join(HEADER_CACHE_DIR, f"{basename}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_header = json.load(f)
                if VERBOSE:
                    print(f"  📂 Using cached header for: {basename}")
                logger.debug(f"Using cached header for: {basename}")
                return cached_header
            except Exception as e:
                logger.warning(f"Error reading cached header for {basename}: {e}")
                # Continue with download if cache read fails
    
    max_retries = 5
    retry_delay = 5
    header_timeout = 60
    
    for attempt in range(max_retries):
        ftp = None
        try:
            if VERBOSE and attempt > 0:
                print(f"  🔄 Retry {attempt}/{max_retries} downloading header for {basename}")
            
            # Get a fresh FTP connection for each attempt
            ftp = get_ftp_connection()
            if not ftp:
                logger.error(f"Failed to establish FTP connection on attempt {attempt+1}")
                time.sleep(retry_delay)
                continue
                
            header_bytes = io.BytesIO()
            ftp.voidcmd('TYPE I')  # Binary mode
            
            # Set a shorter timeout specifically for the data connection
            ftp.sock.settimeout(header_timeout)
            
            # Start a timer to track download time
            start_time = time.time()
            
            # Download just the header portion with a timeout
            try:
                ftp.retrbinary(
                    f'RETR {file_path}',
                    lambda data: header_bytes.write(data) 
                    if header_bytes.tell() < LAS_HEADER_SIZE else None,
                    blocksize=8192
                )
            except ftplib.error_temp as e:
                if "426" in str(e):  # "426 Failure writing network stream" is expected when we abort
                    pass
                else:
                    raise
            
            download_time = time.time() - start_time
            if VERBOSE:
                print(f"  ✅ Downloaded header in {download_time:.2f}s: {basename}")
            
            # Check if we got enough data
            if header_bytes.tell() < 100:  # Minimum size for a valid LAS header
                logger.error(f"Incomplete header data for {file_path}: got {header_bytes.tell()} bytes")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
            
            try:
                # Parse the header
                header_bytes.seek(0)
                with laspy.open(header_bytes) as las:
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
                    
                    # Cache the result if caching is enabled
                    if USE_HEADER_CACHE:
                        try:
                            with open(os.path.join(HEADER_CACHE_DIR, f"{basename}.json"), 'w') as f:
                                json.dump(result, f)
                            logger.debug(f"Cached header for: {basename}")
                        except Exception as e:
                            logger.warning(f"Error caching header for {basename}: {e}")
                    
                    return result
                    
            except Exception as e:
                logger.error(f"Error parsing LAS header for {file_path}: {str(e)}")
                if VERBOSE:
                    print(f"  ❌ Error parsing LAS header: {str(e)}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    continue
                return None
                
        except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
            logger.error(f"Error downloading header for {file_path} (attempt {attempt+1}): {str(e)}")
            if VERBOSE:
                print(f"  ❌ Error downloading header (attempt {attempt+1}): {str(e)}")
            time.sleep(retry_delay)
        finally:
            if ftp:
                try:
                    ftp.quit()
                except:
                    pass
    
    logger.error(f"Failed to download header after {max_retries} attempts: {file_path}")
    if VERBOSE:
        print(f"  ❌ Failed to download header after {max_retries} attempts")
    return None

def list_las_files():
    """List all LAS files in the FEMA_2019/Otsego directory."""
    las_files = []
    
    for attempt in range(RETRY_ATTEMPTS):
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
    
    logger.error(f"Failed to list files after {RETRY_ATTEMPTS} attempts")
    print(f"❌ Failed to list files after {RETRY_ATTEMPTS} attempts")
    return []

def process_las_files(las_files, max_files=None):
    """Process LAS files in batches."""
    results = []
    
    # Limit the number of files if specified
    if max_files and max_files > 0:
        las_files = las_files[:max_files]
    
    total_files = len(las_files)
    logger.info(f"Processing {total_files} LAS files...")
    print(f"🔄 Processing {total_files} LAS files...")
    
    # Process files in batches
    for i in range(0, total_files, BATCH_SIZE):
        batch = las_files[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total_files + BATCH_SIZE - 1) // BATCH_SIZE
        
        logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
        print(f"⏳ Processing batch {batch_num}/{total_batches} ({len(batch)} files)")
        
        for j, filename in enumerate(batch):
            file_path = f"{FTP_PATH}/{filename}"
            file_num = i + j + 1
            logger.info(f"Processing file {file_num}/{total_files}: {filename}")
            print(f"📄 Processing file {file_num}/{total_files}: {filename}")
            
            # Get file info
            for attempt in range(RETRY_ATTEMPTS):
                try:
                    ftp = get_ftp_connection()
                    if not ftp:
                        logger.error(f"Failed to establish FTP connection on attempt {attempt+1}")
                        time.sleep(RETRY_DELAY)
                        continue
                    
                    # Get file size and date
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
                    
                    # Extract header information
                    header_info = extract_las_header(file_path)
                    
                    if header_info:
                        file_info = {
                            "path": f"ftp://{FTP_HOST}{file_path}",
                            "size": size,
                            "date": date_str,
                            "bounds": header_info["bounds"],
                            "version": header_info["version"],
                            "point_count": header_info.get("point_count", 0)
                        }
                        
                        # Add UTM zone if available
                        if "utm_zone" in header_info:
                            file_info["utm_zone"] = header_info["utm_zone"]
                            
                        results.append(file_info)
                        logger.info(f"Successfully processed: {filename}")
                        print(f"  ✅ Successfully processed: {filename}")
                    else:
                        logger.warning(f"Skipping file due to header extraction failure: {filename}")
                        print(f"  ⚠️ Skipping file due to header extraction failure: {filename}")
                    
                    # Add delay between files to prevent FTP lockups
                    time.sleep(DELAY_BETWEEN_FILES)
                    break
                    
                except (ftplib.error_perm, ftplib.error_temp, socket.timeout, socket.error, OSError) as e:
                    logger.error(f"Error processing {filename} (attempt {attempt+1}): {str(e)}")
                    print(f"  ❌ Error processing (attempt {attempt+1}): {str(e)}")
                    time.sleep(RETRY_DELAY)
        
        # Save intermediate results after each batch
        save_results(results)
    
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
    parser.add_argument('--batch-size', type=int, default=BATCH_SIZE, help='Number of files to process in each batch')
    parser.add_argument('--delay', type=float, default=DELAY_BETWEEN_FILES, help='Delay between file processing in seconds')
    args = parser.parse_args()
    
    # Update global settings from arguments
    global BATCH_SIZE, DELAY_BETWEEN_FILES
    BATCH_SIZE = args.batch_size
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
