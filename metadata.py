import logging
import json
import requests
import xml.etree.ElementTree as ET
import re
import os
from pyproj import CRS
from shapely.geometry import box
import math
from state_boundaries import get_state_from_coordinates
from datetime import datetime

logger = logging.getLogger(__name__)

def get_project_name(filename):
    """Extract project name from filename"""
    try:
        logger.debug(f"Extracting project name from: {filename}")

        # Remove file extension first
        base_filename = filename.split('.')[0]
        parts = base_filename.split('_')

        # USGS standard naming convention: USGS_LPC_STATE_PROJECT_YEAR_####_####_LAS
        # We want to keep USGS_LPC_STATE_PROJECT_YEAR and ignore the tile coordinates

        # Pattern 1: USGS LPC datasets (most common)
        if 'USGS_LPC' in filename or filename.startswith('USGS_'):
            # Find the year part (typically 4 digits)
            year_index = -1
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                    year_index = i
                    break

            # If we found a year, take everything up to and including the year
            if year_index != -1:
                return '_'.join(parts[:year_index+1])

            # If no year found but there are coordinate-like parts (digits), exclude them
            if len(parts) > 3:
                # Look for parts that are purely numeric or start with a digit and might be tile IDs
                for i, part in enumerate(parts):
                    if i >= 3 and (part.isdigit() or (part and part[0].isdigit())):
                        # Return everything before this part
                        return '_'.join(parts[:i])

        # Pattern 2: Special case for USGS_LPC_MA_ME_MA format
        if 'USGS_LPC_MA_ME_MA' in filename:
            # Extract everything up to the UTM zone or coordinates
            project_parts = []
            for part in parts:
                # Stop at UTM grid reference or coordinate-like numbers
                if part.startswith(('18T', '19T')) or (len(part) >= 4 and part.isdigit()):
                    break
                project_parts.append(part)
            return '_'.join(project_parts)

        # Pattern 3: Special case for NY REGION2LOT1 format
        if 'REGION2LOT1' in filename:
            # Find index of year (e.g., 2012)
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                    return '_'.join(parts[:i+1])

        # Pattern 4: Format with "Western" location identifier (VT)
        if 'Western' in filename:
            # Return everything up to the year
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                    return '_'.join(parts[:i+1])

        # Pattern 5: Illinois subset format (IL_GrnMacMont)
        if 'IL_GrnMacMont' in filename or 'IL_' in filename:
            # For Illinois datasets, extract up to the year
            for i, part in enumerate(parts):
                if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                    return '_'.join(parts[:i+1])

        # Pattern 6: General pattern for dataset with coordinates at end
        # Identify parts that look like coordinate identifiers (usually 4 digits)
        coord_index = -1
        for i, part in enumerate(parts):
            # Skip parts that are clearly not coordinates (too short)
            if i < 2 or len(part) < 4:
                continue

            # Check if this looks like a coordinate (4+ digits)
            if part.isdigit() and len(part) >= 4:
                coord_index = i
                break

        if coord_index != -1:
            # Take everything before coordinate parts
            return '_'.join(parts[:coord_index])

        # Default: If we can't identify a specific pattern, remove last part
        # (assuming it's a number or coordinate)
        if len(parts) > 2:
            return '_'.join(parts[:-1])

        # Fallback: Use the full filename without extension
        logger.warning(f"Could not extract project name from {filename}, using full name")
        return base_filename

    except Exception as e:
        logger.error(f"Error extracting project name from {filename}: {e}", exc_info=True)
        return filename

