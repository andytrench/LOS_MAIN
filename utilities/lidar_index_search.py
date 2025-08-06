"""
LIDAR Index Search Module

This module provides functions to search the LIDAR index database and integrate
with the existing search functionality.
"""

import logging
import json
import boto3
import os
from typing import List, Dict, Any, Tuple
from shapely.geometry import Polygon
from datetime import date
from functools import lru_cache

# Import the database module
from utilities.lidar_index_db import (
    search_files_by_bbox, database_exists, DEFAULT_DB_PATH
)

# Configure logging
logger = logging.getLogger(__name__)

def search_lidar_index(polygon_points: List[Tuple[float, float]],
                      start_date: date = None, end_date: date = None,
                      format: str = None, db_path: str = DEFAULT_DB_PATH,
                      retrieve_metadata: bool = False,
                      coordinate_order: str = None) -> Dict[str, Any]:
    """
    Search the LIDAR index database for files that intersect with a polygon.

    Args:
        polygon_points: List of (lon, lat) or (lat, lon) tuples forming the polygon
        start_date: Start date for filtering
        end_date: End date for filtering
        format: File format filter
        db_path: Path to the database file
        retrieve_metadata: Whether to retrieve additional metadata from EPT files
        coordinate_order: Force a specific coordinate order ('lonlat' or 'latlon')

    Returns:
        List[Dict[str, Any]]: List of matching files
    """
    try:
        # Check if database exists
        if not database_exists(db_path):
            logger.warning(f"LIDAR index database does not exist at {db_path}")
            return {}

        # Log the polygon points for debugging
        logger.info(f"Polygon points: {polygon_points}")

        # Determine coordinate order and convert points for shapely
        if coordinate_order == 'lonlat':
            # Use (lon, lat) order as specified
            logger.info("Using (lon, lat) coordinate order as specified")
            converted_points = [(lon, lat) for lon, lat in polygon_points]
        elif coordinate_order == 'latlon':
            # Use (lat, lon) order as specified - convert to (lon, lat) for shapely
            logger.info("Using (lat, lon) coordinate order as specified")
            logger.info("Converting (lat, lon) to (lon, lat) for shapely...")
            converted_points = [(lon, lat) for lat, lon in polygon_points]
        else:
            # Auto-detect coordinate order by checking the range of values
            first_coords = [p[0] for p in polygon_points]
            if min(first_coords) >= -180 and max(first_coords) <= 180:
                # Assume (lon, lat) order
                logger.info("Auto-detected (lon, lat) coordinate order")
                converted_points = [(lon, lat) for lon, lat in polygon_points]
            else:
                # Assume (lat, lon) order
                logger.info("Auto-detected (lat, lon) coordinate order")
                logger.info("Converting (lat, lon) to (lon, lat) for shapely...")
                converted_points = [(lon, lat) for lat, lon in polygon_points]

        # Log the converted points
        logger.info(f"Converted points for shapely: {converted_points}")
        logger.info(f"Original polygon points: {polygon_points}")

        # Create the shapely polygon
        polygon = Polygon(converted_points)
        logger.info(f"Shapely polygon created: {polygon}")
        logger.info(f"Polygon area: {polygon.area:.6f} square degrees")

        # Get the bounding box of the polygon
        bounds = polygon.bounds
        min_x, min_y, max_x, max_y = bounds

        logger.info(f"Searching LIDAR index for files in bounding box: {min_x}, {min_y}, {max_x}, {max_y}")

        # Search for files
        files = search_files_by_bbox(min_x, min_y, max_x, max_y, format, db_path)

        # Filter by date if specified
        if start_date or end_date:
            filtered_files = []

            for file in files:
                # Extract year from project name or last_modified
                year = file.get('project_year')

                if not year:
                    # Try to extract year from last_modified
                    last_modified = file.get('last_modified')
                    if last_modified and hasattr(last_modified, 'year'):
                        year = last_modified.year

                # Skip if no year found
                if not year:
                    continue

                # Check if year is within date range
                if start_date and year < start_date.year:
                    continue

                if end_date and year > end_date.year:
                    continue

                filtered_files.append(file)

            logger.info(f"Filtered {len(files)} files by date range: {len(filtered_files)} remaining")
            files = filtered_files

        # Now filter the results to only include files that actually intersect with the polygon
        if files:
            logger.info(f"Found {len(files)} files in bounding box, filtering by actual polygon...")
            filtered_files = []
            intersection_count = 0

            for idx, file in enumerate(files):
                # Log file details for debugging
                logger.info(f"File {idx+1}/{len(files)}: {file.get('key')}")
                logger.info(f"  File bounds: {file.get('min_x')}, {file.get('min_y')} to {file.get('max_x')}, {file.get('max_y')}")

                # Create a polygon for the file using its bounding box
                file_bbox = [
                    (file['min_x'], file['min_y']),
                    (file['min_x'], file['max_y']),
                    (file['max_x'], file['max_y']),
                    (file['max_x'], file['min_y'])
                ]
                logger.info(f"  File bbox points: {file_bbox}")

                try:
                    file_polygon = Polygon(file_bbox)
                    logger.info(f"  File polygon created: {file_polygon}")

                    # Check if the file polygon intersects with the search polygon
                    does_intersect = polygon.intersects(file_polygon)
                    logger.info(f"  Intersection check result: {does_intersect}")

                    if does_intersect:
                        logger.info(f"  File {file['key']} INTERSECTS with the polygon")
                        filtered_files.append(file)
                        intersection_count += 1
                    else:
                        logger.info(f"  File {file['key']} DOES NOT intersect with the polygon")
                except Exception as e:
                    logger.error(f"  Error creating or checking file polygon: {str(e)}")

            logger.info(f"Filtered to {len(filtered_files)} files that intersect with the actual polygon")
            logger.info(f"Intersection count: {intersection_count}")
            files = filtered_files

        # Convert to TNM API format
        tnm_format = convert_to_tnm_format(files, retrieve_metadata)

        logger.info(f"Found {len(tnm_format.get('items', []))} LIDAR files in index")

        return tnm_format

    except Exception as e:
        logger.error(f"Error searching LIDAR index: {str(e)}", exc_info=True)
        return {'items': [], 'total': 0, 'error': str(e)}

