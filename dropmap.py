import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkintermapview
import logging
import math
from math import sin, cos, radians, atan2, asin, pi, sqrt, degrees
import os
import time
import csv
import json
import re
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from PIL import ImageGrab, Image, ImageTk
from datetime import date, datetime
from tkcalendar import DateEntry
import requests
from io import StringIO
import matplotlib.cm as cm
from functools import partial
import threading
import queue
import zipfile
import shutil
import platform
import atexit
from utilities.cleanup_utils import cleanup_all, ignore_ds_store
from utilities.temp_dir_manager import get_temp_dir, get_temp_file, copy_to_output_dir, cleanup_all_temp_dirs
from utilities.finder_utils import safe_open_directory, safe_open_file
import warnings
import tempfile
import sys
import subprocess
import threading
from threading import Thread
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
from dotenv import load_dotenv

# Import project modules
from utilities.UI_main import MainUI, ManualSitesDialog
from utilities.turbine_processor import TurbineProcessor
from utilities.ai_processor import process_document_with_ai
from utilities.elevation import ElevationProfile
from log_config import setup_logging, initialize_logging
from DL2 import UltraVerboseDownloaderer
from utilities.geometry import calculate_polygon_points, export_search_polygon_as_kml, export_search_polygon_as_shapefile, export_search_polygon, export_polygon, export_polygon_as_kml, export_polygon_as_shapefile
from utilities.coordinates import convert_dms_to_decimal as coords_convert_dms_to_decimal
from utilities.coordinates import dms_to_decimal as coords_dms_to_decimal

# Initialize centralized logging
initialize_logging()
from utilities.coordinates import calculate_distance, calculate_distance_meters
from utilities.metadata import ProjectMetadata, get_project_name
from utilities.site_manager import update_json_file, open_manual_sites, edit_sites, load_site_data
from utilities.file_handler import reset_json_file_for_new_project
from utilities.map_manager import MapController
from utilities.pdf_utils import create_certificate, create_json_certificate, add_section_header, add_field
import utilities.pdf_utils as certificates
from utilities.visualization_utils import generate_ring_points, generate_ring_stack, export_search_rings, generate_fresnel_zone
from utilities.search_rings import SearchRingGenerator
from utilities.ui_dialogs import ProjectSelectionDialog, ExportProgressDialog
from utilities.lidar_map_visualization import initialize_map_widget, MapControlPanel, MapStyleManager, LidarVisualizer
from utilities.point_search import search_lidar_by_points as point_search
from utilities.lidar_index_search import search_lidar_index, database_exists
from utilities.aws_download_handler import show_aws_download_dialog
from utilities.ai_path_analyze import run_multi_source_analysis
from utilities.json_loader import load_json_results as load_json_data
from utilities.tower_database import ensure_tower_database_exists, search_towers_in_polygon
from utilities.tnm_parser import parse_tnm_response

# Import project-specific modules that might not exist in the UI_main file
try:
    from projects import ProjectDetailsPane
except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.error(f"Could not import some modules: {e}")

# Create logger
logger = setup_logging(__name__)

# Site management functions are now in utilities/site_manager.py

# Global variables to track markers, path, and polygon
donor_marker = None
recipient_marker = None
path_between_sites = None
polygon_around_path = None
polygon_points = None

# Load environment variables
load_dotenv()

# update_json_file function moved to utilities/site_manager.py

def import_tower_parameters_json():
    """Import data from an existing tower_parameters.json file"""
    try:
        # Open file dialog to select tower_parameters.json file
        from tkinter import filedialog
        
        file_path = filedialog.askopenfilename(
            title="Select tower_parameters.json file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir="."
        )
        
        if not file_path:
            logger.info("User cancelled JSON import")
            return
            
        logger.info(f"Importing tower parameters from: {file_path}")
        
        # Load the JSON data
        import json
        with open(file_path, 'r') as f:
            imported_data = json.load(f)
        
        # Validate that it has the required structure
        if not all(key in imported_data for key in ['site_A', 'site_B', 'general_parameters']):
            messagebox.showerror("Invalid File", 
                               "The selected file does not appear to be a valid tower_parameters.json file.\n"
                               "Required sections: site_A, site_B, general_parameters")
            return
            
        # Reset the project JSON file to ensure a clean state
        if not reset_json_file_for_new_project():
            logger.warning("Failed to reset JSON file, but proceeding.")

        # Clear existing LIDAR data and turbines from the map
        if 'lidar_downloader' in globals() and lidar_downloader:
            logger.info("Clearing existing data before importing new file.")
            lidar_downloader.clear_all_data()
        
        # Update the main JSON file with the imported data
        if not update_json_file(imported_data):
            messagebox.showerror("Import Failed", "Failed to update the project's main JSON file with the imported data.")
            return

        logger.info("Successfully imported tower parameters. Updating application.")
        
        # Update the application's UI with the imported data (same as AI workflow)
        update_details_in_app(imported_data)

        # Automatically check for turbines in the default search area (same as AI workflow)
        logger.info("JSON import complete. Checking for turbines in default search area...")
        
        try:
            if 'lidar_downloader' in globals() and lidar_downloader:
                # Run automatic turbine search to alert user if turbines are found
                turbines_found = lidar_downloader.find_turbines()
                
                if turbines_found and len(turbines_found) > 0:
                    turbine_count = len(turbines_found)
                    search_width = lidar_downloader.polygon_width_ft.get() if hasattr(lidar_downloader, 'polygon_width_ft') else 2000
                    
                    # Show alert about found turbines
                    alert_message = (
                        f"🚨 TURBINES DETECTED!\n\n"
                        f"Found {turbine_count} wind turbine{'s' if turbine_count != 1 else ''} "
                        f"within ±{search_width}ft of your path.\n\n"
                        f"⚠️  These may require clearance analysis.\n\n"
                        f"The turbines are now displayed on the map and elevation profile. "
                        f"Use 'Search Towers' to find additional obstructions if needed."
                    )
                    
                    # Use a warning messagebox to make it prominent
                    messagebox.showwarning("Turbines Found in Path Area", alert_message)
                    logger.info(f"Automatic turbine search found {turbine_count} turbines - user alerted")
                else:
                    logger.info("No turbines found in automatic search")
        except Exception as turbine_error:
            logger.error(f"Error during automatic turbine search: {turbine_error}")
            # Don't show error to user since the main import was successful
                    
        logger.info("Tower parameters JSON import completed successfully")
        
    except FileNotFoundError:
        messagebox.showerror("File Not Found", f"Could not find the selected file: {file_path}")
    except json.JSONDecodeError as e:
        messagebox.showerror("Invalid JSON", f"The selected file is not valid JSON:\n{str(e)}")
    except Exception as e:
        logger.error(f"Error importing tower parameters JSON: {str(e)}", exc_info=True)
        messagebox.showerror("Import Error", f"An error occurred while importing the JSON file:\n{str(e)}")

def update_details_in_app(extracted_data):
    """Update the application with extracted data"""
    try:
        logger.info("Updating map with coordinates: A{}, B{}".format(
            extracted_data['site_A'],
            extracted_data['site_B']
        ))

        # Update the LidarDownloader with site data
        lidar_downloader.update_site_data(
            extracted_data['site_A'],
            extracted_data['site_B']
        )

        # Update map and other UI elements
        update_map(extracted_data['site_A'], extracted_data['site_B'])

        # Update Site A details
        site_a = extracted_data['site_A']
        donor_site_name.set(f"Site Name: {site_a['site_id']}")
        donor_latitude.set(f"Latitude: {site_a['latitude']}")
        donor_longitude.set(f"Longitude: {site_a['longitude']}")
        donor_azimuth.set(f"Azimuth: {site_a['azimuth_deg']}°")
        donor_elevation.set(f"Elevation: {site_a['elevation_ft']} ft")
        donor_antenna_cl.set(f"Antenna CL: {site_a['antenna_cl_ft']} ft")

        # Update Site B details
        site_b = extracted_data['site_B']
        recipient_site_name.set(f"Site Name: {site_b['site_id']}")
        recipient_latitude.set(f"Latitude: {site_b['latitude']}")
        recipient_longitude.set(f"Longitude: {site_b['longitude']}")
        recipient_azimuth.set(f"Azimuth: {site_b['azimuth_deg']}°")
        recipient_elevation.set(f"Elevation: {site_b['elevation_ft']} ft")
        recipient_antenna_cl.set(f"Antenna CL: {site_b['antenna_cl_ft']} ft")

        # Update general parameters
        general = extracted_data['general_parameters']
        project_path_length.set(f"Path Length: {general['path_length_mi']} mi")

        # Optionally, you can add a message to inform the user that the data has been updated
        messagebox.showinfo("Update Successful", "Site details have been updated successfully!")

    except Exception as e:
        logger.error(f"Error updating details: {str(e)}", exc_info=True)
        show_error(f"Error updating details: {str(e)}")

def update_map(site_a, site_b):
    """Update the map with the new site locations"""
    global donor_marker, recipient_marker, path_between_sites, polygon_around_path

    try:
        logger.info(f"Updating map with coordinates: A{site_a}, B{site_b}")
        lat_a, lon_a = coords_convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
        lat_b, lon_b = coords_convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])

        # Log the converted coordinates
        logger.info(f"Converted coordinates: A({lat_a}, {lon_a}), B({lat_b}, {lon_b})")

        # Remove existing markers and paths if they exist
        map_widget.delete_all_marker()
        map_widget.delete_all_path()
        map_widget.delete_all_polygon()

        # Create markers with correct parameters
        donor_marker = map_widget.set_marker(
            lat_a, lon_a,
            text=f"Donor Site\n{lat_a:.6f}, {lon_a:.6f}",
            text_color="black",
            marker_color_outside="blue",
            marker_color_circle="white"
        )

        recipient_marker = map_widget.set_marker(
            lat_b, lon_b,
            text=f"Recipient Site\n{lat_b:.6f}, {lon_b:.6f}",
            text_color="black",
            marker_color_outside="red",
            marker_color_circle="white"
        )

        # Draw path between sites in black
        path_between_sites = map_widget.set_path([
            (lat_a, lon_a),
            (lat_b, lon_b)
        ], color="black", width=2)

        # Calculate and draw polygon around path with black border, extending 200 feet past both sites
        # Use current UI polygon width setting instead of hardcoded 2000ft
        polygon_width = lidar_downloader.polygon_width_ft.get() if lidar_downloader else 2000
        polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), polygon_width)
        polygon_around_path = map_widget.set_polygon(
            polygon_points,
            fill_color=None,
            outline_color="black",
            border_width=1,  # Thinner line to make it less prominent
            name="LOS Polygon"
        )

        # Center map view
        center_lat = (lat_a + lat_b) / 2
        center_lon = (lon_a + lon_b) / 2
        map_widget.set_position(center_lat, center_lon)
        map_widget.set_zoom(11)

        # Update elevation profile
        elevation_profile.update_profile(
            start_coords=(lat_a, lon_a),
            end_coords=(lat_b, lon_b),
            site_a_elev=site_a['elevation_ft'] + site_a['antenna_cl_ft'],
            site_b_elev=site_b['elevation_ft'] + site_b['antenna_cl_ft'],
            site_a_id=site_a['site_id'],
            site_b_id=site_b['site_id']
        )

        # Update LIDAR search area
        if lidar_downloader:
            lidar_downloader.set_polygon_points(polygon_points)

    except Exception as e:
        error_msg = f"Error updating map: {str(e)}"
        logger.error(error_msg, exc_info=True)
        show_error(error_msg)

# Function moved to utilities/coordinates.py

def polygon_click(polygon):
    """
    Handle click event on the polygon.
    """
    logger.info(f"Polygon clicked: {polygon.name}")
    messagebox.showinfo("Polygon Info", "This is the Line of Sight polygon for the microwave link.")

def display_address_info(coords, is_donor):
    """
    Display address information for the given coordinates.
    """
    try:
        address = tkintermapview.convert_coordinates_to_address(coords[0], coords[1])
        if is_donor:
            donor_address.set(f"Donor Address: {address.street}, {address.city}, {address.country}")
        else:
            recipient_address.set(f"Recipient Address: {address.street}, {address.city}, {address.country}")
    except Exception as e:
        logger.error(f"Error getting address info: {str(e)}", exc_info=True)

# Function moved to utilities/map_manager.py

# Function moved to utilities/coordinates.py

# Function moved to utilities/coordinates.py

# Function moved to utilities/coordinates.py

# Function moved to utilities/geometry.py

def on_file_drop(event):
    """
    Handle file drop events using the safer, modernized drag-drop handler.
    This function now directly calls the Gemini-powered AI processor.
    """
    from utilities.drag_drop_handler import safe_handle_drop
    from utilities.file_operation_utils import safe_copy_file
    from utilities.temp_dir_manager import get_temp_dir
    from utilities.ai_processor import process_document_with_ai
    from utilities.file_handler import update_json_file, reset_json_file_for_new_project
    from utilities.drag_drop_handler import reset_processing_state

    def process_dropped_file(original_path):
        """
        The core logic for processing a file, designed to be called by the
        safe drag-drop handler.
        """
        try:
            # Create a safe copy in a temporary directory to avoid file system locks
            temp_dir = get_temp_dir(prefix="lostool_drop_")
            temp_file_path = os.path.join(temp_dir, os.path.basename(original_path))
            
            logger.info(f"Making a safe copy of dropped file to: {temp_file_path}")
            if not safe_copy_file(original_path, temp_file_path):
                show_error("Failed to create a safe copy of the dropped file. Please try again.")
                return

            # Reset the project JSON file to ensure a clean state
            if not reset_json_file_for_new_project():
                logger.warning("Failed to reset JSON file, but proceeding.")

            # Clear existing LIDAR data and turbines from the map
            if 'lidar_downloader' in globals() and lidar_downloader:
                logger.info("Clearing existing data before processing new file.")
                lidar_downloader.clear_all_data()

            # Process the document with the new Gemini AI processor
            logger.info("Calling the Gemini 1.5 Pro AI processor.")
            extracted_data = process_document_with_ai(temp_file_path)

            if not extracted_data:
                show_error("The AI processor could not extract the necessary data from the document.")
                return

            logger.info("Successfully extracted data with Gemini. Updating application.")
            
            # The new AI processor returns data in the final format,
            # so no complex conversion is needed here.
            
            # Update the main JSON file with the new data
            if not update_json_file(extracted_data):
                show_error("Failed to update the project's main JSON file with the extracted data.")
                return

            # Update the application's UI with the new data
            update_details_in_app(extracted_data)

            # Automatically check for turbines in the default search area
            logger.info("PDF processing complete. Checking for turbines in default search area...")
            
            try:
                if 'lidar_downloader' in globals() and lidar_downloader:
                    # Run automatic turbine search to alert user if turbines are found
                    turbines_found = lidar_downloader.find_turbines()
                    
                    if turbines_found and len(turbines_found) > 0:
                        turbine_count = len(turbines_found)
                        search_width = lidar_downloader.polygon_width_ft.get() if hasattr(lidar_downloader, 'polygon_width_ft') else 2000
                        
                        # Show alert about found turbines
                        alert_message = (
                            f"🚨 TURBINES DETECTED!\n\n"
                            f"Found {turbine_count} wind turbine{'s' if turbine_count != 1 else ''} "
                            f"within ±{search_width}ft of your path.\n\n"
                            f"⚠️  These may require clearance analysis.\n\n"
                            f"The turbines are now displayed on the map and elevation profile. "
                            f"Use 'Search Towers' to find additional obstructions if needed."
                        )
                        
                        # Use a warning messagebox to make it prominent
                        messagebox.showwarning("Turbines Found in Path Area", alert_message)
                        logger.info(f"Automatic turbine search found {turbine_count} turbines - user alerted")
                    else:
                        logger.info("Automatic turbine search completed - no turbines found in search area")
                        # Show brief info message for no turbines found
                        messagebox.showinfo("Turbine Search Complete", 
                                          "✅ No wind turbines found in the default search area.\n\n"
                                          "Use 'Search Turbines' to adjust search width or 'Search Towers' "
                                          "to find other potential obstructions.")
                else:
                    logger.warning("Lidar downloader not available for automatic turbine search")
                    
            except Exception as e:
                logger.error(f"Error during automatic turbine search: {e}", exc_info=True)
                # Don't show error to user - just log it and continue
                
            logger.info("Use 'Search Turbines' to adjust search parameters or 'Search Towers' for additional obstructions.")

        except Exception as e:
            logger.error(f"An error occurred during file processing: {e}", exc_info=True)
            show_error(f"A critical error occurred while processing the file: {e}")
        finally:
            # Always reset the processing state to allow for new file drops
            reset_processing_state()

    # Pass the file processing logic to the safe handler
    safe_handle_drop(event, process_dropped_file)

def show_error(message):
    """
    Display an error message in a popup window.
    """
    logger.error(f"Showing error message: {message}")
    messagebox.showerror("Error", message)

def clear_data():
    """
    Clear all displayed data and reset the map.
    """
    logger.info("Clearing all data")
    global donor_marker, recipient_marker, path_between_sites, polygon_around_path, polygon_points

    # Clear project details
    project_link_id.set("")
    project_link_name.set("")
    project_path_length.set("")

    # Clear donor details
    donor_latitude.set("")
    donor_longitude.set("")
    donor_azimuth.set("")
    donor_elevation.set("")
    donor_antenna_cl.set("")
    donor_address.set("")

    # Clear recipient details
    recipient_latitude.set("")
    recipient_longitude.set("")
    recipient_azimuth.set("")
    recipient_elevation.set("")
    recipient_antenna_cl.set("")
    recipient_address.set("")

    # Skip clearing distance label as it's handled elsewhere

    # Clear map
    logger.debug("Clearing map elements")
    map_widget.delete_all_marker()
    map_widget.delete_all_path()
    map_widget.delete_all_polygon()

    # Reset map view
    logger.debug("Resetting map view")
    map_widget.set_position(0, 0)
    map_widget.set_zoom(1)

    # Clear polygon points
    polygon_points = None

def generate_polygon_kml(polygon_points):
    """
    Generate KML content for the polygon.
    """
    kml_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Microwave LOS Polygon</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              {' '.join([f'{lon},{lat},0' for lat, lon in polygon_points])}
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
  </Document>
