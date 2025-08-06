"""
Script to query metadata for LIDAR files in tower_parameters.json and extract dates.
"""

import json
import logging
import os
import sys
from utilities.query_metadata_urls import query_metadata_for_source_id

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_tower_parameters():
    """Load tower parameters from JSON file."""
    try:
        with open('tower_parameters.json', 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading tower_parameters.json: {e}")
        return None

def update_tower_parameters(tower_parameters):
    """Update tower parameters JSON file."""
    try:
        # First make a backup of the original file
        import shutil
        shutil.copy('tower_parameters.json', 'tower_parameters.json.bak')
        logger.info("Created backup of tower_parameters.json")

        # Then write the updated file
        with open('tower_parameters.json', 'w') as f:
            json.dump(tower_parameters, f, indent=2)
        logger.info("Updated tower_parameters.json")
    except Exception as e:
        logger.error(f"Error updating tower_parameters.json: {e}")

        # Try to restore from backup if update failed
        try:
            if os.path.exists('tower_parameters.json.bak'):
                shutil.copy('tower_parameters.json.bak', 'tower_parameters.json')
                logger.info("Restored tower_parameters.json from backup")
        except Exception as restore_error:
            logger.error(f"Error restoring from backup: {restore_error}")

def extract_date_from_url(url):
    """Extract date from URL path."""
    # Look for year in the URL path
    import re

    # First, look for a year in the path segments
    path_segments = url.split('/')
    for segment in path_segments:
        # Look for a year (2000-2025) in the segment
        year_match = re.search(r'(20\d{2})', segment)
        if year_match:
            year = year_match.group(1)
            logger.info(f"Found year {year} in URL path segment: {segment}")
            return {
                'Start': f"{year}-01-01",
                'End': f"{year}-12-31",
                'Publication': f"{year}-12-31"
            }

    # If no year found in path segments, try the filename
    filename = url.split('/')[-1]
    year_match = re.search(r'(20\d{2})', filename)
    if year_match:
        year = year_match.group(1)
        logger.info(f"Found year {year} in filename: {filename}")
        return {
            'Start': f"{year}-01-01",
            'End': f"{year}-12-31",
            'Publication': f"{year}-12-31"
        }

    return None

def query_lidar_dates(tower_parameters):
    """Query metadata for LIDAR files and extract dates."""
    if not tower_parameters or 'lidar_data' not in tower_parameters:
        logger.error("No LIDAR data found in tower_parameters.json")
        return tower_parameters

    # Iterate through LIDAR projects
    for project_name, project_data in tower_parameters['lidar_data'].items():
        logger.info(f"Processing LIDAR project: {project_name}")

        # Check if the project already has valid dates
        if 'dates' in project_data and not all(value == 'N/A' for value in project_data['dates'].values()):
            logger.info(f"Project {project_name} already has valid dates: {project_data['dates']}")
            continue

        # If dates exist but are all N/A, we'll try to extract them
        if 'dates' in project_data:
            logger.info(f"Project {project_name} has dates but they are all N/A: {project_data['dates']}")

        # Initialize dates dictionary
        project_data['dates'] = {
            'Start': 'N/A',
            'End': 'N/A',
            'Publication': 'N/A'
        }

        # First try to extract date from the download URL
        download_url = project_data.get('download_url')
        if download_url:
            logger.info(f"Trying to extract date from download URL: {download_url}")
            dates = extract_date_from_url(download_url)
            if dates:
                project_data['dates'] = dates
                logger.info(f"Extracted dates from download URL: {dates}")
                continue

        # If no date found in download URL, try each file
        for file_data in project_data.get('files', []):
            file_url = file_data.get('download_url')
            if not file_url:
                logger.warning(f"No download URL found for file: {file_data.get('filename')}")
                continue

            logger.info(f"Trying to extract date from file URL: {file_url}")
            dates = extract_date_from_url(file_url)
            if dates:
                project_data['dates'] = dates
                logger.info(f"Extracted dates from file URL: {dates}")
                break

        # Try to extract year from project name if dates are still missing
        if all(value == 'N/A' for value in project_data['dates'].values()):
            logger.warning(f"Could not find any dates for project {project_name}, trying to extract from project name")

            # Look for 4-digit year in project name
            import re
            year_match = re.search(r'(\d{4})', project_name)
            if year_match:
                year = year_match.group(1)
                if 2000 <= int(year) <= 2100:  # Sanity check for reasonable year
                    project_data['dates']['Start'] = f"{year}-01-01"
                    project_data['dates']['End'] = f"{year}-12-31"
                    logger.info(f"Extracted year {year} from project name: {project_name}")

        # Log the final dates
        logger.info(f"Final dates for project {project_name}: {project_data['dates']}")

    return tower_parameters

def main():
    """Main function."""
    # Load tower parameters
    tower_parameters = load_tower_parameters()
    if not tower_parameters:
        return

    # Query LIDAR dates
    updated_parameters = query_lidar_dates(tower_parameters)

    # Update tower parameters
    update_tower_parameters(updated_parameters)

if __name__ == '__main__':
    main()
