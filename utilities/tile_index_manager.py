"""
Utility for downloading and managing USGS LIDAR tile index data.
This module provides functions to download tile index data from the USGS AWS S3 bucket
and use it to get precise tile boundaries for LIDAR files.
"""

import os
import logging
import tempfile
import json
import boto3
import geopandas as gpd
import pandas as pd
from shapely.geometry import box, Polygon, mapping, Point
from shapely.ops import unary_union
from typing import Dict, List, Any, Tuple, Optional
import re
import concurrent.futures
import time

# Configure logging
logger = logging.getLogger(__name__)

# Cache for tile index data to avoid repeated downloads
TILE_INDEX_CACHE = {}

# Cache for spatial indexes
SPATIAL_INDEX_CACHE = {}

# Cache for project metadata
PROJECT_METADATA_CACHE = {}

def initialize_s3_client():
    """Initialize the S3 client with credentials from environment variables."""
    try:
        # Get credentials from environment variables
        aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-west-2')

        logger.info(f"Using AWS credentials: ID={aws_access_key_id[:4] if aws_access_key_id else 'None'}... Region={aws_region}")

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

        logger.info("S3 client initialized successfully")
        return s3_client

    except Exception as e:
        logger.error(f"Error initializing S3 client: {str(e)}", exc_info=True)
        return None

def find_tile_index_files(s3_client, project_name: str) -> List[Dict[str, Any]]:
    """
    Find tile index files (shapefiles, GeoJSON) for a project in the AWS S3 bucket.

    Args:
        s3_client: Initialized boto3 S3 client
        project_name: Name of the project

    Returns:
        List[Dict[str, Any]]: List of tile index file information
    """
    try:
        logger.info(f"Finding tile index files for project: {project_name}")

        # Possible locations for tile index files
        prefixes = [
            f"Projects/{project_name}/tile_index/",
            f"Projects/{project_name}/tileindex/",
            f"Projects/{project_name}/index/",
            f"Projects/{project_name}/metadata/",
            f"Projects/{project_name}/"
        ]

        # File extensions to look for
        extensions = ['.shp', '.geojson', '.json', '.gpkg']

        tile_index_files = []

        for prefix in prefixes:
            logger.info(f"Searching for tile index files in: {prefix}")

            try:
                # List objects with the prefix
                response = s3_client.list_objects_v2(
                    Bucket='usgs-lidar-public',
                    Prefix=prefix,
                    RequestPayer='requester',
                    MaxKeys=100
                )

                # Process the files
                for item in response.get('Contents', []):
                    key = item.get('Key')
                    if key:
                        # Check if the file has a tile index extension
                        if any(key.lower().endswith(ext) for ext in extensions):
                            # Check if the file name contains tile index keywords
                            if any(keyword in key.lower() for keyword in ['tile', 'index', 'boundary', 'footprint']):
                                tile_index_files.append({
                                    'key': key,
                                    'size': item.get('Size'),
                                    'last_modified': item.get('LastModified')
                                })
                                logger.info(f"Found tile index file: {key}")

            except Exception as e:
                logger.warning(f"Error listing objects with prefix {prefix}: {str(e)}")

        # If no tile index files found with keywords, include any files with the right extensions
        if not tile_index_files:
            logger.info("No tile index files found with keywords, looking for any files with the right extensions")

            for prefix in prefixes:
                try:
                    # List objects with the prefix
                    response = s3_client.list_objects_v2(
                        Bucket='usgs-lidar-public',
                        Prefix=prefix,
                        RequestPayer='requester',
                        MaxKeys=100
                    )

                    # Process the files
                    for item in response.get('Contents', []):
                        key = item.get('Key')
                        if key and any(key.lower().endswith(ext) for ext in extensions):
                            tile_index_files.append({
                                'key': key,
                                'size': item.get('Size'),
                                'last_modified': item.get('LastModified')
                            })
                            logger.info(f"Found potential tile index file: {key}")

                except Exception as e:
                    logger.warning(f"Error listing objects with prefix {prefix}: {str(e)}")

        logger.info(f"Found {len(tile_index_files)} tile index files for project {project_name}")
        return tile_index_files

    except Exception as e:
        logger.error(f"Error finding tile index files: {str(e)}", exc_info=True)
        return []

