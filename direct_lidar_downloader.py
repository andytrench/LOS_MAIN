#!/usr/bin/env python3
"""
Direct LIDAR Downloader

This script downloads LIDAR files listed in the tower_parameters.json file.
It uses the AWS S3 client to download files from the USGS 3DEP AWS S3 bucket.

Usage:
    python direct_lidar_downloader.py [--output-dir OUTPUT_DIR] [--aws-key AWS_KEY] [--aws-secret AWS_SECRET]

Author: Augment Agent
Date: 2025-05-06
"""

import os
import sys
import json
import logging
import argparse
import boto3
import threading
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('lidar_download.log')
    ]
)
logger = logging.getLogger(__name__)

class LidarDownloader:
    """Class for downloading LIDAR files from AWS S3"""

    def __init__(self, output_dir: str, aws_key: str = None, aws_secret: str = None, region: str = 'us-west-2'):
        """
        Initialize the LIDAR downloader

        Args:
            output_dir: Directory to save downloaded files
            aws_key: AWS access key ID
            aws_secret: AWS secret access key
            region: AWS region
        """
        self.output_dir = output_dir
        self.aws_key = aws_key
        self.aws_secret = aws_secret
        self.region = region
        self.s3_client = self._initialize_s3_client()
        self.download_stats = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'skipped': 0
        }

    def _initialize_s3_client(self) -> Optional[boto3.client]:
        """
        Initialize the AWS S3 client

        Returns:
            boto3.client: Initialized S3 client or None if initialization failed
        """
        try:
            # Use provided credentials if available, otherwise use environment variables or AWS config
            if self.aws_key and self.aws_secret:
                s3_client = boto3.client(
                    's3',
                    aws_access_key_id=self.aws_key,
                    aws_secret_access_key=self.aws_secret,
                    region_name=self.region
                )
            else:
                s3_client = boto3.client('s3', region_name=self.region)

            logger.info("Successfully initialized AWS S3 client")
            return s3_client

        except Exception as e:
            logger.error(f"Error initializing AWS S3 client: {str(e)}", exc_info=True)
            return None

    def download_file(self, file_info: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Download a LIDAR file from AWS S3

        Args:
            file_info: Dictionary containing file information

        Returns:
            Tuple[bool, str]: (Success status, Local file path or error message)
        """
        try:
            if not self.s3_client:
                return False, "S3 client not initialized"

            # Extract file information
            filename = file_info.get('filename')
            download_url = file_info.get('download_url')
            project_name = file_info.get('project_name', 'unknown')

            # Skip if no download URL
            if not download_url:
                logger.warning(f"No download URL for file {filename}")
                return False, "No download URL"

            # Create project directory
            project_dir = os.path.join(self.output_dir, project_name)
            os.makedirs(project_dir, exist_ok=True)

            # Output path
            output_path = os.path.join(project_dir, filename)

            # Check if file already exists
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"File {filename} already exists, skipping download")
                return True, output_path

            # Parse download URL
            if download_url.startswith('s3://'):
                # Parse S3 URL (s3://bucket/key)
                parts = download_url.replace('s3://', '').split('/', 1)
                if len(parts) == 2:
                    bucket = parts[0]
                    key = parts[1]
                else:
                    return False, f"Invalid S3 URL format: {download_url}"
            elif download_url.startswith('https://s3'):
                # Parse HTTPS URL (https://s3-region.amazonaws.com/bucket/key)
                # or (https://bucket.s3-region.amazonaws.com/key)
                if 'usgs-lidar-public' in download_url:
                    bucket = 'usgs-lidar-public'
                    key = download_url.split('usgs-lidar-public/', 1)[1]
                elif 'usgs-lidar' in download_url:
                    bucket = 'usgs-lidar'
                    key = download_url.split('usgs-lidar/', 1)[1]
                else:
                    return False, f"Unsupported URL format: {download_url}"
            else:
                return False, f"Unsupported URL format: {download_url}"

            # Download file
            logger.info(f"Downloading {filename} from {bucket}/{key}")

            # Download with requester pays option
            self.s3_client.download_file(
                Bucket=bucket,
                Key=key,
                Filename=output_path,
                ExtraArgs={'RequestPayer': 'requester'}
            )

            logger.info(f"Downloaded {filename} to {output_path}")
            return True, output_path

        except Exception as e:
            error_msg = f"Error downloading file {file_info.get('filename', 'unknown')}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg

def load_tower_parameters(file_path: str = 'tower_parameters.json') -> Optional[Dict[str, Any]]:
    """
    Load the tower_parameters.json file

    Args:
        file_path: Path to the tower_parameters.json file

    Returns:
        Dict[str, Any]: Tower parameters or None if loading failed
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Tower parameters file not found: {file_path}")
            return None

        with open(file_path, 'r') as f:
            data = json.load(f)

        logger.info(f"Successfully loaded tower parameters from {file_path}")
        return data

    except Exception as e:
        logger.error(f"Error loading tower parameters: {str(e)}", exc_info=True)
        return None

def extract_lidar_files(tower_params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract LIDAR file information from tower parameters

    Args:
        tower_params: Tower parameters dictionary

    Returns:
        List[Dict[str, Any]]: List of LIDAR file information
    """
    lidar_files = []

    try:
        # Check if LIDAR data exists
        if 'lidar_data' not in tower_params:
            logger.warning("No LIDAR data found in tower parameters")
            return lidar_files

        # Extract files from each LIDAR project
        for project_name, project_data in tower_params['lidar_data'].items():
            if 'files' not in project_data:
                logger.warning(f"No files found for project {project_name}")
                continue

            # Add files to the list
            for file_data in project_data['files']:
                # Add project name to file data
                file_data['project_name'] = project_name
                lidar_files.append(file_data)

        logger.info(f"Extracted {len(lidar_files)} LIDAR files from tower parameters")
        return lidar_files

    except Exception as e:
        logger.error(f"Error extracting LIDAR files: {str(e)}", exc_info=True)
        return []

def update_tower_parameters(tower_params: Dict[str, Any], file_info: Dict[str, Any], local_path: str) -> Dict[str, Any]:
    """
    Update tower parameters with local file path

    Args:
        tower_params: Tower parameters dictionary
        file_info: File information dictionary
        local_path: Local file path

    Returns:
        Dict[str, Any]: Updated tower parameters
    """
    try:
        project_name = file_info['project_name']
        filename = file_info['filename']

        # Find the file in the tower parameters
        for i, file_data in enumerate(tower_params['lidar_data'][project_name]['files']):
            if file_data['filename'] == filename:
                # Update local file path
                tower_params['lidar_data'][project_name]['files'][i]['local_file_path'] = local_path
                break

        return tower_params

    except Exception as e:
        logger.error(f"Error updating tower parameters: {str(e)}", exc_info=True)
        return tower_params

def save_tower_parameters(tower_params: Dict[str, Any], file_path: str = 'tower_parameters.json') -> bool:
    """
    Save tower parameters to file

    Args:
        tower_params: Tower parameters dictionary
        file_path: Path to save the tower parameters

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create backup of existing file
        if os.path.exists(file_path):
            backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(file_path, backup_path)
            logger.info(f"Created backup of tower parameters at {backup_path}")

        # Save updated parameters
        with open(file_path, 'w') as f:
            json.dump(tower_params, f, indent=2)

        logger.info(f"Saved updated tower parameters to {file_path}")
        return True

    except Exception as e:
        logger.error(f"Error saving tower parameters: {str(e)}", exc_info=True)
        return False

def download_all_lidar_files(tower_params_path: str, output_dir: str, aws_key: str = None, aws_secret: str = None,
                            max_workers: int = 4, save_progress: bool = True) -> Dict[str, int]:
    """
    Download all LIDAR files from tower parameters

    Args:
        tower_params_path: Path to the tower parameters file
        output_dir: Directory to save downloaded files
        aws_key: AWS access key ID
        aws_secret: AWS secret access key
        max_workers: Maximum number of download threads
        save_progress: Whether to save progress to tower parameters file

    Returns:
        Dict[str, int]: Download statistics
    """
    # Load tower parameters
    tower_params = load_tower_parameters(tower_params_path)
    if not tower_params:
        return {'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}

    # Extract LIDAR files
    lidar_files = extract_lidar_files(tower_params)
    if not lidar_files:
        return {'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}

    # Initialize downloader
    downloader = LidarDownloader(output_dir, aws_key, aws_secret)
    if not downloader.s3_client:
        logger.error("Failed to initialize S3 client, aborting download")
        return {'total': 0, 'completed': 0, 'failed': 0, 'skipped': 0}

    # Initialize statistics
    stats = {
        'total': len(lidar_files),
        'completed': 0,
        'failed': 0,
        'skipped': 0
    }

    # Create progress tracking function
    def download_with_progress(file_info):
        nonlocal stats

        # Download file
        success, result = downloader.download_file(file_info)

        # Update statistics
        if success:
            if os.path.exists(result):
                if file_info.get('local_file_path') == result:
                    stats['skipped'] += 1
                else:
                    stats['completed'] += 1

                # Update tower parameters with local file path
                if save_progress:
                    tower_params_updated = update_tower_parameters(tower_params, file_info, result)
                    save_tower_parameters(tower_params_updated, tower_params_path)
        else:
            stats['failed'] += 1

        # Print progress
        completed = stats['completed'] + stats['skipped']
        percent = (completed / stats['total']) * 100 if stats['total'] > 0 else 0
        logger.info(f"Progress: {completed}/{stats['total']} ({percent:.1f}%) - Completed: {stats['completed']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")

        return success, result

    # Download files using thread pool
    logger.info(f"Starting download of {len(lidar_files)} LIDAR files with {max_workers} workers")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Execute all downloads and wait for completion
        list(executor.map(download_with_progress, lidar_files))

    # Print final statistics
    logger.info(f"Download complete - Total: {stats['total']}, Completed: {stats['completed']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")

    return stats

def main():
    """Main function"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Download LIDAR files from tower_parameters.json')
    parser.add_argument('--tower-params', type=str, default='tower_parameters.json',
                        help='Path to tower_parameters.json file (default: tower_parameters.json)')
    parser.add_argument('--output-dir', type=str, default='lidar_data',
                        help='Directory to save downloaded files (default: lidar_data)')
    parser.add_argument('--aws-key', type=str, help='AWS access key ID')
    parser.add_argument('--aws-secret', type=str, help='AWS secret access key')
    parser.add_argument('--max-workers', type=int, default=4,
                        help='Maximum number of download threads (default: 4)')
    parser.add_argument('--no-save-progress', action='store_true',
                        help='Do not save download progress to tower_parameters.json')

    args = parser.parse_args()

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Download all LIDAR files
    stats = download_all_lidar_files(
        args.tower_params,
        args.output_dir,
        args.aws_key,
        args.aws_secret,
        args.max_workers,
        not args.no_save_progress
    )

    # Print final statistics
    print(f"\nDownload Statistics:")
    print(f"  Total files: {stats['total']}")
    print(f"  Successfully downloaded: {stats['completed']}")
    print(f"  Already downloaded (skipped): {stats['skipped']}")
    print(f"  Failed: {stats['failed']}")

    # Return exit code
    if stats['failed'] > 0:
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
