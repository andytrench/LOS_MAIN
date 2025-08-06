"""
Utility module for extracting dates from LIDAR project metadata
"""

import re
import logging
from datetime import datetime

# Create logger
logger = logging.getLogger(__name__)

def extract_year_from_project_name(project_name):
    """Extract year from project name
    
    Args:
        project_name: The project name to extract year from
        
    Returns:
        str: The extracted year, or None if not found
    """
    # Look for 4-digit year in project name
    year_match = re.search(r'(?:_|^)(\d{4})(?:_|$)', project_name)
    if year_match:
        year = year_match.group(1)
        if 2000 <= int(year) <= 2100:  # Sanity check for reasonable year
            logger.info(f"Extracted year {year} from project name: {project_name}")
            return year
    
    # Try more aggressive pattern matching if the first attempt fails
    year_match = re.search(r'(\d{4})', project_name)
    if year_match:
        year = year_match.group(1)
        if 2000 <= int(year) <= 2100:  # Sanity check for reasonable year
            logger.info(f"Extracted year {year} from project name using fallback pattern: {project_name}")
            return year
    
    return None

def format_date_string(date_str):
    """Format date string to YYYY-MM-DD
    
    Args:
        date_str: The date string to format
        
    Returns:
        str: The formatted date string, or original if formatting fails
    """
    if not date_str:
        return None
        
    # Try various date formats
    formats = [
        '%Y%m%d',      # YYYYMMDD
        '%Y-%m-%d',    # YYYY-MM-DD
        '%Y/%m/%d',    # YYYY/MM/DD
        '%m/%d/%Y',    # MM/DD/YYYY
        '%d/%m/%Y',    # DD/MM/YYYY
        '%Y',          # YYYY
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # If we couldn't parse the date, return the original
    return date_str

def create_year_dates(year):
    """Create start and end dates for a year
    
    Args:
        year: The year to create dates for
        
    Returns:
        dict: Dictionary with Start and End dates
    """
    if not year:
        return {}
        
    return {
        'Start': f"{year}-01-01",
        'End': f"{year}-12-31"
    }

def extract_dates_from_xml(xml_content):
    """Extract dates from XML metadata
    
    Args:
        xml_content: The XML content to extract dates from
        
    Returns:
        dict: Dictionary with Start, End, and Publication dates
    """
    dates = {}
    
    # Look for begdate (start date)
    start_match = re.search(r'<begdate>(.*?)</begdate>', xml_content)
    if start_match:
        dates['Start'] = format_date_string(start_match.group(1))
    
    # Look for enddate (end date)
    end_match = re.search(r'<enddate>(.*?)</enddate>', xml_content)
    if end_match:
        dates['End'] = format_date_string(end_match.group(1))
    
    # Look for pubdate (publication date)
    pub_match = re.search(r'<pubdate>(.*?)</pubdate>', xml_content)
    if pub_match:
        dates['Publication'] = format_date_string(pub_match.group(1))
    
    return dates

def extract_dates_from_json(json_data):
    """Extract dates from JSON metadata
    
    Args:
        json_data: The JSON data to extract dates from
        
    Returns:
        dict: Dictionary with Start, End, and Publication dates
    """
    dates = {}
    
    # Check for dates in various formats
    if isinstance(json_data, dict):
        # Check for dates directly in the JSON
        if 'dates' in json_data:
            date_data = json_data['dates']
            if isinstance(date_data, dict):
                if 'start' in date_data:
                    dates['Start'] = format_date_string(date_data['start'])
                if 'end' in date_data:
                    dates['End'] = format_date_string(date_data['end'])
                if 'publication' in date_data or 'published' in date_data:
                    pub_date = date_data.get('publication') or date_data.get('published')
                    dates['Publication'] = format_date_string(pub_date)
        
        # Check for acquisition dates
        if 'acquisition' in json_data:
            acq_data = json_data['acquisition']
            if isinstance(acq_data, dict):
                if 'start' in acq_data:
                    dates['Start'] = format_date_string(acq_data['start'])
                if 'end' in acq_data:
                    dates['End'] = format_date_string(acq_data['end'])
        
        # Check for metadata dates
        if 'metadata' in json_data:
            meta_data = json_data['metadata']
            if isinstance(meta_data, dict) and 'date' in meta_data:
                dates['Publication'] = format_date_string(meta_data['date'])
    
    return dates
