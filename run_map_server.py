#!/usr/bin/env python3
"""
Run the map server
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run_map_server')

def main():
    """Main function"""
    try:
        # Add the current directory to the Python path
        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
        
        # Import the map_server module
        from map_server import start_server
        
        # Start the map server
        logger.info("Starting map server...")
        start_server()
        
        logger.info("Map server started successfully")
    except Exception as e:
        logger.error(f"Error starting map server: {e}", exc_info=True)
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