def download_and_parse_tile_index(s3_client, tile_index_file: Dict[str, Any]) -> Optional[gpd.GeoDataFrame]:
    """
    Download and parse a tile index file.

    Args:
        s3_client: Initialized boto3 S3 client
        tile_index_file: Tile index file information

    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame containing tile index data
    """
    try:
        key = tile_index_file.get('key')
        logger.info(f"Downloading and parsing tile index file: {key}")

        # Create a temporary file to store the tile index
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(key)[1], delete=False) as temp_file:
            # Download the tile index file
            s3_client.download_file(
                Bucket='usgs-lidar-public',
                Key=key,
                Filename=temp_file.name,
                ExtraArgs={'RequestPayer': 'requester'}
            )

            # Parse the tile index file based on its extension
            ext = os.path.splitext(key)[1].lower()

            if ext == '.shp':
                # Parse shapefile
                gdf = gpd.read_file(temp_file.name)
                logger.info(f"Parsed shapefile with {len(gdf)} features")

                # Check if the shapefile has a valid geometry column
                if 'geometry' not in gdf.columns or gdf.geometry.isna().all():
                    logger.warning(f"Shapefile {key} has no valid geometry column")
                    return None

                # Log the columns for debugging
                logger.info(f"Shapefile columns: {list(gdf.columns)}")

                return gdf

            elif ext in ['.geojson', '.json']:
                # Parse GeoJSON
                try:
                    gdf = gpd.read_file(temp_file.name)
                    logger.info(f"Parsed GeoJSON with {len(gdf)} features")

                    # Check if the GeoJSON has a valid geometry column
                    if 'geometry' not in gdf.columns or gdf.geometry.isna().all():
                        logger.warning(f"GeoJSON {key} has no valid geometry column")
                        return None

                    # Log the columns for debugging
                    logger.info(f"GeoJSON columns: {list(gdf.columns)}")

                    return gdf
                except Exception as e:
                    logger.warning(f"Error parsing GeoJSON {key}: {str(e)}")

                    # Try parsing as regular JSON
                    try:
                        with open(temp_file.name, 'r') as f:
                            data = json.load(f)

                        # Check if the JSON has a features array
                        if 'features' in data:
                            # Convert to GeoDataFrame
                            gdf = gpd.GeoDataFrame.from_features(data['features'])
                            logger.info(f"Parsed JSON with {len(gdf)} features")

                            # Check if the GeoDataFrame has a valid geometry column
                            if 'geometry' not in gdf.columns or gdf.geometry.isna().all():
                                logger.warning(f"JSON {key} has no valid geometry column")
                                return None

                            # Log the columns for debugging
                            logger.info(f"JSON columns: {list(gdf.columns)}")

                            return gdf
                    except Exception as e2:
                        logger.warning(f"Error parsing JSON {key}: {str(e2)}")
                        return None

            elif ext == '.gpkg':
                # Parse GeoPackage
                gdf = gpd.read_file(temp_file.name)
                logger.info(f"Parsed GeoPackage with {len(gdf)} features")

                # Check if the GeoPackage has a valid geometry column
                if 'geometry' not in gdf.columns or gdf.geometry.isna().all():
                    logger.warning(f"GeoPackage {key} has no valid geometry column")
                    return None

                # Log the columns for debugging
                logger.info(f"GeoPackage columns: {list(gdf.columns)}")

                return gdf

            else:
                logger.warning(f"Unsupported file format: {ext}")
                return None

    except Exception as e:
        logger.error(f"Error downloading and parsing tile index file: {str(e)}", exc_info=True)
        return None
    finally:
        # Clean up temporary file
        try:
            os.unlink(temp_file.name)
        except Exception as e:
            logger.warning(f"Failed to delete temporary file: {str(e)}")