</kml>'''
    return kml_content

def export_kml():
    """
    Export the polygon as a KML file using the lidar_map module.
    """
    global polygon_points, lidar_downloader

    # If lidar_downloader is available, use it
    if lidar_downloader and hasattr(lidar_downloader, 'polygon_points') and lidar_downloader.polygon_points:
        logger.info("Using LidarDownloader to export KML")
        lidar_downloader.export_search_polygon_as_kml()
    # Otherwise fallback to global polygon_points
    elif polygon_points:
        logger.info("Using global polygon_points to export KML")
        # Get site IDs if available via lidar_downloader
        site_a_id = None
        site_b_id = None
        if lidar_downloader:
            site_a_id = lidar_downloader.donor_site.get('site_id') if lidar_downloader.donor_site else None
            site_b_id = lidar_downloader.recipient_site.get('site_id') if lidar_downloader.recipient_site else None

        # Use site IDs in export if available
        if site_a_id and site_b_id:
            export_polygon(polygon_points, site_a_id, site_b_id)
        else:
            export_polygon_as_kml(polygon_points)
    else:
        logger.warning("No polygon data available for export.")
        messagebox.showwarning("No Data", "Please load a project first.")

def export_poly():
    """
    Export the polygon as both KML and shapefile using the lidar_map module.
    """
    global polygon_points, lidar_downloader

    # If lidar_downloader is available, use it
    if lidar_downloader and hasattr(lidar_downloader, 'polygon_points') and lidar_downloader.polygon_points:
        logger.info("Using LidarDownloader to export polygon in multiple formats")
        lidar_downloader.export_search_polygon()
    # Otherwise fallback to global polygon_points
    elif polygon_points:
        logger.info("Using global polygon_points to export polygon in multiple formats")
        # Get site IDs if available via lidar_downloader
        site_a_id = None
        site_b_id = None
        if lidar_downloader:
            site_a_id = lidar_downloader.donor_site.get('site_id') if lidar_downloader.donor_site else None
            site_b_id = lidar_downloader.recipient_site.get('site_id') if lidar_downloader.recipient_site else None

        export_polygon(polygon_points, site_a_id, site_b_id)
    else:
        logger.warning("No polygon data available for export.")
        messagebox.showwarning("No Data", "Please load a project first.")

# Global export functions for menu
def export_shapefile():
    """
    Export the polygon as a shapefile using the lidar_map module.
    """
    global polygon_points, lidar_downloader

    # If lidar_downloader is available, use it
    if lidar_downloader and hasattr(lidar_downloader, 'polygon_points') and lidar_downloader.polygon_points:
        logger.info("Using LidarDownloader to export shapefile")
        lidar_downloader.export_search_polygon_as_shapefile()
    # Otherwise fallback to global polygon_points
    elif polygon_points:
        logger.info("Using global polygon_points to export shapefile")
        # Get site IDs if available via lidar_downloader
        site_a_id = None
        site_b_id = None
        if lidar_downloader:
            site_a_id = lidar_downloader.donor_site.get('site_id') if lidar_downloader.donor_site else None
            site_b_id = lidar_downloader.recipient_site.get('site_id') if lidar_downloader.recipient_site else None

        # Use site IDs in export if available
        if site_a_id and site_b_id:
            export_polygon(polygon_points, site_a_id, site_b_id)
        else:
            export_polygon_as_shapefile(polygon_points)
    else:
        logger.warning("No polygon data available for export.")
        messagebox.showwarning("No Data", "Please load a project first.")

def fetch_metadata(item_id):
    """Fetch metadata from ScienceBase."""
    try:
        logger.info(f"Fetching metadata for item ID: {item_id}")
        url = f"https://www.sciencebase.gov/catalog/item/{item_id}?format=json"

        logger.debug(f"Making request to: {url}")
        response = requests.get(url)

        if response.status_code == 200:
            logger.info("Successfully fetched metadata from ScienceBase")
            metadata = response.json()

            # Log key metadata fields for debugging
            logger.debug(f"Title: {metadata.get('title')}")
            logger.debug(f"Dates count: {len(metadata.get('dates', []))}")
            logger.debug(f"Contacts count: {len(metadata.get('contacts', []))}")
            logger.debug(f"Web links count: {len(metadata.get('webLinks', []))}")

            return metadata
        else:
            logger.error(f"Failed to fetch metadata. Status code: {response.status_code}")
            logger.error(f"Response content: {response.text}")
            return None

    except Exception as e:
        logger.error(f"Error fetching metadata: {e}", exc_info=True)
        return None

def extract_metadata(metadata):
    """Extract metadata from ScienceBase response"""
    try:
        logger.info("Starting metadata extraction")
        logger.debug(f"Raw metadata: {json.dumps(metadata, indent=2)}")

        info = {
            'title': metadata.get('title', 'N/A'),
            'summary': metadata.get('summary', 'N/A'),
            'dates': {
                'Start': metadata.get('startDate', 'N/A'),
                'End': metadata.get('endDate', 'N/A'),
                'Publication': metadata.get('publicationDate', 'N/A')
            }
        }

        # Extract spatial information
        spatial = metadata.get('spatial', {})
        if spatial:
            logger.info("Found spatial information")
            bounds = {
                'minX': spatial.get('boundingBox', {}).get('minX'),
                'maxX': spatial.get('boundingBox', {}).get('maxX'),
                'minY': spatial.get('boundingBox', {}).get('minY'),
                'maxY': spatial.get('boundingBox', {}).get('maxY')
            }
            info['bounds'] = bounds
            logger.info(f"Extracted bounds: {bounds}")

        # Extract web links
        web_links = metadata.get('webLinks', [])
        xml_data = None
        for link in web_links:
            if link.get('type') == 'originalMetadata' and link.get('title') == 'Product Metadata':
                try:
                    xml_url = link.get('uri')
                    logger.info(f"Found XML metadata URL: {xml_url}")
                    response = requests.get(xml_url)
                    if response.status_code == 200:
                        xml_data = ET.fromstring(response.text)
                        logger.info("Successfully fetched XML metadata")
                except Exception as e:
                    logger.error(f"Error fetching XML metadata: {e}")

        if xml_data:
            # Extract quality information
            quality = {}
            quality_info = xml_data.find('.//dataqual')
            if quality_info is not None:
                logger.info("Found quality information in XML")
                quality.update({
                    'vertical_accuracy': quality_info.findtext('.//vertacc/vertaccv', 'N/A'),
                    'horizontal_accuracy': quality_info.findtext('.//horizpa/horizpar', 'N/A'),
                    'logical_consistency': quality_info.findtext('.//logic', 'N/A'),
                    'completeness': quality_info.findtext('.//complete', 'N/A')
                })
                info['quality'] = quality
                logger.info(f"Extracted quality info: {quality}")

            # Extract collection parameters
            collection = {}
            lidar_info = xml_data.find('.//lidar')
            if lidar_info is not None:
                logger.info("Found LIDAR collection information in XML")
                collection.update({
                    'type': lidar_info.findtext('.//colltype', 'N/A'),
                    'sensor': lidar_info.findtext('.//instype', 'N/A'),
                    'platform': lidar_info.findtext('.//platform', 'N/A'),
                    'flying_height': lidar_info.findtext('.//flightheight', 'N/A'),
                    'scan_angle': lidar_info.findtext('.//scanangle', 'N/A'),
                    'pulse_rate': lidar_info.findtext('.//pulserate', 'N/A'),
                    'point_spacing': lidar_info.findtext('.//pointspacing', 'N/A'),
                    'point_density': lidar_info.findtext('.//pointdensity', 'N/A')
                })
                info['collection'] = collection
                logger.info(f"Extracted collection parameters: {collection}")

            # Extract spatial reference
            spref = xml_data.find('.//spref')
            if spref is not None:
                logger.info("Found spatial reference information in XML")
                spatial_ref = {'coordinate_system': {}, 'datum': {}}

                # Extract coordinate system info
                horizsys = spref.find('.//horizsys')
                if horizsys is not None:
                    planar = horizsys.find('.//planar')
                    if planar is not None:
                        gridsys = planar.find('.//gridsys')
                        if gridsys is not None:
                            spatial_ref['coordinate_system'].update({
                                'name': gridsys.findtext('gridsysn', 'N/A'),
                                'zone': gridsys.findtext('.//zone', 'N/A'),
                                'units': planar.findtext('.//plandu', 'N/A')
                            })

                            # Try to extract EPSG code
                            system_name = gridsys.findtext('gridsysn', '')
                            if 'EPSG' in system_name:
                                epsg_code = re.search(r'EPSG:(\d+)', system_name)
                                if epsg_code:
                                    spatial_ref['coordinate_system']['epsg_code'] = epsg_code.group(1)

                # Extract datum info
                geodetic = spref.find('.//geodetic')
                if geodetic is not None:
                    spatial_ref['datum'].update({
                        'horizontal_datum': geodetic.findtext('horizdn', 'N/A'),
                        'vertical_datum': geodetic.findtext('vertdef/altsys/altdatum', 'N/A'),
                        'ellipsoid': geodetic.findtext('ellips', 'N/A')
                    })

                info['spatial_ref'] = spatial_ref
                logger.info(f"Extracted spatial reference: {spatial_ref}")

        # Extract contacts
        contacts = metadata.get('contacts', [])
        if contacts:
            logger.info("Found contact information")
            contact_info = {}
            for contact in contacts:
                contact_type = contact.get('type', '').lower()
                if contact_type == 'originator':
                    contact_info['data_source'] = contact.get('name', 'N/A')
                elif contact_type == 'distributor':
                    contact_info['distributor'] = contact.get('name', 'N/A')
            info['contacts'] = contact_info
            logger.info(f"Extracted contacts: {contact_info}")

        logger.info("Metadata extraction completed successfully")
        return info

    except Exception as e:
        logger.error(f"Error extracting metadata: {e}", exc_info=True)
        return {}

# PDF utility functions moved to utilities/pdf_utils.py

# Visualization utility functions moved to utilities/visualization_utils.py

def get_project_metadata(project_name):
    """Get the metadata for a specific project"""
    if not project_name:
        return {}

    metadata_file = os.path.join('tower_parameters.json')
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                data = json.load(f)

            # Get project specific metadata
            for project, project_data in data.get('lidar', {}).get('projects', {}).items():
                if project == project_name:
                    return project_data
        except Exception as e:
            logger.error(f"Error loading project metadata: {str(e)}")

    return {}

# Define the ApplicationController class (formerly LidarDownloader)
class ApplicationController:
    def __init__(self, parent, map_widget=None, root=None, downloader=None):
        logger.info(f"Initializing ApplicationController with map_widget={map_widget}, root={root}")
        self.parent = parent
        self.map_widget = map_widget
        self.root = root  # Store the root window
        self.downloader = downloader

        # Initialize turbine processor
        self.turbine_processor = TurbineProcessor(map_widget, root)
        self.obstruction_text = None  # Will be set later

        # Set up variables
        self.polygon_width_ft = tk.IntVar(value=2000)
        # Add trace to update polygon when width changes
        self.polygon_width_ft.trace_add('write', self._on_width_change)

        self.polygon_points = None
        self.lidar_polygons = []
        self.selected_files = set()
        self.item_url_map = {}
        self.urls = []  # Store all URLs and their metadata
        self.item_display_order = []
        self.search_count = 0
        self.color_series = ["red", "blue", "green", "orange", "purple", "cyan", "magenta", "yellow", "brown", "pink"]
        self.elevation_profile = None
        self.donor_site = None
        self.recipient_site = None

        # Variables for turbine display that we now forward to TurbineProcessor
        self.show_turbine_labels = self.turbine_processor.show_turbine_labels

        # Initialize project metadata service
        self.project_metadata = ProjectMetadata()

        # Rest of your existing initialization code...
        self.lidar_polygons = []
        self.used_colors = set()
        self.selected_items = set()
        self.projects = {}
        self.spatial_reference_cache = {}
        self.transformer = None
        self.selected_lidar = None
        self.legend_items_frame = None
        self.legend_canvas = None

        # Create metadata instance first
        self.project_metadata = ProjectMetadata()

        # Then set up UI with the metadata instance
        self.setup_ui()

        # First, add a variable to track label visibility state in the LidarDownloader class initialization
        self.show_turbine_labels = tk.BooleanVar(value=False)  # Default to hidden labels

        # Add to existing initialization
        self.last_turbines = []  # Store last set of turbines for refreshing labels

        # Store reference to map_widget for AI analysis
        self.map_widget_ref = map_widget

    def set_downloader(self, downloader):
        """Set the downloader instance"""
        logger.info("Setting downloader instance")
        self.downloader = downloader

    def set_polygon_points(self, points):
        """Set the polygon points for the search area"""
        self.polygon_points = points

        # Also set in turbine processor
        self.turbine_processor.set_polygon_points(points)

    def export_project_certificates(self):
        """Export certificate for the currently selected project"""
        from utilities.certificate_generator import export_project_certificates
        export_project_certificates(self)

    def export_json_certificates(self):
        """Export certificates as JSON"""
        self._export_certificates('json')

    def export_pdf_certificates(self):
        """Export certificates as PDF"""
        self._export_certificates('pdf')

    def _export_certificates(self, format_type):
        """Export certificates for selected projects"""
        try:
            # Get selected projects
            project_selection = ProjectSelectionDialog(self.root, self.project_metadata.projects)
            if not project_selection.result:
                logger.info("Certificate export cancelled by user")
                return

            selected_projects = project_selection.result
            if not selected_projects:
                messagebox.showinfo("No Selection", "No projects selected for certificate export.")
                return

            logger.info(f"Exporting {format_type} certificates for {len(selected_projects)} projects")

            # Ensure output directory exists
            if not os.path.exists("test_output"):
                os.makedirs("test_output")

            # Show progress dialog
            progress = ExportProgressDialog(self.root, len(selected_projects))
            total_exported = 0
            failed_projects = []

            # Process each project
            for i, project_name in enumerate(selected_projects):
                try:
                    logger.info(f"Processing project: {project_name}")

                    # Get project data
                    project_data = self.project_metadata.get_project(project_name)
                    if not project_data:
                        logger.error(f"No metadata found for project: {project_name}")
                        failed_projects.append((project_name, "No metadata found"))
                        progress.update_progress(project_name, (i+1) / len(selected_projects) * 100)
                        continue

                    # Display progress
                    progress.update_progress(project_name, (i+1) / len(selected_projects) * 100)

                    # Count tiles for this project
                    tile_count = 0
                    for item in self.file_list.get_children():
                        values = self.file_list.item(item)['values']
                        if len(values) > 4 and values[4] == project_name:
                            tile_count += 1

                    # Include tile count in project info
                    if 'data' not in project_data:
                        project_data['data'] = {}
                    project_data['data']['tile_count'] = tile_count
                    project_data['tile_count'] = tile_count

                    # Add coverage map if needed
                    self._add_coverage_map_to_project(project_data)

                    # Generate certificate
                    logger.info(f"Generating {format_type} certificate for project: {project_name} with {tile_count} tiles")

                    if format_type == 'json':
                        # For JSON format
                        cert_path = certificates.create_json_certificate(project_data, "test_output")
                    else:
                        # For PDF format
                        cert_path = certificates.create_certificate(project_data, "test_output")

                    if cert_path:
                        total_exported += 1
                        logger.info(f"Successfully created certificate: {cert_path}")
                    else:
                        failed_projects.append((project_name, "Certificate creation failed"))
                        logger.error(f"Failed to create certificate for: {project_name}")
                except Exception as e:
                    failed_projects.append((project_name, str(e)))
                    logger.error(f"Error processing project {project_name}: {e}", exc_info=True)

            # Update final progress and show results
            progress.update_progress("Complete", 100)

            message = f"Successfully exported {total_exported} certificate(s)."
            if failed_projects:
                message += f"\n\nFailed to export {len(failed_projects)} project(s):"
                for project, reason in failed_projects:
                    message += f"\n- {project}: {reason}"

            messagebox.showinfo("Export Complete", message)

            # Open output directory
            if total_exported > 0:
                try:
                    os.startfile("test_output") if platform.system() == "Windows" else (
                        subprocess.call(["open", "test_output"]) if platform.system() == "Darwin"
                        else subprocess.call(["xdg-open", "test_output"])
                    )
                except Exception as e:
                    logger.error(f"Error opening output directory: {e}")

        except Exception as e:
            logger.error(f"Error exporting certificates: {e}", exc_info=True)
            messagebox.showerror("Export Error", f"An error occurred during export: {str(e)}")

    def _add_coverage_map_to_project(self, project_data):
        """Add a coverage map to the project data for certificate generation"""
        try:
            # Check if we have tower parameters
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    site_a = tower_params.get('site_A', {})
                    site_b = tower_params.get('site_B', {})
            except Exception as e:
                logger.warning(f"Could not load tower parameters: {e}")
                return

            # Extract bounds from project
            bounds = {}
            if 'bounds' in project_data:
                bounds = project_data['bounds']
            else:
                # If no bounds in project_data, collect from tiles
                all_tile_bounds = []
                project_name = project_data.get('name', '')

                for item in self.file_list.get_children():
                    values = self.file_list.item(item)['values']
                    if len(values) > 4 and values[4] == project_name:
                        bbox = values[5] if len(values) > 5 else None
                        if bbox and isinstance(bbox, dict):
                            all_tile_bounds.append(bbox)

                if all_tile_bounds:
                    # Calculate overall bounds from all tiles
                    bounds = {
                        'minY': min(b.get('minY', 90) for b in all_tile_bounds),
                        'maxY': max(b.get('maxY', -90) for b in all_tile_bounds),
                        'minX': min(b.get('minX', 180) for b in all_tile_bounds),
                        'maxX': max(b.get('maxX', -180) for b in all_tile_bounds)
                    }

            if not bounds or not all(k in bounds for k in ['minY', 'maxY', 'minX', 'maxX']):
                logger.warning(f"No valid bounds found for project")
                return

            # Add project name to bounds for the capture
            bounds['project_name'] = project_data.get('name', 'Unknown')

            # Capture coverage map
            coverage_map = self.capture_coverage_map(bounds, site_a, site_b)
            if coverage_map:
                logger.info("Successfully added coverage map to project data")
                project_data['map_image'] = coverage_map
                return True

            return False
        except Exception as e:
            logger.error(f"Error adding coverage map: {e}", exc_info=True)
            return False

    def on_item_click(self, event):
        """Handle item click in the file list"""
        try:
            region = self.file_list.identify("region", event.x, event.y)
            column = self.file_list.identify_column(event.x)

            if region == "cell" and column == "#1":  # Checkbox column
                item = self.file_list.identify_row(event.y)
                if item:
                    # Toggle checkbox
                    current_values = list(self.file_list.item(item)['values'])
                    current_values[0] = "✓" if current_values[0] != "✓" else ""
                    self.file_list.item(item, values=current_values)

                    # Update selection tracking
                    url = self.item_url_map.get(item)
                    if url:
                        if current_values[0] == "✓":
                            self.selected_files.add(url)
                            logger.info(f"Selected file: {url}")
                        else:
                            self.selected_files.discard(url)
                            logger.info(f"Deselected file: {url}")

                        logger.info(f"Total selected files: {len(self.selected_files)}")
                    else:
                        logger.warning(f"No URL found for item: {item}")

        except Exception as e:
            logger.error(f"Error handling item click: {str(e)}")

    def select_all(self):
        """Select all items in the file list"""
        try:
            # Get all items in the file list
            items = self.file_list.get_children()

            # Update each item's checkbox and selection state
            for item in items:
                # Update checkbox display
                current_values = list(self.file_list.item(item)['values'])
                current_values[0] = "✓"  # Set checkbox to checked
                self.file_list.item(item, values=current_values)

                # Get URL from item_url_map and add to selected files
                url = self.item_url_map.get(item)
                if url:
                    self.selected_files.add(url)
                    logger.debug(f"Added URL to selection: {url}")
                else:
                    logger.warning(f"No URL found for item {item}")

            logger.info(f"Selected all files: {len(self.selected_files)} total")

        except Exception as e:
            logger.error(f"Error in select_all: {str(e)}", exc_info=True)

    def deselect_all(self):
        """Deselect all items in the file list"""
        try:
            # Get all items in the file list
            items = self.file_list.get_children()

            # Update each item's checkbox and selection state
            for item in items:
                # Update checkbox display
                current_values = list(self.file_list.item(item)['values'])
                current_values[0] = ""  # Clear checkbox
                self.file_list.item(item, values=current_values)

            # Clear selected files set
            self.selected_files.clear()
            logger.info("Deselected all files")

        except Exception as e:
            logger.error(f"Error in deselect_all: {str(e)}", exc_info=True)

    def download_aws_files(self, aws_files):
        """Download files from AWS S3 using the AWS download handler"""
        try:
            logger.info(f"Preparing to download {len(aws_files)} files from AWS S3")

            # Get AWS credentials from environment variables
            aws_credentials = {
                'AWS_ACCESS_KEY_ID': os.environ.get('AWS_ACCESS_KEY_ID', ''),
                'AWS_SECRET_ACCESS_KEY': os.environ.get('AWS_SECRET_ACCESS_KEY', ''),
                'AWS_REGION': os.environ.get('AWS_REGION', 'us-west-2')
            }

            # Show the AWS download dialog
            show_aws_download_dialog(self.root, aws_files, aws_credentials)

        except Exception as e:
            logger.error(f"Error downloading AWS files: {str(e)}", exc_info=True)
            messagebox.showerror("AWS Download Error", f"Failed to download files from AWS: {str(e)}")
            return False

        return True

    def add_to_downloads(self):
        """Add selected items to the download queue with optimized bulk processing"""
        try:
            # Get selected files
            selected_files = self.get_selected_files()
            if not selected_files:
                messagebox.showwarning("No Selection", "Please select files to download.")
                return

            # Check if any of the selected files are from AWS
            aws_files = []
            regular_files = []

            for url in selected_files:
                # Get the item from the URL
                item = next((item for u, item in self.urls if u == url), None)
                if item and item.get('awsSource', False):
                    aws_files.append(item)
                else:
                    regular_files.append(url)

            # If we have AWS files, handle them separately
            if aws_files:
                logger.info(f"Found {len(aws_files)} AWS files to download")
                self.download_aws_files(aws_files)

            # If we have no regular files, return
            if not regular_files:
                return

            # Continue with regular files
            selected_files = regular_files

            # Show progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Adding Files to Download Queue")
            progress_dialog.geometry("400x150")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            # Add progress information
            info_label = ttk.Label(progress_dialog, text="Preparing files for download...", font=("Arial", 10, "bold"))
            info_label.pack(pady=10)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
            progress_bar.pack(fill="x", padx=20, pady=10)

            status_label = ttk.Label(progress_dialog, text="")
            status_label.pack(pady=5)

            def process_files():
                try:
                    # Prepare all file info upfront with metadata
                    file_info_list = []
                    total_files = len(selected_files)

                    for i, url in enumerate(selected_files):
                        try:
                            filename = url.split('/')[-1]
                            # Get file info from LIDAR metadata
                            item = next((item for u, item in self.urls if u == url), None)

                            if item:
                                # Extract all relevant metadata
                                info = {
                                    'filename': filename,
                                    'status': 'Queued',
                                    'progress': 0,
                                    'size_on_disk': 0,
                                    'total_size': item.get('sizeInBytes', 0),
                                    'metadata': {
                                        'project': item.get('project'),
                                        'source_id': item.get('sourceId'),
                                        'date': item.get('date'),
                                        'bounds': item.get('boundingBox'),
                                        'coordinate_system': item.get('spatialReference'),
                                        'resolution': item.get('resolution'),
                                        'quality': item.get('quality')
                                    }
                                }
                                file_info_list.append((url, filename, info))

                                # Update progress
                                progress = (i + 1) / total_files * 100
                                progress_var.set(progress)
                                status_label.config(text=f"Processing file {i + 1} of {total_files}")
                                progress_dialog.update()

                        except Exception as e:
                            logger.error(f"Error preparing info for {url}: {e}", exc_info=True)

                    # Bulk add all files at once
                    if file_info_list:
                        status_label.config(text="Adding files to download queue...")
                        progress_dialog.update()

                        added, skipped, errors = self.downloader.add_urls_bulk(file_info_list)

                        # Show completion message
                        message = f"Added {added} files to download queue."
                        if skipped > 0:
                            message += f"\n{skipped} files were skipped (already in queue)."
                        if errors > 0:
                            message += f"\n{errors} files had errors."

                        # Close dialog and show results
                        progress_dialog.after(1000, lambda: [
                            progress_dialog.destroy(),
                            messagebox.showinfo("Added to Downloads", message)
                        ])

                        # Clear selections
                        self.deselect_all()

                    else:
                        progress_dialog.destroy()
                        messagebox.showwarning("No Files", "No valid files to add to download queue.")

                except Exception as e:
                    logger.error(f"Error in process_files: {e}", exc_info=True)
                    progress_dialog.destroy()
                    messagebox.showerror("Error", f"Failed to process files: {str(e)}")

            # Start processing in a separate thread
            Thread(target=process_files, daemon=True).start()

        except Exception as e:
            logger.error(f"Error adding files to download queue: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add files to download queue: {str(e)}")

    def get_selected_files(self):
        """Return list of selected file URLs with improved error handling"""
        try:
            logger.info(f"Getting selected files from {len(self.selected_files)} selections")

            # The selected_files already contains URLs directly, so we can return them as a list
            selected_urls = list(self.selected_files)

            logger.info(f"Found {len(selected_urls)} valid URLs from selections")
            return selected_urls

        except Exception as e:
            logger.error(f"Error in get_selected_files: {e}", exc_info=True)
            return []

    def setup_ui(self):
        """Set up the user interface"""
        # Create main frame for center column
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill="both", expand=True)

        # LIDAR Search Frame at top
        self.lidar_frame = ttk.LabelFrame(self.main_frame, text="LIDAR Search")
        self.lidar_frame.pack(fill="x", padx=10, pady=5)

        # Create a more organized grid layout with 4 columns
        # Configure columns to have equal weights for better balance
        for i in range(4):
            self.lidar_frame.columnconfigure(i, weight=1)

        # Check if running on macOS for platform-specific adjustments
        is_macos = platform.system() == "Darwin"

        # Configure ttk styles for better date picker appearance
        style = ttk.Style()
        style.configure('DateEntry', relief='solid', borderwidth=2, padx=4, pady=4)
        style.map('DateEntry', relief=[('active', 'solid'), ('focus', 'solid')])

        # Tcl configuration for better popup handling on macOS - fixes z-order issues
        if is_macos:
            root = self.parent.winfo_toplevel()
            root.tk.eval("""
            # Configuration to ensure calendar popup always appears on top
            proc ensureOnTop {w} {
                # Ensure calendar popup appears on top by bringing it to front and making it topmost
                if {[winfo exists $w]} {
                    raise $w
                    wm attributes $w -topmost 1
                    after 100 [list wm attributes $w -topmost 0]
                }
            }

            # Bind this to all tkcalendar popups
            bind all <<CalendarSelected>> {
                ensureOnTop [winfo toplevel %W]
            }
            bind all <<TkcalendarOpened>> {
                ensureOnTop [winfo toplevel %W]
            }
            """)

        # Create a style for LIDAR search buttons
        style = ttk.Style()
        style.configure('LidarSearch.TButton', padding=(2, 1))

        # Row 0: Date selection and search width in a single row
        # Create a frame for the top row controls
        top_row_frame = ttk.Frame(self.lidar_frame)
        top_row_frame.grid(row=0, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        # Configure top row frame columns - 6 columns total
        # 0: Start Date label, 1: Start Date picker, 2: End Date label, 3: End Date picker, 4: Width label, 5: Width spinbox
        for i in range(6):
            top_row_frame.columnconfigure(i, weight=1)

        # Start Date
        ttk.Label(top_row_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.start_date = DateEntry(top_row_frame, width=12, background='darkblue',
                                  foreground='white', date_pattern='yyyy-mm-dd',
                                  borderwidth=2, relief="solid",
                                  selectmode='day',
                                  cursor="hand2",
                                  style='DateEntry')
        self.start_date.set_date(date(2000, 1, 1))
        self.start_date.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        # End Date
        ttk.Label(top_row_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.end_date = DateEntry(top_row_frame, width=12, background='darkblue',
                                foreground='white', date_pattern='yyyy-mm-dd',
                                borderwidth=2, relief="solid",
                                selectmode='day',
                                cursor="hand2",
                                style='DateEntry')
        self.end_date.set_date(date.today())
        self.end_date.grid(row=0, column=3, padx=5, pady=5, sticky='ew')

        # Search Width
        ttk.Label(top_row_frame, text="Search Width (ft):").grid(row=0, column=4, padx=5, pady=5, sticky="e")
        self.width_spinbox = ttk.Spinbox(
            top_row_frame,
            from_=500,
            to=10000,
            increment=100,
            width=8,
            textvariable=self.polygon_width_ft
        )
        self.width_spinbox.grid(row=0, column=5, padx=5, pady=5, sticky="ew")

        # Make sure DateEntry widgets are above other widgets
        self.start_date.winfo_toplevel().lift()
        self.end_date.winfo_toplevel().lift()

        # Add event bindings for better macOS compatibility
        def on_date_click(event):
            # Ensure calendar popup appears above other widgets
            widget = event.widget
            if isinstance(widget, DateEntry):
                # Delay lifting to ensure calendar popup is created
                widget.after(10, lambda: widget._top_cal.lift() if hasattr(widget, '_top_cal') and widget._top_cal else None)

                # macOS specific handling
                if is_macos:
                    # For macOS - ensure popup is visible by adjusting position if needed
                    def adjust_popup_position():
                        if hasattr(widget, '_top_cal') and widget._top_cal:
                            # Get screen dimensions
                            screen_width = widget.winfo_screenwidth()
                            screen_height = widget.winfo_screenheight()

                            # Get calendar popup position and size
                            cal_x = widget._top_cal.winfo_x()
                            cal_y = widget._top_cal.winfo_y()
                            cal_width = widget._top_cal.winfo_width()
                            cal_height = widget._top_cal.winfo_height()

                            # Check if popup is partially off-screen
                            if cal_x + cal_width > screen_width:
                                # Adjust x position
                                new_x = max(0, screen_width - cal_width)
                                widget._top_cal.geometry(f"+{new_x}+{cal_y}")

                            if cal_y + cal_height > screen_height:
                                # Adjust y position
                                new_y = max(0, screen_height - cal_height)
                                widget._top_cal.geometry(f"+{cal_x}+{new_y}")

                            # Ensure it's on top
                            widget._top_cal.attributes('-topmost', True)
                            widget.after(100, lambda: widget._top_cal.attributes('-topmost', False) if hasattr(widget, '_top_cal') and widget._top_cal else None)

                    # Delay adjustment to ensure popup is created and positioned
                    widget.after(50, adjust_popup_position)

        self.start_date.bind("<Button-1>", on_date_click)
        self.end_date.bind("<Button-1>", on_date_click)

        # For macOS, create alternative keyboard shortcuts for calendar navigation
        if is_macos:
            def handle_key_event(widget, event):
                if hasattr(widget, '_top_cal') and widget._top_cal:
                    # Forward key events to the calendar
                    widget._top_cal.event_generate(f"<{event.type}>", keysym=event.keysym)
                    return "break"  # Prevent default handling

            self.start_date.bind("<Key>", lambda event, w=self.start_date: handle_key_event(w, event))
            self.end_date.bind("<Key>", lambda event, w=self.end_date: handle_key_event(w, event))

        # Row 1: Search buttons
        search_controls_frame = ttk.Frame(self.lidar_frame)
        search_controls_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        # Configure search controls frame columns - four equal columns
        search_controls_frame.columnconfigure(0, weight=1)
        search_controls_frame.columnconfigure(1, weight=1)
        search_controls_frame.columnconfigure(2, weight=1)
        search_controls_frame.columnconfigure(3, weight=1)

        # Search button
        self.search_button = ttk.Button(search_controls_frame,
                                      text="Search LIDAR",
                                      command=self.search_lidar,
                                      style='LidarSearch.TButton')
        self.search_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        # Point Search button
        self.point_search_button = ttk.Button(search_controls_frame,
                                           text="Point Search",
                                           command=self.search_lidar_by_points,
                                           style='LidarSearch.TButton')
        self.point_search_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Index/AWS Search button
        self.aws_search_button = ttk.Button(search_controls_frame,
                                         text="Index Search",
                                         command=self.search_lidar_aws,
                                         style='LidarSearch.TButton')
        self.aws_search_button.grid(row=0, column=2, padx=5, pady=5, sticky="ew")

        # Load JSON Results button
        self.load_json_button = ttk.Button(search_controls_frame,
                                        text="Load JSON Results",
                                        command=self.load_json_results,
                                        style='LidarSearch.TButton')
        self.load_json_button.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

                # NOAA Search button
        self.noaa_search_button = ttk.Button(search_controls_frame,
                                      text="NOAA Search",
                                      command=self.search_noaa_data,
                                      style='LidarSearch.TButton')
        self.noaa_search_button.grid(row=0, column=4, padx=5, pady=5, sticky="ew")

        # Note: We're using the built-in search_lidar_aws method which now uses the LIDAR index

        # Row 2: Action buttons
        action_buttons_frame = ttk.Frame(self.lidar_frame)
        action_buttons_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        # Configure action buttons frame columns - two equal columns
        action_buttons_frame.columnconfigure(0, weight=1)
        action_buttons_frame.columnconfigure(1, weight=1)

        # Add "Add All Project Files to Download" button
        self.add_all_button = ttk.Button(
            action_buttons_frame,
            text="Add All Project Files to Download",
            command=self.add_all_files_to_download,
            style='LidarSearch.TButton'
        )
        self.add_all_button.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        # Add "Search Towers" button
        self.search_towers_button = ttk.Button(
            action_buttons_frame,
            text="Search Towers",
            command=self.search_towers,
            style='LidarSearch.TButton'
        )
        self.search_towers_button.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Project Details Pane with project selection
        self.project_details = ProjectDetailsPane(self.main_frame, self, self.project_metadata)

        # Configure project details pane - reduce height from 250 to 150
        self.project_details.main_frame.configure(height=150)  # Reduced height
        self.project_details.main_frame.pack(fill="x", expand=False, padx=10, pady=5)
        self.project_details.main_frame.pack_propagate(False)  # Prevent frame from shrinking

        # File list frame
        self.file_list_frame = ttk.Frame(self.main_frame)
        self.file_list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Initialize the file_list Treeview
        columns = ('Select', 'ID', 'Name', 'Size', 'Project', 'Tile')
        self.file_list = ttk.Treeview(self.file_list_frame, columns=columns, show='headings')

        # Configure columns
        self.file_list.heading('Select', text='✓')
        self.file_list.heading('ID', text='ID')
        self.file_list.heading('Name', text='Name')
        self.file_list.heading('Size', text='Size')
        self.file_list.heading('Project', text='Project')
        self.file_list.heading('Tile', text='Tile ID')

        # Set column widths
        self.file_list.column('Select', width=30, minwidth=30, stretch=False, anchor='center')
        self.file_list.column('ID', width=60, minwidth=60, stretch=True)
        self.file_list.column('Name', width=150, minwidth=100, stretch=True)
        self.file_list.column('Size', width=50, minwidth=50, stretch=False, anchor='e')
        self.file_list.column('Project', width=100, minwidth=80, stretch=True)
        self.file_list.column('Tile', width=80, minwidth=60, stretch=True)

        # Bind click event for checkbox selection
        self.file_list.bind('<ButtonRelease-1>', self.on_item_click)

        # Pack the Treeview with scrollbar
        self.file_list.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(self.file_list_frame, orient="vertical",
                                command=self.file_list.yview)
        scrollbar.pack(side="right", fill="y")
        self.file_list.configure(yscrollcommand=scrollbar.set)

        # Set the file_list in the turbine processor
        self.turbine_processor.set_file_list(self.file_list)

        # Button frame at bottom
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill="x", padx=10, pady=5)

        # Configure columns for even distribution
        self.button_frame.columnconfigure(0, weight=1)
        self.button_frame.columnconfigure(1, weight=1)
        self.button_frame.columnconfigure(2, weight=1)

        # Add buttons in a 2-row grid layout
        ttk.Button(self.button_frame, text="Select All",
                   command=self.select_all).grid(row=0, column=0, padx=5, pady=3, sticky="ew")
        ttk.Button(self.button_frame, text="Deselect All",
                   command=self.deselect_all).grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        ttk.Button(self.button_frame, text="Add to Downloads",
                   command=self.add_to_downloads).grid(row=0, column=2, padx=5, pady=3, sticky="ew")

        # Add Write Project Metadata button in second row
        ttk.Button(self.button_frame, text="Write Project Metadata",
                  command=self.write_project_metadata).grid(row=1, column=0, columnspan=3, padx=5, pady=3, sticky="ew")

        # Export frame
        self.export_frame = ttk.Frame(self.parent)
        self.export_frame.pack(fill="x", padx=10, pady=5)

        # Configure columns for even distribution
        self.export_frame.columnconfigure(0, weight=1)
        self.export_frame.columnconfigure(1, weight=1)

        # Export buttons in a 2-row grid layout
        ttk.Button(self.export_frame, text="Export Certificates",
                  command=self.export_project_certificates).grid(row=0, column=0, padx=5, pady=3, sticky="ew")
        ttk.Button(self.export_frame, text="Export PDF Certificates",
                  command=self.export_pdf_certificates).grid(row=0, column=1, padx=5, pady=3, sticky="ew")
        ttk.Button(self.export_frame, text="Export JSON Certificates",
                  command=self.export_json_certificates).grid(row=1, column=0, padx=5, pady=3, sticky="ew")
        ttk.Button(self.export_frame, text="Export Search Rings",
                  command=self.export_rings_for_sites).grid(row=1, column=1, padx=5, pady=3, sticky="ew")
        ttk.Button(self.export_frame, text="Refresh Metadata",
                  command=self.refresh_metadata).grid(row=2, column=0, columnspan=2, padx=5, pady=3, sticky="ew")

        # Initialize the legend frame attribute
        self.legend_frame = None

        # Use self.root instead of self.master for the after call
        if self.root and self.map_widget:
            self.root.after(500, lambda: self.map_widget.set_zoom(7))

    def search_lidar(self):
        """Search for LIDAR data within the polygon"""
        if not self.polygon_points:
            logger.warning("No polygon points available for LIDAR search")
            messagebox.showwarning("No Polygon", "Please load a project first to define the search area.")
            return

        try:
            # Clear the download queue before starting a new search
            if hasattr(self, 'downloader') and self.downloader:
                logger.info("Clearing download queue before new LIDAR search")
                with self.downloader.lock:
                    # Reset tracking data
                    self.downloader.urls = []
                    self.downloader.file_info = {}

                    # Clear the download queue
                    while not self.downloader.download_queue.empty():
                        try:
                            self.downloader.download_queue.get_nowait()
                            self.downloader.download_queue.task_done()
                        except queue.Empty:
                            break

                    # Reset other tracking variables
                    self.downloader.active_downloads.clear()
                    self.downloader.selected_files.clear()
                    self.downloader.item_url_map.clear()

                # Clear the file list in the UI
                self.downloader.file_list.delete(*self.downloader.file_list.get_children())
                logger.info("Download queue cleared for new search")

            # Clear previous LIDAR polygons from the map
            for polygon in self.lidar_polygons:
                self.map_widget.delete(polygon)
            self.lidar_polygons = []

            # Format polygon points for the API
            polygon_str = ",".join([f"{lon} {lat}" for lat, lon in self.polygon_points])
            logger.debug(f"Formatted polygon string: {polygon_str}")

            base_url = "https://tnmaccess.nationalmap.gov/api/v1/products"

            # Initialize variables for pagination
            offset = 0
            page_size = 25  # Reduced batch size
            all_data = []
            total_results = None

            while True:
                # Get dates with proper error handling
                try:
                    start_date = self.start_date.get_date().strftime("%Y-%m-%d")
                    end_date = self.end_date.get_date().strftime("%Y-%m-%d")
                    logger.info(f"Using date range: {start_date} to {end_date}")
                except Exception as date_err:
                    logger.error(f"Date conversion error: {date_err}")
                    # Use safe defaults if there's an error with the date widgets
                    start_date = "2000-01-01"
                    end_date = date.today().strftime("%Y-%m-%d")
                    messagebox.showwarning("Date Format Issue",
                                          "There was an issue with the date selection. Using default dates instead.")

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
                    
                    # Log the response content type and first part of content for debugging
                    content_type = response.headers.get('content-type', 'unknown')
                    logger.debug(f"Response content type: {content_type}")
                    logger.debug(f"Response status: {response.status_code}")
                    
                    # Check if the response looks like JSON
                    if not content_type.startswith('application/json'):
                        logger.warning(f"Unexpected content type: {content_type}")
                        logger.debug(f"Response content (first 500 chars): {response.text[:500]}")
                    
                    try:
                        raw_data = response.json()
                    except json.JSONDecodeError as json_error:
                        logger.error(f"JSON parsing error: {json_error}")
                        logger.error(f"Response content (first 1000 chars): {response.text[:1000]}")
                        logger.error(f"Full response headers: {dict(response.headers)}")
                        messagebox.showerror("Error", 
                                           f"Invalid response from TNM API. The response was not valid JSON.\n\n"
                                           f"This usually indicates:\n"
                                           f"• TNM service is temporarily unavailable\n" 
                                           f"• Invalid search parameters\n"
                                           f"• Service maintenance\n\n"
                                           f"Please try again later or use one of the other search methods (Index Search, Point Search).")
                        break

                    # Use the conditional parser to handle different TNM response formats
                    data = parse_tnm_response(raw_data, logger)
                    
                    # Check if the parser found an error
                    if data.get('status') == 'error':
                        error_msg = data.get('error', 'Unknown error')
                        logger.error(f"TNM parser found error: {error_msg}")
                        
                        # Check if this is the known TNM small polygon bug
                        if "'str' object has no attribute 'get'" in str(error_msg):
                            logger.warning("TNM small polygon bug detected - attempting retry with larger polygon")
                            
                            # Get current width and suggest a larger one
                            current_width = getattr(self, 'polygon_width_ft', tk.DoubleVar()).get() if hasattr(self, 'polygon_width_ft') else 500
                            suggested_width = max(1000, current_width * 2)
                            
                            response = messagebox.askyesno(
                                "TNM Polygon Size Issue",
                                f"TNM API has a bug with small polygons (current width: {current_width}ft).\n\n"
                                f"Would you like to automatically retry with a {suggested_width}ft width?\n\n"
                                f"This usually resolves the issue.",
                                icon='question'
                            )
                            
                            if response:
                                # Update the polygon width and retry
                                if hasattr(self, 'polygon_width_ft'):
                                    original_width = self.polygon_width_ft.get()
                                    self.polygon_width_ft.set(suggested_width)
                                    logger.info(f"Retrying TNM search with larger polygon: {suggested_width}ft (was {original_width}ft)")
                                    
                                    # Update the polygon points with the new width
                                    if hasattr(self, 'donor_site') and hasattr(self, 'recipient_site'):
                                        try:
                                            from utilities.coordinates import convert_dms_to_decimal
                                            lat_a, lon_a = convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
                                            lat_b, lon_b = convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])
                                            
                                            # Recalculate polygon with new width
                                            from utilities.geometry import calculate_polygon_points
                                            self.polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), suggested_width)
                                            logger.info(f"Recalculated polygon with {suggested_width}ft width")
                                            
                                            # Restart the search with new polygon
                                            self.search_lidar()
                                            return
                                            
                                        except Exception as retry_error:
                                            logger.error(f"Error during retry: {retry_error}")
                                            messagebox.showerror("Retry Failed", f"Could not retry with larger polygon: {str(retry_error)}")
                            
                        messagebox.showerror("TNM API Error", 
                                           f"TNM API returned an error:\n\n"
                                           f"{error_msg}\n\n"
                                           f"Please try again later or use one of the other search methods.")
                        break

                    # Get total results count from first response
                    if total_results is None:
                        total_results = data.get('total', 0)
                        logger.info(f"Total available results: {total_results}")

                    # Add items from this page to our collection
                    items = data.get('items', [])

                    # Log detailed information about items to debug duplicates
                    if offset > 0:
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
                    messagebox.showerror("Error", f"Failed to search for LIDAR data: {str(re)}")
                    break

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
                self.display_lidar_results({"items": all_data})
            else:
                logger.warning("No LIDAR data found")
                messagebox.showinfo("Search Results", "No LIDAR files found in the specified area and time range.")

        except Exception as e:
            logger.error(f"Error in LIDAR search: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred during LIDAR search: {str(e)}")

    def search_lidar_aws(self):
        """Search for LIDAR data using the LIDAR index database and AWS S3 bucket"""
        try:
            # Check if we have polygon points
            if not self.polygon_points:
                logger.warning("No polygon points available for AWS LIDAR search")
                messagebox.showwarning("No Polygon", "Please load a project first to define the search area.")
                return

            # Get date range from UI
            start_date = self.start_date.get_date()
            end_date = self.end_date.get_date()

            logger.info(f"Starting LIDAR index search for data from {start_date} to {end_date}")

            # Clear existing data if we have a downloader
            if hasattr(self, 'downloader') and self.downloader:
                # Clear the file list in the UI
                self.downloader.file_list.delete(*self.downloader.file_list.get_children())
                logger.info("Download queue cleared for new search")

            # Clear previous LIDAR polygons from the map
            for polygon in self.lidar_polygons:
                self.map_widget.delete(polygon)
            self.lidar_polygons = []

            # Show a progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("LIDAR Index Search Progress")
            progress_dialog.geometry("400x180")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            # Create a flag to track if search was cancelled
            self.search_cancelled = False

            # Handle dialog close button (X)
            def on_dialog_close():
                self.search_cancelled = True
                progress_dialog.destroy()

            progress_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

            progress_label = ttk.Label(progress_dialog, text="Searching for LIDAR data in AWS S3 bucket...")
            progress_label.pack(pady=10)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
            progress_bar.pack(fill="x", padx=20, pady=10)

            status_label = ttk.Label(progress_dialog, text="Starting search...")
            status_label.pack(pady=5)

            # Add a cancel button
            cancel_button = ttk.Button(
                progress_dialog,
                text="Cancel Search",
                command=on_dialog_close
            )
            cancel_button.pack(pady=10)

            # Update the UI
            self.root.update()

            # Start a thread to perform the search
            def aws_search_thread():
                try:
                    # Define progress callback
                    def update_progress_callback(message, percent):
                        if self.search_cancelled:
                            return
                        status_label.config(text=message)
                        progress_var.set(percent)
                        self.root.update()

                    # Update initial status
                    update_progress_callback("Initializing AWS S3 search...", 5)

                    # Check if the LIDAR index database exists
                    if database_exists():
                        # Use the LIDAR index database
                        logger.info("Using LIDAR index database for search")
                        update_progress_callback("Searching LIDAR index database...", 20)

                        # Log the polygon points being used for search
                        logger.info(f"Using search width polygon with {len(self.polygon_points)} points")
                        logger.info(f"Polygon points: {self.polygon_points}")

                        # Calculate the approximate area of the polygon (rough estimate)
                        if len(self.polygon_points) >= 3:
                            from shapely.geometry import Polygon
                            # Convert to (lon, lat) for shapely
                            shapely_points = [(lon, lat) for lat, lon in self.polygon_points]
                            try:
                                poly = Polygon(shapely_points)
                                logger.info(f"Approximate polygon area: {poly.area:.6f} square degrees")
                                logger.info(f"Polygon bounds: {poly.bounds}")
                            except Exception as e:
                                logger.error(f"Error calculating polygon area: {e}")

                        # Log individual points for detailed debugging
                        for i, point in enumerate(self.polygon_points):
                            logger.info(f"Polygon point {i}: {point}")

                        # Perform the search with the LIDAR index
                        # Note: self.polygon_points are in (lat, lon) order
                        result = search_lidar_index(
                            self.polygon_points,
                            start_date,
                            end_date,
                            format="laz",  # Use lowercase 'laz' to match database format
                            retrieve_metadata=True,
                            coordinate_order="latlon"  # Specify that our points are in (lat, lon) order
                        )

                        # Check if we found any results
                        if result and result.get('items') and len(result.get('items', [])) > 0:
                            logger.info(f"Found {len(result.get('items', []))} LIDAR files in index")
                            update_progress_callback(f"Found {len(result.get('items', []))} LIDAR files in index", 100)
                        else:
                            logger.warning("No LIDAR files found in index")
                            update_progress_callback("No LIDAR files found in index", 100)
                            messagebox.showinfo("Search Results", "No LIDAR files found in the index for the specified area and time range.")
                            return
                    else:
                        # Fall back to direct AWS search
                        logger.warning("LIDAR index database not found, falling back to direct AWS search")
                        update_progress_callback("LIDAR index database not found, falling back to direct AWS search", 20)

                        # Show a message to the user
                        messagebox.showinfo(
                            "LIDAR Index Not Found",
                            "The LIDAR index database was not found. This search will take longer than usual.\n\n"
                            "To create the LIDAR index database, run one of the following commands:\n"
                            "python update_lidar_index.py --init\n"
                            "python init_lidar_index.py"
                        )

                        # Import the AWS search function
                        from utilities.aws_search import search_aws_lidar

                        # Perform the search with progress updates
                        logger.info("Starting AWS S3 search with progress callback")
                        result = search_aws_lidar(
                            self.polygon_points,
                            start_date,
                            end_date,
                            progress_callback=update_progress_callback,
                            retrieve_metadata=True  # Retrieve additional metadata from EPT files
                        )

                    # Check if search was cancelled
                    if self.search_cancelled:
                        logger.info("AWS search cancelled by user")
                        return

                    # Final progress update
                    update_progress_callback("Processing results...", 95)

                    # Process the results
                    if result and "items" in result and result["items"]:
                        logger.info(f"AWS search found {len(result['items'])} LIDAR files")

                        # Add AWS flag to all items and ensure bounding boxes are valid
                        for i, item in enumerate(result['items']):
                            item['awsSource'] = True

                            # Ensure each item has a valid bounding box
                            if 'boundingBox' not in item or not item['boundingBox']:
                                # Create a default bounding box if missing
                                item['boundingBox'] = {
                                    'minX': -104.0 + (i % 10) * 0.02,  # Default to Colorado area with grid layout
                                    'minY': 39.0 + (i // 10) * 0.02,
                                    'maxX': -104.0 + (i % 10) * 0.02 + 0.015,
                                    'maxY': 39.0 + (i // 10) * 0.02 + 0.015
                                }
                                logger.debug(f"Added default bounding box to item: {item['title']}")

                            # Verify the bounding box has all required keys
                            bbox = item['boundingBox']
                            if not all(k in bbox for k in ['minX', 'minY', 'maxX', 'maxY']):
                                logger.warning(f"Item {i} has invalid bounding box: {bbox}")
                                item['boundingBox'] = {
                                    'minX': -104.0 + (i % 10) * 0.02,
                                    'minY': 39.0 + (i // 10) * 0.02,
                                    'maxX': -104.0 + (i % 10) * 0.02 + 0.015,
                                    'maxY': 39.0 + (i // 10) * 0.02 + 0.015
                                }

                            # Log the bounding box for debugging
                            logger.info(f"Item {i} ({item.get('title', 'Unknown')}) bounding box: {item['boundingBox']}")

                            # Ensure the item has a project name
                            if 'projectName' not in item or not item['projectName']:
                                item['projectName'] = f"AWS_Project_{i // 10}"
                                logger.debug(f"Added default project name to item: {item['title']}")

                        # Close the progress dialog
                        progress_dialog.destroy()

                        # Display the results
                        logger.info("Calling display_lidar_results with AWS search results")
                        self.display_lidar_results(result)

                        # Show a message about AWS files
                        messagebox.showinfo("AWS Search Results",
                                         f"Found {len(result['items'])} LIDAR files in AWS S3 bucket.\n\n"
                                         f"Note: These files will be downloaded directly from AWS S3 using the requester pays option. "
                                         f"Standard AWS charges may apply.")
                    else:
                        logger.warning("No LIDAR data found in AWS search")
                        # Close the progress dialog
                        progress_dialog.destroy()
                        messagebox.showinfo("Search Results", "No LIDAR files found in AWS S3 bucket for the specified area and time range.")
                except Exception as e:
                    logger.error(f"Error in AWS search thread: {str(e)}", exc_info=True)
                    # Close the progress dialog
                    progress_dialog.destroy()
                    messagebox.showerror("Error", f"An error occurred during AWS search: {str(e)}")

            # Start the search thread
            threading.Thread(target=aws_search_thread, daemon=True).start()

        except Exception as e:
            logger.error(f"Error in AWS search: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred during AWS search: {str(e)}")

    def search_lidar_by_points(self):
        """Search for LIDAR data using points along the path"""
        try:
            # Check if we have polygon points
            if not self.polygon_points:
                logger.warning("No polygon points available for LIDAR point search")
                messagebox.showwarning("No Polygon", "Please load a project first to define the search area.")
                return

            # Get date range from UI
            start_date = self.start_date.get_date().strftime("%Y-%m-%d")
            end_date = self.end_date.get_date().strftime("%Y-%m-%d")

            logger.info(f"Starting point search for LIDAR data from {start_date} to {end_date}")

            # Clear existing data if we have a downloader
            if hasattr(self, 'downloader') and self.downloader:
                # Clear the file list in the UI
                self.downloader.file_list.delete(*self.downloader.file_list.get_children())
                logger.info("Download queue cleared for new search")

            # Clear previous LIDAR polygons from the map
            for polygon in self.lidar_polygons:
                self.map_widget.delete(polygon)
            self.lidar_polygons = []

            # Get the site coordinates
            if not hasattr(self, 'donor_site') or not hasattr(self, 'recipient_site'):
                messagebox.showinfo("Missing Sites", "Please select two sites to create a search path first.")
                return

            site_a = self.donor_site
            site_b = self.recipient_site

            # Generate points along the path
            # The number of points depends on the distance - more points for longer paths
            # Convert coordinates from DMS to decimal if needed
            try:
                lat_a, lon_a = coords_convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
                lat_b, lon_b = coords_convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
                logger.info(f"Converted coordinates for point search: Site A: ({lat_a}, {lon_a}), Site B: ({lat_b}, {lon_b})")
            except Exception as e:
                logger.error(f"Error converting coordinates: {e}")
                messagebox.showerror("Coordinate Error", f"Failed to convert coordinates: {str(e)}")
                return

            # Calculate distance to determine number of points
            distance_km = calculate_distance((lat_a, lon_a), (lat_b, lon_b))
            distance_miles = distance_km * 0.621371  # Convert km to miles

            # Calculate number of points based on 0.25 mile spacing
            point_spacing_miles = 0.25  # One point every 1/4 mile
            num_points = max(10, int(distance_miles / point_spacing_miles) + 1)
            logger.info(f"Generating {num_points} points along {distance_km:.2f} km ({distance_miles:.2f} miles) path with {point_spacing_miles} mile spacing (1/4 mile)")

            # Get the search width from the UI
            width_ft = self.polygon_width_ft.get()
            logger.info(f"Using search width of {width_ft} feet for point search")

            # Calculate bearing from start to end
            from utilities.coordinates import calculate_bearing, destination_point
            forward_bearing = calculate_bearing(lat_a, lon_a, lat_b, lon_b)

            # Calculate perpendicular bearings (90 degrees to left and right)
            left_bearing = (forward_bearing - 90) % 360
            right_bearing = (forward_bearing + 90) % 360

            # Convert width from feet to meters
            width_m = width_ft * 0.3048

            # Generate points along multiple parallel paths
            points = []

            # Number of parallel paths (center path + paths on each side)
            num_paths = 3  # Center + 1 on each side
            logger.info(f"Using {num_paths} parallel paths for point search")

            # Generate points along each path
            for path_idx in range(num_paths):
                # Calculate offset from center as a fraction of half width
                if num_paths == 1:
                    offset_fraction = 0  # Just the center path
                else:
                    offset_fraction = (path_idx / (num_paths - 1)) - 0.5  # -0.5 to 0.5

                # Calculate the offset distance
                offset_distance = width_m * offset_fraction

                # Determine the bearing for this offset
                if offset_distance < 0:
                    # Left side
                    offset_bearing = left_bearing
                    offset_distance = abs(offset_distance)
                elif offset_distance > 0:
                    # Right side
                    offset_bearing = right_bearing
                else:
                    # Center path - no offset needed
                    for i in range(num_points):
                        # Calculate position along the path (0 to 1)
                        t = i / (num_points - 1) if num_points > 1 else 0
                        # Linear interpolation between points
                        lat = lat_a + t * (lat_b - lat_a)
                        lon = lon_a + t * (lon_b - lon_a)
                        points.append((lat, lon))
                    continue

                # Calculate the start and end points for this parallel path
                offset_start = destination_point(lat_a, lon_a, offset_bearing, offset_distance)
                offset_end = destination_point(lat_b, lon_b, offset_bearing, offset_distance)

                # Generate points along this parallel path
                for i in range(num_points):
                    # Calculate position along the path (0 to 1)
                    t = i / (num_points - 1) if num_points > 1 else 0
                    # Linear interpolation between points
                    lat = offset_start[0] + t * (offset_end[0] - offset_start[0])
                    lon = offset_start[1] + t * (offset_end[1] - offset_start[1])
                    points.append((lat, lon))

            logger.info(f"Generated {len(points)} total points across {num_paths} parallel paths")

            # Show a progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Point Search Progress")
            progress_dialog.geometry("400x180")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            # Create a flag to track if search was cancelled
            self.search_cancelled = False

            # Handle dialog close button (X)
            def on_dialog_close():
                self.search_cancelled = True
                progress_dialog.destroy()

            progress_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

            progress_label = ttk.Label(progress_dialog, text="Searching for LIDAR data at points along the path...")
            progress_label.pack(pady=10)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
            progress_bar.pack(fill="x", padx=20, pady=10)

            status_label = ttk.Label(progress_dialog, text="Starting search...")
            status_label.pack(pady=5)

            # Add a cancel button
            cancel_button = ttk.Button(
                progress_dialog,
                text="Cancel Search",
                command=on_dialog_close
            )
            cancel_button.pack(pady=10)

            # Update the UI
            self.root.update()

            # Perform the point search
            try:
                # Set up a function to process points in batches and update progress
                total_points = len(points)
                batch_size = max(1, total_points // 10)  # Process in approximately 10 batches
                all_items = []
                unique_source_ids = set()  # Track unique items to avoid duplicates

                # Update progress bar
                def update_progress(current, total):
                    progress_var.set((current / total) * 100)
                    status_label.config(text=f"Searching point {current}/{total}...")
                    progress_dialog.update()

                # Process points in batches
                for i in range(0, total_points, batch_size):
                    # Check if search was cancelled
                    if self.search_cancelled:
                        logger.info("Point search cancelled by user")
                        break

                    # Get the current batch of points
                    batch_points = points[i:i+batch_size]

                    # Update progress
                    update_progress(min(i + batch_size, total_points), total_points)

                    # Search this batch of points with an offset to ensure we capture all relevant tiles
                    # Use 0.001 degrees (approximately 100 meters) as the offset
                    batch_result = point_search(batch_points, start_date, end_date, offset=0.001)

                    # Add unique items to our collection
                    if batch_result and 'items' in batch_result:
                        for item in batch_result['items']:
                            source_id = item.get('sourceId')
                            if source_id and source_id not in unique_source_ids:
                                unique_source_ids.add(source_id)
                                all_items.append(item)

                # Create the final result
                result = {"items": all_items}

                # Process the results if search wasn't cancelled
                if self.search_cancelled:
                    logger.info("Point search results discarded due to cancellation")
                    messagebox.showinfo("Search Cancelled", "The point search was cancelled. No results will be displayed.")
                elif all_items:
                    logger.info(f"Point search found {len(all_items)} unique LIDAR files")
                    # Display the results without showing a message box first
                    # (The message box will be shown by display_lidar_results)
                    try:
                        self.display_lidar_results(result)
                    except Exception as display_error:
                        logger.error(f"Error displaying LIDAR results: {display_error}", exc_info=True)
                        messagebox.showerror("Display Error", f"Error displaying results: {str(display_error)}")
                else:
                    logger.warning("No LIDAR data found in point search")
                    messagebox.showinfo("Search Results", "No LIDAR files found along the path in the specified time range.")
            except Exception as e:
                logger.error(f"Error in point search: {str(e)}", exc_info=True)
                messagebox.showerror("Error", f"An error occurred during point search: {str(e)}")
            finally:
                # Close the progress dialog
                progress_dialog.destroy()

        except Exception as e:
            logger.error(f"Error in point search: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred during point search: {str(e)}")

    def search_noaa_data(self):
        """Search for NOAA LIDAR data using the NOAA index database"""
        try:
            # Check if we have polygon points
            if not self.polygon_points:
                logger.warning("No polygon points available for NOAA LIDAR search")
                messagebox.showwarning("No Polygon", "Please load a project first to define the search area.")
                return

            # Get date range from UI
            start_date = self.start_date.get_date()
            end_date = self.end_date.get_date()

            logger.info(f"Starting NOAA LIDAR search for data from {start_date} to {end_date}")

            # Clear existing data if we have a downloader
            if hasattr(self, 'downloader') and self.downloader:
                logger.info("Clearing download queue before new NOAA search")
                with self.downloader.lock:
                    # Reset tracking data
                    self.downloader.urls = []
                    self.downloader.file_info = {}

                    # Clear the download queue
                    while not self.downloader.download_queue.empty():
                        try:
                            self.downloader.download_queue.get_nowait()
                            self.downloader.download_queue.task_done()
                        except queue.Empty:
                            break

                    # Reset other tracking variables
                    self.downloader.active_downloads.clear()
                    self.downloader.selected_files.clear()
                    self.downloader.item_url_map.clear()

                # Clear the file list in the UI
                self.downloader.file_list.delete(*self.downloader.file_list.get_children())
                logger.info("Download queue cleared for new NOAA search")

            # Clear previous LIDAR polygons from the map
            for polygon in self.lidar_polygons:
                self.map_widget.delete(polygon)
            self.lidar_polygons = []

            # Show a progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("NOAA LIDAR Search Progress")
            progress_dialog.geometry("400x180")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            # Create a flag to track if search was cancelled
            self.search_cancelled = False

            # Handle dialog close button (X)
            def on_dialog_close():
                self.search_cancelled = True
                progress_dialog.destroy()

            progress_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

            progress_label = ttk.Label(progress_dialog, text="Searching for NOAA LIDAR data...")
            progress_label.pack(pady=10)

            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
            progress_bar.pack(fill="x", padx=20, pady=10)

            status_label = ttk.Label(progress_dialog, text="Starting search...")
            status_label.pack(pady=5)

            # Add a cancel button
            cancel_button = ttk.Button(
                progress_dialog,
                text="Cancel Search",
                command=on_dialog_close
            )
            cancel_button.pack(pady=10)

            # Update the UI
            self.root.update()

            # Start a thread to perform the search
            def noaa_search_thread():
                try:
                    # Define progress callback
                    def update_progress_callback(message, percent):
                        if self.search_cancelled:
                            return
                        status_label.config(text=message)
                        progress_var.set(percent)
                        self.root.update()

                    # Update initial status
                    update_progress_callback("Initializing NOAA LIDAR search...", 5)

                    # Import the NOAA search function
                    try:
                        from NOAA.noaa_index_search import search_noaa_index
                        from NOAA.noaa_index_db import database_exists
                        update_progress_callback("NOAA search module loaded...", 10)
                        logger.info("Successfully imported NOAA search modules")
                    except ImportError as e:
                        logger.error(f"Failed to import NOAA search modules: {e}")
                        progress_dialog.destroy()
                        messagebox.showerror("Module Error", 
                                           f"NOAA search modules not available: {str(e)}\n\n"
                                           "Please ensure the NOAA module is properly installed.")
                        return

                    # Check if the NOAA index database exists
                    if not database_exists():
                        logger.warning("NOAA index database not found")
                        update_progress_callback("NOAA index database not found", 100)
                        progress_dialog.destroy()
                        messagebox.showinfo(
                            "NOAA Index Not Found",
                            "The NOAA LIDAR index database was not found.\n\n"
                            "To create the NOAA index database, run:\n"
                            "python NOAA/noaa_indexer.py --init --crawl-all\n\n"
                            "This will download and index NOAA LIDAR datasets for searching."
                        )
                        return

                    # Use the NOAA index database
                    logger.info("Using NOAA index database for search")
                    update_progress_callback("Searching NOAA index database...", 30)

                    # Log the polygon points being used for search
                    logger.info(f"Using search polygon with {len(self.polygon_points)} points")
                    logger.info(f"Polygon points: {self.polygon_points}")

                    # Calculate the approximate area of the polygon
                    if len(self.polygon_points) >= 3:
                        try:
                            from shapely.geometry import Polygon
                            # Convert to (lon, lat) for shapely
                            shapely_points = [(lon, lat) for lat, lon in self.polygon_points]
                            poly = Polygon(shapely_points)
                            logger.info(f"Approximate polygon area: {poly.area:.6f} square degrees")
                            logger.info(f"Polygon bounds: {poly.bounds}")
                        except Exception as e:
                            logger.error(f"Error calculating polygon area: {e}")

                    # Perform the search with the NOAA index
                    # Note: self.polygon_points are in (lat, lon) order
                    update_progress_callback("Querying NOAA database...", 50)
                    
                    result = search_noaa_index(
                        polygon_points=self.polygon_points,
                        start_date=start_date,
                        end_date=end_date,
                        data_type=None,  # Accept all data types (lidar, topobathy, etc.)
                        format=None,  # Accept all formats (LAZ, LAS, EPT)
                        coordinate_order="latlon"  # Specify that our points are in (lat, lon) order
                    )

                    # Check if search was cancelled
                    if self.search_cancelled:
                        logger.info("NOAA search cancelled by user")
                        return

                    # Process the results
                    update_progress_callback("Processing results...", 80)

                    if result and result.get('items') and len(result.get('items', [])) > 0:
                        logger.info(f"Found {len(result.get('items', []))} NOAA LIDAR files")
                        update_progress_callback(f"Found {len(result.get('items', []))} NOAA LIDAR files", 90)

                        # Add NOAA flag to all items and ensure proper formatting
                        for i, item in enumerate(result['items']):
                            item['noaaSource'] = True
                            
                            # Ensure the item has required fields for display
                            if 'downloadURL' not in item:
                                item['downloadURL'] = item.get('file_path', '')
                            
                            if 'sourceId' not in item:
                                item['sourceId'] = f"noaa_{item.get('id', i)}"
                            
                            if 'title' not in item:
                                item['title'] = item.get('filename', f'NOAA_File_{i}')
                            
                            # Ensure project name
                            if 'projectName' not in item:
                                item['projectName'] = item.get('project_name', f'NOAA_Project_{i // 10}')
                            
                            # Ensure bounding box format
                            if 'boundingBox' not in item and all(k in item for k in ['min_x', 'min_y', 'max_x', 'max_y']):
                                item['boundingBox'] = {
                                    'minX': item['min_x'],
                                    'minY': item['min_y'], 
                                    'maxX': item['max_x'],
                                    'maxY': item['max_y']
                                }

                        # Final progress update
                        update_progress_callback("Displaying results...", 95)
                        
                        # Close the progress dialog
                        progress_dialog.destroy()

                        # Display the results using the existing LIDAR results display
                        logger.info("Calling display_lidar_results with NOAA search results")
                        self.display_lidar_results(result)

                        # Show a message about NOAA files
                        messagebox.showinfo("NOAA Search Results",
                                         f"Found {len(result['items'])} NOAA LIDAR files.\n\n"
                                         f"These files are from the NOAA Digital Coast LIDAR dataset.")
                    else:
                        logger.warning("No NOAA LIDAR data found")
                        update_progress_callback("No NOAA data found", 100)
                        # Close the progress dialog
                        progress_dialog.destroy()
                        messagebox.showinfo("Search Results", 
                                          "No NOAA LIDAR files found for the specified area and time range.\n\n"
                                          "This could mean:\n"
                                          "- No NOAA data available for this area\n"
                                          "- The NOAA index needs to be updated\n"
                                          "- The search criteria are too restrictive")

                except Exception as e:
                    logger.error(f"Error in NOAA search thread: {str(e)}", exc_info=True)
                    # Close the progress dialog
                    progress_dialog.destroy()
                    messagebox.showerror("Error", f"An error occurred during NOAA search: {str(e)}")

            # Start the search thread
            threading.Thread(target=noaa_search_thread, daemon=True).start()

        except Exception as e:
            logger.error(f"Error in NOAA search: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred during NOAA search: {str(e)}")

    def display_lidar_results(self, data):
        """Display the LIDAR search results on the map"""
        try:
            # Validate input data
            if not data or not isinstance(data, dict) or 'items' not in data:
                logger.error("Invalid data format passed to display_lidar_results")
                return

            logger.info(f"Displaying LIDAR results - {len(data['items'])} items found")
            self.lidar_data = data

            # Clear existing LIDAR display
            try:
                self.clear_lidar_display()
            except Exception as clear_error:
                logger.error(f"Error clearing LIDAR display: {clear_error}", exc_info=True)
                # Continue anyway to try to display the new data

            # Extract data from results
            items = self.lidar_data['items']

            # Clear existing file list if it exists
            if hasattr(self, 'file_list'):
                self.file_list.delete(*self.file_list.get_children())
                self.selected_files = set()
                self.item_url_map = {}

            # Clear existing tile markers if any
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    marker.delete()
                self.tile_markers = []

            # Clear existing LIDAR polygons and tracking
            self.clear_lidar_polygons()

            # Initialize project_polygons dictionary if it doesn't exist
            if not hasattr(self, 'project_polygons'):
                self.project_polygons = {}

            # Initialize _all_project_polygons as an empty dictionary to serve as backup for all polygons
            self._all_project_polygons = {}

            # Store original tile counts for each project
            if not hasattr(self, 'project_tile_counts'):
                self.project_tile_counts = {}

            # Clear any existing project visibility tracking
            self.project_visibility = {}

            # Initialize project colors dictionary
            self.project_colors = {}

            files_within_polygon = 0
            project_items = {}
            self.projects = {}  # Clear existing projects
            tile_mapping = {}   # Map tile IDs to files
            tile_counter = 1    # For generating tile IDs

            # First pass - collect metadata and group items by project
            logger.info("Starting first pass - collecting unique projects")
            for item in items:
                url = item.get('downloadURL')
                item_id = item.get('sourceId')

                if url and item_id:
                    filename = url.split('/')[-1]
                    project_name = get_project_name(filename)

                    # Initialize project group if needed
                    if project_name not in project_items:
                        project_items[project_name] = []
                        # Assign color if not already assigned
                        if project_name not in self.project_colors:
                            color_index = len(self.project_colors) % len(self.color_series)
                            self.project_colors[project_name] = self.color_series[color_index]
                        logger.info(f"Processing metadata for project: {project_name}")

                        # Process metadata for first item in project
                        self.project_metadata.add_project(project_name, item)

                        # Create project frame in legend
                        project_frame = ttk.Frame(self.legend_items_frame)
                        project_frame.pack(fill='x', padx=5, pady=2)

                        # Add project label
                        label = ttk.Label(
                            project_frame,
                            text=project_name,
                            foreground=self.project_colors[project_name]
                        )
                        label.pack(side='left', padx=(0, 5))

                        # Add visibility toggle button with proper binding
                        self.project_visibility[project_name] = tk.BooleanVar(value=True)

                        # Create toggle button with direct command binding
                        toggle_btn = ttk.Checkbutton(
                            project_frame,
                            text="Show Tiles",
                            variable=self.project_visibility[project_name],
                            command=lambda p=project_name: self.toggle_project_visibility(p)
                        )
                        toggle_btn.pack(side='right', padx=5)

                        # Add tile count label
                        project_tile_count_label = ttk.Label(
                            project_frame,
                            text="Tiles: 0"
                        )
                        project_tile_count_label.pack(side='right', padx=5)

                        # Store the label for this project
                        if not hasattr(self, 'project_tile_count_labels'):
                            self.project_tile_count_labels = {}
                        self.project_tile_count_labels[project_name] = project_tile_count_label

                        # Initialize project polygons list
                        self.project_polygons[project_name] = []

                        # Add to self.projects dictionary for certificate export
                        self.projects[project_name] = {
                            'item_id': item_id,
                            'metadata': item
                        }
                    else:
                        # Add this file to the existing project in project_metadata
                        self.project_metadata.add_file_to_project(project_name, item)

                    project_items[project_name].append(item)
                    files_within_polygon += 1

            # Second pass - process items and update UI
            logger.info("Starting second pass - updating UI")
            for project_name, items in project_items.items():
                # Track unique tile boundaries
                unique_tile_bounds = {}
                tile_labels = []  # Store references to tile labels

                # First identify unique tiles in this project
                for item in items:
                    bbox = item.get('boundingBox')
                    if bbox:
                        # Check if this is an AWS source
                        is_aws = item.get('awsSource', False)
                        aws_tile_id = item.get('tileId', '')

                        # For AWS sources, use a unique ID for each tile to ensure they all display
                        if is_aws:
                            # Use the AWS tile ID as part of the bbox_key to ensure uniqueness
                            bbox_key = (
                                round(bbox['minY'], 6),
                                round(bbox['minX'], 6),
                                round(bbox['maxY'], 6),
                                round(bbox['maxX'], 6),
                                aws_tile_id  # Add the AWS tile ID to make each key unique
                            )
                            logger.info(f"AWS tile {aws_tile_id} with bbox {bbox}")
                        else:
                            # For regular sources, use the bounding box coordinates as the key
                            bbox_key = (
                                round(bbox['minY'], 6),
                                round(bbox['minX'], 6),
                                round(bbox['maxY'], 6),
                                round(bbox['maxX'], 6)
                            )

                        if bbox_key not in unique_tile_bounds:
                            # For AWS tiles, use the AWS tile ID in the display name
                            if is_aws and aws_tile_id:
                                tile_id = f"AWS_{aws_tile_id}"
                            else:
                                tile_id = f"Tile {tile_counter}"

                            unique_tile_bounds[bbox_key] = tile_id
                            tile_counter += 1

                            # Draw LIDAR polygons on map
                            try:
                                # Log the original bounding box coordinates
                                logger.debug(f"Original bounding box for {tile_id}: minY={bbox['minY']}, minX={bbox['minX']}, maxY={bbox['maxY']}, maxX={bbox['maxX']}")

                                # Check if item has custom polygon points (for AWS tiles)
                                custom_polygon_points = item.get('polygon_points')

                                if custom_polygon_points and len(custom_polygon_points) >= 3:
                                    # Use the provided polygon points
                                    polygon_points = custom_polygon_points

                                    # Make sure the polygon is closed (first point equals last point)
                                    if polygon_points[0] != polygon_points[-1]:
                                        polygon_points.append(polygon_points[0])

                                    logger.info(f"Using custom polygon points for {tile_id}")
                                else:
                                    # Create polygon points from bounding box
                                    polygon_points = [
                                        (bbox['minY'], bbox['minX']),
                                        (bbox['minY'], bbox['maxX']),
                                        (bbox['maxY'], bbox['maxX']),
                                        (bbox['maxY'], bbox['minX']),
                                        (bbox['minY'], bbox['minX'])  # Closing point to complete the polygon
                                    ]

                                # Log the polygon points being sent to the map widget
                                logger.debug(f"Setting polygon for {tile_id} with points: {polygon_points}")

                                # Check if this is an AWS tile
                                is_aws = "AWS_" in tile_id

                                if is_aws:
                                    # Use a more visible style for AWS tiles but without opaque fill
                                    # Use the project color for consistency
                                    project_color = self.project_colors[project_name]

                                    # Log the AWS tile being drawn
                                    logger.info(f"Drawing AWS tile {tile_id} with points: {polygon_points} and color {project_color}")

                                    try:
                                        # Create the polygon with a visible style but no fill
                                        polygon = self.map_widget.set_polygon(
                                            polygon_points,
                                            fill_color="",                  # No fill to avoid duplicate appearance
                                            outline_color=project_color,    # Use project color for consistency
                                            border_width=3                  # Thicker border for better visibility
                                        )
                                        logger.info(f"Successfully created AWS polygon for {tile_id}")
                                    except Exception as e:
                                        logger.error(f"Error creating AWS polygon: {e}")
                                        # Fallback to a simpler style if the above fails
                                        polygon = self.map_widget.set_polygon(
                                            polygon_points,
                                            fill_color="",
                                            outline_color=project_color,
                                            border_width=2
                                        )
                                else:
                                    # Regular style for normal tiles
                                    polygon = self.map_widget.set_polygon(
                                        polygon_points,
                                        fill_color="",
                                        outline_color=self.project_colors[project_name],
                                        border_width=2
                                    )

                                # Store attributes directly on the polygon object for tracking
                                polygon.position_list = polygon_points
                                polygon.outline_color = self.project_colors[project_name]
                                polygon.tile_id = tile_id
                                polygon.tile_number = tile_counter - 1
                                polygon.project_name = project_name

                                # Store original polygon data for visibility toggling
                                self.create_original_polygon_data(project_name, polygon_points, self.project_colors[project_name])

                                # Add to tracking structures - ensure project_polygons is properly initialized
                                if not hasattr(self, 'project_polygons'):
                                    self.project_polygons = {}
                                if project_name not in self.project_polygons:
                                    self.project_polygons[project_name] = []

                                # Add polygon to tracking structures
                                self.lidar_polygons.append(polygon)
                                self.project_polygons[project_name].append(polygon)

                                # Log the addition for debugging
                                if len(self.project_polygons[project_name]) % 5 == 0:
                                    logger.info(f"Added polygon to project {project_name}, now tracking {len(self.project_polygons[project_name])} polygons")

                                # Also save to all_project_polygons for visibility toggling
                                if not hasattr(self, '_all_project_polygons'):
                                    self._all_project_polygons = {}

                                if project_name not in self._all_project_polygons:
                                    self._all_project_polygons[project_name] = []

                                # Store the polygon in the master list
                                self._all_project_polygons[project_name].append(polygon)
                            except Exception as e:
                                logger.error(f"Error drawing polygon: {e}")

                # Update tile count label
                tile_count = len(unique_tile_bounds)
                # Store the actual tile count separately so we don't lose it
                self.project_tile_counts[project_name] = tile_count
                logger.info(f"Project {project_name} has {tile_count} unique tiles - updating label")
                if hasattr(self, 'project_tile_count_labels') and project_name in self.project_tile_count_labels:
                    self.project_tile_count_labels[project_name].config(text=f"Tiles: {tile_count}")
                    logger.info(f"Updated tile count label for {project_name} to {tile_count}")
                else:
                    logger.warning(f"Could not update tile count label for {project_name} - label reference not found")

                logger.info(f"Project {project_name} has {tile_count} unique tiles and {len(items)} files")

                # Make sure all files for this project are in the project metadata
                for item in items:
                    # Ensure this file is in the project's files list in metadata
                    self.project_metadata.add_file_to_project(project_name, item)

                # Add items to file list with tile information
                for item in items:
                    url = item.get('downloadURL')
                    item_id = item.get('sourceId')
                    filename = url.split('/')[-1]
                    file_size = item.get('sizeInBytes', 'Unknown')

                    # Get tile ID if available
                    bbox = item.get('boundingBox')
                    tile_id = "Unknown"
                    if bbox:
                        bbox_key = (
                            round(bbox['minY'], 6),
                            round(bbox['minX'], 6),
                            round(bbox['maxY'], 6),
                            round(bbox['maxX'], 6)
                        )
                        if bbox_key in unique_tile_bounds:
                            tile_id = unique_tile_bounds[bbox_key]

                    tree_item = self.file_list.insert("", "end", values=(
                        "",  # Checkbox column (empty by default)
                        item_id,
                        filename,
                        self.format_file_size(file_size),
                        project_name,
                        tile_id
                    ))
                    self.urls.append((url, item))
                    self.item_url_map[tree_item] = url

            # Show results message with tile count information
            result_message = f"Found {files_within_polygon} LIDAR files across {len(project_items)} projects ({tile_counter-1} unique tiles)"
            logger.info(result_message)
            logger.info(f"Projects available for certificate export: {list(self.projects.keys())}")

            # Update the tower_parameters.json with all project information first
            # Do this in a separate try-except block to prevent crashes
            logger.info("Updating tower_parameters.json with all lidar data")
            try:
                # Use a separate thread to update the JSON file to avoid blocking the UI
                def update_json_thread():
                    try:
                        # Import the safe JSON utilities if available
                        try:
                            from utilities.json_utils import safe_update_json_file
                            logger.info("Using safe JSON utilities for update")
                        except ImportError:
                            logger.info("Safe JSON utilities not available, using standard method")

                        # Update the JSON file
                        success = self.project_metadata.update_all_projects_in_json()
                        if not success:
                            logger.warning("Failed to update tower_parameters.json")
                        else:
                            logger.info("Successfully updated tower_parameters.json")
                    except Exception as thread_error:
                        logger.error(f"Error in JSON update thread: {thread_error}", exc_info=True)

                # Start the thread
                import threading
                json_thread = threading.Thread(target=update_json_thread)
                json_thread.daemon = True  # Make it a daemon thread to prevent blocking app shutdown
                json_thread.start()
                logger.info("Started JSON update thread")

                # Store the thread reference for later joining if needed
                self.json_update_thread = json_thread
            except Exception as e:
                logger.error(f"Error setting up JSON update thread: {e}", exc_info=True)
                # Continue with the application even if JSON update fails

            # Then update project selector dropdown using the main thread
            try:
                if (hasattr(self, 'project_details') and self.project_details and 
                    hasattr(self.root, 'after') and self.root.winfo_exists()):
                    
                    # Additional safety check that project_details is still valid
                    if (hasattr(self.project_details, '_update_project_list') and
                        hasattr(self.project_details, 'project_combobox') and
                        self.project_details.project_combobox):
                        
                        # Schedule the update on the main thread using after()
                        self.root.after(100, lambda: self._safe_update_project_list())
                        logger.info("Scheduled project list update on main thread")
                    else:
                        logger.warning("project_details object is not properly initialized")
                else:
                    logger.warning("Could not schedule project list update - missing required attributes or root destroyed")
            except Exception as e:
                logger.error(f"Error scheduling project list update: {e}", exc_info=True)

            # Finally show the message box
            try:
                messagebox.showinfo("Search Results", result_message)
            except Exception as e:
                logger.error(f"Error showing message box: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in LIDAR search: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred during LIDAR search: {str(e)}")

    def _safe_update_project_list(self):
        """Safely update project list with additional error handling"""
        try:
            # Check if we're still in a valid state
            if (hasattr(self, 'project_details') and self.project_details and
                hasattr(self.project_details, '_update_project_list')):
                
                self.project_details._update_project_list()
            else:
                logger.warning("Cannot update project list - project_details is no longer valid")
        except Exception as e:
            # Don't show error dialogs for threading issues during shutdown
            if "main thread is not in main loop" in str(e):
                logger.warning(f"Threading issue in safe project list update: {e}")
            else:
                logger.error(f"Error in safe project list update: {e}", exc_info=True)

    def toggle_project_visibility(self, project_name):
        """Toggle visibility of LIDAR tile outlines for a specific project"""
        try:
            # Ensure project_visibility exists and has the project
            if not hasattr(self, 'project_visibility'):
                logger.error("project_visibility dictionary does not exist")
                return

            if project_name not in self.project_visibility:
                logger.error(f"Project {project_name} not found in project_visibility dictionary")
                return

            # Get current visibility state
            is_visible = self.project_visibility[project_name].get()
            logger.info(f"Toggling visibility for project {project_name} to {is_visible}")

            # Check if tile labels are currently visible
            tile_labels_visible = False
            if hasattr(self, 'tile_ids_var') and self.tile_ids_var.get():
                tile_labels_visible = True
                # Hide existing tile labels before changing visibility
                self.hide_tile_labels()

            # Debug: Check if we have original polygon data
            if hasattr(self, '_original_polygon_data') and project_name in self._original_polygon_data:
                logger.info(f"Found {len(self._original_polygon_data[project_name])} original polygon data entries for {project_name}")
            else:
                logger.warning(f"No original polygon data found for {project_name}")

            # Ensure project_polygons exists
            if not hasattr(self, 'project_polygons'):
                self.project_polygons = {}
                logger.warning("project_polygons dictionary did not exist, created it")

            # Ensure project entry exists
            if project_name not in self.project_polygons:
                self.project_polygons[project_name] = []
                logger.warning(f"Project {project_name} not found in project_polygons dictionary, created it")

            # Get current polygons for this project from our tracking structure
            current_polygons = self.project_polygons.get(project_name, [])
            polygon_count = len(current_polygons)
            logger.info(f"Project {project_name} has {polygon_count} tracked polygons")

            # Step 1: Delete all existing polygons for this project
            deleted_count = 0
            for polygon in current_polygons[:]:  # Create a copy of the list to safely iterate and modify
                try:
                    # Call delete method on the polygon object itself
                    polygon.delete()
                    deleted_count += 1
                except Exception as e:
                    logger.error(f"Error deleting polygon: {e}")

            logger.info(f"Deleted {deleted_count} polygons for project {project_name}")

            # Step 2: Clear our tracking structures
            if hasattr(self, 'lidar_polygons'):
                self.lidar_polygons = [p for p in self.lidar_polygons if p not in current_polygons]
            self.project_polygons[project_name] = []

            # Step 3: If visibility is ON, recreate the polygons
            if is_visible:
                # Get the original polygon data
                if hasattr(self, '_original_polygon_data') and project_name in self._original_polygon_data:
                    original_data = self._original_polygon_data[project_name]
                    logger.info(f"Recreating {len(original_data)} polygons for project {project_name}")

                    # Create new polygons
                    new_polygons = []
                    for i, data in enumerate(original_data):
                        try:
                            # Extract polygon data
                            polygon_points = data['position_list']
                            color = data['outline_color']

                            # Create the polygon
                            if polygon_points and len(polygon_points) >= 3:
                                new_polygon = self.map_widget.set_polygon(
                                    polygon_points,
                                    fill_color="",
                                    outline_color=color,
                                    border_width=2
                                )

                                # Store attributes on the polygon object
                                new_polygon.position_list = polygon_points
                                new_polygon.outline_color = color
                                new_polygon.tile_number = i + 1
                                new_polygon.project_name = project_name

                                # Add to our tracking structures
                                new_polygons.append(new_polygon)
                                if hasattr(self, 'lidar_polygons'):
                                    self.lidar_polygons.append(new_polygon)
                        except Exception as e:
                            logger.error(f"Error creating polygon {i}: {e}")

                    # Update project polygons tracking
                    self.project_polygons[project_name] = new_polygons
                    logger.info(f"Added {len(new_polygons)} polygons for project {project_name}")
                else:
                    logger.warning(f"No original polygon data found for project {project_name}")

            # Force a UI update
            if hasattr(self, 'map_widget') and self.map_widget:
                self.map_widget.update()

            if hasattr(self, 'root') and self.root:
                self.root.update()

            # Recreate tile labels if they were visible before
            if tile_labels_visible:
                logger.info("Recreating tile labels after visibility change")
                self.create_and_show_tile_labels()

            # Debug: Check the state after toggle
            self.debug_polygon_data()

        except Exception as e:
            logger.error(f"Error toggling project visibility: {e}", exc_info=True)

    def show_project_details(self, project_names, parent):
        """Display project details in a new window"""
        details_window = tk.Toplevel(parent)
        details_window.title("LIDAR Project Details")
        details_window.geometry("800x600")

        notebook = ttk.Notebook(details_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        for project_name in project_names:
            project_frame = ttk.Frame(notebook)
            notebook.add(project_frame, text=project_name)

            # Create scrollable frame
            canvas = tk.Canvas(project_frame)
            scrollbar = ttk.Scrollbar(project_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Get formatted project information
            info_text = self.project_metadata.get_formatted_info(project_name)

            # Create text widget with formatted info
            text_widget = tk.Text(scrollable_frame, wrap=tk.WORD, width=80, height=30)
            text_widget.insert('1.0', info_text)
            text_widget.config(state='disabled')
            text_widget.pack(padx=5, pady=5)

            # Pack scrollbar and canvas
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

        # Add validation status
        status_frame = ttk.Frame(details_window)
        status_frame.pack(fill="x", padx=5, pady=5)

        for project_name in project_names:
            valid, message = self.project_metadata.validate_spatial_reference(project_name)
            status_color = "green" if valid else "red"
            ttk.Label(
                status_frame,
                text=f"{project_name}: {message}",
                foreground=status_color
            ).pack(anchor="w")  # Remove extra parenthesis

    def get_next_color(self):
        """Return the next unused color from the color series"""
        available_colors = [c for c in self.color_series if c not in self.used_colors]
        if not available_colors:
            # If all colors are used, start over
            self.used_colors.clear()
            available_colors = self.color_series

        color = available_colors[0]
        self.used_colors.add(color)
        return color

    def process_lidar_file(self, item, color):
        """Process a LIDAR file and add it to the map"""
        try:
            url = item.get('downloadURL')
            if url:
                filename = url.split('/')[-1]
                project_name = get_project_name(filename)

                # Log detailed information about the LIDAR file
                logger.info(f"Processing LIDAR file: {filename}")
                logger.info(f"Project name: {project_name}")
                logger.info(f"Download URL: {url}")
                logger.info(f"Source ID: {item.get('sourceId')}")
                logger.info(f"Size: {self.format_file_size(item.get('sizeInBytes', 'Unknown'))}")

                # Extract and log bounding box information
                bbox = item.get('boundingBox')
                if bbox:
                    logger.info(f"Bounding box: minX={bbox.get('minX')}, maxX={bbox.get('maxX')}, minY={bbox.get('minY')}, maxY={bbox.get('maxY')}")

                if project_name not in self.project_metadata.projects:
                    # Add project metadata from first item
                    logger.info(f"Adding new project metadata for: {project_name}")
                    self.project_metadata.add_project(project_name, item)
                else:
                    logger.info(f"Project {project_name} already exists in metadata")

                    # Validate existing metadata
                    is_valid, missing_fields = self.project_metadata.validate_metadata(project_name)
                    if not is_valid:
                        logger.warning(f"Existing metadata for {project_name} is incomplete. Missing: {missing_fields}")
                        # Update with new item data
                        logger.info(f"Updating project metadata for: {project_name}")
                        self.project_metadata.add_project(project_name, item)
                self.urls.append((url, item))

                # Add to file list
                self.file_list.insert("", "end", values=(
                    '',  # Checkbox column
                    item.get('sourceId'),
                    filename,
                    self.format_file_size(item.get('sizeInBytes', 'Unknown')),
                    project_name
                ))

                # Draw polygon if coordinates available
                bbox = item.get('boundingBox')
                if bbox:
                    try:
                        # Check projection compatibility for each corner of the bounding box
                        corners = [
                            (bbox['minY'], bbox['minX']),
                            (bbox['minY'], bbox['maxX']),
                            (bbox['maxY'], bbox['maxX']),
                            (bbox['maxY'], bbox['minX'])
                        ]

                        for i, (lat, lon) in enumerate(corners):
                            is_compatible, message = self.check_projection_compatibility(lat, lon)
                            if not is_compatible:
                                logger.warning(f"Corner {i+1} of bounding box for {filename} has projection issues: {message}")

                        polygon_points = [
                            (bbox['minY'], bbox['minX']),
                            (bbox['minY'], bbox['maxX']),
                            (bbox['maxY'], bbox['maxX']),
                            (bbox['maxY'], bbox['minX']),
                            (bbox['minY'], bbox['minX'])  # Closing point to complete the polygon
                        ]  # Close the list bracket
                        polygon = self.map_widget.set_polygon(
                            polygon_points,
                            fill_color="",  # Remove fill
                            outline_color=color,
                            border_width=2,
                            name=f"LIDAR_{project_name}"
                        )
                        self.lidar_polygons.append(polygon)

                        # Store the polygon in project_polygons for visibility tracking
                        if project_name not in self.project_polygons:
                            self.project_polygons[project_name] = []
                        self.project_polygons[project_name].append(polygon)

                        # Set initial visibility state with a BooleanVar if it doesn't already exist
                        if project_name not in self.project_visibility:
                            self.project_visibility[project_name] = tk.BooleanVar(value=True)
                            # Add trace to respond to changes
                            self.project_visibility[project_name].trace_add(
                                'write',
                                lambda var, idx, mode, p=project_name: self.on_project_visibility_change(p)
                            )

                        return True
                    except Exception as e:
                        logger.error(f"Error drawing polygon: {e}")
                        return False
                return False
        except Exception as e:
            logger.error(f"Error processing LIDAR file: {str(e)}", exc_info=True)
            return False

    def format_file_size(self, size_in_bytes):
        """Format file size in human-readable format"""
        if isinstance(size_in_bytes, (int, float)):
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_in_bytes < 1024.0:
                    return f"{size_in_bytes:.2f} {unit}"
                size_in_bytes /= 1024.0
        return str(size_in_bytes)

    def update_profile(self, lat1, lon1, lat2, lon2, site_a_name="Site A", site_b_name="Site B"):
        """Update the elevation profile display"""
        try:
            # Clear existing profile
            self.profile_canvas.delete("all")

            # Get elevation data from USGS
            url = "https://epqs.nationalmap.gov/v1/json?"
            points = self.generate_path_points(lat1, lon1, lat2, lon2, 100)
            elevations = []

            for lat, lon in points:
                params = {
                    "x": lon,
                    "y": lat,
                    "units": "Feet",
                    "output": "json"
                }
                response = requests.get(url + urlencode(params))
                if response.status_code == 200:
                    data = response.json()
                    elevation = data["value"]
                    elevations.append(elevation)

            # Draw profile
            if elevations:
                # Calculate canvas dimensions
                canvas_width = self.profile_canvas.winfo_width()
                canvas_height = self.profile_canvas.winfo_height()
                padding = 20

                # Find elevation range
                min_elev = min(elevations)
                max_elev = max(elevations)
                elev_range = max_elev - min_elev

                # Update elevation labels
                self.min_elevation_label.config(text=f"Min Elevation: {min_elev:.1f} ft")
                self.max_elevation_label.config(text=f"Max Elevation: {max_elev:.1f} ft")

                # Draw axes
                self.profile_canvas.create_line(padding, canvas_height-padding,
                                             canvas_width-padding, canvas_height-padding,
                                             width=2)  # X-axis
                self.profile_canvas.create_line(padding, padding,
                                             padding, canvas_height-padding,
                                             width=2)  # Y-axis

                # Plot elevation profile
                x_scale = (canvas_width - 2*padding) / (len(elevations) - 1)
                y_scale = (canvas_height - 2*padding) / elev_range if elev_range > 0 else 1

                points = []
                for i, elev in enumerate(elevations):
                    x = padding + i * x_scale
                    y = canvas_height - padding - (elev - min_elev) * y_scale
                    points.extend([x, y])

                # Draw profile line
                self.profile_canvas.create_line(points, fill="blue", width=2, smooth=True)

                # Add site labels
                self.profile_canvas.create_text(padding, canvas_height-5,
                                             text=site_a_name, anchor="w")
                self.profile_canvas.create_text(canvas_width-padding, canvas_height-5,
                                             text=site_b_name, anchor="e")

        except Exception as e:
            logger.error(f"Error updating elevation profile: {e}")
            messagebox.showerror("Error", f"Failed to update elevation profile: {e}")

    def generate_path_points(self, lat1, lon1, lat2, lon2, num_points):
        """Generate evenly spaced points along the path"""
        points = []
        for i in range(num_points):
            t = i / (num_points - 1)
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            points.append((lat, lon))

    def export_rings_for_sites(self):
        """Export search rings for sites in selected project coordinate system."""
        try:
            if not hasattr(self, 'root'):
                self.root = tk.Tk()
                self.root.withdraw()

            if not self.donor_site or not self.recipient_site:
                messagebox.showerror("Error", "Both donor and recipient site data must be loaded first")
                return

            # Get list of projects with their metadata
            projects = []
            for name, metadata in self.project_metadata.projects.items():
                coord_sys = metadata.get('spatial_ref', {}).get('coordinate_system', {})
                if coord_sys:
                    projects.append(metadata)

            if not projects:
                messagebox.showerror("Error", "No LIDAR projects with coordinate system information found")
                return

            # Show project selection dialog
            dialog = ProjectSelectionDialog(self.root, projects)
            self.root.wait_window(dialog)

            if dialog.selected_project is None:
                return

            # Get selected project data
            project_data = dialog.selected_project
            logger.info(f"Selected project: {project_data.get('name', 'Unknown')}")

            # Get save directory
            initial_dir = os.path.expanduser("~")
            save_dir = filedialog.askdirectory(
                title="Select Directory to Save Search Rings",
                initialdir=initial_dir
            )

            if not save_dir:  # User cancelled
                return

            save_dir = str(save_dir)  # Ensure save_dir is a string
            logger.info(f"Saving search rings to directory: {save_dir}")

            # Initialize search ring generator
            ring_gen = SearchRingGenerator(self.project_metadata)
            if not ring_gen.select_project(project_data):
                messagebox.showerror("Error", "Could not initialize coordinate system")
                return

            success = True
            exported_files = []

            # Export donor rings
            logger.info("Generating donor site search rings...")
            self.donor_site['is_donor'] = True
            donor_rings = ring_gen.generate_rings(self.donor_site)
            if donor_rings:
                if ring_gen.export_rings(save_dir, donor_rings, self.donor_site):
                    exported_files.append(os.path.join(save_dir, f"search_rings_donor_{self.donor_site['site_id']}.xyz"))
                    logger.info("Successfully exported donor rings")
                else:
                    success = False
                    logger.error("Failed to export donor rings")

            # Export recipient rings
            logger.info("Generating recipient site search rings...")
            self.recipient_site['is_donor'] = False
            recipient_rings = ring_gen.generate_rings(self.recipient_site)
            if recipient_rings:
                if ring_gen.export_rings(save_dir, recipient_rings, self.recipient_site):
                    exported_files.append(os.path.join(save_dir, f"search_rings_recipient_{self.recipient_site['site_id']}.xyz"))
                    logger.info("Successfully exported recipient rings")
                else:
                    success = False
                    logger.error("Failed to export recipient rings")

            if success:
                message = "Search rings exported successfully:\n\n"
                message += "\n".join(exported_files)
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", "There were problems exporting some search rings")

        except Exception as e:
            logger.error(f"Error in search rings export: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search rings: {str(e)}")

    def edit_sites(self):
        """Edit existing site coordinates"""
        try:
            from utilities.site_manager import edit_sites as site_manager_edit_sites
            # Use the imported convert_dms_to_decimal function
            from utilities.UI_main import ManualSitesDialog

            # Call the edit_sites function from site_manager.py with the required arguments
            site_manager_edit_sites(
                root=self.root,
                convert_dms_to_decimal=coords_convert_dms_to_decimal,
                calculate_distance=calculate_distance,
                update_details_in_app=update_details_in_app,
                ManualSitesDialog=ManualSitesDialog,
                lidar_downloader=self  # Pass self as the lidar_downloader parameter
            )
        except Exception as e:
            logger.error(f"Error in edit_sites: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to edit sites: {str(e)}")

    def update_site_data(self, site_a, site_b):
        """Update the donor and recipient site data"""
        logger.info("Updating site data in LidarDownloader")
        self.donor_site = site_a
        self.recipient_site = site_b
        logger.debug(f"Updated site data - Donor: {site_a}, Recipient: {site_b}")

        # Update polygon with current width
        if site_a and site_b:
            lat_a, lon_a = coords_convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
            lat_b, lon_b = coords_convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
            self.polygon_points = calculate_polygon_points(
                (lat_a, lon_a),
                (lat_b, lon_b),
                self.polygon_width_ft.get()
            )

    def convert_dms_to_decimal(self, lat_dms, lon_dms):
        """Convert DMS coordinates to decimal degrees"""
        def parse_dms(dms):
            parts = re.match(r'(\d+)-(\d+)-(\d+\.?\d*)\s*([NSEW])', dms).groups()
            deg, min, sec, dir = float(parts[0]), float(parts[1]), float(parts[2]), parts[3]
            dec = deg + min/60 + sec/3600
            if dir in ['S', 'W']:
                dec = -dec
            return dec

        return parse_dms(lat_dms), parse_dms(lon_dms)

    def set_selected_lidar(self, lidar_data):
        """Store selected LIDAR file metadata"""
        self.selected_lidar = lidar_data
        logger.info(f"Selected LIDAR file metadata updated: {lidar_data}")

    def find_turbines(self):
        """Search for wind turbines within the LIDAR path area"""
        # Call the turbine processor with all necessary info
        return self.turbine_processor.find_turbines(
            self.polygon_points,
            self.obstruction_text
        )

    def find_state_turbines(self):
        """Search for all wind turbines in the state containing the LOS path"""
        # Call the turbine processor
        return self.turbine_processor.find_state_turbines(
            None,  # Let the processor determine the state
            self.donor_site,
            self.recipient_site,
            self.obstruction_text
        )

    def clear_turbines(self):
        """Clear all turbine visualizations from the map"""
        self.turbine_processor.clear_turbines()

    def toggle_turbine_labels(self):
        """Toggle visibility of turbine labels"""
        self.turbine_processor.toggle_turbine_labels()

    def search_towers(self):
        """Search for towers within the LIDAR search polygon"""
        logger.info("Searching for towers within the LIDAR search polygon")
        try:
            # Check if we have a valid polygon
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "Please define a search area first by loading a project.")
                return

            # Ensure tower database exists and is populated
            if not ensure_tower_database_exists():
                messagebox.showerror("Error", "Failed to initialize tower database. Please check the logs for details.")
                return

            # Create progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Searching for Towers")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()

            # Add progress information
            ttk.Label(progress_window, text="Searching for towers in the area...", font=("Arial", 10, "bold")).pack(pady=10)
            progress_var = tk.DoubleVar()
            ttk.Progressbar(progress_window, variable=progress_var, maximum=100).pack(fill="x", padx=20, pady=10)
            status_label = ttk.Label(progress_window, text="Initializing search...")
            status_label.pack(pady=5)

            # Update progress
            progress_var.set(10)
            status_label.config(text="Preparing search parameters...")
            progress_window.update()

            # Define a function to run the search in a separate thread
            def search_thread():
                try:
                    # Convert polygon points to (lon, lat) format for search
                    search_polygon = [(point[1], point[0]) for point in self.polygon_points]

                    # Update progress
                    progress_var.set(30)
                    status_label.config(text="Searching tower database...")
                    progress_window.update()

                    # Search for towers
                    towers = search_towers_in_polygon(search_polygon)

                    # Update progress
                    progress_var.set(90)
                    status_label.config(text="Processing results...")
                    progress_window.update()

                    # Update UI in main thread
                    self.root.after(0, lambda: self._display_tower_results(towers, progress_window))
                except Exception as e:
                    logger.error(f"Error in tower search thread: {e}", exc_info=True)
                    self.root.after(0, lambda: self._handle_tower_search_error(e, progress_window))

            # Start search thread
            Thread(target=search_thread).start()

        except Exception as e:
            logger.error(f"Error searching for towers: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to search for towers: {str(e)}")

    def _display_tower_results(self, towers, progress_window):
        """Display tower search results on the map using triangle polygons"""
        try:
            # Close progress window
            progress_window.destroy()

            # Check if we found any towers
            if not towers:
                messagebox.showinfo("Tower Search", "No towers found within the search area.")
                return

            # Store the tower data for later use
            self.tower_data = towers

            # Display towers on map
            if self.map_widget:
                # Clear any existing tower visualizations
                self._clear_tower_visualizations()

                # Create a list to store tower polygons
                self.tower_polygons = []

                # Add tower triangles
                for tower in towers:
                    # Get tower data
                    lat = tower.get('decimal_latitude')
                    lon = tower.get('decimal_longitude')
                    tower_id = tower.get('unique_system_id')

                    if lat is not None and lon is not None:
                        # Create a triangle polygon for the tower
                        # Calculate triangle points (small triangle around the tower location)
                        size = 0.0005  # Size of triangle in degrees (adjust as needed)
                        triangle_points = [
                            (lat, lon),  # Center point
                            (lat + size, lon - size/2),  # Bottom right
                            (lat + size, lon + size/2),  # Bottom left
                        ]

                        # Create the triangle polygon
                        polygon = self.map_widget.set_polygon(
                            triangle_points,
                            fill_color="red",  # Red fill
                            outline_color="black",  # Black outline
                            border_width=1,
                            command=lambda t=tower: self._show_tower_info(t)
                        )

                        # Store the tower data with the polygon
                        polygon.tower_data = tower

                        # Add to our list of tower polygons
                        self.tower_polygons.append(polygon)

            # Show message with count
            messagebox.showinfo("Tower Search", f"Found {len(towers)} towers within the search area.")

            # Add a button to toggle tower visibility if it doesn't exist
            self._add_tower_toggle_button()

        except Exception as e:
            logger.error(f"Error displaying tower results: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to display tower results: {str(e)}")

    def _clear_tower_visualizations(self):
        """Clear all tower visualizations from the map"""
        try:
            # Check if we have tower polygons to clear
            if hasattr(self, 'tower_polygons') and self.tower_polygons:
                for polygon in self.tower_polygons:
                    try:
                        # Delete the polygon from the map
                        self.map_widget.delete(polygon)
                    except Exception as e:
                        logger.warning(f"Error deleting tower polygon: {e}")

                # Clear the list
                self.tower_polygons = []

        except Exception as e:
            logger.error(f"Error clearing tower visualizations: {e}", exc_info=True)

    def _add_tower_toggle_button(self):
        """Add a button to toggle tower visibility if it doesn't exist"""
        try:
            # Check if we already have the button in the obstruction search frame
            if hasattr(self, 'toggle_towers_button') and self.toggle_towers_button:
                return

            # Find the obstruction search frame
            for widget in self.root.winfo_children():
                if isinstance(widget, tk.PanedWindow):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Frame):
                            for frame in child.winfo_children():
                                if isinstance(frame, ttk.LabelFrame) and frame.winfo_children() and \
                                   hasattr(frame, 'cget') and frame.cget('text') == "Obstruction Search":
                                    # Found the obstruction search frame
                                    for button_frame in frame.winfo_children():
                                        if isinstance(button_frame, ttk.Frame):
                                            # Create the toggle button
                                            self.tower_visibility = tk.BooleanVar(value=True)
                                            self.toggle_towers_button = ttk.Button(
                                                button_frame,
                                                text="Toggle Towers",
                                                command=self._toggle_tower_visibility,
                                                style='Obstruction.TButton'
                                            )

                                            # Find an empty grid cell to place the button
                                            # Try to place it in row 1
                                            try:
                                                self.toggle_towers_button.grid(row=1, column=0, padx=2, pady=2, sticky="ew")
                                                return
                                            except Exception:
                                                # If that fails, try other positions
                                                try:
                                                    self.toggle_towers_button.grid(row=1, column=1, padx=2, pady=2, sticky="ew")
                                                    return
                                                except Exception:
                                                    # Last resort, just pack it
                                                    self.toggle_towers_button.pack(fill="x", padx=2, pady=2)
                                                    return

            # If we couldn't find the obstruction search frame, log a warning
            logger.warning("Could not find obstruction search frame to add tower toggle button")

        except Exception as e:
            logger.error(f"Error adding tower toggle button: {e}", exc_info=True)

    def _toggle_tower_visibility(self):
        """Toggle the visibility of tower visualizations"""
        try:
            # Check if we have tower polygons
            if not hasattr(self, 'tower_polygons') or not self.tower_polygons:
                messagebox.showinfo("No Towers", "No tower visualizations to toggle.")
                return

            # Toggle the visibility state
            if not hasattr(self, 'tower_visibility'):
                self.tower_visibility = tk.BooleanVar(value=True)

            # Flip the current value
            current_visibility = self.tower_visibility.get()
            self.tower_visibility.set(not current_visibility)

            # Update the button text
            if hasattr(self, 'toggle_towers_button') and self.toggle_towers_button:
                new_state = self.tower_visibility.get()
                self.toggle_towers_button.config(text="Hide Towers" if new_state else "Show Towers")

            # Update the visibility of all tower polygons
            for polygon in self.tower_polygons:
                if self.tower_visibility.get():
                    # Show the polygon
                    polygon.configure(state="normal")
                    polygon.configure(fill_color="red")
                else:
                    # Hide the polygon (make it transparent)
                    polygon.configure(state="disabled")
                    polygon.configure(fill_color="")

        except Exception as e:
            logger.error(f"Error toggling tower visibility: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to toggle tower visibility: {str(e)}")


    def _handle_tower_search_error(self, error, progress_window):
        """Handle errors in tower search"""
        try:
            # Close progress window
            progress_window.destroy()

            # Show error message
            messagebox.showerror("Tower Search Error", f"Error searching for towers: {str(error)}")

        except Exception as e:
            logger.error(f"Error handling tower search error: {e}", exc_info=True)

    def _show_tower_info(self, tower):
        """Show information about a tower"""
        try:
            # Create info window
            info_window = tk.Toplevel(self.root)
            info_window.title(f"Tower Information")
            info_window.geometry("500x400")
            info_window.transient(self.root)

            # Create scrollable frame
            main_frame = ttk.Frame(info_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)

            canvas = tk.Canvas(main_frame)
            scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            # Add tower information
            ttk.Label(scrollable_frame, text="Tower Information", font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 10))

            # Basic information
            basic_frame = ttk.LabelFrame(scrollable_frame, text="Basic Information")
            basic_frame.pack(fill="x", pady=5)

            # Add fields
            fields = [
                ("Tower ID", tower.get('unique_system_id', 'Unknown')),
                ("Structure Type", tower.get('structure_type', 'Unknown')),
                ("Height", f"{tower.get('overall_height_ground', 'Unknown')} ft"),
                ("Ground Elevation", f"{tower.get('ground_elevation', 'Unknown')} ft"),
                ("Overall Height AMSL", f"{tower.get('overall_height_amsl', 'Unknown')} ft"),
                ("Latitude", tower.get('decimal_latitude', 'Unknown')),
                ("Longitude", tower.get('decimal_longitude', 'Unknown')),
                ("Status", tower.get('status_code', 'Unknown')),
                ("Date Constructed", tower.get('date_constructed', 'Unknown')),
                ("Date Dismantled", tower.get('date_dismantled', 'Unknown') if tower.get('date_dismantled') else 'N/A'),
            ]

            for i, (label, value) in enumerate(fields):
                ttk.Label(basic_frame, text=f"{label}:", width=20, anchor="e").grid(row=i, column=0, padx=5, pady=2, sticky="e")
                ttk.Label(basic_frame, text=str(value)).grid(row=i, column=1, padx=5, pady=2, sticky="w")

            # Location information
            location_frame = ttk.LabelFrame(scrollable_frame, text="Location Information")
            location_frame.pack(fill="x", pady=5)

            location_fields = [
                ("Street", tower.get('structure_street', 'Unknown')),
                ("City", tower.get('structure_city', 'Unknown')),
                ("State", tower.get('structure_state', 'Unknown')),
                ("County Code", tower.get('county_code', 'Unknown')),
                ("Zip Code", tower.get('zip_code', 'Unknown')),
            ]

            for i, (label, value) in enumerate(location_fields):
                ttk.Label(location_frame, text=f"{label}:", width=20, anchor="e").grid(row=i, column=0, padx=5, pady=2, sticky="e")
                ttk.Label(location_frame, text=str(value)).grid(row=i, column=1, padx=5, pady=2, sticky="w")

            # FAA information
            faa_frame = ttk.LabelFrame(scrollable_frame, text="FAA Information")
            faa_frame.pack(fill="x", pady=5)

            faa_fields = [
                ("FAA Study Number", tower.get('faa_study_number', 'Unknown')),
                ("FAA Circular Number", tower.get('faa_circular_number', 'Unknown')),
                ("Date of FAA Determination", tower.get('date_faa_determination', 'Unknown')),
                ("Painting and Lighting", tower.get('painting_and_lighting', 'Unknown')),
            ]

            for i, (label, value) in enumerate(faa_fields):
                ttk.Label(faa_frame, text=f"{label}:", width=20, anchor="e").grid(row=i, column=0, padx=5, pady=2, sticky="e")
                ttk.Label(faa_frame, text=str(value)).grid(row=i, column=1, padx=5, pady=2, sticky="w")

            # Add close button
            ttk.Button(scrollable_frame, text="Close", command=info_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error showing tower info: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to show tower information: {str(e)}")


    def process_lidar_results(self, results):
        """Process LIDAR results returned from search and display on map"""
        try:
            logger.info(f"Processing {len(results)} LIDAR results")

            # Clear existing polygons
            for polygon in self.lidar_polygons:
                self.map_widget.delete(polygon)
            self.lidar_polygons = []

            files_within_polygon = 0
            unique_projects = set()
            self.project_colors = {}

            # Process results
            for item in results:
                url = item.get('downloadURL', '')
                filename = url.split('/')[-1]
                project_name = get_project_name(filename)
                unique_projects.add(project_name)

                # Assign color if not already assigned
                if project_name not in self.project_colors:
                    color_index = len(self.project_colors) % len(self.color_series)
                    self.project_colors[project_name] = self.color_series[color_index]

                # Draw polygon if coordinates are available
                bbox = item.get('boundingBox')
                if bbox:
                    try:
                        polygon_points = [
                            (bbox['minY'], bbox['minX']),
                            (bbox['minY'], bbox['maxX']),
                            (bbox['maxY'], bbox['maxX']),
                            (bbox['maxY'], bbox['minX']),
                            (bbox['minY'], bbox['minX'])  # Closing point
                        ]

                        polygon = self.map_widget.set_polygon(
                            polygon_points,
                            fill_color="",
                            outline_color=self.project_colors[project_name],
                            border_width=2,
                            name=f"LIDAR_{project_name}"
                        )

                        # Add to list of polygons
                        self.lidar_polygons.append(polygon)
                        files_within_polygon += 1

                        # Store item info in polygon
                        polygon.item_data = item
                        color = self.project_colors[project_name]

                        # Store metadata for download
                        self.process_lidar_file(item, color)
                    except Exception as e:
                        logger.error(f"Error drawing polygon: {e}")

            logger.info(f"Found {files_within_polygon} files within search area across {len(unique_projects)} projects")

            # Update UI with result count
            if hasattr(self, 'results_label'):
                self.results_label.config(text=f"Results: {files_within_polygon} files in {len(unique_projects)} projects")

            # Update tile count info
            if hasattr(self, 'tile_info_label'):
                self.tile_info_label.config(text=f"Files within polygon: {files_within_polygon}")

            return files_within_polygon
        except Exception as e:
            logger.error(f"Error processing LIDAR results: {e}", exc_info=True)
            return 0

    def capture_coverage_map(self, project_bounds, site_a, site_b):
        """Capture a map image showing project coverage and LOS path"""
        logger.info("=== Starting coverage map capture process ===")

        try:
            # Calculate window size
            window_width = 800
            map_height = 450  # Fixed map height (16:9 ratio)
            header_height = 30
            button_height = 50
            padding = 40
            total_height = map_height + header_height + button_height + padding

            # Create preview window
            preview_window = tk.Toplevel(self.root)
            preview_window.title("Coverage Map Preview")
            preview_window.geometry(f"{window_width + 20}x{total_height}")
            preview_window.transient(self.root)
            preview_window.grab_set()
            preview_window.lift()
            preview_window.attributes('-topmost', True)
            preview_window.resizable(False, False)

            # Variable to store result
            result = {'path': None}

            # Create map widget
            preview_map = tkintermapview.TkinterMapView(
                preview_window,
                width=window_width,
                height=map_height,
                corner_radius=0
            )
            preview_map.pack(padx=10, pady=5)

            # Collect all LIDAR file bounds for the project
            try:
                logger.debug("Collecting all LIDAR file bounds")
                all_bounds = []
                project_name = project_bounds.get('project_name')

                # Get bounds from all files in the project
                for item in self.file_list.get_children():
                    values = self.file_list.item(item)['values']
                    if len(values) >= 5 and values[4] == project_name:
                        bbox = values[5] if len(values) > 5 else None
                        if bbox and isinstance(bbox, dict):
                            all_bounds.append({
                                'minY': float(bbox['minY']),
                                'maxY': float(bbox['maxY']),
                                'minX': float(bbox['minX']),
                                'maxX': float(bbox['maxX'])
                            })

                # Calculate overall bounds
                if all_bounds:
                    min_lat = min(b['minY'] for b in all_bounds)
                    max_lat = max(b['maxY'] for b in all_bounds)
                    min_lon = min(b['minX'] for b in all_bounds)
                    max_lon = max(b['maxX'] for b in all_bounds)
                else:
                    # Fallback to project bounds
                    min_lat = float(project_bounds['minY'])
                    max_lat = float(project_bounds['maxY'])
                    min_lon = float(project_bounds['minX'])
                    max_lon = float(project_bounds['maxX'])

                # Add LOS path coordinates
                lat_a, lon_a = coords_convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
                lat_b, lon_b = coords_convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])

                # Update bounds to include LOS path
                min_lat = min(min_lat, lat_a, lat_b)
                max_lat = max(max_lat, lat_a, lat_b)
                min_lon = min(min_lon, lon_a, lon_b)
                max_lon = max(max_lon, lon_a, lon_b)

                # Add padding (10%)
                lat_span = max_lat - min_lat
                lon_span = max_lon - min_lon
                min_lat -= lat_span * 0.1
                max_lat += lat_span * 0.1
                min_lon -= lon_span * 0.1
                max_lon += lon_span * 0.1

                # Set map center
                center_lat = (min_lat + max_lat) / 2
                center_lon = (min_lon + max_lon) / 2
                preview_map.set_position(center_lat, center_lon)

                # Calculate zoom level based on bounds
                # Use the larger span to ensure everything fits
                span = max(lat_span, lon_span)
                zoom = max(1, min(20, int(-1.44 * math.log(span) + 12.5)))
                logger.debug(f"Setting zoom level: {zoom}")
                preview_map.set_zoom(zoom)

                # Draw all LIDAR file boundaries
                for bounds in all_bounds:
                    boundary_points = [
                        (bounds['minY'], bounds['minX']),
                        (bounds['minY'], bounds['maxX']),
                        (bounds['maxY'], bounds['maxX']),
                        (bounds['maxY'], bounds['minX']),
                        (bounds['minY'], bounds['minX'])  # Add comma here
                    ]  # Close the list bracket
                    preview_map.set_polygon(
                        boundary_points,
                        outline_color="blue",
                        fill_color=None,
                        border_width=1
                    )

                # Add site markers
                preview_map.set_marker(
                    lat_a, lon_a,
                    text=site_a['site_id'],
                    text_color="black",
                    marker_color_outside="red"
                )
                preview_map.set_marker(
                    lat_b, lon_b,
                    text=site_b['site_id'],
                    text_color="black",
                    marker_color_outside="blue"
                )

                # Draw LOS path
                preview_map.set_path(
                    [(lat_a, lon_a), (lat_b, lon_b)],
                    color="red",
                    width=2
                )

            except Exception as e:
                logger.error(f"Error processing map elements: {e}", exc_info=True)
                raise

            def capture_and_close():
                """Capture the map and close the preview window"""
                try:
                    logger.info("User initiated map capture")
                    # Ensure map is fully loaded
                    preview_window.update_idletasks()
                    time.sleep(2)  # Increased wait time for map rendering

                    # Get map widget coordinates
                    x = preview_map.winfo_rootx()
                    y = preview_map.winfo_rooty()
                    width = preview_map.winfo_width()
                    height = preview_map.winfo_height()

                    logger.debug(f"Capture coordinates: x={x}, y={y}, width={width}, height={height}")

                    # Force update and wait for rendering
                    preview_window.update()
                    time.sleep(0.5)

                    # Capture the map widget only
                    image = ImageGrab.grab(bbox=(x, y, x+width, y+height))

                    # Save image
                    temp_dir = "temp"
                    if not os.path.exists(temp_dir):
                        os.makedirs(temp_dir)

                    image_path = os.path.join(temp_dir, "coverage_map.png")
                    image.save(image_path)

                    # Verify capture
                    if os.path.exists(image_path):
                        file_size = os.path.getsize(image_path)
                        logger.info(f"Map captured and saved ({file_size} bytes): {image_path}")
                        result['path'] = image_path
                        preview_window.destroy()
                    else:
                        raise Exception("Failed to save map image")

                except Exception as e:
                    logger.error(f"Error capturing map: {e}", exc_info=True)
                    messagebox.showerror("Error", f"Failed to capture map: {str(e)}")

            # Add buttons
            button_frame = ttk.Frame(preview_window, height=button_height)
            button_frame.pack(fill="x", padx=10, pady=10)
            button_frame.pack_propagate(False)

            ttk.Button(
                button_frame,
                text="Capture",
                command=capture_and_close
            ).pack(side="right", padx=5)

            ttk.Button(
                button_frame,
                text="Cancel",
                command=preview_window.destroy
            ).pack(side="right", padx=5)

            # Wait for user action
            preview_window.wait_window()

            return result['path']

        except Exception as e:
            logger.error(f"Error in coverage map capture process: {e}", exc_info=True)
            if 'preview_window' in locals():
                preview_window.destroy()
            return None

    def _add_turbine_visualization(self, turbine):
        """Add visualization for a single turbine - forwards to turbine_processor"""
        return self.turbine_processor.add_turbine_visualization(turbine)

    def point_in_polygon(self, point, polygon):
        """Check if a point is inside a polygon using ray casting algorithm"""
        x, y = point
        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def _capture_map_view(self):
        """Capture current map view as image"""
        try:
            # Create temp directory if it doesn't exist
            temp_dir = "temp"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
                logger.info(f"Created temporary directory: {temp_dir}")

            # Save map screenshot
            image_path = os.path.join(temp_dir, f"map_view_{int(time.time())}.png")

            # Force update and wait for rendering
            self.map_widget.update()
            self.root.update()  # Update the entire window
            time.sleep(1.0)  # Wait longer for rendering to complete

            # Get map widget coordinates
            x = self.map_widget.winfo_rootx()
            y = self.map_widget.winfo_rooty()
            width = self.map_widget.winfo_width()
            height = self.map_widget.winfo_height()

            logger.info(f"Capturing map view at coordinates: x={x}, y={y}, width={width}, height={height}")

            # Capture screenshot
            try:
                # Ensure PIL is imported
                from PIL import ImageGrab, Image

                # Capture the screenshot
                image = ImageGrab.grab(bbox=(x, y, x+width, y+height))

                # Save the image with high quality
                image.save(image_path, format='PNG', quality=95)
                logger.info(f"Map view captured and saved to: {image_path}")

                # Verify the image was saved correctly
                if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                    logger.info(f"Image file verified: {os.path.getsize(image_path)} bytes")
                    return image_path
                else:
                    logger.error(f"Image file not created or empty: {image_path}")
                    raise Exception("Failed to save image file")

            except Exception as grab_error:
                logger.error(f"Error capturing screenshot: {grab_error}", exc_info=True)
                # Try alternative method if available
                try:
                    # Alternative method for platforms where ImageGrab might not work well
                    from PIL import Image
                    import io

                    logger.info("Attempting alternative screenshot method using PostScript")

                    # Create a PostScript representation of the widget
                    ps_data = self.map_widget.postscript(colormode='color')

                    # Convert the PostScript to an image
                    img = Image.open(io.BytesIO(ps_data.encode('utf-8')))
                    img.save(image_path, 'PNG')
                    logger.info(f"Map view captured using alternative method and saved to: {image_path}")

                    # Verify the image was saved correctly
                    if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                        logger.info(f"Image file verified (alternative method): {os.path.getsize(image_path)} bytes")
                        return image_path
                    else:
                        logger.error(f"Image file not created or empty (alternative method): {image_path}")
                        raise Exception("Failed to save image file using alternative method")

                except Exception as alt_error:
                    logger.error(f"Alternative screenshot method also failed: {alt_error}", exc_info=True)

                    # Last resort: try to create a blank image with text
                    try:
                        logger.info("Creating fallback blank image with text")
                        from PIL import Image, ImageDraw, ImageFont

                        # Create a blank white image
                        img = Image.new('RGB', (width, height), color='white')
                        draw = ImageDraw.Draw(img)

                        # Add text explaining the issue
                        text = "Map image capture failed"
                        try:
                            font = ImageFont.truetype("arial.ttf", 20)
                        except:
                            font = ImageFont.load_default()

                        # Calculate text position to center it
                        text_width = draw.textlength(text, font=font)
                        text_position = ((width - text_width) / 2, height / 2)

                        # Draw the text
                        draw.text(text_position, text, fill='black', font=font)

                        # Save the image
                        img.save(image_path)
                        logger.info(f"Created fallback image at: {image_path}")
                        return image_path
                    except Exception as fallback_error:
                        logger.error(f"Fallback image creation failed: {fallback_error}", exc_info=True)
                        raise

        except Exception as e:
            logger.error(f"Error capturing map view: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to capture map view: {str(e)}")
            return None

    def center_map_on_path(self):
        """Center the map view on the path and zoom appropriately"""
        try:
            if not hasattr(self, 'polygon_points') or len(self.polygon_points) < 2:
                logger.warning("No polygon points available to center map")
                return

            # Get path endpoints
            path_start = self.polygon_points[0]
            path_end = self.polygon_points[-1]

            # Calculate center point
            center_lat = (path_start[0] + path_end[0]) / 2
            center_lon = (path_start[1] + path_end[1]) / 2

            # Find the min/max bounds to include both sites and any turbines
            # Start with path points
            min_lat = min(path_start[0], path_end[0])
            max_lat = max(path_start[0], path_end[0])
            min_lon = min(path_start[1], path_end[1])
            max_lon = max(path_start[1], path_end[1])

            # Include turbines in bounds calculation if available
            turbines = self.turbine_processor.last_turbines
            if turbines:
                logger.info(f"Including {len(turbines)} turbines in map bounds calculation")
                for turbine in turbines:
                    try:
                        t_lat = turbine.get('latitude') or turbine.get('ylat')
                        t_lon = turbine.get('longitude') or turbine.get('xlong')

                        if t_lat is not None and t_lon is not None:
                            min_lat = min(min_lat, float(t_lat))
                            max_lat = max(max_lat, float(t_lat))
                            min_lon = min(min_lon, float(t_lon))
                            max_lon = max(max_lon, float(t_lon))
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Skipping turbine in bounds calculation: {e}")

            # Add padding (20% on each side)
            lat_range = max_lat - min_lat
            lon_range = max_lon - min_lon

            # Ensure minimum ranges to avoid zero padding
            lat_range = max(lat_range, 0.01)
            lon_range = max(lon_range, 0.01)

            padding_lat = lat_range * 0.2
            padding_lon = lon_range * 0.2

            min_lat -= padding_lat
            max_lat += padding_lat
            min_lon -= padding_lon
            max_lon += padding_lon

            logger.info(f"Map bounds with padding: [{min_lat:.6f}, {min_lon:.6f}] to [{max_lat:.6f}, {max_lon:.6f}]")

            # Calculate haversine distance to determine appropriate zoom
            def haversine_distance(lat1, lon1, lat2, lon2):
                R = 6371000  # Earth's radius in meters
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c

            # Calculate diagonal distance across the bounding box
            diagonal_distance = haversine_distance(min_lat, min_lon, max_lat, max_lon)

            # Calculate zoom level based on diagonal distance
            # These are adjusted to ensure good framing
            if diagonal_distance < 2000:  # Less than 2km
                zoom = 14
            elif diagonal_distance < 5000:  # Less than 5km
                zoom = 13
            elif diagonal_distance < 10000:  # Less than 10km
                zoom = 12
            elif diagonal_distance < 20000:  # Less than 20km
                zoom = 11
            elif diagonal_distance < 50000:  # Less than 50km
                zoom = 10
            elif diagonal_distance < 100000:  # Less than 100km
                zoom = 9
            else:
                zoom = 8

            # Calculate center from the bounds
            center_lat = (min_lat + max_lat) / 2
            center_lon = (min_lon + max_lon) / 2

            # Set map position and zoom
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)

            # Force update to ensure the map rendering is complete
            self.map_widget.update()

            logger.info(f"Centered map on bounds center: ({center_lat:.6f}, {center_lon:.6f}), zoom: {zoom}")

        except Exception as e:
            logger.error(f"Error centering map on path: {e}", exc_info=True)

    def _on_width_change(self, *args):
        """Update the polygon when the width changes"""
        try:
            if hasattr(self, 'donor_site') and hasattr(self, 'recipient_site'):
                if self.donor_site and self.recipient_site:
                    # Get current width value
                    try:
                        width = self.polygon_width_ft.get()
                    except tk.TclError:
                        # If invalid value in spinbox, use default
                        width = 2000
                        self.polygon_width_ft.set(width)

                    # Convert coordinates
                    lat_a, lon_a = coords_convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
                    lat_b, lon_b = coords_convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])

                    # Update polygon points with extension past both sites
                    self.polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), width)  # Now extends 1000 feet past both sites by default

                    # Clear existing polygons and LIDAR results
                    self.map_widget.delete_all_polygon()
                    self.lidar_polygons = []

                    # Clear LIDAR results from UI
                    if hasattr(self, 'file_list'):
                        self.file_list.delete(*self.file_list.get_children())
                    if hasattr(self, 'legend_items_frame'):
                        for widget in self.legend_items_frame.winfo_children():
                            widget.destroy()
                        # Add "No LIDAR data loaded" label
                        ttk.Label(
                            self.legend_items_frame,
                            text="No LIDAR data loaded",
                            foreground="gray"
                        ).pack(anchor="w", padx=5, pady=2)

                    # Draw new polygon
                    polygon_around_path = self.map_widget.set_polygon(
                        self.polygon_points,
                        fill_color=None,
                        outline_color="black",
                        border_width=1,
                        name="LOS Polygon"
                    )

                    logger.debug(f"Updated polygon width to {width} feet")
        except Exception as e:
            logger.error(f"Error updating polygon width: {e}")

    def add_all_files_to_download(self):
        """Add all files from the currently selected project to the download queue"""
        try:
            # Get the currently selected project from the dropdown
            selected_project = self.project_details.project_combobox.get()
            logger.info(f"Attempting to add files from project: {selected_project}")

            if not selected_project or selected_project == "Overview":
                logger.warning("No specific project selected in dropdown")
                messagebox.showwarning("No Project Selected",
                                     "Please select a specific project from the dropdown first.")
                return

            # Deselect all files first
            self.deselect_all()
            logger.info("Cleared previous selections")

            # Get all items in the file list
            items = self.file_list.get_children()
            logger.info(f"Found {len(items)} total files in list")
            files_added = 0

            # Log all project names in the file list for debugging
            project_files = {}
            for item in items:
                values = self.file_list.item(item)['values']
                if values and len(values) >= 5:
                    project_name = values[4]  # Project name in 5th column
                    if project_name not in project_files:
                        project_files[project_name] = 0
                    project_files[project_name] += 1

            logger.info(f"Projects in file list: {project_files}")

            # Select only files from the current project - check all possible columns
            for item in items:
                values = self.file_list.item(item)['values']
                logger.debug(f"Processing item: {values}")

                # Check if this item belongs to the selected project
                # Try both column 4 (index 4) and the last column
                is_project_match = False

                # Check column 4 (index 4)
                if values and len(values) >= 5 and values[4] == selected_project:
                    is_project_match = True

                # Also check the last column
                if values and len(values) >= 1 and values[-1] == selected_project:
                    is_project_match = True

                if is_project_match:
                    logger.debug(f"Setting checkbox for file in project {selected_project}")
                    # Update checkbox display
                    current_values = list(values)
                    current_values[0] = "✓"  # Set checkbox to checked
                    self.file_list.item(item, values=current_values)

                    # Get URL from item_url_map and add to selected files
                    url = self.item_url_map.get(item)
                    if url:
                        self.selected_files.add(url)
                        files_added += 1
                        logger.debug(f"Added URL to selection: {url}")
                    else:
                        logger.warning(f"No URL found for item {item}")

            logger.info(f"Selected {files_added} files from project {selected_project}")

            # Add selected files to downloads if any were selected
            if files_added > 0:
                logger.info("Adding selected files to download queue...")
                self.add_to_downloads()
                messagebox.showinfo(
                    "Files Added",
                    f"Added {files_added} files from project '{selected_project}' to download queue.\nClick 'Start' in the downloader to begin downloading."
                )
                logger.info(f"Successfully added {files_added} files from project {selected_project} to downloads")
            else:
                logger.warning(f"No files found for project {selected_project}")
                messagebox.showwarning(
                    "No Files",
                    f"No files found for project '{selected_project}'. Try searching for LIDAR data first."
                )

        except Exception as e:
            logger.error(f"Error adding all files to download: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add files to download queue: {str(e)}")

    def select_project_for_download(self):
        """Open project selection dialog and add selected project's files to download"""
        try:
            # Get list of available projects from metadata
            projects = []
            for project_name in self.project_metadata.projects:
                project_data = self.project_metadata.get_project(project_name)
                if project_data:
                    projects.append(project_data)

            if not projects:
                messagebox.showwarning(
                    "No Projects",
                    "No LIDAR projects available. Please search for LIDAR data first."
                )
                return

            # Create and show project selection dialog
            dialog = ProjectSelectionDialog(self.parent, projects)
            self.parent.wait_window(dialog)

            # Handle selected project
            if dialog.selected_project:
                project_name = dialog.selected_project.get('name')
                logger.info(f"Selected project: {project_name}")

                # Deselect all files first
                self.deselect_all()

                # Select files for the chosen project - check all possible columns
                files_added = 0
                for item in self.file_list.get_children():
                    values = self.file_list.item(item)['values']

                    # Check if this item belongs to the selected project
                    # Try both column 4 (index 4) and the last column
                    is_project_match = False

                    # Check column 4 (index 4)
                    if values and len(values) >= 5 and values[4] == project_name:
                        is_project_match = True

                    # Also check the last column
                    if values and len(values) >= 1 and values[-1] == project_name:
                        is_project_match = True

                    if is_project_match:
                        # Update checkbox display
                        current_values = list(values)
                        current_values[0] = "✓"  # Set checkbox to checked
                        self.file_list.item(item, values=current_values)

                        # Add to selected files set
                        self.selected_files.add(item)
                        files_added += 1

                logger.info(f"Selected {files_added} files from project {project_name}")

                if files_added > 0:
                    # Add selected files to download
                    self.add_to_downloads()
                    messagebox.showinfo(
                        "Files Added",
                        f"Added {files_added} files from project '{project_name}' to download queue.\nClick 'Start' in the downloader to begin downloading."
                    )
                else:
                    messagebox.showwarning(
                        "No Files",
                        f"No files found for project '{project_name}'. Try searching for LIDAR data first."
                    )

        except Exception as e:
            logger.error(f"Error in select_project_for_download: {e}", exc_info=True)
            messagebox.showerror(
                "Error",
                f"An error occurred while selecting project: {str(e)}"
            )

    def _center_on_project(self, project_id):
        """Center the map on a specific project's bounds."""
        try:
            logger.info(f"Centering map on project: {project_id}")

            # Check if we have this project
            if project_id not in self.projects:
                logger.warning(f"Project {project_id} not found in projects dictionary")
                return False

            project_data = self.projects[project_id]

            # Check if we have bounds information
            if 'bounds' not in project_data:
                logger.warning(f"No bounds information for project {project_id}")
                return False

            bounds = project_data['bounds']

            # Check if we have all the required bounds coordinates
            required_keys = ['west', 'east', 'north', 'south']
            if not all(key in bounds for key in required_keys):
                logger.warning(f"Incomplete bounds information for project {project_id}: {bounds}")
                return False

            # Log the original bounds from the project data
            logger.info(f"Project {project_id} bounds: west={bounds['west']}, east={bounds['east']}, north={bounds['north']}, south={bounds['south']}")

            # Calculate center point
            min_y = float(bounds['south'])
            max_y = float(bounds['north'])
            min_x = float(bounds['west'])
            max_x = float(bounds['east'])

            center_lat = (min_y + max_y) / 2
            center_lon = (min_x + max_x) / 2

            # Log the calculated center point
            logger.info(f"Calculated center point: lat={center_lat}, lon={center_lon}")

            # Calculate appropriate zoom level based on bounds size
            lat_span = max_y - min_y
            lon_span = max_x - min_x
            max_span = max(lat_span, lon_span)

            # Log the span calculations
            logger.info(f"Span calculations: lat_span={lat_span}, lon_span={lon_span}, max_span={max_span}")

            # Determine zoom level based on span
            # These thresholds are approximate and may need adjustment
            if max_span > 5.0:
                zoom = 5
            elif max_span > 2.0:
                zoom = 7
            elif max_span > 1.0:
                zoom = 9
            elif max_span > 0.5:
                zoom = 10
            elif max_span > 0.25:
                zoom = 11
            elif max_span > 0.1:
                zoom = 12
            elif max_span > 0.05:
                zoom = 13
            elif max_span > 0.01:
                zoom = 14
            else:
                zoom = 15

            # Set the map position
            logger.info(f"Setting map position to: lat={center_lat}, lon={center_lon}, zoom={zoom}")
            self.map_widget.set_position(center_lat, center_lon)
            self.map_widget.set_zoom(zoom)

            # Log the actual map position after setting
            current_position = self.map_widget.get_position()
            current_zoom = self.map_widget.zoom
            logger.info(f"Current map position after setting: lat={current_position[0]}, lon={current_position[1]}, zoom={current_zoom}")

            # Add a small delay to ensure the map updates
            self.root.update()
            time.sleep(0.5)

            # Log the map position again after the delay
            current_position = self.map_widget.get_position()
            current_zoom = self.map_widget.zoom
            logger.info(f"Map position after delay: lat={current_position[0]}, lon={current_position[1]}, zoom={current_zoom}")

            return True

        except Exception as e:
            logger.error(f"Error centering map on project {project_id}: {e}", exc_info=True)
            return False

    def check_projection_compatibility(self, lat, lon):
        """
        Check if coordinates are compatible with Web Mercator projection (EPSG:3857).
        Web Mercator has limitations at extreme latitudes.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            tuple: (is_compatible, message)
        """
        try:
            # Web Mercator is limited to approximately ±85.05 degrees latitude
            max_lat = 85.05

            if abs(lat) > max_lat:
                logger.warning(f"Latitude {lat} is outside Web Mercator projection limits (±{max_lat}°)")
                return False, f"Latitude {lat} is outside Web Mercator projection limits (±{max_lat}°)"

            # Check if longitude is within normal range (-180 to 180)
            if abs(lon) > 180:
                logger.warning(f"Longitude {lon} is outside normal range (-180° to 180°)")
                return False, f"Longitude {lon} is outside normal range (-180° to 180°)"

            # For debugging, calculate the tile coordinates at zoom level 0
            # At zoom level 0, the world is represented by a single tile
            n = 2.0 ** 0
            x_tile = n * ((lon + 180) / 360)
            y_tile = n * (1 - (math.log(math.tan(math.radians(lat)) + 1/math.cos(math.radians(lat))) / math.pi)) / 2

            logger.debug(f"Coordinates ({lat}, {lon}) map to tile coordinates at zoom 0: ({x_tile}, {y_tile})")

            return True, "Coordinates are compatible with Web Mercator projection"

        except Exception as e:
            logger.error(f"Error checking projection compatibility: {e}", exc_info=True)
            return False, f"Error checking projection: {str(e)}"

    def write_project_metadata(self):
        """Sample project metadata and write it to the tower_parameters.json file"""
        try:
            # Check if we have any LIDAR data
            if not self.urls:
                messagebox.showwarning("No LIDAR Data", "No LIDAR data available. Please search for LIDAR data first.")
                return

            # Create progress dialog
            progress_dialog = tk.Toplevel(self.root)
            progress_dialog.title("Writing Project Metadata")
            progress_dialog.geometry("400x150")
            progress_dialog.transient(self.root)
            progress_dialog.grab_set()

            # Add progress information
            ttk.Label(progress_dialog, text="Processing project metadata...").pack(pady=10)
            progress_var = tk.DoubleVar()
            progress_bar = ttk.Progressbar(progress_dialog, variable=progress_var, maximum=100)
            progress_bar.pack(fill="x", padx=20, pady=10)
            status_label = ttk.Label(progress_dialog, text="")
            status_label.pack(pady=5)

            # Create a progress update callback function
            def update_progress(current, total, project_name, status):
                progress_var.set((current / total) * 100 if total > 0 else 0)
                status_label.config(text=f"Processing {project_name}: {status}")
                progress_dialog.update()

            # Call the ProjectMetadata.write_project_metadata method
            processed_projects, failed_projects = self.project_metadata.write_project_metadata(
                urls=self.urls,
                root=self.root,
                update_progress_callback=update_progress
            )

            # Close progress dialog
            progress_dialog.destroy()

            # Show success message
            if processed_projects:
                success_message = f"Successfully wrote metadata for {len(processed_projects)} projects to tower_parameters.json"
                if failed_projects:
                    success_message += f"\n\nFailed to process {len(failed_projects)} projects:"
                    for project, error in failed_projects[:5]:  # Show first 5 failures
                        success_message += f"\n- {project}: {error}"
                    if len(failed_projects) > 5:
                        success_message += f"\n- ... and {len(failed_projects) - 5} more"

                messagebox.showinfo("Metadata Written", success_message)

                # Refresh project details window with updated metadata
                logger.info("Refreshing project details with updated metadata")
                project_items = {}
                for url, item in self.urls:
                    filename = url.split('/')[-1]
                    project_name = get_project_name(filename)
                    if project_name not in project_items:
                        project_items[project_name] = []
                    project_items[project_name].append(item)

                # Update project details pane with new metadata
                if hasattr(self, 'project_details') and self.project_details:
                    self.project_details.update_project_details(project_items)

                    # Update project combobox with available projects
                    self.project_details.project_combobox['values'] = sorted(self.project_metadata.projects.keys())
                    if self.project_details.project_combobox['values']:
                        self.project_details.project_combobox.current(0)
            else:
                error_message = "Failed to write metadata for any projects."
                if failed_projects:
                    error_message += "\n\nErrors:"
                    for project, error in failed_projects[:10]:  # Show first 10 failures
                        error_message += f"\n- {project}: {error}"
                    if len(failed_projects) > 10:
                        error_message += f"\n- ... and {len(failed_projects) - 10} more"

                messagebox.showwarning("No Metadata Written", error_message)

        except Exception as e:
            logger.error(f"Error writing project metadata: {e}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred writing project metadata: {str(e)}")

    def create_and_show_tile_labels(self):
        """Create and show numbered labels for each LIDAR tile on the map"""
        try:
            # Remove any existing tile labels first
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    try:
                        marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting marker: {e}")
                self.tile_markers = []
            else:
                self.tile_markers = []  # Initialize if it doesn't exist

            # Check if we have any polygons to label
            if not hasattr(self, 'lidar_polygons') or not self.lidar_polygons:
                logger.warning("No LIDAR polygons to label")
                return 0

            # Create a new marker for each tile
            logger.info(f"Creating tile labels for {len(self.lidar_polygons)} polygons")
            created_count = 0

            for i, polygon in enumerate(self.lidar_polygons):
                try:
                    # Skip if polygon is not visible (belongs to a hidden project)
                    if hasattr(polygon, 'project_name'):
                        project_name = polygon.project_name
                        if hasattr(self, 'project_visibility') and project_name in self.project_visibility:
                            if not self.project_visibility[project_name].get():
                                # Skip this polygon as its project is not visible
                                continue

                    # Get the position from the polygon
                    if hasattr(polygon, 'position_list') and polygon.position_list:
                        # Calculate center point of the polygon
                        lat_sum = 0
                        lon_sum = 0
                        count = 0

                        for lat, lon in polygon.position_list:
                            if lat and lon:  # Make sure coordinates are valid
                                lat_sum += lat
                                lon_sum += lon
                                count += 1

                        if count > 0:
                            # Average the coordinates to find center
                            center_lat = lat_sum / count
                            center_lon = lon_sum / count

                            # Get the tile number and polygon color
                            tile_number = getattr(polygon, 'tile_number', i + 1)
                            polygon_color = getattr(polygon, 'outline_color', "#FF0000")  # Default to red if no color

                            # Create a marker with just text, no pin
                            # Use the simplest approach with minimal parameters
                            marker = self.map_widget.set_marker(
                                center_lat, center_lon,
                                text=str(tile_number),
                                text_color=polygon_color,
                                font=("Arial", 8, "bold")
                            )

                            # Store the marker for later deletion
                            self.tile_markers.append(marker)
                            created_count += 1

                            if created_count % 5 == 0 or created_count <= 3:  # Log first few and then every 5th
                                logger.info(f"Created text-only marker {tile_number} at {center_lat:.6f}, {center_lon:.6f} with color {polygon_color}")
                except Exception as e:
                    logger.error(f"Error creating tile marker: {e}", exc_info=True)

            logger.info(f"Created a total of {created_count} tile markers")
            # Return the number of markers created
            return created_count

        except Exception as e:
            logger.error(f"Error creating tile labels: {e}", exc_info=True)
            return 0

    def hide_tile_labels(self):
        """Hide all tile labels"""
        try:
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    try:
                        marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting marker: {e}")
                self.tile_markers = []
                logger.info("Removed all tile markers")
                return True
            return False
        except Exception as e:
            logger.error(f"Error hiding tile labels: {e}", exc_info=True)
            return False

    def on_project_visibility_change(self, project_name):
        """Handle project visibility changes from the checkbutton"""
        try:
            # This function is likely unnecessary since we're now using direct command binding
            # But keep it for backward compatibility with any existing calls

            # Perform the toggle directly
            self.toggle_project_visibility(project_name)

        except Exception as e:
            logger.error(f"Error in visibility change handler: {e}", exc_info=True)

    def clear_all_data(self):
        """Clear all data in the application, including LIDAR display, downloads, and project data"""
        try:
            logger.info("Clearing all application data")

            # Clear LIDAR display first
            self.clear_lidar_display()

            # Clear legend items frame if it exists
            if hasattr(self, 'legend_items_frame') and self.legend_items_frame:
                try:
                    # Clear all widgets in the legend frame
                    for widget in self.legend_items_frame.winfo_children():
                        widget.destroy()

                    # Add "No LIDAR data loaded" label
                    ttk.Label(
                        self.legend_items_frame,
                        text="No LIDAR data loaded",
                        foreground="gray"
                    ).pack(anchor="w", padx=5, pady=2)

                    logger.info("Cleared legend items frame")
                except Exception as legend_error:
                    logger.error(f"Error clearing legend items frame: {legend_error}", exc_info=True)

            # Clear downloader data
            if hasattr(self, 'downloader') and self.downloader:
                try:
                    logger.info("Clearing downloader data")
                    # Reset the download queue
                    if hasattr(self.downloader, 'queue'):
                        self.downloader.queue = []
                    # Reset the download list
                    if hasattr(self.downloader, 'download_list'):
                        self.downloader.download_list = []
                    # Reset the download status
                    if hasattr(self.downloader, 'download_status'):
                        self.downloader.download_status = {}
                    # Clear the download list display if it exists
                    if hasattr(self.downloader, 'download_list_display'):
                        try:
                            for item in self.downloader.download_list_display.get_children():
                                self.downloader.download_list_display.delete(item)
                        except Exception as e:
                            logger.debug(f"Error clearing download list display: {e}")
                except Exception as downloader_error:
                    logger.error(f"Error clearing downloader data: {downloader_error}", exc_info=True)

            # Clear project metadata
            if hasattr(self, 'project_metadata'):
                try:
                    logger.info("Clearing project metadata")
                    self.project_metadata.projects = {}
                except Exception as metadata_error:
                    logger.error(f"Error clearing project metadata: {metadata_error}", exc_info=True)

            # Clear search polygon
            if hasattr(self, 'polygon_points'):
                self.polygon_points = []

            # Clear any search polygon on the map
            if hasattr(self, 'search_polygon') and self.search_polygon:
                try:
                    self.search_polygon.delete()
                    self.search_polygon = None
                except Exception as e:
                    logger.debug(f"Error deleting search polygon: {e}")

            # Clear any path between sites
            if hasattr(self, 'path_between_sites') and self.path_between_sites:
                try:
                    self.path_between_sites.delete()
                    self.path_between_sites = None
                except Exception as e:
                    logger.debug(f"Error deleting path between sites: {e}")

            # Reset site data
            self.donor_site = None
            self.recipient_site = None

            # Clear any site markers
            if hasattr(self, 'donor_marker') and self.donor_marker:
                try:
                    self.donor_marker.delete()
                    self.donor_marker = None
                except Exception as e:
                    logger.debug(f"Error deleting donor marker: {e}")

            if hasattr(self, 'recipient_marker') and self.recipient_marker:
                try:
                    self.recipient_marker.delete()
                    self.recipient_marker = None
                except Exception as e:
                    logger.debug(f"Error deleting recipient marker: {e}")

            # Reset any other data structures
            self.projects = {}
            self.selected_files = set()
            self.item_url_map = {}

            # Clear any windows or dialogs
            if hasattr(self, 'progress_window') and self.progress_window:
                try:
                    self.progress_window.destroy()
                    self.progress_window = None
                except Exception as e:
                    logger.debug(f"Error destroying progress window: {e}")

            logger.info("All application data cleared successfully")
            # No popup message - just continue silently
            return True
        except Exception as e:
            logger.error(f"Error clearing all data: {e}", exc_info=True)
            # No error popup - just log the error and continue
            return False

    def clear_lidar_display(self):
        """Clear the LIDAR display completely"""
        try:
            logger.info("Clearing LIDAR display")

            # Clear file list
            if hasattr(self, 'file_list'):
                try:
                    for item in self.file_list.get_children():
                        try:
                            self.file_list.delete(item)
                        except Exception as e:
                            logger.debug(f"Error deleting file list item: {e}")
                except Exception as file_list_error:
                    logger.error(f"Error clearing file list: {file_list_error}", exc_info=True)

            # Clear existing LIDAR polygons
            if hasattr(self, 'lidar_polygons'):
                for polygon in self.lidar_polygons:
                    try:
                        polygon.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting polygon: {e}")
                self.lidar_polygons = []
            else:
                self.lidar_polygons = []

            # Clear project polygons tracking
            if hasattr(self, 'project_polygons'):
                for project_name, polygons in self.project_polygons.items():
                    for polygon in polygons:
                        try:
                            polygon.delete()
                        except Exception as e:
                            logger.debug(f"Error deleting project polygon: {e}")
                self.project_polygons = {}
            else:
                self.project_polygons = {}

            # Clear any tile markers
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    try:
                        marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting tile marker: {e}")
                self.tile_markers = []

            # Reset tracking data structures
            self._all_project_polygons = {}
            self.project_visibility = {}
            self.project_colors = {}
            self.selected_files = set()

            logger.info("LIDAR display cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing LIDAR display: {e}", exc_info=True)

    def clear_lidar_polygons(self):
        """Clear all LIDAR polygons from the map"""
        try:
            logger.info("Clearing LIDAR polygons")

            # Clear existing LIDAR polygons
            if hasattr(self, 'lidar_polygons'):
                for polygon in self.lidar_polygons:
                    try:
                        polygon.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting polygon: {e}")
                self.lidar_polygons = []
            else:
                self.lidar_polygons = []

            # Clear project polygons tracking
            if hasattr(self, 'project_polygons'):
                for project_name, polygons in self.project_polygons.items():
                    for polygon in polygons:
                        try:
                            polygon.delete()
                        except Exception as e:
                            logger.debug(f"Error deleting project polygon: {e}")
                self.project_polygons = {}
            else:
                self.project_polygons = {}

            logger.info("LIDAR polygons cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing LIDAR polygons: {e}", exc_info=True)

    def create_original_polygon_data(self, project_name, polygon_points, color):
        """Store original polygon data for later recreation when toggling visibility"""
        try:
            # Initialize _original_polygon_data if it doesn't exist
            if not hasattr(self, '_original_polygon_data'):
                self._original_polygon_data = {}

            # Initialize project entry if it doesn't exist
            if project_name not in self._original_polygon_data:
                self._original_polygon_data[project_name] = []

            # Create simple data structure with just the essential polygon info
            polygon_data = {
                'position_list': polygon_points,
                'outline_color': color
            }

            # Add to the project's data list
            self._original_polygon_data[project_name].append(polygon_data)

            # Log the addition
            count = len(self._original_polygon_data[project_name])
            if count % 10 == 0 or count <= 5:  # Log first few and then every 10th polygon
                logger.debug(f"Stored original polygon data for project {project_name}, total: {count}")

            return True
        except Exception as e:
            logger.error(f"Error storing original polygon data: {e}", exc_info=True)
            return False

    def debug_polygon_data(self):
        """Debug the polygon data structures"""
        try:
            logger.info("=== DEBUGGING POLYGON DATA STRUCTURES ===")

            # Check lidar_polygons
            if not hasattr(self, 'lidar_polygons'):
                logger.info("lidar_polygons structure does not exist")
            else:
                logger.info(f"lidar_polygons has {len(self.lidar_polygons)} polygons")
                # Check for common attributes on a few sample polygons
                if self.lidar_polygons:
                    sample = min(3, len(self.lidar_polygons))
                    logger.info(f"Examining {sample} sample polygons from lidar_polygons:")
                    for i in range(sample):
                        polygon = self.lidar_polygons[i]
                        has_position = hasattr(polygon, 'position_list')
                        has_color = hasattr(polygon, 'outline_color')
                        has_name = hasattr(polygon, 'name')
                        logger.info(f"  Polygon {i}: has position_list={has_position}, has outline_color={has_color}, has name={has_name}")

            # Check _original_polygon_data
            if not hasattr(self, '_original_polygon_data'):
                logger.info("_original_polygon_data structure does not exist")
            else:
                logger.info(f"_original_polygon_data has {len(self._original_polygon_data)} projects")
                for project_name, data_list in self._original_polygon_data.items():
                    logger.info(f"  Project {project_name}: {len(data_list)} polygons")
                    # Debug sample data
                    if data_list:
                        sample_data = data_list[0]
                        attributes = ', '.join(sample_data.keys())
                        logger.info(f"  Sample data attributes: {attributes}")

            # Check if _all_project_polygons exists
            if not hasattr(self, '_all_project_polygons'):
                logger.info("_all_project_polygons structure does not exist")
            else:
                logger.info(f"_all_project_polygons has {len(self._all_project_polygons)} projects")
                for project_name, polygons in self._all_project_polygons.items():
                    logger.info(f"  Project {project_name}: {len(polygons)} polygons")

            # Check current project polygons
            if not hasattr(self, 'project_polygons'):
                logger.info("project_polygons structure does not exist")
            else:
                logger.info(f"project_polygons has {len(self.project_polygons)} projects")
                for project_name, polygons in self.project_polygons.items():
                    logger.info(f"  Project {project_name}: {len(polygons)} polygons")

            # Check visibility state
            if not hasattr(self, 'project_visibility'):
                logger.info("project_visibility structure does not exist")
            else:
                logger.info(f"project_visibility has {len(self.project_visibility)} projects")
                for project_name, var in self.project_visibility.items():
                    if hasattr(var, 'get'):
                        logger.info(f"  Project {project_name}: visibility = {var.get()}")
                    else:
                        logger.warning(f"  Project {project_name}: visibility variable is not a BooleanVar!")

            logger.info("=== END DEBUGGING POLYGON DATA ===")

        except Exception as e:
            logger.error(f"Error during debug_polygon_data: {e}", exc_info=True)

    def debug_canvas_items(self):
        """Debug function to examine canvas items and their tags"""
        try:
            logger.info("=== CANVAS DEBUGGING ===")

            # Check if we have access to the canvas
            if not hasattr(self, 'map_widget') or not hasattr(self.map_widget, 'canvas'):
                logger.warning("No canvas available for debugging")
                return

            canvas = self.map_widget.canvas
            all_items = canvas.find_all()
            logger.info(f"Canvas contains {len(all_items)} items")

            # Initialize counters
            polygons = 0
            lidar_polygons = 0
            project_polygons = {}

            # Sample a few items to see what they look like
            sample_size = min(5, len(all_items))
            logger.info(f"Examining first {sample_size} items:")

            # First pass - examine a sample of items
            for i, item_id in enumerate(all_items):
                if i < sample_size:
                    try:
                        item_type = canvas.type(item_id)
                        tags = canvas.gettags(item_id)
                        coords = canvas.coords(item_id)
                        logger.info(f"  Item {item_id}: type={item_type}, tags={tags}, coords_length={len(coords) if coords else 0}")
                    except Exception as e:
                        logger.error(f"  Error examining item {item_id}: {e}")

            # Second pass - count polygons and check for LIDAR tags
            for item_id in all_items:
                try:
                    if canvas.type(item_id) == "polygon":
                        polygons += 1
                        tags = canvas.gettags(item_id)

                        # Check for LIDAR tags
                        if tags:
                            for tag in tags:
                                if 'LIDAR_' in tag:
                                    lidar_polygons += 1
                                    # Extract project name from tag
                                    parts = tag.split('_')
                                    if len(parts) > 1:
                                        # For tags like 'LIDAR_USGS_LPC_NH_Connecticut_River_2015'
                                        # We need to reconstruct the project name from parts 1 onwards
                                        project_name = '_'.join(parts[1:]) if len(parts) > 2 else parts[1]
                                        project_polygons[project_name] = project_polygons.get(project_name, 0) + 1
                                    break
                except Exception as e:
                    logger.debug(f"Error examining polygon {item_id}: {e}")

            # Log summary information
            logger.info(f"Canvas contains {polygons} polygons, {lidar_polygons} LIDAR polygons")
            logger.info("LIDAR polygons by project:")
            for project, count in project_polygons.items():
                logger.info(f"  Project {project}: {count} polygons")

            # Compare with our tracking
            if hasattr(self, 'project_polygons'):
                logger.info("Comparing with project_polygons tracking:")
                for project, polygons in self.project_polygons.items():
                    tracked = len(polygons)
                    on_canvas = project_polygons.get(project, 0)
                    logger.info(f"  Project {project}: tracked={tracked}, on_canvas={on_canvas}")

            logger.info("=== END CANVAS DEBUGGING ===")
        except Exception as e:
            logger.error(f"Error in debug_canvas_items: {e}", exc_info=True)

    def export_map_view(self):
        """Export a map screenshot with sites, path, and turbines"""
        try:
            if not hasattr(self, 'polygon_points'):
                messagebox.showwarning("No Data",
                                     "Please load a project with sites first.")
                return

            # Ask for save location
            output_file = filedialog.asksaveasfilename(
                title="Save Map Image",
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg"), ("All Files", "*.*")]
            )
            if not output_file:
                return

            # Center the map on the path
            self.center_map_on_path()

            # Create a custom dialog that stays open until user explicitly clicks a button
            # but allows interaction with the main window
            adjust_dialog = tk.Toplevel(self.root)
            adjust_dialog.title("Adjust Map View")
            adjust_dialog.geometry("400x150")
            adjust_dialog.transient(self.root)
            # Don't use grab_set() as it prevents interaction with the main window
            # adjust_dialog.grab_set()  # Make dialog modal

            # Keep dialog on top but allow map interaction
            adjust_dialog.attributes('-topmost', True)

            # Set focus to dialog but allow switching back to main window
            adjust_dialog.focus_set()

            # Add instructions label
            ttk.Label(
                adjust_dialog,
                text="The map has been centered.\n\nYou can now adjust the map zoom and position.\nClick 'Capture' when ready.",
                justify=tk.CENTER
            ).pack(pady=20)

            # Create capture flag
            capture_flag = {'proceed': False}

            # Create button frame
            button_frame = ttk.Frame(adjust_dialog)
            button_frame.pack(side=tk.BOTTOM, pady=15)

            # Add buttons
            def on_capture():
                capture_flag['proceed'] = True
                adjust_dialog.destroy()

            def on_cancel():
                adjust_dialog.destroy()

            ttk.Button(
                button_frame,
                text="Capture",
                command=on_capture
            ).pack(side=tk.LEFT, padx=20)

            ttk.Button(
                button_frame,
                text="Cancel",
                command=on_cancel
            ).pack(side=tk.LEFT, padx=20)

            # Position the dialog in a corner that doesn't cover the center of the map
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            dialog_width = 400
            dialog_height = 150

            # Position in the top-right corner of the screen
            dialog_x = screen_width - dialog_width - 20
            dialog_y = 100

            adjust_dialog.geometry(f"{dialog_width}x{dialog_height}+{dialog_x}+{dialog_y}")

            # Wait for dialog to be closed
            logger.info("Waiting for user to adjust map view")
            self.root.wait_window(adjust_dialog)
            logger.info(f"Dialog closed, proceed flag: {capture_flag['proceed']}")

            # Proceed with capture only if the capture button was clicked
            if capture_flag['proceed']:
                # Capture the map view
                try:
                    # Get map widget coordinates
                    x = self.map_widget.winfo_rootx()
                    y = self.map_widget.winfo_rooty()
                    width = self.map_widget.winfo_width()
                    height = self.map_widget.winfo_height()

                    # Force update and wait for rendering
                    self.map_widget.update()
                    self.root.update()
                    time.sleep(0.5)  # Wait for rendering

                    # Capture screenshot
                    try:
                        from PIL import ImageGrab
                        logger.info(f"Capturing map widget at coords: ({x}, {y}, {width}, {height})")
                        image = ImageGrab.grab(bbox=(x, y, x+width, y+height))
                        image.save(output_file, quality=95)

                        # Verify the image was saved
                        if os.path.exists(output_file):
                            # Open the directory containing the image using our safe utility
                            output_dir = os.path.dirname(output_file)
                            safe_open_directory(output_dir)

                            messagebox.showinfo("Export Successful",
                                             f"Map view has been exported to:\n{output_file}")
                        else:
                            raise Exception("Failed to save image file")
                    except Exception as e:
                        logger.error(f"Error capturing screenshot: {e}", exc_info=True)
                        messagebox.showerror("Error", f"Failed to capture screenshot: {str(e)}")
                except Exception as e:
                    logger.error(f"Error exporting map view: {e}", exc_info=True)
                    messagebox.showerror("Error", f"Failed to export map view: {str(e)}")
            else:
                logger.info("Map export cancelled by user")

        except Exception as e:
            logger.error(f"Error in export_map_view: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export map view: {str(e)}")

    def _view_on_map(self):
        """Open a custom Google Maps view with both sites marked and a line between them"""
        try:
            if not hasattr(self, 'donor_site') or not hasattr(self, 'recipient_site'):
                messagebox.showwarning("No Sites", "Please load site coordinates first.")
                return

            # Import and use the LOS_map_view module to display the map
            import LOS_map_view
            import map_server

            # First ensure any existing server is stopped and cleaned up
            map_server.stop_server()
            map_server.cleanup_zombie_processes()

            # Then open the map with fresh server
            LOS_map_view.view_on_map(self.donor_site, self.recipient_site)

        except Exception as e:
            logger.error(f"Error in _view_on_map: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to open map: {str(e)}")

    def clear_all_data(self):
        """Clear all lidar data and update the tower_parameters.json file"""
        try:
            # Clear internal data
            logger.info("Clearing all lidar data")

            # Clear UI elements
            self.clear_lidar_display()

            # Clear project metadata
            if hasattr(self, 'project_metadata'):
                self.project_metadata.projects = {}
                logger.info("Cleared project metadata")

                # Update project details pane if it exists
                if hasattr(self, 'project_details') and self.project_details:
                    try:
                        # Schedule update on main thread to avoid threading issues
                        if hasattr(self.root, 'after'):
                            self.root.after(10, self.project_details._update_project_list)
                            logger.info("Scheduled project pane update after clearing metadata")
                        else:
                            # Direct update if after method not available
                            self.project_details._update_project_list()
                            logger.info("Updated project pane directly after clearing metadata")
                    except Exception as update_error:
                        logger.error(f"Error updating project pane after clearing metadata: {update_error}", exc_info=True)

            # Clear data in tower_parameters.json
            try:
                with open('tower_parameters.json', 'r') as f:
                    data = json.load(f)

                # Keep only site and general parameters, clear lidar and turbines
                if 'site_A' in data and 'site_B' in data and 'general_parameters' in data:
                    new_data = {
                        'site_A': data['site_A'],
                        'site_B': data['site_B'],
                        'general_parameters': data['general_parameters'],
                        'turbines': [],
                        'lidar_data': {}
                    }

                    with open('tower_parameters.json', 'w') as f:
                        json.dump(new_data, f, indent=2)

                    logger.info("Cleared lidar data and turbines from tower_parameters.json")
                    # No popup message - just continue silently
                else:
                    logger.warning("tower_parameters.json does not have required fields")
                    messagebox.showwarning("Warning", "Could not clear data: tower_parameters.json is missing required fields")
            except Exception as e:
                logger.error(f"Error clearing tower_parameters.json: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to clear data: {str(e)}")

        except Exception as e:
            logger.error(f"Error in clear_all_data: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to clear data: {str(e)}")

    def refresh_metadata(self):
        """Refresh metadata for all projects"""
        try:
            logger.info("Refreshing metadata for all projects")
            self.project_metadata.refresh_all_metadata()
            logger.info("Metadata refresh completed")
            messagebox.showinfo("Metadata Refresh", "Metadata for all projects has been refreshed successfully.")
        except Exception as e:
            logger.error(f"Error refreshing metadata: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to refresh metadata: {str(e)}")

    def load_json_results(self):
        """Load LIDAR results from tower_parameters.json"""
        try:
            logger.info("Loading LIDAR results from tower_parameters.json")

            # Use the imported function to load and display results
            success = load_json_data(self)

            if success:
                logger.info("Successfully loaded LIDAR results from JSON")
            else:
                logger.warning("Failed to load LIDAR results from JSON")

        except Exception as e:
            logger.error(f"Error loading JSON results: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load LIDAR results from JSON: {str(e)}")

    def set_elevation_profile(self, elevation_profile):
        """Set the elevation profile for visualization"""
        self.elevation_profile = elevation_profile

        # Also set in turbine processor
        self.turbine_processor.set_elevation_profile(elevation_profile)

    def export_search_polygon(self):
        """Export the search polygon in multiple formats"""
        logger.info("Exporting search polygon in multiple formats")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Get site IDs if available
            site_a_id = self.donor_site.get('site_id') if hasattr(self, 'donor_site') and self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if hasattr(self, 'recipient_site') and self.recipient_site else None

            # Import export_polygon function from geometry module
            from utilities.geometry import export_search_polygon

            # Call export function with site data
            export_search_polygon(self.polygon_points, self.donor_site, self.recipient_site)

            logger.info(f"Search polygon exported in multiple formats for sites {site_a_id} and {site_b_id}")

        except Exception as e:
            logger.error(f"Error exporting search polygon: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search polygon: {str(e)}")

    def export_search_polygon_as_kml(self):
        """Export the search polygon as a KML file"""
        logger.info("Exporting search polygon as KML")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Import export function from geometry module
            from utilities.geometry import export_search_polygon_as_kml

            # Call export function with site data
            export_search_polygon_as_kml(self.polygon_points, self.donor_site, self.recipient_site)

            logger.info("Search polygon exported as KML")

        except Exception as e:
            logger.error(f"Error exporting search polygon as KML: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export KML: {str(e)}")

    def export_search_polygon_as_shapefile(self):
        """Export the search polygon as a shapefile"""
        logger.info("Exporting search polygon as shapefile")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Import export function from geometry module
            from utilities.geometry import export_search_polygon_as_shapefile

            # Call export function with site data
            export_search_polygon_as_shapefile(self.polygon_points, self.donor_site, self.recipient_site)

            logger.info("Search polygon exported as shapefile")

        except Exception as e:
            logger.error(f"Error exporting search polygon as shapefile: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export shapefile: {str(e)}")

    def analyze_path_with_ai(self):
        """Initiates the AI visual analysis of the path."""
        logger.info("AI Path Analysis button clicked.")

        # 1. Check if site data is available
        if not self.donor_site or not self.recipient_site:
            messagebox.showwarning("Missing Data", "Please load donor and recipient site data first.")
            logger.warning("AI analysis aborted: Missing site data.")
            return

        # 2. Get coordinates and convert if necessary
        try:
            lat_a, lon_a = coords_convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
            lat_b, lon_b = coords_convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])
            start_coords = (lat_a, lon_a)
            end_coords = (lat_b, lon_b)
            logger.info(f"Coordinates for AI analysis: Start={start_coords}, End={end_coords}")
        except Exception as e:
            logger.error(f"Error converting coordinates for AI analysis: {e}", exc_info=True)
            messagebox.showerror("Coordinate Error", f"Failed to process site coordinates: {e}")
            return

        # 3. Get map widget and root window references
        # Use self.root and self.map_widget_ref stored during initialization
        if not self.root or not self.map_widget_ref:
            logger.error("Root window or map widget reference not found in ApplicationController.")
            messagebox.showerror("Internal Error", "UI components not found for analysis.")
            return

        # 4. Run analysis in a separate thread
        logger.info("Starting AI analysis in a background thread.")
        analysis_thread = threading.Thread(
            target=run_multi_source_analysis,
            args=(self.root, start_coords, end_coords), # Pass root, start, end only
            daemon=True
        )
        analysis_thread.start()

        messagebox.showinfo("Analysis Started", "AI path analysis started in the background. A progress dialog will appear, and a report will be shown upon completion.")





# Setup the main application window
logger.info("Setting up main application window")
root = TkinterDnD.Tk()
root.title("Microwave Line of Sight Project Viewer")
root.geometry("1800x1000")

# Create a PanedWindow for three equal columns
paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL, sashwidth=4, sashrelief="raised")
paned_window.pack(fill=tk.BOTH, expand=True)

# Create main frames for three columns with minimum widths
left_frame = ttk.Frame(paned_window, width=600, relief="flat")
center_frame = ttk.Frame(paned_window, width=600, relief="flat")
right_frame = ttk.Frame(paned_window, width=600, relief="flat")

# Add frames to paned window with minimum sizes
paned_window.add(left_frame, minsize=500)
paned_window.add(center_frame, minsize=500)
paned_window.add(right_frame, minsize=500)

# Ensure the frames maintain their size
left_frame.pack_propagate(False)
center_frame.pack_propagate(False)
right_frame.pack_propagate(False)

# Left column (Path data and Map)
# Project Details
project_link_id = tk.StringVar()
project_link_name = tk.StringVar()
project_path_length = tk.StringVar()

# Donor Site Details
donor_site_name = tk.StringVar()
donor_latitude = tk.StringVar()
donor_longitude = tk.StringVar()
donor_azimuth = tk.StringVar()
donor_elevation = tk.StringVar()
donor_antenna_cl = tk.StringVar()
donor_address = tk.StringVar()

# Recipient Site Details
recipient_site_name = tk.StringVar()
recipient_latitude = tk.StringVar()
recipient_longitude = tk.StringVar()
recipient_azimuth = tk.StringVar()
recipient_elevation = tk.StringVar()
recipient_antenna_cl = tk.StringVar()
recipient_address = tk.StringVar()

# Create a frame to hold all site details in a more compact format
site_details_frame = ttk.Frame(left_frame)
site_details_frame.pack(fill="x", padx=5, pady=5)

# Project Details - More compact layout
project_frame = ttk.LabelFrame(site_details_frame, text="Project Details")
project_frame.pack(fill="x", padx=5, pady=2)

# Use grid layout for more compact display
ttk.Label(project_frame, textvariable=project_link_id).grid(row=0, column=0, sticky="w", padx=5)
ttk.Label(project_frame, textvariable=project_link_name).grid(row=0, column=1, sticky="w", padx=5)
ttk.Label(project_frame, textvariable=project_path_length).grid(row=0, column=2, sticky="w", padx=5)

# Sites Frame - Contains both donor and recipient details
sites_frame = ttk.Frame(site_details_frame)
sites_frame.pack(fill="x", padx=5, pady=2)

# Donor Site Details - More compact layout using grid
donor_frame = ttk.LabelFrame(sites_frame, text="Donor Site")
donor_frame.pack(side="left", fill="x", expand=True, padx=2)

ttk.Label(donor_frame, text="Donor", font=("Arial", 10, "bold"), foreground="blue").grid(row=0, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_site_name).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_latitude).grid(row=2, column=0, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_longitude).grid(row=2, column=1, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_azimuth).grid(row=3, column=0, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_elevation).grid(row=3, column=1, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_antenna_cl).grid(row=4, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(donor_frame, textvariable=donor_address).grid(row=5, column=0, columnspan=2, sticky="w", padx=5)

# Recipient Site Details - More compact layout using grid
recipient_frame = ttk.LabelFrame(sites_frame, text="Recipient Site")
recipient_frame.pack(side="left", fill="x", expand=True, padx=2)

ttk.Label(recipient_frame, text="Recipient", font=("Arial", 10, "bold"), foreground="red").grid(row=0, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_site_name).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_latitude).grid(row=2, column=0, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_longitude).grid(row=2, column=1, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_azimuth).grid(row=3, column=0, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_elevation).grid(row=3, column=1, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_antenna_cl).grid(row=4, column=0, columnspan=2, sticky="w", padx=5)
ttk.Label(recipient_frame, textvariable=recipient_address).grid(row=5, column=0, columnspan=2, sticky="w", padx=5)

# Create a frame to hold both map and elevation profile
map_and_profile_frame = ttk.Frame(left_frame)
map_and_profile_frame.pack(fill="both", expand=True, padx=5, pady=5)

# Map frame in a LabelFrame
map_frame = ttk.LabelFrame(map_and_profile_frame, text="Map View")
map_frame.pack(fill="both", expand=True, padx=10, pady=5)

# Create a frame for the map header
map_header_frame = ttk.Frame(map_frame)
map_header_frame.pack(fill="x", padx=5, pady=2)

# Add "Import JSON" button in the header
ttk.Button(
    map_header_frame,
    text="Import JSON",
    command=import_tower_parameters_json
).pack(side="right", padx=5)

# Add "Edit Sites" button in the header (renamed from "Manual Sites")
ttk.Button(
    map_header_frame,
    text="Edit Sites",
    command=lambda: lidar_downloader.edit_sites()
).pack(side="right", padx=5)

# Add View on Map button in the header
ttk.Button(
    map_header_frame,
    text="View on Map",
    command=lambda: lidar_downloader._view_on_map()
).pack(side="right", padx=5)

# Add AI Path Analyze button
ttk.Button(
    map_header_frame,
    text="AI path analyze",
    command=lambda: lidar_downloader.analyze_path_with_ai()  # Add command later
).pack(side="right", padx=5)

# Add Export Polygon button in the header
ttk.Button(
    map_header_frame,
    text="Export Polygon",
    command=lambda: lidar_downloader.export_search_polygon()
).pack(side="right", padx=5)

# Add Export KML button
ttk.Button(
    map_header_frame,
    text="Export KML",
    command=lambda: lidar_downloader.export_search_polygon_as_kml()
).pack(side="right", padx=5)

# Add Export Shapefile button
ttk.Button(
    map_header_frame,
    text="Export Shapefile",
    command=lambda: lidar_downloader.export_search_polygon_as_shapefile()
).pack(side="right", padx=5)

def toggle_tile_ids(var):
    """Toggle visibility of tile ID labels"""
    try:
        show_tile_ids = var.get()
        logger.info(f"Tile ID labels {'shown' if show_tile_ids else 'hidden'}")

        # Global reference to the lidar_downloader instance
        global lidar_downloader

        # First check if there are any polygons to work with
        if not hasattr(lidar_downloader, 'lidar_polygons'):
            logger.warning("No lidar_polygons attribute found")
            messagebox.showinfo("No Tiles", "No LIDAR tiles have been loaded yet. Please run a LIDAR search first.")
            return

        visible_polygons = len(lidar_downloader.lidar_polygons)
        logger.info(f"Found {visible_polygons} visible polygons for tile labeling")

        if visible_polygons == 0:
            # Check if we have any polygons at all in the backup
            all_polygons = 0
            if hasattr(lidar_downloader, '_all_project_polygons'):
                for project, polygons in lidar_downloader._all_project_polygons.items():
                    all_polygons += len(polygons)

            logger.info(f"Found {all_polygons} total polygons in all projects (including hidden)")

            # If all projects are hidden, inform the user
            if all_polygons > 0 and visible_polygons == 0:
                logger.warning("No visible tiles to label - please check if Show Tiles is enabled in Project Legend")
                messagebox.showinfo("No Visible Tiles", "There are no visible tiles to label. Please make sure 'Show Tiles' is checked for at least one project in the Project Legend.")
                # Set toggle back to off since we can't show labels
                var.set(False)
                return

        # Use the direct methods to show/hide tile labels
        if show_tile_ids:
            # Create and show tile labels
            count = lidar_downloader.create_and_show_tile_labels()
            logger.info(f"Created {count} tile number markers")
            if count == 0:
                logger.warning("No tile markers were created - please check if any tiles are visible")
                messagebox.showinfo("No Markers Created", "No tile markers could be created. Make sure at least one project has 'Show Tiles' checked.")
                # Set toggle back to off
                var.set(False)
        else:
            # Hide all tile labels
            lidar_downloader.hide_tile_labels()
            logger.info("Removed all tile markers")

    except Exception as e:
        logger.error(f"Error toggling tile IDs: {e}", exc_info=True)
        # Print more details for debugging
        import traceback
        traceback.print_exc()

def toggle_labels(var):
    """Toggle visibility of turbine labels"""
    try:
        show_labels = var.get()
        logger.info(f"Toggle Labels button clicked, setting to {show_labels}")

        # Check if lidar_downloader exists and has the necessary attributes
        if not 'lidar_downloader' in globals() or not hasattr(lidar_downloader, 'show_turbine_labels'):
            logger.error("LidarDownloader not initialized or missing show_turbine_labels attribute")
            messagebox.showinfo("No Turbines", "No turbines have been loaded yet. Please search for turbines first.")
            var.set(not show_labels)  # Revert the toggle
            return

        # Check if there are any turbines to label
        if not hasattr(lidar_downloader, 'last_turbines') or not lidar_downloader.last_turbines:
            logger.warning("No turbines available to label")
            messagebox.showinfo("No Turbines", "No turbines have been found. Please search for turbines first.")
            var.set(not show_labels)  # Revert the toggle
            return

        # Set the show_turbine_labels variable in the LidarDownloader instance
        lidar_downloader.show_turbine_labels.set(show_labels)

        # Call the toggle_turbine_labels method to handle the visibility change
        lidar_downloader.toggle_turbine_labels()

        # Provide feedback to the user
        turbine_count = len(lidar_downloader.last_turbines)
        if show_labels:
            logger.info(f"Showing labels for {turbine_count} turbines")
        else:
            logger.info(f"Hiding labels for {turbine_count} turbines")

        logger.info(f"Turbine labels toggled successfully to {'visible' if show_labels else 'hidden'}")

    except Exception as e:
        logger.error(f"Error toggling labels: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to toggle turbine labels: {str(e)}")
        var.set(not show_labels)  # Revert the toggle

# Initialize map widget using the utility function
map_widget = initialize_map_widget(map_frame, width=600, height=400, initial_zoom=7)

# Create map control panel
map_control_panel = MapControlPanel(map_frame, map_widget)

# Set up toggle commands
map_control_panel.set_labels_command(toggle_labels)
map_control_panel.set_tile_ids_command(toggle_tile_ids)

# Store the reference to tile_ids_var in the root object for accessibility
root.tile_ids_var = map_control_panel.tile_ids_var

# This function is now handled by the MapStyleManager class

# Use the style dropdown from the map control panel
map_control_panel.style_dropdown.bind('<<ComboboxSelected>>', map_control_panel.style_manager.on_style_change)

# Elevation frame
elevation_frame = ttk.Frame(map_and_profile_frame)
elevation_frame.pack(fill="both", expand=True, padx=5, pady=5)

# Elevation Profile
elevation_profile = ElevationProfile(elevation_frame)
elevation_profile.frame.pack(fill="both", expand=True)

# Add button frame under elevation profile (empty now but kept for potential future use)
elevation_button_frame = ttk.Frame(elevation_frame)
elevation_button_frame.pack(fill="x", padx=5, pady=5)

# Project Legend with proper sizing and placement
legend_frame = ttk.LabelFrame(center_frame, text="Project Legend")
legend_frame.pack(fill="x", padx=5, pady=5)  # Pack at top of center frame

# Create scrollable frame for legend with increased height
legend_canvas = tk.Canvas(legend_frame, height=150)  # Increased from 60 to 150
legend_scrollbar = ttk.Scrollbar(legend_frame, orient="vertical", command=legend_canvas.yview)

# Pack scrollbar and canvas
legend_scrollbar.pack(side="right", fill="y")
legend_canvas.pack(side="left", fill="both", expand=True)
legend_canvas.configure(yscrollcommand=legend_scrollbar.set)

# Create frame for legend items
legend_items_frame = ttk.Frame(legend_canvas)
legend_canvas_window = legend_canvas.create_window(
    (0, 0),
    window=legend_items_frame,
    anchor="nw",
    width=legend_canvas.winfo_width()
)

# Configure scrolling and resizing
def configure_legend_scroll(event=None):
    """Update the scroll region when the legend content changes"""
    legend_canvas.configure(scrollregion=legend_canvas.bbox("all"))

def on_canvas_configure(event):
    """Update the legend frame width when canvas resizes"""
    legend_canvas.itemconfig(legend_canvas_window, width=event.width)

# Bind events for proper scrolling
legend_items_frame.bind("<Configure>", configure_legend_scroll)
legend_canvas.bind("<Configure>", on_canvas_configure)

# Bind mousewheel for scrolling
def _on_mousewheel(event):
    legend_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

legend_canvas.bind_all("<MouseWheel>", _on_mousewheel)

# Add initial "No LIDAR data" label
ttk.Label(
    legend_items_frame,
    text="No LIDAR data loaded",
    foreground="gray"
).pack(anchor="w", padx=5, pady=2)

# Right column (UltraVerboseDownloaderer)
downloader = UltraVerboseDownloaderer(right_frame)
logger.info("Downloader initialized")

# Initialize ApplicationController with the downloader instance
lidar_downloader = ApplicationController(center_frame, map_widget, root, downloader)
lidar_downloader.legend_items_frame = legend_items_frame
lidar_downloader.legend_canvas = legend_canvas
logger.info("ApplicationController instance created")

# Set the position of the sashes to divide the window equally
def set_sash_positions(event=None):
    width = paned_window.winfo_width()
    if width > 0:  # Only adjust if width is valid
        # Calculate positions ensuring minimum width for each panel
        first_sash = max(500, width // 3)
        second_sash = max(first_sash + 500, 2 * width // 3)

        # Place sashes
        paned_window.sash_place(0, first_sash, 0)
        paned_window.sash_place(1, second_sash, 0)

# Bind the function to configure event of paned_window
paned_window.bind("<Configure>", set_sash_positions)

# Instructions Label
instructions = tk.Label(right_frame, text="Drag and drop a PDF file to load project details", font=("Arial", 10, "italic"))
instructions.pack(pady=5)

# Menu Bar
logger.info("Setting up menu bar")
menu_bar = tk.Menu(root)
root.config(menu=menu_bar)

# File Menu
file_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="File", menu=file_menu)

# Add menu items
file_menu.add_command(label="Import JSON", command=import_tower_parameters_json)
file_menu.add_separator()
file_menu.add_command(label="Clear Data", command=clear_data)
file_menu.add_command(label="Export KML", command=export_kml)
file_menu.add_command(label="Export Shapefile", command=export_shapefile)
file_menu.add_command(label="Export Poly", command=export_poly)

# Add Export Search Rings command using the lidar_downloader instance
file_menu.add_command(
    label="Export Search Rings",
    command=lambda: lidar_downloader.export_rings_for_sites()
)

file_menu.add_separator()
file_menu.add_command(label="Exit", command=root.quit)

# Help Menu
help_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Help", menu=help_menu)
help_menu.add_command(
    label="About",
    command=lambda: messagebox.showinfo(
        "About",
        "Microwave Line of Sight Project Viewer\nVersion 1.0"
    )
)

# Tools Menu
tools_menu = tk.Menu(menu_bar, tearoff=0)
menu_bar.add_cascade(label="Tools", menu=tools_menu)
tools_menu.add_command(label="Find Turbines", command=lidar_downloader.find_turbines)

# Bind drag-and-drop event
logger.info("Binding drag-and-drop event")
root.drop_target_register(DND_FILES)
root.dnd_bind('<<Drop>>', on_file_drop)

# Create Obstruction Search section
obstruction_search_frame = ttk.LabelFrame(center_frame, text="Obstruction Search")
obstruction_search_frame.pack(fill="x", padx=10, pady=5)

# Add search frame inside obstruction section
obstruction_button_frame = ttk.Frame(obstruction_search_frame)
obstruction_button_frame.pack(fill=tk.X, padx=5, pady=5)

# Create a style for obstruction buttons
style = ttk.Style()
style.configure('Obstruction.TButton', padding=(2, 1), font=('TkDefaultFont', 9))

# Configure columns for even distribution
obstruction_button_frame.columnconfigure(0, weight=1)
obstruction_button_frame.columnconfigure(1, weight=1)

# Row 1 - Search buttons
search_turbines_button = ttk.Button(
    obstruction_button_frame,
    text="Search Turbines",
    command=lidar_downloader.find_turbines,
    style='Obstruction.TButton'
)
search_turbines_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

state_search_button = ttk.Button(
    obstruction_button_frame,
    text="Search State Turbines",
    command=lambda: lidar_downloader.find_state_turbines(),
    style='Obstruction.TButton'
)
state_search_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

# Row 2 - Export buttons
export_map_button = ttk.Button(
    obstruction_button_frame,
    text="Export Map View",
    command=lambda: lidar_downloader.export_map_view(),
    style='Obstruction.TButton'
)
export_map_button.grid(row=1, column=0, columnspan=2, padx=2, pady=2, sticky="ew")

# Create obstruction info frame
obstruction_info_frame = ttk.LabelFrame(center_frame, text="Obstruction Information")
obstruction_info_frame.pack(fill="x", padx=10, pady=5)

# Add text display for obstruction info
obstruction_text = tk.Text(obstruction_info_frame, height=3, wrap=tk.WORD)
obstruction_text.pack(fill="x", padx=5, pady=5)
obstruction_text.insert("1.0", "No obstructions analyzed yet")
obstruction_text.config(state="disabled")

# Set the obstruction_text widget in the lidar_downloader
lidar_downloader.obstruction_text = obstruction_text

logger.info("Application setup complete, entering main loop")
root.mainloop()
logger.info("Application closed")

