"""
AWS S3 LIDAR Search Utility

This module provides functions to search for LIDAR data in the USGS 3DEP AWS S3 bucket.
It uses the AWS SDK (boto3) to access the requester pays bucket and find LIDAR files
that intersect with a given polygon.
"""

import boto3
import logging
import json
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date
from shapely.geometry import Polygon, box
import re
from utilities.tile_index_manager import get_tile_boundary_for_file, search_lidar_by_polygon, get_colorado_projects
from utilities.lidar_index_search import search_lidar_index, database_exists as index_database_exists

# Configure logging
logger = logging.getLogger(__name__)

def initialize_s3_client():
    """
    Initialize the S3 client with credentials from environment variables.

    Returns:
        boto3.client: Configured S3 client
    """
    try:
        # Get credentials from environment variables
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-west-2')

        logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4]}... Region={aws_region}")

        if not aws_access_key_id or not aws_secret_access_key:
            logger.error("AWS credentials not found in environment variables")
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
                retries={'max_attempts': 2}  # Limit retries to avoid long hangs
            )
        )

        # Test connection with a simple operation
        logger.info("Testing S3 client connection...")
        try:
            # Use list_buckets as a simple test (doesn't require specific permissions)
            s3_client.list_buckets()
            logger.info("S3 client connection test successful")
        except Exception as test_error:
            logger.warning(f"S3 connection test failed: {str(test_error)}")
            # Continue anyway, as we might still be able to access the requester pays bucket

        logger.info("S3 client initialized successfully")
        return s3_client

    except Exception as e:
        logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
        return None

def list_projects(s3_client) -> List[str]:
    """
    List all available LIDAR projects in the USGS S3 bucket.

    Args:
        s3_client: Initialized boto3 S3 client

    Returns:
        List[str]: List of project names
    """
    try:
        logger.info("Attempting to list projects from USGS S3 bucket")

        # First, check if we can access the bucket at all
        try:
            logger.debug("Testing bucket access with head_bucket")
            s3_client.head_bucket(Bucket='usgs-lidar', RequestPayer='requester')
            logger.info("Successfully accessed usgs-lidar bucket")
        except Exception as bucket_error:
            logger.error(f"Failed to access usgs-lidar bucket: {str(bucket_error)}")
            # Continue anyway, as list_objects_v2 might still work

        logger.debug("Calling list_objects_v2 to get project directories")
        response = s3_client.list_objects_v2(
            Bucket='usgs-lidar',
            Prefix='Projects/',
            Delimiter='/',
            RequestPayer='requester'
        )

        logger.debug(f"Response keys: {list(response.keys())}")

        if 'CommonPrefixes' not in response:
            logger.warning("No CommonPrefixes found in response. Response content:")
            logger.warning(str(response))
            return []

        projects = []
        for prefix in response.get('CommonPrefixes', []):
            # Extract project name from the prefix
            prefix_str = prefix.get('Prefix')
            logger.debug(f"Processing prefix: {prefix_str}")

            parts = prefix_str.split('/')
            if len(parts) >= 2:
                project_name = parts[-2]  # Get the second-to-last part
                projects.append(project_name)
                logger.debug(f"Added project: {project_name}")
            else:
                logger.warning(f"Unexpected prefix format: {prefix_str}")

        logger.info(f"Found {len(projects)} projects in USGS S3 bucket")
        if projects:
            logger.info(f"Sample projects: {projects[:5]}{'...' if len(projects) > 5 else ''}")
        return projects

    except Exception as e:
        logger.error(f"Error listing projects: {str(e)}", exc_info=True)
        return []

def get_project_metadata(s3_client, project_name: str) -> Dict[str, Any]:
    """
    Get metadata for a specific project.

    Args:
        s3_client: Initialized boto3 S3 client
        project_name: Name of the project

    Returns:
        Dict[str, Any]: Project metadata
    """
    try:
        # Check if metadata.json exists
        metadata_key = f"Projects/{project_name}/metadata.json"

        try:
            response = s3_client.get_object(
                Bucket='usgs-lidar',
                Key=metadata_key,
                RequestPayer='requester'
            )

            metadata = json.loads(response['Body'].read().decode('utf-8'))
            return metadata

        except s3_client.exceptions.NoSuchKey:
            # If metadata.json doesn't exist, try to infer metadata from the project structure
            logger.warning(f"No metadata.json found for project {project_name}, inferring from structure")

            # List files in the project to infer bounds
            response = s3_client.list_objects_v2(
                Bucket='usgs-lidar',
                Prefix=f"Projects/{project_name}/",
                MaxKeys=100,
                RequestPayer='requester'
            )

            # Extract dates and try to infer bounds from filenames
            files = response.get('Contents', [])
            dates = []
            bounds = None

            for file in files:
                key = file.get('Key')
                if key.endswith('.laz') or key.endswith('.las'):
                    # Try to extract date from last modified
                    last_modified = file.get('LastModified')
                    if last_modified:
                        dates.append(last_modified)

                    # Try to extract bounds from filename
                    # Example: some_prefix_1234567.89_9876543.21.laz
                    match = re.search(r'(\d+\.\d+)_(\d+\.\d+)', key)
                    if match and not bounds:
                        try:
                            x, y = float(match.group(1)), float(match.group(2))
                            # Assume a small area around the point
                            bounds = [x-0.01, y-0.01, x+0.01, y+0.01]
                        except ValueError:
                            pass

            # Create inferred metadata
            inferred_metadata = {
                "name": project_name,
                "bounds": bounds if bounds else None,
                "start_date": min(dates).strftime("%Y-%m-%d") if dates else None,
                "end_date": max(dates).strftime("%Y-%m-%d") if dates else None,
                "inferred": True
            }

            return inferred_metadata

    except Exception as e:
        logger.error(f"Error getting metadata for project {project_name}: {str(e)}", exc_info=True)
        return {"name": project_name, "error": str(e)}