def get_tile_index_for_project(project_name: str) -> Optional[gpd.GeoDataFrame]:
    """
    Get the tile index for a project.

    Args:
        project_name: Name of the project

    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame containing tile index data
    """
    try:
        # Check if the tile index is already in the cache
        if project_name in TILE_INDEX_CACHE:
            logger.info(f"Using cached tile index for project {project_name}")
            return TILE_INDEX_CACHE[project_name]

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if not s3_client:
            logger.error("Failed to initialize S3 client")
            return None

        # Find tile index files
        tile_index_files = find_tile_index_files(s3_client, project_name)
        if not tile_index_files:
            logger.warning(f"No tile index files found for project {project_name}")
            return None

        # Try to download and parse each tile index file
        for tile_index_file in tile_index_files:
            gdf = download_and_parse_tile_index(s3_client, tile_index_file)
            if gdf is not None:
                # Cache the tile index
                TILE_INDEX_CACHE[project_name] = gdf
                return gdf

        logger.warning(f"Failed to parse any tile index files for project {project_name}")
        return None

    except Exception as e:
        logger.error(f"Error getting tile index for project {project_name}: {str(e)}", exc_info=True)
        return None

def match_file_to_tile_index(filename: str, tile_index: gpd.GeoDataFrame) -> Optional[Dict[str, Any]]:
    """
    Match a file to a tile in the tile index.

    Args:
        filename: Name of the file
        tile_index: GeoDataFrame containing tile index data

    Returns:
        Optional[Dict[str, Any]]: Tile information including bounding box and polygon points
    """
    try:
        logger.info(f"Matching file {filename} to tile index")

        # Extract the base filename without extension
        base_filename = os.path.splitext(filename)[0]

        # Look for columns that might contain the filename or tile ID
        filename_columns = []
        for col in tile_index.columns:
            if any(keyword in col.lower() for keyword in ['name', 'file', 'tile', 'id']):
                filename_columns.append(col)

        logger.info(f"Potential filename columns: {filename_columns}")

        # Try to find a match in each column
        for col in filename_columns:
            # Convert column to string to ensure we can do string comparisons
            tile_index[col] = tile_index[col].astype(str)

            # Look for exact matches
            matches = tile_index[tile_index[col] == base_filename]
            if not matches.empty:
                logger.info(f"Found exact match in column {col}")
                match = matches.iloc[0]
                return process_tile_match(match)

            # Look for partial matches
            matches = tile_index[tile_index[col].str.contains(base_filename, regex=False)]
            if not matches.empty:
                logger.info(f"Found partial match in column {col}")
                match = matches.iloc[0]
                return process_tile_match(match)

            # Try the other way around - filename contains column value
            for idx, row in tile_index.iterrows():
                if row[col] in base_filename:
                    logger.info(f"Found match where filename contains column value")
                    return process_tile_match(row)

        # If no match found by filename, try to extract coordinates from filename
        # and find the tile that contains those coordinates
        coords = extract_coordinates_from_filename(filename)
        if coords:
            logger.info(f"Extracted coordinates from filename: {coords}")

            # Create a point from the coordinates
            from shapely.geometry import Point
            point = Point(coords['x'], coords['y'])

            # Find tiles that contain the point
            matches = tile_index[tile_index.geometry.contains(point)]
            if not matches.empty:
                logger.info(f"Found tile that contains the point")
                match = matches.iloc[0]
                return process_tile_match(match)

        logger.warning(f"No match found for file {filename}")
        return None

    except Exception as e:
        logger.error(f"Error matching file to tile index: {str(e)}", exc_info=True)
        return None

def process_tile_match(match: pd.Series) -> Dict[str, Any]:
    """
    Process a tile match from the tile index.

    Args:
        match: Series containing tile information

    Returns:
        Dict[str, Any]: Tile information including bounding box and polygon points
    """
    try:
        # Get the geometry
        geometry = match.geometry

        # Convert to GeoJSON
        geojson = mapping(geometry)

        # Extract coordinates
        coords = []

        if geojson['type'] == 'Polygon':
            # Use the first ring (exterior)
            coords = geojson['coordinates'][0]
        elif geojson['type'] == 'MultiPolygon':
            # Use the first polygon's exterior ring
            coords = geojson['coordinates'][0][0]

        # Convert to (lat, lon) format for the map widget
        polygon_points = [(y, x) for x, y in coords]

        # Calculate bounding box
        bounds = geometry.bounds
        bbox = {
            'minX': bounds[0],
            'minY': bounds[1],
            'maxX': bounds[2],
            'maxY': bounds[3]
        }

        # Return the tile information
        return {
            'polygon_points': polygon_points,
            'boundingBox': bbox,
            'metadata_source': 'tile_index'
        }

    except Exception as e:
        logger.error(f"Error processing tile match: {str(e)}", exc_info=True)
        return {
            'polygon_points': [],
            'boundingBox': {
                'minX': -100.0,
                'minY': 40.0,
                'maxX': -99.995,
                'maxY': 40.005
            },
            'metadata_source': 'error'
        }