# Create a cache directory for metadata
METADATA_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data', 'metadata_cache')
os.makedirs(METADATA_CACHE_DIR, exist_ok=True)

@lru_cache(maxsize=128)
def retrieve_ept_metadata(bucket: str, project_name: str, filename: str) -> Dict[str, Any]:
    """
    Retrieve metadata from EPT files.

    Args:
        bucket: S3 bucket name
        project_name: Project name
        filename: Filename

    Returns:
        Dict[str, Any]: Metadata from EPT files
    """
    # Extract the actual project name from the filename
    # Example: USGS_LPC_CO_EasternColorado_2018_A18_LD31961336.laz
    # Project name should be CO_Eastern_B5_2018 or similar
    if 'CO_Eastern' in filename:
        if 'B1' in filename:
            actual_project_name = 'CO_Eastern_B1_2018'
        elif 'B2_QL1_Central' in filename:
            actual_project_name = 'CO_Eastern_B2_QL1_Central_2018'
        elif 'B2_QL2_Central' in filename:
            actual_project_name = 'CO_Eastern_B2_QL2_Central_2018'
        elif 'B2_QL2_North' in filename:
            actual_project_name = 'CO_Eastern_B2_QL2_North_2018'
        elif 'B3' in filename:
            actual_project_name = 'CO_Eastern_B3_2018'
        elif 'B4' in filename:
            actual_project_name = 'CO_Eastern_B4_2018'
        elif 'B5' in filename:
            actual_project_name = 'CO_Eastern_B5_2018'
        elif 'B6' in filename:
            actual_project_name = 'CO_Eastern_B6_2018'
        elif 'ElPaso' in filename:
            actual_project_name = 'CO_Eastern_ElPaso_2018'
        elif 'North_Priority' in filename:
            actual_project_name = 'CO_Eastern_North_Priority_2018'
        elif 'South_Priority2' in filename:
            actual_project_name = 'CO_Eastern_South_Priority2_2018'
        else:
            actual_project_name = 'CO_Eastern_B1_2018'  # Default to B1
    else:
        # Use the provided project name
        actual_project_name = project_name
    try:
        # Check if we have cached metadata
        cache_key = f"{bucket}_{project_name}_{filename}"
        cache_file = os.path.join(METADATA_CACHE_DIR, f"{cache_key.replace('/', '_')}.json")

        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    metadata = json.load(f)
                logger.info(f"Retrieved metadata from cache for {filename}")
                return metadata
            except Exception as e:
                logger.warning(f"Error reading cached metadata for {filename}: {str(e)}")

        # Initialize S3 client
        s3_client = boto3.client('s3')

        # Initialize metadata dictionary
        metadata = {}

        # Try to get ept.json
        try:
            ept_json_key = f"{actual_project_name}/ept.json"
            logger.info(f"Trying to get ept.json from {ept_json_key}")
            response = s3_client.get_object(
                Bucket=bucket,
                Key=ept_json_key,
                RequestPayer='requester'
            )
            ept_data = json.loads(response['Body'].read().decode('utf-8'))

            # Extract metadata from ept.json
            if ept_data.get('bounds'):
                metadata['bounds'] = ept_data['bounds']
            if ept_data.get('points'):
                metadata['points'] = ept_data['points']
            if ept_data.get('schema'):
                metadata['schema'] = ept_data['schema']
            if ept_data.get('srs'):
                metadata['srs'] = ept_data['srs']
        except Exception as e:
            logger.warning(f"Error getting ept.json for project {actual_project_name}: {str(e)}")

        # Try to get individual metadata file
        try:
            metadata_key = f"{actual_project_name}/ept-sources/{filename}.json"
            logger.info(f"Trying to get metadata from {metadata_key}")
            response = s3_client.get_object(
                Bucket=bucket,
                Key=metadata_key,
                RequestPayer='requester'
            )
            file_metadata = json.loads(response['Body'].read().decode('utf-8'))

            # Extract metadata from file metadata
            metadata['file_metadata'] = file_metadata
        except Exception as e:
            logger.warning(f"Error getting metadata for file {filename}: {str(e)}")

        # If we couldn't get the individual file metadata, try to get the list.json file
        if 'file_metadata' not in metadata:
            try:
                list_key = f"{actual_project_name}/ept-sources/list.json"
                logger.info(f"Trying to get list.json from {list_key}")
                response = s3_client.get_object(
                    Bucket=bucket,
                    Key=list_key,
                    RequestPayer='requester'
                )
                list_data = json.loads(response['Body'].read().decode('utf-8'))

                # Find the file in the list
                for item in list_data:
                    if filename in item.get('path', ''):
                        metadata['file_metadata'] = item
                        break
            except Exception as e:
                logger.warning(f"Error getting list.json for project {actual_project_name}: {str(e)}")

        # If we still couldn't get the file metadata, try to get the manifest.json file
        if 'file_metadata' not in metadata:
            try:
                manifest_key = f"{actual_project_name}/ept-sources/manifest.json"
                logger.info(f"Trying to get manifest.json from {manifest_key}")
                response = s3_client.get_object(
                    Bucket=bucket,
                    Key=manifest_key,
                    RequestPayer='requester'
                )
                manifest_data = json.loads(response['Body'].read().decode('utf-8'))

                # Find the file in the manifest
                for item in manifest_data:
                    if filename in item.get('path', ''):
                        metadata['file_metadata'] = item
                        break
            except Exception as e:
                logger.warning(f"Error getting manifest.json for project {actual_project_name}: {str(e)}")

        # Save metadata to cache
        try:
            with open(cache_file, 'w') as f:
                json.dump(metadata, f)
            logger.info(f"Saved metadata to cache for {filename}")
        except Exception as e:
            logger.warning(f"Error saving metadata to cache for {filename}: {str(e)}")

        return metadata
    except Exception as e:
        logger.error(f"Error retrieving EPT metadata: {str(e)}", exc_info=True)
        return {}

