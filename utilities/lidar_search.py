import logging
import time
import requests
from datetime import date
import tkinter as tk
from tkinter import messagebox

# Configure logging
logger = logging.getLogger(__name__)

def search_lidar_data(polygon_points, start_date, end_date, callback=None):
    """
    Search for LIDAR data within a polygon area.
    
    Args:
        polygon_points: List of (lat, lon) tuples defining the search area
        start_date: Start date for the search (YYYY-MM-DD string or date object)
        end_date: End date for the search (YYYY-MM-DD string or date object)
        callback: Optional callback function to process results
        
    Returns:
        Dictionary containing search results
    """
    try:
        # Format polygon points for the API
        polygon_str = ",".join([f"{lon} {lat}" for lat, lon in polygon_points])
        logger.debug(f"Formatted polygon string: {polygon_str}")

        base_url = "https://tnmaccess.nationalmap.gov/api/v1/products"

        # Initialize variables for pagination
        offset = 0
        page_size = 25  # Reduced batch size
        all_data = []
        total_results = None

        # Convert dates to strings if they are date objects
        if isinstance(start_date, date):
            start_date = start_date.strftime("%Y-%m-%d")
        if isinstance(end_date, date):
            end_date = end_date.strftime("%Y-%m-%d")
            
        logger.info(f"Using date range: {start_date} to {end_date}")

        while True:
            params = {
                "polygon": polygon_str,
                "datasets": "Lidar Point Cloud (LPC)",
                "prodFormats": "LAZ",  # Only get LAZ files
                "outputFormat": "JSON",
                "dateType": "dateCreated",
                "start": start_date,
                "end": end_date,
                "maxResults": str(page_size),  # Convert to string to ensure compatibility
                "offset": str(offset)          # Convert to string to ensure compatibility
            }

            logger.info(f"Making LIDAR API request - Page: {offset//page_size + 1}, Offset: {offset}, Items so far: {len(all_data)}")

            try:
                response = requests.get(base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()

                # Get total results count from first response
                if total_results is None:
                    total_results = data.get('total', 0)
                    logger.info(f"Total available results: {total_results}")

                # Add items from this page to our collection
                items = data.get('items', [])

                # Log detailed information about items to debug duplicates
                if offset > 0 and items:
                    logger.debug(f"First item on this page: {items[0]['sourceId'] if items else 'No items'}")
                    logger.debug(f"Last item on this page: {items[-1]['sourceId'] if items else 'No items'}")

                    # Check for duplicates between pages
                    prev_source_ids = set(item.get('sourceId') for item in all_data)
                    current_source_ids = set(item.get('sourceId') for item in items)
                    duplicate_count = len(prev_source_ids.intersection(current_source_ids))
                    if duplicate_count > 0:
                        logger.warning(f"Found {duplicate_count} duplicate items on page {offset//page_size + 1}")

                        # Don't add duplicates to all_data
                        new_items = [item for item in items if item.get('sourceId') not in prev_source_ids]
                        logger.info(f"Adding {len(new_items)} new non-duplicate items")
                        all_data.extend(new_items)
                    else:
                        all_data.extend(items)
                else:
                    # On first page, just add all items
                    all_data.extend(items)

                current_page_count = len(items)

                # Detailed logging for this page
                logger.info(f"Page {offset//page_size + 1} results:")
                logger.info(f"- Items in this page: {current_page_count}")
                logger.info(f"- Total items collected: {len(all_data)}")
                logger.info(f"- Expected total: {total_results}")

                # Break if we've got all results or this page was empty
                if current_page_count == 0:
                    logger.info("No more results in this page, stopping pagination")
                    break
                if len(all_data) >= total_results:
                    logger.info("Collected all available results")
                    break

                # Calculate next offset based on the total items collected so far
                # This ensures we don't skip or duplicate results
                offset = len(all_data)
                logger.info(f"Next offset set to: {offset}")

                # Add a small delay between requests to avoid rate limiting
                time.sleep(0.5)

            except requests.exceptions.RequestException as re:
                logger.error(f"Request failed: {re}")
                if hasattr(re, 'response') and re.response is not None:
                    logger.error(f"Response status: {re.response.status_code}")
                    logger.error(f"Response content: {re.response.text[:500]}")
                if callback:
                    callback({"error": f"Failed to search for LIDAR data: {str(re)}"})
                return {"error": str(re)}

        # Process all collected results
        if all_data:
            logger.info(f"Processing {len(all_data)} total LIDAR results")

            # Final duplicate check - ensure all results are unique by sourceId
            source_ids_seen = set()
            unique_results = []
            for item in all_data:
                source_id = item.get('sourceId')
                if source_id not in source_ids_seen:
                    source_ids_seen.add(source_id)
                    unique_results.append(item)

            # Log if we found any duplicates
            duplicate_count = len(all_data) - len(unique_results)
            if duplicate_count > 0:
                logger.warning(f"Removed {duplicate_count} duplicate results in final cleanup")
                all_data = unique_results

            # Log some sample data to verify what we're getting
            if len(all_data) > 0:
                logger.debug(f"Sample first result: {all_data[0]}")
            if len(all_data) > 49:
                logger.debug(f"Sample 50th result: {all_data[49]}")
                
            # Call the callback function if provided
            if callback:
                callback({"items": all_data})
                
            return {"items": all_data}
        else:
            logger.warning("No LIDAR data found")
            if callback:
                callback({"items": []})
            return {"items": []}

    except Exception as e:
        logger.error(f"Error in LIDAR search: {str(e)}", exc_info=True)
        if callback:
            callback({"error": f"An error occurred during LIDAR search: {str(e)}"})
        return {"error": str(e)}

def format_file_size(size_bytes):
    """
    Format file size in bytes to a human-readable format.
    
    Args:
        size_bytes: Size in bytes (can be int, float, or string)
        
    Returns:
        Formatted string with appropriate units
    """
    if isinstance(size_bytes, str):
        try:
            size_bytes = float(size_bytes)
        except ValueError:
            return size_bytes  # Return original if not convertible
    
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes/(1024*1024):.1f} MB"
    else:
        return f"{size_bytes/(1024*1024*1024):.2f} GB"

def group_lidar_by_project(items):
    """
    Group LIDAR data items by project name.
    
    Args:
        items: List of LIDAR data items from the API
        
    Returns:
        Dictionary mapping project names to lists of items
    """
    from utilities.metadata import get_project_name
    
    project_items = {}
    
    for item in items:
        url = item.get('downloadURL')
        if url:
            filename = url.split('/')[-1]
            project_name = get_project_name(filename)
            
            if project_name not in project_items:
                project_items[project_name] = []
                
            project_items[project_name].append(item)
    
    return project_items
