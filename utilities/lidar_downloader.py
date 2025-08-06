"""
LidarDownloader class using the new UI components.
This is a refactored version of the LidarDownloader class from dropmap.py.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import math
import json
import os
import queue
from datetime import date
from threading import Thread

# Import utility modules
from utilities.ui_components import ButtonPanel
from utilities.ui_panels import LidarSearchPanel, ProjectControlPanel, FileListPanel
from utilities.lidar_map import export_polygon_as_kml, export_polygon_as_shapefile, export_polygon
from utilities.turbine_processor import TurbineProcessor
from utilities.metadata import ProjectMetadata
from utilities.geometry import calculate_polygon_points
from utilities.coordinates import convert_dms_to_decimal
from utilities.tower_database import ensure_tower_database_exists, search_towers_in_polygon

# Create logger
logger = logging.getLogger(__name__)

class LidarDownloader:
    """Refactored LidarDownloader class using the new UI components"""

    def __init__(self, parent, map_widget=None, root=None, downloader=None):
        """Initialize the LidarDownloader

        Args:
            parent: Parent widget
            map_widget: Map widget
            root: Root window
            downloader: Downloader instance
        """
        logger.info(f"Initializing LidarDownloader with map_widget={map_widget}, root={root}")
        self.parent = parent
        self.map_widget = map_widget
        self.root = root
        self.downloader = downloader

        # Initialize turbine processor
        self.turbine_processor = TurbineProcessor(map_widget, root)

        # Initialize variables
        self.polygon_width_ft = tk.IntVar(value=2000)
        # Add trace to update polygon when width changes
        self.polygon_width_ft.trace_add('write', self._on_width_change)

        self.polygon_points = []
        self.donor_site = None
        self.recipient_site = None
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

        # Track label visibility state
        self.show_turbine_labels = tk.BooleanVar(value=False)  # Default to hidden labels
        self.last_turbines = []  # Store last set of turbines for refreshing labels

        # Set up UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface using the new panel classes"""
        # Create main frame for center column
        self.main_frame = ttk.Frame(self.parent)
        self.main_frame.pack(fill="both", expand=True)

        # Create LIDAR search panel
        self.lidar_search_panel = LidarSearchPanel(self.main_frame)
        self.lidar_search_panel.pack(fill="x", pady=5)

        # Set callbacks for LIDAR search panel
        self.lidar_search_panel.set_callbacks(
            on_search=self.search_lidar,
            on_clear=self.clear_all_data,
            on_add_all=self.add_all_files_to_download,
            on_export_kml=lambda: export_polygon_as_kml(self.polygon_points, "search_area.kml"),
            on_export_shapefile=lambda: export_polygon_as_shapefile(self.polygon_points, "search_area.shp"),
            on_search_towers=self.search_towers
        )

        # Connect the polygon width variable
        self.lidar_search_panel.polygon_width_ft = self.polygon_width_ft

        # Create project control panel
        self.project_control_panel = ProjectControlPanel(self.main_frame)
        self.project_control_panel.pack(fill="x", pady=5)

        # Set callbacks for project control panel
        self.project_control_panel.set_callbacks(
            on_project_change=self.on_project_change,
            on_view_map=self._view_on_map,
            on_add_files=self.add_project_files_to_download
        )

        # Add separator
        ttk.Separator(self.main_frame, orient="horizontal").pack(fill="x", padx=10, pady=5)

        # Create file list panel
        self.file_list_panel = FileListPanel(self.main_frame, "LIDAR Files")
        self.file_list_panel.pack(fill="both", expand=True, pady=5)

        # Set callbacks for file list panel
        self.file_list_panel.set_callbacks(
            on_select_all=self.select_all_files,
            on_deselect_all=self.deselect_all_files,
            on_add_to_downloads=self.add_selected_to_downloads,
            on_write_metadata=self.write_project_metadata
        )

        # Store references to UI elements we need to access later
        self.tree = self.file_list_panel.tree
        self.project_dropdown = self.project_control_panel.project_dropdown
        self.project_var = self.project_control_panel.project_var
        self.start_date = self.lidar_search_panel.start_date
        self.end_date = self.lidar_search_panel.end_date

        # Add additional buttons for certificate export and search rings
        self.add_certificate_export_buttons()

    def add_certificate_export_buttons(self):
        """Add buttons for certificate export and search rings"""
        # Create a button panel for additional functionality
        self.export_button_panel = ButtonPanel(self.file_list_panel.frame)

        # First row - Export certificates buttons
        self.export_button_panel.add_row(columns=3)

        self.export_button_panel.add_button(
            "Export Certificates",
            self.export_certificates,
            column=0
        )

        self.export_button_panel.add_button(
            "Export PDF Certificates",
            lambda: self.export_certificates(format_type='pdf'),
            column=1
        )

        self.export_button_panel.add_button(
            "Export JSON Certificates",
            lambda: self.export_certificates(format_type='json'),
            column=2
        )

        # Second row - Export search rings button
        self.export_button_panel.add_row(columns=1)

        self.export_button_panel.add_button(
            "Export Search Rings",
            self.export_search_rings,
            column=0
        )

        # Third row - Refresh metadata button
        self.export_button_panel.add_row(columns=1)

        self.export_button_panel.add_button(
            "Refresh Metadata",
            self.refresh_metadata,
            column=0
        )

        # Pack the button panel
        self.export_button_panel.pack(fill="x", padx=5, pady=5)

    # Methods called from outside the class

    def set_downloader(self, downloader):
        """Set the downloader instance"""
        logger.info("Setting downloader instance")
        self.downloader = downloader

    def set_polygon_points(self, points):
        """Set the polygon points for the search area"""
        logger.info(f"Setting polygon points: {len(points)} points")
        self.polygon_points = points

        # Also set in turbine processor
        if hasattr(self, 'turbine_processor'):
            self.turbine_processor.set_polygon_points(points)

    def update_site_data(self, site_a, site_b):
        """Update the donor and recipient site data"""
        logger.info("Updating site data in LidarDownloader")
        self.donor_site = site_a
        self.recipient_site = site_b
        logger.debug(f"Updated site data - Donor: {site_a}, Recipient: {site_b}")

        # Update polygon with current width
        if site_a and site_b:
            try:
                lat_a, lon_a = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
                lat_b, lon_b = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
                self.polygon_points = calculate_polygon_points(
                    (lat_a, lon_a),
                    (lat_b, lon_b),
                    self.polygon_width_ft.get()
                )
                logger.info(f"Updated polygon with {len(self.polygon_points)} points")
            except Exception as e:
                logger.error(f"Error updating polygon: {e}", exc_info=True)

    def center_map_on_path(self):
        """Center the map on the path between donor and recipient sites"""
        try:
            if not self.map_widget:
                logger.warning("No map widget available")
                return

            if not hasattr(self, 'donor_site') or not hasattr(self, 'recipient_site'):
                logger.warning("No donor or recipient site defined")
                return

            if not self.donor_site or not self.recipient_site:
                logger.warning("Donor or recipient site is None")
                return

            # Get coordinates
            lat_a, lon_a = convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
            lat_b, lon_b = convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])

            # Calculate center point
            center_lat = (lat_a + lat_b) / 2
            center_lon = (lon_a + lon_b) / 2

            # Center map
            self.map_widget.set_position(center_lat, center_lon)

            # Calculate appropriate zoom level based on distance
            # This is a simple heuristic - adjust as needed
            import math
            lat_diff = abs(lat_a - lat_b)
            lon_diff = abs(lon_a - lon_b)
            max_diff = max(lat_diff, lon_diff)

            # Simple logarithmic scale for zoom
            if max_diff > 0:
                zoom = max(1, min(19, int(math.log(1.0 / max_diff) * 1.5)))
                self.map_widget.set_zoom(zoom)
            else:
                # Default zoom if points are very close
                self.map_widget.set_zoom(12)

            logger.info(f"Centered map at {center_lat}, {center_lon} with zoom {self.map_widget.zoom}")
        except Exception as e:
            logger.error(f"Error centering map on path: {e}", exc_info=True)

    def _on_width_change(self, *args):
        """Update the polygon when the width changes"""
        try:
            if hasattr(self, 'donor_site') and hasattr(self, 'recipient_site'):
                if self.donor_site and self.recipient_site:
                    # Update polygon with new width
                    lat_a, lon_a = convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
                    lat_b, lon_b = convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])

                    width_ft = self.polygon_width_ft.get()
                    logger.info(f"Width changed to {width_ft} ft, updating polygon")

                    self.polygon_points = calculate_polygon_points(
                        (lat_a, lon_a),
                        (lat_b, lon_b),
                        width_ft
                    )

                    # Update map display
                    if self.map_widget:
                        # Remove existing polygon if any
                        for polygon in self.map_widget.canvas.find_withtag("LOS Polygon"):
                            self.map_widget.canvas.delete(polygon)

                        # Draw new polygon
                        self.map_widget.set_polygon(
                            self.polygon_points,
                            fill_color=None,
                            outline_color="black",
                            border_width=1,
                            name="LOS Polygon"
                        )
        except Exception as e:
            logger.error(f"Error updating polygon width: {e}", exc_info=True)

    def clear_all_data(self):
        """Clear all data including LIDAR and turbines"""
        logger.info("Clearing all data")
        try:
            # Clear LIDAR display
            self.clear_lidar_display()

            # Clear turbines
            if hasattr(self, 'turbine_processor'):
                self.turbine_processor.clear_turbines()
                self.last_turbines = []

            # Clear project data
            self.projects = {}
            if hasattr(self, 'project_metadata'):
                self.project_metadata.projects = {}

            # Update UI
            if hasattr(self, 'project_dropdown'):
                self.project_dropdown.configure(values=["Overview"])
                self.project_var.set("Overview")

            # Clear tree
            if hasattr(self, 'tree'):
                for item in self.tree.get_children():
                    self.tree.delete(item)

            # Clear download queue
            if hasattr(self, 'downloader') and self.downloader:
                try:
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
                except Exception as e:
                    logger.error(f"Error clearing download queue: {e}", exc_info=True)

            logger.info("All data cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing all data: {e}", exc_info=True)

    def clear_lidar_display(self):
        """Clear LIDAR display from the map"""
        logger.info("Clearing LIDAR display")
        try:
            # Clear polygons from map
            if self.map_widget:
                for polygon in self.lidar_polygons:
                    try:
                        self.map_widget.canvas.delete(polygon)
                    except Exception as e:
                        logger.warning(f"Error deleting polygon: {e}")

            # Clear legend
            if hasattr(self, 'legend_items_frame') and self.legend_items_frame:
                for widget in self.legend_items_frame.winfo_children():
                    widget.destroy()

                # Add "No LIDAR data" label
                ttk.Label(
                    self.legend_items_frame,
                    text="No LIDAR data loaded",
                    foreground="gray"
                ).pack(anchor="w", padx=5, pady=2)

                # Update scroll region
                if hasattr(self, 'legend_canvas') and self.legend_canvas:
                    self.legend_canvas.configure(scrollregion=self.legend_canvas.bbox("all"))

            # Reset variables
            self.lidar_polygons = []
            self.used_colors = set()

            logger.info("LIDAR display cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing LIDAR display: {e}", exc_info=True)

    def find_turbines(self):
        """Search for wind turbines within the LIDAR path area"""
        logger.info("Searching for turbines")
        try:
            # Get the obstruction_text widget from the UI
            obstruction_text = None
            try:
                # This assumes obstruction_text is a global variable
                if 'obstruction_text' in globals():
                    obstruction_text = globals()['obstruction_text']
            except Exception as e:
                logger.warning(f"Could not get obstruction_text widget: {e}")

            # Call the turbine processor with all necessary info
            return self.turbine_processor.find_turbines(
                self.polygon_points,
                self.donor_site,
                self.recipient_site,
                obstruction_text
            )
        except Exception as e:
            logger.error(f"Error finding turbines: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to find turbines: {str(e)}")
            return None

    def find_state_turbines(self):
        """Search for state wind turbines within the LIDAR path area"""
        logger.info("Searching for state turbines")
        try:
            # Get the obstruction_text widget from the UI
            obstruction_text = None
            try:
                # This assumes obstruction_text is a global variable
                if 'obstruction_text' in globals():
                    obstruction_text = globals()['obstruction_text']
            except Exception as e:
                logger.warning(f"Could not get obstruction_text widget: {e}")

            # Call the turbine processor with all necessary info
            return self.turbine_processor.find_state_turbines(
                self.polygon_points,
                self.donor_site,
                self.recipient_site,
                obstruction_text
            )
        except Exception as e:
            logger.error(f"Error finding state turbines: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to find state turbines: {str(e)}")
            return None

    def toggle_turbine_labels(self):
        """Toggle the visibility of turbine labels"""
        try:
            show_labels = self.show_turbine_labels.get()
            logger.info(f"Toggling turbine labels to {'visible' if show_labels else 'hidden'}")

            # Update labels in turbine processor
            if hasattr(self, 'turbine_processor'):
                self.turbine_processor.toggle_labels(show_labels)

            logger.info("Turbine labels toggled successfully")
        except Exception as e:
            logger.error(f"Error toggling turbine labels: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to toggle turbine labels: {str(e)}")

    def export_map_view(self):
        """Export the current map view as an image"""
        logger.info("Exporting map view")
        try:
            from utilities.certificate_generator import export_map_view as export_map

            # Call the export function
            export_map(self.map_widget, self.root)

            logger.info("Map view exported successfully")
        except Exception as e:
            logger.error(f"Error exporting map view: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export map view: {str(e)}")

    def export_search_polygon_as_kml(self):
        """Export the search polygon as a KML file"""
        logger.info("Exporting search polygon as KML")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Get site IDs if available
            site_a_id = self.donor_site.get('site_id') if hasattr(self, 'donor_site') and self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if hasattr(self, 'recipient_site') and self.recipient_site else None

            # Generate filename
            filename = "search_area.kml"
            if site_a_id and site_b_id:
                filename = f"search_area_{site_a_id}_{site_b_id}.kml"

            # Export polygon
            export_polygon_as_kml(self.polygon_points, filename)

            logger.info(f"Search polygon exported as KML: {filename}")
            messagebox.showinfo("Export Successful", f"Search polygon exported as {filename}")
        except Exception as e:
            logger.error(f"Error exporting search polygon as KML: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search polygon as KML: {str(e)}")

    def export_search_polygon_as_shapefile(self):
        """Export the search polygon as a shapefile"""
        logger.info("Exporting search polygon as shapefile")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Get site IDs if available
            site_a_id = self.donor_site.get('site_id') if hasattr(self, 'donor_site') and self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if hasattr(self, 'recipient_site') and self.recipient_site else None

            # Generate filename
            filename = "search_area.shp"
            if site_a_id and site_b_id:
                filename = f"search_area_{site_a_id}_{site_b_id}.shp"

            # Export polygon
            export_polygon_as_shapefile(self.polygon_points, filename)

            logger.info(f"Search polygon exported as shapefile: {filename}")
            messagebox.showinfo("Export Successful", f"Search polygon exported as {filename}")
        except Exception as e:
            logger.error(f"Error exporting search polygon as shapefile: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search polygon as shapefile: {str(e)}")

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

            # Generate base filename
            base_filename = "search_area"
            if site_a_id and site_b_id:
                base_filename = f"search_area_{site_a_id}_{site_b_id}"

            # Export polygon in multiple formats
            export_polygon(self.polygon_points, base_filename)

            logger.info(f"Search polygon exported in multiple formats: {base_filename}.*")
            messagebox.showinfo("Export Successful", f"Search polygon exported in multiple formats")
        except Exception as e:
            logger.error(f"Error exporting search polygon: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search polygon: {str(e)}")

    def export_rings_for_sites(self):
        """Export search rings for the current sites"""
        logger.info("Exporting search rings for sites")
        try:
            # Check if we have site data
            if not hasattr(self, 'donor_site') or not hasattr(self, 'recipient_site'):
                messagebox.showwarning("Warning", "No site data available")
                return

            if not self.donor_site or not self.recipient_site:
                messagebox.showwarning("Warning", "No site data available")
                return

            # Get site data
            site_a = self.donor_site
            site_b = self.recipient_site

            # Ask for save directory
            save_dir = filedialog.askdirectory(title="Select directory to save search rings")
            if not save_dir:
                logger.info("Export cancelled - no directory selected")
                return

            # Export search rings
            from utilities.search_rings import SearchRingGenerator

            logger.info(f"Saving search rings to directory: {save_dir}")

            # Initialize search ring generator
            ring_gen = SearchRingGenerator(self.project_metadata)

            # Export for donor site
            if site_a:
                logger.info(f"Exporting search rings for donor site: {site_a.get('site_id')}")
                ring_gen.export_search_rings(site_a, save_dir, is_donor=True)

            # Export for recipient site
            if site_b:
                logger.info(f"Exporting search rings for recipient site: {site_b.get('site_id')}")
                ring_gen.export_search_rings(site_b, save_dir, is_donor=False)

            logger.info("Search rings exported successfully")
            messagebox.showinfo("Export Successful", f"Search rings exported to {save_dir}")
        except Exception as e:
            logger.error(f"Error exporting search rings: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export search rings: {str(e)}")

    # Core UI functionality methods

    def search_lidar(self):
        """Search for LIDAR data"""
        logger.info("Searching for LIDAR data")
        # Implementation would go here

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

            # Show progress dialog
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Searching Towers")
            progress_window.geometry("400x150")
            progress_window.transient(self.root)
            progress_window.grab_set()

            # Add progress message
            message_label = ttk.Label(progress_window, text="Searching for towers within the polygon...")
            message_label.pack(pady=10)

            # Add progress bar
            progress_bar = ttk.Progressbar(progress_window, mode="indeterminate")
            progress_bar.pack(fill="x", padx=20, pady=10)
            progress_bar.start(10)

            # Add cancel button
            cancel_button = ttk.Button(progress_window, text="Cancel", command=progress_window.destroy)
            cancel_button.pack(pady=10)

            # Update UI
            self.root.update()

            # Define a function to run the search in a separate thread
            def search_thread():
                try:
                    # Convert polygon points to (lon, lat) format for search
                    search_polygon = [(point[1], point[0]) for point in self.polygon_points]

                    # Search for towers
                    towers = search_towers_in_polygon(search_polygon)

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
        """Display tower search results on the map"""
        try:
            # Close progress window
            progress_window.destroy()

            # Check if we found any towers
            if not towers:
                messagebox.showinfo("Tower Search", "No towers found within the search area.")
                return

            # Display towers on map
            if self.map_widget:
                # Clear any existing tower markers
                for marker in self.map_widget.canvas.find_withtag("Tower Marker"):
                    self.map_widget.canvas.delete(marker)

                # Add tower markers
                for tower in towers:
                    # Get tower data
                    lat = tower.get('decimal_latitude')
                    lon = tower.get('decimal_longitude')
                    height = tower.get('overall_height_ground')
                    tower_id = tower.get('unique_system_id')
                    structure_type = tower.get('structure_type', 'Unknown')

                    if lat is not None and lon is not None:
                        # Create marker
                        marker = self.map_widget.set_marker(
                            lat, lon,
                            text="T",
                            marker_color_circle="red",
                            marker_color_outside="black",
                            font="Arial 8 bold",
                            text_color="white",
                            command=lambda t=tower: self._show_tower_info(t)
                        )

                        # Add tag to identify tower markers
                        self.map_widget.canvas.itemconfig(marker, tags=("Tower Marker", f"Tower_{tower_id}"))

            # Show message with count
            messagebox.showinfo("Tower Search", f"Found {len(towers)} towers within the search area.")

        except Exception as e:
            logger.error(f"Error displaying tower results: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to display tower results: {str(e)}")

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
            info_window.title(f"Tower Information - ID: {tower.get('unique_system_id')}")
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
            row = 0

            # Add header
            ttk.Label(scrollable_frame, text="Tower Information", font=("Arial", 12, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=5, pady=5)
            row += 1

            # Add basic information
            ttk.Label(scrollable_frame, text="Registration Number:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('registration_number', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Structure Type:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('structure_type', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Height (ft):", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=f"{tower.get('overall_height_ground', 'N/A')}").grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Ground Elevation (ft):", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=f"{tower.get('ground_elevation', 'N/A')}").grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Overall Height AMSL (ft):", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=f"{tower.get('overall_height_amsl', 'N/A')}").grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Latitude:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            lat_str = f"{tower.get('latitude_degrees', 'N/A')}° {tower.get('latitude_minutes', 'N/A')}' {tower.get('latitude_seconds', 'N/A')}\" {tower.get('latitude_direction', '')}"
            ttk.Label(scrollable_frame, text=lat_str).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Longitude:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            lon_str = f"{tower.get('longitude_degrees', 'N/A')}° {tower.get('longitude_minutes', 'N/A')}' {tower.get('longitude_seconds', 'N/A')}\" {tower.get('longitude_direction', '')}"
            ttk.Label(scrollable_frame, text=lon_str).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Decimal Coordinates:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            coord_str = f"{tower.get('decimal_latitude', 'N/A')}, {tower.get('decimal_longitude', 'N/A')}"
            ttk.Label(scrollable_frame, text=coord_str).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            # Add location information
            ttk.Label(scrollable_frame, text="Location Information", font=("Arial", 12, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(15, 5))
            row += 1

            ttk.Label(scrollable_frame, text="Street Address:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('structure_street', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="City:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('structure_city', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="State:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('structure_state', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="ZIP Code:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('zip_code', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            # Add FAA information
            ttk.Label(scrollable_frame, text="FAA Information", font=("Arial", 12, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(15, 5))
            row += 1

            ttk.Label(scrollable_frame, text="FAA Study Number:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('faa_study_number', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="FAA Determination Date:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('date_faa_determination', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Painting and Lighting:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('painting_and_lighting', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            # Add dates information
            ttk.Label(scrollable_frame, text="Dates", font=("Arial", 12, "bold")).grid(
                row=row, column=0, columnspan=2, sticky="w", padx=5, pady=(15, 5))
            row += 1

            ttk.Label(scrollable_frame, text="Date Constructed:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('date_constructed', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            ttk.Label(scrollable_frame, text="Date Issued:", font=("Arial", 10, "bold")).grid(
                row=row, column=0, sticky="w", padx=5, pady=2)
            ttk.Label(scrollable_frame, text=tower.get('date_issued', 'N/A')).grid(
                row=row, column=1, sticky="w", padx=5, pady=2)
            row += 1

            # Add close button
            ttk.Button(info_window, text="Close", command=info_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error showing tower info: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to show tower information: {str(e)}")

    def add_all_files_to_download(self):
        """Add all files to download"""
        logger.info("Adding all files to download")
        # Implementation would go here

    def on_project_change(self, event):
        """Handle project change"""
        logger.info(f"Project changed to {self.project_var.get()}")
        # Implementation would go here

    def _view_on_map(self):
        """View project on map"""
        logger.info("Viewing project on map")
        # Implementation would go here

    def add_project_files_to_download(self):
        """Add project files to download"""
        logger.info("Adding project files to download")
        # Implementation would go here

    def select_all_files(self):
        """Select all files"""
        logger.info("Selecting all files")
        # Implementation would go here

    def deselect_all_files(self):
        """Deselect all files"""
        logger.info("Deselecting all files")
        # Implementation would go here

    def add_selected_to_downloads(self):
        """Add selected files to downloads"""
        logger.info("Adding selected files to downloads")
        # Implementation would go here

    def write_project_metadata(self):
        """Write project metadata"""
        logger.info("Writing project metadata")
        # Implementation would go here

    def export_certificates(self, format_type=None):
        """Export certificates"""
        logger.info(f"Exporting certificates (format: {format_type})")
        # Implementation would go here

    def export_search_rings(self):
        """Export search rings"""
        logger.info("Exporting search rings")
        # Implementation would go here

    def refresh_metadata(self):
        """Refresh metadata"""
        logger.info("Refreshing metadata")
        # Implementation would go here