def convert_to_tnm_format(files: List[Dict[str, Any]], retrieve_metadata: bool = False) -> Dict[str, Any]:
    """
    Convert files from the database format to TNM API format.

    Args:
        files: List of files from the database
        retrieve_metadata: Whether to retrieve additional metadata from EPT files

    Returns:
        Dict[str, Any]: Files in TNM API format
    """
    try:
        items = []

        # Process each file

        for file in files:
            # Extract file data
            key = file.get('key')
            bucket = file.get('bucket')
            filename = file.get('filename')
            size = file.get('size')
            last_modified = file.get('last_modified')
            project_name = file.get('project_name')

            # Extract bounding box
            bbox = file.get('boundingBox')

            # Extract polygon points
            polygon_points = file.get('polygon_points')

            # Extract project name from key for EPT metadata URLs
            project_parts = key.split('/')
            project_name_from_key = project_parts[0] if len(project_parts) > 0 else ''

            # Get EPT metadata URLs from database or create them
            ept_json_url = file.get('ept_json_url') or f"https://s3-us-west-2.amazonaws.com/{bucket}/{project_name_from_key}/ept.json"
            ept_sources_url = file.get('ept_sources_url') or f"https://s3-us-west-2.amazonaws.com/{bucket}/{project_name_from_key}/ept-sources/list.json"
            ept_metadata_url = file.get('ept_metadata_url') or (f"https://s3-us-west-2.amazonaws.com/{bucket}/{project_name_from_key}/ept-sources/{filename}.json" if filename else '')

            # Initialize additional metadata
            additional_metadata = {}

            # Store metadata URLs without fetching the actual metadata
            # This avoids errors when metadata files don't exist
            if retrieve_metadata and project_name_from_key and filename:
                logger.info(f"Storing metadata URLs for {filename} in project {project_name_from_key}")
                # Instead of fetching metadata, just store the URLs
                additional_metadata = {
                    'ept_json_url': ept_json_url,
                    'ept_sources_url': ept_sources_url,
                    'ept_metadata_url': ept_metadata_url
                }
                logger.info(f"Stored metadata URLs for {filename}")

            # Get point cloud information from database or metadata
            point_count = file.get('point_count') or additional_metadata.get('points', size // 100 if size else 0)
            resolution = file.get('resolution') or 1.0
            point_spacing = file.get('point_spacing') or 1.0
            coordinate_system = file.get('coordinate_system') or additional_metadata.get('srs', {}).get('wkt', '')

            # Create item in TNM API format
            item = {
                'sourceId': f"INDEX_{file.get('id')}",
                'sourceName': 'LIDAR Index',
                'sourceOriginName': 'USGS 3DEP',
                'title': filename,
                'publicationDate': str(last_modified) if last_modified else '',
                'lastUpdated': str(last_modified) if last_modified else '',
                'downloadURL': f"https://s3-us-west-2.amazonaws.com/{bucket}/{key}",
                'ept_json_url': ept_json_url,
                'ept_sources_url': ept_sources_url,
                'ept_metadata_url': ept_metadata_url,
                'url': f"https://s3-us-west-2.amazonaws.com/{bucket}/{key}",  # Add URL for compatibility
                'sizeInBytes': size,
                'format': file.get('format', '').upper(),
                'metaUrl': f"s3://{bucket}/metadata.json",
                'projectName': project_name,
                'dataSource': 'LIDAR Index',
                'awsSource': True,  # Flag to identify AWS source
                'boundingBox': bbox,  # Add bounding box for map display
                'tileId': f"INDEX_TILE_{file.get('id')}",  # Add unique tile ID
                'resolution': resolution,  # Resolution from database or default
                'pointSpacing': point_spacing,  # Point spacing from database or default
                'pointCount': point_count,  # Point count from database or metadata or estimate
                'classification': file.get('classification', 'Unclassified'),  # Classification from metadata or default
                'year': file.get('project_year', 2020),  # Extract year or use default
                'awsKey': key,  # Store the original S3 key for direct download
                'metadata_source': file.get('metadata_source', 'index'),  # Source of the metadata
                'polygon_points': polygon_points,  # Actual polygon points if available

                # EPT metadata URLs
                'eptJsonUrl': ept_json_url,
                'eptSourcesUrl': ept_sources_url,
                'eptMetadataUrl': ept_metadata_url,
                'rawMetadata': True,  # Flag indicating raw metadata is available

                # Additional metadata from EPT sources
                'coordinateSystem': coordinate_system,  # Coordinate system from database or metadata
                'acquisitionDate': file.get('acquisition_date', ''),  # Acquisition date from metadata
                'hasMetadata': True,  # Flag indicating metadata is available
                'schema': additional_metadata.get('schema', []),  # Schema from metadata
                'rawMetadata': additional_metadata  # Raw metadata for advanced users
            }

            items.append(item)

        return {
            'items': items,
            'total': len(items),
            'source': 'LIDAR Index'
        }

    except Exception as e:
        logger.error(f"Error converting to TNM format: {str(e)}", exc_info=True)
        return {'items': [], 'total': 0, 'error': str(e)}

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Test search
    polygon_points = [
        (37.7, -105.0),
        (37.7, -104.5),
        (38.0, -104.5),
        (38.0, -105.0),
        (37.7, -105.0)
    ]

    results = search_lidar_index(polygon_points)

    print(f"Found {len(results.get('items', []))} LIDAR files")

    for item in results.get('items', [])[:5]:
        print(f"- {item['title']} ({item['projectName']})")
