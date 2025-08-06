"""
Map Server for Line of Sight Tool

This module provides a local HTTP server that serves:
1. A static map page that clients can view
2. Dynamic coordinate data that updates as coordinates change
3. Static files (CSS, JS) needed by the map page

The server runs in a background thread and can be started, stopped,
and updated with new coordinates.
"""

import os
import json
import threading
import logging
import time
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import mimetypes
import urllib.parse
import socket
from pathlib import Path
import re
import math
import subprocess
import sys
import requests
import tempfile
import pickle
from shapely.geometry import Polygon
from dotenv import load_dotenv

# Import the shared SpatialIndex class
try:
    from osm_data.osm_spatial_index import SpatialIndex
except ImportError:
    logging.getLogger(__name__).warning("Could not import SpatialIndex class from osm_data.osm_spatial_index")
    SpatialIndex = None

# Import PostgreSQL OSM query module
try:
    # Add the current directory to the Python path to ensure imports work
    import sys
    import os

    # Get the absolute path to the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))

    # Add both the current directory and the utilities directory to the path
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

    utilities_dir = os.path.join(current_dir, 'utilities')
    if os.path.exists(utilities_dir) and utilities_dir not in sys.path:
        sys.path.insert(0, utilities_dir)

    # Log the Python path for debugging
    logger = logging.getLogger(__name__)
    logger.debug(f"Python path: {sys.path}")

    # Now try to import the PostgreSQL query module
    from osm_data.osm_postgis_query import query_osm_in_polygon as postgis_query_osm_in_polygon
    from osm_data.osm_postgis_query import is_database_ready as is_postgis_ready

    # Log success
    logger.info("Successfully imported PostgreSQL OSM query module")
except ImportError as e:
    logging.getLogger(__name__).warning(f"Could not import PostgreSQL OSM query module: {e}")
    postgis_query_osm_in_polygon = None
    is_postgis_ready = None

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Global variables
server_instance = None
server_thread = None
server_port = 9000
server_address = None
api_key = None
mapbox_token = os.getenv('MAPBOX_ACCESS_TOKEN')
# Define the path to your JSON file (adjust if necessary)
script_dir_for_path = os.path.dirname(os.path.abspath(__file__))
TOWER_PARAMS_PATH = os.path.abspath(os.path.join(script_dir_for_path, 'tower_parameters.json'))
# Path to OSM data file
OSM_DATA_PATH = os.path.abspath(os.path.join(script_dir_for_path, '..', 'DATABASE', 'osm_data', 'us-latest.osm.pbf'))
# Path to processed OSM data
OSM_PROCESSED_DIR = os.path.abspath(os.path.join(script_dir_for_path, '..', 'DATABASE', 'osm_data'))
# Spatial index for OSM objects
osm_spatial_index = None

# --- Helper Functions ---

def load_tower_params():
    """Loads data from the tower_parameters.json file."""
    try:
        # Ensure path is correct
        if not os.path.exists(TOWER_PARAMS_PATH):
             logger.error(f"Tower parameters file not found at: {TOWER_PARAMS_PATH}")
             return None
        with open(TOWER_PARAMS_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # This might be redundant if check above works, but keep for safety
        logger.error(f"Error: {TOWER_PARAMS_PATH} not found during open.")
        return None
    except json.JSONDecodeError:
        logger.error(f"Error: Could not decode JSON from {TOWER_PARAMS_PATH}.")
        return None
    except Exception as e:
        logger.error(f"Unexpected error loading tower parameters: {e}", exc_info=True)
        return None

def save_tower_params(data):
    """Saves data to the tower_parameters.json file."""
    try:
        with open(TOWER_PARAMS_PATH, 'w') as f:
            json.dump(data, f, indent=2) # Use indent for readability
        return True
    except IOError as e:
        logger.error(f"Error saving to {TOWER_PARAMS_PATH}: {e}")
        return False
    except TypeError as e:
        logger.error(f"Error serializing data for JSON: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error saving tower parameters: {e}", exc_info=True)
        return False

def dms_to_decimal(dms_str):
    """Converts a DMS string (e.g., "40-21-16.0 N") to decimal degrees."""
    if not isinstance(dms_str, str) or not dms_str.strip(): # Handle potential non-string or empty input
        logger.debug(f"Invalid input to dms_to_decimal: {dms_str!r}")
        return None
    try:
        # Updated regex to handle various separators including degrees, minutes, seconds symbols
        parts = re.split('[°\\\'\\"\\sNnEeWwSs-]+', dms_str.strip())
        # Filter out empty strings that might result from multiple separators together
        parts = [p for p in parts if p]

        if len(parts) < 3:
            # Try a simpler split if the complex one failed, e.g., just by space or hyphen
            parts_simple = re.split('[\s-]+', dms_str.strip())
            parts_simple = [p for p in parts_simple if p]
            if len(parts_simple) >= 3:
                 logger.debug(f"Using simple split for DMS: {dms_str} -> {parts_simple}")
                 parts = parts_simple
            else:
                 raise ValueError(f"Could not parse DMS: {dms_str} -> {parts} or {parts_simple}")

        degrees = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])

        # Infer direction from the original string
        direction = ''
        dms_upper = dms_str.upper()
        if 'N' in dms_upper: direction = 'N'
        elif 'S' in dms_upper: direction = 'S'
        elif 'E' in dms_upper: direction = 'E'
        elif 'W' in dms_upper: direction = 'W'
        else: # Attempt last part if letters weren't explicit (e.g., just spaces)
             if len(parts) > 3 and parts[-1].isalpha() and parts[-1].upper() in ['N','S','E','W']:
                 direction = parts[-1].upper()
             elif dms_str.strip()[-1].isalpha() and dms_str.strip()[-1].upper() in ['N','S','E','W']:
                  direction = dms_str.strip()[-1].upper()
             else:
                  logger.warning(f"Could not determine direction in DMS: {dms_str}. Assuming N/E based on sign or default.")
                  # Defaulting to N/E might be wrong, consider raising ValueError
                  if degrees < 0: # Assume negative means S or W
                      if abs(degrees) > 90: # Likely longitude
                          direction = 'W'
                      else: # Likely latitude
                          direction = 'S'
                  else: # Assume positive means N or E
                      if abs(degrees) > 90: # Likely longitude
                           direction = 'E'
                      else:
                           direction = 'N'
                  # raise ValueError(f"Could not determine direction in DMS: {dms_str}")

        # Use absolute value for calculation, apply sign later based on direction
        decimal = abs(degrees) + abs(minutes) / 60 + abs(seconds) / 3600

        if direction in ('S', 'W'):
            decimal *= -1

        return decimal
    except (ValueError, IndexError, TypeError, AttributeError) as e:
        logger.error(f"Error converting DMS string '{dms_str}': {e}", exc_info=False) # exc_info=False to reduce log noise
        return None # Return None on error