def extract_coordinates_from_filename(filename: str) -> Optional[Dict[str, float]]:
    """
    Extract coordinates from a filename.

    Args:
        filename: Name of the file

    Returns:
        Optional[Dict[str, float]]: Coordinates (x, y) if found, None otherwise
    """
    try:
        # Pattern 1: Look for numeric grid coordinates (e.g., 6273_1836)
        match = re.search(r'_(\\d{4})_(\\d{4})[a-d]?_', filename)
        if match:
            try:
                x = int(match.group(1))
                y = int(match.group(2))
                return {'x': x, 'y': y}
            except (ValueError, IndexError):
                pass

        # Pattern 2: Look for decimal coordinates (e.g., 123.456_789.012)
        match = re.search(r'(\\d+\\.\\d+)_(\\d+\\.\\d+)', filename)
        if match:
            try:
                x = float(match.group(1))
                y = float(match.group(2))
                return {'x': x, 'y': y}
            except (ValueError, IndexError):
                pass

        # Pattern 3: Look for UTM coordinates (e.g., 18TWP552896)
        match = re.search(r'_(\\d{2}[A-Z]{3}\\d{6})', filename)
        if match:
            # This would require a proper UTM to lat/lon conversion
            # For now, just return None
            pass

        return None

    except Exception as e:
        logger.error(f"Error extracting coordinates from filename: {str(e)}", exc_info=True)
        return None

def get_tile_boundary_for_file(project_name: str, filename: str) -> Dict[str, Any]:
    """
    Get the tile boundary for a file.

    Args:
        project_name: Name of the project
        filename: Name of the file

    Returns:
        Dict[str, Any]: Tile boundary information
    """
    try:
        # Get the tile index for the project
        tile_index = get_tile_index_for_project(project_name)
        if tile_index is None:
            logger.warning(f"No tile index found for project {project_name}")
            return {
                'boundingBox': {
                    'minX': -100.0,
                    'minY': 40.0,
                    'maxX': -99.995,
                    'maxY': 40.005
                },
                'metadata_source': 'default'
            }

        # Match the file to a tile in the index
        tile_match = match_file_to_tile_index(filename, tile_index)
        if tile_match:
            return tile_match

        # If no match found, use the project-level bounding box
        project_bbox = get_project_bounding_box(tile_index)
        if project_bbox:
            logger.info(f"Using project-level bounding box for file {filename}")
            return {
                'boundingBox': project_bbox,
                'metadata_source': 'project'
            }

        # If all else fails, return a default bounding box
        logger.warning(f"Using default bounding box for file {filename}")
        return {
            'boundingBox': {
                'minX': -100.0,
                'minY': 40.0,
                'maxX': -99.995,
                'maxY': 40.005
            },
            'metadata_source': 'default'
        }

    except Exception as e:
        logger.error(f"Error getting tile boundary for file: {str(e)}", exc_info=True)
        return {
            'boundingBox': {
                'minX': -100.0,
                'minY': 40.0,
                'maxX': -99.995,
                'maxY': 40.005
            },
            'metadata_source': 'error'
        }

def get_project_bounding_box(tile_index: gpd.GeoDataFrame) -> Optional[Dict[str, float]]:
    """
    Get the bounding box for a project.

    Args:
        tile_index: GeoDataFrame containing tile index data

    Returns:
        Optional[Dict[str, float]]: Bounding box for the project
    """
    try:
        # Calculate the total bounds of the tile index
        total_bounds = tile_index.total_bounds

        # Create a bounding box
        bbox = {
            'minX': total_bounds[0],
            'minY': total_bounds[1],
            'maxX': total_bounds[2],
            'maxY': total_bounds[3]
        }

        return bbox

    except Exception as e:
        logger.error(f"Error getting project bounding box: {str(e)}", exc_info=True)
        return None

