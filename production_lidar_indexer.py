#!/usr/bin/env python3
"""
Production LIDAR Indexer

This script creates a comprehensive index of all LIDAR data available in the USGS AWS S3 bucket,
with proper metadata extraction and optimization for production use.

Features:
- Indexes all available LIDAR projects
- Extracts detailed metadata from EPT sources
- Optimizes the database for performance
- Provides progress reporting and error handling
- Creates a production-ready index

Usage:
    python production_lidar_indexer.py [--region REGION] [--limit LIMIT] [--db-path DB_PATH]

Options:
    --region REGION    Region to index (e.g., 'CO' for Colorado, 'all' for all regions)
    --limit LIMIT      Limit the number of projects to index (for testing)
    --db-path DB_PATH  Path to the database file
"""

import os
import sys
import logging
import json
import math
import sqlite3
import argparse
import boto3
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f"lidar_indexer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

# Import the database module
try:
    from utilities.lidar_index_db import (
        init_database, get_database_stats, database_exists, DEFAULT_DB_PATH,
        add_project, add_file, start_crawl, update_crawl, optimize_database
    )
except ImportError:
    logger.error("Could not import database module. Make sure utilities/lidar_index_db.py exists.")
    sys.exit(1)

# Global variables
MAX_WORKERS = 20  # Maximum number of worker threads for file processing
MAX_PROJECT_WORKERS = 5  # Maximum number of worker threads for project processing
BATCH_SIZE = 200  # Number of files to process in a batch
PROGRESS_INTERVAL = 5  # Seconds between progress updates

def initialize_s3_client():
    """
    Initialize the S3 client with credentials from environment variables.

    Returns:
        boto3.client: S3 client or None if initialization fails
    """
    try:
        # Get credentials from environment variables
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-west-2')

        logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4] if aws_access_key_id else 'None'}... Region={aws_region}")

        if not aws_access_key_id or not aws_secret_access_key:
            logger.error("AWS credentials not found in environment variables")
            logger.error("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return None

        # Create S3 client with timeout configuration
        logger.info("Creating S3 client with timeout configuration")
        session = boto3.session.Session()
        s3_client = session.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
            config=boto3.session.Config(
                connect_timeout=10,  # 10 seconds connection timeout
                read_timeout=10,     # 10 seconds read timeout
                retries={'max_attempts': 3}  # Retry configuration
            )
        )

        logger.info("S3 client initialized successfully")
        return s3_client

    except Exception as e:
        logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
        return None

def convert_web_mercator_to_wgs84(x, y):
    """
    Convert Web Mercator (EPSG:3857) coordinates to WGS84 (EPSG:4326).

    Args:
        x: X coordinate in Web Mercator
        y: Y coordinate in Web Mercator

    Returns:
        Tuple[float, float]: Longitude, Latitude in WGS84
    """
    try:
        # Convert Web Mercator to WGS84
        lon = x / 20037508.34 * 180
        lat = y / 20037508.34 * 180
        lat = 180 / math.pi * (2 * math.atan(math.exp(lat * math.pi / 180)) - math.pi / 2)

        return lon, lat
    except Exception as e:
        logger.error(f"Error converting coordinates: {str(e)}", exc_info=True)
        return 0.0, 0.0

def get_projects(s3_client, region=None, limit=None):
    """
    Get all projects from the USGS S3 bucket, optionally filtered by region.

    Args:
        s3_client: Boto3 S3 client
        region: Region code to filter projects (e.g., 'CO' for Colorado)
        limit: Maximum number of projects to return

    Returns:
        List[Dict[str, Any]]: List of projects
    """
    try:
        logger.info(f"Getting projects from USGS S3 bucket{' for region ' + region if region else ''}")

        # List all objects in the bucket
        projects = []
        continuation_token = None

        while True:
            # Parameters for list_objects_v2
            params = {
                'Bucket': 'usgs-lidar-public',
                'Delimiter': '/',
                'RequestPayer': 'requester',
                'MaxKeys': 1000  # Maximum allowed by S3 API
            }

            # Add continuation token if we have one
            if continuation_token:
                params['ContinuationToken'] = continuation_token

            # Make the request
            response = s3_client.list_objects_v2(**params)

            # Process the prefixes (directories)
            for prefix in response.get('CommonPrefixes', []):
                prefix_name = prefix.get('Prefix', '')
                if prefix_name:
                    # Extract project name from prefix
                    project_name = prefix_name.rstrip('/')

                    # Filter by region if specified
                    if region and region.lower() != 'all':
                        if not project_name.startswith(f"{region}_") and f"_{region}_" not in project_name and region.lower() not in project_name.lower():
                            continue

                    # Extract year from project name if possible
                    year = None
                    import re
                    year_match = re.search(r'_(\d{4})(?:_|$)', project_name)
                    if year_match:
                        year = int(year_match.group(1))

                    projects.append({
                        'name': project_name,
                        'prefix': prefix_name,
                        'year': year,
                        'source': 'USGS AWS S3'
                    })
                    logger.info(f"Found project: {project_name}")

                    # Check if we've reached the limit
                    if limit and len(projects) >= limit:
                        logger.info(f"Reached limit of {limit} projects")
                        return projects

            # Check if there are more results
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break

        logger.info(f"Found {len(projects)} projects")
        return projects

    except Exception as e:
        logger.error(f"Error getting projects: {str(e)}", exc_info=True)
        return []