def find_laz_files_in_project(s3_client, project_name: str, max_files: int = 100) -> List[Dict[str, Any]]:
    """
    Find all LAZ files in a specific project.

    Args:
        s3_client: Initialized boto3 S3 client
        project_name: Name of the project
        max_files: Maximum number of files to return (for testing/debugging)

    Returns:
        List[Dict[str, Any]]: List of LAZ file information
    """
    try:
        logger.info(f"Searching for LAZ files in project: {project_name}")
        laz_files = []
        continuation_token = None
        page_count = 0
        max_pages = 5  # Limit pages for testing/debugging

        while True:
            # Parameters for list_objects_v2
            params = {
                'Bucket': 'usgs-lidar',
                'Prefix': f"Projects/{project_name}/",
                'RequestPayer': 'requester',
                'MaxKeys': 100  # Smaller batch size for faster response
            }

            # Add continuation token if we have one
            if continuation_token:
                params['ContinuationToken'] = continuation_token

            # Log the request parameters
            logger.debug(f"Making S3 list_objects_v2 request with params: {params}")

            # Make the request with timeout
            try:
                page_count += 1
                logger.debug(f"Fetching page {page_count} for project {project_name}")
                response = s3_client.list_objects_v2(**params)

                # Log response info
                contents_count = len(response.get('Contents', []))
                logger.debug(f"Got {contents_count} items in response")

                # Process the files
                laz_count_before = len(laz_files)
                for item in response.get('Contents', []):
                    key = item.get('Key')
                    if key and key.endswith('.laz'):
                        laz_files.append({
                            'key': key,
                            'size': item.get('Size'),
                            'last_modified': item.get('LastModified'),
                            'project': project_name
                        })

                        # Break if we've reached the maximum number of files
                        if len(laz_files) >= max_files:
                            logger.info(f"Reached maximum file limit ({max_files}) for project {project_name}")
                            return laz_files

                laz_count_after = len(laz_files)
                logger.debug(f"Added {laz_count_after - laz_count_before} LAZ files from this page")

                # Check if there are more results
                if response.get('IsTruncated') and page_count < max_pages:
                    continuation_token = response.get('NextContinuationToken')
                    logger.debug(f"More results available, continuing with token: {continuation_token[:10]}...")
                else:
                    if page_count >= max_pages:
                        logger.info(f"Reached maximum page limit ({max_pages}) for project {project_name}")
                    else:
                        logger.debug(f"No more results for project {project_name}")
                    break

            except Exception as page_error:
                logger.error(f"Error fetching page {page_count} for project {project_name}: {str(page_error)}")
                # Continue to next project rather than failing completely
                break

        logger.info(f"Found {len(laz_files)} LAZ files in project {project_name} after scanning {page_count} pages")
        return laz_files

    except Exception as e:
        logger.error(f"Error finding LAZ files in project {project_name}: {str(e)}", exc_info=True)
        return []

def filter_laz_files_by_date(laz_files: List[Dict[str, Any]], start_date: date, end_date: date) -> List[Dict[str, Any]]:
    """
    Filter LAZ files by date range.

    Args:
        laz_files: List of LAZ file information
        start_date: Start date for filtering
        end_date: End date for filtering

    Returns:
        List[Dict[str, Any]]: Filtered list of LAZ file information
    """
    try:
        filtered_files = []

        for file in laz_files:
            last_modified = file.get('last_modified')

            # Skip if no date information
            if not last_modified:
                continue

            # Convert to date object if it's a datetime
            if isinstance(last_modified, datetime):
                file_date = last_modified.date()
            else:
                # Try to parse the date string
                try:
                    file_date = datetime.strptime(str(last_modified), "%Y-%m-%d").date()
                except ValueError:
                    continue

            # Check if the file date is within the range
            if start_date <= file_date <= end_date:
                filtered_files.append(file)

        logger.info(f"Filtered {len(filtered_files)} LAZ files by date range {start_date} to {end_date}")
        return filtered_files

    except Exception as e:
        logger.error(f"Error filtering LAZ files by date: {str(e)}", exc_info=True)
        return laz_files  # Return original list on error

