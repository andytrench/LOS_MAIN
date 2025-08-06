import os
import json
import webbrowser
import logging
import re
import sys
from datetime import datetime
from tkinter import messagebox
from utilities.coordinates import convert_dms_to_decimal, dms_to_decimal, parse_dms
import urllib.parse

# Ensure the current directory is in the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Now import map_server
import map_server

# Set up logging
# Configure logs to display on console
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_map_file():
    """Ensure the map HTML file exists with the correct API key"""

    # Get Google Maps API key from environment
    api_key = os.getenv("GOOGLE_MAPS_API_KEY")
    if not api_key:
        messagebox.showwarning("Missing API Key", "Google Maps API key not found. Check your .env file.")
        return False

    # Ensure the templates directory exists
    templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)

    # Path to the map file
    map_file_path = os.path.join(templates_dir, 'map.html')

    # Check if we need to update the API key
    if os.path.exists(map_file_path):
        try:
            with open(map_file_path, 'r') as f:
                content = f.read()
                if f'key={api_key}' in content:
                    return True  # API key already set correctly
                else:
                    # Update the API key
                    logger.info("Updating map template with API key")
                    updated_content = re.sub(r'key=[A-Za-z0-9_\-]+', f'key={api_key}', content)

                    with open(map_file_path, 'w') as f:
                        f.write(updated_content)
                    return True
        except Exception as e:
            logger.error(f"Error updating API key in map file: {e}", exc_info=True)
            return False

    # If we got here, the file doesn't exist or had an error
    logger.error("Map file does not exist or could not be updated")
    return False

