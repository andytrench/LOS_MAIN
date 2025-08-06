"""
Utility functions for exporting data from the application.
"""

import os
import csv
import json
import logging
import math
import pandas as pd
import platform
import shutil
import subprocess
from datetime import datetime
from tkinter import filedialog, messagebox
from PIL import ImageGrab
from utilities.file_operation_utils import safe_copy_file, safe_create_directory

# Set up logging
logger = logging.getLogger(__name__)

def export_lidar_data_to_csv(lidar_downloader):
    """
    Export LIDAR data table to CSV file.

    Args:
        lidar_downloader: The LidarDownloader instance containing the LIDAR data

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        # Check if there's data to export
        if not hasattr(lidar_downloader, 'urls') or not lidar_downloader.urls:
            messagebox.showwarning("No Data", "No LIDAR data available to export.")
            return False

        # Ask for save location
        output_file = filedialog.asksaveasfilename(
            title="Save LIDAR Data",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")]
        )

        if not output_file:
            logger.info("LIDAR data export cancelled by user")
            return False

        # Prepare data for export
        data = []
        for url, item in lidar_downloader.urls:
            # Extract relevant information
            file_data = {
                'Source ID': item.get('sourceId', ''),
                'Title': item.get('title', ''),
                'Project Name': item.get('projectName', ''),
                'Publication Date': item.get('publicationDate', ''),
                'Last Updated': item.get('lastUpdated', ''),
                'Format': item.get('format', ''),
                'Size (bytes)': item.get('sizeInBytes', ''),
                'Download URL': url
            }

            # Add bounding box information if available
            bbox = item.get('boundingBox', {})
            if bbox:
                file_data.update({
                    'Min X': bbox.get('minX', ''),
                    'Min Y': bbox.get('minY', ''),
                    'Max X': bbox.get('maxX', ''),
                    'Max Y': bbox.get('maxY', '')
                })

            data.append(file_data)

        # Write to CSV
        if data:
            # Convert to DataFrame for easier CSV export
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False)

            logger.info(f"LIDAR data exported to {output_file}")
            messagebox.showinfo("Export Successful", f"LIDAR data exported to:\n{output_file}")

            # Open the directory containing the file
            try:
                os.startfile(os.path.dirname(output_file)) if os.name == 'nt' else os.system(f'open "{os.path.dirname(output_file)}"')
            except Exception as e:
                logger.error(f"Error opening directory: {e}")

            return True
        else:
            messagebox.showwarning("No Data", "No LIDAR data available to export.")
            return False

    except Exception as e:
        logger.error(f"Error exporting LIDAR data to CSV: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export LIDAR data: {str(e)}")
        return False

def export_lidar_data_to_json(lidar_downloader):
    """
    Export LIDAR data table to JSON file.

    Args:
        lidar_downloader: The LidarDownloader instance containing the LIDAR data

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        # Check if there's data to export
        if not hasattr(lidar_downloader, 'urls') or not lidar_downloader.urls:
            messagebox.showwarning("No Data", "No LIDAR data available to export.")
            return False

        # Ask for save location
        output_file = filedialog.asksaveasfilename(
            title="Save LIDAR Data",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )

        if not output_file:
            logger.info("LIDAR data export cancelled by user")
            return False

        # Prepare data for export
        data = []
        for url, item in lidar_downloader.urls:
            # Create a copy of the item to avoid modifying the original
            item_copy = item.copy() if isinstance(item, dict) else {}

            # Add the URL to the item
            item_copy['downloadURL'] = url

            # Add to data list
            data.append(item_copy)

        # Write to JSON
        if data:
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

            logger.info(f"LIDAR data exported to {output_file}")
            messagebox.showinfo("Export Successful", f"LIDAR data exported to:\n{output_file}")

            # Open the directory containing the file
            try:
                os.startfile(os.path.dirname(output_file)) if os.name == 'nt' else os.system(f'open "{os.path.dirname(output_file)}"')
            except Exception as e:
                logger.error(f"Error opening directory: {e}")

            return True
        else:
            messagebox.showwarning("No Data", "No LIDAR data available to export.")
            return False

    except Exception as e:
        logger.error(f"Error exporting LIDAR data to JSON: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export LIDAR data: {str(e)}")
        return False

