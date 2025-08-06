"""
Site management utilities for the LOS application.
Provides functions for managing site data.
"""

import tkinter as tk
from tkinter import messagebox
import json
import re
import logging
import os
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def update_json_file(extracted_data):
    """
    Update the tower_parameters.json file with the extracted data.
    Clears all existing lidar data and turbine search results.

    Args:
        extracted_data: Dictionary containing site data
    """
    # Clean up coordinate formats
    if 'site_A' in extracted_data and 'longitude' in extracted_data['site_A']:
        # Fix formatting issues in coordinates by removing extra spaces between digits
        extracted_data['site_A']['longitude'] = re.sub(r'(\d+)-(\d+)-\s+(\d+)', r'\1-\2-\3', extracted_data['site_A']['longitude'])
        extracted_data['site_A']['latitude'] = re.sub(r'(\d+)-(\d+)-\s+(\d+)', r'\1-\2-\3', extracted_data['site_A']['latitude'])

    if 'site_B' in extracted_data and 'longitude' in extracted_data['site_B']:
        # Fix formatting issues in coordinates by removing extra spaces between digits
        extracted_data['site_B']['longitude'] = re.sub(r'(\d+)-(\d+)-\s+(\d+)', r'\1-\2-\3', extracted_data['site_B']['longitude'])
        extracted_data['site_B']['latitude'] = re.sub(r'(\d+)-(\d+)-\s+(\d+)', r'\1-\2-\3', extracted_data['site_B']['latitude'])

    # Validate and handle frequency_ghz
    if 'general_parameters' in extracted_data:
        frequency_ghz = extracted_data['general_parameters'].get('frequency_ghz')
        
        # Check if frequency is invalid (null, 0, or negative)
        if frequency_ghz is None or frequency_ghz == 0.0 or (isinstance(frequency_ghz, (int, float)) and frequency_ghz <= 0):
            logger.warning("Invalid or missing frequency_ghz detected in extracted data")
            
            # Try to prompt user for frequency
            from tkinter import simpledialog
            frequency_input = simpledialog.askstring(
                "Missing Frequency",
                "The frequency could not be extracted from the document.\n\n"
                "Please enter the microwave link frequency in GHz\n"
                "(common values: 6, 11, 18, 23, 38):",
                initialvalue="11.0"
            )
            
            if frequency_input:
                try:
                    frequency_ghz = float(frequency_input)
                    if frequency_ghz <= 0:
                        logger.error("User entered invalid frequency value")
                        messagebox.showwarning("Invalid Frequency", "Frequency must be greater than 0 GHz. Please re-enter.")
                        return False  # Don't save invalid data
                    else:
                        logger.info(f"User provided frequency: {frequency_ghz} GHz")
                except ValueError:
                    logger.error("User entered non-numeric frequency value")
                    messagebox.showwarning("Invalid Frequency", "Invalid frequency value. Please re-enter.")
                    return False  # Don't save invalid data
            else:
                logger.info("User cancelled frequency input, keeping original frequency value")
                # Don't override - keep the original value that may have been extracted correctly
                frequency_ghz = extracted_data['general_parameters'].get('frequency_ghz')
                if frequency_ghz is None:
                    logger.warning("No frequency available - user will need to set manually")
                    frequency_ghz = None  # Set to None instead of hardcoded default
            
            # Update the extracted data with the validated frequency
            extracted_data['general_parameters']['frequency_ghz'] = frequency_ghz
        else:
            logger.info(f"Valid frequency found in extracted data: {frequency_ghz} GHz")

    # Create a fresh JSON structure with only essential data
    new_data = {
        'site_A': extracted_data['site_A'],
        'site_B': extracted_data['site_B'],
        'general_parameters': extracted_data['general_parameters'],
        # Initialize empty arrays for data that will be populated later
        'turbines': [],
        'lidar_data': {}
    }

    logger.info("Cleared existing lidar and turbine data while updating tower_parameters.json")

    # Write the new data to file
    with open('tower_parameters.json', 'w') as file:
        json.dump(new_data, file, indent=2)

    # Return the new data for further processing
    return new_data

def open_manual_sites(root, convert_dms_to_decimal, calculate_distance, update_details_in_app, ManualSitesDialog, lidar_downloader=None):
    """
    Open dialog for manual entry of site coordinates

    Args:
        root: The root Tkinter window
        convert_dms_to_decimal: Function to convert DMS to decimal coordinates
        calculate_distance: Function to calculate distance between points
        update_details_in_app: Function to update the app with new site details
        ManualSitesDialog: Dialog class for manual site entry
        lidar_downloader: LidarDownloader instance for tower search
    """
    def process_manual_data(data):
        """Process the manually entered data"""
        logger.info("Processing manually entered site data")
        try:
            # Update JSON file
            update_json_file(data)
            # Update app details
            update_details_in_app(data)

            # Run tower search after saving site data
            logger.info("Running tower search after manual site entry")
            if lidar_downloader:
                # Use after to avoid blocking the UI
                root.after(1000, lambda: lidar_downloader.search_towers())
                logger.info("Scheduled tower search after manual site entry")
            else:
                logger.warning("No lidar_downloader available for tower search")
        except Exception as e:
            logger.error(f"Error processing manual site data: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to process site data: {str(e)}")

    # Create and show dialog
    dialog = ManualSitesDialog(root, process_manual_data, convert_dms_to_decimal, calculate_distance)
    root.wait_window(dialog)

