"""
Utilities for safer file operations.
Provides functions to help prevent Finder crashes when working with files.
"""

import os
import time
import logging
import shutil
import platform
import tempfile
import threading
from log_config import setup_logging

# Configure logging
logger = setup_logging(__name__)

# Global state tracking
_file_op_lock = threading.Lock()
_last_file_op_time = 0
_min_file_op_interval = 0.1  # Minimum seconds between file operations

def can_perform_file_op():
    """Check if a file operation can be performed"""
    global _last_file_op_time
    with _file_op_lock:
        current_time = time.time()
        time_since_last = current_time - _last_file_op_time
        
        if time_since_last < _min_file_op_interval:
            time.sleep(_min_file_op_interval - time_since_last)
            
        _last_file_op_time = time.time()
        return True

def safe_remove_file(file_path):
    """
    Safely remove a file with rate limiting and error handling.
    
    Args:
        file_path: Path to the file to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Skip .DS_Store files
        if os.path.basename(file_path) == '.DS_Store':
            logger.debug(f"Skipping .DS_Store file: {file_path}")
            return True
            
        # Check if file exists
        if not os.path.exists(file_path):
            logger.debug(f"File does not exist, skipping: {file_path}")
            return True
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Remove the file
        os.remove(file_path)
        logger.debug(f"Successfully removed file: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing file {file_path}: {str(e)}")
        return False

def safe_copy_file(src, dst):
    """
    Safely copy a file with rate limiting and error handling.
    
    Args:
        src: Source file path
        dst: Destination file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Skip .DS_Store files
        if os.path.basename(src) == '.DS_Store' or os.path.basename(dst) == '.DS_Store':
            logger.debug(f"Skipping .DS_Store file: {src} -> {dst}")
            return True
            
        # Check if source file exists
        if not os.path.exists(src):
            logger.error(f"Source file does not exist: {src}")
            return False
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Create destination directory if it doesn't exist
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
            
        # Use a temporary file for the copy to avoid partial writes
        temp_dst = f"{dst}.tmp"
        
        # Copy the file using read/write operations
        with open(src, 'rb') as src_file:
            with open(temp_dst, 'wb') as dst_file:
                dst_file.write(src_file.read())
                
        # If the destination file exists, remove it first
        if os.path.exists(dst):
            os.remove(dst)
            
        # Rename the temporary file to the destination
        os.rename(temp_dst, dst)
        
        # Ensure file permissions match
        shutil.copymode(src, dst)
        
        logger.debug(f"Successfully copied file: {src} -> {dst}")
        return True
        
    except Exception as e:
        logger.error(f"Error copying file {src} to {dst}: {str(e)}")
        return False

def safe_move_file(src, dst):
    """
    Safely move a file with rate limiting and error handling.
    
    Args:
        src: Source file path
        dst: Destination file path
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Skip .DS_Store files
        if os.path.basename(src) == '.DS_Store' or os.path.basename(dst) == '.DS_Store':
            logger.debug(f"Skipping .DS_Store file: {src} -> {dst}")
            return True
            
        # Check if source file exists
        if not os.path.exists(src):
            logger.error(f"Source file does not exist: {src}")
            return False
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Create destination directory if it doesn't exist
        dst_dir = os.path.dirname(dst)
        if not os.path.exists(dst_dir):
            os.makedirs(dst_dir, exist_ok=True)
            
        # Use a temporary file for the move to avoid partial writes
        temp_dst = f"{dst}.tmp"
        
        # Copy the file using read/write operations
        with open(src, 'rb') as src_file:
            with open(temp_dst, 'wb') as dst_file:
                dst_file.write(src_file.read())
                
        # If the destination file exists, remove it first
        if os.path.exists(dst):
            os.remove(dst)
            
        # Rename the temporary file to the destination
        os.rename(temp_dst, dst)
        
        # Remove the source file
        os.remove(src)
        
        logger.debug(f"Successfully moved file: {src} -> {dst}")
        return True
        
    except Exception as e:
        logger.error(f"Error moving file {src} to {dst}: {str(e)}")
        return False

def safe_create_directory(directory_path):
    """
    Safely create a directory with rate limiting and error handling.
    
    Args:
        directory_path: Path to the directory to create
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if directory already exists
        if os.path.exists(directory_path):
            logger.debug(f"Directory already exists: {directory_path}")
            return True
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Create the directory
        os.makedirs(directory_path, exist_ok=True)
        logger.debug(f"Successfully created directory: {directory_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error creating directory {directory_path}: {str(e)}")
        return False

def safe_remove_directory(directory_path):
    """
    Safely remove a directory with rate limiting and error handling.
    
    Args:
        directory_path: Path to the directory to remove
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if directory exists
        if not os.path.exists(directory_path):
            logger.debug(f"Directory does not exist: {directory_path}")
            return True
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Remove .DS_Store files first to prevent Finder issues
        for root, dirs, files in os.walk(directory_path):
            for file in files:
                if file == '.DS_Store':
                    try:
                        os.remove(os.path.join(root, file))
                        logger.debug(f"Removed .DS_Store file: {os.path.join(root, file)}")
                    except Exception as e:
                        logger.warning(f"Error removing .DS_Store file: {str(e)}")
        
        # Remove the directory
        shutil.rmtree(directory_path)
        logger.debug(f"Successfully removed directory: {directory_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error removing directory {directory_path}: {str(e)}")
        return False

def safe_open_file(file_path):
    """
    Safely open a file with its default application.
    
    Args:
        file_path: Path to the file to open
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False
            
        # Apply rate limiting
        can_perform_file_op()
            
        # Open the file with the default application
        if platform.system() == 'Darwin':  # macOS
            import subprocess
            subprocess.call(['open', file_path])
        elif platform.system() == 'Windows':  # Windows
            import os
            os.startfile(file_path)
        else:  # Linux
            import subprocess
            subprocess.call(['xdg-open', file_path])
            
        logger.debug(f"Successfully opened file: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Error opening file {file_path}: {str(e)}")
        return False
