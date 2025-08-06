"""
Cleanup utilities for the application.
Provides functions to clean up temporary files and handle .DS_Store files.
"""

import os
import logging
import fnmatch
import time
import shutil
from datetime import datetime, timedelta

# Configure logging
logger = logging.getLogger(__name__)

def ignore_ds_store(directory):
    """
    DISABLED: Previously created .DS_Store files that were causing Finder issues.
    Now this function is a no-op to prevent Finder crashes.

    Args:
        directory: Directory that would have had .DS_Store created (ignored now)
    """
    # Function disabled to prevent Finder crashes
    logger.info(f"DS_Store creation disabled for directory: {directory}")
    return

def cleanup_ds_store_files(directory, recursive=True):
    """
    Clean up .DS_Store files in the specified directory.
    Modified to be more cautious with Finder's files.

    Args:
        directory: Directory to clean up
        recursive: Whether to clean up subdirectories recursively
    """
    # We'll only log that we would have cleaned up .DS_Store files
    # but won't actually remove them to prevent Finder issues
    logger.info(f"DS_Store cleanup disabled for directory: {directory}")
    return 0

def cleanup_old_temp_files(directory, pattern="*.tmp", max_age_days=1):
    """
    Clean up old temporary files in the specified directory.

    Args:
        directory: Directory to clean up
        pattern: File pattern to match
        max_age_days: Maximum age of files to keep in days

    Returns:
        int: Number of files cleaned up
    """
    try:
        count = 0
        now = datetime.now()
        max_age = timedelta(days=max_age_days)

        for root, dirs, files in os.walk(directory):
            for filename in fnmatch.filter(files, pattern):
                file_path = os.path.join(root, filename)

                # Check file age
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                age = now - file_time

                if age > max_age:
                    try:
                        os.remove(file_path)
                        count += 1
                        logger.info(f"Removed old temporary file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing temporary file {file_path}: {e}")

        logger.info(f"Cleaned up {count} old temporary files")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up old temporary files: {e}")
        return 0

def cleanup_old_backup_files(directory, pattern="*.bak", max_age_days=7):
    """
    Clean up old backup files in the specified directory.

    Args:
        directory: Directory to clean up
        pattern: File pattern to match
        max_age_days: Maximum age of files to keep in days

    Returns:
        int: Number of files cleaned up
    """
    try:
        count = 0
        now = datetime.now()
        max_age = timedelta(days=max_age_days)

        for root, dirs, files in os.walk(directory):
            for filename in fnmatch.filter(files, pattern):
                file_path = os.path.join(root, filename)

                # Check file age
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                age = now - file_time

                if age > max_age:
                    try:
                        os.remove(file_path)
                        count += 1
                        logger.info(f"Removed old backup file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing backup file {file_path}: {e}")

        logger.info(f"Cleaned up {count} old backup files")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up old backup files: {e}")
        return 0

def cleanup_all(base_directory=None):
    """
    Clean up all temporary files and .DS_Store files.

    Args:
        base_directory: Base directory to clean up (uses current directory if None)

    Returns:
        dict: Counts of files cleaned up by type
    """
    if base_directory is None:
        base_directory = os.getcwd()

    results = {
        "ds_store": 0,
        "temp_files": 0,
        "backup_files": 0
    }

    # Clean up .DS_Store files
    results["ds_store"] = cleanup_ds_store_files(base_directory)

    # Clean up old temporary files
    results["temp_files"] = cleanup_old_temp_files(base_directory)

    # Clean up old backup files
    results["backup_files"] = cleanup_old_backup_files(base_directory)

    logger.info(f"Cleanup complete: {results}")
    return results