def export_map_view(map_widget, parent_window=None):
    """
    Export the current map view as an image.

    Args:
        map_widget: The map widget to capture
        parent_window: The parent window (for dialog positioning)

    Returns:
        bool: True if export was successful, False otherwise
        str: Path to the exported image if successful, None otherwise
    """
    try:
        # Ask for save location
        output_file = filedialog.asksaveasfilename(
            title="Save Map View",
            defaultextension=".png",
            filetypes=[("PNG Files", "*.png"), ("JPEG Files", "*.jpg"), ("All Files", "*.*")]
        )

        if not output_file:
            logger.info("Map view export cancelled by user")
            return False, None

        # Ensure map widget is updated
        if hasattr(map_widget, 'update'):
            map_widget.update()

        # Get map widget's position and size
        x = map_widget.winfo_rootx()
        y = map_widget.winfo_rooty()
        width = map_widget.winfo_width()
        height = map_widget.winfo_height()

        # Capture screenshot
        image = ImageGrab.grab((x, y, x+width, y+height))

        # Save image
        image.save(output_file)

        logger.info(f"Map view exported to {output_file}")
        messagebox.showinfo("Export Successful", f"Map view exported to:\n{output_file}")

        # Open the directory containing the file
        try:
            os.startfile(os.path.dirname(output_file)) if os.name == 'nt' else os.system(f'open "{os.path.dirname(output_file)}"')
        except Exception as e:
            logger.error(f"Error opening directory: {e}")

        return True, output_file

    except Exception as e:
        logger.error(f"Error exporting map view: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export map view: {str(e)}")
        return False, None

