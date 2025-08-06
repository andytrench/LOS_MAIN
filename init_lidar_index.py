#!/usr/bin/env python3
"""
Initialize LIDAR Index

This script initializes the LIDAR index database with data from the USGS AWS S3 bucket.
It uses the fast_lidar_indexer module to create a comprehensive index of all LIDAR files.
"""

import os
import sys
import logging
import argparse
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"lidar_index_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def parse_args():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = argparse.ArgumentParser(description='Initialize LIDAR index database')
    parser.add_argument('--region', type=str, help='Limit initialization to a specific region (e.g., CO)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--background', action='store_true', help='Run in the background')
    
    return parser.parse_args()

def run_indexer(region=None, verbose=False):
    """
    Run the fast_lidar_indexer to initialize the database.
    
    Args:
        region: Limit initialization to a specific region
        verbose: Enable verbose logging
    """
    try:
        # Import the indexer
        from fast_lidar_indexer import main as run_indexer_main
        
        # Set environment variables
        if verbose:
            os.environ['VERBOSE'] = '1'
        
        if region:
            os.environ['REGION'] = region
        
        # Set initialization flag
        os.environ['INIT'] = '1'
        
        # Run the indexer
        run_indexer_main()
    
    except Exception as e:
        logger.error(f"Error running LIDAR indexer: {str(e)}", exc_info=True)

def main():
    """
    Main function.
    """
    try:
        # Parse arguments
        args = parse_args()
        
        # Set log level
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
        
        # Run in background or foreground
        if args.background:
            # Run the indexer in a separate thread
            thread = threading.Thread(
                target=run_indexer,
                args=(args.region, args.verbose),
                daemon=True
            )
            thread.start()
            
            # Print message
            print("LIDAR index initialization started in the background.")
            print("You can continue using the application while it runs.")
            print(f"Check lidar_index_init_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log for progress updates.")
        else:
            # Run the indexer in the foreground
            logger.info("Starting LIDAR index initialization...")
            start_time = datetime.now()
            
            run_indexer(args.region, args.verbose)
            
            end_time = datetime.now()
            duration = end_time - start_time
            logger.info(f"LIDAR index initialization completed in {duration}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error initializing LIDAR index: {str(e)}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