def get_colorado_projects() -> List[str]:
    """
    Get a list of known Colorado LIDAR projects.

    Returns:
        List[str]: List of Colorado project names
    """
    # List of known Colorado LIDAR projects
    colorado_projects = [
        'USGS_LPC_CO_SoPlatteRiver_Lot1_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot2_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot3_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot4_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot5_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot6_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot7_2013_LAS_2015',
        'USGS_LPC_CO_SoPlatteRiver_Lot8_2013_LAS_2015',
        'USGS_LPC_CO_SanLuis_2011',
        'USGS_LPC_CO_GrandMesa_2016_LAS_2017',
        'USGS_LPC_CO_WesternCO_2016_LAS_2017',
        'USGS_LPC_CO_NorthernCO_2013_LAS_2015',
        'USGS_LPC_CO_CentralCO_2013_LAS_2015',
        'USGS_LPC_CO_SouthernCO_2013_LAS_2015',
        'USGS_LPC_CO_EasternCO_2013_LAS_2015',
        'USGS_LPC_CO_FrontRange_2013_LAS_2015',
        'USGS_LPC_CO_Denver_2013_LAS_2015',
        'USGS_LPC_CO_PuebloCounty_2014_LAS_2016',
        'USGS_LPC_CO_ElPasoCounty_2014_LAS_2016',
        'CO_Eastern_Plains_2018',
        'CO_Montezuma_County_2018',
        'CO_Routt_County_2018',
        'CO_Weld_County_2018',
        'CO_Mesa_County_2018',
        'CO_Larimer_County_2018',
        'CO_Huerfano_County_2018',
        'CO_Fremont_County_2018',
        'CO_Custer_County_2018',
        'CO_Chaffee_County_2018',
        'CO_Alamosa_County_2018',
        'CO_Pueblo_County_2018',
        'CO_Otero_County_2018',
        'CO_Las_Animas_County_2018',
        'CO_Crowley_County_2018',
        'CO_Bent_County_2018',
        'CO_Baca_County_2018',
        'CO_Prowers_County_2018',
        'CO_Kiowa_County_2018',
        'CO_Costilla_County_2018',
        'CO_Conejos_County_2018',
        'CO_Rio_Grande_County_2018',
        'CO_Mineral_County_2018',
        'CO_Saguache_County_2018',
        'CO_Gunnison_County_2018',
        'CO_Hinsdale_County_2018',
        'CO_San_Juan_County_2018',
        'CO_Dolores_County_2018',
        'CO_San_Miguel_County_2018',
        'CO_Ouray_County_2018',
        'CO_Montrose_County_2018',
        'CO_Delta_County_2018',
        'CO_Garfield_County_2018',
        'CO_Eagle_County_2018',
        'CO_Pitkin_County_2018',
        'CO_Summit_County_2018',
        'CO_Grand_County_2018',
        'CO_Jackson_County_2018',
        'CO_Moffat_County_2018',
        'CO_Rio_Blanco_County_2018',
        'CO_Boulder_County_2018',
        'CO_Jefferson_County_2018',
        'CO_Denver_County_2018',
        'CO_Arapahoe_County_2018',
        'CO_Adams_County_2018',
        'CO_Douglas_County_2018',
        'CO_Elbert_County_2018',
        'CO_Lincoln_County_2018',
        'CO_Kit_Carson_County_2018',
        'CO_Cheyenne_County_2018',
        'CO_Yuma_County_2018',
        'CO_Washington_County_2018',
        'CO_Morgan_County_2018',
        'CO_Logan_County_2018',
        'CO_Sedgwick_County_2018',
        'CO_Phillips_County_2018'
    ]

    logger.info(f"Using {len(colorado_projects)} known Colorado LIDAR projects")
    return colorado_projects

