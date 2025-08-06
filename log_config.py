import logging
import os
import sys
from datetime import datetime
import atexit

# Global variables for centralized logging
_main_log_file = None
_file_handler = None
_is_logging_initialized = False

def initialize_logging(log_level=logging.INFO):
    """
    Initialize centralized logging for the entire application.

    Args:
        log_level (int): Logging level (default: logging.INFO)
    """
    global _main_log_file, _file_handler, _is_logging_initialized

    if _is_logging_initialized:
        return

    # Create logs directory if it doesn't exist
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Create a timestamp for the log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    _main_log_file = os.path.join(log_dir, f'{timestamp}_application.log')

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Create file handler
    _file_handler = logging.FileHandler(_main_log_file)
    _file_handler.setLevel(log_level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    _file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add the handlers to the root logger
    root_logger.addHandler(_file_handler)
    root_logger.addHandler(console_handler)

    # Register cleanup function to close handlers on exit
    atexit.register(cleanup_logging)

    _is_logging_initialized = True

    # Log initialization
    root_logger.info(f"Centralized logging initialized")
    root_logger.info(f"Main log file: {_main_log_file}")

def cleanup_logging():
    """
    Clean up logging handlers on application exit.
    """
    global _file_handler
    if _file_handler:
        _file_handler.close()

def setup_logging(module_name, log_level=logging.INFO):
    """
    Set up logging for a specific module using the centralized configuration.

    Args:
        module_name (str): Name of the module for which logging is being set up
        log_level (int): Logging level (default: logging.INFO)

    Returns:
        logger: Configured logger instance
    """
    # Ensure centralized logging is initialized
    if not _is_logging_initialized:
        initialize_logging(log_level)

    # Get logger for the module
    logger = logging.getLogger(module_name)
    logger.setLevel(log_level)

    # Log that this module's logger is set up
    logger.info(f"Module {module_name} logging initialized")

    return logger