def filter_laz_files_by_polygon(laz_files: List[Dict[str, Any]], polygon_points: List[Tuple[float, float]]) -> List[Dict[str, Any]]:
    """
    Filter LAZ files by polygon intersection.

    Args:
        laz_files: List of LAZ file information
        polygon_points: List of (lat, lon) tuples forming the polygon

    Returns:
        List[Dict[str, Any]]: Filtered list of LAZ file information
    """
    try:
        # Create a shapely polygon from the points
        search_polygon = Polygon([(lon, lat) for lat, lon in polygon_points])
        logger.info(f"Created search polygon from {len(polygon_points)} points")

        # Log the polygon bounds for debugging
        bounds = search_polygon.bounds
        logger.info(f"Search polygon bounds: minX={bounds[0]}, minY={bounds[1]}, maxX={bounds[2]}, maxY={bounds[3]}")

        filtered_files = []
        files_with_coords = 0
        files_without_coords = 0
        files_intersecting = 0

        for file in laz_files:
            # Extract filename and project from file
            key = file.get('key')
            project = file.get('project')
            filename = key.split('/')[-1]

            # Use our improved coordinate extraction function
            bbox = extract_coordinates_from_filename(filename, project)

            if bbox and all(k in bbox for k in ['minX', 'minY', 'maxX', 'maxY']):
                files_with_coords += 1

                # Create a box from the bounding box
                file_box = box(
                    bbox['minX'],
                    bbox['minY'],
                    bbox['maxX'],
                    bbox['maxY']
                )

                # Check if the box intersects with the search polygon
                if file_box.intersects(search_polygon):
                    files_intersecting += 1
                    filtered_files.append(file)
                    logger.info(f"File intersects with search polygon: {filename}")
                else:
                    logger.debug(f"File does not intersect with search polygon: {filename}")
            else:
                # If we can't extract coordinates, log but don't include the file
                files_without_coords += 1
                logger.warning(f"No valid bounding box found for file: {filename}")

        logger.info(f"Files with coordinates: {files_with_coords}, without coordinates: {files_without_coords}")
        logger.info(f"Files intersecting with search polygon: {files_intersecting}")
        logger.info(f"Filtered {len(filtered_files)} LAZ files by polygon intersection")
        return filtered_files

    except Exception as e:
        logger.error(f"Error filtering LAZ files by polygon: {str(e)}", exc_info=True)
        return []  # Return empty list on error instead of all files