def list_all_projects(s3_client=None) -> List[str]:
    """
    List all available LIDAR projects in the USGS AWS S3 bucket.

    Args:
        s3_client: Initialized boto3 S3 client (optional)

    Returns:
        List[str]: List of project names
    """
    try:
        # Initialize S3 client if not provided
        if s3_client is None:
            s3_client = initialize_s3_client()
            if s3_client is None:
                logger.error("Failed to initialize S3 client")
                return []

        # Check if we have cached the project list
        if 'all_projects' in PROJECT_METADATA_CACHE:
            logger.info("Using cached project list")
            return PROJECT_METADATA_CACHE['all_projects']

        logger.info("Listing all LIDAR projects in USGS AWS S3 bucket")
        projects = []
        continuation_token = None

        while True:
            # Parameters for list_objects_v2
            params = {
                'Bucket': 'usgs-lidar-public',
                'Prefix': 'Projects/',
                'Delimiter': '/',
                'RequestPayer': 'requester',
                'MaxKeys': 1000  # Maximum allowed by S3 API
            }

            # Add continuation token if we have one
            if continuation_token:
                params['ContinuationToken'] = continuation_token

            # Make the request
            response = s3_client.list_objects_v2(**params)

            # Extract project names from CommonPrefixes
            for prefix in response.get('CommonPrefixes', []):
                prefix_name = prefix.get('Prefix', '')
                if prefix_name.startswith('Projects/'):
                    # Extract project name from prefix
                    project_name = prefix_name.split('/')[1]
                    if project_name:
                        projects.append(project_name)

            # Check if there are more results
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break

        logger.info(f"Found {len(projects)} LIDAR projects")

        # Cache the project list
        PROJECT_METADATA_CACHE['all_projects'] = projects

        return projects

    except Exception as e:
        logger.error(f"Error listing all projects: {str(e)}", exc_info=True)
        return []

def build_spatial_index_for_project(project_name: str) -> Optional[gpd.GeoDataFrame]:
    """
    Build a spatial index for a project.

    Args:
        project_name: Name of the project

    Returns:
        Optional[gpd.GeoDataFrame]: GeoDataFrame with spatial index
    """
    try:
        # Check if we already have a spatial index for this project
        if project_name in SPATIAL_INDEX_CACHE:
            logger.info(f"Using cached spatial index for project {project_name}")
            return SPATIAL_INDEX_CACHE[project_name]

        # Get the tile index for the project
        tile_index = get_tile_index_for_project(project_name)
        if tile_index is None:
            logger.warning(f"No tile index found for project {project_name}")
            return None

        # Make sure the tile index has a valid geometry column
        if 'geometry' not in tile_index.columns or tile_index.geometry.isna().all():
            logger.warning(f"Tile index for project {project_name} has no valid geometry column")
            return None

        # Build the spatial index
        logger.info(f"Building spatial index for project {project_name}")
        tile_index.sindex  # This builds the spatial index

        # Cache the spatial index
        SPATIAL_INDEX_CACHE[project_name] = tile_index

        return tile_index

    except Exception as e:
        logger.error(f"Error building spatial index for project {project_name}: {str(e)}", exc_info=True)
        return None

