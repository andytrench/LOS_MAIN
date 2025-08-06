"""
Drag and drop handler for the LOS application.
Provides safer handling of drag-and-drop operations to prevent Finder crashes.
"""

import os
import time
import logging
import threading
from tkinter import messagebox
from log_config import setup_logging

# Configure logging
logger = setup_logging(__name__)

# Global state tracking
_last_drop_time = 0
_min_drop_interval = 2.0  # Minimum seconds between drops
_processing_lock = threading.Lock()
_is_processing = False

def safe_handle_drop(event, process_callback):
    """
    Safely handle a file drop event with rate limiting and state tracking.
    
    Args:
        event: The drop event from TkinterDnD
        process_callback: Function to call with the file path when processing
        
    Returns:
        bool: True if the drop was handled, False if it was rejected
    """
    global _last_drop_time, _is_processing
    
    # Get the file path from the event
    try:
        file_path = event.data.strip('{}')
        logger.info(f"File drop detected: {file_path}")
        
        # Check if the file exists
        if not os.path.exists(file_path):
            logger.error(f"Dropped file does not exist: {file_path}")
            messagebox.showerror("Error", f"File not found: {file_path}")
            return False
            
        # Apply rate limiting
        current_time = time.time()
        time_since_last = current_time - _last_drop_time
        
        if time_since_last < _min_drop_interval:
            logger.warning(f"Drop rejected: too soon after previous drop ({time_since_last:.1f}s < {_min_drop_interval}s)")
            messagebox.showinfo("Please Wait", "Please wait a moment before dropping another file.")
            return False
            
        # Check if already processing a file
        with _processing_lock:
            if _is_processing:
                logger.warning("Drop rejected: already processing a file")
                messagebox.showinfo("Processing in Progress", "Please wait for the current file to finish processing.")
                return False
                
            # Mark as processing
            _is_processing = True
            
        # Update last drop time
        _last_drop_time = current_time
        
        # Process the file in a separate thread
        def process_thread():
            global _is_processing
            try:
                logger.info(f"Processing dropped file: {file_path}")
                process_callback(file_path)
                logger.info(f"Finished processing dropped file: {file_path}")
            except Exception as e:
                logger.error(f"Error processing dropped file: {str(e)}", exc_info=True)
                messagebox.showerror("Error", f"Failed to process file: {str(e)}")
            finally:
                # Mark as no longer processing
                with _processing_lock:
                    _is_processing = False
        
        # Start the processing thread
        threading.Thread(target=process_thread, daemon=True).start()
        return True
        
    except Exception as e:
        logger.error(f"Error handling file drop: {str(e)}", exc_info=True)
        messagebox.showerror("Error", f"Failed to handle dropped file: {str(e)}")
        
        # Reset processing state in case of error
        with _processing_lock:
            _is_processing = False
            
        return False

def is_processing():
    """Check if a file is currently being processed"""
    with _processing_lock:
        return _is_processing

def reset_processing_state():
    """Reset the processing state (for use in error recovery)"""
    global _is_processing
    with _processing_lock:
        _is_processing = False
    logger.info("Processing state has been reset")
