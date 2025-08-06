"""
Utilities for interacting with the file system and Finder on macOS.
"""

import os
import sys
import logging
import subprocess
import platform
import time
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Rate limiting for Finder interactions
_last_finder_interaction = 0
_min_interaction_interval = 2.0  # Minimum seconds between Finder interactions

def safe_open_directory(directory_path):
    """
    Safely open a directory in the file explorer, respecting the DISABLE_FINDER_OPEN setting.
    Includes rate limiting to prevent overwhelming Finder.

    Args:
        directory_path: Path to the directory to open

    Returns:
        bool: True if the directory was opened successfully, False otherwise
    """
    global _last_finder_interaction

    try:
        # Check if directory exists
        if not os.path.exists(directory_path):
            logger.error(f"Directory does not exist: {directory_path}")
            return False

        # Check if opening directories is disabled
        disable_finder_open = os.getenv("DISABLE_FINDER_OPEN", "false").lower() == "true"
        if disable_finder_open:
            logger.info(f"Directory opening is disabled by configuration: {directory_path}")
            return False

        # Apply rate limiting for Finder interactions
        current_time = time.time()
        time_since_last = current_time - _last_finder_interaction

        if time_since_last < _min_interaction_interval:
            wait_time = _min_interaction_interval - time_since_last
            logger.info(f"Rate limiting Finder interaction, waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)

        # Update last interaction time
        _last_finder_interaction = time.time()

        # Open directory based on platform
        if platform.system() == "Darwin":  # macOS
            logger.info(f"Opening directory in Finder: {directory_path}")
            subprocess.run(["open", directory_path], check=False)
        elif platform.system() == "Windows":
            logger.info(f"Opening directory in Explorer: {directory_path}")
            os.startfile(directory_path)
        else:  # Linux
            logger.info(f"Opening directory in file manager: {directory_path}")
            subprocess.run(["xdg-open", directory_path], check=False)

        return True
    except Exception as e:
        logger.error(f"Error opening directory {directory_path}: {e}")
        return False

def safe_open_file(file_path):
    """
    Safely open a file with the default application, respecting the DISABLE_FINDER_OPEN setting.
    Includes rate limiting to prevent overwhelming Finder.

    Args:
        file_path: Path to the file to open

    Returns:
        bool: True if the file was opened successfully, False otherwise
    """
    global _last_finder_interaction

    try:
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False

        # Check if opening files is disabled
        disable_finder_open = os.getenv("DISABLE_FINDER_OPEN", "false").lower() == "true"
        if disable_finder_open:
            logger.info(f"File opening is disabled by configuration: {file_path}")
            return False

        # Apply rate limiting for Finder interactions
        current_time = time.time()
        time_since_last = current_time - _last_finder_interaction

        if time_since_last < _min_interaction_interval:
            wait_time = _min_interaction_interval - time_since_last
            logger.info(f"Rate limiting Finder interaction, waiting {wait_time:.2f} seconds")
            time.sleep(wait_time)

        # Update last interaction time
        _last_finder_interaction = time.time()

        # Open file based on platform
        if platform.system() == "Darwin":  # macOS
            logger.info(f"Opening file with default application: {file_path}")
            subprocess.run(["open", file_path], check=False)
        elif platform.system() == "Windows":
            logger.info(f"Opening file with default application: {file_path}")
            os.startfile(file_path)
        else:  # Linux
            logger.info(f"Opening file with default application: {file_path}")
            subprocess.run(["xdg-open", file_path], check=False)

        return True
    except Exception as e:
        logger.error(f"Error opening file {file_path}: {e}")
        return False