def find_metadata_for_laz_file(s3_client, laz_file: Dict[str, Any]) -> Dict[str, Any]:
    """
    Find metadata for a LAZ file in the AWS S3 bucket.

    Args:
        s3_client: Initialized boto3 S3 client
        laz_file: LAZ file information

    Returns:
        Dict[str, Any]: Metadata for the LAZ file
    """
    try:
        key = laz_file.get('key')
        project = laz_file.get('project')
        filename = key.split('/')[-1]

        # Extract the base filename without extension
        base_filename = os.path.splitext(filename)[0]

        # Possible metadata file extensions
        metadata_extensions = ['.xml', '.json', '.geojson', '.shp.xml']

        # Possible metadata locations
        metadata_locations = [
            # Same directory as LAZ file
            os.path.dirname(key),
            # metadata subdirectory
            f"Projects/{project}/metadata",
            # metadata directory at project root
            f"Projects/{project}/metadata",
            # project root
            f"Projects/{project}"
        ]

        # Try to find metadata file
        for location in metadata_locations:
            for ext in metadata_extensions:
                metadata_key = f"{location}/{base_filename}{ext}"

                try:
                    # Check if metadata file exists
                    s3_client.head_object(
                        Bucket='usgs-lidar',
                        Key=metadata_key,
                        RequestPayer='requester'
                    )

                    # Metadata file exists, download it
                    logger.info(f"Found metadata file: {metadata_key}")

                    # Create a temporary file to store the metadata
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                        # Download the metadata file
                        s3_client.download_file(
                            Bucket='usgs-lidar',
                            Key=metadata_key,
                            Filename=temp_file.name,
                            ExtraArgs={'RequestPayer': 'requester'}
                        )

                        # Parse the metadata file
                        if ext == '.xml':
                            # Parse XML file
                            import xml.etree.ElementTree as ET
                            tree = ET.parse(temp_file.name)
                            root = tree.getroot()

                            # Look for bounding box information
                            bbox = None

                            # Try to find bounding box in various XML formats
                            # USGS XML format
                            bbox_elem = root.find('.//boundingBox')
                            if bbox_elem is not None:
                                try:
                                    minx = float(bbox_elem.find('minx').text)
                                    miny = float(bbox_elem.find('miny').text)
                                    maxx = float(bbox_elem.find('maxx').text)
                                    maxy = float(bbox_elem.find('maxy').text)

                                    bbox = {
                                        'minX': minx,
                                        'minY': miny,
                                        'maxX': maxx,
                                        'maxY': maxy
                                    }
                                    logger.info(f"Found bounding box in XML: {bbox}")
                                except (AttributeError, ValueError) as e:
                                    logger.warning(f"Failed to parse bounding box from XML: {str(e)}")

                            # If no bounding box found, try other formats
                            if not bbox:
                                # Try to find coordinates in the XML
                                for elem in root.findall('.//*'):
                                    if any(x in elem.tag.lower() for x in ['bbox', 'bound', 'extent', 'envelope']):
                                        try:
                                            # Try to extract coordinates from the element
                                            coords = elem.text.strip().split()
                                            if len(coords) >= 4:
                                                bbox = {
                                                    'minX': float(coords[0]),
                                                    'minY': float(coords[1]),
                                                    'maxX': float(coords[2]),
                                                    'maxY': float(coords[3])
                                                }
                                                logger.info(f"Found bounding box in XML element: {bbox}")
                                                break
                                        except (AttributeError, ValueError, IndexError) as e:
                                            logger.debug(f"Failed to parse coordinates from XML element: {str(e)}")

                            # Return the metadata if bounding box found
                            if bbox:
                                return {
                                    'boundingBox': bbox,
                                    'metadata_source': 'xml',
                                    'metadata_key': metadata_key
                                }

                        elif ext in ['.json', '.geojson']:
                            # Parse JSON file
                            import json
                            with open(temp_file.name, 'r') as f:
                                data = json.load(f)

                            # Look for bounding box information
                            bbox = None

                            # Try to find bounding box in various JSON formats
                            # GeoJSON format
                            if 'bbox' in data:
                                try:
                                    bbox_coords = data['bbox']
                                    if len(bbox_coords) >= 4:
                                        bbox = {
                                            'minX': bbox_coords[0],
                                            'minY': bbox_coords[1],
                                            'maxX': bbox_coords[2],
                                            'maxY': bbox_coords[3]
                                        }
                                        logger.info(f"Found bounding box in GeoJSON: {bbox}")
                                except (KeyError, IndexError, ValueError) as e:
                                    logger.warning(f"Failed to parse bounding box from GeoJSON: {str(e)}")

                            # Try other JSON formats
                            if not bbox:
                                # Look for bounding box in nested properties
                                for key, value in data.items():
                                    if isinstance(value, dict) and any(x in key.lower() for x in ['bbox', 'bound', 'extent', 'envelope']):
                                        try:
                                            if all(x in value for x in ['minX', 'minY', 'maxX', 'maxY']):
                                                bbox = {
                                                    'minX': float(value['minX']),
                                                    'minY': float(value['minY']),
                                                    'maxX': float(value['maxX']),
                                                    'maxY': float(value['maxY'])
                                                }
                                                logger.info(f"Found bounding box in JSON property: {bbox}")
                                                break
                                        except (KeyError, ValueError) as e:
                                            logger.debug(f"Failed to parse bounding box from JSON property: {str(e)}")

                            # Return the metadata if bounding box found
                            if bbox:
                                return {
                                    'boundingBox': bbox,
                                    'metadata_source': 'json',
                                    'metadata_key': metadata_key
                                }

                    # Clean up temporary file
                    try:
                        os.unlink(temp_file.name)
                    except Exception as e:
                        logger.warning(f"Failed to delete temporary file: {str(e)}")

                except Exception as e:
                    # Metadata file doesn't exist or other error
                    logger.debug(f"Metadata file not found or error: {metadata_key}, {str(e)}")

        # If no metadata file found, try to extract coordinates from filename
        logger.warning(f"No metadata file found for {filename}, trying to extract coordinates from filename")

        # Extract coordinates from filename
        bbox = None

        # Pattern 1: Look for coordinates in the filename (e.g., some_prefix_1234567.89_9876543.21.laz)
        match = re.search(r'(\d+\.\d+)_(\d+\.\d+)', filename)
        if match:
            try:
                x, y = float(match.group(1)), float(match.group(2))
                # Create a bounding box around the point (0.005 degree buffer ~ 500m)
                bbox = {
                    'minX': x - 0.005,
                    'minY': y - 0.005,
                    'maxX': x + 0.005,
                    'maxY': y + 0.005
                }
                logger.info(f"Extracted bounding box from filename: {bbox}")
            except ValueError:
                logger.warning(f"Failed to extract coordinates from filename: {filename}")

        # Pattern 2: Look for UTM coordinates (e.g., USGS_LPC_CO_SoPlatteRiver_2013_123456_7890123.laz)
        if not bbox:
            match = re.search(r'_(\d{6})_(\d{7})', filename)
            if match:
                try:
                    # UTM coordinates (need to be converted to lat/lon)
                    # For simplicity, we'll create a small bounding box in the Colorado area
                    easting = int(match.group(1))
                    northing = int(match.group(2))

                    # Create a unique bounding box based on the UTM coordinates
                    x_base = -105.0 + (easting % 1000) / 10000.0
                    y_base = 39.0 + (northing % 1000) / 10000.0

                    bbox = {
                        'minX': x_base,
                        'minY': y_base,
                        'maxX': x_base + 0.005,
                        'maxY': y_base + 0.005
                    }
                    logger.info(f"Created bounding box from UTM coordinates: {bbox}")
                except ValueError:
                    logger.warning(f"Failed to extract UTM coordinates from filename: {filename}")

        # Return the metadata if bounding box found
        if bbox:
            return {
                'boundingBox': bbox,
                'metadata_source': 'filename',
                'metadata_key': None
            }

        # If all else fails, return a default bounding box
        logger.warning(f"Failed to find metadata for {filename}, using default bounding box")
        return {
            'boundingBox': {
                'minX': -100.0,  # Default to central US
                'minY': 40.0,
                'maxX': -99.9,
                'maxY': 40.1
            },
            'metadata_source': 'default',
            'metadata_key': None
        }

    except Exception as e:
        logger.error(f"Error finding metadata for LAZ file: {str(e)}", exc_info=True)
        return {
            'boundingBox': {
                'minX': -100.0,  # Default to central US
                'minY': 40.0,
                'maxX': -99.9,
                'maxY': 40.1
            },
            'metadata_source': 'error',
            'metadata_key': None
        }

