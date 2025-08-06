#!/usr/bin/env python3
"""
Merger Launcher Utility

This utility handles launching the PDAL merger2.py application with downloaded LAS/LAZ files
from the download queue. It provides integration between the LOStool download system and
the PDAL Merger2 application.

Features:
- Gathers completed downloads from the download queue
- Creates file lists for merger2.py
- Launches merger2.py with appropriate command line arguments
- Handles different launch methods (direct files, file lists)
- Provides proper error handling and logging
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import tkinter.messagebox as messagebox

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MERGER2_PATH = "/Users/master15/Desktop/Software/LOStool/PDAL_merge/merger2.py"


def get_downloaded_files_from_queue(downloader_instance) -> List[Tuple[str, str]]:
    """
    Extract completed downloaded files from the download queue.
    
    Args:
        downloader_instance: Instance of UltraVerboseDownloaderer
        
    Returns:
        List of tuples containing (filename, full_path) for completed downloads
    """
    completed_files = []
    
    try:
        if not hasattr(downloader_instance, 'file_info'):
            logger.warning("Downloader instance missing file_info attribute")
            return completed_files
            
        for url, info in downloader_instance.file_info.items():
            if info.get('status') == 'Complete':
                filename = info.get('filename')
                if filename:
                    # Construct full path using destination folder
                    full_path = os.path.join(downloader_instance.destination_folder, filename)
                    
                    # Verify file exists and is a LAS/LAZ file
                    if os.path.exists(full_path):
                        file_ext = os.path.splitext(filename)[1].lower()
                        if file_ext in ['.las', '.laz']:
                            completed_files.append((filename, full_path))
                            logger.debug(f"Found completed LAS/LAZ file: {filename}")
                        else:
                            logger.debug(f"Skipping non-LAS/LAZ file: {filename}")
                    else:
                        logger.warning(f"Completed file not found on disk: {full_path}")
                        
    except Exception as e:
        logger.error(f"Error extracting downloaded files: {e}", exc_info=True)
        
    logger.info(f"Found {len(completed_files)} completed LAS/LAZ downloads")
    return completed_files


def get_downloaded_files_from_tower_parameters() -> List[Tuple[str, str]]:
    """
    Extract downloaded file paths from tower_parameters.json.
    
    Returns:
        List of tuples containing (filename, full_path) for files with local_file_path
    """
    completed_files = []
    
    try:
        if not os.path.exists('tower_parameters.json'):
            logger.warning("tower_parameters.json not found")
            return completed_files
            
        with open('tower_parameters.json', 'r') as f:
            tower_data = json.load(f)
            
        lidar_data = tower_data.get('lidar_data', {})
        
        for project_name, project_info in lidar_data.items():
            local_file_path = project_info.get('local_file_path')
            if local_file_path and os.path.exists(local_file_path):
                filename = os.path.basename(local_file_path)
                file_ext = os.path.splitext(filename)[1].lower()
                
                if file_ext in ['.las', '.laz']:
                    completed_files.append((filename, local_file_path))
                    logger.debug(f"Found LAS/LAZ file from tower_parameters: {filename}")
                    
    except Exception as e:
        logger.error(f"Error reading tower_parameters.json: {e}", exc_info=True)
        
    logger.info(f"Found {len(completed_files)} LAS/LAZ files in tower_parameters.json")
    return completed_files


def create_file_list(file_paths: List[str], prefix: str = "merger_files") -> str:
    """
    Create a temporary file list for merger2.py.
    
    Args:
        file_paths: List of file paths to include
        prefix: Prefix for temporary file name
        
    Returns:
        Path to the temporary file list
    """
    try:
        # Create temporary file
        temp_fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix=prefix + '_')
        
        with os.fdopen(temp_fd, 'w') as f:
            # Write only the file paths, no comments
            # merger2.py will handle project detection from the filenames
            for file_path in file_paths:
                f.write(f"{file_path}\n")
                
        logger.info(f"Created file list with {len(file_paths)} files: {temp_path}")
        return temp_path
        
    except Exception as e:
        logger.error(f"Error creating file list: {e}", exc_info=True)
        raise


def find_python_executable() -> str:
    """
    Find the best Python executable to use for launching merger2.py.
    
    Returns:
        Path to Python executable
    """
    # Try current Python first (same environment as dropmap.py)
    python_paths = [
        sys.executable,  # Current Python (same as dropmap.py)
        '/opt/homebrew/bin/python3.10',
        '/usr/local/bin/python3.10',
        '/usr/bin/python3.10', 
        'python3.10',
        'python3',
        'python'
    ]
    
    for python_path in python_paths:
        try:
            result = subprocess.run(
                [python_path, '--version'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                logger.info(f"Using Python executable: {python_path}")
                return python_path
        except Exception:
            continue
            
    logger.warning("No suitable Python executable found, using sys.executable")
    return sys.executable


def launch_merger_with_files(file_paths: List[str], 
                           project_name: Optional[str] = None,
                           auto_analyze: bool = False,
                           output_dir: Optional[str] = None,
                           use_file_list: bool = True) -> bool:
    """
    Launch merger2.py with the specified files.
    
    Args:
        file_paths: List of LAS/LAZ file paths
        project_name: Optional project name for the session
        auto_analyze: Whether to automatically run analysis
        output_dir: Optional output directory
        use_file_list: Whether to use file list method (vs direct args)
        
    Returns:
        True if launched successfully, False otherwise
    """
    try:
        # Verify merger2.py exists
        if not os.path.exists(MERGER2_PATH):
            logger.error(f"merger2.py not found at: {MERGER2_PATH}")
            messagebox.showerror("Error", f"PDAL Merger2 not found at expected path:\n{MERGER2_PATH}")
            return False
            
        # Copy tower_parameters.json to merger directory
        logger.info("Copying tower_parameters.json to merger directory...")
        if not copy_tower_parameters_to_merger():
            logger.warning("Failed to copy tower_parameters.json, but continuing with launch")
            
        # Find Python executable
        python_exe = find_python_executable()
        
        # Build command
        cmd = [python_exe, MERGER2_PATH]
        
        temp_file_list = None
        
        try:
            # Only add files if we have them
            if file_paths:
                if use_file_list or len(file_paths) > 10:  # Use file list for many files
                    # Create temporary file list
                    temp_file_list = create_file_list(file_paths, "merger_launch")
                    cmd.extend(['--files-from', temp_file_list])
                else:
                    # Add files directly as arguments
                    cmd.extend(file_paths)
            else:
                logger.info("Launching merger with no files - merger will open empty")
            
            # Add optional arguments
            if project_name:
                cmd.extend(['--project-name', project_name])
                
            if auto_analyze:
                cmd.append('--auto-analyze')
                
            if output_dir and os.path.exists(output_dir):
                cmd.extend(['--output-dir', output_dir])
                
            # Get working directory (merger2.py directory)
            merger_dir = os.path.dirname(MERGER2_PATH)
            
            file_count = len(file_paths) if file_paths else 0
            logger.info(f"Launching merger2.py with {file_count} files")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            # Launch process
            if sys.platform == 'darwin':  # macOS
                # Use 'nice' to lower process priority
                subprocess.Popen(['nice', '-n', '10'] + cmd, cwd=merger_dir)
            else:
                subprocess.Popen(cmd, cwd=merger_dir)
                
            logger.info("PDAL Merger2 launched successfully")
            
            # Show success message
            if file_paths:
                project_info = f" for project '{project_name}'" if project_name else ""
                messagebox.showinfo(
                    "Success", 
                    f"PDAL Merger2 launched successfully with {len(file_paths)} files{project_info}."
                )
            else:
                messagebox.showinfo(
                    "Success", 
                    "PDAL Merger2 launched successfully. You can now add files manually within the merger."
                )
            
            return True
            
        finally:
            # Clean up temporary file list after a delay (allow merger2.py to read it)
            if temp_file_list and os.path.exists(temp_file_list):
                # Schedule cleanup after 30 seconds
                import threading
                def cleanup():
                    import time
                    time.sleep(30)
                    try:
                        os.unlink(temp_file_list)
                        logger.debug(f"Cleaned up temporary file list: {temp_file_list}")
                    except Exception as e:
                        logger.debug(f"Failed to cleanup temp file: {e}")
                        
                threading.Thread(target=cleanup, daemon=True).start()
            
    except Exception as e:
        logger.error(f"Error launching merger2.py: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to launch PDAL Merger2:\n{str(e)}")
        return False


def launch_merger_from_downloader(downloader_instance, 
                                project_name: Optional[str] = None,
                                auto_analyze: bool = True) -> bool:
    """
    Launch merger2.py with files from the downloader instance.
    
    Args:
        downloader_instance: Instance of UltraVerboseDownloaderer
        project_name: Optional project name (None = let merger2.py auto-detect)
        auto_analyze: Whether to auto-analyze
        
    Returns:
        True if launched successfully, False otherwise
    """
    try:
        # Get completed files from download queue
        queue_files = get_downloaded_files_from_queue(downloader_instance)
        
        # Also get files from tower_parameters.json as backup
        tower_files = get_downloaded_files_from_tower_parameters()
        
        # Combine and deduplicate files
        all_files = {}
        
        for filename, path in queue_files + tower_files:
            all_files[path] = filename  # Use path as key to deduplicate
            
        file_paths = list(all_files.keys())
        
        if not file_paths:
            logger.info("No completed LAS/LAZ downloads found - launching merger empty")
        
        # Don't pass project_name - let merger2.py auto-detect projects from filenames
        # Use downloader's destination folder as output directory
        output_dir = getattr(downloader_instance, 'destination_folder', None)
        
        return launch_merger_with_files(
            file_paths=file_paths,
            project_name=None,  # Let merger2.py handle project detection
            auto_analyze=auto_analyze,
            output_dir=output_dir
        )
        
    except Exception as e:
        logger.error(f"Error launching merger from downloader: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to launch merger from downloads:\n{str(e)}")
        return False


def launch_merger_from_tower_parameters(project_name: Optional[str] = None,
                                      auto_analyze: bool = True) -> bool:
    """
    Launch merger2.py with files from tower_parameters.json.
    
    Args:
        project_name: Optional project name
        auto_analyze: Whether to auto-analyze
        
    Returns:
        True if launched successfully, False otherwise
    """
    try:
        # Get files from tower_parameters.json
        tower_files = get_downloaded_files_from_tower_parameters()
        
        if not tower_files:
            logger.warning("No LAS/LAZ files found in tower_parameters.json")
            messagebox.showinfo(
                "No Files",
                "No LAS/LAZ files with local paths found in tower_parameters.json."
            )
            return False
            
        file_paths = [path for _, path in tower_files]
        
        # Auto-generate project name if not provided
        if not project_name:
            project_name = "Tower Parameters Files"
            
        return launch_merger_with_files(
            file_paths=file_paths,
            project_name=project_name,
            auto_analyze=auto_analyze
        )
        
    except Exception as e:
        logger.error(f"Error launching merger from tower parameters: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to launch merger from tower parameters:\n{str(e)}")
        return False


def copy_tower_parameters_to_merger():
    """
    Copy tower_parameters.json to the merger directory so merger2.py can access tower data.
    
    Returns:
        bool: True if copied successfully or not needed, False if failed
    """
    try:
        # Check if tower_parameters.json exists
        source = "tower_parameters.json"
        if not os.path.exists(source):
            logger.info("No tower_parameters.json found to copy")
            return True  # Not an error, just no file to copy
        
        # Get merger directory
        merger_dir = os.path.dirname(MERGER2_PATH)
        if not os.path.exists(merger_dir):
            logger.warning(f"Merger directory not found: {merger_dir}")
            return False
            
        # Destination path
        destination = os.path.join(merger_dir, "tower_parameters.json")
        
        # Copy the file
        import shutil
        shutil.copy2(source, destination)
        logger.info(f"Copied tower_parameters.json to merger directory: {destination}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error copying tower_parameters.json: {e}", exc_info=True)
        return False


# Test functions for development
def test_file_discovery():
    """Test function to check file discovery methods"""
    print("Testing file discovery methods...")
    
    # Test tower_parameters.json method
    tower_files = get_downloaded_files_from_tower_parameters()
    print(f"Found {len(tower_files)} files in tower_parameters.json:")
    for filename, path in tower_files:
        print(f"  {filename}: {path}")
        
    return tower_files


if __name__ == "__main__":
    # Enable debug logging for testing
    logging.basicConfig(level=logging.DEBUG)
    
    # Test file discovery
    test_files = test_file_discovery()
    
    if test_files:
        print(f"\nTesting launcher with {len(test_files)} files...")
        file_paths = [path for _, path in test_files]
        
        # Test launch (but don't actually launch in test mode)
        print("Would launch merger2.py with files:")
        for path in file_paths:
            print(f"  {path}") 