"""
Temporary directory manager for the application.
Provides utilities for creating, managing, and cleaning up temporary directories.
"""

import os
import time
import tempfile
import shutil
import atexit
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Global registry of temporary directories to clean up on exit
_temp_dirs = set()

# Session-wide temporary directory
_session_temp_dir = None

# Cache of temporary files by purpose
_temp_file_cache = {}

# Last cleanup time
_last_cleanup_time = 0

# Minimum interval between cleanups (seconds)
_min_cleanup_interval = 300  # 5 minutes

def get_temp_dir(prefix="lostool_", use_session_dir=True):
    """
    Get a temporary directory, using the session-wide directory if available.

    Args:
        prefix: Prefix for the temporary directory name
        use_session_dir: Whether to use the session-wide temporary directory

    Returns:
        str: Path to the temporary directory
    """
    global _session_temp_dir

    # Use the session-wide temporary directory if requested
    if use_session_dir:
        if _session_temp_dir is None:
            _session_temp_dir = tempfile.mkdtemp(prefix=f"{prefix}session_")
            _temp_dirs.add(_session_temp_dir)
            logger.info(f"Created session-wide temporary directory: {_session_temp_dir}")
        return _session_temp_dir
    else:
        # Create a new temporary directory
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        _temp_dirs.add(temp_dir)
        logger.info(f"Created temporary directory: {temp_dir}")
        return temp_dir

def get_temp_file(suffix=".tmp", prefix="lostool_", dir=None, purpose=None, reuse=True):
    """
    Get a temporary file, optionally reusing existing files for the same purpose.

    Args:
        suffix: Suffix for the temporary file
        prefix: Prefix for the temporary file
        dir: Directory to create the file in (uses session temp dir if None)
        purpose: Purpose identifier for file caching (e.g., 'screenshot', 'json_backup')
        reuse: Whether to reuse existing files for the same purpose

    Returns:
        str: Path to the temporary file
    """
    global _temp_file_cache

    # Check if we can reuse an existing file for this purpose
    if purpose and reuse and purpose in _temp_file_cache:
        cached_path = _temp_file_cache[purpose]
        if os.path.exists(cached_path):
            logger.info(f"Reusing cached temporary file for {purpose}: {cached_path}")
            # Truncate the file to ensure it's empty
            with open(cached_path, 'w') as f:
                pass
            return cached_path

    # Use the session-wide temporary directory if none specified
    if dir is None:
        dir = get_temp_dir()

    # Create a new temporary file
    fd, temp_path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
    os.close(fd)  # Close the file descriptor

    # Cache the file path if a purpose is specified
    if purpose:
        _temp_file_cache[purpose] = temp_path
        logger.info(f"Created and cached temporary file for {purpose}: {temp_path}")
    else:
        logger.info(f"Created temporary file: {temp_path}")

    return temp_path

def cleanup_temp_dir(temp_dir):
    """
    Clean up a temporary directory.

    Args:
        temp_dir: Path to the temporary directory
    """
    if os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Cleaned up temporary directory: {temp_dir}")
            _temp_dirs.discard(temp_dir)
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory {temp_dir}: {e}")

def cleanup_all_temp_dirs():
    """Clean up all registered temporary directories."""
    logger.info(f"Cleaning up {len(_temp_dirs)} temporary directories")
    for temp_dir in list(_temp_dirs):
        cleanup_temp_dir(temp_dir)

def maybe_periodic_cleanup():
    """
    Perform a cleanup if enough time has passed since the last cleanup.
    This reduces the frequency of file system operations.
    """
    global _last_cleanup_time

    current_time = time.time()
    time_since_last = current_time - _last_cleanup_time

    if time_since_last >= _min_cleanup_interval:
        logger.info(f"Performing periodic cleanup after {time_since_last:.1f} seconds")
        cleanup_temp_files_only()
        _last_cleanup_time = current_time
        return True
    else:
        logger.debug(f"Skipping periodic cleanup, only {time_since_last:.1f} seconds since last cleanup")
        return False

# Register cleanup function to run on exit
atexit.register(cleanup_all_temp_dirs)

def prevent_finder_crash():
    """
    Apply various fixes to prevent Finder from crashing when working with files.
    This should be called at application startup.
    """
    try:
        # Set environment variables to prevent .DS_Store creation
        os.environ['COPYFILE_DISABLE'] = '1'  # Prevent ._ files in archives

        # Create a .metadata_never_index file in the temp directory to prevent Spotlight indexing
        session_dir = get_temp_dir()
        metadata_file = os.path.join(session_dir, '.metadata_never_index')
        if not os.path.exists(metadata_file):
            with open(metadata_file, 'w') as f:
                f.write('# This directory should never be indexed by Spotlight')
            logger.info(f"Created .metadata_never_index file in {session_dir}")

        # Run an initial cleanup to remove any stale temporary files
        cleanup_temp_files_only()

        logger.info("Applied Finder crash prevention measures")
        return True

    except Exception as e:
        logger.error(f"Error applying Finder crash prevention: {str(e)}")
        return False

def cleanup_temp_files_only(base_directory=None):
    """
    Clean up only temporary files, avoiding any .DS_Store operations.
    This is a safer alternative to cleanup_all() that won't affect Finder.

    Args:
        base_directory: Base directory to clean up (uses current directory if None)

    Returns:
        int: Number of files cleaned up
    """
    if base_directory is None:
        base_directory = os.getcwd()

    count = 0

    # Clean up temporary directories we've registered
    cleanup_all_temp_dirs()

    # Look for orphaned temp files with our prefix
    for root, dirs, files in os.walk(base_directory):
        for filename in files:
            if filename.startswith('lostool_') and filename.endswith('.tmp'):
                file_path = os.path.join(root, filename)
                try:
                    os.remove(file_path)
                    count += 1
                    logger.info(f"Removed orphaned temp file: {file_path}")
                except Exception as e:
                    logger.error(f"Error removing temp file {file_path}: {e}")

    logger.info(f"Cleaned up {count} orphaned temporary files")
    return count

def copy_to_output_dir(temp_file, output_dir, output_filename=None):
    """
    Copy a temporary file to the output directory.

    Args:
        temp_file: Path to the temporary file
        output_dir: Path to the output directory
        output_filename: Name for the output file (uses original name if None)

    Returns:
        str: Path to the copied file
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    if output_filename is None:
        output_filename = os.path.basename(temp_file)

    output_path = os.path.join(output_dir, output_filename)

    try:
        # Use a safer copy method that avoids Finder issues
        safe_copy_file(temp_file, output_path)
        logger.info(f"Copied temporary file to output: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error copying temporary file to output: {e}")
        return None

def safe_copy_file(src, dst):
    """
    Safely copy a file using a method that avoids Finder issues.

    Args:
        src: Source file path
        dst: Destination file path

    Returns:
        str: Path to the destination file
    """
    try:
        # Skip .DS_Store files
        if os.path.basename(src) == '.DS_Store' or os.path.basename(dst) == '.DS_Store':
            logger.debug(f"Skipping .DS_Store file: {src} -> {dst}")
            return dst

        # Check if source file exists
        if not os.path.exists(src):
            logger.error(f"Source file does not exist: {src}")
            raise FileNotFoundError(f"Source file does not exist: {src}")

        # Create a temporary file in the destination directory
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

        return dst

    except Exception as e:
        logger.error(f"Error safely copying file {src} to {dst}: {str(e)}")
        raise
