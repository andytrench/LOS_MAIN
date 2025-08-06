"""
Utilities for safer drag-and-drop operations.
Provides functions to help prevent Finder crashes when working with drag-and-drop.
"""

import os
import time
import logging
import threading
import tkinter as tk
from tkinter import messagebox
from log_config import setup_logging

# Configure logging
logger = setup_logging(__name__)

# Global state tracking
_drag_in_progress = False
_drag_lock = threading.Lock()
_last_drag_time = 0
_min_drag_interval = 1.0  # Minimum seconds between drags

def is_drag_in_progress():
    """Check if a drag operation is in progress"""
    with _drag_lock:
        return _drag_in_progress

def set_drag_in_progress(in_progress):
    """Set the drag in progress state"""
    global _drag_in_progress, _last_drag_time
    with _drag_lock:
        _drag_in_progress = in_progress
        if not in_progress:
            _last_drag_time = time.time()

def can_start_drag():
    """Check if a new drag operation can be started"""
    global _last_drag_time
    with _drag_lock:
        if _drag_in_progress:
            logger.warning("Cannot start a new drag, a previous drag is still in progress")
            return False
            
        current_time = time.time()
        time_since_last = current_time - _last_drag_time
        
        if time_since_last < _min_drag_interval:
            logger.warning(f"Cannot start a new drag, too soon after previous drag ({time_since_last:.1f}s < {_min_drag_interval}s)")
            return False
            
        _drag_in_progress = True
        return True

def end_drag():
    """End a drag operation"""
    set_drag_in_progress(False)

def safe_drag_start(callback):
    """
    Safely start a drag operation with rate limiting.
    
    Args:
        callback: Function to call if the drag can be started
        
    Returns:
        bool: True if the drag was started, False otherwise
    """
    if can_start_drag():
        try:
            callback()
            return True
        except Exception as e:
            logger.error(f"Error during drag operation: {str(e)}")
            end_drag()
            return False
    return False

def register_drag_end_handlers(root):
    """
    Register handlers to detect when a drag operation ends.
    
    Args:
        root: The Tkinter root window
    """
    # Bind to mouse button release events
    root.bind("<ButtonRelease-1>", lambda e: end_drag())
    
    # Bind to window focus events
    root.bind("<FocusIn>", lambda e: end_drag())
    
    # Bind to window configure events (resize, move)
    root.bind("<Configure>", lambda e: end_drag())
    
    # Create a periodic check to reset drag state if stuck
    def check_drag_state():
        if is_drag_in_progress():
            # If drag has been in progress for more than 5 seconds, reset it
            with _drag_lock:
                if time.time() - _last_drag_time > 5.0:
                    logger.warning("Drag operation timed out, resetting state")
                    _drag_in_progress = False
        
        # Schedule the next check
        root.after(1000, check_drag_state)
    
    # Start the periodic check
    root.after(1000, check_drag_state)

class SafeDragManager:
    """
    Manager for safer drag-and-drop operations.
    """
    def __init__(self, root):
        """
        Initialize the drag manager.
        
        Args:
            root: The Tkinter root window
        """
        self.root = root
        register_drag_end_handlers(root)
        
    def start_drag(self, callback):
        """
        Start a drag operation safely.
        
        Args:
            callback: Function to call if the drag can be started
            
        Returns:
            bool: True if the drag was started, False otherwise
        """
        return safe_drag_start(callback)
        
    def is_drag_in_progress(self):
        """Check if a drag operation is in progress"""
        return is_drag_in_progress()
        
    def end_drag(self):
        """End a drag operation"""
        end_drag()
