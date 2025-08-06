"""
AWS S3 LIDAR Downloader Utility

This module provides functions to download LIDAR data from the USGS 3DEP AWS S3 bucket.
It uses the AWS SDK (boto3) to access the requester pays bucket and download LIDAR files.
"""

import boto3
import logging
import os
import threading
import queue
import time
from typing import List, Dict, Any, Optional, Callable
from tkinter import messagebox

# Configure logging
logger = logging.getLogger(__name__)

class AWSDownloader:
    """
    Class for downloading LIDAR data from AWS S3 bucket.
    """
    
    def __init__(self, output_dir: str, progress_callback: Optional[Callable] = None):
        """
        Initialize the AWS downloader.
        
        Args:
            output_dir: Directory to save downloaded files
            progress_callback: Callback function to update progress
        """
        self.output_dir = output_dir
        self.progress_callback = progress_callback
        self.download_queue = queue.Queue()
        self.download_threads = []
        self.stop_event = threading.Event()
        self.s3_client = self._initialize_s3_client()
    
    def _initialize_s3_client(self):
        """
        Initialize the S3 client with credentials from environment variables.
        
        Returns:
            boto3.client: Configured S3 client
        """
        try:
            # Get credentials from environment variables
            aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            aws_region = os.environ.get('AWS_REGION', 'us-west-2')
            
            if not aws_access_key_id or not aws_secret_access_key:
                logger.error("AWS credentials not found in environment variables")
                return None
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region
            )
            
            logger.info("S3 client initialized successfully")
            return s3_client
        
        except Exception as e:
            logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
            return None
    
    def add_file_to_queue(self, file_info: Dict[str, Any]):
        """
        Add a file to the download queue.
        
        Args:
            file_info: Dictionary containing file information
        """
        try:
            if not self.s3_client:
                logger.error("S3 client not initialized, cannot add file to queue")
                return
            
            # Extract necessary information
            download_url = file_info.get('downloadURL')
            if not download_url or not download_url.startswith('s3://'):
                logger.error(f"Invalid download URL: {download_url}")
                return
            
            # Parse S3 URL
            s3_parts = download_url.replace('s3://', '').split('/', 1)
            if len(s3_parts) != 2:
                logger.error(f"Invalid S3 URL format: {download_url}")
                return
            
            bucket = s3_parts[0]
            key = s3_parts[1]
            
            # Create output path
            filename = os.path.basename(key)
            project_name = file_info.get('projectName', 'unknown')
            output_path = os.path.join(self.output_dir, project_name, filename)
            
            # Create project directory if it doesn't exist
            os.makedirs(os.path.join(self.output_dir, project_name), exist_ok=True)
            
            # Add to queue
            self.download_queue.put({
                'bucket': bucket,
                'key': key,
                'output_path': output_path,
                'file_info': file_info
            })
            
            logger.info(f"Added file to download queue: {filename}")
        
        except Exception as e:
            logger.error(f"Error adding file to download queue: {str(e)}", exc_info=True)
    
    def start_download(self, num_threads: int = 3):
        """
        Start downloading files from the queue.
        
        Args:
            num_threads: Number of download threads to use
        """
        try:
            if not self.s3_client:
                logger.error("S3 client not initialized, cannot start download")
                messagebox.showerror("AWS Error", "Failed to initialize AWS S3 client. Check your credentials.")
                return
            
            # Reset stop event
            self.stop_event.clear()
            
            # Create and start download threads
            for i in range(num_threads):
                thread = threading.Thread(
                    target=self._download_worker,
                    name=f"aws-download-{i}",
                    daemon=True
                )
                self.download_threads.append(thread)
                thread.start()
            
            logger.info(f"Started {num_threads} download threads")
        
        except Exception as e:
            logger.error(f"Error starting download: {str(e)}", exc_info=True)
            messagebox.showerror("Download Error", f"Failed to start download: {str(e)}")
    
    def _download_worker(self):
        """
        Worker function for download threads.
        """
        try:
            while not self.stop_event.is_set():
                try:
                    # Get file from queue with timeout
                    file_info = self.download_queue.get(timeout=1)
                except queue.Empty:
                    # No more files in queue
                    break
                
                try:
                    # Extract information
                    bucket = file_info.get('bucket')
                    key = file_info.get('key')
                    output_path = file_info.get('output_path')
                    
                    # Create directory if it doesn't exist
                    os.makedirs(os.path.dirname(output_path), exist_ok=True)
                    
                    # Download file
                    logger.info(f"Downloading {key} to {output_path}")
                    
                    # Update progress
                    if self.progress_callback:
                        self.progress_callback(f"Downloading {os.path.basename(key)}...")
                    
                    # Download with requester pays
                    self.s3_client.download_file(
                        Bucket=bucket,
                        Key=key,
                        Filename=output_path,
                        ExtraArgs={'RequestPayer': 'requester'}
                    )
                    
                    logger.info(f"Downloaded {key} to {output_path}")
                    
                    # Mark task as done
                    self.download_queue.task_done()
                
                except Exception as e:
                    logger.error(f"Error downloading file {key}: {str(e)}", exc_info=True)
                    # Mark task as done even if it failed
                    self.download_queue.task_done()
        
        except Exception as e:
            logger.error(f"Error in download worker: {str(e)}", exc_info=True)
    
    def stop_download(self):
        """
        Stop all download threads.
        """
        try:
            # Set stop event
            self.stop_event.set()
            
            # Wait for threads to finish
            for thread in self.download_threads:
                if thread.is_alive():
                    thread.join(timeout=1)
            
            # Clear thread list
            self.download_threads = []
            
            logger.info("Stopped all download threads")
        
        except Exception as e:
            logger.error(f"Error stopping download: {str(e)}", exc_info=True)
    
    def get_queue_size(self) -> int:
        """
        Get the current size of the download queue.
        
        Returns:
            int: Number of files in the queue
        """
        return self.download_queue.qsize()
    
    def is_downloading(self) -> bool:
        """
        Check if download is in progress.
        
        Returns:
            bool: True if download is in progress, False otherwise
        """
        return any(thread.is_alive() for thread in self.download_threads)
    
    def download_metadata(self, project_name: str) -> Optional[str]:
        """
        Download metadata for a project.
        
        Args:
            project_name: Name of the project
            
        Returns:
            Optional[str]: Path to downloaded metadata file or None if failed
        """
        try:
            if not self.s3_client:
                logger.error("S3 client not initialized, cannot download metadata")
                return None
            
            # Create metadata directory
            metadata_dir = os.path.join(self.output_dir, project_name)
            os.makedirs(metadata_dir, exist_ok=True)
            
            # Output path
            output_path = os.path.join(metadata_dir, 'metadata.json')
            
            # Download metadata
            try:
                self.s3_client.download_file(
                    Bucket='usgs-lidar',
                    Key=f"Projects/{project_name}/metadata.json",
                    Filename=output_path,
                    ExtraArgs={'RequestPayer': 'requester'}
                )
                
                logger.info(f"Downloaded metadata for project {project_name}")
                return output_path
            
            except self.s3_client.exceptions.NoSuchKey:
                logger.warning(f"No metadata.json found for project {project_name}")
                return None
        
        except Exception as e:
            logger.error(f"Error downloading metadata for project {project_name}: {str(e)}", exc_info=True)
            return None
