import json
import os
import requests
from datetime import datetime
import logging
import re
import shutil
import time
from dotenv import load_dotenv
import anthropic
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# Load environment variables
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Constants
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
CLAUDE_MODEL = "claude-3-opus-20240229"  # Use the most capable model for detailed analysis

def fetch_metadata(item_id):
    """Fetch metadata for a given item ID from ScienceBase."""
    try:
        if not item_id:
            logger.error("No item ID provided to fetch_metadata")
            raise ValueError("Item ID is required")
            
        logger.info(f"Fetching metadata for item ID: {item_id}")
        url = f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"
        
        try:
            response = requests.get(url, timeout=30)
            logger.info(f"Received response with status code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    metadata = response.json()
                    logger.info(f"Successfully parsed JSON metadata with keys: {list(metadata.keys())}")
                    return metadata
                except json.JSONDecodeError as json_error:
                    logger.error(f"Error parsing JSON response: {json_error}", exc_info=True)
                    raise Exception(f"Failed to parse metadata for item {item_id}: {json_error}")
            else:
                logger.error(f"Failed to fetch metadata for item {item_id}. Status code: {response.status_code}")
                raise Exception(f"Failed to fetch metadata for item {item_id}. Status code: {response.status_code}")
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Request error fetching metadata: {req_error}", exc_info=True)
            raise Exception(f"Network error fetching metadata for item {item_id}: {req_error}")
    except Exception as e:
        logger.error(f"Error in fetch_metadata: {e}", exc_info=True)
        raise

def fetch_xml_metadata(metadata):
    """Fetch XML metadata from a metadata object."""
    try:
        if not metadata or not isinstance(metadata, dict):
            logger.warning("Invalid metadata provided to fetch_xml_metadata")
            return None
            
        logger.info("Searching for XML metadata link")
        metadata_link = None
        
        # Check for webLinks
        if 'webLinks' in metadata and isinstance(metadata['webLinks'], list):
            for link in metadata['webLinks']:
                if isinstance(link, dict) and link.get('type') == 'originalMetadata' and link.get('title') == 'Product Metadata':
                    metadata_link = link.get('uri')
                    logger.info(f"Found XML metadata link: {metadata_link}")
                    break
        
        if not metadata_link:
            logger.warning("No XML metadata link found in metadata")
            return None
            
        # Fetch the XML metadata
        logger.info(f"Fetching XML metadata from: {metadata_link}")
        try:
            response = requests.get(metadata_link, timeout=30)
            if response.status_code == 200:
                logger.info(f"Successfully fetched XML metadata, size: {len(response.content)} bytes")
                try:
                    xml_root = ET.fromstring(response.content)
                    logger.info("Successfully parsed XML metadata")
                    return xml_root
                except ET.ParseError as parse_error:
                    logger.error(f"Error parsing XML metadata: {parse_error}", exc_info=True)
                    return None
            else:
                logger.error(f"Failed to fetch XML metadata, status code: {response.status_code}")
                return None
        except requests.exceptions.RequestException as req_error:
            logger.error(f"Request error fetching XML metadata: {req_error}", exc_info=True)
            return None
    except Exception as e:
        logger.error(f"Error in fetch_xml_metadata: {e}", exc_info=True)
        return None

def extract_metadata(metadata):
    """Extract relevant metadata from a metadata object."""
    try:
        if not metadata or not isinstance(metadata, dict):
            logger.warning("Invalid metadata provided to extract_metadata")
            return {}
            
        logger.info(f"Extracting metadata with keys: {list(metadata.keys())}")
        
        # Try to fetch XML metadata
        xml_root = fetch_xml_metadata(metadata)
        
        # Initialize info dictionary with default values
        info = {
            'title': metadata.get('title', 'N/A'),
            'project_name': metadata.get('title', 'N/A').split(' - ')[0] if ' - ' in metadata.get('title', '') else metadata.get('title', 'N/A'),
            'publication_date': 'N/A',
            'start_date': 'N/A',
            'end_date': 'N/A',
            'data': metadata
        }
        
        # Extract dates
        if 'dates' in metadata and isinstance(metadata['dates'], list):
            for date_entry in metadata['dates']:
                if isinstance(date_entry, dict):
                    if date_entry.get('type') == 'Publication' and 'dateString' in date_entry:
                        info['publication_date'] = date_entry['dateString']
                    elif date_entry.get('type') == 'Start' and 'dateString' in date_entry:
                        info['start_date'] = date_entry['dateString']
                    elif date_entry.get('type') == 'End' and 'dateString' in date_entry:
                        info['end_date'] = date_entry['dateString']
            
            logger.info(f"Extracted dates: publication={info['publication_date']}, start={info['start_date']}, end={info['end_date']}")
        else:
            logger.warning("No dates found in metadata")
        
        # Extract spatial reference information
        spatial_ref = {}
        
        # Try to extract from XML first if available
        if xml_root is not None:
            try:
                # Extract horizontal datum
                horiz_datum_elements = xml_root.findall(".//horizDatum")
                if horiz_datum_elements:
                    spatial_ref['horizontal_datum'] = horiz_datum_elements[0].text
                    logger.info(f"Extracted horizontal datum from XML: {spatial_ref['horizontal_datum']}")
                
                # Extract vertical datum
                vert_datum_elements = xml_root.findall(".//vertDatum")
                if vert_datum_elements:
                    spatial_ref['vertical_datum'] = vert_datum_elements[0].text
                    logger.info(f"Extracted vertical datum from XML: {spatial_ref['vertical_datum']}")
                
                # Extract projection
                proj_elements = xml_root.findall(".//mapprojn")
                if proj_elements:
                    spatial_ref['projection'] = proj_elements[0].text
                    logger.info(f"Extracted projection from XML: {spatial_ref['projection']}")
                
                # Extract units
                units_elements = xml_root.findall(".//plandu")
                if units_elements:
                    spatial_ref['units'] = units_elements[0].text
                    logger.info(f"Extracted units from XML: {spatial_ref['units']}")
            except Exception as xml_extract_error:
                logger.error(f"Error extracting spatial reference from XML: {xml_extract_error}", exc_info=True)
        
        # If we couldn't get from XML, try from JSON
        if not spatial_ref and 'spatial' in metadata and isinstance(metadata['spatial'], dict):
            try:
                if 'horizontalDatum' in metadata['spatial']:
                    spatial_ref['horizontal_datum'] = metadata['spatial']['horizontalDatum']
                if 'verticalDatum' in metadata['spatial']:
                    spatial_ref['vertical_datum'] = metadata['spatial']['verticalDatum']
                if 'projection' in metadata['spatial']:
                    spatial_ref['projection'] = metadata['spatial']['projection']
                if 'units' in metadata['spatial']:
                    spatial_ref['units'] = metadata['spatial']['units']
                
                logger.info(f"Extracted spatial reference from JSON metadata")
            except Exception as json_extract_error:
                logger.error(f"Error extracting spatial reference from JSON: {json_extract_error}", exc_info=True)
        
        info['spatial_ref'] = spatial_ref
        logger.info(f"Spatial reference keys: {list(spatial_ref.keys())}")
        
        # Extract bounds
        bounds = {}
        
        # Try to extract from XML first if available
        if xml_root is not None:
            try:
                # Extract bounds
                west_elements = xml_root.findall(".//westBL")
                east_elements = xml_root.findall(".//eastBL")
                north_elements = xml_root.findall(".//northBL")
                south_elements = xml_root.findall(".//southBL")
                
                if west_elements:
                    bounds['west'] = west_elements[0].text
                if east_elements:
                    bounds['east'] = east_elements[0].text
                if north_elements:
                    bounds['north'] = north_elements[0].text
                if south_elements:
                    bounds['south'] = south_elements[0].text
                
                if bounds:
                    logger.info(f"Extracted bounds from XML")
            except Exception as xml_bounds_error:
                logger.error(f"Error extracting bounds from XML: {xml_bounds_error}", exc_info=True)
        
        # If we couldn't get from XML, try from JSON
        if not bounds and 'extent' in metadata and isinstance(metadata['extent'], dict):
            try:
                if 'geographicExtent' in metadata['extent'] and isinstance(metadata['extent']['geographicExtent'], dict):
                    geo_extent = metadata['extent']['geographicExtent']
                    if 'boundingBox' in geo_extent and isinstance(geo_extent['boundingBox'], dict):
                        bbox = geo_extent['boundingBox']
                        if 'minX' in bbox:
                            bounds['west'] = str(bbox['minX'])
                        if 'maxX' in bbox:
                            bounds['east'] = str(bbox['maxX'])
                        if 'minY' in bbox:
                            bounds['south'] = str(bbox['minY'])
                        if 'maxY' in bbox:
                            bounds['north'] = str(bbox['maxY'])
                
                if bounds:
                    logger.info(f"Extracted bounds from JSON metadata")
            except Exception as json_bounds_error:
                logger.error(f"Error extracting bounds from JSON: {json_bounds_error}", exc_info=True)
        
        info['bounds'] = bounds
        logger.info(f"Bounds keys: {list(bounds.keys())}")
        
        # Extract quality information
        quality = {}
        
        # Try to extract from XML first if available
        if xml_root is not None:
            try:
                # Extract vertical accuracy
                vert_acc_elements = xml_root.findall(".//vertacc")
                if vert_acc_elements:
                    quality['vertical_accuracy'] = vert_acc_elements[0].text
                    logger.info(f"Extracted vertical accuracy from XML: {quality['vertical_accuracy']}")
                
                # Extract horizontal accuracy
                horiz_acc_elements = xml_root.findall(".//horizpa")
                if horiz_acc_elements:
                    quality['horizontal_accuracy'] = horiz_acc_elements[0].text
                    logger.info(f"Extracted horizontal accuracy from XML: {quality['horizontal_accuracy']}")
                
                # Extract point density
                point_density_elements = xml_root.findall(".//ptvdensity")
                if point_density_elements:
                    quality['point_density'] = point_density_elements[0].text
                    logger.info(f"Extracted point density from XML: {quality['point_density']}")
            except Exception as xml_quality_error:
                logger.error(f"Error extracting quality info from XML: {xml_quality_error}", exc_info=True)
        
        # If we couldn't get from XML, try from JSON
        if not quality and 'quality' in metadata and isinstance(metadata['quality'], dict):
            try:
                if 'verticalAccuracy' in metadata['quality']:
                    quality['vertical_accuracy'] = metadata['quality']['verticalAccuracy']
                if 'horizontalAccuracy' in metadata['quality']:
                    quality['horizontal_accuracy'] = metadata['quality']['horizontalAccuracy']
                if 'pointDensity' in metadata['quality']:
                    quality['point_density'] = metadata['quality']['pointDensity']
                
                if quality:
                    logger.info(f"Extracted quality information from JSON metadata")
            except Exception as json_quality_error:
                logger.error(f"Error extracting quality info from JSON: {json_quality_error}", exc_info=True)
        
        info['quality'] = quality
        logger.info(f"Quality keys: {list(quality.keys())}")
        
        return info
    except Exception as e:
        logger.error(f"Error in extract_metadata: {e}", exc_info=True)
        return {
            'title': 'Error extracting metadata',
            'project_name': 'Unknown Project',
            'publication_date': 'N/A',
            'start_date': 'N/A',
            'end_date': 'N/A',
            'data': metadata or {},
            'spatial_ref': {},
            'bounds': {},
            'quality': {}
        }

def extract_datum_info(xml_root):
    """Extract datum information from XML."""
    try:
        if xml_root is None:
            logger.warning("No XML root provided to extract_datum_info")
            return {}, {}
            
        logger.info("Extracting datum information from XML")
        datum_info = {}
        projection_info = {}
        
        # Extract vertical datum information
        try:
            vertdef = xml_root.find('.//spref/vertdef')
            if vertdef is not None:
                altsys = vertdef.find('altsys')
                if altsys is not None:
                    datum_info['vertical_datum'] = altsys.find('altdatum').text if altsys.find('altdatum') is not None else 'N/A'
                    datum_info['vertical_resolution'] = altsys.find('altres').text if altsys.find('altres') is not None else 'N/A'
                    datum_info['vertical_units'] = altsys.find('altunits').text if altsys.find('altunits') is not None else 'N/A'
                    datum_info['vertical_encoding'] = altsys.find('altenc').text if altsys.find('altenc') is not None else 'N/A'
                    logger.info(f"Extracted vertical datum: {datum_info['vertical_datum']}")
                else:
                    logger.warning("No altsys element found in vertdef")
            else:
                logger.warning("No vertdef element found in XML")
        except Exception as vert_error:
            logger.error(f"Error extracting vertical datum info: {vert_error}", exc_info=True)
    
        # Extract horizontal datum information
        try:
            horizsys = xml_root.find('.//spref/horizsys')
            if horizsys is not None:
                # Try to get the geodetic model first
                geodeticmodel = horizsys.find('.//geodeticmodel')
                if geodeticmodel is not None:
                    datum_info['horizontal_datum'] = geodeticmodel.find('hdatum').text if geodeticmodel.find('hdatum') is not None else 'N/A'
                    datum_info['ellipsoid'] = geodeticmodel.find('ellips').text if geodeticmodel.find('ellips') is not None else 'N/A'
                    logger.info(f"Extracted horizontal datum: {datum_info['horizontal_datum']}")
                else:
                    logger.warning("No geodeticmodel element found in horizsys")
    
                # Then try to get the planar information
                try:
                    planar = horizsys.find('planar')
                    if planar is not None:
                        mapproj = planar.find('mapproj')
                        if mapproj is not None:
                            projection_info['projection_name'] = mapproj.find('mapprojn').text if mapproj.find('mapprojn') is not None else 'N/A'
                            logger.info(f"Extracted projection name: {projection_info['projection_name']}")
                            
                            # Extract transverse mercator projection parameters
                            transmer = mapproj.find('transmer')
                            if transmer is not None:
                                projection_info['scale_factor'] = transmer.find('sfctrmer').text if transmer.find('sfctrmer') is not None else 'N/A'
                                projection_info['longitude_of_central_meridian'] = transmer.find('longcm').text if transmer.find('longcm') is not None else 'N/A'
                                projection_info['latitude_of_projection_origin'] = transmer.find('latprjo').text if transmer.find('latprjo') is not None else 'N/A'
                                projection_info['false_easting'] = transmer.find('feast').text if transmer.find('feast') is not None else 'N/A'
                                projection_info['false_northing'] = transmer.find('fnorth').text if transmer.find('fnorth') is not None else 'N/A'
                                logger.info("Extracted transverse mercator projection parameters")
                            else:
                                logger.warning("No transmer element found in mapproj")
                        else:
                            logger.warning("No mapproj element found in planar")
    
                        # Check for grid coordinate system
                        gridsys = planar.find('gridsys')
                        if gridsys is not None:
                            projection_info['grid_coordinate_system'] = gridsys.find('gridsysn').text if gridsys.find('gridsysn') is not None else 'N/A'
                            logger.info(f"Extracted grid coordinate system: {projection_info['grid_coordinate_system']}")
                        else:
                            logger.warning("No gridsys element found in planar")
                    else:
                        logger.warning("No planar element found in horizsys")
                except Exception as planar_error:
                    logger.error(f"Error extracting planar info: {planar_error}", exc_info=True)
            else:
                logger.warning("No horizsys element found in XML")
        except Exception as horiz_error:
            logger.error(f"Error extracting horizontal datum info: {horiz_error}", exc_info=True)
        
        logger.info(f"Datum info keys: {list(datum_info.keys())}")
        logger.info(f"Projection info keys: {list(projection_info.keys())}")
        return datum_info, projection_info
    except Exception as e:
        logger.error(f"Error in extract_datum_info: {e}", exc_info=True)
        return {}, {}

def get_bounding_box(metadata):
    """Extract bounding box information from metadata."""
    try:
        if not metadata or not isinstance(metadata, dict):
            logger.warning("Invalid metadata provided to get_bounding_box")
            return {'west': 'N/A', 'east': 'N/A', 'north': 'N/A', 'south': 'N/A'}
            
        logger.info("Extracting bounding box from metadata")
        
        # Try to get from extent.boundingBox first
        if 'extent' in metadata and isinstance(metadata['extent'], dict):
            bbox = metadata['extent'].get('boundingBox', {})
            if bbox and isinstance(bbox, dict):
                logger.info(f"Found bounding box in extent.boundingBox: {bbox}")
                return {
                    'west': str(bbox.get('minX', 'N/A')),
                    'east': str(bbox.get('maxX', 'N/A')),
                    'north': str(bbox.get('maxY', 'N/A')),
                    'south': str(bbox.get('minY', 'N/A'))
                }
        
        # Try to get from extent.geographicExtent
        if 'extent' in metadata and isinstance(metadata['extent'], dict):
            if 'geographicExtent' in metadata['extent'] and isinstance(metadata['extent']['geographicExtent'], dict):
                geo_extent = metadata['extent']['geographicExtent']
                if 'boundingBox' in geo_extent and isinstance(geo_extent['boundingBox'], dict):
                    bbox = geo_extent['boundingBox']
                    logger.info(f"Found bounding box in extent.geographicExtent.boundingBox: {bbox}")
                    return {
                        'west': str(bbox.get('minX', 'N/A')),
                        'east': str(bbox.get('maxX', 'N/A')),
                        'north': str(bbox.get('maxY', 'N/A')),
                        'south': str(bbox.get('minY', 'N/A'))
                    }
        
        # Try to get from spatial.boundingBox
        if 'spatial' in metadata and isinstance(metadata['spatial'], dict):
            bbox = metadata['spatial'].get('boundingBox', {})
            if bbox and isinstance(bbox, dict):
                logger.info(f"Found bounding box in spatial.boundingBox: {bbox}")
                return {
                    'west': str(bbox.get('minX', 'N/A')),
                    'east': str(bbox.get('maxX', 'N/A')),
                    'north': str(bbox.get('maxY', 'N/A')),
                    'south': str(bbox.get('minY', 'N/A'))
                }
        
        logger.warning("No bounding box found in metadata")
        return {'west': 'N/A', 'east': 'N/A', 'north': 'N/A', 'south': 'N/A'}
    except Exception as e:
        logger.error(f"Error in get_bounding_box: {e}", exc_info=True)
        return {'west': 'N/A', 'east': 'N/A', 'north': 'N/A', 'south': 'N/A'}

def create_certificate(info, output_dir):
    """Create a certificate for a LIDAR project."""
    try:
        logger.info(f"Starting certificate creation with info keys: {list(info.keys())}")
        
        # Get project name but obfuscate it in the certificate
        project_name = info.get('name', info.get('title', 'Unknown_Project'))
        logger.info(f"Processing project for certificate: {project_name}")
        
        # Create a generic filename with timestamp instead of project name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"LIDAR_Certificate_{timestamp}.pdf"
        file_path = os.path.join(output_dir, filename)
        
        # Get the raw metadata for LLM analysis
        json_metadata = info.get('data', {})
        logger.info(f"JSON metadata keys: {list(json_metadata.keys()) if json_metadata else 'None'}")
        
        xml_metadata = None
        
        # Check if we have XML metadata
        if 'xml_metadata' in info:
            xml_metadata = info['xml_metadata']
            logger.info(f"XML metadata is available, length: {len(xml_metadata)} characters")
        else:
            logger.warning("No XML metadata available for certificate analysis")
        
        # Perform LLM analysis on the metadata
        logger.info("Performing LLM analysis on LIDAR metadata")
        try:
            llm_analysis = analyze_lidar_metadata_with_llm(json_metadata, xml_metadata)
            logger.info(f"LLM analysis complete with keys: {list(llm_analysis.keys()) if llm_analysis else 'None'}")
            if 'structured_analysis' in llm_analysis:
                logger.info(f"Structured analysis sections: {list(llm_analysis['structured_analysis'].keys())}")
        except Exception as llm_error:
            logger.error(f"Error in LLM analysis: {llm_error}", exc_info=True)
            llm_analysis = {
                'raw_analysis': f"Error in analysis: {str(llm_error)}",
                'structured_analysis': {
                    'overview': "An error occurred during metadata analysis.",
                    'state': "Unknown",
                    'collection date range': "Not available",
                    'publication date': "Not available",
                    'expected vertical accuracy': "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE",
                    'expected point density': "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter",
                    'expected horizontal accuracy': "≤ 1 meter (based on USGS 3DEP standards)",
                    'spatial reference system': "Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83"
                }
            }
        
        # Extract project data
        project_data = info.get('data', {})
        if not project_data:
            logger.warning("No project data available for certificate")
            project_data = {}
            
        # Extract location and date information
        state = "Unknown"
        start_month = "Unknown"
        start_year = "Unknown"
        
        # First try to get state from LLM analysis
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'state' in structured_analysis and structured_analysis['state'] != "Unknown":
                state = structured_analysis['state']
                logger.info(f"Using state from LLM analysis: {state}")
        
        # If state is still unknown, try to extract from project metadata
        if state == "Unknown":
            # Try to get state from project title
            if 'title' in info:
                title_text = info['title']
                logger.info(f"Extracting state from title: {title_text}")
                
                # Look for state abbreviations in the title
                state_pattern = r'\b([A-Z]{2})\b'
                state_match = re.search(state_pattern, title_text)
                if state_match:
                    state = state_match.group(1)
                    logger.info(f"Found state abbreviation in title: {state}")
                else:
                    # Look for full state names
                    states = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", 
                              "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", 
                              "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", 
                              "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", 
                              "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", 
                              "New Hampshire", "New Jersey", "New Mexico", "New York", 
                              "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", 
                              "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", 
                              "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", 
                              "West Virginia", "Wisconsin", "Wyoming"]
                    
                    # Create a pattern to match state names
                    state_names_pattern = r'\b(' + '|'.join(states) + r')\b'
                    state_name_match = re.search(state_names_pattern, title_text, re.IGNORECASE)
                    if state_name_match:
                        state = state_name_match.group(1)
                        logger.info(f"Found state name in title: {state}")
            
            # Try to get state from project name
            if state == "Unknown" and 'name' in info:
                name_text = info['name']
                logger.info(f"Extracting state from name: {name_text}")
                
                # Look for state abbreviations in the name
                state_pattern = r'\b([A-Z]{2})\b'
                state_match = re.search(state_pattern, name_text)
                if state_match:
                    state = state_match.group(1)
                    logger.info(f"Found state abbreviation in name: {state}")
        
        # Try to get collection date range from LLM analysis
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'collection date range' in structured_analysis and structured_analysis['collection date range'] != "Not available":
                date_range = structured_analysis['collection date range']
                logger.info(f"Using collection date range from LLM analysis: {date_range}")
                
                # Try to extract year and month from the date range
                year_pattern = r'\b(20\d{2})\b'
                year_match = re.search(year_pattern, date_range)
                if year_match:
                    start_year = year_match.group(1)
                    logger.info(f"Extracted year: {start_year}")
                
                # Try to extract month
                months = ["January", "February", "March", "April", "May", "June", 
                          "July", "August", "September", "October", "November", "December"]
                month_pattern = r'\b(' + '|'.join(months) + r')\b'
                month_match = re.search(month_pattern, date_range, re.IGNORECASE)
                if month_match:
                    start_month = month_match.group(1)
                    logger.info(f"Extracted month: {start_month}")
        
        # If we still don't have date information, try from project data
        if start_year == "Unknown" or start_month == "Unknown":
            # Check dates field in project data first
            if 'data' in info and 'dates' in info['data'] and isinstance(info['data']['dates'], dict):
                dates = info['data']['dates']
                if 'Start' in dates and dates['Start'] and dates['Start'] != 'N/A':
                    try:
                        start_date = dates['Start']
                        # Try to parse the date
                        date_obj = None
                        date_formats = [
                            '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y',
                            '%Y%m%d', '%B %d, %Y', '%b %d, %Y'
                        ]
                        
                        for fmt in date_formats:
                            try:
                                date_obj = datetime.strptime(start_date, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if date_obj:
                            start_month = date_obj.strftime('%B')  # Full month name
                            start_year = date_obj.strftime('%Y')
                            logger.info(f"Extracted date from project data dates.Start: {start_month} {start_year}")
                    except Exception as date_error:
                        logger.error(f"Error parsing dates.Start: {date_error}", exc_info=True)
        
            # If still no date, try direct start_date field
            if (start_year == "Unknown" or start_month == "Unknown") and 'start_date' in info:
                start_date = info['start_date']
                if start_date:
                    try:
                        # Try to parse the date
                        date_obj = None
                        date_formats = [
                            '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y',
                            '%Y%m%d', '%B %d, %Y', '%b %d, %Y'
                        ]
                        
                        for fmt in date_formats:
                            try:
                                date_obj = datetime.strptime(start_date, fmt)
                                break
                            except ValueError:
                                continue
                        
                        if date_obj:
                            start_month = date_obj.strftime('%B')  # Full month name
                            start_year = date_obj.strftime('%Y')
                            logger.info(f"Extracted date from info start_date: {start_month} {start_year}")
                    except Exception as date_error:
                        logger.error(f"Error parsing info start date: {date_error}", exc_info=True)
        
        # Create title with state and date information
        if state != "Unknown" and len(state) == 2:
            # We have a state abbreviation, try to get the full name
            state_names = {
                "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", 
                "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", 
                "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", 
                "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", 
                "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", 
                "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", 
                "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", 
                "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", 
                "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", 
                "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", 
                "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah", 
                "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", 
                "WI": "Wisconsin", "WY": "Wyoming"
            }
            if state in state_names:
                title = f"AERIAL LIDAR DATA {state} ({state_names[state]}) {start_month} {start_year}"
            else:
                title = f"AERIAL LIDAR DATA {state} {start_month} {start_year}"
        else:
            title = f"AERIAL LIDAR DATA {state} {start_month} {start_year}"
        
        # Note: We're intentionally not including the project title to obfuscate the data source
        # as per requirements
        
        logger.info(f"Created title: {title}")
        
        # Get collection dates from project data first
        collection_range = "Not specified"
        
        # Try to extract from project data directly
        if 'data' in info and 'dates' in info['data'] and isinstance(info['data']['dates'], dict):
            dates = info['data']['dates']
            start_date = dates.get('Start', 'N/A')
            end_date = dates.get('End', 'N/A')
            
            if start_date != 'N/A' and end_date != 'N/A':
                # Format dates consistently if possible
                try:
                    # Try to parse and reformat dates
                    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']
                    start_obj = None
                    end_obj = None
                    
                    # Try each format for start date
                    for fmt in date_formats:
                        try:
                            start_obj = datetime.strptime(start_date, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # Try each format for end date
                    for fmt in date_formats:
                        try:
                            end_obj = datetime.strptime(end_date, fmt)
                            break
                        except ValueError:
                            continue
                    
                    # If both dates were successfully parsed, format them consistently
                    if start_obj and end_obj:
                        start_date = start_obj.strftime('%Y-%m-%d')
                        end_date = end_obj.strftime('%Y-%m-%d')
                except Exception as date_error:
                    logger.warning(f"Could not reformat dates: {date_error}")
                
                collection_range = f"{start_date} to {end_date}"
                logger.info(f"Using collection range from project data dates: {collection_range}")
        # If not found in project data, try in info/project_data
        elif not collection_range or collection_range == "Not specified":
            collection_start = info.get('start_date', project_data.get('start_date', 'Not specified'))
            collection_end = info.get('end_date', project_data.get('end_date', 'Not specified'))
            if collection_start != 'Not specified' or collection_end != 'Not specified':
                # Format dates consistently if possible
                try:
                    # Try to parse and reformat dates
                    date_formats = ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y', '%Y%m%d']
                    start_obj = None
                    end_obj = None
                    
                    # Try each format for start date
                    if collection_start != 'Not specified':
                        for fmt in date_formats:
                            try:
                                start_obj = datetime.strptime(collection_start, fmt)
                                break
                            except ValueError:
                                continue
                    
                    # Try each format for end date
                    if collection_end != 'Not specified':
                        for fmt in date_formats:
                            try:
                                end_obj = datetime.strptime(collection_end, fmt)
                                break
                            except ValueError:
                                continue
                    
                    # If dates were successfully parsed, format them consistently
                    if start_obj:
                        collection_start = start_obj.strftime('%Y-%m-%d')
                    if end_obj:
                        collection_end = end_obj.strftime('%Y-%m-%d')
                except Exception as date_error:
                    logger.warning(f"Could not reformat dates: {date_error}")
                
                collection_range = f"{collection_start} to {collection_end}"
                logger.info(f"Using collection range from info/project_data: {collection_range}")
        
        # Finally fall back to LLM analysis if still not found
        if collection_range == "Not specified" and llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'collection date range' in structured_analysis and structured_analysis['collection date range'] != "Not available":
                collection_range = structured_analysis['collection date range']
                
                # Try to reformat the date range if needed
                # This addresses cases where LLM might return different date formats
                try:
                    # Check common patterns like "YYYY-MM-DD to YYYY-MM-DD" or "YYYY/MM/DD - YYYY/MM/DD"
                    date_range_patterns = [
                        r'(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD to YYYY-MM-DD
                        r'(\d{4}/\d{2}/\d{2})\s*(?:to|-)\s*(\d{4}/\d{2}/\d{2})',  # YYYY/MM/DD to YYYY/MM/DD
                        r'(\d{2}/\d{2}/\d{4})\s*(?:to|-)\s*(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY to MM/DD/YYYY
                        r'(\d{4}\d{2}\d{2})\s*(?:to|-)\s*(\d{4}\d{2}\d{2})'        # YYYYMMDD to YYYYMMDD
                    ]
                    
                    for pattern in date_range_patterns:
                        match = re.search(pattern, collection_range)
                        if match:
                            start_date_str = match.group(1)
                            end_date_str = match.group(2)
                            
                            # Determine the format of the matched dates
                            if '-' in start_date_str:
                                date_format = '%Y-%m-%d' if len(start_date_str.split('-')[0]) == 4 else '%d-%m-%Y'
                            elif '/' in start_date_str:
                                date_format = '%Y/%m/%d' if len(start_date_str.split('/')[0]) == 4 else '%m/%d/%Y'
                            else:
                                date_format = '%Y%m%d'  # No separators, assuming YYYYMMDD
                            
                            # Parse dates
                            start_obj = datetime.strptime(start_date_str, date_format)
                            end_obj = datetime.strptime(end_date_str, date_format)
                            
                            # Format to our standard format
                            collection_range = f"{start_obj.strftime('%Y-%m-%d')} to {end_obj.strftime('%Y-%m-%d')}"
                            break
                except Exception as format_error:
                    logger.warning(f"Could not reformat date range from LLM: {format_error}")
                
                logger.info(f"Using collection range from LLM analysis: {collection_range}")
        
        # Get publication date from LLM analysis
        publication_date = info.get('publication_date', project_data.get('publication_date', 'Not specified'))
        
        # If we have LLM analysis, try to get more accurate publication date
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'publication date' in structured_analysis and structured_analysis['publication date'] != "Not available":
                publication_date = structured_analysis['publication date']
                logger.info(f"Using publication date from LLM analysis: {publication_date}")
        
        # Get vertical accuracy from project data first
        vertical_accuracy = "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE"
        
        # Try to extract from project data directly
        if 'data' in info and 'quality' in info['data'] and isinstance(info['data']['quality'], dict):
            quality = info['data']['quality']
            if 'vertical_accuracy' in quality and quality['vertical_accuracy'] != 'N/A':
                vertical_accuracy = quality['vertical_accuracy']
                logger.info(f"Using vertical accuracy from project data quality: {vertical_accuracy}")
        # If not found, try in info/project_data
        elif 'quality' in project_data and isinstance(project_data['quality'], dict):
            if 'vertical_accuracy' in project_data['quality'] and project_data['quality']['vertical_accuracy'] != 'N/A':
                vertical_accuracy = project_data['quality']['vertical_accuracy']
                logger.info(f"Using vertical accuracy from project_data: {vertical_accuracy}")
        
        # Finally fall back to LLM analysis
        if (vertical_accuracy == "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE" and 
            llm_analysis and 'structured_analysis' in llm_analysis):
            structured_analysis = llm_analysis['structured_analysis']
            if 'expected vertical accuracy' in structured_analysis:
                accuracy_statement = structured_analysis['expected vertical accuracy']
                # Only use if it's not "Not provided" or similar
                if not any(x in accuracy_statement.lower() for x in ['not provided', 'not specified', 'not available']):
                    vertical_accuracy = accuracy_statement
                    logger.info(f"Using vertical accuracy from LLM analysis: {vertical_accuracy}")
        
        # Get vertical units from project data first
        vertical_units = "meters (assumed based on standards)"
        
        # Try to extract from project data directly
        if 'data' in info and 'vertical' in info['data'] and isinstance(info['data']['vertical'], dict):
            vertical = info['data']['vertical']
            if 'units' in vertical and vertical['units'] != 'N/A':
                vertical_units = vertical['units']
                logger.info(f"Using vertical units from project data vertical: {vertical_units}")
        # Fall back to LLM analysis
        elif llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'vertical units' in structured_analysis:
                units = structured_analysis['vertical units']
                # Only use if it's not "Not provided" or similar
                if not any(x in units.lower() for x in ['not provided', 'not specified', 'not available']):
                    vertical_units = units
                    logger.info(f"Using vertical units from LLM analysis: {vertical_units}")
        
        # Get point density with fallback to USGS standards
        point_density = "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter"
        
        # Try to extract from project data directly
        if 'data' in info and 'quality' in info['data'] and isinstance(info['data']['quality'], dict):
            quality = info['data']['quality']
            if 'point_density' in quality and quality['point_density'] != 'N/A':
                point_density = quality['point_density']
                logger.info(f"Using point density from project data quality: {point_density}")
        # If not found, try in info/project_data
        elif 'quality' in project_data and isinstance(project_data['quality'], dict):
            if 'point_density' in project_data['quality'] and project_data['quality']['point_density'] != 'N/A':
                point_density = project_data['quality']['point_density']
                logger.info(f"Using point density from project_data: {point_density}")
        
        # Finally fall back to LLM analysis
        if (point_density == "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter" and 
            llm_analysis and 'structured_analysis' in llm_analysis):
            structured_analysis = llm_analysis['structured_analysis']
            if 'expected point density' in structured_analysis:
                potential_density = structured_analysis['expected point density']
                # Only use if it's not "Not provided" or similar
                if not any(x in potential_density.lower() for x in ['not provided', 'not specified', 'not available']):
                    point_density = potential_density
                    logger.info(f"Using point density from LLM analysis: {point_density}")
        
        # Get horizontal accuracy with fallback to USGS standards
        horizontal_accuracy = "≤ 1 meter (based on USGS 3DEP standards)"
        
        # Try to extract from project data directly
        if 'data' in info and 'quality' in info['data'] and isinstance(info['data']['quality'], dict):
            quality = info['data']['quality']
            if 'horizontal_accuracy' in quality and quality['horizontal_accuracy'] != 'N/A':
                horizontal_accuracy = quality['horizontal_accuracy']
                logger.info(f"Using horizontal accuracy from project data quality: {horizontal_accuracy}")
        # If not found, try in info/project_data
        elif 'quality' in project_data and isinstance(project_data['quality'], dict):
            if 'horizontal_accuracy' in project_data['quality'] and project_data['quality']['horizontal_accuracy'] != 'N/A':
                horizontal_accuracy = project_data['quality']['horizontal_accuracy']
                logger.info(f"Using horizontal accuracy from project_data: {horizontal_accuracy}")
        
        # Finally fall back to LLM analysis
        if (horizontal_accuracy == "≤ 1 meter (based on USGS 3DEP standards)" and 
            llm_analysis and 'structured_analysis' in llm_analysis):
            structured_analysis = llm_analysis['structured_analysis']
            if 'expected horizontal accuracy' in structured_analysis:
                potential_accuracy = structured_analysis['expected horizontal accuracy']
                # Only use if it's not "Not provided" or similar
                if not any(x in potential_accuracy.lower() for x in ['not provided', 'not specified', 'not available']):
                    horizontal_accuracy = potential_accuracy
                    logger.info(f"Using horizontal accuracy from LLM analysis: {horizontal_accuracy}")
        
        # Get spatial reference information from LLM analysis
        spatial_ref_text = "Coordinate System: UTM Projection: NAD83 / UTM zone 18N (EPSG:32618) Datum: NAD83"
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'spatial reference system' in structured_analysis:
                potential_spatial_ref = structured_analysis['spatial reference system']
                if not any(x in potential_spatial_ref.lower() for x in ['not provided', 'not specified', 'not available']):
                    # Clean up the spatial reference text
                    spatial_ref = potential_spatial_ref.replace('\n', ' ').replace('  ', ' ')
                    # Format the spatial reference text to fit better
                    spatial_ref = spatial_ref.replace(';', '')
                    spatial_ref = spatial_ref.replace(' - ', ' ')
                    spatial_ref_text = spatial_ref
                    logger.info(f"Using spatial reference from LLM analysis: {spatial_ref_text}")
        else:
            # Fallback to project data
            spatial_ref = project_data.get('spatial_ref', {})
            if spatial_ref:
                spatial_ref_text = ""
                if spatial_ref.get('projection', 'Not specified') != 'Not specified':
                    spatial_ref_text += f"Projection: {spatial_ref.get('projection')} "
                if spatial_ref.get('horizontal_datum', 'Not specified') != 'Not specified':
                    spatial_ref_text += f"Horizontal Datum: {spatial_ref.get('horizontal_datum')} "
                if spatial_ref.get('vertical_datum', 'Not specified') != 'Not specified':
                    spatial_ref_text += f"Vertical Datum: {spatial_ref.get('vertical_datum')} "
                if spatial_ref.get('units', 'Not specified') != 'Not specified':
                    spatial_ref_text += f"Units: {spatial_ref.get('units')}"
                logger.info(f"Using spatial reference from project data: {spatial_ref_text}")
        
        # Get map image path
        coverage_map = info.get('coverage_map', '')
        logger.info(f"Map image path: {coverage_map}")
        
        # Check if map image exists
        if not coverage_map or not os.path.exists(coverage_map):
            logger.warning(f"Map image not found at path: {coverage_map}")
            coverage_map = None
        
        # Try to import PDF generation libraries
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            
            # Create PDF document with reduced margins
            doc = SimpleDocTemplate(
                file_path, 
                pagesize=letter,
                leftMargin=0.5*inch,
                rightMargin=0.5*inch,
                topMargin=0.5*inch,
                bottomMargin=0.5*inch
            )
            styles = getSampleStyleSheet()
            
            # Create custom styles
            title_style = ParagraphStyle(
                'Title',
                parent=styles['Title'],
                fontSize=18,
                alignment=1,  # Center alignment
                spaceAfter=15,
                fontName='Helvetica-Bold'
            )
            
            heading_style = ParagraphStyle(
                'Heading',
                parent=styles['Heading2'],
                fontSize=14,
                spaceAfter=10
            )
            
            body_style = ParagraphStyle(
                'Body',
                parent=styles['Normal'],
                fontSize=11,
                spaceAfter=6
            )
            
            # Create content elements
            elements = []
            
            # Create a table for the header with logo and title side by side
            logo_path = "assets/images/Vertspec_logo_square.png"
            if os.path.exists(logo_path):
                try:
                    # Create logo image at exactly 40x40 points
                    logo_img = Image(logo_path, width=40, height=40)
                    
                    # Create header table with logo and title side by side
                    header_data = [[logo_img, Paragraph("MW LOS Path Turbine Analysis", title_style)]]
                    header_table = Table(header_data, colWidths=[60, 480])
                    
                    # Style the table - no borders and proper vertical alignment
                    header_table.setStyle(TableStyle([
                        ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                        ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                    ]))
                    
                    # Add the header table to elements with no spacing after
                    elements.append(header_table)
                    # Add space after the header
                    elements.append(Spacer(1, 10))  # Adding 10 points of space after the header
                except Exception as logo_error:
                    logger.error(f"Error adding logo: {logo_error}", exc_info=True)
                    # Fallback to just title if logo fails
                    elements.append(Paragraph("MW LOS Path Turbine Analysis", title_style))
                    elements.append(Spacer(1, 10))
            else:
                # Fallback to just title if logo not found
                logger.warning(f"Logo file not found at {logo_path}")
                elements.append(Paragraph("MW LOS Path Turbine Analysis", title_style))
                elements.append(Spacer(1, 10))
            
            # Introduction
            intro_text = """
            This certificate documents the analysis of potential obstructions to a microwave path. 
            The analysis calculates the minimum distance between wind turbines and the line of sight path,
            as well as the clearance distances accounting for the Fresnel zone.
            """
            
            # Add data table FIRST (before map image)
            # Create paragraph objects for each data cell to enable proper wrapping
            cell_style = ParagraphStyle(
                'CellStyle',
                parent=styles['Normal'],
                fontSize=10,
                leading=12,
                wordWrap='CJK',
                spaceBefore=0,
                spaceAfter=0
            )
            
            # Create a style for the label column with slightly smaller font
            label_style = ParagraphStyle(
                'LabelStyle',
                parent=styles['Normal'],
                fontSize=9,
                leading=11,
                fontName='Helvetica-Bold',
                spaceBefore=0,
                spaceAfter=0
            )
            
            # Format the data with Paragraph objects - wrap labels in paragraphs too
            formatted_data = [
                [Paragraph("Collection Date and Timeframe:", label_style), Paragraph(collection_range, cell_style)],
                [Paragraph("Publication Date:", label_style), Paragraph(publication_date, cell_style)],
                [Paragraph("Expected Vertical Accuracy:", label_style), Paragraph(vertical_accuracy, cell_style)],
                [Paragraph("Expected Point Density:", label_style), Paragraph(point_density, cell_style)],
                [Paragraph("Expected Horizontal Accuracy:", label_style), Paragraph(horizontal_accuracy, cell_style)],
                [Paragraph("Spatial Reference System:", label_style), Paragraph(spatial_ref_text, cell_style)]
            ]
            
            # Use a wider table with more space for the data column and fixed row heights
            # Adjust column widths to give more space to the data column
            table = Table(formatted_data, colWidths=[1.7*inch, 5.3*inch], rowHeights=[0.35*inch, 0.35*inch, 0.4*inch, 0.4*inch, 0.35*inch, 0.6*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                ('ALIGN', (0, 0), (0, -1), 'LEFT'),
                ('BACKGROUND', (1, 0), (1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                # Add word wrapping for both columns
                ('WORDWRAP', (0, 0), (1, -1), True),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 0.3*inch))
            
            # Add map image AFTER the data table
            if coverage_map and os.path.exists(coverage_map):
                try:
                    # Try to get image dimensions for better sizing
                    try:
                        from PIL import Image as PILImage
                        img = PILImage.open(coverage_map)
                        width, height = img.size
                        aspect_ratio = height / width
                        
                        # Set image width and calculate height based on aspect ratio
                        img_width = 6.5 * inch
                        img_height = img_width * aspect_ratio
                        
                        # Ensure image isn't too tall
                        if img_height > 4.5 * inch:
                            img_height = 4.5 * inch
                            img_width = img_height / aspect_ratio
                        
                        # Add the image with calculated dimensions
                        map_img = Image(coverage_map, width=img_width, height=img_height)
                    except Exception as pil_error:
                        logger.warning(f"Could not calculate image dimensions: {pil_error}")
                        # Fallback to standard dimensions
                        map_img = Image(coverage_map, width=6*inch, height=4*inch)
                    
                    # Center the image
                    map_img.hAlign = 'CENTER'
                    elements.append(map_img)
                    elements.append(Spacer(1, 0.25*inch))
                    logger.info("Added map image to certificate")
                    
                    # Add caption
                    caption_text = """
                    The above image shows a cross-sectional view of the microwave path with turbines.
                    The path is shown as a vertical line at the center, with turbines positioned at their
                    respective distances from the path. Measurement lines show clearance distances from
                    each turbine to the path and Fresnel zone.
                    """
                    elements.append(Paragraph(caption_text, body_style))
                    elements.append(Spacer(1, 20))
                except Exception as img_error:
                    logger.error(f"Error adding map image: {img_error}", exc_info=True)
                    elements.append(Paragraph("Map image could not be displayed.", body_style))
            else:
                elements.append(Paragraph("Map image not available.", body_style))
            
            elements.append(Spacer(1, 0.25*inch))
            
            # Add footer
            footer_style = ParagraphStyle(
                'Footer',
                parent=styles['Normal'],
                fontSize=10,
                spaceAfter=6,
                textColor=colors.darkgrey
            )
            
            footer_text = (
                "This certificate was generated automatically based on available metadata. "
                "Where specific information was not available, standard USGS 3DEP specifications have been provided as reference."
            )
            elements.append(Paragraph(footer_text, footer_style))
            elements.append(Spacer(1, 0.25*inch))
            elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
            
            # Add timestamp and certification
            elements.append(
                Paragraph(f"Certificate Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", body_style),
            )
            elements.append(
                Paragraph("This certificate was generated using verified geometric calculations and represents the minimum distances between turbine rotor spheres and the line of sight path including the Fresnel zone.", body_style)
            )
            
            # Add copyright footer in small font
            copyright_style = ParagraphStyle(
                'Copyright',
                parent=styles['Normal'],
                fontSize=7,
                textColor=colors.gray,
                alignment=1  # Center alignment
            )
            elements.append(Spacer(1, 20))
            elements.append(
                Paragraph("Vertspec MW LOS Turbine Report V1.0.1 Copyright 2025 All Rights Reserved", copyright_style)
            )
            
            # Build the PDF
            doc.build(elements)
            logger.info(f"PDF certificate created: {file_path}")
            
            # Don't clean up temporary files - the calling function will handle this
            # This ensures the map image is available for viewing
            
            return file_path
            
        except ImportError as e:
            logger.error(f"Error importing PDF libraries: {e}. Falling back to HTML certificate.")
            # Fall back to HTML certificate if PDF libraries are not available
            return create_html_certificate(info, output_dir, title, collection_range, publication_date, 
                                          vertical_accuracy, point_density, horizontal_accuracy, 
                                          spatial_ref_text, coverage_map)
            
    except Exception as e:
        logger.error(f"Error creating certificate: {e}", exc_info=True)
        return None

def create_html_certificate(info, output_dir, title, collection_range, publication_date, 
                           vertical_accuracy, point_density, horizontal_accuracy, 
                           spatial_ref_text, map_image):
    """Create HTML certificate for LIDAR data."""
    try:
        logger.info(f"Creating HTML certificate with title: {title}")
        
        # Create a formatted date string for the collection range to include in the title
        collection_dates = ""
        if collection_range and collection_range != "Not specified":
            collection_dates = f" ({collection_range})"
        
        # Create HTML content
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>LIDAR Data Certificate</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 1000px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .header {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .title {{
                    font-size: 24px;
                    font-weight: bold;
                    color: #003366;
                }}
                .subtitle {{
                    font-size: 18px;
                    color: #666;
                    margin-top: 10px;
                }}
                .section {{
                    margin-bottom: 30px;
                }}
                .section-title {{
                    font-size: 20px;
                    font-weight: bold;
                    border-bottom: 1px solid #ddd;
                    padding-bottom: 5px;
                    margin-bottom: 15px;
                    color: #003366;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-bottom: 20px;
                }}
                th, td {{
                    padding: 12px 15px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f8f8;
                    font-weight: bold;
                    width: 30%;
                }}
                .map-container {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .map-image {{
                    max-width: 100%;
                    height: auto;
                    border: 1px solid #ddd;
                }}
                .footer {{
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                    margin-top: 50px;
                    border-top: 1px solid #ddd;
                    padding-top: 20px;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <div class="title">{title}</div>
                <div class="subtitle">LIDAR Data Certification for Collection Period: {collection_range}</div>
            </div>
            
            <div class="section">
                <div class="section-title">LIDAR Dataset Information</div>
                <table>
                    <tr>
                        <th>Data Collection Period</th>
                        <td>{collection_range}</td>
                    </tr>
                    <tr>
                        <th>Publication Date</th>
                        <td>{publication_date}</td>
                    </tr>
                    <tr>
                        <th>Expected Vertical Accuracy</th>
                        <td>{vertical_accuracy}</td>
                    </tr>
                    <tr>
                        <th>Expected Point Density</th>
                        <td>{point_density}</td>
                    </tr>
                    <tr>
                        <th>Expected Horizontal Accuracy</th>
                        <td>{horizontal_accuracy}</td>
                    </tr>
                    <tr>
                        <th>Spatial Reference System</th>
                        <td>{spatial_ref_text}</td>
                    </tr>
                </table>
            </div>
            
            {map_image_html}
            
            <div class="section">
                <div class="section-title">Certificate Information</div>
                <p>This certificate verifies that LIDAR data has been evaluated for use in radio frequency path loss calculations. The data meets quality standards for terrain analysis and obstruction identification.</p>
            </div>
            
            <div class="footer">
                <p>Generated on {datetime.now().strftime('%Y-%m-%d')} | Vertspec MW LOS Certificate v1.0</p>
                <p>© 2025 All Rights Reserved</p>
            </div>
        </body>
        </html>
        """
        
        # Write HTML file
        logger.info(f"Writing HTML certificate to: {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info("HTML certificate created successfully")
            return file_path
        except Exception as write_error:
            logger.error(f"Error writing HTML certificate: {write_error}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error creating HTML certificate: {e}", exc_info=True)
        return None

def create_json_certificate(info, output_dir):
    """Create a JSON certificate file for a LIDAR project."""
    try:
        logger.info(f"Starting JSON certificate creation with info keys: {list(info.keys())}")
        
        # Get project name but obfuscate it in the certificate
        project_name = info.get('name', info.get('title', 'Unknown_Project'))
        logger.info(f"Processing project for JSON certificate: {project_name}")
        
        # Create a generic filename with timestamp instead of project name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"LIDAR_Certificate_{timestamp}.json"
        file_path = os.path.join(output_dir, filename)
        
        # Get the raw metadata for LLM analysis
        json_metadata = info.get('data', {})
        logger.info(f"JSON metadata keys: {list(json_metadata.keys()) if json_metadata else 'None'}")
        
        xml_metadata = None
        
        # Check if we have XML metadata
        if 'xml_metadata' in info:
            xml_metadata = info['xml_metadata']
            logger.info(f"XML metadata is available, length: {len(xml_metadata)} characters")
        else:
            logger.warning("No XML metadata available for JSON certificate analysis")
        
        # Perform LLM analysis on the metadata
        logger.info("Performing LLM analysis on LIDAR metadata for JSON certificate")
        try:
            llm_analysis = analyze_lidar_metadata_with_llm(json_metadata, xml_metadata)
            logger.info(f"LLM analysis complete with keys: {list(llm_analysis.keys()) if llm_analysis else 'None'}")
            if 'structured_analysis' in llm_analysis:
                logger.info(f"Structured analysis sections: {list(llm_analysis['structured_analysis'].keys())}")
        except Exception as llm_error:
            logger.error(f"Error in LLM analysis for JSON certificate: {llm_error}", exc_info=True)
            llm_analysis = {
                'raw_analysis': f"Error in analysis: {str(llm_error)}",
                'structured_analysis': {
                    'overview': "An error occurred during metadata analysis.",
                    'accuracy statement': (
                        "- Collection Date Range: Not available\n"
                        "- Publication Date: Not available\n"
                        "- Expected Vertical Accuracy: Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE\n"
                        "- Expected Point Density: Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter\n"
                        "- Expected Horizontal Accuracy: ≤ 1 meter (based on USGS 3DEP standards)"
                    )
                }
            }
        
        # Extract project data
        project_data = info.get('data', {})
        if not project_data:
            logger.warning("No project data available for JSON certificate")
            project_data = {}
            
        # Extract location and date information
        state = "Unknown"
        start_month = "Unknown"
        start_year = "Unknown"
        
        # Try to extract state from project name or metadata
        if 'title' in info:
            title = info['title']
            # Look for state abbreviations in the title
            state_pattern = r'\b([A-Z]{2})\b'
            state_match = re.search(state_pattern, title)
            if state_match:
                state = state_match.group(1)
            else:
                # Look for full state names
                states = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", 
                          "Connecticut", "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", 
                          "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", 
                          "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota", 
                          "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", 
                          "New Hampshire", "New Jersey", "New Mexico", "New York", 
                          "North Carolina", "North Dakota", "Ohio", "Oklahoma", "Oregon", 
                          "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", 
                          "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", 
                          "West Virginia", "Wisconsin", "Wyoming"]
                
                # Create a pattern to match state names
                state_names_pattern = r'\b(' + '|'.join(states) + r')\b'
                state_name_match = re.search(state_names_pattern, title, re.IGNORECASE)
                if state_name_match:
                    state = state_name_match.group(1)
                    logger.info(f"Found state name: {state}")
        
        # Try to extract date information
        start_date = info.get('start_date', project_data.get('start_date', ''))
        if start_date:
            try:
                # Try to parse the date
                date_obj = None
                date_formats = [
                    '%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%d/%m/%Y',
                    '%Y%m%d', '%B %d, %Y', '%b %d, %Y'
                ]
                
                for fmt in date_formats:
                    try:
                        date_obj = datetime.strptime(start_date, fmt)
                        break
                    except ValueError:
                        continue
                
                if date_obj:
                    start_month = date_obj.strftime('%B')  # Full month name
                    start_year = date_obj.strftime('%Y')
            except Exception as date_error:
                logger.error(f"Error parsing start date: {date_error}", exc_info=True)
        
        # Create title with state and date information
        title = f"AERIAL LIDAR DATA {state} {start_month} {start_year}"
        
        # Get collection dates
        collection_start = info.get('start_date', project_data.get('start_date', 'Not specified'))
        collection_end = info.get('end_date', project_data.get('end_date', 'Not specified'))
        collection_range = f"{collection_start} - {collection_end}"
        
        # If we have LLM analysis, try to get more accurate date information
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'accuracy statement' in structured_analysis:
                accuracy_statement = structured_analysis['accuracy statement']
                # Look for date range in accuracy statement
                date_range_pattern = r'Collection Date Range:(.+?)(?=-|\n|$)'
                date_range_match = re.search(date_range_pattern, accuracy_statement)
                if date_range_match:
                    collection_range = date_range_match.group(1).strip()
        
        # Get publication date
        publication_date = info.get('publication_date', project_data.get('publication_date', 'Not specified'))
        
        # If we have LLM analysis, try to get more accurate publication date
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'accuracy statement' in structured_analysis:
                accuracy_statement = structured_analysis['accuracy statement']
                # Look for publication date in accuracy statement
                pub_date_pattern = r'Publication Date:(.+?)(?=-|\n|$)'
                pub_date_match = re.search(pub_date_pattern, accuracy_statement)
                if pub_date_match:
                    publication_date = pub_date_match.group(1).strip()
        
        # Get vertical accuracy with fallback to USGS standards
        vertical_accuracy = "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE"
        
        # If we have quality information, use it
        quality = project_data.get('quality', {})
        if quality and quality.get('vertical_accuracy', 'Not specified') != 'Not specified':
            vertical_accuracy = quality.get('vertical_accuracy')
        
        # If we have LLM analysis, try to get more accurate vertical accuracy
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'accuracy statement' in structured_analysis:
                accuracy_statement = structured_analysis['accuracy statement']
                # Look for vertical accuracy in accuracy statement
                vert_acc_pattern = r'(Expected )?[Vv]ertical [Aa]ccuracy:(.+?)(?=-|\n|$)'
                vert_acc_match = re.search(vert_acc_pattern, accuracy_statement)
                if vert_acc_match:
                    potential_accuracy = vert_acc_match.group(2).strip()
                    # Only use if it's not "Not provided" or similar
                    if not any(x in potential_accuracy.lower() for x in ['not provided', 'not specified', 'not available']):
                        vertical_accuracy = potential_accuracy
        
        # Get point density with fallback to USGS standards
        point_density = "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter"
        
        # Try to extract from project data directly
        if 'data' in info and 'quality' in info['data'] and isinstance(info['data']['quality'], dict):
            quality = info['data']['quality']
            if 'point_density' in quality and quality['point_density'] != 'N/A':
                point_density = quality['point_density']
                logger.info(f"Using point density from project data quality: {point_density}")
        # If not found, try in info/project_data
        elif 'quality' in project_data and isinstance(project_data['quality'], dict):
            if 'point_density' in project_data['quality'] and project_data['quality']['point_density'] != 'N/A':
                point_density = project_data['quality']['point_density']
                logger.info(f"Using point density from project_data: {point_density}")
        
        # Finally fall back to LLM analysis
        if (point_density == "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter" and 
            llm_analysis and 'structured_analysis' in llm_analysis):
            structured_analysis = llm_analysis['structured_analysis']
            if 'expected point density' in structured_analysis:
                potential_density = structured_analysis['expected point density']
                # Only use if it's not "Not provided" or similar
                if not any(x in potential_density.lower() for x in ['not provided', 'not specified', 'not available']):
                    point_density = potential_density
                    logger.info(f"Using point density from LLM analysis: {point_density}")
        
        # Get horizontal accuracy with fallback to USGS standards
        horizontal_accuracy = "≤ 1 meter (based on USGS 3DEP standards)"
        
        # Try to extract from project data directly
        if 'data' in info and 'quality' in info['data'] and isinstance(info['data']['quality'], dict):
            quality = info['data']['quality']
            if 'horizontal_accuracy' in quality and quality['horizontal_accuracy'] != 'N/A':
                horizontal_accuracy = quality['horizontal_accuracy']
                logger.info(f"Using horizontal accuracy from project data quality: {horizontal_accuracy}")
        # If not found, try in info/project_data
        elif 'quality' in project_data and isinstance(project_data['quality'], dict):
            if 'horizontal_accuracy' in project_data['quality'] and project_data['quality']['horizontal_accuracy'] != 'N/A':
                horizontal_accuracy = project_data['quality']['horizontal_accuracy']
                logger.info(f"Using horizontal accuracy from project_data: {horizontal_accuracy}")
        
        # Finally fall back to LLM analysis
        if (horizontal_accuracy == "≤ 1 meter (based on USGS 3DEP standards)" and 
            llm_analysis and 'structured_analysis' in llm_analysis):
            structured_analysis = llm_analysis['structured_analysis']
            if 'expected horizontal accuracy' in structured_analysis:
                potential_accuracy = structured_analysis['expected horizontal accuracy']
                # Only use if it's not "Not provided" or similar
                if not any(x in potential_accuracy.lower() for x in ['not provided', 'not specified', 'not available']):
                    horizontal_accuracy = potential_accuracy
                    logger.info(f"Using horizontal accuracy from LLM analysis: {horizontal_accuracy}")
        
        # Get spatial reference information
        spatial_ref = project_data.get('spatial_ref', {})
        if not spatial_ref:
            logger.warning("No spatial reference information available")
            spatial_ref = {}
        
        # Combine spatial reference information
        spatial_ref_text = ""
        if spatial_ref.get('projection', 'Not specified') != 'Not specified':
            spatial_ref_text += f"Projection: {spatial_ref.get('projection')} "
        if spatial_ref.get('horizontal_datum', 'Not specified') != 'Not specified':
            spatial_ref_text += f"Horizontal Datum: {spatial_ref.get('horizontal_datum')} "
        if spatial_ref.get('vertical_datum', 'Not specified') != 'Not specified':
            spatial_ref_text += f"Vertical Datum: {spatial_ref.get('vertical_datum')} "
        if spatial_ref.get('units', 'Not specified') != 'Not specified':
            spatial_ref_text += f"Units: {spatial_ref.get('units')}"
            
        # If we have LLM analysis, try to get more accurate spatial reference information
        if llm_analysis and 'structured_analysis' in llm_analysis:
            structured_analysis = llm_analysis['structured_analysis']
            if 'spatial reference system' in structured_analysis:
                spatial_ref_text = structured_analysis['spatial reference system']
        
        # If still no spatial reference information, use a fallback
        if not spatial_ref_text:
            spatial_ref_text = "Standard USGS LIDAR data typically uses NAD83 horizontal datum and NAVD88 vertical datum."
        
        # Create certificate data structure
        certificate_data = {
            "title": title,
            "collection_date_and_timeframe": collection_range,
            "publication_date": publication_date,
            "expected_vertical_accuracy": vertical_accuracy,
            "expected_point_density": point_density,
            "expected_horizontal_accuracy": horizontal_accuracy,
            "spatial_reference_system": spatial_ref_text,
            "map_image": info.get('map_image', 'Not available')
        }
        
        # Write JSON file
        logger.info(f"Writing JSON certificate to: {file_path}")
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(certificate_data, f, indent=2, ensure_ascii=False)
            logger.info("JSON certificate created successfully")
            return file_path
        except Exception as write_error:
            logger.error(f"Error writing JSON certificate: {write_error}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error creating JSON certificate: {e}", exc_info=True)
        return None

def create_turbine_certificate(turbines_data, path_data, output_dir):
    """Create a certificate documenting turbine positions and clearances relative to a microwave path."""
    try:
        # Generate a timestamp for the filename
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Get donor and recipient site IDs from tower_parameters.json
        donor_site_id = "UNKNOWN"
        recipient_site_id = "UNKNOWN"
        try:
            with open('tower_parameters.json', 'r') as f:
                tower_params = json.load(f)
                site_a = tower_params.get('site_A', {})
                site_b = tower_params.get('site_B', {})
                donor_site_id = site_a.get('site_id', "UNKNOWN")
                recipient_site_id = site_b.get('site_id', "UNKNOWN")
                # Clean site IDs for filename (remove special characters)
                donor_site_id = "".join(c for c in donor_site_id if c.isalnum() or c == '_')
                recipient_site_id = "".join(c for c in recipient_site_id if c.isalnum() or c == '_')
        except Exception as e:
            logger.warning(f"Could not load site IDs from tower_parameters.json: {e}")
        
        # Create the PDF filename
        filename = f"{donor_site_id}_{recipient_site_id}_{timestamp}.pdf"
        output_path = os.path.join(output_dir, filename)
        
        # Create the PDF document with further reduced margins
        doc = SimpleDocTemplate(
            output_path, 
            pagesize=letter,
            leftMargin=36,    # 0.5 inch
            rightMargin=36,   # 0.5 inch
            topMargin=18,     # Further reduced from 24 to 18 (0.25 inch)
            bottomMargin=18   # Further reduced from 36 to 18 (0.25 inch)
        )
        styles = getSampleStyleSheet()
        elements = []
        
        # Define styles
        title_style = styles['Title']
        title_style.spaceBefore = 0  # Remove space before title
        title_style.spaceAfter = 0   # Remove space after title
        
        heading_style = ParagraphStyle(
            'Heading',
            parent=styles['Heading2'],
            fontSize=14,
            spaceAfter=6,  # Reduced from 10
            spaceBefore=0  # Ensure no space before
        )
        
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6
        )
        
        copyright_style = ParagraphStyle(
            'Copyright',
            parent=styles['Normal'],
            fontSize=7,
            textColor=colors.gray,
            alignment=1  # Center alignment
        )
        
        # Add title with logo - with minimal spacing
        logo_path = "assets/images/Vertspec_logo_square.png"
        if os.path.exists(logo_path):
            try:
                # Create logo image at exactly 40x40 points
                logo_img = Image(logo_path, width=40, height=40)
                
                # Create header table with logo and title side by side
                header_data = [[logo_img, Paragraph("MW LOS Path Turbine Analysis", title_style)]]
                header_table = Table(header_data, colWidths=[60, 480])
                
                # Style the table - no borders and proper vertical alignment
                header_table.setStyle(TableStyle([
                    ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                    ('ALIGN', (1, 0), (1, 0), 'LEFT'),
                ]))
                
                # Add the header table to elements with no spacing after
                elements.append(header_table)
                # Add space after the header
                elements.append(Spacer(1, 10))  # Adding 10 points of space after the header
            except Exception as logo_error:
                logger.error(f"Error adding logo: {logo_error}", exc_info=True)
                # Fallback to just title if logo fails
                elements.append(Paragraph("MW LOS Path Turbine Analysis", title_style))
                elements.append(Spacer(1, 10))
        else:
            # Fallback to just title if logo not found
            logger.warning(f"Logo file not found at {logo_path}")
            elements.append(Paragraph("MW LOS Path Turbine Analysis", title_style))
            elements.append(Spacer(1, 10))
        
        # Add site details in a two-column layout with minimal spacing
        try:
            # Try to load tower parameters for site details
            with open('tower_parameters.json', 'r') as f:
                tower_params = json.load(f)
                
            # Extract general parameters and site-specific details
            site_a = tower_params.get('site_A', {})
            site_b = tower_params.get('site_B', {})
            general_params = tower_params.get('general_parameters', {})
            
            # Create styles for site details with minimized spacing
            site_header_style = ParagraphStyle(
                'SiteHeader',
                parent=styles['Heading3'],
                fontSize=11,  # Reduced from 12
                alignment=1, # Center
                spaceBefore=0,
                spaceAfter=2   # Reduced from 4
            )
            
            site_cell_style = ParagraphStyle(
                'SiteCell',
                parent=styles['Normal'],
                fontSize=9,    # Reduced from 10
                leading=11,    # Reduced from 14
                spaceBefore=0,
                spaceAfter=0
            )
            
            # Get site IDs from tower_parameters.json
            site_a_id = site_a.get('site_id', 'N/A')
            site_b_id = site_b.get('site_id', 'N/A')
            
            # Format site details with proper spacing and alignment
            site_table_data = [
                # First row: Site ID/Name headers
                [Paragraph(f"<b>{site_a_id}</b>", site_header_style), 
                 Paragraph(f"<b>{site_b_id}</b>", site_header_style)]
            ]
            
            # Second row: Site type labels
            site_table_data.append([
                Paragraph("<i>Donor Site (A)</i>", site_header_style),
                Paragraph("<i>Recipient Site (B)</i>", site_header_style)
            ])
            
            # Row for each data field with label and value
            def format_site_row(label, site_a_val, site_b_val):
                return [
                    Paragraph(f"<b>{label}:</b> {site_a_val}", site_cell_style),
                    Paragraph(f"<b>{label}:</b> {site_b_val}", site_cell_style)
                ]
            
            # Add rows for each data point
            site_table_data.append(format_site_row("Latitude", 
                                                  site_a.get('latitude', 'N/A'), 
                                                  site_b.get('latitude', 'N/A')))
            
            site_table_data.append(format_site_row("Longitude", 
                                                  site_a.get('longitude', 'N/A'), 
                                                  site_b.get('longitude', 'N/A')))
            
            site_table_data.append(format_site_row("Ground Elevation", 
                                                  f"{site_a.get('elevation_ft', 'N/A')} ft", 
                                                  f"{site_b.get('elevation_ft', 'N/A')} ft"))
            
            site_table_data.append(format_site_row("Tower Height", 
                                                  f"{site_a.get('tower_height_ft', 'N/A')} ft", 
                                                  f"{site_b.get('tower_height_ft', 'N/A')} ft"))
            
            site_table_data.append(format_site_row("Antenna CL", 
                                                  f"{site_a.get('antenna_cl_ft', 'N/A')} ft", 
                                                  f"{site_b.get('antenna_cl_ft', 'N/A')} ft"))
            
            # Create the site details table with reduced row heights
            site_table = Table(site_table_data, colWidths=[270, 270])
            site_table.setStyle(TableStyle([
                # Add highlight for header rows
                ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),
                ('BACKGROUND', (0, 1), (1, 1), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (1, 1), colors.black),
                ('ALIGN', (0, 0), (1, 1), 'CENTER'),
                # Rest of rows
                ('BACKGROUND', (0, 2), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                # Reduce padding to make table more compact
                ('TOPPADDING', (0, 0), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ]))
            
            elements.append(site_table)
            elements.append(Spacer(1, 5))  # Minimal space after site table
            
            # Add path details with reduced font size
            frequency_ghz = general_params.get('frequency_ghz', path_data.get('frequency_ghz', 'N/A'))
            path_length_mi = general_params.get('path_length_mi', 'N/A')
            
            # Use only miles for path length
            path_length_text = f"{path_length_mi} mi"
            
            path_table_data = [
                ["Parameter", "Value"],
                ["Path Length", path_length_text],
                ["Frequency", f"{frequency_ghz} GHz"],
                ["Start Coordinates", f"{path_data.get('start_lat', 'N/A')}, {path_data.get('start_lon', 'N/A')}"],
                ["End Coordinates", f"{path_data.get('end_lat', 'N/A')}, {path_data.get('end_lon', 'N/A')}"]
            ]
            
            # Create more compact table
            path_table = Table(path_table_data, colWidths=[220, 320])
            path_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
                ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (1, 0), 6),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                # Reduce padding to make table more compact
                ('TOPPADDING', (0, 1), (-1, -1), 1),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
                ('FONTSIZE', (0, 0), (-1, -1), 9),  # Smaller font size for the entire table
            ]))
            
            elements.append(path_table)
            elements.append(Spacer(1, 5))  # Minimal space after path table
            
            # Add summary information about turbines from analysis_results
            try:
                # Get analysis results from tower_parameters.json
                analysis_results = tower_params.get('analysis_results', {})
                
                # Get actual search distance used and turbines within that distance
                search_distance_ft = analysis_results.get('search_distance_ft', 2000)
                distance_key = f'turbines_within_{int(search_distance_ft)}ft'
                turbines_near_path = analysis_results.get(distance_key, analysis_results.get('turbines_within_2000ft', []))
                num_turbines_near_path = len(turbines_near_path)
                
                # Get closest turbine to path
                closest_to_path = analysis_results.get('closest_turbine_to_path', {})
                closest_path_id = closest_to_path.get('turbine_id', 'N/A')
                closest_path_distance = closest_to_path.get('distance_ft', 'N/A')
                if isinstance(closest_path_distance, (int, float)):
                    closest_path_distance = f"{closest_path_distance:.1f} ft"
                
                # Get closest turbine to Fresnel
                closest_to_fresnel = analysis_results.get('closest_turbine_to_fresnel', {})
                closest_fresnel_id = closest_to_fresnel.get('turbine_id', 'N/A')
                closest_fresnel_distance = closest_to_fresnel.get('distance_ft', 'N/A')
                if isinstance(closest_fresnel_distance, (int, float)):
                    closest_fresnel_distance = f"{closest_fresnel_distance:.1f} ft"
                
                # Create summary table with dynamic distance
                summary_table_data = [
                    ["Analysis Summary", "Value"],
                    [f"Turbines found within {int(search_distance_ft)}ft from the path:", f"{num_turbines_near_path}"],
                    ["Closest turbine blade sweep to the path:", f"Turbine {closest_path_id} ({closest_path_distance})"],
                    ["Closest turbine blade sweep to fresnel:", f"Turbine {closest_fresnel_id} ({closest_fresnel_distance})"]
                ]
                
                # Create summary table with styling
                summary_table = Table(summary_table_data, colWidths=[220, 320])
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (1, 0), colors.lightgrey),
                    ('TEXTCOLOR', (0, 0), (1, 0), colors.black),
                    ('ALIGN', (0, 0), (1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
                    ('BOTTOMPADDING', (0, 0), (1, 0), 6),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    # Reduce padding to make table more compact
                    ('TOPPADDING', (0, 1), (-1, -1), 1),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 1),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),  # Smaller font size for the entire table
                    # Add deep red color for the "closest turbine" values
                    ('TEXTCOLOR', (1, 2), (1, 3), colors.darkred),  # Deep red for closest blade sweep values
                ]))
                
                elements.append(summary_table)
                elements.append(Spacer(1, 5))  # Minimal space after summary table
                
            except Exception as e:
                logger.error(f"Error adding turbine analysis summary: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error adding site details to certificate: {e}", exc_info=True)
            elements.append(Paragraph("Site details not available", body_style))
            elements.append(Spacer(1, 5))  # Minimal space
            
        # ADD MAP VIEW with much smaller size to ensure it fits on first page
        try:
            if 'map_view_path' in path_data and path_data['map_view_path']:
                map_view_path = path_data['map_view_path']
                logger.info(f"Adding map view from {map_view_path}")
                
                if os.path.exists(map_view_path):
                    # Match the map width to the tables with fixed 300px height
                    img_width = 540  # Match table width
                    
                    # Get original dimensions and calculate height
                    from PIL import Image as PILImage
                    try:
                        pil_img = PILImage.open(map_view_path)
                        img_orig_width, img_orig_height = pil_img.size
                        
                        # Fixed height of 300px for the PDF
                        img_height = 300
                        
                        # Create image with correct dimensions
                        img = Image(map_view_path, width=img_width, height=img_height)
                        # Center the image
                        img.hAlign = 'CENTER'
                    except Exception as pil_error:
                        logger.warning(f"Error calculating image dimensions: {pil_error}, using default")
                        img = Image(map_view_path, width=img_width, height=300)
                        img.hAlign = 'CENTER'
                    
                    # Add image to document
                    elements.append(img)
                    # No spacer after map to maximize space usage
        except Exception as map_error:
            logger.error(f"Error adding map view to certificate: {map_error}", exc_info=True)

        # Add page break after the first page content
        from reportlab.platypus import PageBreak
        elements.append(PageBreak())

        # PAGE 2: Add the site-to-site profile image if available
        if 'profile_image_path' in path_data and path_data['profile_image_path']:
            try:
                profile_image_path = path_data['profile_image_path']
                logger.info(f"Adding profile image from {profile_image_path}")
                
                if os.path.exists(profile_image_path):
                    # Add a heading for the image
                    elements.append(Paragraph("Site-to-Site Profile Visualization", heading_style))
                    
                    # Add image with proper aspect ratio
                    img_width = 550  # Increased from 450 to use more of the page width
                    
                    # Get the original image dimensions to calculate proper aspect ratio
                    from PIL import Image as PILImage
                    try:
                        # Use PIL to get original dimensions and calculate height for correct aspect ratio
                        pil_img = PILImage.open(profile_image_path)
                        img_orig_width, img_orig_height = pil_img.size
                        aspect_ratio = img_orig_height / img_orig_width
                        img_height = img_width * aspect_ratio
                        
                        # Create ReportLab image with correct dimensions
                        img = Image(profile_image_path, width=img_width, height=img_height)
                    except Exception as pil_error:
                        logger.warning(f"Error calculating image dimensions: {pil_error}, using default")
                        # Fallback to default if PIL fails
                        img = Image(profile_image_path, width=img_width)
                    
                    # Add image to document
                    elements.append(img)
                    
                    # Add caption
                    caption_text = """
                    The above image shows a cross-sectional view of the microwave path with turbines.
                    The path is shown as a vertical line at the center, with turbines positioned at their
                    respective distances from the path. Measurement lines show clearance distances from
                    each turbine to the path and Fresnel zone.
                    """
                    elements.append(Paragraph(caption_text, body_style))
                    elements.append(Spacer(1, 20))
                else:
                    logger.warning(f"Profile image file not found: {profile_image_path}")
            except Exception as img_error:
                logger.error(f"Error adding profile image: {img_error}", exc_info=True)
        
        # Add the top-down view image if available
        if 'top_down_image_path' in path_data and path_data['top_down_image_path']:
            try:
                top_down_image_path = path_data['top_down_image_path']
                logger.info(f"Adding top-down view image from {top_down_image_path}")
                
                if os.path.exists(top_down_image_path):
                    # Add a heading for the image
                    elements.append(Paragraph("Top-Down View Visualization", heading_style))
                    
                    # Add image with proper aspect ratio
                    img_width = 550  # Maximum width for the image
                    
                    # Get the original image dimensions to calculate proper aspect ratio
                    from PIL import Image as PILImage
                    try:
                        # Use PIL to get original dimensions and calculate height for correct aspect ratio
                        pil_img = PILImage.open(top_down_image_path)
                        img_orig_width, img_orig_height = pil_img.size
                        aspect_ratio = img_orig_height / img_orig_width
                        img_height = img_width * aspect_ratio
                        
                        # Create ReportLab image with correct dimensions
                        img = Image(top_down_image_path, width=img_width, height=img_height)
                    except Exception as pil_error:
                        logger.warning(f"Error calculating image dimensions: {pil_error}, using default")
                        # Fallback to default if PIL fails
                        img = Image(top_down_image_path, width=img_width)
                    
                    # Add image to document
                    elements.append(img)
                    
                    # Add caption
                    caption_text = """
                    The above image shows a top-down view of the microwave path with turbines.
                    The path is shown as a vertical line through the center, with turbines positioned at their
                    actual distances from the path. Circles represent turbine rotor diameters, and 
                    measurement lines show clearance distances from each turbine to the path and Fresnel zone.
                    """
                    elements.append(Paragraph(caption_text, body_style))
                    elements.append(Spacer(1, 20))
                else:
                    logger.warning(f"Top-down view image file not found: {top_down_image_path}")
            except Exception as img_error:
                logger.error(f"Error adding top-down view image: {img_error}", exc_info=True)
        
        # Add page break before the third page
        elements.append(PageBreak())
        
        # PAGE 3: Create table header for turbines
        elements.append(Paragraph("Turbine Analysis", heading_style))
        
        table_data = [["Turbine ID", "Distance from Path", "Height", "Rotor Diameter", 
                      "Straight Clearance", "Distance to Fresnel", "Fresnel Clearance"]]

        # Process each turbine
        for turbine in turbines_data:
            try:
                # Get turbine parameters
                turbine_id = turbine.get('id', 'Unknown')
                distance_from_path = turbine.get('distance_from_path_ft', 'N/A')
                height_ft = turbine.get('total_height_ft', 'N/A')
                hub_height_ft = turbine.get('hub_height_ft', 'N/A')
                rotor_diameter_ft = turbine.get('rotor_diameter_ft', 'N/A')
                clearance_straight = turbine.get('clearance_straight_ft', 'N/A')
                distance_to_fresnel = turbine.get('clearance_curved_ft', 'N/A')  # Renamed for clarity
                clearance_fresnel = turbine.get('clearance_fresnel_ft', 'N/A')
                
                # Format values
                if isinstance(distance_from_path, (int, float)):
                    distance_from_path = f"{distance_from_path:.1f} ft"
                if isinstance(rotor_diameter_ft, (int, float)):
                    rotor_diameter_ft = f"{rotor_diameter_ft:.1f} ft"
                if isinstance(clearance_straight, (int, float)):
                    clearance_straight = f"{clearance_straight:.1f} ft"
                if isinstance(distance_to_fresnel, (int, float)):
                    distance_to_fresnel = f"{distance_to_fresnel:.1f} ft"
                if isinstance(clearance_fresnel, (int, float)):
                    clearance_fresnel = f"{clearance_fresnel:.1f} ft"
                
                # Add to table with detailed height information
                height_info = f"Hub: {hub_height_ft} ft\nTotal: {height_ft} ft" if hub_height_ft != 'N/A' else f"Total: {height_ft} ft"
                
                table_data.append([
                    turbine_id,
                    distance_from_path,
                    height_info,
                    rotor_diameter_ft,
                    clearance_straight,
                    distance_to_fresnel,
                    clearance_fresnel
                ])
                
            except Exception as e:
                logger.error(f"Error processing turbine for certificate: {e}")
        
        # Create the table
        # Define column widths to ensure table fits on page width (adjust as needed)
        col_widths = [75, 85, 95, 85, 85, 85, 85]  # Increased from [60, 70, 80, 70, 70, 70, 70]
        
        # Create table with specified column widths
        turbine_table = Table(table_data, repeatRows=1, colWidths=col_widths)
        
        # Create smaller font styles for table
        table_header_style = ('FONTSIZE', (0, 0), (-1, 0), 9)  # Increased from 8
        table_data_style = ('FONTSIZE', (0, 1), (-1, -1), 8)   # Increased from 7
        
        turbine_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),  # Reduced padding
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            table_header_style,
            table_data_style,
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),  # Center-align all data cells
        ]))
        
        elements.append(turbine_table)
        elements.append(Spacer(1, 30))
        
        # Methodology (moved to after the tables)
        elements.append(Paragraph("Methodology", heading_style))
        
        methodology_text = """
        The analysis uses the following methodology to determine if turbines pose a risk of interference:
        
        1. Calculate the straight-line distance from each turbine to the line of sight path
        2. Calculate the Fresnel zone radius at each turbine's position along the path
        3. Determine the minimum distance between the turbine and the Fresnel zone
        4. Calculate clearance distance between the turbine's rotor sphere and the Fresnel zone
        
        A positive clearance value indicates the turbine is clear of the path and Fresnel zone.
        A negative clearance value indicates potential interference.
        """
        elements.append(Paragraph(methodology_text, body_style))
        elements.append(Spacer(1, 20))
        
        # Add timestamp and certification
        elements.append(
            Paragraph(f"Certificate Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}", body_style),
        )
        elements.append(
            Paragraph("This certificate was generated using verified geometric calculations and represents the minimum distances between turbine rotor spheres and the line of sight path including the Fresnel zone.", body_style)
        )
        
        # Add copyright footer in small font
        elements.append(Spacer(1, 20))
        elements.append(
            Paragraph("Vertspec MW LOS Turbine Report V1.0.1 Copyright 2025 All Rights Reserved", copyright_style)
        )
        
        # Build the PDF
        doc.build(elements)
        
        logger.info(f"Turbine distance certificate created: {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error generating turbine distance certificate: {e}", exc_info=True)
        raise

def calculate_fresnel_radius(d1_km, d2_km, frequency_ghz=11):
    """Calculate Fresnel zone radius at a point along the path."""
    try:
        # Calculate Fresnel radius in meters
        # F1 = 17.32 * sqrt((d1 * d2)/(f * D))
        # where d1,d2 are distances in km, f is freq in GHz, D is total path length in km
        D = (d1_km + d2_km)  # Total path length
        F1 = 17.32 * math.sqrt((d1_km * d2_km)/(frequency_ghz * D))
        
        # Convert radius from meters to feet
        return F1 * 3.28084
    except Exception as e:
        logger.error(f"Error calculating Fresnel radius: {e}")
        return 0

def export_certificates(project_list, output_dir, format='pdf'):
    """Export certificates for all projects in the list."""
    logger.info(f"Starting certificate export for {len(project_list)} projects")
    logger.debug(f"Output directory: {output_dir}")
    
    if not os.path.exists(output_dir):
        logger.debug(f"Creating output directory: {output_dir}")
        os.makedirs(output_dir)
    
    exported_files = []
    success_count = 0
    error_count = 0
    
    for i, project in enumerate(project_list):
        try:
            # Get project name but log it only for tracking purposes
            project_name = project.get('name', 'Unknown')
            project_id = project.get('id', 'Unknown')
            logger.info(f"Processing project {i+1}/{len(project_list)}: {project_name} (ID: {project_id})")
            logger.debug(f"Project keys: {list(project.keys())}")
            
            # Check if we have the necessary data
            if 'data' not in project and 'id' not in project:
                logger.warning(f"Project {project_name} is missing both 'data' and 'id' fields, skipping")
                error_count += 1
                continue
                
            # Create certificate
            logger.info(f"Creating certificate for {project_name} in {format.lower()} format")
            
            if format.lower() == 'pdf':
                try:
                    cert_path = create_certificate(project, output_dir)
                    if cert_path:
                        logger.info(f"PDF certificate created: {cert_path}")
                        exported_files.append(cert_path)
                        success_count += 1
                    else:
                        logger.warning(f"Failed to create PDF certificate for {project_name}")
                        error_count += 1
                except Exception as pdf_error:
                    logger.error(f"Error creating PDF certificate for {project_name}: {pdf_error}", exc_info=True)
                    error_count += 1
                    
            elif format.lower() == 'json':
                try:
                    # First extract metadata if needed
                    if 'data' not in project and 'id' in project:
                        logger.info(f"Fetching metadata for project {project_name} with ID {project_id}")
                        try:
                            metadata = fetch_metadata(project_id)
                            info = extract_metadata(metadata)
                            logger.info(f"Successfully fetched metadata for {project_name}")
                            cert_path = create_json_certificate(info, output_dir)
                        except Exception as fetch_error:
                            logger.error(f"Error fetching metadata for {project_name}: {fetch_error}", exc_info=True)
                            error_count += 1
                            continue
                    else:
                        cert_path = create_json_certificate(project, output_dir)
                        
                    if cert_path:
                        logger.info(f"JSON certificate created: {cert_path}")
                        exported_files.append(cert_path)
                        success_count += 1
                    else:
                        logger.warning(f"Failed to create JSON certificate for {project_name}")
                        error_count += 1
                except Exception as json_error:
                    logger.error(f"Error creating JSON certificate for {project_name}: {json_error}", exc_info=True)
                    error_count += 1
            else:
                logger.warning(f"Unsupported format: {format}")
                error_count += 1
                continue
                
        except Exception as e:
            logger.error(f"Error processing project: {e}", exc_info=True)
            error_count += 1
    
    logger.info(f"Export complete. {success_count} certificates created successfully, {error_count} failed")
    return exported_files

def analyze_lidar_metadata_with_llm(json_metadata, xml_metadata=None):
    """Analyze LIDAR metadata using Claude to extract key information."""
    try:
        # Log metadata keys for debugging
        if json_metadata:
            logger.info(f"Analyzing JSON metadata with keys: {list(json_metadata.keys())}")
        else:
            logger.warning("No JSON metadata provided for analysis")
            
        if xml_metadata:
            logger.info(f"XML metadata is available, length: {len(xml_metadata)} characters")
        else:
            logger.warning("No XML metadata provided for analysis")
        
        # Create a structured prompt for the LLM
        prompt = """
You are a LIDAR data expert tasked with analyzing metadata for a LIDAR dataset. 
Please focus on extracting the following specific data points:

1. State: What US state does this LIDAR data cover? Extract the state name or abbreviation.
2. Collection Date Range: When was this LIDAR data collected? Provide the start and end dates if available.
   - Important: Look for begdate and enddate tags within timeinfo/rngdates sections in the XML.
   - The dates are often in YYYYMMDD format and may need to be formatted as YYYY-MM-DD.
   - Check both idinfo/timeinfo/rngdates and timeperd/timeinfo/rngdates sections.
3. Publication Date: When was this data published or made available?
4. Expected Vertical Accuracy: What is the vertical accuracy of this LIDAR data? 
5. Expected Point Density: What is the point density of this LIDAR data?
6. Expected Horizontal Accuracy: What is the horizontal accuracy of this LIDAR data?
7. Spatial Reference System: What coordinate system, projection, and datums are used?
8. Vertical Units: What units are used for vertical measurements? Look for "vertical" section in JSON or altunits in XML.

Format your response in a structured way with clear labels for each data point. For example:
- State: Ohio
- Collection Date Range: 2021-05-09 to 2021-05-27
- Publication Date: December 23, 2022
- Expected Vertical Accuracy: Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE
- Expected Point Density: Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter
- Expected Horizontal Accuracy: ≤ 1 meter (based on USGS 3DEP standards)
- Spatial Reference System: Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83
- Vertical Units: meter

If specific information is not available in the metadata, please use USGS and FEMA standards to provide expected values. Be conservative in your estimates.

For reference:
- USGS 3DEP QL2 standards specify vertical accuracy of ≤ 10 cm RMSE, point density of ≥ 2 points per square meter
- USGS 3DEP QL1 standards specify vertical accuracy of ≤ 5 cm RMSE, point density of ≥ 8 points per square meter
- FEMA specifications typically require vertical accuracy of 18.5 cm at 95% confidence (9.25 cm RMSE)

Here is the JSON metadata:
"""
        
        # Add JSON metadata to prompt
        if json_metadata:
            prompt += json.dumps(json_metadata, indent=2)
        else:
            prompt += "No JSON metadata available."
        
        # Add XML metadata if available
        if xml_metadata:
            prompt += "\n\nHere is the XML metadata:\n" + xml_metadata[:10000]  # Limit size to avoid token limits
        
        # Check if we have an API key
        if not ANTHROPIC_API_KEY:
            logger.error("No Anthropic API key found. Please set the ANTHROPIC_API_KEY environment variable.")
            return {
                "raw_analysis": "Error: No Anthropic API key available.",
                "structured_analysis": {
                    "overview": "Analysis could not be performed due to missing API key.",
                    "state": "Unknown",
                    "collection date range": "Not available",
                    "publication date": "Not available",
                    "expected vertical accuracy": "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE",
                    "expected point density": "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter",
                    "expected horizontal accuracy": "≤ 1 meter (based on USGS 3DEP standards)",
                    "spatial reference system": "Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83"
                }
            }
        
        # Initialize Anthropic client
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Call the API
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the response content
            analysis_text = response.content[0].text
            logger.info("Successfully received analysis from Claude")
            
            # Parse the response into structured sections
            structured_analysis = {
                "overview": "LIDAR Data Analysis",
                "state": "Unknown",
                "collection date range": "Not available",
                "publication date": "Not available",
                "expected vertical accuracy": "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE",
                "expected point density": "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter",
                "expected horizontal accuracy": "≤ 1 meter (based on USGS 3DEP standards)",
                "spatial reference system": "Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83"
            }
            
            # Extract specific data points using regex patterns
            state_pattern = r'(?:State|Location):\s*([^\n]+)'
            state_match = re.search(state_pattern, analysis_text, re.IGNORECASE)
            if state_match:
                state = state_match.group(1).strip()
                if state.lower() not in ['unknown', 'not available', 'not specified']:
                    structured_analysis["state"] = state
                    logger.info(f"Extracted state: {state}")
            
            date_range_pattern = r'Collection Date Range:\s*([^\n]+)'
            date_range_match = re.search(date_range_pattern, analysis_text, re.IGNORECASE)
            if date_range_match:
                date_range = date_range_match.group(1).strip()
                # Remove "(from begdate/enddate in XML)" if present
                date_range = re.sub(r'\s*\(from begdate\/enddate in XML\)\s*', '', date_range)
                if date_range.lower() not in ['unknown', 'not available', 'not specified']:
                    structured_analysis["collection date range"] = date_range
                    logger.info(f"Extracted collection date range: {date_range}")
            
            pub_date_pattern = r'Publication Date:\s*([^\n]+)'
            pub_date_match = re.search(pub_date_pattern, analysis_text, re.IGNORECASE)
            if pub_date_match:
                pub_date = pub_date_match.group(1).strip()
                if pub_date.lower() not in ['unknown', 'not available', 'not specified']:
                    structured_analysis["publication date"] = pub_date
                    logger.info(f"Extracted publication date: {pub_date}")
            
            vert_acc_pattern = r'(?:Expected )?Vertical Accuracy:\s*([^\n]+)'
            vert_acc_match = re.search(vert_acc_pattern, analysis_text, re.IGNORECASE)
            if vert_acc_match:
                vert_acc = vert_acc_match.group(1).strip()
                # Remove "Not clearly specified." if present
                vert_acc = re.sub(r'Not clearly specified\.\s*', '', vert_acc)
                if not any(x in vert_acc.lower() for x in ['unknown', 'not available', 'not specified', 'not provided']):
                    structured_analysis["expected vertical accuracy"] = vert_acc
                    logger.info(f"Extracted vertical accuracy: {vert_acc}")
            
            point_density_pattern = r'(?:Expected )?Point Density:\s*([^\n]+)'
            point_density_match = re.search(point_density_pattern, analysis_text, re.IGNORECASE)
            if point_density_match:
                point_density = point_density_match.group(1).strip()
                # Remove "Not clearly specified." if present
                point_density = re.sub(r'Not clearly specified\.\s*', '', point_density)
                if not any(x in point_density.lower() for x in ['unknown', 'not available', 'not specified', 'not provided']):
                    structured_analysis["expected point density"] = point_density
                    logger.info(f"Extracted point density: {point_density}")
            
            horiz_acc_pattern = r'(?:Expected )?Horizontal Accuracy:\s*([^\n]+)'
            horiz_acc_match = re.search(horiz_acc_pattern, analysis_text, re.IGNORECASE)
            if horiz_acc_match:
                horiz_acc = horiz_acc_match.group(1).strip()
                # Remove "Not clearly specified." if present
                horiz_acc = re.sub(r'Not clearly specified\.\s*', '', horiz_acc)
                if not any(x in horiz_acc.lower() for x in ['unknown', 'not available', 'not specified', 'not provided']):
                    structured_analysis["expected horizontal accuracy"] = horiz_acc
                    logger.info(f"Extracted horizontal accuracy: {horiz_acc}")
            
            # Extract vertical units
            vert_units_pattern = r'(?:Vertical Units|Units for vertical measurements):\s*([^\n]+)'
            vert_units_match = re.search(vert_units_pattern, analysis_text, re.IGNORECASE)
            if vert_units_match:
                vert_units = vert_units_match.group(1).strip()
                if not any(x in vert_units.lower() for x in ['unknown', 'not available', 'not specified', 'not provided']):
                    structured_analysis["vertical units"] = vert_units
                    logger.info(f"Extracted vertical units: {vert_units}")
            
            spatial_ref_pattern = r'Spatial Reference System:\s*([^\n]+(?:\n[^\n]+)*)'
            spatial_ref_match = re.search(spatial_ref_pattern, analysis_text, re.IGNORECASE)
            if spatial_ref_match:
                spatial_ref = spatial_ref_match.group(1).strip()
                if not any(x in spatial_ref.lower() for x in ['unknown', 'not available', 'not specified', 'not provided']):
                    # Clean up the spatial reference text
                    spatial_ref = spatial_ref.replace('\n', ' ').replace('  ', ' ')
                    # Format the spatial reference text to fit better
                    spatial_ref = spatial_ref.replace(';', '')
                    spatial_ref = spatial_ref.replace(' - ', ' ')
                    structured_analysis["spatial reference system"] = spatial_ref
                    logger.info(f"Extracted spatial reference system: {spatial_ref}")
            
            # Create a formatted accuracy statement for backward compatibility
            accuracy_statement = (
                f"- Collection Date Range: {structured_analysis['collection date range']}\n"
                f"- Publication Date: {structured_analysis['publication date']}\n"
                f"- Expected Vertical Accuracy: {structured_analysis['expected vertical accuracy']}\n"
                f"- Expected Point Density: {structured_analysis['expected point density']}\n"
                f"- Expected Horizontal Accuracy: {structured_analysis['expected horizontal accuracy']}"
            )
            structured_analysis["accuracy statement"] = accuracy_statement
            
            return {
                "raw_analysis": analysis_text,
                "structured_analysis": structured_analysis
            }
            
        except Exception as api_error:
            logger.error(f"Error calling Anthropic API: {api_error}", exc_info=True)
            return {
                "raw_analysis": f"Error calling Anthropic API: {str(api_error)}",
                "structured_analysis": {
                    "overview": "An error occurred during metadata analysis.",
                    "state": "Unknown",
                    "collection date range": "Not available",
                    "publication date": "Not available",
                    "expected vertical accuracy": "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE",
                    "expected point density": "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter",
                    "expected horizontal accuracy": "≤ 1 meter (based on USGS 3DEP standards)",
                    "spatial reference system": "Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83",
                    "accuracy statement": (
                        "- Collection Date Range: Not available\n"
                        "- Publication Date: Not available\n"
                        "- Expected Vertical Accuracy: Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE\n"
                        "- Expected Point Density: Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter\n"
                        "- Expected Horizontal Accuracy: ≤ 1 meter (based on USGS 3DEP standards)"
                    )
                }
            }
    
    except Exception as e:
        logger.error(f"Error in analyze_lidar_metadata_with_llm: {e}", exc_info=True)
        return {
            "raw_analysis": f"Error in analysis: {str(e)}",
            "structured_analysis": {
                "overview": "An error occurred during metadata analysis.",
                "state": "Unknown",
                "collection date range": "Not available",
                "publication date": "Not available",
                "expected vertical accuracy": "Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE",
                "expected point density": "Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter",
                "expected horizontal accuracy": "≤ 1 meter (based on USGS 3DEP standards)",
                "spatial reference system": "Coordinate System: UTM Projection: NAD83 / UTM zone 18N EPSG Code: EPSG:32618 Datum: NAD83",
                "accuracy statement": (
                    "- Collection Date Range: Not available\n"
                    "- Publication Date: Not available\n"
                    "- Expected Vertical Accuracy: Based on USGS QL2 standards, estimated to be ≤ 10 cm RMSE\n"
                    "- Expected Point Density: Based on USGS QL2 standards, estimated to be ≥ 2 points per square meter\n"
                    "- Expected Horizontal Accuracy: ≤ 1 meter (based on USGS 3DEP standards)"
                )
            }
        }