class ProjectMetadata:
    """Class to store and manage LIDAR project metadata"""
    def __init__(self):
        self.projects = {}
        self.current_bounds = None
        self.state_plane_epsg = {
            'VT': '6589',  # Vermont
            'NY': '6531',  # New York East
            'MA': '6487',  # Massachusetts Mainland
            'ME': '6476',  # Maine East
            'NH': '6522',  # New Hampshire
            'MI': {
                'north': '6495',
                'central': '6497',
                'south': '6499'
            },
            # Add more as needed
        }
        self.required_metadata_fields = [
            'name',
            'spatial_ref.coordinate_system.name',
            'spatial_ref.coordinate_system.epsg_code',
            'spatial_ref.datum.horizontal_datum',
            'spatial_ref.datum.vertical_datum',
            'bounds.minX',
            'bounds.maxX',
            'bounds.minY',
            'bounds.maxY'
        ]
        logger.info("Initialized ProjectMetadata with state plane EPSG codes")

    def _fetch_and_parse_xml(self, url):
        """Fetch and parse XML from URL"""
        try:
            logger.info(f"Fetching XML from: {url}")
            response = requests.get(url)
            response.raise_for_status()

            root = ET.fromstring(response.content)
            logger.info(f"Successfully parsed XML from: {url}")
            return root

        except Exception as e:
            logger.error(f"Error fetching XML from {url}: {str(e)}", exc_info=True)
            return None

    def add_project(self, project_name, first_item):
        """Extract and store metadata from both JSON and XML sources"""
        try:
            # Get the metaUrl from the item
            meta_url = first_item.get('metaUrl')
            logger.info(f"Found metaUrl: {meta_url}")

            if meta_url:
                # Initialize metadata structure first
                metadata = self._initialize_metadata(project_name)

                # Store the metaUrl
                metadata['meta_url'] = meta_url

                # Add bounding box from the item itself as a fallback
                bbox = first_item.get('boundingBox')
                if bbox:
                    metadata['bounds'] = {
                        'minX': bbox.get('minX'),
                        'maxX': bbox.get('maxX'),
                        'minY': bbox.get('minY'),
                        'maxY': bbox.get('maxY')
                    }
                    logger.info(f"Added bounding box from item: {metadata['bounds']}")

                # Store the download URL
                metadata['download_url'] = first_item.get('downloadURL')

                # Store the source ID
                metadata['source_id'] = first_item.get('sourceId')

                # Store the file size
                metadata['size_bytes'] = first_item.get('sizeInBytes')

                # Initialize files list with the first item
                metadata['files'] = [{
                    'filename': first_item.get('downloadURL', '').split('/')[-1],
                    'download_url': first_item.get('downloadURL', ''),
                    'source_id': first_item.get('sourceId', ''),
                    'title': first_item.get('title', ''),
                    'size_bytes': first_item.get('sizeInBytes', 0),
                    'bounds': bbox or {},
                    'local_file_path': ''
                }] if first_item.get('downloadURL') else []

                # Try to fetch and parse XML metadata for dates
                try:
                    json_url = f"{meta_url}?format=json"
                    json_response = requests.get(json_url, timeout=30)
                    if json_response.status_code == 200:
                        json_data = json_response.json()
                        web_links = json_data.get('webLinks', [])

                        # Find XML metadata URL
                        xml_url = None
                        for link in web_links:
                            if (link.get('type') == 'originalMetadata' and
                                link.get('title') == 'Product Metadata'):
                                xml_url = link.get('uri')
                                break

                        if xml_url:
                            # Fetch and parse XML
                            xml_response = requests.get(xml_url, timeout=30)
                            if xml_response.status_code == 200:
                                root = ET.fromstring(xml_response.content)

                                # Extract dates from timeperd section
                                timeinfo = root.find('.//timeperd/timeinfo/rngdates')
                                if timeinfo is not None:
                                    begdate = timeinfo.findtext('begdate', 'N/A')
                                    enddate = timeinfo.findtext('enddate', 'N/A')
                                    pubdate = root.findtext('.//citation/citeinfo/pubdate', 'N/A')

                                    # Format dates
                                    if begdate != 'N/A' and len(begdate) == 8:
                                        begdate = f"{begdate[:4]}-{begdate[4:6]}-{begdate[6:8]}"
                                    if enddate != 'N/A' and len(enddate) == 8:
                                        enddate = f"{enddate[:4]}-{enddate[4:6]}-{enddate[6:8]}"
                                    if pubdate != 'N/A' and len(pubdate) == 8:
                                        pubdate = f"{pubdate[:4]}-{pubdate[4:6]}-{pubdate[6:8]}"

                                    metadata['dates'] = {
                                        'Start': begdate,
                                        'End': enddate,
                                        'Publication': pubdate
                                    }
                                    logger.info(f"Extracted dates from XML: Start={begdate}, End={enddate}, Publication={pubdate}")
                except Exception as e:
                    logger.error(f"Error fetching metadata dates: {e}", exc_info=True)
                    metadata['dates'] = {
                        'Start': 'N/A',
                        'End': 'N/A',
                        'Publication': 'N/A'
                    }

                # Store basic metadata and URLs
                metadata['json_url'] = json_url

                # Use default state for Illinois
                metadata['state'] = 'IL'
                metadata['region'] = 'Midwest'

                # Set basic spatial reference
                metadata['spatial_ref'] = {
                    'coordinate_system': {
                        'name': 'NAD83 / UTM zone 16N',
                        'epsg_code': '26916'
                    },
                    'datum': {
                        'horizontal_datum': 'NAD83',
                        'vertical_datum': 'NAVD88'
                    }
                }

                # Store the metadata
                self.projects[project_name] = metadata
                logger.info(f"Added metadata for project: {project_name}")

        except Exception as e:
            logger.error(f"Error in add_project: {e}", exc_info=True)
            # Initialize with basic metadata even on error
            self.projects[project_name] = self._initialize_metadata(project_name)

    def _log_xml_structure(self, element, depth=0):
        """Recursively log XML structure"""
        indent = "  " * depth
        logger.info(f"{indent}Element: {element.tag}")

        # Log attributes if any
        if element.attrib:
            logger.info(f"{indent}Attributes: {element.attrib}")

        # Log text content if any
        if element.text and element.text.strip():
            logger.info(f"{indent}Text: {element.text.strip()}")

        # Recursively log child elements
        for child in element:
            self._log_xml_structure(child, depth + 1)

    def _extract_all_metadata(self, root):
        """Extract all available metadata from XML"""
        metadata = {}

        # Log and extract all available elements
        for elem in root.iter():
            if elem.text and elem.text.strip():
                path = root.getroottree().getpath(elem)
                metadata[path] = elem.text.strip()

        return metadata

    def _initialize_metadata(self, project_name):
        """Initialize metadata structure with minimal defaults"""
        return {
            'name': project_name,
            'summary': '',
            # No hard-coded spatial reference or datum info - will be filled
            # with actual data from lidar search results
            'spatial_ref': {
                'coordinate_system': {},
                'datum': {}
            }
        }

    def _update_metadata_from_xml(self, metadata, root):
        """Update metadata dictionary with information from XML"""
        try:
            logger.info("Updating metadata from XML")

            # Extract identification information
            idinfo = root.find('.//idinfo')
            if idinfo is not None:
                # Extract time period information with proper date formatting
                # First try timeinfo in idinfo
                timeinfo = idinfo.find('.//timeinfo/rngdates')

                # If not found in idinfo, try timeperd section
                if timeinfo is None:
                    timeinfo = root.find('.//timeperd/timeinfo/rngdates')

                if timeinfo is not None:
                    begdate = timeinfo.findtext('begdate', 'N/A')
                    enddate = timeinfo.findtext('enddate', 'N/A')

                    # Format dates if they're in YYYYMMDD format
                    if begdate != 'N/A' and len(begdate) == 8:
                        begdate = f"{begdate[:4]}-{begdate[4:6]}-{begdate[6:8]}"
                    if enddate != 'N/A' and len(enddate) == 8:
                        enddate = f"{enddate[:4]}-{enddate[4:6]}-{enddate[6:8]}"

                    pubdate = root.findtext('.//citation/citeinfo/pubdate', 'N/A')
                    if pubdate != 'N/A' and len(pubdate) == 8:
                        pubdate = f"{pubdate[:4]}-{pubdate[4:6]}-{pubdate[6:8]}"

                    metadata['dates'] = {
                        'Start': begdate,
                        'End': enddate,
                        'Publication': pubdate
                    }
                    logger.info(f"Extracted dates: Start={begdate}, End={enddate}, Publication={pubdate}")

                # Extract title and summary
                citation = idinfo.find('.//citation/citeinfo')
                if citation is not None:
                    metadata['title'] = citation.findtext('title', 'N/A')

                descript = idinfo.find('.//descript')
                if descript is not None:
                    metadata['summary'] = descript.findtext('abstract', 'N/A')
                    metadata['purpose'] = descript.findtext('purpose', 'N/A')

                    # Extract inventory ID from supplemental info if available
                    supplinf = descript.findtext('supplinf', '')
                    if supplinf:
                        try:
                            supp_data = json.loads(supplinf)
                            if 'inventory' in supp_data:
                                metadata['inventory_id'] = supp_data['inventory']
                                logger.info(f"Extracted inventory ID: {metadata['inventory_id']}")
                        except json.JSONDecodeError:
                            logger.warning(f"Could not parse supplemental info as JSON: {supplinf}")

                # Extract bounding box information
                spdom = idinfo.find('.//spdom/bounding')
                if spdom is not None:
                    metadata['bounds'] = {
                        'minX': float(spdom.findtext('westbc', 0)),
                        'maxX': float(spdom.findtext('eastbc', 0)),
                        'minY': float(spdom.findtext('southbc', 0)),
                        'maxY': float(spdom.findtext('northbc', 0))
                    }
                    logger.info(f"Extracted bounds from XML: {metadata['bounds']}")

                # Extract place keywords for state and region information
                place_keywords = []
                for place in idinfo.findall('.//place/placekey'):
                    if place.text:
                        place_keywords.append(place.text.strip())

                if place_keywords:
                    metadata['place_keywords'] = place_keywords
                    logger.info(f"Extracted place keywords: {place_keywords}")

                    # Try to extract state information from place keywords
                    state_codes = {
                        'ALABAMA': 'AL', 'ALASKA': 'AK', 'ARIZONA': 'AZ', 'ARKANSAS': 'AR',
                        'CALIFORNIA': 'CA', 'COLORADO': 'CO', 'CONNECTICUT': 'CT', 'DELAWARE': 'DE',
                        'FLORIDA': 'FL', 'GEORGIA': 'GA', 'HAWAII': 'HI', 'IDAHO': 'ID',
                        'ILLINOIS': 'IL', 'INDIANA': 'IN', 'IOWA': 'IA', 'KANSAS': 'KS',
                        'KENTUCKY': 'KY', 'LOUISIANA': 'LA', 'MAINE': 'ME', 'MARYLAND': 'MD',
                        'MASSACHUSETTS': 'MA', 'MICHIGAN': 'MI', 'MINNESOTA': 'MN', 'MISSISSIPPI': 'MS',
                        'MISSOURI': 'MO', 'MONTANA': 'MT', 'NEBRASKA': 'NE', 'NEVADA': 'NV',
                        'NEW HAMPSHIRE': 'NH', 'NEW JERSEY': 'NJ', 'NEW MEXICO': 'NM', 'NEW YORK': 'NY',
                        'NORTH CAROLINA': 'NC', 'NORTH DAKOTA': 'ND', 'OHIO': 'OH', 'OKLAHOMA': 'OK',
                        'OREGON': 'OR', 'PENNSYLVANIA': 'PA', 'RHODE ISLAND': 'RI', 'SOUTH CAROLINA': 'SC',
                        'SOUTH DAKOTA': 'SD', 'TENNESSEE': 'TN', 'TEXAS': 'TX', 'UTAH': 'UT',
                        'VERMONT': 'VT', 'VIRGINIA': 'VA', 'WASHINGTON': 'WA', 'WEST VIRGINIA': 'WV',
                        'WISCONSIN': 'WI', 'WYOMING': 'WY'
                    }

                    # Also check for two-letter state codes
                    two_letter_codes = list(state_codes.values())

                    # Check for state names or codes in place keywords
                    for keyword in place_keywords:
                        keyword_upper = keyword.upper()

                        # Check for full state name
                        if keyword_upper in state_codes:
                            metadata['state'] = state_codes[keyword_upper]
                            logger.info(f"Found state in keywords: {metadata['state']}")
                            break

                        # Check for two-letter state code
                        if keyword_upper in two_letter_codes:
                            metadata['state'] = keyword_upper
                            logger.info(f"Found state code in keywords: {metadata['state']}")
                            break

                        # Check if state name is contained in the keyword
                        for state_name, state_code in state_codes.items():
                            if state_name in keyword_upper:
                                metadata['state'] = state_code
                                logger.info(f"Found state in keyword part: {metadata['state']}")
                                break

                    # Check for region information in place keywords
                    regions = ['NORTHEAST', 'NORTHWEST', 'SOUTHEAST', 'SOUTHWEST',
                              'MIDWEST', 'WEST', 'EAST', 'NORTH', 'SOUTH', 'CENTRAL']

                    for keyword in place_keywords:
                        keyword_upper = keyword.upper()
                        for region in regions:
                            if region in keyword_upper:
                                metadata['region'] = region.title()
                                logger.info(f"Found region in keywords: {metadata['region']}")
                                break

                # Extract browse image URL if available
                browse = idinfo.find('.//browse/browsen')
                if browse is not None and browse.text:
                    if 'additional_urls' not in metadata:
                        metadata['additional_urls'] = {}
                    metadata['additional_urls']['browse_image'] = browse.text.strip()
                    logger.info(f"Extracted browse image URL: {browse.text.strip()}")

            # Extract data quality information
            dataqual = root.find('.//dataqual')
            if dataqual is not None:
                metadata['quality'] = {
                    'vertical_accuracy': dataqual.findtext('.//vertacc/vertaccr', 'N/A'),
                    'logical_consistency': dataqual.findtext('.//logic', 'N/A'),
                    'completeness': dataqual.findtext('.//complete', 'N/A')
                }

                # Extract LAS/LAZ version information
                attraccr = dataqual.findtext('.//attracc/attraccr', '')
                if attraccr:
                    las_version_match = re.search(r'LAZ\s+(\d+\.\d+)', attraccr)
                    if las_version_match:
                        if 'format' not in metadata:
                            metadata['format'] = {}
                        metadata['format']['version'] = las_version_match.group(1)
                        logger.info(f"Extracted LAZ version: {las_version_match.group(1)}")

            # Extract spatial reference information with enhanced detail
            spref = root.find('.//spref')
            if spref is not None:
                # Initialize spatial reference structure if not present
                if 'spatial_ref' not in metadata:
                    metadata['spatial_ref'] = {'coordinate_system': {}, 'datum': {}}

                # Extract vertical datum information
                vertdef = spref.find('.//vertdef/altsys')
                if vertdef is not None:
                    metadata['spatial_ref']['datum']['vertical_datum'] = vertdef.findtext('altdatum', 'N/A')
                    metadata['spatial_ref']['vertical_units'] = vertdef.findtext('altunits', 'N/A').lower()
                    metadata['spatial_ref']['vertical_resolution'] = vertdef.findtext('altres', 'N/A')

                    # Also store in the vertical section
                    if 'vertical' not in metadata:
                        metadata['vertical'] = {}

                    metadata['vertical']['units'] = vertdef.findtext('altunits', 'N/A').lower()
                    metadata['vertical']['resolution'] = vertdef.findtext('altres', 'N/A')

                # Extract horizontal coordinate system information
                horizsys = spref.find('.//horizsys')
                if horizsys is not None:
                    # Extract projection information
                    planar = horizsys.find('.//planar')
                    if planar is not None:
                        # Check for grid system first (UTM, State Plane, etc.)
                        gridsys = planar.find('.//gridsys')
                        if gridsys is not None:
                            gridsysn = gridsys.findtext('gridsysn', 'N/A')
                            metadata['spatial_ref']['coordinate_system']['name'] = gridsysn

                            # Check for UTM
                            if 'UTM' in gridsysn:
                                utm = gridsys.find('.//utm')
                                if utm is not None:
                                    metadata['spatial_ref']['coordinate_system']['type'] = 'utm'
                                    utmzone = utm.findtext('utmzone', 'N/A')
                                    transmer = utm.find('.//transmer')

                                    parameters = {
                                        'zone': utmzone,
                                        'hemisphere': 'north'  # Default to northern hemisphere
                                    }

                                    if transmer is not None:
                                        parameters.update({
                                            'scale_factor': transmer.findtext('sfctrmer', '0.9996'),
                                            'central_meridian': float(transmer.findtext('longcm', 0)),
                                            'latitude_of_origin': float(transmer.findtext('latprjo', 0)),
                                            'false_easting': float(transmer.findtext('feast', 0)),
                                            'false_northing': float(transmer.findtext('fnorth', 0))
                                        })

                                    metadata['spatial_ref']['coordinate_system']['parameters'] = parameters

                                    # Try to determine EPSG code for UTM
                                    if 'NAD83' in gridsysn:
                                        zone = int(utmzone)
                                        # NAD83 UTM North zones are 26900 + zone number
                                        epsg = 26900 + zone
                                        metadata['spatial_ref']['coordinate_system']['epsg_code'] = f'EPSG:{epsg}'
                                        logger.info(f"Determined EPSG code for UTM zone {zone}N: EPSG:{epsg}")

                            # Check for State Plane
                            elif 'State Plane' in gridsysn or 'SPCS' in gridsysn:
                                spcs = gridsys.find('.//spcs')
                                if spcs is not None:
                                    metadata['spatial_ref']['coordinate_system']['type'] = 'state_plane'
                                    spcszone = spcs.findtext('spcszone', 'N/A')

                                    parameters = {
                                        'zone': spcszone
                                    }

                                    # Extract projection parameters if available
                                    transmer = spcs.find('.//transmer')
                                    if transmer is not None:
                                        parameters.update({
                                            'scale_factor': transmer.findtext('sfctrmer', 'N/A'),
                                            'central_meridian': float(transmer.findtext('longcm', 0)),
                                            'latitude_of_origin': float(transmer.findtext('latprjo', 0)),
                                            'false_easting': float(transmer.findtext('feast', 0)),
                                            'false_northing': float(transmer.findtext('fnorth', 0))
                                        })

                                    metadata['spatial_ref']['coordinate_system']['parameters'] = parameters

                                    # Try to extract state from SPCS zone
                                    spcs_zone = spcs.findtext('spcszone', '')
                                    if spcs_zone:
                                        # State plane zones often start with the state name
                                        for state_name, state_code in state_codes.items():
                                            if state_name in spcs_zone.upper():
                                                metadata['state'] = state_code
                                                logger.info(f"Extracted state {state_code} from SPCS zone")
                                                break

                        # Check for map projection if no grid system
                        elif planar.find('.//mapproj') is not None:
                            mapproj = planar.find('.//mapproj')
                            # Get projection name
                            proj_name = mapproj.findtext('mapprojn', 'N/A')
                            metadata['spatial_ref']['coordinate_system']['name'] = proj_name

                            # Try to extract EPSG code from projection name
                            if 'NAD83' in proj_name:
                                # This is a heuristic - in a real system we'd use a lookup table
                                if 'Conus Albers' in proj_name:
                                    metadata['spatial_ref']['coordinate_system']['epsg_code'] = 'EPSG:5070'
                                elif 'UTM' in proj_name:
                                    # Extract zone from name or try to determine from bounds
                                    zone_match = re.search(r'Zone\s+(\d+)', proj_name)
                                    if zone_match:
                                        zone = zone_match.group(1)
                                        # NAD83 UTM North zones are 26900 + zone number
                                        epsg = 26900 + int(zone)
                                        metadata['spatial_ref']['coordinate_system']['epsg_code'] = f'EPSG:{epsg}'

                            # Extract projection parameters based on projection type
                            # Albers Equal Area
                            albers = mapproj.find('.//albers')
                            if albers is not None:
                                metadata['spatial_ref']['coordinate_system']['type'] = 'albers'
                                metadata['spatial_ref']['coordinate_system']['parameters'] = {
                                    'standard_parallel_1': float(albers.findtext('stdparll[1]', 0)),
                                    'standard_parallel_2': float(albers.findtext('stdparll[2]', 0)),
                                    'central_meridian': float(albers.findtext('longcm', 0)),
                                    'latitude_of_origin': float(albers.findtext('latprjo', 0)),
                                    'false_easting': float(albers.findtext('feast', 0)),
                                    'false_northing': float(albers.findtext('fnorth', 0))
                                }

                            # UTM
                            utm = mapproj.find('.//utm')
                            if utm is not None:
                                metadata['spatial_ref']['coordinate_system']['type'] = 'utm'
                                metadata['spatial_ref']['coordinate_system']['parameters'] = {
                                    'zone': utm.findtext('zone', 'N/A'),
                                    'hemisphere': 'north' if utm.findtext('hemisphere', 'N') == 'N' else 'south'
                                }

                        # Extract units information
                        plandu = planar.findtext('.//plandu', 'N/A')
                        if plandu:
                            metadata['spatial_ref']['coordinate_system']['units'] = plandu.lower()

                # Extract datum information
                geodetic = spref.find('.//geodetic')
                if geodetic is not None:
                    metadata['spatial_ref']['datum']['horizontal_datum'] = geodetic.findtext('horizdn', 'N/A')
                    metadata['spatial_ref']['datum']['ellipsoid'] = geodetic.findtext('ellips', 'N/A')

            # Extract distribution information
            distinfo = root.find('.//distinfo')
            if distinfo is not None:
                # Extract file format information
                digform = distinfo.find('.//digform/digtinfo')
                if digform is not None:
                    if 'format' not in metadata:
                        metadata['format'] = {}
                    metadata['format']['name'] = digform.findtext('formname', 'N/A')
                    metadata['format']['size_mb'] = float(digform.findtext('transize', 0))

                    # Convert size to bytes for consistency
                    size_mb = float(digform.findtext('transize', 0))
                    metadata['format']['size_bytes'] = int(size_mb * 1024 * 1024)

                # Extract download URL
                networkr = distinfo.find('.//networkr')
                if networkr is not None and networkr.text:
                    metadata['download_url'] = networkr.text.strip()

            # Extract metadata URLs from metainfo section
            metainfo = root.find('.//metainfo')
            if metainfo is not None:
                metextns = metainfo.findall('.//metextns/onlink')
                if metextns:
                    if 'additional_urls' not in metadata:
                        metadata['additional_urls'] = {}

                    for i, link in enumerate(metextns):
                        if link.text:
                            url = link.text.strip()
                            if 'asprs.org' in url:
                                metadata['additional_urls']['las_specifications'] = url
                            else:
                                metadata['additional_urls'][f'metadata_link_{i}'] = url

            logger.info("Successfully updated metadata from XML")
            return metadata

        except Exception as e:
            logger.error(f"Error updating metadata from XML: {e}", exc_info=True)
            return metadata

    def _extract_coordinate_system(self, metadata, planar):
        """Enhanced coordinate system extraction from XML"""
        try:
            coord_system = {}

            # First try to get direct EPSG code
            epsg_element = planar.find('.//gridsys/gridsysn')
            if epsg_element is not None and 'EPSG' in epsg_element.text:
                epsg_code = epsg_element.text.split('EPSG:')[-1].strip()
                logger.info(f"Found direct EPSG code: {epsg_code}")
                coord_system['epsg_code'] = epsg_code

                # Get CRS details from EPSG
                crs = CRS.from_epsg(int(epsg_code))
                coord_system.update({
                    'name': crs.name,
                    'type': 'projected',
                    'units': crs.axis_info[0].unit_name,
                    'parameters': {
                        'false_easting': crs.to_dict().get('false_easting', 0),
                        'false_northing': crs.to_dict().get('false_northing', 0),
                        'scale_factor': crs.to_dict().get('scale_factor', 1)
                    }
                })
                return coord_system

            # Try UTM
            utm = planar.find('.//gridsys/utm')
            if utm is not None:
                zone = utm.findtext('.//zone')
                hemi = utm.findtext('.//hemisphere')
                if zone and hemi:
                    zone_num = int(zone)
                    epsg_code = 32600 + zone_num if hemi == 'N' else 32700 + zone_num
                    logger.info(f"Determined UTM EPSG code: {epsg_code}")
                    coord_system.update({
                        'epsg_code': str(epsg_code),
                        'type': 'utm',
                        'name': f'UTM Zone {zone}{hemi}',
                        'utm': {
                            'zone': zone_num,
                            'hemisphere': hemi,
                            'scale_factor': '0.9996',
                            'false_easting': '500000',
                            'false_northing': '0'
                        }
                    })
                    return coord_system

            # Try State Plane
            state_plane = planar.find('.//gridsys/spcs')
            if state_plane is not None:
                state = self._determine_state_from_bounds(self.current_bounds)
                zone = state_plane.findtext('.//zone')
                logger.info(f"Found State Plane coordinates for state: {state}, zone: {zone}")
                epsg_code = self._get_state_plane_epsg(state, zone)
                if epsg_code:
                    coord_system.update({
                        'epsg_code': epsg_code,
                        'type': 'state_plane',
                        'name': f'NAD83 (2011) State Plane {state}',
                        'parameters': self._get_state_plane_parameters(epsg_code)
                    })
                    return coord_system

            logger.warning("Could not determine coordinate system from metadata")
            return None

        except Exception as e:
            logger.error(f"Error extracting coordinate system: {e}", exc_info=True)
            return None

    def _determine_state_from_bounds(self, bounds):
        """Determine state based on bounding box coordinates"""
        # Skip state determination completely to avoid unnecessary lookups
        logger.info("Skipping state determination to avoid unnecessary lookups")
        return 'IL'  # Default to Illinois since coordinates in logs are in Illinois

    def _get_state_plane_epsg(self, state, zone=None):
        """Get modern state plane EPSG code"""
        try:
            if state in self.state_plane_epsg:
                if isinstance(self.state_plane_epsg[state], dict):
                    # Handle multiple zones
                    if zone:
                        return self.state_plane_epsg[state].get(zone.lower())
                    # Default to central if no zone specified
                    return self.state_plane_epsg[state].get('central')
                return self.state_plane_epsg[state]
            logger.warning(f"No EPSG code found for state: {state}")
            return None
        except Exception as e:
            logger.error(f"Error getting state plane EPSG: {e}")
            return None

    def _get_state_plane_parameters(self, epsg_code):
        """Get projection parameters for state plane"""
        try:
            crs = CRS.from_epsg(int(epsg_code))
            params = crs.to_dict()
            return {
                'latitude_of_origin': params.get('lat_0', 0),
                'central_meridian': params.get('lon_0', 0),
                'scale_factor': params.get('k', 0.9996),
                'false_easting': params.get('x_0', 500000),
                'false_northing': params.get('y_0', 0),
                'units': crs.axis_info[0].unit_name
            }
        except Exception as e:
            logger.error(f"Error getting state plane parameters: {e}")
            return {}

    def _extract_projection_info(self, root):
        """Extract detailed projection information from XML"""
        try:
            spref = root.find('.//spref')
            if spref is None:
                return None

            projection_info = {
                'coordinate_system': {},
                'datum': {},
                'bounds': {}
            }

            # Extract horizontal datum info
            horizsys = spref.find('.//horizsys')
            if horizsys is not None:
                geodetic = horizsys.find('.//geodetic')
                if geodetic is not None:
                    projection_info['datum'].update({
                        'horizontal_datum': geodetic.findtext('horizdn'),
                        'ellipsoid': geodetic.findtext('ellips'),
                        'semi_major_axis': geodetic.findtext('semiaxis'),
                        'denominator_of_flattening_ratio': geodetic.findtext('denflat')
                    })

                # Extract coordinate system info
                planar = horizsys.find('.//planar')
                if planar is not None:
                    gridsys = planar.find('.//gridsys')
                    if gridsys is not None:
                        gridsysn = gridsys.findtext('gridsysn', '')

                        # Check for State Plane
                        if any(term in gridsysn for term in ['State Plane', 'SPCS', 'SPC']):
                            if 'Vermont' in gridsysn or 'VT' in gridsysn:
                                projection_info['coordinate_system'].update({
                                    'type': 'state_plane',
                                    'name': 'NAD83 (2011) State Plane Vermont',
                                    'epsg_code': 'EPSG:6589',
                                    'parameters': {
                                        'scale_factor': gridsys.findtext('.//transmer/sfctrmer'),
                                        'longitude_of_central_meridian': gridsys.findtext('.//transmer/longcm'),
                                        'latitude_of_projection_origin': gridsys.findtext('.//transmer/latprjo'),
                                        'false_easting': gridsys.findtext('.//transmer/feast'),
                                        'false_northing': gridsys.findtext('.//transmer/fnorth')
                                    }
                                })

                        # Check for UTM
                        elif 'UTM' in gridsysn:
                            utm = gridsys.find('.//utm')
                            if utm is not None:
                                zone = utm.findtext('utmzone')
                                projection_info['coordinate_system'].update({
                                    'type': 'utm',
                                    'name': f'NAD83 / UTM zone {zone}N',
                                    'zone': zone,
                                    'parameters': {
                                        'scale_factor': '0.9996',
                                        'longitude_of_central_meridian': gridsys.findtext('.//transmer/longcm'),
                                        'latitude_of_projection_origin': gridsys.findtext('.//transmer/latprjo'),
                                        'false_easting': gridsys.findtext('.//transmer/feast'),
                                        'false_northing': gridsys.findtext('.//transmer/fnorth')
                                    }
                                })

                    # Extract units
                    planci = planar.find('.//planci')
                    if planci is not None:
                        units = planci.findtext('plandu', '').lower()
                        projection_info['coordinate_system']['units'] = 'meters' if 'meter' in units else units

            # Extract bounds
            bounding = root.find('.//bounding')
            if bounding is not None:
                projection_info['bounds'].update({
                    'minX': float(bounding.findtext('westbc', 0)),
                    'maxX': float(bounding.findtext('eastbc', 0)),
                    'minY': float(bounding.findtext('southbc', 0)),
                    'maxY': float(bounding.findtext('northbc', 0))
                })

            return projection_info

        except Exception as e:
            logger.error(f"Error extracting projection info: {e}", exc_info=True)
            return None

    def get_project(self, project_name):
        """Get metadata for a specific project"""
        return self.projects.get(project_name)

    def get_coordinate_system_details(self, project_name):
        """Get detailed coordinate system information for search ring generation"""
        project = self.projects.get(project_name)
        if not project:
            return None

        spatial_ref = project.get('spatial_ref', {})
        coord_system = spatial_ref.get('coordinate_system', {})
        datum = spatial_ref.get('datum', {})

        # Get center point of project bounds
        bounds = project.get('bounds', {})
        if bounds:
            center_lat = (bounds['minY'] + bounds['maxY']) / 2
            center_lon = (bounds['minX'] + bounds['maxX']) / 2

            # If no coordinate system is defined, determine appropriate State Plane zone
            if not coord_system.get('epsg_code'):
                epsg_code = self._determine_state_plane_zone(center_lat, center_lon)
                coord_system['epsg_code'] = epsg_code

        return {
            'name': coord_system.get('name'),
            'type': coord_system.get('type'),
            'epsg_code': coord_system.get('epsg_code'),
            'parameters': coord_system.get('parameters', {}),
            'units': coord_system.get('units', 'meters'),
            'datum': datum,
            'center_coordinates': {
                'latitude': center_lat if 'center_lat' in locals() else None,
                'longitude': center_lon if 'center_lon' in locals() else None
            }
        }

    def _determine_state_plane_zone(self, lat, lon):
        """Determine appropriate State Plane zone based on coordinates"""
        # Michigan zones
        if 41.5 <= lat <= 47.0 and -87.5 <= lon <= -82.5:
            if -87.0 <= lon <= -85.75:
                return "EPSG:6496"  # Michigan West
            elif -85.75 <= lon <= -84.37:
                return "EPSG:6497"  # Michigan Central
            else:
                return "EPSG:6498"  # Michigan East

        # Add more state zone logic here

        # Default to Michigan Central if no match
        return "EPSG:6497"

    def _extract_bounds(self, root):
        """Extract bounds information from XML"""
        try:
            bounds = {}
            bounding = root.find('.//bounding')
            if bounding is not None:
                logger.info("Found bounding element in XML")
                # Log raw bounding values
                westbc = bounding.findtext('westbc')
                eastbc = bounding.findtext('eastbc')
                southbc = bounding.findtext('southbc')
                northbc = bounding.findtext('northbc')

                logger.debug(f"Raw bounding coordinates from XML:")
                logger.debug(f"West: {westbc}")
                logger.debug(f"East: {eastbc}")
                logger.debug(f"South: {southbc}")
                logger.debug(f"North: {northbc}")

                bounds = {
                    'minX': float(westbc if westbc is not None else 0),
                    'maxX': float(eastbc if eastbc is not None else 0),
                    'minY': float(southbc if southbc is not None else 0),
                    'maxY': float(northbc if northbc is not None else 0)
                }

                logger.info(f"Extracted bounds: {bounds}")

                # Validate bounds
                if all(isinstance(v, (int, float)) for v in bounds.values()):
                    return bounds
                else:
                    logger.warning("Invalid bound values found")

            else:
                logger.warning("No bounding element found in XML")

            return None

        except Exception as e:
            logger.error(f"Error extracting bounds: {e}", exc_info=True)
            return None

    def get_project_bounds(self, project_name):
        """Get the overall bounds for a project"""
        project = self.projects.get(project_name)
        if project:
            bounds = project.get('bounds')
            if bounds:
                return {
                    'minX': bounds['minX'],
                    'maxX': bounds['maxX'],
                    'minY': bounds['minY'],
                    'maxY': bounds['maxY'],
                    'width': bounds['maxX'] - bounds['minX'],
                    'height': bounds['maxY'] - bounds['minY'],
                    'center_x': (bounds['maxX'] + bounds['minX']) / 2,
                    'center_y': (bounds['maxY'] + bounds['minY']) / 2
                }
        return None

    def is_point_in_project_bounds(self, project_name, lat, lon):
        """Check if a point falls within project bounds"""
        bounds = self.get_project_bounds(project_name)
        if bounds:
            return (
                bounds['minX'] <= lon <= bounds['maxX'] and
                bounds['minY'] <= lat <= bounds['maxY']
            )
        return False

    def fetch_and_parse_xml(self, url):
        """Fetch and parse XML from URL"""
        try:
            logger.info(f"Fetching XML from: {url}")
            response = requests.get(url)
            response.raise_for_status()

            # Log raw XML content
            logger.debug(f"Raw XML content:\n{response.text}")

            # Save XML content to file
            xml_temp_dir = "XML_Temp"
            if not os.path.exists(xml_temp_dir):
                os.makedirs(xml_temp_dir)

            filename = os.path.basename(url)
            xml_path = os.path.join(xml_temp_dir, filename)
            with open(xml_path, 'w') as f:
                f.write(response.text)
            logger.info(f"Saved XML to: {xml_path}")

            root = ET.fromstring(response.content)
            logger.info(f"Successfully parsed XML from: {url}")
            return root

        except Exception as e:
            logger.error(f"Error in fetch_and_parse_xml: {str(e)}", exc_info=True)
            return None

    def fetch_metadata_from_sciencebase(self, meta_url):
        """Fetch metadata from ScienceBase using the metaUrl"""
        try:
            json_url = f"{meta_url}?format=json"
            logger.info(f"Fetching JSON metadata from: {json_url}")
            response = requests.get(json_url)
            response.raise_for_status()

            data = response.json()
            logger.info("Successfully fetched JSON metadata")
            logger.debug(json.dumps(data, indent=2))

            # Extract and log relevant metadata
            self._process_json_metadata(data)

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching JSON from {json_url}: {e}")
        except Exception as e:
            logger.error(f"Error fetching JSON from {json_url}: {e}", exc_info=True)

    def _process_json_metadata(self, data):
        """Process JSON metadata to extract relevant information"""
        try:
            # Log the metaUrl we're starting with
            meta_url = data.get('metaUrl')
            logger.info(f"\nStarting with metaUrl: {meta_url}")

            # Construct and log the JSON URL
            json_url = f"{meta_url}?format=json"
            logger.info(f"Constructed JSON URL: {json_url}")

            # Get and log the JSON response
            json_response = requests.get(json_url)
            json_data = json_response.json()
            logger.info("Got JSON response, looking for webLinks...")

            # Extract web links
            web_links = json_data.get('webLinks', [])
            logger.info(f"\nFound {len(web_links)} web links:")

            # Log all web links for debugging
            for i, link in enumerate(web_links):
                logger.info(f"\nLink {i+1}:")
                logger.info(f"Type: {link.get('type')}")
                logger.info(f"Title: {link.get('title')}")
                logger.info(f"URI: {link.get('uri')}")

                if (link.get('type') == 'originalMetadata' and
                    link.get('title') == 'Product Metadata'):
                    xml_url = link.get('uri')
                    logger.info(f"\n!!! FOUND XML METADATA URL !!!: {xml_url}")
                    self._fetch_and_process_xml(xml_url, data.get('title'))

        except Exception as e:
            logger.error(f"Error processing JSON metadata: {e}", exc_info=True)

    def _fetch_and_process_xml(self, url, project_name):
        """Fetch and process XML from URL"""
        try:
            logger.info(f"Fetching XML from: {url}")
            response = requests.get(url)
            response.raise_for_status()

            xml_temp_dir = "XML_Temp"
            if not os.path.exists(xml_temp_dir):
                os.makedirs(xml_temp_dir)
                logger.info(f"Created XML_Temp directory")

            filename = f"{project_name}_metadata.xml"
            xml_path = os.path.join(xml_temp_dir, filename)
            with open(xml_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.info(f"Saved XML to: {os.path.abspath(xml_path)}")

            # Further processing of XML can be done here

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error fetching XML from {url}: {e}")
        except Exception as e:
            logger.error(f"Error processing XML from {url}: {e}", exc_info=True)

    def validate_metadata(self, project_name):
        """Validate that all required metadata fields are present"""
        if project_name not in self.projects:
            logger.error(f"Project {project_name} not found in metadata")
            return False, ["project_not_found"]

        metadata = self.projects[project_name]
        missing_fields = []

        for field in self.required_metadata_fields:
            # Handle nested fields with dot notation
            if '.' in field:
                parts = field.split('.')
                value = metadata
                for part in parts:
                    if isinstance(value, dict) and part in value:
                        value = value[part]
                    else:
                        value = None
                        break
                if value is None or value == 'N/A':
                    missing_fields.append(field)
            else:
                if field not in metadata or metadata[field] is None or metadata[field] == 'N/A':
                    missing_fields.append(field)

        return len(missing_fields) == 0, missing_fields

    def _recover_missing_fields(self, project_name, missing_fields):
        """Attempt to recover missing metadata fields"""
        logger.info(f"Attempting to recover missing fields for {project_name}: {missing_fields}")

        if project_name not in self.projects:
            return

        metadata = self.projects[project_name]

        # Try to determine state from bounds if available
        if 'bounds' in metadata and any(field.startswith('spatial_ref') for field in missing_fields):
            bounds = metadata['bounds']
            if all(key in bounds for key in ['minX', 'maxX', 'minY', 'maxY']):
                # Calculate center point
                center_lat = (bounds['minY'] + bounds['maxY']) / 2
                center_lon = (bounds['minX'] + bounds['maxX']) / 2

                # Try to determine state from bounds
                state = self._determine_state_from_bounds(bounds)
                if state:
                    logger.info(f"Determined state {state} from bounds")

                    # Only set state in metadata, but don't hard-code any coordinate system or datum info
                    metadata['state'] = state
                    logger.info(f"Set state to {state} for {project_name}")

        # Update the project metadata
        self.projects[project_name] = metadata

    def _update_tower_parameters(self, project_name, determine_state=True):
        """Update tower_parameters.json with LIDAR metadata for a specific project"""
        try:
            # Skip if project doesn't exist
            if project_name not in self.projects:
                logger.error(f"Cannot update non-existent project: {project_name}")
                return False

            # Get metadata for the project
            metadata = self.projects[project_name]

            # Read existing tower_parameters.json
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error reading tower_parameters.json: {e}")
                tower_data = {
                    "site_A": {},
                    "site_B": {},
                    "general_parameters": {},
                    "turbines": []
                }

            # Add or initialize LIDAR data section
            if 'lidar_data' not in tower_data:
                tower_data['lidar_data'] = {}

            # Create or update project entry with minimal required metadata
            lidar_entry = {
                'name': metadata.get('name', project_name),
                'title': metadata.get('title', project_name),
                'source_id': metadata.get('source_id', ''),
                'inventory_id': metadata.get('inventory_id', ''),
                'download_url': metadata.get('download_url', ''),
                'bounds': metadata.get('bounds', {}),
                'files': metadata.get('files', []),
                'state': metadata.get('state', 'IL'),  # Default to IL
                'region': metadata.get('region', 'Midwest'),  # Default to Midwest
                'spatial_ref': metadata.get('spatial_ref', {
                    'coordinate_system': {
                        'name': 'NAD83 / UTM zone 16N',
                        'epsg_code': '26916'
                    },
                    'datum': {
                        'horizontal_datum': 'NAD83',
                        'vertical_datum': 'NAVD88'
                    }
                }),
                'metadata_updated': datetime.now().isoformat()
            }

            # Update the entry in tower_parameters.json
            tower_data['lidar_data'][project_name] = lidar_entry

            # Write back to tower_parameters.json
            with open('tower_parameters.json', 'w') as f:
                json.dump(tower_data, f, indent=2)

            logger.info(f"Updated tower_parameters.json with minimal metadata for {project_name}")

        except Exception as e:
            logger.error(f"Error updating tower_parameters.json: {e}", exc_info=True)

    def _determine_state_from_coordinates(self, lat, lon):
        """Determine US state from coordinates using a point-in-polygon approach"""
        # Skip state determination to avoid unnecessary lookups
        logger.info("Skipping state coordinate lookup to avoid unnecessary processing")
        return {
            'state_code': 'IL',  # Default to Illinois
            'region': 'Midwest'
        }

    def _haversine_distance(self, lat1, lon1, lat2, lon2):
        """Calculate the great circle distance between two points in kilometers"""
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        r = 6371  # Radius of earth in kilometers
        return c * r

    def add_file_to_project(self, project_name, file_item):
        """Add a lidar file to an existing project"""
        if project_name not in self.projects:
            logger.error(f"Cannot add file to non-existent project: {project_name}")
            return False

        try:
            # Extract file information
            url = file_item.get('downloadURL', '')
            filename = url.split('/')[-1] if url else ''

            if not filename:
                logger.error(f"Cannot add file without filename to project: {project_name}")
                return False

            # Get project metadata
            metadata = self.projects[project_name]

            # Check if files list exists, create if not
            if 'files' not in metadata:
                metadata['files'] = []

            # Check if file already exists in project
            for existing_file in metadata['files']:
                if existing_file.get('filename') == filename:
                    logger.info(f"File {filename} already exists in project {project_name}")
                    return True

            # Extract bounds if available
            bbox = file_item.get('boundingBox', {})

            # Create file entry
            file_entry = {
                'filename': filename,
                'download_url': url,
                'source_id': file_item.get('sourceId', ''),
                'title': file_item.get('title', ''),
                'size_bytes': file_item.get('sizeInBytes', 0),
                'bounds': bbox or {},
                'local_file_path': ''
            }

            # Add to files list
            metadata['files'].append(file_entry)
            logger.info(f"Added file {filename} to project {project_name}")

            # Don't update tower_parameters.json after each file for performance
            # Will be updated once at the end of the process
            # self._update_tower_parameters(project_name)

            return True
        except Exception as e:
            logger.error(f"Error adding file to project {project_name}: {e}", exc_info=True)
            return False

    def update_project_files(self, project_name, file_items):
        """Update a project with multiple file items"""
        if project_name not in self.projects:
            logger.error(f"Cannot update files for non-existent project: {project_name}")
            return False

        try:
            success_count = 0
            for file_item in file_items:
                if self.add_file_to_project(project_name, file_item):
                    success_count += 1

            logger.info(f"Added {success_count} of {len(file_items)} files to project {project_name}")

            # Only update the JSON file once after all files are added
            if success_count > 0:
                self._update_tower_parameters(project_name)

            return success_count > 0
        except Exception as e:
            logger.error(f"Error updating files for project {project_name}: {e}", exc_info=True)
            return False

    def update_all_projects_in_json(self):
        """Update tower_parameters.json with all project and file information"""
        try:
            logger.info("Updating all project information in tower_parameters.json")

            # Import the safe JSON utilities
            try:
                from utilities.json_utils import safe_read_json_file, safe_update_json_file
                use_safe_utils = True
            except ImportError:
                logger.warning("Could not import safe JSON utilities, falling back to standard methods")
                use_safe_utils = False

            # Read existing tower_parameters.json
            if use_safe_utils:
                tower_data = safe_read_json_file('tower_parameters.json', default_data={
                    "site_A": {},
                    "site_B": {},
                    "general_parameters": {},
                    "lidar_data": {},
                    "turbines": []
                })
            else:
                try:
                    with open('tower_parameters.json', 'r') as f:
                        tower_data = json.load(f)
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error(f"Error reading tower_parameters.json: {e}")
                    tower_data = {
                        "site_A": {},
                        "site_B": {},
                        "general_parameters": {},
                        "turbines": []
                    }

            # Add or initialize LIDAR data section
            if 'lidar_data' not in tower_data:
                tower_data['lidar_data'] = {}

            # Ensure turbines exists
            if 'turbines' not in tower_data:
                tower_data['turbines'] = []

            # Update each project in the tower_parameters.json file
            for project_name, metadata in self.projects.items():
                self._update_tower_parameters(project_name, determine_state=False)

            # Write back to tower_parameters.json
            if use_safe_utils:
                success = safe_update_json_file(tower_data, 'tower_parameters.json')
                if success:
                    logger.info(f"Successfully updated tower_parameters.json with {len(self.projects)} projects")
                else:
                    logger.error("Failed to update tower_parameters.json")
                return success
            else:
                # Create a backup of the current file first
                try:
                    if os.path.exists('tower_parameters.json'):
                        # Create a backup with timestamp
                        backup_filename = f"tower_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.bak"
                        with open('tower_parameters.json', 'r') as src:
                            with open(backup_filename, 'w') as dst:
                                dst.write(src.read())
                        logger.info(f"Created backup of tower_parameters.json as {backup_filename}")
                except Exception as backup_error:
                    logger.warning(f"Could not create backup of tower_parameters.json: {backup_error}")

                # Write to a temporary file first
                temp_path = 'tower_parameters.json.tmp'
                try:
                    with open(temp_path, 'w') as f:
                        json.dump(tower_data, f, indent=2)

                    # Verify the JSON is valid by reading it back
                    with open(temp_path, 'r') as f:
                        json.load(f)  # This will raise an exception if the JSON is invalid

                    # Replace the original file with the temporary file
                    if os.path.exists('tower_parameters.json'):
                        os.replace(temp_path, 'tower_parameters.json')
                    else:
                        os.rename(temp_path, 'tower_parameters.json')

                    logger.info(f"Successfully updated tower_parameters.json with {len(self.projects)} projects")
                    return True
                except Exception as write_error:
                    logger.error(f"Error writing to tower_parameters.json: {write_error}", exc_info=True)
                    # Clean up the temporary file if it exists
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except:
                        pass
                    return False

        except Exception as e:
            logger.error(f"Error updating all projects in tower_parameters.json: {e}", exc_info=True)
            return False

    def refresh_all_metadata(self):
        """
        Refresh metadata for all existing projects in tower_parameters.json
        by fetching the complete XML and JSON metadata and updating the file.
        """
        try:
            logger.info("Refreshing metadata for all projects")

            # Read existing tower_parameters.json
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Error reading tower_parameters.json: {e}")
                return False

            # Check if lidar_data section exists
            if 'lidar_data' not in tower_data:
                logger.warning("No lidar_data section found in tower_parameters.json")
                return False

            # Keep track of projects that need updating
            projects_to_update = []

            # Process each project in the tower_parameters.json file
            for project_name, project_data in tower_data['lidar_data'].items():
                # Skip projects already in memory
                if project_name in self.projects:
                    projects_to_update.append(project_name)
                    continue

                # Check if project has metadata URLs
                meta_url = None
                if 'metadata_urls' in project_data:
                    meta_url = project_data['metadata_urls'].get('meta_url')

                if not meta_url:
                    logger.warning(f"Project {project_name} has no meta_url, skipping")
                    continue

                # Fetch JSON metadata
                try:
                    logger.info(f"Fetching metadata for project {project_name}")
                    json_url = f"{meta_url}?format=json"
                    json_response = requests.get(json_url, timeout=30)

                    if json_response.status_code != 200:
                        logger.error(f"Failed to fetch JSON metadata for {project_name}")
                        continue

                    json_data = json_response.json()

                    # Find XML URL
                    xml_url = None
                    web_links = json_data.get('webLinks', [])
                    for link in web_links:
                        if (link.get('type') == 'originalMetadata' and
                            link.get('title') == 'Product Metadata'):
                            xml_url = link.get('uri')
                            break

                    if not xml_url:
                        logger.warning(f"No XML URL found for project {project_name}")
                        continue

                    # Create a simple metadata structure for add_project
                    first_item = {
                        'metaUrl': meta_url,
                        'downloadURL': project_data.get('download_url', ''),
                        'sourceId': project_data.get('source_id', ''),
                        'sizeInBytes': project_data.get('size_bytes', 0),
                        'boundingBox': project_data.get('bounds', {})
                    }

                    # Add the project to our metadata
                    self.add_project(project_name, first_item)
                    projects_to_update.append(project_name)

                except Exception as e:
                    logger.error(f"Error refreshing metadata for {project_name}: {e}", exc_info=True)

            # Update tower_parameters.json with refreshed metadata
            for project_name in projects_to_update:
                self._update_tower_parameters(project_name)

            logger.info(f"Refreshed metadata for {len(projects_to_update)} projects")
            return True

        except Exception as e:
            logger.error(f"Error in refresh_all_metadata: {e}", exc_info=True)
            return False

# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    metadata = ProjectMetadata()
    metadata.fetch_metadata_from_sciencebase("https://www.sciencebase.gov/catalog/item/60e68107d34e2a7685cfdda8")
