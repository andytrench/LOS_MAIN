"""
AWS Search Module with LIDAR Index Integration

This module provides functions to search for LIDAR data in the USGS AWS S3 bucket,
with integration with the LIDAR index database.
"""

import logging
from typing import List, Dict, Any, Tuple
from datetime import date
from shapely.geometry import Polygon

# Import from existing modules
from utilities.aws_search import initialize_s3_client, convert_laz_to_tnm_format
from utilities.tile_index_manager import search_lidar_by_polygon, get_colorado_projects
from utilities.lidar_index_search import search_lidar_index, database_exists as index_database_exists

# Configure logging
logger = logging.getLogger(__name__)

def search_aws_lidar_with_index(polygon_points: List[Tuple[float, float]], start_date: date, end_date: date, progress_callback=None, retrieve_metadata: bool = False) -> Dict[str, Any]:
    """
    Search for LIDAR data using the LIDAR index database and AWS S3 bucket.

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
            progress_callback("Initializing search...", 5)

        # First, check if we have a LIDAR index database
        if index_database_exists():
            logger.info("Using LIDAR index database for search")

            # Update progress
            if progress_callback:
                progress_callback("Searching LIDAR index...", 10)

            # Search the LIDAR index
            index_results = search_lidar_index(polygon_points, start_date, end_date, retrieve_metadata=retrieve_metadata)

            # Check if we found any results
            if index_results and index_results.get('items') and len(index_results.get('items', [])) > 0:
                logger.info(f"Found {len(index_results.get('items', []))} LIDAR files in index")

                # Update progress
                if progress_callback:
                    progress_callback("Found LIDAR files in index", 100)

                return index_results
            else:
                logger.info("No LIDAR files found in index, falling back to direct search")
        else:
            logger.info("LIDAR index database not found, using direct search")

        # Update progress
        if progress_callback:
            progress_callback("Initializing AWS S3 client...", 15)

        # Initialize S3 client
        s3_client = initialize_s3_client()
        if not s3_client:
            logger.error("Failed to initialize S3 client - check AWS credentials")
            return {'items': [], 'total': 0, 'error': 'Failed to initialize S3 client'}

        logger.info("AWS S3 client initialized successfully")

        # Update progress
        if progress_callback:
            progress_callback("Creating search polygon...", 20)

        # Create a shapely polygon from the points
        # Note: shapely uses (x, y) = (lon, lat) order, but our points are (lat, lon)
        search_polygon = Polygon([(lon, lat) for lat, lon in polygon_points])
        logger.info(f"Created search polygon from {len(polygon_points)} points")

        # Log the polygon bounds for debugging
        bounds = search_polygon.bounds
        logger.info(f"Search polygon bounds: minX={bounds[0]}, minY={bounds[1]}, maxX={bounds[2]}, maxY={bounds[3]}")

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

                # For Colorado, try specific county projects based on coordinates
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

        # Count total files
        total_files = sum(len(files) for files in project_files.values())
        logger.info(f"Found {total_files} LIDAR files across {len(project_files)} projects")

        # Update progress
        if progress_callback:
            progress_callback("Processing search results...", 80)

        # Flatten the results
        all_laz_files = []
        for project, files in project_files.items():
            logger.info(f"Found {len(files)} LIDAR files in project {project}")
            all_laz_files.extend(files)

        # Filter by date
        date_filtered_files = []
        for file in all_laz_files:
            # Extract year from last_modified
            last_modified = file.get('last_modified')
            if last_modified and hasattr(last_modified, 'year'):
                year = last_modified.year

                # Check if year is within date range
                if start_date and year < start_date.year:
                    continue

                if end_date and year > end_date.year:
                    continue

            date_filtered_files.append(file)

        logger.info(f"Files after date filtering: {len(date_filtered_files)}")

        # Update progress
        if progress_callback:
            progress_callback("Converting results to TNM format...", 90)

        # Convert to TNM API format
        tnm_format = convert_laz_to_tnm_format(date_filtered_files, s3_client)
        logger.info(f"Final result: {len(tnm_format.get('items', []))} LIDAR files")

        # Update progress
        if progress_callback:
            progress_callback("Search complete", 100)

        return tnm_format

    except Exception as e:
        logger.error(f"Error searching AWS LIDAR: {str(e)}", exc_info=True)
        return {'items': [], 'total': 0, 'error': str(e)}
