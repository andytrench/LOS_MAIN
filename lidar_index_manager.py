#!/usr/bin/env python3
"""
LIDAR Index Manager

This script provides a command-line interface for managing the LIDAR file index.
It allows you to:
1. Initialize the database
2. Crawl the USGS AWS S3 bucket to index LIDAR files
3. Update the index with new data
4. Search for LIDAR files by location
5. View statistics about the index
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import the database module
from utilities.lidar_index_db import (
    init_database, get_database_stats, database_exists, DEFAULT_DB_PATH,
    search_files_by_bbox
)

# Import the crawler module
from utilities.lidar_crawler import LidarCrawler

def init_command(args):
    """
    Initialize the LIDAR index database.
    
    Args:
        args: Command-line arguments
    """
    try:
        # Check if database already exists
        if database_exists(args.db_path) and not args.force:
            logger.warning(f"Database already exists at {args.db_path}")
            logger.warning("Use --force to reinitialize the database")
            return 1
        
        # Initialize database
        logger.info(f"Initializing database at {args.db_path}")
        init_database(args.db_path)
        
        logger.info("Database initialized successfully")
        return 0
    
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}", exc_info=True)
        return 1

def crawl_command(args):
    """
    Crawl the USGS AWS S3 bucket to index LIDAR files.
    
    Args:
        args: Command-line arguments
    """
    try:
        # Check if database exists
        if not database_exists(args.db_path):
            logger.error(f"Database does not exist at {args.db_path}")
            logger.error("Use 'init' command to initialize the database")
            return 1
        
        # Create crawler
        crawler = LidarCrawler(args.db_path)
        
        # Run crawler
        crawler.run(args.max_projects)
        
        return 0
    
    except Exception as e:
        logger.error(f"Error crawling LIDAR files: {str(e)}", exc_info=True)
        return 1

def update_command(args):
    """
    Update the LIDAR index with new data.
    
    Args:
        args: Command-line arguments
    """
    try:
        # Check if database exists
        if not database_exists(args.db_path):
            logger.error(f"Database does not exist at {args.db_path}")
            logger.error("Use 'init' command to initialize the database")
            return 1
        
        # Create crawler
        crawler = LidarCrawler(args.db_path)
        
        # Run crawler
        crawler.run(args.max_projects)
        
        return 0
    
    except Exception as e:
        logger.error(f"Error updating LIDAR index: {str(e)}", exc_info=True)
        return 1

def search_command(args):
    """
    Search for LIDAR files by location.
    
    Args:
        args: Command-line arguments
    """
    try:
        # Check if database exists
        if not database_exists(args.db_path):
            logger.error(f"Database does not exist at {args.db_path}")
            logger.error("Use 'init' command to initialize the database")
            return 1
        
        # Parse bounding box
        min_x = args.min_x
        min_y = args.min_y
        max_x = args.max_x
        max_y = args.max_y
        
        # Search for files
        files = search_files_by_bbox(min_x, min_y, max_x, max_y, args.format, args.db_path)
        
        # Print results
        print(f"Found {len(files)} LIDAR files in bounding box: {min_x}, {min_y}, {max_x}, {max_y}")
        
        if files:
            print("\nLIDAR Files:")
            print("=" * 80)
            print(f"{'Project':<40} {'Filename':<30} {'Size (MB)':<10}")
            print("-" * 80)
            
            for file in files[:args.limit]:
                project = file.get('project_name', '')
                filename = file.get('filename', '')
                size = file.get('size', 0) / (1024 * 1024)  # Convert to MB
                
                print(f"{project:<40} {filename:<30} {size:<10.2f}")
            
            if len(files) > args.limit:
                print(f"\n... and {len(files) - args.limit} more files")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error searching LIDAR files: {str(e)}", exc_info=True)
        return 1

def stats_command(args):
    """
    View statistics about the LIDAR index.
    
    Args:
        args: Command-line arguments
    """
    try:
        # Check if database exists
        if not database_exists(args.db_path):
            logger.error(f"Database does not exist at {args.db_path}")
            logger.error("Use 'init' command to initialize the database")
            return 1
        
        # Get database stats
        stats = get_database_stats(args.db_path)
        
        # Print stats
        print("LIDAR Index Statistics:")
        print("=" * 80)
        print(f"Database path: {stats['db_path']}")
        print(f"Database size: {stats['db_size'] / (1024 * 1024):.2f} MB")
        print(f"Projects: {stats['project_count']}")
        print(f"Files: {stats['file_count']}")
        
        print("\nFile formats:")
        for format, count in stats.get('format_counts', {}).items():
            print(f"  {format}: {count}")
        
        if stats.get('latest_crawl'):
            latest_crawl = stats['latest_crawl']
            print("\nLatest crawl:")
            print(f"  ID: {latest_crawl['id']}")
            print(f"  Status: {latest_crawl['status']}")
            print(f"  Start time: {latest_crawl['start_time']}")
            print(f"  End time: {latest_crawl['end_time']}")
            print(f"  Projects added: {latest_crawl['projects_added']}")
            print(f"  Projects updated: {latest_crawl['projects_updated']}")
            print(f"  Files added: {latest_crawl['files_added']}")
            print(f"  Files updated: {latest_crawl['files_updated']}")
        
        return 0
    
    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}", exc_info=True)
        return 1

def main():
    """
    Main function.
    """
    # Create argument parser
    parser = argparse.ArgumentParser(description='LIDAR Index Manager')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH,
                        help='Path to the database file')
    
    # Create subparsers for commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize the database')
    init_parser.add_argument('--force', action='store_true',
                            help='Force reinitialization if database already exists')
    
    # Crawl command
    crawl_parser = subparsers.add_parser('crawl', help='Crawl LIDAR files')
    crawl_parser.add_argument('--max-projects', type=int,
                             help='Maximum number of projects to crawl')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update the index with new data')
    update_parser.add_argument('--max-projects', type=int,
                              help='Maximum number of projects to update')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search for LIDAR files by location')
    search_parser.add_argument('--min-x', type=float, required=True,
                              help='Minimum X coordinate (longitude)')
    search_parser.add_argument('--min-y', type=float, required=True,
                              help='Minimum Y coordinate (latitude)')
    search_parser.add_argument('--max-x', type=float, required=True,
                              help='Maximum X coordinate (longitude)')
    search_parser.add_argument('--max-y', type=float, required=True,
                              help='Maximum Y coordinate (latitude)')
    search_parser.add_argument('--format', type=str,
                              help='File format filter (e.g., laz, las)')
    search_parser.add_argument('--limit', type=int, default=10,
                              help='Maximum number of results to display')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='View statistics about the index')
    
    # Parse arguments
    args = parser.parse_args()
    
    # Run command
    if args.command == 'init':
        return init_command(args)
    elif args.command == 'crawl':
        return crawl_command(args)
    elif args.command == 'update':
        return update_command(args)
    elif args.command == 'search':
        return search_command(args)
    elif args.command == 'stats':
        return stats_command(args)
    else:
        parser.print_help()
        return 1

if __name__ == '__main__':
    sys.exit(main())
