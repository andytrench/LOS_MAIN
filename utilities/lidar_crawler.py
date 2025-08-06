"""
LIDAR Crawler Module

This module provides functions to crawl the USGS AWS S3 bucket and index all LIDAR files.
It populates the LIDAR index database with project and file information.
"""

import os
import sys
import logging
import boto3
import json
import re
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import concurrent.futures
from shapely.geometry import box, Polygon, mapping
import time

# Import the database module
from utilities.lidar_index_db import (
    init_database, add_project, add_file, start_crawl, update_crawl,
    get_database_stats, database_exists, DEFAULT_DB_PATH
)

# Configure logging
logger = logging.getLogger(__name__)

class LidarCrawler:
    """
    Crawler for indexing LIDAR files in the USGS AWS S3 bucket.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        """
        Initialize the LIDAR crawler.

        Args:
            db_path: Path to the database file
        """
        self.db_path = db_path
        self.s3_client = None
        self.crawl_id = None
        self.stats = {
            'projects_added': 0,
            'projects_updated': 0,
            'files_added': 0,
            'files_updated': 0,
            'errors': 0
        }

    def initialize_s3_client(self) -> bool:
        """
        Initialize the S3 client with credentials from environment variables.

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get credentials from environment variables
            aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
            aws_region = os.environ.get('AWS_REGION', 'us-west-2')

            logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4] if aws_access_key_id else 'None'}... Region={aws_region}")

            if not aws_access_key_id or not aws_secret_access_key:
                logger.error("AWS credentials not found in environment variables")
                return False

            # Create S3 client with timeout configuration
            logger.info("Creating S3 client with timeout configuration")
            session = boto3.session.Session()
            self.s3_client = session.client(
                's3',
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                region_name=aws_region,
                config=boto3.session.Config(
                    connect_timeout=10,  # 10 seconds connection timeout
                    read_timeout=10,     # 10 seconds read timeout
                    retries={'max_attempts': 2}  # Limit retries to avoid long hangs
                )
            )

            logger.info("S3 client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
            return False

    def list_top_level_directories(self) -> List[str]:
        """
        List top-level directories in the USGS LIDAR bucket.

        Returns:
            List[str]: List of top-level directories
        """
        try:
            logger.info("Listing top-level directories in USGS LIDAR bucket")

            # List objects with delimiter to get top-level directories
            response = self.s3_client.list_objects_v2(
                Bucket='usgs-lidar-public',
                Delimiter='/',
                RequestPayer='requester'
            )

            # Extract directory names from CommonPrefixes
            directories = []
            for prefix in response.get('CommonPrefixes', []):
                prefix_name = prefix.get('Prefix', '')
                if prefix_name:
                    directories.append(prefix_name)
                    logger.info(f"Found top-level directory: {prefix_name}")

            return directories

        except Exception as e:
            logger.error(f"Error listing top-level directories: {str(e)}", exc_info=True)
            return []

    def list_projects(self, prefix: str = 'Projects/') -> List[Dict[str, Any]]:
        """
        List projects in the USGS LIDAR bucket.

        Args:
            prefix: Directory prefix

        Returns:
            List[Dict[str, Any]]: List of projects
        """
        try:
            logger.info(f"Listing projects with prefix: {prefix}")

            # List objects with delimiter to get projects
            response = self.s3_client.list_objects_v2(
                Bucket='usgs-lidar-public',
                Prefix=prefix,
                Delimiter='/',
                RequestPayer='requester'
            )

            # Extract project names from CommonPrefixes
            projects = []
            for prefix_obj in response.get('CommonPrefixes', []):
                prefix_name = prefix_obj.get('Prefix', '')
                if prefix_name:
                    # Extract project name from prefix
                    project_name = prefix_name.split('/')[-2] if prefix_name.endswith('/') else prefix_name.split('/')[-1]
                    if project_name:
                        # Extract year from project name if possible
                        year = None
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

            return projects

        except Exception as e:
            logger.error(f"Error listing projects: {str(e)}", exc_info=True)
            return []

    def crawl_projects(self, max_projects: int = None) -> None:
        """
        Crawl projects in the USGS LIDAR bucket.

        Args:
            max_projects: Maximum number of projects to crawl (None for all)
        """
        try:
            # Start crawl
            self.crawl_id = start_crawl(self.db_path)

            # List top-level directories
            top_level_dirs = self.list_top_level_directories()

            # Check if Projects directory exists
            projects_dir = next((d for d in top_level_dirs if d.startswith('Projects/')), None)

            if projects_dir:
                # List projects in the Projects directory
                logger.info(f"Found Projects directory: {projects_dir}")
                all_projects = self.list_projects(projects_dir)
            else:
                # If Projects directory doesn't exist, treat top-level directories as projects
                logger.warning("Projects directory not found in USGS LIDAR bucket")
                logger.info("Treating top-level directories as projects")

                all_projects = []
                for dir_name in top_level_dirs:
                    # Skip directories that don't look like LIDAR projects
                    if not any(keyword in dir_name.lower() for keyword in ['lidar', 'lpc', 'las', 'laz', 'point', 'cloud', 'dem']):
                        continue

                    # Extract project name from directory name
                    project_name = dir_name.rstrip('/')

                    # Extract year from project name if possible
                    year = None
                    year_match = re.search(r'_(\d{4})(?:_|$)', project_name)
                    if year_match:
                        year = int(year_match.group(1))

                    all_projects.append({
                        'name': project_name,
                        'prefix': dir_name,
                        'year': year,
                        'source': 'USGS AWS S3'
                    })
                    logger.info(f"Found project: {project_name}")

            if not all_projects:
                logger.error("No projects found in USGS LIDAR bucket")
                update_crawl(self.crawl_id, 'failed', self.stats,
                            "No projects found", self.db_path)
                return
            logger.info(f"Found {len(all_projects)} projects in USGS LIDAR bucket")

            # Limit the number of projects if specified
            if max_projects and len(all_projects) > max_projects:
                logger.info(f"Limiting to {max_projects} projects for crawling")
                all_projects = all_projects[:max_projects]

            # Process each project
            for i, project_data in enumerate(all_projects):
                try:
                    logger.info(f"Processing project {i+1}/{len(all_projects)}: {project_data['name']}")

                    # Add project to database
                    project_id = add_project(project_data, self.db_path)

                    # Update stats
                    if project_id > 0:
                        self.stats['projects_added'] += 1
                    else:
                        self.stats['projects_updated'] += 1

                    # Process files in the project
                    self.crawl_project_files(project_data, project_id)

                except Exception as e:
                    logger.error(f"Error processing project {project_data['name']}: {str(e)}", exc_info=True)
                    self.stats['errors'] += 1

            # Update crawl status
            update_crawl(self.crawl_id, 'completed', self.stats, None, self.db_path)

            logger.info(f"Crawl completed: {self.stats}")

        except Exception as e:
            logger.error(f"Error crawling projects: {str(e)}", exc_info=True)
            if self.crawl_id:
                update_crawl(self.crawl_id, 'failed', self.stats, str(e), self.db_path)

    def crawl_project_files(self, project_data: Dict[str, Any], project_id: int) -> None:
        """
        Crawl files in a project.

        Args:
            project_data: Project data
            project_id: Project ID in the database
        """
        try:
            project_name = project_data.get('name')
            project_prefix = project_data.get('prefix')

            logger.info(f"Crawling files in project: {project_name}")

            # List of possible subdirectories to check for LAZ/LAS files
            subdirs = [
                '',  # Project root
                'laz/',
                'las/',
                'las/tiled/',
                'pointcloud/',
                'points/',
                'data/',
                'lidar/',
                'tiles/'
            ]

            # Process each subdirectory
            for subdir in subdirs:
                prefix = f"{project_prefix}{subdir}"
                self.crawl_directory(prefix, project_id)

        except Exception as e:
            logger.error(f"Error crawling files in project {project_data.get('name')}: {str(e)}", exc_info=True)
            self.stats['errors'] += 1

    def crawl_directory(self, prefix: str, project_id: int, max_files: int = None) -> None:
        """
        Crawl files in a directory.

        Args:
            prefix: Directory prefix
            project_id: Project ID in the database
            max_files: Maximum number of files to process (None for all)
        """
        try:
            logger.info(f"Crawling directory: {prefix}")

            # List objects in the directory
            continuation_token = None
            file_count = 0

            while True:
                # Parameters for list_objects_v2
                params = {
                    'Bucket': 'usgs-lidar-public',
                    'Prefix': prefix,
                    'RequestPayer': 'requester',
                    'MaxKeys': 1000  # Maximum allowed by S3 API
                }

                # Add continuation token if we have one
                if continuation_token:
                    params['ContinuationToken'] = continuation_token

                # Make the request
                response = self.s3_client.list_objects_v2(**params)

                # Process the files
                for item in response.get('Contents', []):
                    key = item.get('Key')
                    if key and (key.lower().endswith('.laz') or key.lower().endswith('.las')):
                        # Process the file
                        self.process_file({
                            'bucket': 'usgs-lidar-public',
                            'key': key,
                            'size': item.get('Size'),
                            'last_modified': item.get('LastModified')
                        }, project_id)

                        file_count += 1

                        # Check if we've reached the maximum number of files
                        if max_files and file_count >= max_files:
                            logger.info(f"Reached maximum file limit ({max_files})")
                            return

                # Check if there are more results
                if response.get('IsTruncated'):
                    continuation_token = response.get('NextContinuationToken')
                else:
                    break

            logger.info(f"Processed {file_count} files in directory {prefix}")

        except Exception as e:
            logger.error(f"Error crawling directory {prefix}: {str(e)}", exc_info=True)
            self.stats['errors'] += 1

    def process_file(self, file_data: Dict[str, Any], project_id: int) -> None:
        """
        Process a file and add it to the database.

        Args:
            file_data: File data
            project_id: Project ID in the database
        """
        try:
            key = file_data.get('key')
            filename = key.split('/')[-1] if key else ''

            # Extract project name from key
            key_parts = key.split('/')
            project_name = key_parts[0] if len(key_parts) > 0 else ''

            # Extract bounding box from EPT data
            bbox = self.extract_bbox_from_ept(project_name)
            if not bbox:
                # Fall back to filename-based extraction
                bbox = self.extract_bbox_from_filename(filename, key)

            if bbox:
                file_data['boundingBox'] = bbox

                # Create polygon points from bounding box
                min_x = bbox.get('minX')
                min_y = bbox.get('minY')
                max_x = bbox.get('maxX')
                max_y = bbox.get('maxY')

                if all(v is not None for v in [min_x, min_y, max_x, max_y]):
                    # Create polygon points in the correct order for display
                    polygon_points = [
                        (min_y, min_x),  # Bottom-left corner
                        (min_y, max_x),  # Bottom-right corner
                        (max_y, max_x),  # Top-right corner
                        (max_y, min_x),  # Top-left corner
                        (min_y, min_x)   # Back to start to close the polygon
                    ]
                    file_data['polygon_points'] = polygon_points

            # Add metadata source
            file_data['metadata_source'] = 'ept' if bbox else 'filename'

            # Add file to database
            file_id = add_file(file_data, project_id, self.db_path)

            # Update stats
            if file_id > 0:
                self.stats['files_added'] += 1
            else:
                self.stats['files_updated'] += 1

        except Exception as e:
            logger.error(f"Error processing file {file_data.get('key')}: {str(e)}", exc_info=True)
            self.stats['errors'] += 1

    def extract_bbox_from_ept(self, project_name: str) -> Optional[Dict[str, float]]:
        """
        Extract bounding box from EPT data.

        Args:
            project_name: Project name

        Returns:
            Optional[Dict[str, float]]: Bounding box if found, None otherwise
        """
        try:
            logger.info(f"Extracting bounding box from EPT data for project {project_name}")

            # Initialize S3 client if not already initialized
            if self.s3_client is None:
                if not self.initialize_s3_client():
                    return None

            # First, try to get the boundary.json file
            boundary_key = f"{project_name}/boundary.json"
            try:
                response = self.s3_client.get_object(
                    Bucket='usgs-lidar-public',
                    Key=boundary_key,
                    RequestPayer='requester'
                )
                boundary_data = json.loads(response['Body'].read().decode('utf-8'))

                logger.info(f"Found boundary.json for project {project_name}")

                # Extract bounding box from GeoJSON
                if boundary_data.get('type') == 'MultiPolygon' and boundary_data.get('coordinates'):
                    # Extract coordinates from the first polygon
                    coords = boundary_data['coordinates'][0][0]

                    # Calculate bounding box
                    lons = [coord[0] for coord in coords]
                    lats = [coord[1] for coord in coords]

                    min_x = min(lons)
                    min_y = min(lats)
                    max_x = max(lons)
                    max_y = max(lats)

                    logger.info(f"Extracted bounding box from boundary.json: {min_x}, {min_y}, {max_x}, {max_y}")

                    return {
                        'minX': min_x,
                        'minY': min_y,
                        'maxX': max_x,
                        'maxY': max_y
                    }
            except Exception as e:
                logger.warning(f"Error getting boundary.json for project {project_name}: {str(e)}")

            # If boundary.json fails, try ept.json
            ept_key = f"{project_name}/ept.json"
            try:
                response = self.s3_client.get_object(
                    Bucket='usgs-lidar-public',
                    Key=ept_key,
                    RequestPayer='requester'
                )
                ept_data = json.loads(response['Body'].read().decode('utf-8'))

                logger.info(f"Found ept.json for project {project_name}")

                # Extract bounding box from EPT data
                if ept_data.get('bounds'):
                    bounds = ept_data['bounds']

                    # EPT bounds are in the format [minX, minY, minZ, maxX, maxY, maxZ]
                    min_x = bounds[0]
                    min_y = bounds[1]
                    max_x = bounds[3]
                    max_y = bounds[4]

                    # Check if the bounds are in a projected coordinate system
                    if ept_data.get('srs') and ept_data['srs'].get('wkt'):
                        # This is likely in a projected coordinate system (e.g., EPSG:3857)
                        # We need to convert to WGS84 (EPSG:4326) for our database
                        # For simplicity, we'll use a rough approximation for Web Mercator
                        if ept_data['srs'].get('horizontal') == '3857':
                            # Convert Web Mercator to WGS84
                            # These are very rough approximations
                            lon1 = min_x / 20037508.34 * 180
                            lat1 = min_y / 20037508.34 * 180
                            lat1 = 180 / math.pi * (2 * math.atan(math.exp(lat1 * math.pi / 180)) - math.pi / 2)

                            lon2 = max_x / 20037508.34 * 180
                            lat2 = max_y / 20037508.34 * 180
                            lat2 = 180 / math.pi * (2 * math.atan(math.exp(lat2 * math.pi / 180)) - math.pi / 2)

                            min_x = lon1
                            min_y = lat1
                            max_x = lon2
                            max_y = lat2

                    logger.info(f"Extracted bounding box from ept.json: {min_x}, {min_y}, {max_x}, {max_y}")

                    return {
                        'minX': min_x,
                        'minY': min_y,
                        'maxX': max_x,
                        'maxY': max_y
                    }
            except Exception as e:
                logger.warning(f"Error getting ept.json for project {project_name}: {str(e)}")

            # If both methods fail, fall back to default bounding box
            logger.warning(f"Could not extract bounding box from EPT data for project {project_name}, using default")

            # Get base coordinates based on project region
            base_lon, base_lat, _ = self.get_region_parameters(project_name)

            # Create a default bounding box
            min_x = base_lon - 0.5
            min_y = base_lat - 0.5
            max_x = base_lon + 0.5
            max_y = base_lat + 0.5

            return {
                'minX': min_x,
                'minY': min_y,
                'maxX': max_x,
                'maxY': max_y
            }

        except Exception as e:
            logger.error(f"Error extracting bbox from EPT data for project {project_name}: {str(e)}", exc_info=True)
            return None

    def extract_bbox_from_filename(self, filename: str, key: str) -> Optional[Dict[str, float]]:
        """
        Extract bounding box from filename.

        Args:
            filename: Filename
            key: S3 key

        Returns:
            Optional[Dict[str, float]]: Bounding box if found, None otherwise
        """
        try:
            # Extract project name from key
            key_parts = key.split('/')
            project_name = key_parts[0] if len(key_parts) > 0 else ''

            # First, try to get the bounding box from EPT data
            ept_bbox = self.extract_bbox_from_ept(project_name)
            if ept_bbox:
                return ept_bbox

            # If EPT data is not available, fall back to filename-based extraction
            logger.warning(f"Falling back to filename-based extraction for {filename}")

            # Get base coordinates based on project region
            base_lon, base_lat, _ = self.get_region_parameters(project_name)

            # Create a default bounding box
            min_x = base_lon - 0.1
            min_y = base_lat - 0.1
            max_x = base_lon + 0.1
            max_y = base_lat + 0.1

            return {
                'minX': min_x,
                'minY': min_y,
                'maxX': max_x,
                'maxY': max_y
            }

        except Exception as e:
            logger.error(f"Error extracting bbox from filename {filename}: {str(e)}", exc_info=True)
            return None

    def get_region_parameters(self, project_name: str) -> Tuple[float, float, float]:
        """
        Get region-specific parameters for coordinate conversion.

        Args:
            project_name: Project name

        Returns:
            Tuple[float, float, float]: Base longitude, base latitude, scale factor
        """
        # Default parameters
        base_lon = -100.0
        base_lat = 40.0
        scale_factor = 0.00001

        # Check for specific regions
        project_lower = project_name.lower()

        # California
        if 'ca_' in project_lower or 'california' in project_lower:
            if 'losangeles' in project_lower or 'los_angeles' in project_lower:
                base_lon = -118.5
                base_lat = 34.0
            elif 'sanfrancisco' in project_lower or 'san_francisco' in project_lower:
                base_lon = -122.5
                base_lat = 37.7
            elif 'sandiego' in project_lower or 'san_diego' in project_lower:
                base_lon = -117.2
                base_lat = 32.7
            else:
                base_lon = -120.0
                base_lat = 37.0

        # Colorado
        elif 'co_' in project_lower or 'colorado' in project_lower:
            if 'denver' in project_lower:
                base_lon = -105.0
                base_lat = 39.7
            elif 'soplatteriver' in project_lower or 'so_platte_river' in project_lower:
                base_lon = -105.0
                base_lat = 39.0
            else:
                base_lon = -105.5
                base_lat = 39.0

        # Texas
        elif 'tx_' in project_lower or 'texas' in project_lower:
            if 'houston' in project_lower or 'harvey' in project_lower:
                base_lon = -95.4
                base_lat = 29.7
            elif 'dallas' in project_lower:
                base_lon = -96.8
                base_lat = 32.8
            else:
                base_lon = -97.0
                base_lat = 31.0

        return base_lon, base_lat, scale_factor

    def run(self, max_projects: int = None) -> None:
        """
        Run the LIDAR crawler.

        Args:
            max_projects: Maximum number of projects to crawl (None for all)
        """
        try:
            # Initialize database if it doesn't exist
            if not database_exists(self.db_path):
                logger.info(f"Initializing database at {self.db_path}")
                init_database(self.db_path)

            # Initialize S3 client
            if not self.initialize_s3_client():
                logger.error("Failed to initialize S3 client")
                return

            # Crawl projects
            self.crawl_projects(max_projects)

            # Print stats
            logger.info("Crawl statistics:")
            logger.info(f"  Projects added: {self.stats['projects_added']}")
            logger.info(f"  Projects updated: {self.stats['projects_updated']}")
            logger.info(f"  Files added: {self.stats['files_added']}")
            logger.info(f"  Files updated: {self.stats['files_updated']}")
            logger.info(f"  Errors: {self.stats['errors']}")

            # Print database stats
            db_stats = get_database_stats(self.db_path)
            logger.info("Database statistics:")
            logger.info(f"  Database size: {db_stats['db_size'] / (1024 * 1024):.2f} MB")
            logger.info(f"  Projects: {db_stats['project_count']}")
            logger.info(f"  Files: {db_stats['file_count']}")

        except Exception as e:
            logger.error(f"Error running LIDAR crawler: {str(e)}", exc_info=True)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='LIDAR Crawler')
    parser.add_argument('--max-projects', type=int, help='Maximum number of projects to crawl')
    parser.add_argument('--db-path', type=str, default=DEFAULT_DB_PATH, help='Path to the database file')
    args = parser.parse_args()

    # Run crawler
    crawler = LidarCrawler(args.db_path)
    crawler.run(args.max_projects)
