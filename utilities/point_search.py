import requests
import logging
import json
from typing import List, Dict, Any, Tuple, Optional
from datetime import date

# Configure logging
logger = logging.getLogger(__name__)

def fetch_tnm_point_data(x: float = -104.9903, y: float = 39.7392,
                        dataset: str = 'Lidar Point Cloud (LPC)',
                        formats: str = 'LAS,LAZ',
                        start_date: str = None,
                        end_date: str = None,
                        offset: float = 0.0) -> Optional[Dict[str, Any]]:
    """
    Fetch TNM data for a specific point location.

    Args:
        x: Longitude in decimal degrees
        y: Latitude in decimal degrees
        dataset: Dataset name to search for
        formats: Comma-separated list of product formats
        start_date: Optional start date for filtering (YYYY-MM-DD)
        end_date: Optional end date for filtering (YYYY-MM-DD)
        offset: Optional offset in decimal degrees to create a small bounding box around the point
               (default: 0.0, which means use a single point)

    Returns:
        Dictionary containing the API response or None if the request fails
    """
    # TNM API base URL
    base_url = "https://tnmaccess.nationalmap.gov/api/v1"
    products_endpoint = "/products"

    # Apply offset to create a small bounding box around the point
    # This helps ensure we capture all relevant tiles
    x_min = x - offset
    y_min = y - offset
    x_max = x + offset
    y_max = y + offset

    # Build query parameters - notice the trailing comma in bbox parameter
    # If offset is provided, use a small bounding box instead of a single point
    if offset > 0:
        params = {
            'bbox': f"{x_min},{y_min},{x_max},{y_max},",  # Small bounding box with trailing comma
            'prodFormats': formats,
            'datasets': dataset,
            'outputFormat': 'JSON'
        }
    else:
        params = {
            'bbox': f"{x},{y},{x},{y},",  # Single point as bbox with trailing comma
            'prodFormats': formats,
            'datasets': dataset,
            'outputFormat': 'JSON'
        }

    # Add date parameters if provided
    if start_date and end_date:
        params['dateType'] = 'dateCreated'
        params['start'] = start_date
        params['end'] = end_date

    # Construct the URL with parameters
    url = f"{base_url}{products_endpoint}"

    if offset > 0:
        logger.info(f"Searching for {dataset} data in bounding box: ({x_min}, {y_min}) to ({x_max}, {y_max})")
    else:
        logger.info(f"Searching for {dataset} data at coordinates: ({x}, {y})")
    logger.info(f"Formats requested: {formats}")
    logger.debug(f"API URL: {url}")
    logger.debug(f"Query parameters: {params}")

    try:
        # Make the API request
        response = requests.get(url, params=params)
        response.raise_for_status()

        # Try to parse the JSON response
        try:
            raw_data = response.json()
        except json.JSONDecodeError as json_error:
            logger.error(f"JSON parsing error: {json_error}")
            return None
            
        # Use conditional parsing to handle different TNM response formats
        try:
            from utilities.tnm_parser import parse_tnm_response
            data = parse_tnm_response(raw_data, logger)
            
            # Check if the parser found an error
            if data.get('status') == 'error':
                logger.error(f"TNM parser found error: {data.get('error')}")
                return None
        except ImportError:
            # Fallback to direct parsing if import fails
            logger.warning("Could not import TNM parser, using direct parsing")
            data = raw_data

        # Process and display results
        if data.get('items') and len(data['items']) > 0:
            items = data['items']
            logger.info(f"Found {len(items)} products at point ({x}, {y})")

            for index, item in enumerate(items, 1):
                logger.debug(f"\n{index}. {item.get('title', 'Unnamed product')}")
                logger.debug(f"   Format: {item.get('format', 'Unknown')}")
                logger.debug(f"   Size: {item.get('sizeInBytes', 0) / 1024 / 1024:.2f} MB")
                logger.debug(f"   Date: {item.get('publicationDate', 'Unknown')}")

                if item.get('downloadURL'):
                    logger.debug(f"   Download: {item['downloadURL']}")
                if item.get('previewGraphicURL'):
                    logger.debug(f"   Preview: {item['previewGraphicURL']}")

                bbox = item.get('boundingBox', {})
                if bbox:
                    logger.debug(f"   Bounds: {bbox.get('minX', 'N/A')}, {bbox.get('minY', 'N/A')} to "
                          f"{bbox.get('maxX', 'N/A')}, {bbox.get('maxY', 'N/A')}")

            if data.get('messages'):
                logger.debug("\nAPI Messages:")
                for msg in data['messages']:
                    logger.debug(f"- {msg}")
        else:
            logger.info(f"No products found at location ({x}, {y}).")

        return data
    except requests.exceptions.RequestException as error:
        logger.error(f"Error fetching data from TNM API: {error}")
        return None

def search_lidar_by_points(points: List[Tuple[float, float]],
                          start_date: str = None,
                          end_date: str = None,
                          offset: float = 0.001) -> Dict[str, Any]:
    """
    Search for LIDAR data at multiple points along a path.

    Args:
        points: List of (lat, lon) tuples representing points along the path
        start_date: Start date for filtering (YYYY-MM-DD)
        end_date: End date for filtering (YYYY-MM-DD)
        offset: Offset in decimal degrees to create a small bounding box around each point
                (default: 0.001, approximately 100 meters)

    Returns:
        Dictionary containing combined search results
    """
    logger.info(f"Starting point-based LIDAR search with {len(points)} points")
    logger.info(f"Using points with offset {offset} degrees (approximately {offset * 111000:.0f} meters)")

    # Convert dates to strings if they are date objects
    if isinstance(start_date, date):
        start_date = start_date.strftime("%Y-%m-%d")
    if isinstance(end_date, date):
        end_date = end_date.strftime("%Y-%m-%d")

    all_items = []
    unique_source_ids = set()  # Track unique items to avoid duplicates

    for i, (lat, lon) in enumerate(points):
        logger.info(f"Searching point {i+1}/{len(points)}: ({lat}, {lon}) with offset {offset}")

        # Search at this point with the specified offset
        result = fetch_tnm_point_data(
            x=lon,  # Note: x is longitude
            y=lat,  # y is latitude
            dataset='Lidar Point Cloud (LPC)',
            formats='LAZ',
            start_date=start_date,
            end_date=end_date,
            offset=offset  # Use the offset parameter to create a small bounding box
        )

        if result and 'items' in result:
            # Add unique items to our collection
            for item in result['items']:
                source_id = item.get('sourceId')
                if source_id and source_id not in unique_source_ids:
                    unique_source_ids.add(source_id)
                    all_items.append(item)

    logger.info(f"Point search complete. Found {len(all_items)} unique LIDAR files")
    return {"items": all_items}
