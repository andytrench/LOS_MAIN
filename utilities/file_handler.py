"""
File handling module for the LOS application.
Handles file drops, processing, and JSON updates.
"""

import json
import logging
import os
import shutil
from datetime import datetime
from tkinter import messagebox
from log_config import setup_logging
from utilities.ai_processor import process_document_with_ai
from utilities.temp_dir_manager import get_temp_dir, get_temp_file, copy_to_output_dir

# Create logger
logger = setup_logging(__name__)

def update_json_file(data):
    """Update the tower_parameters.json file with new data"""
    try:
        # Create backup of existing file in a temp directory
        if os.path.exists("tower_parameters.json"):
            # Create a temp directory for backups
            backup_dir = get_temp_dir(prefix="json_backup_")
            backup_filename = f"tower_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.bak"
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2("tower_parameters.json", backup_path)
            logger.info(f"Created backup of tower_parameters.json in temp directory: {backup_path}")

        # Validate and handle frequency_ghz before saving
        if 'general_parameters' in data:
            frequency_ghz = data['general_parameters'].get('frequency_ghz')
            
            # Check if frequency is invalid (null, 0, or negative)
            if frequency_ghz is None or frequency_ghz == 0.0 or (isinstance(frequency_ghz, (int, float)) and frequency_ghz <= 0):
                logger.warning("Invalid or missing frequency_ghz detected in data before saving")
                
                # Try to prompt user for frequency
                from tkinter import messagebox, simpledialog
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
                    frequency_ghz = data['general_parameters'].get('frequency_ghz')
                    if frequency_ghz is None:
                        logger.warning("No frequency available - user will need to set manually")
                        frequency_ghz = None  # Set to None instead of hardcoded default
                
                # Update the data with the validated frequency
                data['general_parameters']['frequency_ghz'] = frequency_ghz
            else:
                logger.info(f"Valid frequency found in data: {frequency_ghz} GHz")

        # Update with new data using the safer method
        result = save_json_data(data, "tower_parameters.json")

        if result:
            logger.info("Successfully updated tower_parameters.json")
        else:
            logger.error("Failed to update tower_parameters.json")

        return result
    except Exception as e:
        logger.error(f"Error updating JSON file: {str(e)}", exc_info=True)
        messagebox.showerror("Error", f"Failed to update JSON file: {str(e)}")
        return False

def process_dropped_file(file_path, update_app_callback):
    """Process a dropped file and extract data"""
    logger.info(f"Processing dropped file: {file_path}")
    try:
        # Process document with AI
        extracted_data = process_document_with_ai(file_path)

        if extracted_data and 'site_A' in extracted_data and 'site_B' in extracted_data:
            logger.info("Successfully extracted data. Updating JSON and app.")
            update_json_file(extracted_data)
            update_app_callback(extracted_data)
            return True
        else:
            logger.warning("Could not extract all necessary details from the file.")
            messagebox.showwarning("Extraction Error", "Could not extract all necessary details from the file.")
            return False
    except Exception as e:
        logger.error(f"An error occurred while processing the file: {str(e)}", exc_info=True)
        messagebox.showerror("Error", f"An error occurred while processing the file: {str(e)}")
        return False

def load_json_data(file_path="tower_parameters.json"):
    """Load data from JSON file"""
    try:
        if not os.path.exists(file_path):
            logger.warning(f"JSON file not found: {file_path}")
            return None

        with open(file_path, "r") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {file_path}: {str(e)}", exc_info=True)

        # Create a backup of the corrupted file
        backup_path = f"{file_path}.corrupted.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup of corrupted file at {backup_path}")
        except Exception as backup_err:
            logger.error(f"Failed to create backup of corrupted file: {str(backup_err)}")

        return None
    except Exception as e:
        logger.error(f"Error loading JSON file: {str(e)}", exc_info=True)
        return None

def save_json_data(data, file_path="tower_parameters.json"):
    """Save data to JSON file using a temporary file in a temp directory"""
    try:
        # Create a temporary file in a temp directory
        temp_path = get_temp_file(suffix=".json.tmp", prefix="json_")

        # Write data to the temporary file
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)

        # Then rename it to the target file
        if os.path.exists(file_path):
            os.replace(temp_path, file_path)
        else:
            shutil.copy2(temp_path, file_path)
            os.remove(temp_path)  # Remove the temp file after copying

        logger.info(f"Data saved to {file_path}")
        return True
    except Exception as e:
        logger.error(f"Error saving JSON file: {str(e)}", exc_info=True)
        return False

def clear_json_section(section_key, file_path="tower_parameters.json"):
    """Clear a specific section in the JSON file"""
    try:
        data = load_json_data(file_path)
        if data and section_key in data:
            if isinstance(data[section_key], dict):
                data[section_key] = {}
            elif isinstance(data[section_key], list):
                data[section_key] = []
            else:
                data[section_key] = None

            save_json_data(data, file_path)
            logger.info(f"Cleared section '{section_key}' in {file_path}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error clearing JSON section: {str(e)}", exc_info=True)
        return False