def edit_sites(root, convert_dms_to_decimal, calculate_distance, update_details_in_app, ManualSitesDialog, lidar_downloader=None):
    """
    Edit existing site coordinates

    Args:
        root: The root Tkinter window
        convert_dms_to_decimal: Function to convert DMS to decimal coordinates
        calculate_distance: Function to calculate distance between points
        update_details_in_app: Function to update the app with new site details
        ManualSitesDialog: Dialog class for manual site entry
        lidar_downloader: LidarDownloader instance for tower search
    """
    try:
        # Get current data from JSON file
        with open("tower_parameters.json", "r") as f:
            current_data = json.load(f)

        # Define callback for the dialog
        def process_site_data(data):
            """Process the site data from dialog"""
            logger.info("Processing site data from edit dialog")
            try:
                # Update JSON file
                update_json_file(data)
                # Update app details
                update_details_in_app(data)

                # Run tower search after saving site data
                logger.info("Running tower search after site edit")
                if lidar_downloader:
                    # Use after to avoid blocking the UI
                    root.after(1000, lambda: lidar_downloader.search_towers())
                    logger.info("Scheduled tower search after site edit")
                else:
                    logger.warning("No lidar_downloader available for tower search")
            except Exception as e:
                logger.error(f"Error processing site data: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to process site data: {str(e)}")

        # Create and show dialog with current data
        dialog = ManualSitesDialog(root, process_site_data, convert_dms_to_decimal, calculate_distance)

        # Pre-fill the dialog with current values if available
        if 'site_A' in current_data and 'site_B' in current_data:
            # Site A
            site_a = current_data['site_A']
            dialog.site_a_fields["site_id"].delete(0, tk.END)
            dialog.site_a_fields["site_id"].insert(0, site_a.get('site_id', 'Donor Site'))

            dialog.site_a_fields["latitude"].delete(0, tk.END)
            dialog.site_a_fields["latitude"].insert(0, site_a.get('latitude', ''))

            dialog.site_a_fields["longitude"].delete(0, tk.END)
            dialog.site_a_fields["longitude"].insert(0, site_a.get('longitude', ''))

            dialog.site_a_fields["elevation_ft"].delete(0, tk.END)
            dialog.site_a_fields["elevation_ft"].insert(0, site_a.get('elevation_ft', '0'))

            dialog.site_a_fields["antenna_cl_ft"].delete(0, tk.END)
            dialog.site_a_fields["antenna_cl_ft"].insert(0, site_a.get('antenna_cl_ft', '0'))

            dialog.site_a_fields["azimuth_deg"].delete(0, tk.END)
            dialog.site_a_fields["azimuth_deg"].insert(0, site_a.get('azimuth_deg', '0'))

            # Site B
            site_b = current_data['site_B']
            dialog.site_b_fields["site_id"].delete(0, tk.END)
            dialog.site_b_fields["site_id"].insert(0, site_b.get('site_id', 'Recipient Site'))

            dialog.site_b_fields["latitude"].delete(0, tk.END)
            dialog.site_b_fields["latitude"].insert(0, site_b.get('latitude', ''))

            dialog.site_b_fields["longitude"].delete(0, tk.END)
            dialog.site_b_fields["longitude"].insert(0, site_b.get('longitude', ''))

            dialog.site_b_fields["elevation_ft"].delete(0, tk.END)
            dialog.site_b_fields["elevation_ft"].insert(0, site_b.get('elevation_ft', '0'))

            dialog.site_b_fields["antenna_cl_ft"].delete(0, tk.END)
            dialog.site_b_fields["antenna_cl_ft"].insert(0, site_b.get('antenna_cl_ft', '0'))

            dialog.site_b_fields["azimuth_deg"].delete(0, tk.END)
            dialog.site_b_fields["azimuth_deg"].insert(0, site_b.get('azimuth_deg', '0'))

            # Load frequency value if available
            if 'general_parameters' in current_data and 'frequency_ghz' in current_data['general_parameters']:
                dialog.frequency_ghz.delete(0, tk.END)
                dialog.frequency_ghz.insert(0, str(current_data['general_parameters']['frequency_ghz']))

        root.wait_window(dialog)
    except Exception as e:
        logger.error(f"Error in edit_sites: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to edit sites: {str(e)}")

def load_site_data():
    """
    Load site data from tower_parameters.json

    Returns:
        Dictionary containing site data, or None if file doesn't exist
    """
    try:
        if os.path.exists("tower_parameters.json"):
            with open("tower_parameters.json", "r") as f:
                return json.load(f)
        else:
            logger.warning("tower_parameters.json not found")
            return None
    except Exception as e:
        logger.error(f"Error loading site data: {e}", exc_info=True)
        return None