def extract_ept_metadata(s3_client, project_name):
    """
    Extract metadata from EPT files.

    Args:
        s3_client: Boto3 S3 client
        project_name: Project name

    Returns:
        Dict[str, Any]: Metadata from EPT files
    """
    try:
        logger.info(f"Extracting metadata from EPT files for project {project_name}")

        # Initialize metadata dictionary
        metadata = {}

        # Try to get ept.json
        try:
            ept_json_key = f"{project_name}/ept.json"
            response = s3_client.get_object(
                Bucket='usgs-lidar-public',
                Key=ept_json_key,
                RequestPayer='requester'
            )
            ept_data = json.loads(response['Body'].read().decode('utf-8'))

            # Extract metadata from ept.json
            metadata['ept_json'] = ept_data

            # Extract key metadata fields
            if ept_data.get('bounds'):
                metadata['bounds'] = ept_data['bounds']
            if ept_data.get('points'):
                metadata['points'] = ept_data['points']
            if ept_data.get('schema'):
                metadata['schema'] = ept_data['schema']
            if ept_data.get('srs'):
                metadata['srs'] = ept_data['srs']

            logger.info(f"Successfully extracted metadata from ept.json for project {project_name}")
        except Exception as e:
            logger.warning(f"Error getting ept.json for project {project_name}: {str(e)}")

        # Try to get ept-sources/manifest.json
        try:
            manifest_key = f"{project_name}/ept-sources/manifest.json"
            response = s3_client.get_object(
                Bucket='usgs-lidar-public',
                Key=manifest_key,
                RequestPayer='requester'
            )
            manifest_data = json.loads(response['Body'].read().decode('utf-8'))

            # Extract metadata from manifest.json
            metadata['manifest'] = manifest_data

            logger.info(f"Successfully extracted metadata from manifest.json for project {project_name}")
        except Exception as e:
            logger.warning(f"Error getting manifest.json for project {project_name}: {str(e)}")

        return metadata

    except Exception as e:
        logger.error(f"Error extracting EPT metadata for project {project_name}: {str(e)}", exc_info=True)
        return {}