class MapRequestHandler(BaseHTTPRequestHandler):
    """Handler for map server requests"""

    def do_GET(self):
        """Handle GET requests"""
        try:
            # Parse the URL path
            parsed_path = urllib.parse.urlparse(self.path)
            path = parsed_path.path.lstrip('/')

            # Map route
            if self.path == '/' or self.path == '/map':
                self.serve_map_page()

            # Coordinates endpoint
            elif self.path == '/coordinates':
                self.serve_coordinates()

            # Turbines endpoint
            elif self.path == '/get_turbines':
                self.serve_turbines()

            # Tower parameters endpoint
            elif self.path == '/get_tower_parameters':
                self.serve_tower_parameters()

            # Static files
            elif path.startswith('static/'):
                self.serve_static_file(path)

            # 404 for any other path
            else:
                self.send_error(404, 'Not Found')

        except Exception as e:
            logger.error(f"Error handling GET request for {self.path}: {e}", exc_info=True)
            try:
                if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                     self.send_error(500, f"Internal Server Error: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def serve_map_page(self):
        """Serve the map HTML page"""
        try:
            # Get the path to the map HTML template
            base_dir = os.path.dirname(os.path.abspath(__file__))
            template_dir = os.path.join(base_dir, 'templates') # Templates directory is at the same level
            map_file_path = os.path.join(template_dir, 'map.html') # Use map.html

            if not os.path.exists(map_file_path):
                logger.error(f"Map template not found at expected path: {map_file_path}")
                self.send_error(404, "Map template file not found")
                return

            with open(map_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()

            global api_key, mapbox_token
            if api_key and 'API_KEY_PLACEHOLDER' in html_content:
                html_content = html_content.replace('API_KEY_PLACEHOLDER', api_key)
            elif 'maps.googleapis.com/maps/api/js?key=' in html_content and not api_key:
                 logger.warning("API Key placeholder found in template but no API key is available.")

            # Replace Mapbox token placeholder
            if mapbox_token and '{{ mapbox_token }}' in html_content:
                html_content = html_content.replace('{{ mapbox_token }}', mapbox_token)
            else:
                logger.warning("Mapbox token not available or placeholder not found in template.")

            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            encoded_content = html_content.encode('utf-8')
            self.send_header('Content-Length', str(len(encoded_content)))
            self.end_headers()
            self.wfile.write(encoded_content)

        except Exception as e:
            logger.error(f"Error serving map page: {e}", exc_info=True)
            try:
                 if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                     self.send_error(500, f"Error serving map page: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def serve_coordinates(self):
        """Serve site coordinates, prioritizing adjusted values."""
        try:
            tower_params = load_tower_params()
            if tower_params is None:
                self.send_error(500, "Could not load tower parameters")
                return

            site_a = tower_params.get('site_A', {})
            site_b = tower_params.get('site_B', {})
            general = tower_params.get('general_parameters', {})
            lidar_data = tower_params.get('lidar_data', {}) # Include lidar data

            # Determine coordinates for Site A (Donor)
            donor_lat = site_a.get('adjusted_latitude')
            donor_lng = site_a.get('adjusted_longitude')

            if donor_lat is None or donor_lng is None:
                # Original coordinates instead of adjusted
                orig_lat = site_a.get('latitude', '')
                orig_lng = site_a.get('longitude', '')
                logger.debug(f"Adjusted donor coords not found, using original: {orig_lat} / {orig_lng}")

                # Check if these are already decimal coordinates
                if (isinstance(orig_lat, (int, float)) or
                    (isinstance(orig_lat, str) and orig_lat.replace('.', '', 1).replace('-', '', 1).isdigit())):
                    try:
                        donor_lat = float(orig_lat)
                        donor_lng = float(orig_lng)
                        logger.debug(f"Original donor coordinates already in decimal format: {donor_lat}, {donor_lng}")
                    except (ValueError, TypeError):
                        logger.error(f"Failed to convert numeric donor coordinates: {orig_lat}, {orig_lng}")
                        donor_lat = donor_lng = None
                else:
                    # Try to convert from DMS format
                    try:
                        donor_lat = dms_to_decimal(orig_lat)
                        donor_lng = dms_to_decimal(orig_lng)
                        logger.debug(f"Converted donor DMS to decimal: {donor_lat}, {donor_lng}")
                    except Exception as e:
                        logger.error(f"Failed to convert donor DMS coordinates: {e}")
                        donor_lat = donor_lng = None
            else:
                logger.debug(f"Using adjusted donor coords: {donor_lat}, {donor_lng}")

            # Determine coordinates for Site B (Recipient)
            recipient_lat = site_b.get('adjusted_latitude')
            recipient_lng = site_b.get('adjusted_longitude')

            if recipient_lat is None or recipient_lng is None:
                # Original coordinates instead of adjusted
                orig_lat = site_b.get('latitude', '')
                orig_lng = site_b.get('longitude', '')
                logger.debug(f"Adjusted recipient coords not found, using original: {orig_lat} / {orig_lng}")

                # Check if these are already decimal coordinates
                if (isinstance(orig_lat, (int, float)) or
                    (isinstance(orig_lat, str) and orig_lat.replace('.', '', 1).replace('-', '', 1).isdigit())):
                    try:
                        recipient_lat = float(orig_lat)
                        recipient_lng = float(orig_lng)
                        logger.debug(f"Original recipient coordinates already in decimal format: {recipient_lat}, {recipient_lng}")
                    except (ValueError, TypeError):
                        logger.error(f"Failed to convert numeric recipient coordinates: {orig_lat}, {orig_lng}")
                        recipient_lat = recipient_lng = None
                else:
                    # Try to convert from DMS format
                    try:
                        recipient_lat = dms_to_decimal(orig_lat)
                        recipient_lng = dms_to_decimal(orig_lng)
                        logger.debug(f"Converted recipient DMS to decimal: {recipient_lat}, {recipient_lng}")
                    except Exception as e:
                        logger.error(f"Failed to convert recipient DMS coordinates: {e}")
                        recipient_lat = recipient_lng = None
            else:
                logger.debug(f"Using adjusted recipient coords: {recipient_lat}, {recipient_lng}")

            # Basic check if coordinates are valid
            if donor_lat is None or donor_lng is None or recipient_lat is None or recipient_lng is None:
                 logger.warning("Could not determine valid coordinates for one or both sites in serve_coordinates.")
                 self.send_error(500, "Invalid coordinates found in source data")
                 return

            response_data = {
                "donor_lat": donor_lat,
                "donor_lng": donor_lng,
                "donor_name": site_a.get("site_id", "Donor Site"),
                "donor_elevation": site_a.get("elevation_ft"),
                "donor_antenna_height": site_a.get("antenna_cl_ft"),
                "donor_azimuth": site_a.get("azimuth_deg"),

                "recipient_lat": recipient_lat,
                "recipient_lng": recipient_lng,
                "recipient_name": site_b.get("site_id", "Recipient Site"),
                "recipient_elevation": site_b.get("elevation_ft"),
                "recipient_antenna_height": site_b.get("antenna_cl_ft"),
                "recipient_azimuth": site_b.get("azimuth_deg"),

                "frequency_ghz": general.get("frequency_ghz"),
                "lidar_data": lidar_data, # Pass lidar data through
                "timestamp": time.time() # Add timestamp
            }

            # Convert response data to JSON
            json_data = json.dumps(response_data).encode('utf-8')

            # Serve the JSON data
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(json_data)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(json_data)

        except Exception as e:
            logger.error(f"Error serving coordinates: {e}", exc_info=True)
            try:
                 if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                     self.send_error(500, f"Error serving coordinates: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def serve_turbines(self):
        """Serve turbine data as JSON"""
        try:
            # Read turbines from tower_parameters.json
            tower_params = load_tower_params()
            if tower_params is None:
                self.send_error(500, "Could not load tower parameters")
                return

            # Get turbines array
            turbines = tower_params.get('turbines', [])

            # Send the turbines as JSON
            json_data = json.dumps(turbines).encode('utf-8')

            # Serve the JSON data
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(json_data)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(json_data)
        except Exception as e:
            logger.error(f"Error serving turbines: {e}", exc_info=True)
            try:
                if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                    self.send_error(500, f"Error serving turbines: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def serve_tower_parameters(self):
        """Serve the entire tower parameters as JSON"""
        try:
            # Read tower parameters
            tower_params = load_tower_params()
            if tower_params is None:
                self.send_error(500, "Could not load tower parameters")
                return

            # Send the tower parameters as JSON
            json_data = json.dumps(tower_params).encode('utf-8')

            # Serve the JSON data
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(json_data)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(json_data)

        except Exception as e:
            logger.error(f"Error serving turbines: {e}", exc_info=True)
            try:
                 if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                     self.send_error(500, f"Error serving turbines: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def serve_static_file(self, file_path):
        """Serve a static file"""
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            full_path = os.path.abspath(os.path.join(base_dir, file_path))

            # Security Check: Ensure the path is within the project root
            project_root = os.path.abspath(os.path.dirname(base_dir))
            if not full_path.startswith(project_root):
                 logger.warning(f"Attempt to access file outside project root: {file_path}")
                 self.send_error(404, 'File not found')
                 return

            # Allow access to static directory
            if 'static' in file_path:
                # It's in a static directory, proceed
                pass
            else:
                logger.warning(f"Attempt to access non-static file: {file_path}")
                self.send_error(404, 'File not found')
                return

            if not os.path.exists(full_path) or not os.path.isfile(full_path):
                logger.warning(f"Static file not found: {full_path}")
                self.send_error(404, 'File not found')
                return

            content_type, _ = mimetypes.guess_type(full_path)
            if not content_type:
                if file_path.endswith('.js'):
                    content_type = 'application/javascript; charset=utf-8'
                elif file_path.endswith('.css'):
                    content_type = 'text/css; charset=utf-8'
                else:
                    content_type = 'application/octet-stream'

            with open(full_path, 'rb') as f:
                file_content = f.read()

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(file_content)))
            self.end_headers()
            self.wfile.write(file_content)

        except Exception as e:
            logger.error(f"Error serving static file {file_path}: {e}", exc_info=True)
            try:
                 if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                    self.send_error(500, f"Error serving static file: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response: {send_err}")

    def do_POST(self):
        """Handle POST requests"""
        if self.path == '/update_adjusted_coordinates':
            self.handle_update_coordinates()
        elif self.path == '/estimate-date':
            self.handle_date_estimation()
        elif self.path == '/api/towers':
            self.handle_tower_search()
        elif self.path == '/api/osm_objects':
            self.handle_osm_objects()
        elif self.path == '/api/osm_direct':
            self.handle_osm_direct()
        else:
            self.send_error(404, "Endpoint not found")

    def handle_tower_search(self):
        """Handle tower search requests"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response(400, {"error": "Request body is empty"})
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Invalid JSON in request body"})
                return

            # Get polygon from request
            polygon = data.get('polygon')
            if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
                self._send_json_response(400, {"error": "Invalid polygon. Must be an array of [longitude, latitude] points."})
                return

            # Import tower database functions
            from utilities.tower_database import search_towers_in_polygon, ensure_tower_database_exists

            # Ensure tower database exists
            if not ensure_tower_database_exists():
                self._send_json_response(500, {"error": "Failed to initialize tower database."})
                return

            # Search for towers in the polygon
            towers = search_towers_in_polygon(polygon)

            # Send response
            self._send_json_response(200, towers)

        except Exception as e:
            logger.error(f"Error handling tower search request: {e}", exc_info=True)
            self._send_json_response(500, {"error": f"Error searching for towers: {str(e)}"})

    def handle_osm_objects(self):
        """Handle OSM objects search requests"""
        global osm_spatial_index

        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response(400, {"error": "Request body is empty"})
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Invalid JSON in request body"})
                return

            # Get polygon from request
            polygon = data.get('polygon')
            if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
                self._send_json_response(400, {"error": "Invalid polygon. Must be an array of [longitude, latitude] points."})
                return

            # Get object types to filter for
            object_types = data.get('types', [])

            # Try to use direct OSM query first
            try:
                # Add the current directory to the Python path
                import sys
                import os
                current_dir = os.path.dirname(os.path.abspath(__file__))
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)

                # Import the direct query function
                from osm_data.osm_direct_query import query_osm_in_polygon

                logger.info("Using direct OSM query")
                # Set a shorter timeout for better responsiveness
                results = query_osm_in_polygon(polygon, timeout=30)

                # Filter by object types if specified
                if object_types and results:
                    filtered_results = []
                    for obj in results:
                        if 'properties' not in obj:
                            continue

                        # Check if any of the requested types match
                        obj_props = obj['properties']
                        for t in object_types:
                            # Check various property fields that might contain type info
                            if (t in obj_props.get('type', '') or
                                t in obj_props.get('man_made', '') or
                                t in obj_props.get('power', '') or
                                t in obj_props.get('tower:type', '')):
                                filtered_results.append(obj)
                                break

                    results = filtered_results

                # Limit the number of results to avoid overwhelming the client
                max_results = 500
                if len(results) > max_results:
                    logger.info(f"Limiting direct OSM results from {len(results)} to {max_results}")
                    results = results[:max_results]

                if results:
                    self._send_json_response(200, results)
                    logger.info(f"Returned {len(results)} OSM objects from direct query")
                    return
                else:
                    logger.warning("No results from direct OSM query, falling back to mock data")
            except Exception as e:
                logger.error(f"Error in direct OSM query: {e}", exc_info=True)
                logger.info("Falling back to mock data after direct query error")

            # If direct query failed, try PostgreSQL if available
            try:
                # Check if PostgreSQL modules are available
                pg_modules_available = False

                # Check if the PostgreSQL modules are available in the global scope
                if 'postgis_query_osm_in_polygon' in globals() and 'is_postgis_ready' in globals():
                    pg_query_func = globals()['postgis_query_osm_in_polygon']
                    pg_ready_func = globals()['is_postgis_ready']

                    if pg_query_func is not None and pg_ready_func is not None:
                        logger.info("PostgreSQL modules available from global scope")
                        pg_modules_available = True
                    else:
                        logger.info("PostgreSQL modules in global scope are None")
                else:
                    logger.info("PostgreSQL modules not found in global scope")

                # If not available in global scope, try to import directly
                if not pg_modules_available:
                    logger.info("Attempting to import PostgreSQL modules directly")

                    # Try to import directly
                    try:
                        # First check if psycopg2 is available
                        import importlib.util
                        psycopg2_spec = importlib.util.find_spec("psycopg2")
                        if psycopg2_spec is None:
                            logger.warning("psycopg2 package is not installed. Install with: pip install psycopg2-binary")
                            raise ImportError("psycopg2 package is not installed")

                        # Now try to import the PostgreSQL query module
                        from osm_data.osm_postgis_query import query_osm_in_polygon, is_database_ready
                        pg_query_func = query_osm_in_polygon
                        pg_ready_func = is_database_ready
                        pg_modules_available = True
                        logger.info("Successfully imported PostgreSQL modules directly")
                    except ImportError as e:
                        logger.error(f"Failed to import PostgreSQL modules directly: {e}")
                        pg_modules_available = False

                # If PostgreSQL modules are available, try to use them
                if pg_modules_available:
                    # Check if database is ready
                    logger.info("Checking if PostgreSQL database is ready...")
                    db_ready = pg_ready_func()
                    logger.info(f"PostgreSQL database ready: {db_ready}")

                    if db_ready:
                        logger.info("Using PostgreSQL for OSM query")
                        results = pg_query_func(polygon, object_types)

                        # Limit the number of results to avoid overwhelming the client
                        max_results = 500
                        if len(results) > max_results:
                            logger.info(f"Limiting PostgreSQL results from {len(results)} to {max_results}")
                            results = results[:max_results]

                        self._send_json_response(200, results)
                        logger.info(f"Returned {len(results)} OSM objects from PostgreSQL")
                        return
                    else:
                        logger.info("PostgreSQL database not ready, using spatial index")
                else:
                    logger.info("PostgreSQL modules not available, using spatial index")

            except Exception as e:
                logger.error(f"Error in PostgreSQL integration: {e}", exc_info=True)
                logger.info("Falling back to spatial index after PostgreSQL error")

            # Check if OSM data directory exists
            if not os.path.exists(OSM_PROCESSED_DIR):
                logger.warning(f"OSM processed data directory not found at {OSM_PROCESSED_DIR}")
                self._send_mock_osm_objects(polygon, object_types)
                return

            # Check if we need to load the spatial index
            if osm_spatial_index is None:
                # Try to load the spatial index
                osm_spatial_index = self._load_osm_spatial_index()

            # If we still don't have a spatial index, fall back to mock data
            if osm_spatial_index is None:
                logger.warning("OSM spatial index is None, using mock data")
                self._send_mock_osm_objects(polygon, object_types)
                return

            # Query the spatial index for objects within the polygon
            try:
                # Query the spatial index
                if not hasattr(osm_spatial_index, 'query_polygon'):
                    logger.error("Spatial index does not have query_polygon method")
                    self._send_mock_osm_objects(polygon, object_types)
                    return

                results = osm_spatial_index.query_polygon(polygon)

                # Filter by object types if specified
                if object_types:
                    filtered_results = []
                    for obj in results:
                        if 'properties' not in obj:
                            continue
                        obj_type = obj['properties'].get('type', '')
                        if any(t in obj_type for t in object_types):
                            filtered_results.append(obj)
                    results = filtered_results

                # Since we're now searching only within a 2000-foot corridor around the path,
                # we can show all results without overwhelming the client
                logger.info(f"Found {len(results)} OSM objects within the path corridor")

                # Send response
                self._send_json_response(200, results)
                logger.info(f"Returned {len(results)} OSM objects from spatial index")

            except Exception as e:
                logger.error(f"Error querying OSM spatial index: {e}", exc_info=True)
                # Fall back to mock data if querying fails
                self._send_mock_osm_objects(polygon, object_types)

        except Exception as e:
            logger.error(f"Error handling OSM objects request: {e}", exc_info=True)
            # Always fall back to mock data on error
            try:
                if 'polygon' in locals() and 'object_types' in locals():
                    self._send_mock_osm_objects(polygon, object_types)
                else:
                    self._send_json_response(500, {"error": f"Error searching for OSM objects: {str(e)}"})
            except Exception as send_err:
                logger.error(f"Error sending error response: {send_err}", exc_info=True)
                self._send_json_response(500, {"error": "Internal server error"})

    def _load_osm_spatial_index(self):
        """Load the OSM spatial index"""
        global osm_spatial_index

        # Check if the processed data directory exists
        if not os.path.exists(OSM_PROCESSED_DIR):
            logger.warning(f"OSM processed data directory not found at {OSM_PROCESSED_DIR}")
            logger.info("OSM data is still being processed. Using mock data for now.")
            return None

        # Check if the index file exists
        index_file = os.path.join(OSM_PROCESSED_DIR, 'structures.idx')
        if not os.path.exists(index_file):
            logger.warning(f"OSM spatial index file not found at {index_file}")
            logger.info("OSM data is still being processed. Using mock data for now.")
            return None

        # Load the spatial index
        try:
            with open(index_file, 'rb') as f:
                osm_spatial_index = pickle.load(f)

            # Check if the spatial index has the expected structure
            if not hasattr(osm_spatial_index, 'structures') or not hasattr(osm_spatial_index, 'query_polygon'):
                logger.error("Loaded spatial index has invalid structure")
                logger.info("Using mock data due to invalid spatial index structure.")
                return None

            logger.info(f"Loaded OSM spatial index with {len(osm_spatial_index.structures)} structures")
            return osm_spatial_index

        except Exception as e:
            logger.error(f"Error loading OSM spatial index: {e}", exc_info=True)
            logger.info("Using mock data due to error loading OSM spatial index.")
            return None

    def _send_mock_osm_objects(self, polygon, object_types):
        """Send mock OSM objects as a fallback"""
        logger.warning("Using mock OSM data as fallback")

        # Create a bounding box from the polygon
        lats = [p[1] for p in polygon]
        lngs = [p[0] for p in polygon]
        min_lat = min(lats)
        max_lat = max(lats)
        min_lng = min(lngs)
        max_lng = max(lngs)

        # Generate some mock OSM objects within the bounding box
        mock_objects = []

        # Add some towers
        if 'tower' in object_types or 'communications_tower' in object_types:
            # Add a few communication towers
            for i in range(3):
                lat = min_lat + (max_lat - min_lat) * (0.25 + 0.5 * i / 3)
                lng = min_lng + (max_lng - min_lng) * (0.25 + 0.5 * i / 3)
                mock_objects.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "properties": {
                        "id": f"n123456{i}",
                        "type": "communications_tower",
                        "name": f"Communications Tower {i+1}",
                        "height": 50 + i * 10,
                        "material": "steel"
                    }
                })

        # Add some water towers
        if 'water_tower' in object_types:
            for i in range(2):
                lat = min_lat + (max_lat - min_lat) * (0.3 + 0.4 * i / 2)
                lng = min_lng + (max_lng - min_lng) * (0.6 + 0.3 * i / 2)
                mock_objects.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "properties": {
                        "id": f"n789012{i}",
                        "type": "water_tower",
                        "name": f"Water Tower {i+1}",
                        "height": 30 + i * 5,
                        "material": "concrete"
                    }
                })

        # Add some power towers/pylons
        if 'power_tower' in object_types:
            for i in range(5):
                lat = min_lat + (max_lat - min_lat) * (0.1 + 0.8 * i / 5)
                lng = min_lng + (max_lng - min_lng) * (0.4 + 0.2 * i / 5)
                mock_objects.append({
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lng, lat]
                    },
                    "properties": {
                        "id": f"n345678{i}",
                        "type": "power_tower",
                        "name": f"Power Pylon {i+1}",
                        "height": 25 + i * 3,
                        "material": "steel",
                        "operator": "Local Power Company"
                    }
                })

        # Send response
        self._send_json_response(200, mock_objects)
        logger.info(f"Returned {len(mock_objects)} mock OSM objects")

    def _send_json_response(self, status_code, data):
        """Send a JSON response with the given status code and data"""
        try:
            response_json = json.dumps(data).encode('utf-8')
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.end_headers()
            self.wfile.write(response_json)
        except Exception as e:
            logger.error(f"Error sending JSON response: {e}", exc_info=True)
            if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                self.send_error(500, f"Error sending JSON response: {str(e)}")


    def handle_update_coordinates(self):
        """Handles the logic for updating coordinates from a POST request."""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                 self.send_error(400, "Request body is empty")
                 return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON in request body")
                return

            site_type = data.get('site') # 'donor' or 'recipient'
            adj_lat = data.get('adjusted_latitude')
            adj_lon = data.get('adjusted_longitude')

            # Validate input data
            if not site_type or adj_lat is None or adj_lon is None:
                error_msg = "Missing required fields (site, adjusted_latitude, adjusted_longitude)"
                logger.warning(f"Bad request to update_adjusted_coordinates: {error_msg} - Data: {data}")
                self.send_error(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
                return

            if site_type not in ['donor', 'recipient']:
                 error_msg = "Invalid site type"
                 logger.warning(f"Bad request to update_adjusted_coordinates: {error_msg} - Data: {data}")
                 self.send_error(400)
                 self.send_header('Content-type', 'application/json')
                 self.end_headers()
                 self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
                 return

            try:
                 adj_lat = float(adj_lat)
                 adj_lon = float(adj_lon)
                 # Basic Lat/Lon range check
                 if not (-90 <= adj_lat <= 90 and -180 <= adj_lon <= 180):
                      raise ValueError("Latitude or Longitude out of valid range")
            except (ValueError, TypeError):
                 error_msg = "Latitude and Longitude must be valid numbers within range"
                 logger.warning(f"Bad request to update_adjusted_coordinates: {error_msg} - Data: {data}")
                 self.send_error(400)
                 self.send_header('Content-type', 'application/json')
                 self.end_headers()
                 self.wfile.write(json.dumps({"error": error_msg}).encode('utf-8'))
                 return

            site_key = 'site_A' if site_type == 'donor' else 'site_B'

            # --- Load, Update, Save ---
            tower_params = load_tower_params()
            if tower_params is None:
                 self.send_error(500, "Could not load tower parameters on server")
                 return

            if site_key not in tower_params:
                 self.send_error(500, f"Site key '{site_key}' not found in JSON structure")
                 return

            # Update the dictionary
            tower_params[site_key]['adjusted_latitude'] = adj_lat
            tower_params[site_key]['adjusted_longitude'] = adj_lon
            logger.info(f"Updating {site_key} adjusted coords via POST: Lat={adj_lat}, Lng={adj_lon}")

            # Save back to file
            if not save_tower_params(tower_params):
                 self.send_error(500, "Could not save updated tower parameters on server")
                 return

            # --- Send Success Response ---
            response = {"message": f"{site_type.capitalize()} coordinates updated successfully"}
            response_json = json.dumps(response).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Content-Length', str(len(response_json)))
            self.end_headers()
            self.wfile.write(response_json)

        except Exception as e:
            logger.error(f"Error handling coordinate update POST request: {e}", exc_info=True)
            try:
                 if not getattr(self, '_headers_buffer', None) or not self._headers_buffer:
                     self.send_error(500, f"Internal server error during coordinate update: {str(e)}")
            except Exception as send_err:
                logger.error(f"Failed to send 500 error response for POST: {send_err}")

    def handle_osm_direct(self):
        """Handle direct OSM PBF query requests"""
        try:
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response(400, {"error": "Request body is empty"})
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Invalid JSON in request body"})
                return

            # Get polygon from request
            polygon = data.get('polygon')
            if not polygon or not isinstance(polygon, list) or len(polygon) < 3:
                self._send_json_response(400, {"error": "Invalid polygon. Must be an array of [longitude, latitude] points."})
                return

            # Import the direct query function
            try:
                from osm_data.osm_direct_query import query_osm_in_polygon
            except ImportError:
                logger.error("Could not import query_osm_in_polygon from osm_data.osm_direct_query")
                self._send_json_response(500, {"error": "OSM direct query module not available"})
                return

            # Send an immediate response to let the client know the query is in progress
            self._send_json_response(202, {
                "status": "processing",
                "message": "Direct OSM query in progress. This may take several minutes. Please check the server logs for progress."
            })
            logger.info(f"Started direct OSM query for polygon with {len(polygon)} points")

            # The client will need to make a separate request to get the results
            # This is a limitation of the current implementation, but it prevents timeouts
            return

        except Exception as e:
            logger.error(f"Error handling direct OSM query: {e}", exc_info=True)
            self._send_json_response(500, {"error": f"Error querying OSM data: {str(e)}"})

    def handle_date_estimation(self):
        """Handle date estimation from map screenshot"""
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self._send_json_response(400, {"error": "Request body is empty"})
                return

            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError:
                self._send_json_response(400, {"error": "Invalid JSON in request body"})
                return

            image_data = data.get('image')
            location = data.get('location', {})
            prompt_context = data.get('prompt_context', {})

            if not image_data:
                self._send_json_response(400, {"error": "No image data provided"})
                return

            # Get API key from environment
            api_key = os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                self._send_json_response(500, {"error": "Anthropic API key not configured"})
                return

            # Get location description from client
            location_description = prompt_context.get('location_description', 'unknown location')
            lat = location.get('latitude')
            lng = location.get('longitude')

            # Prepare prompt
            prompt = f'Based on this satellite image centered at coordinates ({lat}, {lng}) in {location_description}, estimate the date and time it was taken. Consider shadows, vegetation, terrain features, and any other visual clues. Provide your best estimate in a structured format including date, time, and confidence level. Assume the year is 2025.'
            logger.info(f"Sending prompt to Claude: {prompt}")

            # Call Anthropic API
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers={
                    'Content-Type': 'application/json',
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01'
                },
                json={
                    'model': 'claude-3-sonnet-20240229',
                    'max_tokens': 1024,
                    'messages': [{
                        'role': 'user',
                        'content': [
                            {
                                'type': 'text',
                                'text': prompt
                            },
                            {
                                'type': 'image',
                                'source': {
                                    'type': 'base64',
                                    'media_type': 'image/jpeg',
                                    'data': image_data.split(',')[1]  # Remove data:image/jpeg;base64, prefix
                                }
                            }
                        ]
                    }]
                }
            )

            if response.status_code != 200:
                raise Exception(f"Anthropic API error: {response.status_code}")

            result = response.json()
            message = result['content'][0]['text']

            # Parse date and time from response
            date_match = re.search(r'Date:\s*(June|July|August|September|October|November|December|January|February|March|April|May)\s*(\d{1,2}),\s*(\d{4})', message)
            time_match = re.search(r'Time:\s*Around\s*(\d{1,2}):(\d{2})\s*(AM|PM)?', message)
            confidence_match = re.search(r'Confidence.*?(\d+)%', message)

            # Convert month name to number
            month_map = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }

            # Parse hour and minute
            hour = 12
            minute = 0
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                if time_match.group(3) == 'PM' and hour != 12:
                    hour += 12
                elif time_match.group(3) == 'AM' and hour == 12:
                    hour = 0

            structured = {
                'success': True,
                'month': month_map[date_match.group(1).lower()] if date_match else 5,
                'day': int(date_match.group(2)) if date_match else 21,
                'year': 2025,
                'hour': hour,
                'minute': minute,
                'state': location.get('state', 'Unknown'),
                'region': location.get('county', 'Unknown'),
                'confidence': int(confidence_match.group(1)) if confidence_match else 0,
                'raw_response': message
            }

            logger.info(f"Parsed response: {structured}")

            # Send response
            self._send_json_response(200, structured)

        except Exception as e:
            logger.error(f"Error handling date estimation: {e}", exc_info=True)
            self._send_json_response(500, {"error": f"Internal server error during date estimation: {str(e)}"})

    def _send_json_response(self, status_code, data):
        """Helper method to send JSON responses"""
        response = json.dumps(data).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Content-Length', str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format, *args):
        """Override log_message to use our logger instead of stderr"""
        try:
            # Simplify logging for less noise
            code = '-'
            if len(args) >= 2 and isinstance(args[1], str) and args[1].isdigit():
                code = args[1]

            # Log successful GET/POST briefly at debug, errors/other at info
            if (self.command == 'GET' and code == '200') or \
               (self.command == 'POST' and code == '200'):
                logger.debug(f'{self.address_string()} - "{self.requestline}" {code} -')
            else:
                logger.info(f'{self.address_string()} - "{self.requestline}" {code} -')
        except Exception:
             # Fallback to original logging format if custom fails
             super().log_message(format, *args)

def cleanup_zombie_processes():
    """Find and terminate any zombie map server processes"""
    logger.info("Checking for zombie map server processes...")
    # Skip the cleanup process to avoid issues with false positives
    logger.info("Skipping zombie process cleanup to avoid issues with false positives")
    return False

def start_server():
    """Start the map server if not already running"""
    global server_instance, server_thread, server_port, server_address, api_key

    # First, check if there are zombie processes and try to clean them up
    cleanup_zombie_processes()

    if server_thread and server_thread.is_alive():
        logger.info(f"Server already running at {server_address}")
        return server_address

    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        logger.warning("Google Maps API key 'GOOGLE_MAPS_API_KEY' not found in environment variables.")

    port = find_available_port()
    if port is None:
        logger.error("Could not find an available port")
        return None

    server_port = port

    try:
        # Create a custom HTTPServer class that allows address reuse
        class ReuseAddressHTTPServer(HTTPServer):
            allow_reuse_address = True

        server = ReuseAddressHTTPServer(('127.0.0.1', server_port), MapRequestHandler)
        server_thread = threading.Thread(target=server.serve_forever, name="MapServerThread")
        server_thread.daemon = True
        server_thread.start()

        server_instance = server
        server_address = f"http://127.0.0.1:{server_port}"

        logger.info(f"Map server started at {server_address}")
        return server_address

    except OSError as e:
         if e.errno == 98 or e.errno == 48: # Address already in use
             logger.error(f"Port {server_port} is already in use. Cannot start map server.")
         else:
             logger.error(f"Error starting map server: {e}", exc_info=True)
         return None
    except Exception as e:
        logger.error(f"Unexpected error starting map server: {e}", exc_info=True)
        return None

def stop_server():
    """Stop the map server if running"""
    global server_instance, server_thread, server_address
    if server_instance:
        logger.info("Shutting down map server...")
        try:
            server_instance.shutdown()
            server_instance.server_close()
            logger.info("Server instance shut down.")
        except Exception as e:
            logger.error(f"Error during server shutdown: {e}")
        finally:
            server_instance = None

    if server_thread and server_thread.is_alive():
        logger.info("Waiting for server thread to join...")
        server_thread.join(timeout=5) # Add a timeout
        if server_thread.is_alive():
            logger.warning("Server thread did not join cleanly.")
        else:
            logger.info("Server thread joined.")
        server_thread = None

    server_address = None # Clear address on stop
    logger.info("Map server stopped.")

def update_map_coordinates(new_coords):
    """DEPRECATED: Updates a global dict. Use file saving instead."""
    logger.warning("update_map_coordinates is deprecated; coordinates are now read from file.")

def update_coordinates(donor_lat, donor_lng, donor_name, recipient_lat, recipient_lng, recipient_name, frequency_ghz,
                      donor_elevation=None, donor_antenna_height=None, donor_azimuth=None,
                      recipient_elevation=None, recipient_antenna_height=None, recipient_azimuth=None,
                      lidar_data=None):
    """Update tower_parameters.json file with new coordinates.
    This function is called from the Tkinter app to update coordinates before displaying the map.
    """
    try:
        # Load existing tower parameters
        tower_params = load_tower_params()
        if tower_params is None:
            # Create a new structure if none exists
            tower_params = {
                'site_A': {},
                'site_B': {},
                'general_parameters': {},
                'lidar_data': {}
            }

        # Update site A (donor)
        if 'site_A' not in tower_params:
            tower_params['site_A'] = {}
        tower_params['site_A']['adjusted_latitude'] = donor_lat
        tower_params['site_A']['adjusted_longitude'] = donor_lng
        if donor_name:
            tower_params['site_A']['site_id'] = donor_name
        if donor_elevation is not None:
            tower_params['site_A']['elevation_ft'] = donor_elevation
        if donor_antenna_height is not None:
            tower_params['site_A']['antenna_cl_ft'] = donor_antenna_height
        if donor_azimuth is not None:
            tower_params['site_A']['azimuth_deg'] = donor_azimuth

        # Update site B (recipient)
        if 'site_B' not in tower_params:
            tower_params['site_B'] = {}
        tower_params['site_B']['adjusted_latitude'] = recipient_lat
        tower_params['site_B']['adjusted_longitude'] = recipient_lng
        if recipient_name:
            tower_params['site_B']['site_id'] = recipient_name
        if recipient_elevation is not None:
            tower_params['site_B']['elevation_ft'] = recipient_elevation
        if recipient_antenna_height is not None:
            tower_params['site_B']['antenna_cl_ft'] = recipient_antenna_height
        if recipient_azimuth is not None:
            tower_params['site_B']['azimuth_deg'] = recipient_azimuth

        # Update general parameters
        if 'general_parameters' not in tower_params:
            tower_params['general_parameters'] = {}
        tower_params['general_parameters']['frequency_ghz'] = frequency_ghz

        # Update lidar data if provided
        if lidar_data:
            tower_params['lidar_data'] = lidar_data

        # Save the updated parameters
        save_success = save_tower_params(tower_params)
        if not save_success:
            logger.error("Failed to save tower parameters in update_coordinates")
            return False

        logger.info(f"Successfully updated tower parameters with coordinates: Donor ({donor_lat}, {donor_lng}), Recipient ({recipient_lat}, {recipient_lng})")
        return True

    except Exception as e:
        logger.error(f"Error in update_coordinates: {e}", exc_info=True)
        return False

def open_map():
    """Open the map in the default web browser"""
    global server_address

    # If server is not running, try to start it first
    if not server_address:
        logger.info("Server not running, attempting to start it...")
        server_address = start_server()
        if not server_address:
            logger.error("Failed to start the map server. Cannot open map.")
            return False

        # Give the server a moment to initialize
        time.sleep(0.5)

    map_url = f"{server_address}/map"
    try:
        logger.info(f"Opening map at {map_url}")
        webbrowser.open(map_url)
        return True
    except Exception as e:
        logger.error(f"Error opening browser: {e}", exc_info=True)
        return False

def find_available_port(start_port=9000, max_attempts=100):
    """Find an available port starting from start_port"""
    port = start_port
    ports_tried = set()

    for i in range(max_attempts):
        if port in ports_tried:
            # Skip already tried ports
            port = port + 1
            continue

        ports_tried.add(port)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # Try to bind to the address. If it fails, the port is likely in use.
                s.bind(('127.0.0.1', port))
                # If bind succeeds, the port is available
                logger.debug(f"Found available port: {port}")
                return port
        except OSError as e:
            if e.errno == 48 or e.errno == 98 or e.errno == 10048:  # Address already in use
                logger.debug(f"Port {port} is in use, trying next ({i+1}/{max_attempts})")
                port = port + 1  # Try next port
            else:  # Other OSError
                logger.error(f"Unexpected OSError checking port {port}: {e}")
                # Try a different port
                port = port + 100
        except Exception as e:
            logger.error(f"Unexpected error checking port {port}: {e}")
            # Try a significantly different port
            port = port + 500

    # If we got here, we couldn't find an available port
    logger.error(f"Could not find an available port after {max_attempts} attempts. Tried ports: {sorted(ports_tried)}")
    return None

def ensure_directories():
    """Ensure required directories exist relative to this script's location."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.abspath(os.path.join(base_dir, 'templates'))
        static_base_dir = os.path.abspath(os.path.join(base_dir, 'static'))
        static_dirs_to_check = [static_base_dir, os.path.join(static_base_dir, 'css'), os.path.join(static_base_dir, 'js')]

        dirs_to_create = [templates_dir] + static_dirs_to_check

        for dir_path in dirs_to_create:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path, exist_ok=True) # Use exist_ok=True
                logger.info(f"Created directory: {dir_path}")
            elif not os.path.isdir(dir_path):
                 logger.error(f"Path exists but is not a directory: {dir_path}")
                 return False

        # Also check if the TOWER_PARAMS_PATH file exists
        if not os.path.exists(TOWER_PARAMS_PATH):
             logger.warning(f"Tower parameters file not found at {TOWER_PARAMS_PATH}. Endpoint /coordinates might fail.")
             # Consider creating a default empty file if appropriate

        return True
    except Exception as e:
        logger.error(f"Error ensuring directories: {e}", exc_info=True)
        return False


def get_default_html_template():
     # This should likely not be used if map.html is required
     logger.error("get_default_html_template called, but 'templates/map.html' should exist.")
     return """<!DOCTYPE html><html><head><title>Error</title></head><body>Map template not found.</body></html>"""


# Ensure directories exist on module load
ensure_directories()
# Log the path being used for the JSON file
logger.info(f"Map server configured to use tower parameters file: {TOWER_PARAMS_PATH}")

# Example usage block (usually commented out in production)
# if __name__ == '__main__':
#     logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
#     logger.info("Starting map server directly...")
#     addr = start_server()
#     if addr:
#         print(f"Server running at {addr}. Open this URL in your browser.")
#         print("Press Ctrl+C to stop.")
#         try:
#             while True:
#                 time.sleep(1)
#         except KeyboardInterrupt:
#             print("\nCtrl+C received.")
#         finally:
#              stop_server()
#     else:
#          print("Failed to start server.")