def view_on_map(donor_site=None, recipient_site=None):
    """Open a custom Google Maps view with both sites marked and a line between them."""
    try:
        # First stop any existing server and clean up
        map_server.stop_server()
        map_server.cleanup_zombie_processes()

        # Load tower data if no sites provided
        tower_data = {}
        if not donor_site or not recipient_site:
            try:
                logger.info("No sites provided, loading from tower_parameters.json")
                with open('tower_parameters.json', 'r') as f:
                    tower_data = json.load(f)
                    logger.debug(f"Loaded tower data: {tower_data}")

                if 'site_A' not in tower_data or 'site_B' not in tower_data:
                    logger.error("Missing site data in tower_parameters.json")
                    messagebox.showwarning("No Sites", "Please load site coordinates first.")
                    return

                donor_site = tower_data['site_A']
                recipient_site = tower_data['site_B']

                logger.info("Successfully loaded site data from tower_parameters.json")
                logger.debug(f"Donor site data: {donor_site}")
                logger.debug(f"Recipient site data: {recipient_site}")

            except Exception as e:
                logger.error(f"Error loading from tower_parameters.json: {e}", exc_info=True)
                messagebox.showwarning("No Sites", "Please load site coordinates first.")
                return

        # Process site coordinates
        try:
            # Validate coordinate existence
            required_fields = ['latitude', 'longitude']
            for field in required_fields:
                if field not in donor_site or field not in recipient_site:
                    error_msg = f"Missing {field} in site data"
                    logger.error(error_msg)
                    messagebox.showerror("Error", error_msg)
                    return

            # First, check for and prefer adjusted coordinates if they exist
            donor_lat = donor_site.get('adjusted_latitude')
            donor_lng = donor_site.get('adjusted_longitude')
            if donor_lat is not None and donor_lng is not None:
                logger.info(f"Using adjusted donor coordinates: {donor_lat}, {donor_lng}")
            else:
                # Log raw coordinates before conversion
                logger.info(f"Raw donor coordinates: lat={donor_site['latitude']}, lon={donor_site['longitude']}")

                # Check if the coordinates are already in decimal format
                if (isinstance(donor_site['latitude'], (int, float)) or
                    (isinstance(donor_site['latitude'], str) and
                     donor_site['latitude'].replace('.', '', 1).replace('-', '', 1).isdigit())):
                    # They're already decimal
                    try:
                        donor_lat = float(donor_site['latitude'])
                        donor_lng = float(donor_site['longitude'])
                        logger.info(f"Donor coordinates already in decimal format: {donor_lat}, {donor_lng}")
                    except (ValueError, TypeError):
                        # Fallback to using convert_dms_to_decimal
                        logger.warning(f"Failed to directly convert donor coordinates as decimal, trying DMS conversion")
                        donor_lat, donor_lng = convert_dms_to_decimal(donor_site['latitude'], donor_site['longitude'])
                        logger.info(f"Converted donor coordinates via DMS converter: {donor_lat}, {donor_lng}")
                else:
                    # Convert from DMS format
                    try:
                        donor_lat, donor_lng = convert_dms_to_decimal(donor_site['latitude'], donor_site['longitude'])
                        logger.info(f"Converted donor coordinates from DMS: {donor_lat}, {donor_lng}")
                    except Exception as e:
                        logger.error(f"Error converting donor coordinates: {e}", exc_info=True)
                        messagebox.showerror("Coordinate Error", f"Failed to convert donor coordinates: {str(e)}")
                        return

            # Same approach for recipient coordinates
            recipient_lat = recipient_site.get('adjusted_latitude')
            recipient_lng = recipient_site.get('adjusted_longitude')
            if recipient_lat is not None and recipient_lng is not None:
                logger.info(f"Using adjusted recipient coordinates: {recipient_lat}, {recipient_lng}")
            else:
                # Log raw coordinates before conversion
                logger.info(f"Raw recipient coordinates: lat={recipient_site['latitude']}, lon={recipient_site['longitude']}")

                # Check if the coordinates are already in decimal format
                if (isinstance(recipient_site['latitude'], (int, float)) or
                    (isinstance(recipient_site['latitude'], str) and
                     recipient_site['latitude'].replace('.', '', 1).replace('-', '', 1).isdigit())):
                    # They're already decimal
                    try:
                        recipient_lat = float(recipient_site['latitude'])
                        recipient_lng = float(recipient_site['longitude'])
                        logger.info(f"Recipient coordinates already in decimal format: {recipient_lat}, {recipient_lng}")
                    except (ValueError, TypeError):
                        # Fallback to using convert_dms_to_decimal
                        logger.warning(f"Failed to directly convert recipient coordinates as decimal, trying DMS conversion")
                        recipient_lat, recipient_lng = convert_dms_to_decimal(recipient_site['latitude'], recipient_site['longitude'])
                        logger.info(f"Converted recipient coordinates via DMS converter: {recipient_lat}, {recipient_lng}")
                else:
                    # Convert from DMS format
                    try:
                        recipient_lat, recipient_lng = convert_dms_to_decimal(recipient_site['latitude'], recipient_site['longitude'])
                        logger.info(f"Converted recipient coordinates from DMS: {recipient_lat}, {recipient_lng}")
                    except Exception as e:
                        logger.error(f"Error converting recipient coordinates: {e}", exc_info=True)
                        messagebox.showerror("Coordinate Error", f"Failed to convert recipient coordinates: {str(e)}")
                        return

            # Validate converted coordinates
            if (donor_lat == 0 and donor_lng == 0) or (recipient_lat == 0 and recipient_lng == 0):
                error_msg = "Coordinates converted to 0,0 - likely invalid format"
                logger.error(error_msg)
                messagebox.showerror("Coordinate Error", error_msg)
                return

            logger.info(f"Final coordinates for map: Donor ({donor_lat}, {donor_lng}), Recipient ({recipient_lat}, {recipient_lng})")

            # Get site names
            donor_name = donor_site.get('site_id', 'Donor Site')
            recipient_name = recipient_site.get('site_id', 'Recipient Site')

            # Get frequency from general parameters
            frequency_ghz = 11.0  # Default value
            if tower_data and 'general_parameters' in tower_data and 'frequency_ghz' in tower_data['general_parameters']:
                frequency_ghz = float(tower_data['general_parameters']['frequency_ghz'])

            # Get additional site data if available
            donor_elevation = donor_site.get('elevation_ft')
            donor_antenna_height = donor_site.get('antenna_cl_ft')
            donor_azimuth = donor_site.get('azimuth_deg')

            recipient_elevation = recipient_site.get('elevation_ft')
            recipient_antenna_height = recipient_site.get('antenna_cl_ft')
            recipient_azimuth = recipient_site.get('azimuth_deg')

            # Get lidar data if available
            lidar_data = None
            if tower_data and 'lidar_data' in tower_data:
                # Process lidar data with individual lidar files
                lidar_data = {}

                # Process each project
                for project_name, project_info in tower_data['lidar_data'].items():
                    # Create a new entry for this project
                    lidar_data[project_name] = {
                        'name': project_info.get('name', project_name),
                        'title': project_info.get('title', project_name),
                        'download_url': project_info.get('download_url', ''),
                        'files': []  # Initialize files array
                    }

                    # If the project has its own bounds, use them
                    if 'bounds' in project_info:
                        lidar_data[project_name]['bounds'] = project_info['bounds']

                        # Add the project itself as a file if it has bounds
                        lidar_data[project_name]['files'].append({
                            'name': project_info.get('name', project_name),
                            'title': project_info.get('title', ''),
                            'bounds': project_info['bounds'],
                            'download_url': project_info.get('download_url', '')
                        })

                    # Check for embedded file array within the project
                    if 'files' in project_info and isinstance(project_info['files'], list):
                        for file_data in project_info['files']:
                            if 'bounds' in file_data:
                                file_entry = {
                                    'name': file_data.get('filename', file_data.get('name', '')),
                                    'title': file_data.get('title', ''),
                                    'bounds': file_data['bounds'],
                                    'download_url': file_data.get('download_url', '')
                                }
                                lidar_data[project_name]['files'].append(file_entry)

                # Log the processed data
                total_files = sum(len(project['files']) for project in lidar_data.values())
                logger.info(f"Processed {len(lidar_data)} lidar projects with a total of {total_files} individual lidar files")

            # Ensure the map file exists with the correct API key
            if not ensure_map_file():
                logger.error("Could not prepare map file")
                messagebox.showerror("Error", "Could not prepare map file")
                return

            # Start a fresh server instance
            server_address = map_server.start_server()
            if not server_address:
                logger.error("Failed to start map server")
                messagebox.showerror("Error", "Failed to start map server")
                return

            # Update coordinates in the server
            map_server.update_coordinates(
                donor_lat=donor_lat,
                donor_lng=donor_lng,
                donor_name=donor_name,
                recipient_lat=recipient_lat,
                recipient_lng=recipient_lng,
                recipient_name=recipient_name,
                frequency_ghz=frequency_ghz,
                donor_elevation=donor_elevation,
                donor_antenna_height=donor_antenna_height,
                donor_azimuth=donor_azimuth,
                recipient_elevation=recipient_elevation,
                recipient_antenna_height=recipient_antenna_height,
                recipient_azimuth=recipient_azimuth,
                lidar_data=lidar_data
            )

            # Open the map in the browser
            map_server.open_map()

            logger.info("Map view opened successfully")

        except Exception as e:
            logger.error(f"Error in coordinate processing: {e}", exc_info=True)
            messagebox.showerror("Error", f"Error processing coordinates: {str(e)}")

    except Exception as e:
        logger.error(f"Error creating map view: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to create map view: {str(e)}")

# Add direct call with better error handling
if __name__ == "__main__":
    # Configure logs to display on console
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                       force=True)  # Override any existing configurations

    # Load Google Maps API key from .env file if it exists
    try:
        import dotenv
        logger.info("Loading .env file if available...")
        dotenv.load_dotenv()
    except ImportError:
        logger.warning("dotenv module not installed, skipping environment loading")

    logger.info("Starting map view...")

    # Try to make sure tower_parameters.json exists
    if not os.path.exists('tower_parameters.json'):
        logger.error("tower_parameters.json not found!")
    else:
        logger.info(f"Found tower_parameters.json in {os.path.abspath('tower_parameters.json')}")

    # Call view_on_map function with try/except
    try:
        logger.info("Calling view_on_map function...")
        view_on_map()
        logger.info("view_on_map function completed")
    except Exception as e:
        logger.error(f"Error running view_on_map: {e}", exc_info=True)