def process_source_file(source, project_id, project_metadata, project_data, db_path):
    """
    Process a source file and add it to the database.

    Args:
        source: Source file data
        project_id: Project ID in the database
        project_metadata: Project metadata
        project_data: Project data
        db_path: Path to the database file

    Returns:
        int: File ID in the database
    """
    try:
        # Extract file information
        path = source.get('path', '')
        bounds = source.get('bounds', [])
        points = source.get('points', 0)

        # Skip if no path or bounds
        if not path or not bounds or len(bounds) != 6:
            logger.warning(f"Skipping source file with invalid data: {path}")
            return 0

        # Extract filename from path
        filename = path.split('/')[-1]

        # Convert bounds from Web Mercator to WGS84
        min_x_mercator, min_y_mercator, min_z = bounds[0], bounds[1], bounds[2]
        max_x_mercator, max_y_mercator, max_z = bounds[3], bounds[4], bounds[5]

        min_lon, min_lat = convert_web_mercator_to_wgs84(min_x_mercator, min_y_mercator)
        max_lon, max_lat = convert_web_mercator_to_wgs84(max_x_mercator, max_y_mercator)

        # Create EPT metadata URLs
        ept_json_url = f"s3://usgs-lidar-public/{project_data['name']}/ept.json"
        ept_sources_url = f"s3://usgs-lidar-public/{project_data['name']}/ept-sources/list.json"
        ept_metadata_url = f"s3://usgs-lidar-public/{project_data['name']}/ept-sources/{filename}.json" if filename else ''

        # Create file data
        file_data = {
            'bucket': 'usgs-lidar-public',
            'key': path.replace('s3://usgs-lidar/', ''),
            'filename': filename,
            'size': source.get('size', 0),
            'format': filename.split('.')[-1].lower(),
            'boundingBox': {
                'minX': min_lon,
                'minY': min_lat,
                'maxX': max_lon,
                'maxY': max_lat
            },
            'polygon_points': [
                (min_lat, min_lon),  # Bottom-left corner
                (min_lat, max_lon),  # Bottom-right corner
                (max_lat, max_lon),  # Top-right corner
                (max_lat, min_lon),  # Top-left corner
                (min_lat, min_lon)   # Back to start to close the polygon
            ],
            'metadata_source': 'ept-sources',
            'pointCount': points,
            'resolution': 1.0,  # Default resolution
            'pointSpacing': 1.0,  # Default point spacing
            'project_year': project_metadata.get('year'),
            'coordinateSystem': project_metadata.get('srs', {}).get('wkt', ''),
            'eptJsonUrl': ept_json_url,
            'eptSourcesUrl': ept_sources_url,
            'eptMetadataUrl': ept_metadata_url,
            'metadata': json.dumps({
                'schema': project_metadata.get('schema', []),
                'raw': source
            })
        }

        # Add file to database
        file_id = add_file(file_data, project_id, db_path)

        return file_id

    except Exception as e:
        logger.error(f"Error processing source file: {str(e)}", exc_info=True)
        return 0

def process_project(s3_client, project_data, db_path):
    """
    Process a project and add it to the database.

    Args:
        s3_client: Boto3 S3 client
        project_data: Project data
        db_path: Path to the database file

    Returns:
        Dict[str, int]: Statistics about the processing
    """
    try:
        project_name = project_data['name']
        logger.info(f"Processing project: {project_name}")

        # Extract EPT metadata
        project_metadata = extract_ept_metadata(s3_client, project_name)

        # Add project to database
        project_id = add_project(project_data, db_path)

        # Initialize stats
        stats = {
            'files_added': 0,
            'files_updated': 0,
            'errors': 0
        }

        # Check if we have manifest data
        if 'manifest' in project_metadata and isinstance(project_metadata['manifest'], list):
            manifest_data = project_metadata['manifest']
            logger.info(f"Processing {len(manifest_data)} files from manifest for project {project_name}")

            # Process files in batches
            for i in range(0, len(manifest_data), BATCH_SIZE):
                batch = manifest_data[i:i+BATCH_SIZE]
                logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(manifest_data) + BATCH_SIZE - 1)//BATCH_SIZE} ({len(batch)} files)")

                # Process each file in the batch
                with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                    # Submit tasks
                    future_to_source = {
                        executor.submit(process_source_file, source, project_id, project_metadata, project_data, db_path): source
                        for source in batch
                    }

                    # Process results as they complete
                    for future in as_completed(future_to_source):
                        source = future_to_source[future]
                        try:
                            file_id = future.result()
                            if file_id > 0:
                                stats['files_added'] += 1
                            else:
                                stats['files_updated'] += 1
                        except Exception as e:
                            logger.error(f"Error processing file: {str(e)}", exc_info=True)
                            stats['errors'] += 1
        else:
            logger.warning(f"No manifest data found for project {project_name}")

        logger.info(f"Processed project {project_name}: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error processing project {project_data['name']}: {str(e)}", exc_info=True)
        return {
            'files_added': 0,
            'files_updated': 0,
            'errors': 1
        }