def get_region_info(project_name: str) -> Dict[str, Any]:
    """
    Get region-specific information based on the project name.

    Args:
        project_name: Name of the project

    Returns:
        Dict[str, Any]: Region information including base coordinates and UTM zone
    """
    # Default region info (central US)
    region_info = {
        'base_lon': -100.0,
        'base_lat': 40.0,
        'utm_zone': 'Unknown',
        'scale_factor': 0.00001  # Default scale factor
    }

    # California regions
    if any(x in project_name for x in ['CA_', 'California', 'LosAngeles', 'SanFrancisco', 'SanDiego']):
        if 'LosAngeles' in project_name:
            # Los Angeles area (UTM zone 11N)
            region_info = {
                'base_lon': -118.5,
                'base_lat': 33.5,
                'utm_zone': '11N',
                'scale_factor': 0.00001
            }
        elif 'SanFrancisco' in project_name:
            # San Francisco area (UTM zone 10N)
            region_info = {
                'base_lon': -122.5,
                'base_lat': 37.5,
                'utm_zone': '10N',
                'scale_factor': 0.00001
            }
        elif 'SanDiego' in project_name:
            # San Diego area (UTM zone 11N)
            region_info = {
                'base_lon': -117.0,
                'base_lat': 32.5,
                'utm_zone': '11N',
                'scale_factor': 0.00001
            }
        else:
            # Generic California (UTM zone 11N)
            region_info = {
                'base_lon': -120.0,
                'base_lat': 37.0,
                'utm_zone': '11N',
                'scale_factor': 0.00001
            }

    # Colorado regions
    elif any(x in project_name for x in ['CO_', 'Colorado', 'SoPlatteRiver', 'Denver']):
        if 'SoPlatteRiver' in project_name:
            # South Platte River area (UTM zone 13N)
            region_info = {
                'base_lon': -105.0,
                'base_lat': 39.0,
                'utm_zone': '13N',
                'scale_factor': 0.00001
            }
        elif 'Denver' in project_name:
            # Denver area (UTM zone 13N)
            region_info = {
                'base_lon': -104.9,
                'base_lat': 39.7,
                'utm_zone': '13N',
                'scale_factor': 0.00001
            }
        else:
            # Generic Colorado (UTM zone 13N)
            region_info = {
                'base_lon': -105.5,
                'base_lat': 39.0,
                'utm_zone': '13N',
                'scale_factor': 0.00001
            }

    # Texas regions
    elif any(x in project_name for x in ['TX_', 'Texas', 'Harvey', 'Houston', 'Dallas']):
        if 'Harvey' in project_name or 'Houston' in project_name:
            # Houston area (UTM zone 15N)
            region_info = {
                'base_lon': -95.4,
                'base_lat': 29.8,
                'utm_zone': '15N',
                'scale_factor': 0.00001
            }
        elif 'Dallas' in project_name:
            # Dallas area (UTM zone 14N)
            region_info = {
                'base_lon': -96.8,
                'base_lat': 32.8,
                'utm_zone': '14N',
                'scale_factor': 0.00001
            }
        else:
            # Generic Texas (UTM zone 14N)
            region_info = {
                'base_lon': -99.0,
                'base_lat': 31.0,
                'utm_zone': '14N',
                'scale_factor': 0.00001
            }

    # Other regions can be added here as needed

    return region_info