def update_json_section(section_key, section_data, file_path="tower_parameters.json"):
    """Update a specific section in the JSON file"""
    try:
        data = load_json_data(file_path)
        if data is None:
            # Create a new data structure if the file doesn't exist or is corrupted
            data = {
                "site_A": {},
                "site_B": {},
                "general_parameters": {},
                "lidar_data": {},
                "turbines": [],
                "fresnel_parameters": {
                    "fresnel_found": False,
                    "zones": [
                        {
                            "zone": 1,
                            "enabled": True,
                            "zone_percent": 60.0,
                            "k_factor": 1.33,
                            "color": "#0000FF",
                            "color_name": "blue"
                        },
                        {
                            "zone": 2,
                            "enabled": True,
                            "zone_percent": 30.0,
                            "k_factor": 0.67,
                            "color": "#FFFF00",
                            "color_name": "yellow"
                        },
                        {
                            "zone": 3,
                            "enabled": True,
                            "zone_percent": 100.0,
                            "k_factor": 1.33,
                            "color": "#FF0000",
                            "color_name": "red"
                        },
                        {
                            "zone": 4,
                            "enabled": True,
                            "zone_percent": 115.0,  # 15% margin over the largest Fresnel zone
                            "k_factor": 1.33,  # Use same K factor as zone 1
                            "color": "#800080",
                            "color_name": "purple",
                            "name": "Report Fresnel",
                            "description": "15% margin over the largest Fresnel zone for reporting purposes"
                        }
                    ]
                }
            }

        # Update the section
        data[section_key] = section_data

        # Save the updated data
        result = save_json_data(data, file_path)
        if result:
            logger.info(f"Updated section '{section_key}' in {file_path}")
        else:
            logger.error(f"Failed to update section '{section_key}' in {file_path}")

        return result
    except Exception as e:
        logger.error(f"Error updating JSON section: {str(e)}", exc_info=True)
        return False

def reset_json_file_for_new_project(file_path="tower_parameters.json"):
    """Reset the JSON file for a new project, preserving only site and general parameters"""
    try:
        # Load existing data
        data = load_json_data(file_path)

        # Create a backup in a temp directory if the file exists
        if os.path.exists(file_path):
            backup_dir = get_temp_dir(prefix="json_backup_")
            backup_filename = f"tower_parameters_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.bak"
            backup_path = os.path.join(backup_dir, backup_filename)
            shutil.copy2(file_path, backup_path)
            logger.info(f"Created backup of {file_path} in temp directory: {backup_path}")

        # Extract the sections to preserve if data exists
        if data is not None:
            site_a = data.get('site_A', {})
            site_b = data.get('site_B', {})
            general_parameters = data.get('general_parameters', {})
            fresnel_parameters = data.get('fresnel_parameters', None)
        else:
            # Default empty structure if no data exists
            site_a = {}
            site_b = {}
            general_parameters = {}
            fresnel_parameters = None
            logger.warning(f"No existing data found in {file_path}, creating new structure")

        # Create a new data structure with only the preserved sections
        # Ensure exact structure with all required fields
        new_data = {
            "site_A": site_a,
            "site_B": site_b,
            "general_parameters": general_parameters,
            "turbines": [],
            "lidar_data": {}
        }

        # Add Fresnel parameters if they exist
        if fresnel_parameters:
            new_data['fresnel_parameters'] = fresnel_parameters
            logger.info("Preserved Fresnel parameters during JSON reset")

        # Save the new data using a direct approach to ensure correct formatting
        try:
            # First write to a string to verify JSON is valid
            json_str = json.dumps(new_data, indent=2)

            # Create a temporary file in a temp directory
            temp_path = get_temp_file(suffix=".json.tmp", prefix="json_reset_")

            # Write to the temporary file
            with open(temp_path, "w") as f:
                f.write(json_str)

            # Verify the temporary file is valid JSON
            with open(temp_path, "r") as f:
                json.load(f)  # This will raise an exception if JSON is invalid

            # Replace the original file with the temporary file
            if os.path.exists(file_path):
                os.replace(temp_path, file_path)
            else:
                shutil.copy2(temp_path, file_path)
                os.remove(temp_path)  # Remove the temp file after copying

            logger.info(f"Reset {file_path} for new project, preserving site and general parameters")
            return True
        except Exception as write_error:
            logger.error(f"Error writing reset JSON file: {str(write_error)}", exc_info=True)
            # Try to clean up the temporary file
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except:
                pass
            return False
    except Exception as e:
        logger.error(f"Error resetting JSON file for new project: {str(e)}", exc_info=True)
        return False