def index_projects(s3_client, projects, db_path=DEFAULT_DB_PATH):
    """
    Index all projects.

    Args:
        s3_client: Boto3 S3 client
        projects: List of projects to index
        db_path: Path to the database file

    Returns:
        Dict[str, int]: Statistics about the indexing process
    """
    try:
        # Start crawl
        crawl_id = start_crawl(db_path)

        # Initialize stats
        stats = {
            'projects_added': 0,
            'projects_updated': 0,
            'files_added': 0,
            'files_updated': 0,
            'errors': 0
        }

        # Initialize progress tracking
        total_projects = len(projects)
        start_time = time.time()
        last_progress_time = start_time

        # Process each project
        for i, project_data in enumerate(projects):
            try:
                # Process the project
                project_stats = process_project(s3_client, project_data, db_path)

                # Update stats
                if project_stats.get('files_added', 0) > 0:
                    stats['projects_added'] += 1
                else:
                    stats['projects_updated'] += 1

                stats['files_added'] += project_stats.get('files_added', 0)
                stats['files_updated'] += project_stats.get('files_updated', 0)
                stats['errors'] += project_stats.get('errors', 0)

                # Update progress
                current_time = time.time()
                if current_time - last_progress_time >= PROGRESS_INTERVAL:
                    elapsed_time = current_time - start_time
                    progress = (i + 1) / total_projects
                    estimated_total_time = elapsed_time / progress if progress > 0 else 0
                    estimated_remaining_time = estimated_total_time - elapsed_time

                    logger.info(f"Progress: {i+1}/{total_projects} projects ({progress:.1%})")
                    logger.info(f"Elapsed time: {elapsed_time:.1f}s, Estimated remaining time: {estimated_remaining_time:.1f}s")
                    logger.info(f"Stats so far: {stats}")

                    # Update crawl status
                    update_crawl(crawl_id, 'in_progress', stats, None, db_path)

                    last_progress_time = current_time

            except Exception as e:
                logger.error(f"Error processing project {project_data['name']}: {str(e)}", exc_info=True)
                stats['errors'] += 1

        # Update crawl status
        update_crawl(crawl_id, 'completed', stats, None, db_path)

        logger.info(f"Indexing completed: {stats}")
        return stats

    except Exception as e:
        logger.error(f"Error indexing projects: {str(e)}", exc_info=True)
        if crawl_id:
            update_crawl(crawl_id, 'failed', stats, str(e), db_path)
        return {'error': str(e)}

def main():
    """
    Main function.
    """
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='Production LIDAR Indexer')
        parser.add_argument('--region', type=str, default='all', help='Region to index (e.g., CO for Colorado, all for all regions)')
        parser.add_argument('--limit', type=int, help='Limit the number of projects to index (for testing)')
        parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH, help='Path to the database file')
        args = parser.parse_args()

        # Set AWS credentials
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-west-2')

        if not aws_access_key_id or not aws_secret_access_key:
            logger.error("AWS credentials not found in environment variables")
            logger.error("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            return 1

        logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4]}... Region={aws_region}")

        # Initialize database
        db_path = args.db_path

        # Check if database already exists
        if database_exists(db_path):
            logger.info(f"Database already exists at {db_path}")

            # Get initial stats
            initial_stats = get_database_stats(db_path)
            logger.info("Initial database statistics:")
            logger.info(f"  Projects: {initial_stats['project_count']}")
            logger.info(f"  Files: {initial_stats['file_count']}")

            # Ask for confirmation to continue
            response = input("Do you want to continue indexing and add to the existing database? (y/n): ")
            if response.lower() != 'y':
                logger.info("Indexing cancelled by user")
                return 0
        else:
            logger.info(f"Initializing database at {db_path}")
            init_database(db_path)

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if not s3_client:
            logger.error("Failed to initialize S3 client")
            return 1

        # Get projects
        projects = get_projects(s3_client, args.region, args.limit)

        if not projects:
            logger.error(f"No projects found{' for region ' + args.region if args.region != 'all' else ''}")
            return 1

        # Index projects
        logger.info(f"Starting indexing of {len(projects)} projects")
        start_time = datetime.now()

        stats = index_projects(s3_client, projects, db_path)

        end_time = datetime.now()
        duration = end_time - start_time
        logger.info(f"Indexing completed in {duration}")

        if 'error' in stats:
            logger.error(f"Indexing failed: {stats['error']}")
            return 1

        # Optimize database
        logger.info("Optimizing database")
        optimize_database(db_path)

        # Get final stats
        final_stats = get_database_stats(db_path)
        logger.info("Final database statistics:")
        logger.info(f"  Projects: {final_stats['project_count']}")
        logger.info(f"  Files: {final_stats['file_count']}")
        logger.info(f"  Database size: {final_stats['db_size'] / (1024 * 1024):.2f} MB")

        if final_stats.get('format_counts'):
            logger.info("File formats:")
            for format, count in final_stats.get('format_counts', {}).items():
                logger.info(f"  {format}: {count}")

        logger.info("LIDAR indexing completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Indexing interrupted by user")
        return 0

    except Exception as e:
        logger.error(f"Error indexing LIDAR data: {str(e)}", exc_info=True)
        return 1

if __name__ == '__main__':
    sys.exit(main())
