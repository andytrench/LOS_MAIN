"""
Utility to query metadata URLs for LIDAR files and extract dates.
"""

import requests
import json
import xml.etree.ElementTree as ET
import re
import logging
import sys
import os
from datetime import datetime

# Add parent directory to path to allow importing from utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utilities.extract_dates import extract_dates_from_xml, extract_dates_from_json, format_date_string

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_tnm_metadata_url(source_id):
    """
    Get the metadata URL for a TNM item by source ID.
    
    Args:
        source_id: The source ID of the item
        
    Returns:
        str: The metadata URL
    """
    return f"https://tnmaccess.nationalmap.gov/api/v1/products/{source_id}"

def extract_metadata_urls_from_json(json_data):
    """
    Extract metadata URLs from JSON response.
    
    Args:
        json_data: The JSON data from the TNM API
        
    Returns:
        dict: Dictionary with metadata URLs
    """
    urls = {
        'xml': None,
        'json': None,
        'html': None
    }
    
    # Check if we have webLinks
    if 'webLinks' in json_data:
        for link in json_data['webLinks']:
            if link.get('type') == 'originalMetadata' and link.get('title') == 'Product Metadata':
                urls['xml'] = link.get('uri')
            elif link.get('type') == 'metadata' and link.get('title') == 'Metadata':
                urls['html'] = link.get('uri')
    
    # The JSON URL is the same as the API URL
    urls['json'] = json_data.get('metaUrl')
    
    return urls

def query_metadata_for_source_id(source_id):
    """
    Query metadata for a source ID and extract dates.
    
    Args:
        source_id: The source ID of the item
        
    Returns:
        dict: Dictionary with dates and metadata URLs
    """
    result = {
        'source_id': source_id,
        'dates': {
            'Start': 'N/A',
            'End': 'N/A',
            'Publication': 'N/A'
        },
        'urls': {
            'xml': None,
            'json': None,
            'html': None
        },
        'raw_data': None
    }
    
    try:
        # Get the metadata URL
        meta_url = get_tnm_metadata_url(source_id)
        logger.info(f"Querying metadata for source ID {source_id} at {meta_url}")
        
        # Query the metadata
        response = requests.get(meta_url, timeout=30)
        if response.status_code != 200:
            logger.error(f"Error querying metadata: {response.status_code}")
            return result
        
        # Parse the JSON response
        json_data = response.json()
        result['raw_data'] = json_data
        
        # Extract metadata URLs
        result['urls'] = extract_metadata_urls_from_json(json_data)
        logger.info(f"Extracted metadata URLs: {result['urls']}")
        
        # Try to extract dates from JSON
        json_dates = extract_dates_from_json(json_data)
        if json_dates:
            for key, value in json_dates.items():
                if value:
                    result['dates'][key] = value
            logger.info(f"Extracted dates from JSON: {json_dates}")
        
        # Try to extract dates from XML if available
        if result['urls']['xml']:
            try:
                xml_response = requests.get(result['urls']['xml'], timeout=30)
                if xml_response.status_code == 200:
                    xml_content = xml_response.content.decode('utf-8')
                    xml_dates = extract_dates_from_xml(xml_content)
                    
                    # Update dates if found in XML
                    for key, value in xml_dates.items():
                        if value and result['dates'][key] == 'N/A':
                            result['dates'][key] = value
                    
                    logger.info(f"Extracted dates from XML: {xml_dates}")
            except Exception as e:
                logger.error(f"Error extracting dates from XML: {e}")
        
        # Try to extract dates from publication date in JSON
        if 'publicationDate' in json_data and result['dates']['Publication'] == 'N/A':
            pub_date = json_data['publicationDate']
            result['dates']['Publication'] = format_date_string(pub_date)
            logger.info(f"Extracted publication date from JSON: {pub_date}")
        
        # Try to extract dates from title or filename
        if 'title' in json_data:
            title = json_data['title']
            year_match = re.search(r'(\d{4})', title)
            if year_match:
                year = year_match.group(1)
                if 2000 <= int(year) <= 2100:  # Sanity check for reasonable year
                    if result['dates']['Start'] == 'N/A':
                        result['dates']['Start'] = f"{year}-01-01"
                    if result['dates']['End'] == 'N/A':
                        result['dates']['End'] = f"{year}-12-31"
                    logger.info(f"Extracted year {year} from title: {title}")
        
        return result
    except Exception as e:
        logger.error(f"Error querying metadata: {e}")
        return result

def query_metadata_for_file(filename, source_id=None):
    """
    Query metadata for a file and extract dates.
    
    Args:
        filename: The filename to query metadata for
        source_id: Optional source ID to use instead of extracting from filename
        
    Returns:
        dict: Dictionary with dates and metadata URLs
    """
    # If source_id is provided, use it directly
    if source_id:
        return query_metadata_for_source_id(source_id)
    
    # Otherwise, try to extract source_id from filename
    # This is a placeholder - in a real implementation, you would need to
    # query the TNM API to find the source_id for the filename
    logger.error(f"Source ID not provided and cannot be extracted from filename: {filename}")
    return {
        'source_id': None,
        'dates': {
            'Start': 'N/A',
            'End': 'N/A',
            'Publication': 'N/A'
        },
        'urls': {
            'xml': None,
            'json': None,
            'html': None
        },
        'raw_data': None
    }

def main():
    """Main function to test the utility."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Query metadata URLs for LIDAR files and extract dates.')
    parser.add_argument('--source-id', help='Source ID to query metadata for')
    parser.add_argument('--file', help='File to query metadata for')
    args = parser.parse_args()
    
    if args.source_id:
        result = query_metadata_for_source_id(args.source_id)
        print(f"Results for source ID {args.source_id}:")
    elif args.file:
        result = query_metadata_for_file(args.file)
        print(f"Results for file {args.file}:")
    else:
        print("Please provide either --source-id or --file")
        return
    
    print(f"Dates:")
    for key, value in result['dates'].items():
        print(f"  {key}: {value}")
    
    print(f"Metadata URLs:")
    for key, value in result['urls'].items():
        print(f"  {key}: {value}")

if __name__ == '__main__':
    main()
