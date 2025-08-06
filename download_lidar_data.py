#!/usr/bin/env python3
"""
Download LIDAR Data

This script downloads LIDAR data from the USGS AWS S3 bucket for the Las Animas County area.
"""

import os
import sys
import json
import logging
import boto3
import time
import random
from typing import List, Dict, Any, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_search_results(file_path: str) -> Dict[str, Any]:
    """
    Load search results from a JSON file.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dict[str, Any]: Search results
    """
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading search results: {str(e)}")
        return {}

def initialize_s3_client():
    """
    Initialize the S3 client with credentials from environment variables.
    
    Returns:
        boto3.client: S3 client or None if initialization fails
    """
    try:
        # Get credentials from environment variables
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-west-2')
        
        logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4] if aws_access_key_id else 'None'}... Region={aws_region}")
        
        if not aws_access_key_id or not aws_secret_access_key:
            logger.error("AWS credentials not found in environment variables")
            logger.error("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return None
        
        # Create S3 client with timeout configuration
        logger.info("Creating S3 client with timeout configuration")
        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
            config=boto3.session.Config(
                connect_timeout=10,  # 10 seconds connection timeout
                read_timeout=10,     # 10 seconds read timeout
                retries={'max_attempts': 3}  # Retry configuration
            )
        )
        
        logger.info("S3 client initialized successfully")
        return s3_client
    
    except Exception as e:
        logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
        return None

def download_lidar_file(s3_client, bucket: str, key: str, output_dir: str) -> bool:
    """
    Download a LIDAR file from S3.
    
    Args:
        s3_client: Boto3 S3 client
        bucket: S3 bucket name
        key: S3 object key
        output_dir: Output directory
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Extract filename from key
        filename = os.path.basename(key)
        
        # Create output path
        output_path = os.path.join(output_dir, filename)
        
        # Check if file already exists
        if os.path.exists(output_path):
            logger.info(f"File {filename} already exists, skipping download")
            return True
        
        # Download file
        logger.info(f"Downloading {filename} from {bucket}/{key}")
        s3_client.download_file(
            Bucket=bucket,
            Key=key,
            Filename=output_path,
            ExtraArgs={'RequestPayer': 'requester'}
        )
        
        logger.info(f"Downloaded {filename} to {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error downloading file {key}: {str(e)}", exc_info=True)
        return False

def download_sample_lidar_files(s3_client, results: Dict[str, Any], output_dir: str, max_files_per_project: int = 3) -> List[str]:
    """
    Download sample LIDAR files from search results.
    
    Args:
        s3_client: Boto3 S3 client
        results: Search results
        output_dir: Output directory
        max_files_per_project: Maximum number of files to download per project
        
    Returns:
        List[str]: List of downloaded file paths
    """
    try:
        # Group results by project
        projects = {}
        for item in results.get('items', []):
            project_name = item.get('projectName', 'Unknown')
            if project_name not in projects:
                projects[project_name] = []
            projects[project_name].append(item)
        
        # Download sample files from each project
        downloaded_files = []
        for project_name, items in projects.items():
            # Create project directory
            project_dir = os.path.join(output_dir, project_name)
            os.makedirs(project_dir, exist_ok=True)
            
            # Select random sample of files
            sample_items = random.sample(items, min(max_files_per_project, len(items)))
            
            # Download each file
            for item in sample_items:
                download_url = item.get('downloadURL', '')
                if download_url.startswith('s3://'):
                    # Parse S3 URL
                    parts = download_url.replace('s3://', '').split('/', 1)
                    if len(parts) == 2:
                        bucket = parts[0]
                        key = parts[1]
                        
                        # Download file
                        if download_lidar_file(s3_client, bucket, key, project_dir):
                            downloaded_files.append(os.path.join(project_dir, os.path.basename(key)))
                
                # Sleep to avoid rate limiting
                time.sleep(0.5)
        
        return downloaded_files
    
    except Exception as e:
        logger.error(f"Error downloading sample LIDAR files: {str(e)}", exc_info=True)
        return []

def main():
    """
    Main function.
    """
    try:
        # Set AWS credentials from environment variables
        # Set these in your environment or .env file:
        # export AWS_ACCESS_KEY_ID="your_access_key_here"
        # export AWS_SECRET_ACCESS_KEY="your_secret_key_here"
        # export AWS_REGION="us-west-2"
        
        if not os.environ.get('AWS_ACCESS_KEY_ID'):
            print("Warning: AWS_ACCESS_KEY_ID not set in environment")
        if not os.environ.get('AWS_SECRET_ACCESS_KEY'):
            print("Warning: AWS_SECRET_ACCESS_KEY not set in environment")
        if not os.environ.get('AWS_REGION'):
            os.environ['AWS_REGION'] = 'us-west-2'  # Default region
        
        # Load search results
        results = load_search_results('lidar_index_search_results.json')
        
        if not results:
            logger.error("No search results found")
            return 1
        
        # Initialize S3 client
        s3_client = initialize_s3_client()
        
        if not s3_client:
            logger.error("Failed to initialize S3 client")
            return 1
        
        # Download sample LIDAR files
        output_dir = 'lidar_data'
        downloaded_files = download_sample_lidar_files(s3_client, results, output_dir)
        
        if not downloaded_files:
            logger.error("No files downloaded")
            return 1
        
        logger.info(f"Downloaded {len(downloaded_files)} LIDAR files to {output_dir}")
        
        # Print downloaded files
        for file_path in downloaded_files:
            logger.info(f"  {file_path}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error downloading LIDAR data: {str(e)}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