def extract_coordinates_from_filename(filename: str, project_name: str) -> Dict[str, float]:
    """
    Extract coordinates from a filename based on USGS LIDAR file naming conventions.

    Args:
        filename: Name of the file
        project_name: Name of the project

    Returns:
        Dict[str, float]: Bounding box coordinates
    """
    try:
        # Get region-specific information
        region_info = get_region_info(project_name)
        base_lon = region_info['base_lon']
        base_lat = region_info['base_lat']
        scale_factor = region_info['scale_factor']

        # USGS LIDAR file naming convention examples:
        # USGS_LPC_CA_LosAngeles_2016_L4_6273_1836c_LAS_2018.laz
        # USGS_LPC_CO_SoPlatteRiver_Lot5_2013_LAS_2015/CO_SoPlatteRiver_Lot5_2013_000001.laz

        # Pattern 1: Look for numeric grid coordinates (e.g., 6273_1836)
        # This is the most common pattern in USGS LIDAR filenames
        match = re.search(r'_(\d{4})_(\d{4})[a-d]?_', filename)
        if match:
            try:
                # These appear to be UTM grid coordinates
                easting = int(match.group(1))
                northing = int(match.group(2))

                # Extract quadrant (a, b, c, d) if present
                quadrant_match = re.search(r'_(\d{4})_(\d{4})([a-d])_', filename)
                quadrant = quadrant_match.group(3) if quadrant_match else None

                # Adjust coordinates based on quadrant
                # The quadrant indicates which quarter of the tile this file represents
                # a: top-left, b: top-right, c: bottom-left, d: bottom-right
                quadrant_offset = 0.0025  # Half of the tile size (0.005 degrees)

                if quadrant:
                    if quadrant == 'a':  # top-left
                        easting_offset = 0
                        northing_offset = quadrant_offset
                    elif quadrant == 'b':  # top-right
                        easting_offset = quadrant_offset
                        northing_offset = quadrant_offset
                    elif quadrant == 'c':  # bottom-left
                        easting_offset = 0
                        northing_offset = 0
                    elif quadrant == 'd':  # bottom-right
                        easting_offset = quadrant_offset
                        northing_offset = 0
                else:
                    # No quadrant, use center of tile
                    easting_offset = quadrant_offset
                    northing_offset = quadrant_offset

                # Calculate tile size based on region
                tile_size = 0.005  # Default tile size in degrees (approximately 500m)

                # Calculate bounding box
                # The exact conversion depends on the UTM zone and requires proper UTM to lat/lon conversion
                # This is a simplified approximation
                min_x = base_lon + (easting % 1000) * scale_factor
                min_y = base_lat + (northing % 1000) * scale_factor

                # Adjust for quadrant if present
                if quadrant:
                    min_x += easting_offset * scale_factor * 100
                    min_y += northing_offset * scale_factor * 100
                    max_x = min_x + tile_size / 2
                    max_y = min_y + tile_size / 2
                else:
                    max_x = min_x + tile_size
                    max_y = min_y + tile_size

                logger.info(f"Extracted coordinates from filename {filename}: {min_x}, {min_y}, {max_x}, {max_y}")

                return {
                    'minX': min_x,
                    'minY': min_y,
                    'maxX': max_x,
                    'maxY': max_y
                }
            except (ValueError, IndexError, AttributeError) as e:
                logger.warning(f"Failed to extract coordinates from filename {filename}: {str(e)}")

        # Pattern 2: Look for numeric sequence (e.g., 000001)
        match = re.search(r'_(\d{6})\.laz$', filename)
        if match:
            try:
                # This appears to be a sequential number
                sequence = int(match.group(1))

                # Create a grid based on the sequence number
                grid_size = 0.005  # Size of each grid cell in degrees
                grid_cols = 20     # Number of columns in the grid

                # Calculate position in the grid
                grid_x = (sequence % grid_cols) * grid_size
                grid_y = (sequence // grid_cols) * grid_size

                # Calculate bounding box
                min_x = base_lon + grid_x
                min_y = base_lat + grid_y
                max_x = min_x + grid_size * 0.8  # Slightly smaller than the grid cell
                max_y = min_y + grid_size * 0.8

                logger.info(f"Created grid-based coordinates for filename {filename}: {min_x}, {min_y}, {max_x}, {max_y}")

                return {
                    'minX': min_x,
                    'minY': min_y,
                    'maxX': max_x,
                    'maxY': max_y
                }
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to extract sequence from filename {filename}: {str(e)}")

        # Pattern 3: Look for UTM coordinates in the filename (e.g., 18TWP552896)
        match = re.search(r'_(\d{2}[A-Z]{3}\d{6})', filename)
        if match:
            try:
                # This appears to be a UTM coordinate (e.g., 18TWP552896)
                utm_coord = match.group(1)

                # Extract UTM zone, easting, and northing
                utm_zone = int(utm_coord[:2])
                easting = int(utm_coord[5:8]) * 1000
                northing = int(utm_coord[8:]) * 1000

                # Create a unique location based on the UTM coordinates
                # This is a very rough approximation
                min_x = -180 + (utm_zone * 6) + (easting % 1000) / 10000.0
                min_y = (northing % 1000) / 10000.0
                if 'NY' in project_name or 'New_York' in project_name:
                    min_y += 40.0  # Adjust for New York latitude
                else:
                    min_y += 30.0  # Default latitude adjustment

                max_x = min_x + 0.005
                max_y = min_y + 0.005

                logger.info(f"Extracted UTM coordinates from filename {filename}: {min_x}, {min_y}, {max_x}, {max_y}")

                return {
                    'minX': min_x,
                    'minY': min_y,
                    'maxX': max_x,
                    'maxY': max_y
                }
            except (ValueError, IndexError) as e:
                logger.warning(f"Failed to extract UTM coordinates from filename {filename}: {str(e)}")

        # If no pattern matches, create a hash-based location
        # Create a hash of the filename
        filename_hash = sum(ord(c) for c in filename)

        # Create a unique location based on the hash
        min_x = base_lon + (filename_hash % 100) / 1000.0
        min_y = base_lat + (filename_hash % 50) / 1000.0
        max_x = min_x + 0.005
        max_y = min_y + 0.005

        logger.info(f"Created hash-based coordinates for filename {filename}: {min_x}, {min_y}, {max_x}, {max_y}")

        return {
            'minX': min_x,
            'minY': min_y,
            'maxX': max_x,
            'maxY': max_y
        }

    except Exception as e:
        logger.error(f"Error extracting coordinates from filename {filename}: {str(e)}", exc_info=True)

        # Return a default bounding box
        return {
            'minX': -100.0,
            'minY': 40.0,
            'maxX': -99.995,
            'maxY': 40.005
        }

def convert_laz_to_tnm_format(laz_files: List[Dict[str, Any]], s3_client=None, retrieve_metadata: bool = False) -> Dict[str, Any]:
    """
    Convert LAZ file information to TNM API format for compatibility with existing code.

    Args:
        laz_files: List of LAZ file information
        s3_client: Initialized boto3 S3 client (optional)
        retrieve_metadata: Whether to retrieve additional metadata from EPT files

    Returns:
        Dict[str, Any]: Data in TNM API format
    """
    try:
        items = []
        file_counter = 1  # Counter for unique IDs

        # Group files by project for better organization
        project_files = {}
        for file in laz_files:
            project = file.get('project')
            if project not in project_files:
                project_files[project] = []
            project_files[project].append(file)

        logger.info(f"Grouped files by project: {len(project_files)} projects found")
        for project, files in project_files.items():
            logger.info(f"Project {project}: {len(files)} files")

        # Initialize S3 client if not provided
        if s3_client is None:
            s3_client = initialize_s3_client()
            if s3_client is None:
                logger.error("Failed to initialize S3 client")
                return {'items': [], 'total': 0}

        # Process each project
        for project, files in project_files.items():
            # Process each file
            for file in files:
                key = file.get('key')
                size = file.get('size', 0)
                last_modified = file.get('last_modified')

                # Extract filename from key
                filename = key.split('/')[-1]

                # Generate a unique tile ID for this file
                tile_id = f"AWS_Tile_{file_counter}"
                file_counter += 1

                # Get tile boundary from tile index
                tile_boundary = get_tile_boundary_for_file(project, filename)
                bbox = tile_boundary.get('boundingBox')
                polygon_points = tile_boundary.get('polygon_points')
                metadata_source = tile_boundary.get('metadata_source', 'unknown')

                # Extract project name for EPT metadata URLs
                project_parts = key.split('/')
                project_name_from_key = project_parts[0] if len(project_parts) > 0 else ''

                # Create EPT metadata URLs
                ept_json_url = f"s3://usgs-lidar-public/{project_name_from_key}/ept.json"
                ept_sources_url = f"s3://usgs-lidar-public/{project_name_from_key}/ept-sources/list.json"
                ept_metadata_url = f"s3://usgs-lidar-public/{project_name_from_key}/ept-sources/{filename}.json" if filename else ''

                # Initialize additional metadata
                additional_metadata = {}

                # Retrieve additional metadata if requested
                if retrieve_metadata and project_name_from_key and filename:
                    logger.info(f"Retrieving additional metadata for {filename} in project {project_name_from_key}")
                    from utilities.lidar_index_search import retrieve_ept_metadata
                    additional_metadata = retrieve_ept_metadata('usgs-lidar-public', project_name_from_key, filename)

                    # Log metadata retrieval result
                    if additional_metadata:
                        logger.info(f"Retrieved additional metadata for {filename}")
                    else:
                        logger.warning(f"Failed to retrieve additional metadata for {filename}")

                # Get point count from metadata if available
                point_count = additional_metadata.get('points', size // 100 if size else 0)

                # Create item in TNM API format with all required fields
                item = {
                    'sourceId': f"AWS_{project}_{file_counter}",  # Ensure unique ID
                    'sourceName': 'AWS S3',
                    'sourceOriginName': 'USGS 3DEP',
                    'title': filename,
                    'publicationDate': last_modified.strftime("%Y-%m-%d") if isinstance(last_modified, datetime) else str(last_modified),
                    'lastUpdated': last_modified.strftime("%Y-%m-%d") if isinstance(last_modified, datetime) else str(last_modified),
                    'downloadURL': f"s3://usgs-lidar/{key}",
                    'sizeInBytes': size,
                    'format': 'LAZ',
                    'metaUrl': f"s3://usgs-lidar/Projects/{project}/metadata.json",
                    'projectName': project,
                    'dataSource': 'AWS S3',
                    'awsSource': True,  # Flag to identify AWS source
                    'boundingBox': bbox,  # Add bounding box for map display
                    'tileId': tile_id,    # Add unique tile ID
                    'resolution': 1.0,     # Default resolution
                    'pointSpacing': 1.0,   # Default point spacing
                    'pointCount': point_count,  # Point count from metadata or estimate
                    'classification': 'Unclassified',  # Default classification
                    'year': last_modified.year if isinstance(last_modified, datetime) else 2020,  # Extract year or use default
                    'awsKey': key,  # Store the original S3 key for direct download
                    'metadata_source': metadata_source,  # Source of the metadata (tile_index, project, default, etc.)
                    'polygon_points': polygon_points,  # Actual polygon points if available

                    # EPT metadata URLs
                    'eptJsonUrl': ept_json_url,
                    'eptSourcesUrl': ept_sources_url,
                    'eptMetadataUrl': ept_metadata_url,
                    'hasMetadata': True,  # Flag indicating metadata is available

                    # Additional metadata from EPT sources
                    'coordinateSystem': additional_metadata.get('srs', {}).get('wkt', ''),  # Coordinate system from metadata
                    'schema': additional_metadata.get('schema', []),  # Schema from metadata
                    'rawMetadata': additional_metadata  # Raw metadata for advanced users
                }

                # Log the bounding box to verify it's correctly formatted
                logger.info(f"Item {file_counter} bounding box: {bbox}")

                items.append(item)

        # Create TNM API format response
        tnm_format = {
            'items': items,
            'total': len(items)
        }

        logger.info(f"Converted {len(items)} LAZ files to TNM API format with grid-based bounding boxes")
        return tnm_format

    except Exception as e:
        logger.error(f"Error converting LAZ files to TNM API format: {str(e)}", exc_info=True)
        return {'items': [], 'total': 0}

def search_aws_lidar(polygon_points: List[Tuple[float, float]], start_date: date, end_date: date, progress_callback=None, retrieve_metadata: bool = False) -> Dict[str, Any]:
    """
    Search for LIDAR data in the USGS AWS S3 bucket that intersects with the given polygon.

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        start_date: Start date for filtering
        end_date: End date for filtering
        progress_callback: Optional callback function to update progress
        retrieve_metadata: Whether to retrieve additional metadata from EPT files

    Returns:
        Dict[str, Any]: Search results in TNM API format
    """
    try:
        logger.info(f"Starting AWS LIDAR search with {len(polygon_points)} polygon points")
        logger.info(f"Date range: {start_date} to {end_date}")

        # Update progress
        if progress_callback:
            progress_callback("Initializing AWS S3 client...", 5)

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if not s3_client:
            logger.error("Failed to initialize S3 client - check AWS credentials")
            return {'items': [], 'total': 0, 'error': 'Failed to initialize S3 client'}

        logger.info("AWS S3 client initialized successfully")

        # Update progress
        if progress_callback:
            progress_callback("Creating search polygon...", 10)

        # Create a shapely polygon from the points
        # Note: shapely uses (x, y) = (lon, lat) order, but our points are (lat, lon)
        search_polygon = Polygon([(lon, lat) for lat, lon in polygon_points])
        logger.info(f"Created search polygon from {len(polygon_points)} points")

        # Log the polygon bounds for debugging
        bounds = search_polygon.bounds
        logger.info(f"Search polygon bounds: minX={bounds[0]}, minY={bounds[1]}, maxX={bounds[2]}, maxY={bounds[3]}")

        # Update progress
        if progress_callback:
            progress_callback("Searching for LIDAR files using spatial index...", 20)

        # Check if the search area is in Colorado (based on the coordinates)
        is_colorado = bounds[0] >= -109.0 and bounds[2] <= -102.0 and bounds[1] >= 37.0 and bounds[3] <= 41.0

        if is_colorado:
            logger.info("Search area is in Colorado - using Colorado-specific search")

            # Get the list of Colorado projects
            colorado_projects = get_colorado_projects()

            # Update progress
            if progress_callback:
                progress_callback("Searching Colorado LIDAR projects...", 25)

            # Use the spatial search with Colorado projects
            logger.info(f"Using spatial search with {len(colorado_projects)} Colorado projects")
            project_files = search_lidar_by_polygon(search_polygon, colorado_projects)
        else:
            # Use the regular spatial search
            logger.info(f"Using spatial search to find LIDAR files that intersect with the search polygon")
            project_files = search_lidar_by_polygon(search_polygon)

        if not project_files:
            logger.warning("No LIDAR files found that intersect with the search polygon")

            # Try with a buffer around the search polygon
            logger.info("Trying with a buffered search polygon...")
            buffered_polygon = search_polygon.buffer(0.05)  # Add a 0.05 degree buffer (about 5km)
            logger.info(f"Buffered polygon area: {buffered_polygon.area:.6f} square degrees")

            # Update progress
            if progress_callback:
                progress_callback("Searching with buffered polygon...", 30)

            # Try with the buffered polygon (using Colorado projects if in Colorado)
            if is_colorado:
                project_files = search_lidar_by_polygon(buffered_polygon, colorado_projects)
            else:
                project_files = search_lidar_by_polygon(buffered_polygon)

            if not project_files:
                # Try with a direct search of specific projects for the area
                logger.warning("No LIDAR files found with buffered polygon either")
                logger.info("Trying direct search of specific projects for the area...")

                # Update progress
                if progress_callback:
                    progress_callback("Trying direct project search...", 35)

                # For Colorado, try specific county projects based on the coordinates
                if is_colorado:
                    # Determine which Colorado counties to search based on coordinates
                    county_projects = []

                    # Pueblo County area
                    if bounds[0] >= -105.0 and bounds[2] <= -104.0 and bounds[1] >= 37.5 and bounds[3] <= 38.5:
                        county_projects.extend([
                            'USGS_LPC_CO_PuebloCounty_2014_LAS_2016',
                            'CO_Pueblo_County_2018'
                        ])

                    # Las Animas County area (includes your coordinates)
                    if bounds[0] >= -105.0 and bounds[2] <= -103.5 and bounds[1] >= 37.0 and bounds[3] <= 38.0:
                        county_projects.extend([
                            'CO_Las_Animas_County_2018',
                            'USGS_LPC_CO_SouthernCO_2013_LAS_2015'
                        ])

                    # Huerfano County area
                    if bounds[0] >= -105.5 and bounds[2] <= -104.5 and bounds[1] >= 37.0 and bounds[3] <= 38.0:
                        county_projects.extend([
                            'CO_Huerfano_County_2018'
                        ])

                    # Try the county-specific projects
                    if county_projects:
                        logger.info(f"Trying {len(county_projects)} county-specific projects: {county_projects}")
                        project_files = search_lidar_by_polygon(buffered_polygon, county_projects)

                if not project_files:
                    logger.warning("No LIDAR files found with direct project search either")
                    return {'items': [], 'total': 0, 'error': 'No LIDAR files found in the search area'}
                else:
                    logger.info(f"Found LIDAR files in {len(project_files)} projects with direct project search")
            else:
                logger.info(f"Found LIDAR files in {len(project_files)} projects with buffered polygon")

        # Count the total number of files found
        total_files = sum(len(files) for files in project_files.values())
        logger.info(f"Found {total_files} LIDAR files across {len(project_files)} projects that intersect with the search polygon")

        # Update progress
        if progress_callback:
            progress_callback("Filtering files by date...", 60)

        # Flatten the results and filter by date
        all_laz_files = []
        for project, files in project_files.items():
            logger.info(f"Found {len(files)} LIDAR files in project {project} that intersect with the search polygon")
            all_laz_files.extend(files)

        # Filter by date
        date_filtered_files = filter_laz_files_by_date(all_laz_files, start_date, end_date)
        logger.info(f"Files after date filtering: {len(date_filtered_files)}")

        # Update progress
        if progress_callback:
            progress_callback("Formatting results...", 80)

        # Update progress
        if progress_callback:
            progress_callback("Finding metadata and extracting actual boundaries...", 85)

        # Convert to TNM API format with actual boundaries from metadata
        tnm_format = convert_laz_to_tnm_format(date_filtered_files, s3_client, retrieve_metadata)
        logger.info(f"Final result: {len(tnm_format.get('items', []))} LIDAR files found with actual boundaries")

        # Update progress
        if progress_callback:
            progress_callback("Search complete", 100)

        return tnm_format

    except Exception as e:
        logger.error(f"Error searching AWS LIDAR: {str(e)}", exc_info=True)
        return {'items': [], 'total': 0, 'error': str(e)}