def find_tiles_intersecting_polygon(search_polygon: Polygon, projects: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Find all tiles that intersect with a search polygon.

    Args:
        search_polygon: Shapely Polygon defining the search area
        projects: List of project names to search (optional, searches all projects if None)

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary of project names to lists of tile information
    """
    try:
        # Log the search polygon details
        bounds = search_polygon.bounds
        logger.info(f"Finding tiles intersecting with search polygon")
        logger.info(f"Search polygon bounds: minX={bounds[0]:.6f}, minY={bounds[1]:.6f}, maxX={bounds[2]:.6f}, maxY={bounds[3]:.6f}")
        logger.info(f"Search polygon area: {search_polygon.area:.6f} square degrees")
        logger.info(f"Search polygon coordinates: {list(search_polygon.exterior.coords)}")

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if s3_client is None:
            logger.error("Failed to initialize S3 client")
            return {}

        # Get all projects if not provided
        if projects is None:
            projects = list_all_projects(s3_client)
            logger.info(f"Found {len(projects)} total projects in AWS S3 bucket")
        else:
            logger.info(f"Using {len(projects)} provided projects for search")

        # For debugging, log the first few projects
        if projects:
            logger.info(f"First few projects: {projects[:5]}")

        # Limit the number of projects for testing
        max_projects = 20  # Increased from 10 to 20 for better coverage
        if len(projects) > max_projects:
            logger.info(f"Limiting to {max_projects} projects for testing")
            projects = projects[:max_projects]

        # Find tiles in each project
        results = {}

        for project in projects:
            logger.info(f"Searching project {project} for tiles intersecting with polygon")

            # Build spatial index for the project
            tile_index = build_spatial_index_for_project(project)
            if tile_index is None:
                logger.warning(f"No spatial index available for project {project}")
                continue

            # Use the spatial index to find tiles that intersect with the search polygon
            try:
                # Get the bounds of the search polygon
                bounds = search_polygon.bounds

                # Use the spatial index to find candidate tiles
                possible_matches_idx = list(tile_index.sindex.intersection(bounds))
                possible_matches = tile_index.iloc[possible_matches_idx]

                # Perform precise intersection check
                intersecting_tiles = possible_matches[possible_matches.geometry.intersects(search_polygon)]

                if not intersecting_tiles.empty:
                    logger.info(f"Found {len(intersecting_tiles)} tiles in project {project} that intersect with the search polygon")

                    # Process each tile
                    project_results = []

                    for idx, tile in intersecting_tiles.iterrows():
                        # Extract tile information
                        tile_info = process_tile_match(tile)

                        # Add project information
                        tile_info['project'] = project

                        # Try to find a file ID or name
                        file_id = None
                        for col in tile.index:
                            if any(keyword in col.lower() for keyword in ['name', 'file', 'tile', 'id']):
                                file_id = str(tile[col])
                                break

                        if file_id:
                            tile_info['file_id'] = file_id

                        project_results.append(tile_info)

                    results[project] = project_results

            except Exception as e:
                logger.error(f"Error searching project {project}: {str(e)}", exc_info=True)

        logger.info(f"Found tiles in {len(results)} projects that intersect with the search polygon")
        return results

    except Exception as e:
        logger.error(f"Error finding tiles intersecting with polygon: {str(e)}", exc_info=True)
        return {}

def find_laz_files_for_tiles(project_name: str, tiles: List[Dict[str, Any]], s3_client=None) -> List[Dict[str, Any]]:
    """
    Find LAZ files for tiles in a project.

    Args:
        project_name: Name of the project
        tiles: List of tile information
        s3_client: Initialized boto3 S3 client (optional)

    Returns:
        List[Dict[str, Any]]: List of LAZ file information
    """
    try:
        logger.info(f"Finding LAZ files for {len(tiles)} tiles in project {project_name}")

        # Initialize S3 client if not provided
        if s3_client is None:
            s3_client = initialize_s3_client()
            if s3_client is None:
                logger.error("Failed to initialize S3 client")
                return []

        # Possible locations for LAZ files
        prefixes = [
            f"Projects/{project_name}/laz/",
            f"Projects/{project_name}/las/",
            f"Projects/{project_name}/las/tiled/",
            f"Projects/{project_name}/pointcloud/",
            f"Projects/{project_name}/data/",
            f"Projects/{project_name}/"
        ]

        # Find all LAZ files in the project
        all_laz_files = []

        for prefix in prefixes:
            logger.info(f"Searching for LAZ files in {prefix}")

            continuation_token = None
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
                response = s3_client.list_objects_v2(**params)

                # Process the files
                for item in response.get('Contents', []):
                    key = item.get('Key')
                    if key and (key.endswith('.laz') or key.endswith('.las')):
                        all_laz_files.append({
                            'key': key,
                            'size': item.get('Size'),
                            'last_modified': item.get('LastModified'),
                            'project': project_name
                        })

                # Check if there are more results
                if response.get('IsTruncated'):
                    continuation_token = response.get('NextContinuationToken')
                else:
                    break

        logger.info(f"Found {len(all_laz_files)} LAZ files in project {project_name}")

        # Match LAZ files to tiles
        matched_files = []

        for tile in tiles:
            file_id = tile.get('file_id')
            if not file_id:
                continue

            # Find LAZ files that match the tile ID
            for laz_file in all_laz_files:
                key = laz_file.get('key')
                filename = os.path.basename(key)

                # Check if the filename contains the tile ID
                if file_id in filename or filename in file_id:
                    # Add tile information to the LAZ file
                    laz_file['boundingBox'] = tile.get('boundingBox')
                    laz_file['polygon_points'] = tile.get('polygon_points')
                    laz_file['metadata_source'] = 'tile_index'

                    matched_files.append(laz_file)

        logger.info(f"Matched {len(matched_files)} LAZ files to tiles in project {project_name}")
        return matched_files

    except Exception as e:
        logger.error(f"Error finding LAZ files for tiles: {str(e)}", exc_info=True)
        return []

def search_lidar_by_polygon(search_polygon: Polygon, projects: List[str] = None) -> Dict[str, List[Dict[str, Any]]]:
    """
    Search for LIDAR files that intersect with a search polygon.

    Args:
        search_polygon: Shapely Polygon defining the search area
        projects: List of project names to search (optional, searches all projects if None)

    Returns:
        Dict[str, List[Dict[str, Any]]]: Dictionary of project names to lists of LIDAR file information
    """
    try:
        # Log the search polygon details
        bounds = search_polygon.bounds
        logger.info(f"Searching for LIDAR files that intersect with polygon")
        logger.info(f"Search polygon bounds: minX={bounds[0]:.6f}, minY={bounds[1]:.6f}, maxX={bounds[2]:.6f}, maxY={bounds[3]:.6f}")
        logger.info(f"Search polygon area: {search_polygon.area:.6f} square degrees")
        logger.info(f"Search polygon coordinates: {list(search_polygon.exterior.coords)}")

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if s3_client is None:
            logger.error("Failed to initialize S3 client")
            return {}

        # Find tiles that intersect with the search polygon
        logger.info("Finding tiles that intersect with the search polygon...")
        intersecting_tiles = find_tiles_intersecting_polygon(search_polygon, projects)

        if not intersecting_tiles:
            logger.warning("No tiles found that intersect with the search polygon")

            # For debugging, try with a simplified polygon
            logger.info("Trying with a simplified polygon...")
            simplified_polygon = search_polygon.simplify(0.001)
            logger.info(f"Simplified polygon area: {simplified_polygon.area:.6f} square degrees")
            logger.info(f"Simplified polygon coordinates: {list(simplified_polygon.exterior.coords)}")

            # Try with the simplified polygon
            intersecting_tiles = find_tiles_intersecting_polygon(simplified_polygon, projects)

            if not intersecting_tiles:
                logger.warning("No tiles found with simplified polygon either")
                return {}
            else:
                logger.info(f"Found tiles in {len(intersecting_tiles)} projects with simplified polygon")

        # Find LAZ files for each project's tiles
        results = {}
        total_tiles = sum(len(tiles) for tiles in intersecting_tiles.values())
        logger.info(f"Found {total_tiles} tiles in {len(intersecting_tiles)} projects that intersect with the search polygon")

        for project, tiles in intersecting_tiles.items():
            logger.info(f"Finding LAZ files for {len(tiles)} tiles in project {project}...")
            # Find LAZ files for the tiles
            laz_files = find_laz_files_for_tiles(project, tiles, s3_client)

            if laz_files:
                logger.info(f"Found {len(laz_files)} LAZ files in project {project}")
                results[project] = laz_files
            else:
                logger.warning(f"No LAZ files found for tiles in project {project}")

        total_files = sum(len(files) for files in results.values())
        logger.info(f"Found {total_files} LIDAR files in {len(results)} projects that intersect with the search polygon")
        return results

    except Exception as e:
        logger.error(f"Error searching LIDAR by polygon: {str(e)}", exc_info=True)
        return {}

if __name__ == "__main__":
    # Test the module
    logging.basicConfig(level=logging.INFO)

    # Test with a project
    project_name = "USGS_LPC_CA_LosAngeles_2016_LAS_2018"

    # Test spatial search
    from shapely.geometry import Polygon

    # Create a test polygon (Los Angeles area)
    search_polygon = Polygon([
        (-118.5, 34.0),
        (-118.5, 34.1),
        (-118.4, 34.1),
        (-118.4, 34.0),
        (-118.5, 34.0)
    ])

    # Search for LIDAR files
    results = search_lidar_by_polygon(search_polygon, [project_name])

    # Print the results
    for project, files in results.items():
        print(f"Project {project}: {len(files)} files")
        for file in files[:5]:  # Print first 5 files
            print(f"  {file['key']}")
            print(f"    Bounding box: {file.get('boundingBox')}")
            print(f"    Metadata source: {file.get('metadata_source')}")

    # Test with a specific file
    tile_index = get_tile_index_for_project(project_name)

    if tile_index is not None:
        print(f"Found tile index with {len(tile_index)} features")
        print(f"Columns: {list(tile_index.columns)}")

        # Test with a file
        filename = "CA_LosAngeles_2016_000010.laz"
        tile_boundary = get_tile_boundary_for_file(project_name, filename)

        print(f"Tile boundary for {filename}: {tile_boundary}")
    else:
        print(f"No tile index found for project {project_name}")