def export_criticals(app_controller, output_dir=None):
    """
    Export critical project files:
    1. LIDAR data table to a folder called "image_LIDAR_table"
    2. Map view to a folder called "image_LIDAR_map"
    3. Copy tower_parameters.json file to the output directory

    Args:
        app_controller: The application controller instance
        output_dir: Optional output directory. If None, user will be prompted

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        # Ask for output directory if not provided
        if not output_dir:
            output_dir = filedialog.askdirectory(
                title="Select folder to save critical files",
                initialdir=os.path.expanduser("~")
            )

        if not output_dir:
            logger.info("Criticals export cancelled by user")
            return False

        logger.info(f"Exporting critical files to: {output_dir}")

        # Create subdirectories
        lidar_table_dir = os.path.join(output_dir, "image_LIDAR_table")
        lidar_map_dir = os.path.join(output_dir, "image_LIDAR_map")

        safe_create_directory(lidar_table_dir)
        safe_create_directory(lidar_map_dir)

        # 1. Export LIDAR data table to CSV
        lidar_success = False
        if hasattr(app_controller, 'downloader') and app_controller.downloader:
            try:
                # Get the currently selected project if available
                selected_project = None
                if hasattr(app_controller, 'project_details') and hasattr(app_controller.project_details, 'project_combobox'):
                    selected_project = app_controller.project_details.project_combobox.get()
                    if selected_project == "Overview":
                        selected_project = None

                # Get project data if available
                project_data = None
                if selected_project and hasattr(app_controller, 'project_metadata'):
                    project_data = app_controller.project_metadata.get_project(selected_project)

                # Prepare data for export
                data = []
                for url, item in app_controller.downloader.urls:
                    # Extract relevant information
                    file_data = {
                        'Source ID': item.get('sourceId', ''),
                        'Title': item.get('title', ''),
                        'Project Name': item.get('projectName', ''),
                        'Publication Date': item.get('publicationDate', ''),
                        'Last Updated': item.get('lastUpdated', ''),
                        'Format': item.get('format', ''),
                        'Size (bytes)': item.get('sizeInBytes', ''),
                        'Download URL': url
                    }

                    # Add bounding box information if available
                    bbox = item.get('boundingBox', {})
                    if bbox:
                        file_data.update({
                            'Min X': bbox.get('minX', ''),
                            'Min Y': bbox.get('minY', ''),
                            'Max X': bbox.get('maxX', ''),
                            'Max Y': bbox.get('maxY', '')
                        })

                    data.append(file_data)

                # Write to CSV
                if data:
                    # Create output file path
                    output_file = os.path.join(lidar_table_dir, "lidar_data.csv")

                    # Convert to DataFrame for easier CSV export
                    df = pd.DataFrame(data)
                    df.to_csv(output_file, index=False)

                    logger.info(f"LIDAR data exported to {output_file}")
                    lidar_success = True
            except Exception as e:
                logger.error(f"Error exporting LIDAR data: {e}", exc_info=True)

        # 2. Export map view using the same process as in project certificate
        map_success = False
        try:
            # Check if we have tower parameters
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    site_a = tower_params.get('site_A', {})
                    site_b = tower_params.get('site_B', {})
            except Exception as e:
                logger.warning(f"Could not load tower parameters: {e}")
                site_a = {}
                site_b = {}

            # Get bounds information
            bounds = {}

            # Try to get bounds from project data if available
            if hasattr(app_controller, 'project_details') and hasattr(app_controller.project_details, 'project_combobox'):
                selected = app_controller.project_details.project_combobox.get()
                if selected and selected != "Overview" and hasattr(app_controller, 'project_metadata'):
                    project_data = app_controller.project_metadata.get_project(selected)
                    if project_data and 'bounds' in project_data:
                        bounds = project_data['bounds']
                        logger.info(f"Using bounds from project: {selected}")

            # If no bounds from project, try to get from LIDAR data
            if not bounds and hasattr(app_controller, 'downloader') and app_controller.downloader:
                # Collect bounds from all LIDAR tiles
                all_tile_bounds = []
                for url, item in app_controller.downloader.urls:
                    bbox = item.get('boundingBox', {})
                    if bbox:
                        all_tile_bounds.append(bbox)

                if all_tile_bounds:
                    # Calculate overall bounds from all tiles
                    bounds = {
                        'minY': min(b.get('minY', 90) for b in all_tile_bounds),
                        'maxY': max(b.get('maxY', -90) for b in all_tile_bounds),
                        'minX': min(b.get('minX', 180) for b in all_tile_bounds),
                        'maxX': max(b.get('maxX', -180) for b in all_tile_bounds)
                    }
                    logger.info("Using bounds calculated from LIDAR tiles")

            # If still no bounds, use site coordinates
            if not bounds and site_a and site_b:
                # Convert coordinates to decimal if needed
                try:
                    from utilities.coordinates import convert_dms_to_decimal
                    lat_a, lon_a = convert_dms_to_decimal(site_a.get('latitude', '0'), site_a.get('longitude', '0'))
                    lat_b, lon_b = convert_dms_to_decimal(site_b.get('latitude', '0'), site_b.get('longitude', '0'))

                    # Create bounds with padding
                    padding = 0.05  # About 5km at equator
                    bounds = {
                        'minY': min(lat_a, lat_b) - padding,
                        'maxY': max(lat_a, lat_b) + padding,
                        'minX': min(lon_a, lon_b) - padding,
                        'maxX': max(lon_a, lon_b) + padding
                    }
                    logger.info("Using bounds calculated from site coordinates")
                except Exception as e:
                    logger.error(f"Error calculating bounds from site coordinates: {e}")

            # If we have bounds, capture the map
            if bounds and all(k in bounds for k in ['minY', 'maxY', 'minX', 'maxX']):
                # Add project name to bounds for the capture
                bounds['project_name'] = "Critical Export"

                # Ensure LIDAR tile bounding boxes are visible
                selected_project = None
                if hasattr(app_controller, 'project_details') and hasattr(app_controller.project_details, 'project_combobox'):
                    selected_project = app_controller.project_details.project_combobox.get()
                    if selected_project == "Overview":
                        selected_project = None

                # Make sure project tiles are visible
                if selected_project and hasattr(app_controller, 'project_visibility') and selected_project in app_controller.project_visibility:
                    # Set the project visibility to True to ensure tiles are shown
                    app_controller.project_visibility[selected_project].set(True)
                    # Call the toggle function to apply the visibility change
                    if hasattr(app_controller, 'toggle_project_visibility'):
                        logger.info(f"Ensuring LIDAR tiles for project {selected_project} are visible")
                        app_controller.toggle_project_visibility(selected_project)

                    # Give time for the UI to update
                    import time
                    app_controller.root.update()
                    time.sleep(0.5)

                # Use the same capture_coverage_map method as in project certificate
                if hasattr(app_controller, 'capture_coverage_map'):
                    coverage_map = app_controller.capture_coverage_map(bounds, site_a, site_b)
                    if coverage_map:
                        # Copy the map to our output directory
                        output_file = os.path.join(lidar_map_dir, "map_view.png")
                        safe_copy_file(coverage_map, output_file)
                        logger.info(f"Map view exported to {output_file}")
                        map_success = True
                else:
                    # Fallback to direct capture if capture_coverage_map not available
                    if hasattr(app_controller, 'map_widget_ref') and app_controller.map_widget_ref:
                        map_widget = app_controller.map_widget_ref

                        # Center map on bounds
                        center_lat = (bounds['minY'] + bounds['maxY']) / 2
                        center_lon = (bounds['minX'] + bounds['maxX']) / 2
                        map_widget.set_position(center_lat, center_lon)

                        # Calculate zoom level based on bounds
                        lat_diff = bounds['maxY'] - bounds['minY']
                        lon_diff = bounds['maxX'] - bounds['minX']
                        max_diff = max(lat_diff, lon_diff)
                        zoom = max(1, min(19, int(14 - math.log2(max_diff * 111))))  # Rough conversion to appropriate zoom
                        map_widget.set_zoom(zoom)

                        # If we have a selected project, ensure its LIDAR tiles are visible
                        if selected_project and hasattr(app_controller, 'downloader'):
                            # Check if the downloader has a method to ensure tiles are visible
                            if hasattr(app_controller.downloader, 'ensure_project_tiles_visible'):
                                logger.info(f"Ensuring LIDAR tiles for project {selected_project} are visible")
                                app_controller.downloader.ensure_project_tiles_visible(selected_project)

                            # Alternative approach: if the project has a visibility toggle
                            elif hasattr(app_controller.downloader, 'project_visibility') and selected_project in app_controller.downloader.project_visibility:
                                app_controller.downloader.project_visibility[selected_project].set(True)
                                if hasattr(app_controller.downloader, 'toggle_project_visibility'):
                                    app_controller.downloader.toggle_project_visibility(selected_project)

                        # Wait for map to update
                        import time
                        map_widget.update()
                        app_controller.root.update()
                        time.sleep(1.5)  # Wait for map to render

                        # Capture screenshot
                        x = map_widget.winfo_rootx()
                        y = map_widget.winfo_rooty()
                        width = map_widget.winfo_width()
                        height = map_widget.winfo_height()

                        image = ImageGrab.grab((x, y, x+width, y+height))
                        output_file = os.path.join(lidar_map_dir, "map_view.png")
                        image.save(output_file)

                        logger.info(f"Map view exported to {output_file}")
                        map_success = True
            else:
                logger.warning("No valid bounds found for map capture")
        except Exception as e:
            logger.error(f"Error exporting map view: {e}", exc_info=True)

        # 3. Copy tower_parameters.json file
        json_success = False
        tower_params_path = os.path.join(os.getcwd(), "tower_parameters.json")
        if os.path.exists(tower_params_path):
            try:
                # Copy the file to the output directory
                output_json_path = os.path.join(output_dir, "tower_parameters.json")
                safe_copy_file(tower_params_path, output_json_path)
                logger.info(f"tower_parameters.json copied to {output_json_path}")
                json_success = True
            except Exception as e:
                logger.error(f"Error copying tower_parameters.json: {e}", exc_info=True)
        else:
            logger.warning("tower_parameters.json not found")

        # Show results
        success_items = []
        if lidar_success:
            success_items.append("LIDAR data table")
        if map_success:
            success_items.append("Map view")
        if json_success:
            success_items.append("tower_parameters.json")

        if success_items:
            message = "Successfully exported:\n- " + "\n- ".join(success_items)
            messagebox.showinfo("Export Complete", message)

            # Open the output directory
            try:
                if platform.system() == "Windows":
                    os.startfile(output_dir)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.call(["open", output_dir])
                else:  # Linux
                    subprocess.call(["xdg-open", output_dir])
            except Exception as e:
                logger.error(f"Error opening output directory: {e}")

            return True
        else:
            messagebox.showwarning("Export Warning", "No items were successfully exported.")
            return False

    except Exception as e:
        logger.error(f"Error exporting criticals: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export critical files: {str(e)}")
        return False
