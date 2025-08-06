"""
Utility functions for safely handling JSON operations.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime
import shutil

# Set up logging
logger = logging.getLogger(__name__)

# Global lock for JSON file operations
json_file_lock = threading.Lock()

def safe_update_json_file(data, file_path="tower_parameters.json", max_retries=3, retry_delay=0.5):
    """
    Safely update a JSON file with proper locking and error handling.
    
    Args:
        data: The data to write to the JSON file
        file_path: The path to the JSON file
        max_retries: Maximum number of retries if the operation fails
        retry_delay: Delay between retries in seconds
        
    Returns:
        bool: True if the operation was successful, False otherwise
    """
    # Acquire the lock to ensure thread safety
    with json_file_lock:
        for attempt in range(max_retries):
            try:
                # Create a backup of the existing file
                if os.path.exists(file_path):
                    backup_path = f"{file_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.copy2(file_path, backup_path)
                    logger.debug(f"Created backup of {file_path} at {backup_path}")
                
                # Write to a temporary file first
                temp_path = f"{file_path}.tmp"
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Verify the JSON is valid by reading it back
                with open(temp_path, 'r') as f:
                    json.load(f)  # This will raise an exception if the JSON is invalid
                
                # Replace the original file with the temporary file
                if os.path.exists(file_path):
                    os.replace(temp_path, file_path)
                else:
                    os.rename(temp_path, file_path)
                
                logger.info(f"Successfully updated {file_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error updating JSON file (attempt {attempt+1}/{max_retries}): {str(e)}", exc_info=True)
                
                # Clean up the temporary file if it exists
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        return False

def safe_update_json_section(section_key, section_data, file_path="tower_parameters.json", max_retries=3, retry_delay=0.5):
    """
    Safely update a section of a JSON file with proper locking and error handling.
    
    Args:
        section_key: The key of the section to update
        section_data: The data to write to the section
        file_path: The path to the JSON file
        max_retries: Maximum number of retries if the operation fails
        retry_delay: Delay between retries in seconds
        
    Returns:
        bool: True if the operation was successful, False otherwise
    """
    # Acquire the lock to ensure thread safety
    with json_file_lock:
        for attempt in range(max_retries):
            try:
                # Read the existing data
                data = None
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                    except json.JSONDecodeError as e:
                        logger.error(f"Error decoding JSON from {file_path}: {str(e)}")
                        # Create a backup of the corrupted file
                        backup_path = f"{file_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                        shutil.copy2(file_path, backup_path)
                        logger.info(f"Created backup of corrupted file at {backup_path}")
                        data = None
                
                # Create a new data structure if the file doesn't exist or is corrupted
                if data is None:
                    data = {
                        "site_A": {},
                        "site_B": {},
                        "general_parameters": {},
                        "lidar_data": {},
                        "turbines": []
                    }
                
                # Update the section
                data[section_key] = section_data
                
                # Write to a temporary file first
                temp_path = f"{file_path}.tmp"
                with open(temp_path, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Verify the JSON is valid by reading it back
                with open(temp_path, 'r') as f:
                    json.load(f)  # This will raise an exception if the JSON is invalid
                
                # Replace the original file with the temporary file
                if os.path.exists(file_path):
                    os.replace(temp_path, file_path)
                else:
                    os.rename(temp_path, file_path)
                
                logger.info(f"Successfully updated section '{section_key}' in {file_path}")
                return True
                
            except Exception as e:
                logger.error(f"Error updating JSON section (attempt {attempt+1}/{max_retries}): {str(e)}", exc_info=True)
                
                # Clean up the temporary file if it exists
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except Exception as cleanup_error:
                    logger.error(f"Error cleaning up temporary file: {str(cleanup_error)}")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        return False

def safe_read_json_file(file_path="tower_parameters.json", default_data=None, max_retries=3, retry_delay=0.5):
    """
    Safely read a JSON file with proper locking and error handling.
    
    Args:
        file_path: The path to the JSON file
        default_data: The default data to return if the file doesn't exist or is corrupted
        max_retries: Maximum number of retries if the operation fails
        retry_delay: Delay between retries in seconds
        
    Returns:
        The data from the JSON file, or the default data if the file doesn't exist or is corrupted
    """
    # Acquire the lock to ensure thread safety
    with json_file_lock:
        for attempt in range(max_retries):
            try:
                if not os.path.exists(file_path):
                    logger.warning(f"JSON file not found: {file_path}")
                    return default_data
                
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                return data
                
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from {file_path} (attempt {attempt+1}/{max_retries}): {str(e)}")
                
                # Create a backup of the corrupted file
                if os.path.exists(file_path):
                    backup_path = f"{file_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    try:
                        shutil.copy2(file_path, backup_path)
                        logger.info(f"Created backup of corrupted file at {backup_path}")
                    except Exception as backup_error:
                        logger.error(f"Error creating backup of corrupted file: {str(backup_error)}")
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
            
            except Exception as e:
                logger.error(f"Error reading JSON file (attempt {attempt+1}/{max_retries}): {str(e)}", exc_info=True)
                
                # Wait before retrying
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        
        return default_data
