#!/usr/bin/env python3
"""
Initialize the tower database from FCC data files.

This script initializes the tower database by parsing the FCC data files
and storing the data in a SQLite database for efficient querying.
"""

import os
import sys
import logging
import argparse
from utilities.tower_database import init_database, import_tower_data, get_database_stats

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Initialize tower database from FCC data files')
    parser.add_argument('--force', action='store_true', help='Force reinitialization if database already exists')
    parser.add_argument('--db-path', default=None, help='Path to the database file')
    args = parser.parse_args()

    try:
        # Initialize database
        logger.info("Initializing tower database")
        if args.db_path:
            success = init_database(args.db_path, args.force)
        else:
            success = init_database(force=args.force)

        if not success:
            logger.error("Failed to initialize tower database")
            return 1

        # Import tower data
        logger.info("Importing tower data")
        if args.db_path:
            success = import_tower_data(args.db_path)
        else:
            success = import_tower_data()

        if not success:
            logger.error("Failed to import tower data")
            return 1

        # Get database stats
        logger.info("Getting database statistics")
        if args.db_path:
            stats = get_database_stats(args.db_path)
        else:
            stats = get_database_stats()

        # Print statistics
        print(f"Tower database statistics:")
        print(f"  Registration records: {stats.get('registration_count', 0)}")
        print(f"  Coordinates records: {stats.get('coordinates_count', 0)}")
        print(f"  Entity records: {stats.get('entity_count', 0)}")
        print(f"  Database size: {stats.get('db_size', 0) / (1024 * 1024):.2f} MB")

        # Print structure type counts
        print(f"\nStructure types:")
        for structure_type, count in stats.get('structure_type_counts', {}).items():
            print(f"  {structure_type}: {count}")

        # Print height statistics
        print(f"\nHeight statistics:")
        print(f"  Min height: {stats.get('min_height', 'N/A')}")
        print(f"  Max height: {stats.get('max_height', 'N/A')}")
        print(f"  Avg height: {stats.get('avg_height', 'N/A')}")

        logger.info("Tower database initialization completed successfully")
        return 0

    except Exception as e:
        logger.error(f"Error initializing tower database: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main())
