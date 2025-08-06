import tkinter as tk
from tkinter import ttk
import logging
import tkinter.messagebox as messagebox
import json
import webbrowser

logger = logging.getLogger(__name__)

class ProjectDetailsPane:
    """Class to display LIDAR project details"""
    def __init__(self, master, lidar_downloader, metadata):
        self.master = master
        self.lidar_downloader = lidar_downloader
        self.metadata = metadata

        # Create main frame
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill="x", expand=False)

        # Create project selection frame
        self.selection_frame = ttk.Frame(self.main_frame)
        self.selection_frame.pack(fill="x", padx=5, pady=2)

        # Add project selection combobox
        ttk.Label(self.selection_frame, text="Select Project:").pack(side="left", padx=5)
        self.project_combobox = ttk.Combobox(self.selection_frame, state="readonly", width=50)
        self.project_combobox.pack(side="left", padx=5)

        # Add "Add to Downloads" button
        ttk.Button(self.selection_frame,
                  text="Add Project Files to Download",
                  command=self._add_project_to_downloads).pack(side="right", padx=5)

        # Add "View on Map" button
        ttk.Button(self.selection_frame,
                  text="View on Map",
                  command=self._view_on_map).pack(side="right", padx=5)

        # Create overview frame with scrolling
        self.overview_frame = ttk.Frame(self.main_frame)
        self.overview_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Create text widget with scrollbar
        self.overview_text = tk.Text(self.overview_frame, wrap=tk.WORD, padx=5, pady=5)
        text_scrollbar = ttk.Scrollbar(self.overview_frame, orient="vertical",
                                     command=self.overview_text.yview)
        self.overview_text.configure(yscrollcommand=text_scrollbar.set)

        # Configure tags for formatting
        self.overview_text.tag_configure("title", font=("Arial", 12, "bold"), foreground="#003366")
        self.overview_text.tag_configure("section", font=("Arial", 10, "bold"), foreground="#006699")
        self.overview_text.tag_configure("subsection", font=("Arial", 9, "bold"), foreground="#0099CC")
        self.overview_text.tag_configure("data", font=("Arial", 10))
        self.overview_text.tag_configure("highlight", font=("Arial", 10, "bold"), foreground="#CC6600")
        self.overview_text.tag_configure("url", font=("Arial", 10, "underline"), foreground="blue")
        self.overview_text.tag_configure("warning", font=("Arial", 10, "italic"), foreground="red")
        self.overview_text.tag_configure("success", font=("Arial", 10), foreground="green")
        self.overview_text.tag_configure("date", font=("Arial", 11, "bold"), foreground="red")

        # Pack text widget and its scrollbar
        text_scrollbar.pack(side="right", fill="y")
        self.overview_text.pack(side="left", fill="both", expand=True)

        # Add initial overview text
        self.overview_text.configure(state="normal")
        self.overview_text.delete(1.0, tk.END)
        self.overview_text.insert(tk.END, "LIDAR Project Overview\n", "title")
        self.overview_text.insert(tk.END, "=" * 50 + "\n\n")
        self.overview_text.insert(tk.END, "Select a project to view details.\n", "data")
        self.overview_text.configure(state="disabled")

        # Create notebook for project tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill="both", expand=True, padx=2, pady=2)

        # Initialize project tabs dictionary
        self.project_tabs = {}

        # Bind selection event
        self.project_combobox.bind('<<ComboboxSelected>>', self._on_project_selected)

        # Update project list
        self._update_project_list()

    def _update_project_list(self):
        """Update the project combobox with available projects"""
        try:
            import logging
            import tkinter as tk
            logger = logging.getLogger(__name__)
            logger.info("Starting _update_project_list")

            # Thread safety check - ensure we're in the main thread
            try:
                # Attempt to access the main thread's Tcl interpreter
                if hasattr(self, 'master') and self.master:
                    self.master.tk.call('info', 'exists', 'tcl_version')
                elif hasattr(self, 'project_combobox') and self.project_combobox:
                    self.project_combobox.tk.call('info', 'exists', 'tcl_version')
            except RuntimeError as e:
                logger.error(f"Thread safety check failed - not in main thread: {e}")
                return  # Exit silently if not in main thread
            except Exception as e:
                logger.warning(f"Thread safety check inconclusive: {e}")
                # Continue but be extra careful

            # Get list of projects safely
            project_keys = []
            if hasattr(self, 'metadata') and self.metadata:
                logger.info(f"Metadata exists with {len(self.metadata.projects)} projects")
                project_keys = list(self.metadata.projects.keys())
                logger.info(f"Project keys: {project_keys}")
            else:
                logger.warning("Metadata object is missing or empty")

            projects = ["Overview"] + sorted(project_keys)
            logger.info(f"Combined project list: {projects}")

            # Update combobox values safely with additional checks
            try:
                if hasattr(self, 'project_combobox') and self.project_combobox:
                    # Additional check that the widget still exists and is valid
                    if self.project_combobox.winfo_exists():
                        logger.info("Updating project_combobox values")
                        self.project_combobox['values'] = projects
                        if projects:
                            self.project_combobox.set("Overview")
                            logger.info("Set combobox to 'Overview'")
                    else:
                        logger.warning("project_combobox widget no longer exists")
                else:
                    logger.warning("project_combobox is missing or invalid")
            except tk.TclError as e:
                logger.error(f"TclError updating combobox: {e}")
                return
            except Exception as e:
                logger.error(f"Error updating combobox: {e}")
                return

            # Count tiles per project for the overview
            project_items = {}
            try:
                if hasattr(self, 'lidar_downloader') and self.lidar_downloader:
                    logger.info("lidar_downloader exists")
                    # Check if file_list exists and is initialized
                    if (hasattr(self.lidar_downloader, 'file_list') and
                        self.lidar_downloader.file_list and
                        hasattr(self.lidar_downloader.file_list, 'get_children')):

                        logger.info("file_list exists, processing items")
                        try:
                            # Check if the file_list widget still exists before accessing it
                            if self.lidar_downloader.file_list.winfo_exists():
                                children = self.lidar_downloader.file_list.get_children()
                                logger.info(f"Found {len(children)} items in file_list")
                                for item in children:
                                    values = self.lidar_downloader.file_list.item(item)['values']
                                    if len(values) > 0 and values[-1] != "":
                                        project_name = values[-1]
                                        if project_name not in project_items:
                                            project_items[project_name] = []
                                        project_items[project_name].append(item)
                                logger.info(f"Processed items into {len(project_items)} projects")
                            else:
                                logger.warning("file_list widget no longer exists")
                        except tk.TclError as e:
                            logger.error(f"TclError accessing file_list: {e}")
                        except Exception as e:
                            logger.error(f"Error processing file list items: {e}", exc_info=True)
                    else:
                        # This is normal during initialization, so just log at debug level
                        logger.debug("file_list is not yet initialized")
                else:
                    logger.warning("lidar_downloader is missing or invalid")
            except Exception as e:
                logger.error(f"Error processing project items: {e}", exc_info=True)

            # Update overview tab safely
            try:
                if hasattr(self, 'update_overview_tab'):
                    logger.info("Calling update_overview_tab")
                    self.update_overview_tab(project_items)
                    logger.info("Completed update_overview_tab")
                else:
                    logger.warning("update_overview_tab method is missing")
            except tk.TclError as e:
                logger.error(f"TclError in update_overview_tab: {e}")
            except Exception as e:
                logger.error(f"Error in update_overview_tab: {e}", exc_info=True)

            logger.info("Successfully completed _update_project_list")

        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            # Don't log full stack trace for thread safety errors - they're expected during shutdown
            if "main thread is not in main loop" in str(e) or "RuntimeError" in str(type(e).__name__):
                logger.warning(f"Threading issue in project list update: {e}")
            else:
                logger.error(f"Error updating project list: {e}", exc_info=True)

    def _on_project_selected(self, _):
        """Handle project selection"""
        selected = self.project_combobox.get()

        try:
            self.overview_text.configure(state="normal")
            self.overview_text.delete(1.0, tk.END)

            if not selected or selected == "Overview":
                self.update_overview_tab({})
                return

            # Get project metadata
            metadata = self.metadata.get_project(selected)
            if not metadata:
                logger.warning(f"No metadata found for project: {selected}")
                self.overview_text.insert(tk.END, f"No details available for project: {selected}\n", "data")
                self.overview_text.configure(state="disabled")
                return

            # Project Title
            self.overview_text.insert(tk.END, f"Project Details: {metadata.get('title', selected)}\n", "title")
            self.overview_text.insert(tk.END, "=" * 50 + "\n\n")

            # Count files for this project - MOVED UP as requested
            file_count = 0
            if hasattr(self.lidar_downloader, 'file_list'):
                for item in self.lidar_downloader.file_list.get_children():
                    values = self.lidar_downloader.file_list.item(item)['values']
                    if len(values) > 0 and values[-1] == selected:
                        file_count += 1

            self.overview_text.insert(tk.END, "• Files Available: ", "data")
            self.overview_text.insert(tk.END, f"{file_count}\n\n", "data")

            # Extract project year from name for fallback
            project_year = None
            for part in selected.split('_'):
                if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                    project_year = part
                    break

            # Dates - Display prominently at the top with red text
            dates = metadata.get('dates', {})

            # If dates are missing but we have a project year, add it
            if project_year and (dates.get('Start', 'N/A') == 'N/A' or dates.get('End', 'N/A') == 'N/A'):
                if 'dates' not in metadata:
                    metadata['dates'] = {}
                if dates.get('Start', 'N/A') == 'N/A':
                    metadata['dates']['Start'] = f"{project_year}-01-01"
                if dates.get('End', 'N/A') == 'N/A':
                    metadata['dates']['End'] = f"{project_year}-12-31"
                dates = metadata['dates']
                logger.info(f"Added dates from project year: {project_year}")

            # Add date section header
            self.overview_text.insert(tk.END, "PROJECT DATES\n", "section")

            # Display collection dates
            start_date = dates.get('Start', 'N/A')
            end_date = dates.get('End', 'N/A')
            pub_date = dates.get('Publication', 'N/A')

            if start_date != 'N/A' or end_date != 'N/A':
                self.overview_text.insert(tk.END, "• Collection Period: ", "highlight")
                if start_date != 'N/A' and end_date != 'N/A':
                    # Extract years for red highlighting
                    start_year = start_date.split('-')[0] if '-' in start_date else start_date
                    end_year = end_date.split('-')[0] if '-' in end_date else end_date

                    # Insert with red years
                    self.overview_text.insert(tk.END, f"{start_year}", "date")
                    self.overview_text.insert(tk.END, f"{start_date[len(start_year):]} to ", "highlight")
                    self.overview_text.insert(tk.END, f"{end_year}", "date")
                    self.overview_text.insert(tk.END, f"{end_date[len(end_year):]}\n", "highlight")
                elif start_date != 'N/A':
                    # Extract year for red highlighting
                    start_year = start_date.split('-')[0] if '-' in start_date else start_date

                    # Insert with red year
                    self.overview_text.insert(tk.END, "Started ", "highlight")
                    self.overview_text.insert(tk.END, f"{start_year}", "date")
                    self.overview_text.insert(tk.END, f"{start_date[len(start_year):]}\n", "highlight")
                elif end_date != 'N/A':
                    # Extract year for red highlighting
                    end_year = end_date.split('-')[0] if '-' in end_date else end_date

                    # Insert with red year
                    self.overview_text.insert(tk.END, "Completed ", "highlight")
                    self.overview_text.insert(tk.END, f"{end_year}", "date")
                    self.overview_text.insert(tk.END, f"{end_date[len(end_year):]}\n", "highlight")
            else:
                # If we have a project year but no dates, display it
                if project_year:
                    self.overview_text.insert(tk.END, "• Project Year: ", "highlight")
                    self.overview_text.insert(tk.END, f"{project_year}\n", "date")
                else:
                    self.overview_text.insert(tk.END, "• Collection Period: Not available\n", "warning")

            # Display publication date
            if pub_date != 'N/A':
                self.overview_text.insert(tk.END, "• Publication Date: ", "highlight")
                # Extract year for red highlighting
                pub_year = pub_date.split('-')[0] if '-' in pub_date else pub_date

                # Insert with red year
                self.overview_text.insert(tk.END, f"{pub_year}", "date")
                self.overview_text.insert(tk.END, f"{pub_date[len(pub_year):]}\n", "highlight")

            self.overview_text.insert(tk.END, "\n", "data")

            # Dates section already added at the top

            # Coordinate System - MOVED UP as requested
            coord_system = metadata.get('spatial_ref', {}).get('coordinate_system', {})
            if coord_system:
                self.overview_text.insert(tk.END, "Coordinate System\n", "section")

                if coord_system.get('name', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Name: ", "data")
                    self.overview_text.insert(tk.END, f"{coord_system.get('name')}\n", "data")

                if coord_system.get('type', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Type: ", "data")
                    self.overview_text.insert(tk.END, f"{coord_system.get('type')}\n", "data")

                if coord_system.get('epsg_code', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• EPSG Code: ", "data")
                    self.overview_text.insert(tk.END, f"{coord_system.get('epsg_code')}\n", "data")

                if coord_system.get('units', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Units: ", "data")
                    self.overview_text.insert(tk.END, f"{coord_system.get('units')}\n", "data")

                # Projection Parameters
                parameters = coord_system.get('parameters', {})
                if parameters:
                    self.overview_text.insert(tk.END, "\nProjection Parameters:\n", "subsection")

                    # UTM Parameters
                    if coord_system.get('type') == 'utm':
                        if parameters.get('zone', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• Zone: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('zone')}\n", "data")

                        if parameters.get('hemisphere', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• Hemisphere: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('hemisphere')}\n", "data")

                        if parameters.get('scale_factor', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• Scale Factor: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('scale_factor')}\n", "data")

                        if parameters.get('central_meridian', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• Central Meridian: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('central_meridian')}°\n", "data")

                        if parameters.get('latitude_of_origin', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• Latitude of Origin: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('latitude_of_origin')}°\n", "data")

                        if parameters.get('false_easting', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• False Easting: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('false_easting')} meters\n", "data")

                        if parameters.get('false_northing', 'N/A') != 'N/A':
                            self.overview_text.insert(tk.END, "• False Northing: ", "data")
                            self.overview_text.insert(tk.END, f"{parameters.get('false_northing')} meters\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Datum Information - MOVED UP as requested
            datum = metadata.get('spatial_ref', {}).get('datum', {})
            if datum:
                self.overview_text.insert(tk.END, "Datum Information\n", "section")

                if datum.get('horizontal_datum', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Horizontal Datum: ", "data")
                    self.overview_text.insert(tk.END, f"{datum.get('horizontal_datum')}\n", "data")

                if datum.get('vertical_datum', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Vertical Datum: ", "data")
                    self.overview_text.insert(tk.END, f"{datum.get('vertical_datum')}\n", "data")

                if datum.get('ellipsoid', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Ellipsoid: ", "data")
                    self.overview_text.insert(tk.END, f"{datum.get('ellipsoid')}\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Vertical information - MOVED UP as related to units
            vertical = metadata.get('vertical', {})
            if vertical:
                vert_units = vertical.get('units', 'N/A')
                vert_resolution = vertical.get('resolution', 'N/A')

                if vert_units != 'N/A':
                    self.overview_text.insert(tk.END, "• Vertical Units: ", "data")
                    self.overview_text.insert(tk.END, f"{vert_units}\n", "data")

                if vert_resolution != 'N/A':
                    self.overview_text.insert(tk.END, "• Vertical Resolution: ", "data")
                    self.overview_text.insert(tk.END, f"{vert_resolution}\n", "data")

            # Location Information
            state = metadata.get('state', 'N/A')
            region = metadata.get('region', 'N/A')
            if state != 'N/A' or region != 'N/A':
                self.overview_text.insert(tk.END, "Location Information\n", "section")
                if state != 'N/A':
                    self.overview_text.insert(tk.END, "• State: ", "data")
                    self.overview_text.insert(tk.END, f"{state}\n", "data")
                if region != 'N/A':
                    self.overview_text.insert(tk.END, "• Region: ", "data")
                    self.overview_text.insert(tk.END, f"{region}\n", "data")

                # Place Keywords
                place_keywords = metadata.get('place_keywords', [])
                if place_keywords:
                    self.overview_text.insert(tk.END, "• Place Keywords: ", "data")
                    self.overview_text.insert(tk.END, f"{', '.join(place_keywords)}\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Collection Information
            collection = metadata.get('collection_parameters', {})
            if collection:
                self.overview_text.insert(tk.END, "Collection Information\n", "section")

                if collection.get('type', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Type: ", "data")
                    self.overview_text.insert(tk.END, f"{collection.get('type')}\n", "data")

                if collection.get('platform', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Platform: ", "data")
                    self.overview_text.insert(tk.END, f"{collection.get('platform')}\n", "data")

                if collection.get('sensor', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Sensor: ", "data")
                    self.overview_text.insert(tk.END, f"{collection.get('sensor')}\n", "data")

                if collection.get('flying_height', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Flying Height: ", "data")
                    self.overview_text.insert(tk.END, f"{collection.get('flying_height')}\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Format Information
            format_info = metadata.get('format', {})
            if format_info:
                self.overview_text.insert(tk.END, "Format Information\n", "section")

                if format_info.get('name', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Format: ", "data")
                    self.overview_text.insert(tk.END, f"{format_info.get('name')}\n", "data")

                if format_info.get('version', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Version: ", "data")
                    self.overview_text.insert(tk.END, f"{format_info.get('version')}\n", "data")

                if format_info.get('size_mb', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Size: ", "data")
                    size_str = f"{format_info.get('size_mb'):.2f} MB"
                    if format_info.get('size_bytes', 'N/A') != 'N/A':
                        size_str += f" ({format_info.get('size_bytes'):,} bytes)"
                    self.overview_text.insert(tk.END, f"{size_str}\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Coverage
            bounds = metadata.get('bounds', {})
            if bounds:
                self.overview_text.insert(tk.END, "Coverage Area\n", "section")

                if bounds.get('maxY', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• North: ", "data")
                    self.overview_text.insert(tk.END, f"{bounds.get('maxY')}°\n", "data")

                if bounds.get('minY', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• South: ", "data")
                    self.overview_text.insert(tk.END, f"{bounds.get('minY')}°\n", "data")

                if bounds.get('maxX', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• East: ", "data")
                    self.overview_text.insert(tk.END, f"{bounds.get('maxX')}°\n", "data")

                if bounds.get('minX', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• West: ", "data")
                    self.overview_text.insert(tk.END, f"{bounds.get('minX')}°\n", "data")

                # Add calculated values
                if all(k in bounds for k in ['minX', 'maxX', 'minY', 'maxY']):
                    width = bounds.get('maxX', 0) - bounds.get('minX', 0)
                    height = bounds.get('maxY', 0) - bounds.get('minY', 0)
                    self.overview_text.insert(tk.END, "• Width: ", "data")
                    self.overview_text.insert(tk.END, f"{width:.6f}°\n", "data")
                    self.overview_text.insert(tk.END, "• Height: ", "data")
                    self.overview_text.insert(tk.END, f"{height:.6f}°\n", "data")

                # Add center coordinates
                center = metadata.get('center_coordinates', {})
                if center and 'latitude' in center and 'longitude' in center:
                    self.overview_text.insert(tk.END, "\nCenter Coordinates:\n", "subsection")
                    self.overview_text.insert(tk.END, "• Latitude: ", "data")
                    self.overview_text.insert(tk.END, f"{center.get('latitude')}°\n", "data")
                    self.overview_text.insert(tk.END, "• Longitude: ", "data")
                    self.overview_text.insert(tk.END, f"{center.get('longitude')}°\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # Quality Information
            quality = metadata.get('quality', {})
            if quality:
                self.overview_text.insert(tk.END, "Quality Information\n", "section")

                if quality.get('vertical_accuracy', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Vertical Accuracy: ", "data")
                    self.overview_text.insert(tk.END, f"{quality.get('vertical_accuracy')}\n", "data")

                if quality.get('logical_consistency', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Logical Consistency: ", "data")
                    self.overview_text.insert(tk.END, f"{quality.get('logical_consistency')}\n", "data")

                if quality.get('completeness', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Completeness: ", "data")
                    self.overview_text.insert(tk.END, f"{quality.get('completeness')}\n", "data")

                self.overview_text.insert(tk.END, "\n")

            # URLs and File Paths
            self.overview_text.insert(tk.END, "URLs and File Paths\n", "section")

            if metadata.get('download_url', 'N/A') != 'N/A':
                self.overview_text.insert(tk.END, "• Download URL: ", "data")
                self.overview_text.insert(tk.END, f"{metadata.get('download_url')}\n", "data")

            # Metadata URLs
            metadata_urls = metadata.get('metadata_urls', {})
            if metadata_urls:
                if metadata_urls.get('json_url', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• JSON URL: ", "data")
                    self.overview_text.insert(tk.END, f"{metadata_urls.get('json_url')}\n", "data")

                if metadata_urls.get('xml_url', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• XML URL: ", "data")
                    self.overview_text.insert(tk.END, f"{metadata_urls.get('xml_url')}\n", "data")

                if metadata_urls.get('meta_url', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Meta URL: ", "data")
                    self.overview_text.insert(tk.END, f"{metadata_urls.get('meta_url')}\n", "data")

            # Additional URLs
            additional_urls = metadata.get('additional_urls', {})
            if additional_urls:
                self.overview_text.insert(tk.END, "\nAdditional URLs:\n", "subsection")
                for url_type, url in additional_urls.items():
                    self.overview_text.insert(tk.END, f"• {url_type.replace('_', ' ').title()}: ", "data")
                    self.overview_text.insert(tk.END, f"{url}\n", "data")

            # Local File Path
            if metadata.get('local_file_path', 'N/A') != 'N/A':
                self.overview_text.insert(tk.END, "\n• Local XML Path: ", "data")
                self.overview_text.insert(tk.END, f"{metadata.get('local_file_path')}\n", "data")

            # Metadata Update Timestamp
            if metadata.get('metadata_updated', 'N/A') != 'N/A':
                self.overview_text.insert(tk.END, "\n• Metadata Last Updated: ", "data")
                self.overview_text.insert(tk.END, f"{metadata.get('metadata_updated')}\n", "data")

            self.overview_text.configure(state="disabled")

        except Exception as e:
            logger.error(f"Error displaying project details: {e}", exc_info=True)
            self.overview_text.insert(tk.END, f"Error displaying project details: {str(e)}\n", "data")
            self.overview_text.configure(state="disabled")

    def _add_project_to_downloads(self):
        """Add selected project's files to download queue"""
        try:
            selected = self.project_combobox.get()

            if not selected or selected == "Overview":
                messagebox.showwarning("No Selection", "Please select a specific project first.")
                return

            # Verify project exists
            if selected not in self.metadata.projects:
                messagebox.showerror("Error", f"Project '{selected}' not found in metadata.")
                return

            # Deselect all files first
            self.lidar_downloader.deselect_all()

            # Select files for the chosen project
            files_added = 0
            total_size = 0

            for item in self.lidar_downloader.file_list.get_children():
                values = self.lidar_downloader.file_list.item(item)['values']
                if len(values) >= 5 and values[4] == selected:  # Project name is in 5th column (index 4)
                    # Update checkbox in the UI
                    self.lidar_downloader.file_list.set(item, "Select", "✓")
                    # Add to selected files set
                    self.lidar_downloader.selected_files.add(item)
                    files_added += 1
                    # Try to parse size if available
                    try:
                        size_str = values[3].replace(' MB', '')
                        total_size += float(size_str)
                    except:
                        pass

            if files_added > 0:
                # Add selected files to download queue
                self.lidar_downloader.add_to_downloads()
                size_msg = f" (Total size: {total_size:.2f} MB)" if total_size > 0 else ""
                project_title = self.metadata.get_project(selected).get('title', selected)
                messagebox.showinfo(
                    "Files Added",
                    f"Added {files_added} LIDAR tiles from project '{project_title}' to download queue{size_msg}.\n\n"
                    f"This represents the complete collection for the project."
                )
                logger.info(f"Added {files_added} tiles from project '{selected}' to download queue")
            else:
                messagebox.showwarning(
                    "No Files",
                    f"No LIDAR tiles found for project '{selected}'. Try searching for LIDAR data first."
                )
                logger.warning(f"No files found for project '{selected}'")

        except Exception as e:
            logger.error(f"Error adding files to download queue: {e}", exc_info=True)
            messagebox.showerror(
                "Error",
                f"An error occurred while adding files to download queue: {str(e)}"
            )

    def update_overview_tab(self, project_items):
        """Update the overview tab with summary information"""
        try:
            # Thread safety check - ensure we're in the main thread
            try:
                if hasattr(self, 'overview_text') and self.overview_text:
                    self.overview_text.tk.call('info', 'exists', 'tcl_version')
            except RuntimeError as e:
                logger.error(f"Thread safety check failed in update_overview_tab - not in main thread: {e}")
                return  # Exit silently if not in main thread
            except Exception as e:
                logger.warning(f"Thread safety check inconclusive in update_overview_tab: {e}")
                # Continue but be extra careful

            # Check if overview_text widget still exists
            if not (hasattr(self, 'overview_text') and self.overview_text and self.overview_text.winfo_exists()):
                logger.warning("overview_text widget is missing or no longer exists")
                return

            self.overview_text.configure(state="normal")
            self.overview_text.delete(1.0, tk.END)

            # Header
            self.overview_text.insert(tk.END, "LIDAR Project Summary\n", "title")
            self.overview_text.insert(tk.END, "=" * 50 + "\n\n")

            if not self.metadata.projects:
                self.overview_text.insert(tk.END, "No LIDAR projects loaded. Use the search function to find available data.\n", "data")
                self.overview_text.configure(state="disabled")
                return

            # Total summary at the top
            total_files = sum(len(items) for items in project_items.values()) if project_items else 0
            if total_files > 0:
                self.overview_text.insert(tk.END, "• Total Projects: ", "data")
                self.overview_text.insert(tk.END, f"{len(self.metadata.projects)}\n", "data")
                self.overview_text.insert(tk.END, "• Total LIDAR Tiles: ", "data")
                self.overview_text.insert(tk.END, f"{total_files}\n", "data")
                self.overview_text.insert(tk.END, "• Average Tiles Per Project: ", "data")
                avg_tiles = total_files / max(1, len(self.metadata.projects))
                self.overview_text.insert(tk.END, f"{avg_tiles:.1f}\n\n", "data")

            # Project summaries
            for project_name in sorted(self.metadata.projects.keys()):
                metadata = self.metadata.get_project(project_name)
                if not metadata:
                    continue

                # Project header
                self.overview_text.insert(tk.END, f"\nProject: {metadata.get('title', project_name)}\n", "section")
                self.overview_text.insert(tk.END, "-" * 50 + "\n")

                # Count files for this project - MOVED UP as requested
                file_count = 0
                if hasattr(self.lidar_downloader, 'file_list'):
                    for item in self.lidar_downloader.file_list.get_children():
                        values = self.lidar_downloader.file_list.item(item)['values']
                        if len(values) > 0 and values[-1] == project_name:
                            file_count += 1

                # If no files found in file_list, check project_items
                if file_count == 0 and project_items and project_name in project_items:
                    file_count = len(project_items[project_name])

                self.overview_text.insert(tk.END, "• LIDAR Tiles in Collection: ", "highlight")
                self.overview_text.insert(tk.END, f"{file_count}\n", "highlight")

                # Dates - MOVED UP as requested
                dates = metadata.get('dates', {})
                if dates:
                    start_date = dates.get('Start', 'N/A')
                    end_date = dates.get('End', 'N/A')
                    pub_date = dates.get('Publication', 'N/A')

                    # Display collection dates prominently
                    if start_date != 'N/A' or end_date != 'N/A':
                        self.overview_text.insert(tk.END, "• Collection Period: ", "highlight")
                        if start_date != 'N/A' and end_date != 'N/A':
                            # Extract years for red highlighting
                            start_year = start_date.split('-')[0] if '-' in start_date else start_date
                            end_year = end_date.split('-')[0] if '-' in end_date else end_date

                            # Insert with red years
                            self.overview_text.insert(tk.END, f"{start_year}", "date")
                            self.overview_text.insert(tk.END, f"{start_date[len(start_year):]} to ", "highlight")
                            self.overview_text.insert(tk.END, f"{end_year}", "date")
                            self.overview_text.insert(tk.END, f"{end_date[len(end_year):]}\n", "highlight")
                        elif start_date != 'N/A':
                            # Extract year for red highlighting
                            start_year = start_date.split('-')[0] if '-' in start_date else start_date

                            # Insert with red year
                            self.overview_text.insert(tk.END, "Started ", "highlight")
                            self.overview_text.insert(tk.END, f"{start_year}", "date")
                            self.overview_text.insert(tk.END, f"{start_date[len(start_year):]}\n", "highlight")
                        elif end_date != 'N/A':
                            # Extract year for red highlighting
                            end_year = end_date.split('-')[0] if '-' in end_date else end_date

                            # Insert with red year
                            self.overview_text.insert(tk.END, "Completed ", "highlight")
                            self.overview_text.insert(tk.END, f"{end_year}", "date")
                            self.overview_text.insert(tk.END, f"{end_date[len(end_year):]}\n", "highlight")
                    else:
                        # Extract project year from name for fallback
                        project_year = None
                        for part in project_name.split('_'):
                            if part.isdigit() and len(part) == 4 and 2000 <= int(part) <= 2100:
                                project_year = part
                                break

                        # If we have a project year but no dates, display it
                        if project_year:
                            self.overview_text.insert(tk.END, "• Project Year: ", "highlight")
                            self.overview_text.insert(tk.END, f"{project_year}\n", "date")

                    # Display publication date
                    if pub_date != 'N/A':
                        self.overview_text.insert(tk.END, "• Publication Date: ", "highlight")
                        # Extract year for red highlighting
                        pub_year = pub_date.split('-')[0] if '-' in pub_date else pub_date

                        # Insert with red year
                        self.overview_text.insert(tk.END, f"{pub_year}", "date")
                        self.overview_text.insert(tk.END, f"{pub_date[len(pub_year):]}\n", "highlight")

                # Coordinate System - MOVED UP as requested
                coord_system = metadata.get('spatial_ref', {}).get('coordinate_system', {})
                if coord_system:
                    cs_name = coord_system.get('name', 'N/A')
                    cs_type = coord_system.get('type', 'N/A')
                    epsg = coord_system.get('epsg_code', 'N/A')
                    units = coord_system.get('units', 'N/A')

                    cs_info = []
                    if cs_name != 'N/A':
                        cs_info.append(cs_name)
                    elif cs_type != 'N/A':
                        if cs_type == 'utm':
                            zone = coord_system.get('parameters', {}).get('zone', '')
                            hemisphere = coord_system.get('parameters', {}).get('hemisphere', '')
                            if zone and hemisphere:
                                cs_info.append(f"UTM Zone {zone}{hemisphere}")
                            else:
                                cs_info.append("UTM")
                        else:
                            cs_info.append(cs_type.upper())

                    if epsg != 'N/A':
                        cs_info.append(f"{epsg}")

                    if cs_info:
                        self.overview_text.insert(tk.END, "• Coordinate System: ", "data")
                        self.overview_text.insert(tk.END, f"{' | '.join(cs_info)}\n", "data")

                    # Units - MOVED UP and separated as requested
                    if units != 'N/A':
                        self.overview_text.insert(tk.END, "• Units: ", "data")
                        self.overview_text.insert(tk.END, f"{units}\n", "data")

                # Datum Information - MOVED UP as requested
                datum = metadata.get('spatial_ref', {}).get('datum', {})
                if datum:
                    h_datum = datum.get('horizontal_datum', 'N/A')
                    v_datum = datum.get('vertical_datum', 'N/A')

                    if h_datum != 'N/A':
                        self.overview_text.insert(tk.END, "• Horizontal Datum: ", "data")
                        self.overview_text.insert(tk.END, f"{h_datum}\n", "data")

                    if v_datum != 'N/A':
                        self.overview_text.insert(tk.END, "• Vertical Datum: ", "data")
                        self.overview_text.insert(tk.END, f"{v_datum}\n", "data")

                # Vertical information - MOVED UP as related to units
                vertical = metadata.get('vertical', {})
                if vertical:
                    vert_units = vertical.get('units', 'N/A')
                    vert_resolution = vertical.get('resolution', 'N/A')

                    if vert_units != 'N/A':
                        self.overview_text.insert(tk.END, "• Vertical Units: ", "data")
                        self.overview_text.insert(tk.END, f"{vert_units}\n", "data")

                    if vert_resolution != 'N/A':
                        self.overview_text.insert(tk.END, "• Vertical Resolution: ", "data")
                        self.overview_text.insert(tk.END, f"{vert_resolution}\n", "data")

                # Location Information
                state = metadata.get('state', 'N/A')
                region = metadata.get('region', 'N/A')
                if state != 'N/A' or region != 'N/A':
                    location_info = []
                    if state != 'N/A':
                        location_info.append(state)
                    if region != 'N/A':
                        location_info.append(region)
                    self.overview_text.insert(tk.END, "• Location: ", "data")
                    self.overview_text.insert(tk.END, f"{', '.join(location_info)}\n", "data")

                # Format Information
                format_info = metadata.get('format', {})
                if format_info:
                    format_name = format_info.get('name', 'N/A')
                    version = format_info.get('version', 'N/A')
                    size_mb = format_info.get('size_mb', 'N/A')

                    format_str = format_name
                    if version != 'N/A':
                        format_str += f" v{version}"
                    if size_mb != 'N/A':
                        format_str += f" ({size_mb:.2f} MB)"

                    self.overview_text.insert(tk.END, "• Format: ", "data")
                    self.overview_text.insert(tk.END, f"{format_str}\n", "data")

                # Coverage
                bounds = metadata.get('bounds', {})
                if bounds and all(k in bounds for k in ['minX', 'maxX', 'minY', 'maxY']):
                    width = bounds.get('maxX', 0) - bounds.get('minX', 0)
                    height = bounds.get('maxY', 0) - bounds.get('minY', 0)
                    self.overview_text.insert(tk.END, "• Coverage Area: ", "data")
                    self.overview_text.insert(tk.END, f"{width:.6f}° × {height:.6f}°\n", "data")

                    # Add center coordinates if available
                    center = metadata.get('center_coordinates', {})
                    if center and 'latitude' in center and 'longitude' in center:
                        self.overview_text.insert(tk.END, "• Center: ", "data")
                        self.overview_text.insert(tk.END,
                            f"{center.get('latitude', 0):.6f}°, {center.get('longitude', 0):.6f}°\n", "data")

                # Quality - Shortened version for overview
                quality = metadata.get('quality', {})
                if quality:
                    v_accuracy = quality.get('vertical_accuracy', 'N/A')
                    if v_accuracy != 'N/A':
                        self.overview_text.insert(tk.END, "• Vertical Accuracy: ", "data")
                        self.overview_text.insert(tk.END, f"{v_accuracy}\n", "data")

                # URLs - Just indicate if available
                metadata_urls = metadata.get('metadata_urls', {})
                if metadata_urls:
                    has_urls = []
                    if metadata_urls.get('xml_url', 'N/A') != 'N/A':
                        has_urls.append("XML")
                    if metadata_urls.get('json_url', 'N/A') != 'N/A':
                        has_urls.append("JSON")

                    if has_urls:
                        self.overview_text.insert(tk.END, "• Metadata Available: ", "data")
                        self.overview_text.insert(tk.END, f"{', '.join(has_urls)}\n", "data")

                # Local file path - Just indicate if available
                if metadata.get('local_file_path', 'N/A') != 'N/A':
                    self.overview_text.insert(tk.END, "• Local XML: ", "data")
                    self.overview_text.insert(tk.END, "Available\n", "data")

                # Last updated timestamp - shortened
                if metadata.get('metadata_updated', 'N/A') != 'N/A':
                    update_time = metadata.get('metadata_updated', 'N/A')
                    # Try to shorten the timestamp to just the date
                    try:
                        if 'T' in update_time:
                            update_time = update_time.split('T')[0]
                    except:
                        pass

                    self.overview_text.insert(tk.END, "• Last Updated: ", "data")
                    self.overview_text.insert(tk.END, f"{update_time}\n", "data")

                self.overview_text.insert(tk.END, "-" * 50 + "\n")

            self.overview_text.configure(state="disabled")

        except tk.TclError as e:
            logger.error(f"TclError in overview tab update: {e}")
        except Exception as e:
            # Don't log full stack trace for thread safety errors - they're expected during shutdown
            if "main thread is not in main loop" in str(e) or "RuntimeError" in str(type(e).__name__):
                logger.warning(f"Threading issue in overview tab update: {e}")
            else:
                logger.error(f"Error updating overview tab: {e}", exc_info=True)

    def update_project_details(self, project_items):
        """Update the project details display with new data"""
        try:
            logger.debug(f"Updating project details with items: {project_items}")

            # Update overview tab first
            self.update_overview_tab(project_items)

            # Update individual project tabs
            for project_name, items in project_items.items():
                text_widget = self.create_project_tab(project_name)
                text_widget.configure(state="normal")
                text_widget.delete(1.0, tk.END)

                # Get metadata from project_metadata instance
                metadata = self.metadata.get_project(project_name)
                if not metadata:
                    logger.warning(f"No metadata found for project: {project_name}")
                    continue

                # Project Title and Basic Info
                text_widget.insert(tk.END, f"{metadata.get('title', project_name)}\n", "title")
                text_widget.insert(tk.END, "-" * 50 + "\n\n")

                # Add summary if available
                if metadata.get('summary'):
                    text_widget.insert(tk.END, f"{metadata.get('summary')}\n\n", "data")

                # Collection Information
                text_widget.insert(tk.END, "Collection Information\n", "section")
                text_widget.insert(tk.END, f"File Count: {len(items)}\n", "data")

                # Source and Inventory IDs
                text_widget.insert(tk.END, f"Source ID: {metadata.get('source_id', 'N/A')}\n", "data")
                text_widget.insert(tk.END, f"Inventory ID: {metadata.get('inventory_id', 'N/A')}\n", "data")

                # Dates with proper formatting
                dates = metadata.get('dates', {})
                if dates:
                    text_widget.insert(tk.END,
                        f"Collection Date: {dates.get('Start', 'N/A')} to {dates.get('End', 'N/A')}\n",
                        "data")
                    text_widget.insert(tk.END,
                        f"Publication Date: {dates.get('Publication', 'N/A')}\n",
                        "data")

                # Format Information
                text_widget.insert(tk.END, "\nFormat Information\n", "section")
                format_info = metadata.get('format', {})
                if format_info:
                    text_widget.insert(tk.END, f"Format: {format_info.get('name', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Version: {format_info.get('version', 'N/A')}\n", "data")

                    # Show size in both MB and bytes if available
                    if 'size_mb' in format_info:
                        text_widget.insert(tk.END, f"Size: {format_info.get('size_mb', 0):.2f} MB", "data")
                        if 'size_bytes' in format_info:
                            text_widget.insert(tk.END, f" ({format_info.get('size_bytes', 0):,} bytes)", "data")
                        text_widget.insert(tk.END, "\n", "data")

                # Coordinate System Information
                text_widget.insert(tk.END, "\nCoordinate System\n", "section")
                coord_system = metadata.get('spatial_ref', {}).get('coordinate_system', {})

                # System name and type
                if coord_system.get('name'):
                    text_widget.insert(tk.END, "Name: ", "data")
                    text_widget.insert(tk.END, f"{coord_system.get('name', 'N/A')}\n", "highlight")
                if coord_system.get('type'):
                    text_widget.insert(tk.END, "Type: ", "data")
                    text_widget.insert(tk.END, f"{coord_system.get('type', 'N/A')}\n", "highlight")
                if coord_system.get('epsg_code'):
                    text_widget.insert(tk.END, "EPSG Code: ", "data")
                    text_widget.insert(tk.END, f"{coord_system.get('epsg_code', 'N/A')}\n", "highlight")
                if coord_system.get('units'):
                    text_widget.insert(tk.END, "Units: ", "data")
                    text_widget.insert(tk.END, f"{coord_system.get('units', 'N/A')}\n", "data")

                # Projection Parameters
                parameters = coord_system.get('parameters', {})
                if parameters:
                    text_widget.insert(tk.END, "\nProjection Parameters:\n", "subsection")

                    # UTM Parameters
                    if coord_system.get('type') == 'utm':
                        text_widget.insert(tk.END, f"Zone: {parameters.get('zone', 'N/A')}\n", "data")
                        text_widget.insert(tk.END, f"Hemisphere: {parameters.get('hemisphere', 'N/A')}\n", "data")
                        text_widget.insert(tk.END, f"Scale Factor: {parameters.get('scale_factor', '0.9996')}\n", "data")
                        text_widget.insert(tk.END, f"Central Meridian: {parameters.get('central_meridian', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"Latitude of Origin: {parameters.get('latitude_of_origin', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"False Easting: {parameters.get('false_easting', 'N/A')} meters\n", "data")
                        text_widget.insert(tk.END, f"False Northing: {parameters.get('false_northing', 'N/A')} meters\n", "data")

                    # Albers Parameters
                    elif coord_system.get('type') == 'albers':
                        text_widget.insert(tk.END, f"Standard Parallel 1: {parameters.get('standard_parallel_1', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"Standard Parallel 2: {parameters.get('standard_parallel_2', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"Central Meridian: {parameters.get('central_meridian', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"Latitude of Origin: {parameters.get('latitude_of_origin', 'N/A')}°\n", "data")
                        text_widget.insert(tk.END, f"False Easting: {parameters.get('false_easting', 'N/A')} meters\n", "data")
                        text_widget.insert(tk.END, f"False Northing: {parameters.get('false_northing', 'N/A')} meters\n", "data")

                    # State Plane Parameters
                    elif coord_system.get('type') == 'state_plane':
                        text_widget.insert(tk.END, f"Zone: {parameters.get('zone', 'N/A')}\n", "data")
                        # Add other state plane parameters if available

                # Datum Information
                text_widget.insert(tk.END, "\nDatum Information\n", "section")
                datum = metadata.get('spatial_ref', {}).get('datum', {})
                text_widget.insert(tk.END, f"Horizontal Datum: {datum.get('horizontal_datum', 'N/A')}\n", "data")
                text_widget.insert(tk.END, f"Vertical Datum: {datum.get('vertical_datum', 'N/A')}\n", "data")
                text_widget.insert(tk.END, f"Ellipsoid: {datum.get('ellipsoid', 'N/A')}\n", "data")

                # Vertical Information
                vertical = metadata.get('vertical', {})
                if vertical:
                    text_widget.insert(tk.END, f"Vertical Units: {vertical.get('units', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Vertical Resolution: {vertical.get('resolution', 'N/A')}\n", "data")

                # Coverage Bounds
                text_widget.insert(tk.END, "\nCoverage Bounds\n", "section")
                bounds = metadata.get('bounds', {})
                if bounds:
                    text_widget.insert(tk.END, f"West: {bounds.get('minX', 'N/A')}°\n", "data")
                    text_widget.insert(tk.END, f"East: {bounds.get('maxX', 'N/A')}°\n", "data")
                    text_widget.insert(tk.END, f"South: {bounds.get('minY', 'N/A')}°\n", "data")
                    text_widget.insert(tk.END, f"North: {bounds.get('maxY', 'N/A')}°\n", "data")

                    # Add calculated values
                    width = bounds.get('maxX', 0) - bounds.get('minX', 0)
                    height = bounds.get('maxY', 0) - bounds.get('minY', 0)
                    text_widget.insert(tk.END, "Width: ", "data")
                    text_widget.insert(tk.END, f"{width:.6f}°\n", "highlight")
                    text_widget.insert(tk.END, "Height: ", "data")
                    text_widget.insert(tk.END, f"{height:.6f}°\n", "highlight")

                    # Add center coordinates
                    center = metadata.get('center_coordinates', {})
                    if center:
                        text_widget.insert(tk.END, "\nCenter Coordinates:\n", "subsection")
                        text_widget.insert(tk.END, "Latitude: ", "data")
                        text_widget.insert(tk.END, f"{center.get('latitude', 'N/A')}°\n", "highlight")
                        text_widget.insert(tk.END, "Longitude: ", "data")
                        text_widget.insert(tk.END, f"{center.get('longitude', 'N/A')}°\n", "highlight")

                # Quality Information
                text_widget.insert(tk.END, "\nQuality Information\n", "section")
                quality = metadata.get('quality', {})
                if quality:
                    text_widget.insert(tk.END, f"Vertical Accuracy: {quality.get('vertical_accuracy', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Logical Consistency: {quality.get('logical_consistency', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Completeness: {quality.get('completeness', 'N/A')}\n", "data")

                # Collection Parameters
                text_widget.insert(tk.END, "\nCollection Parameters\n", "section")
                collection = metadata.get('collection_parameters', {})
                if collection:
                    text_widget.insert(tk.END, f"Collection Type: {collection.get('type', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Sensor: {collection.get('sensor', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Platform: {collection.get('platform', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Flying Height: {collection.get('flying_height', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Scan Angle: {collection.get('scan_angle', 'N/A')}\n", "data")
                    text_widget.insert(tk.END, f"Pulse Rate: {collection.get('pulse_rate', 'N/A')}\n", "data")

                # State and Region Information
                text_widget.insert(tk.END, "\nLocation Information\n", "section")
                text_widget.insert(tk.END, f"State: {metadata.get('state', 'N/A')}\n", "data")
                text_widget.insert(tk.END, f"Region: {metadata.get('region', 'N/A')}\n", "data")

                # Place Keywords
                place_keywords = metadata.get('place_keywords', [])
                if place_keywords:
                    text_widget.insert(tk.END, f"Place Keywords: {', '.join(place_keywords)}\n", "data")

                # URLs and File Paths
                text_widget.insert(tk.END, "\nURLs and File Paths\n", "section")
                text_widget.insert(tk.END, f"Download URL: {metadata.get('download_url', 'N/A')}\n", "url")

                # Metadata URLs
                metadata_urls = metadata.get('metadata_urls', {})
                if metadata_urls:
                    text_widget.insert(tk.END, f"JSON URL: {metadata_urls.get('json_url', 'N/A')}\n", "url")
                    text_widget.insert(tk.END, f"XML URL: {metadata_urls.get('xml_url', 'N/A')}\n", "url")
                    text_widget.insert(tk.END, f"Meta URL: {metadata_urls.get('meta_url', 'N/A')}\n", "url")

                # Additional URLs
                additional_urls = metadata.get('additional_urls', {})
                if additional_urls:
                    text_widget.insert(tk.END, "\nAdditional URLs:\n", "subsection")
                    for url_type, url in additional_urls.items():
                        text_widget.insert(tk.END, f"{url_type.replace('_', ' ').title()}: {url}\n", "url")

                # Local File Path
                if metadata.get('local_file_path', 'N/A') != 'N/A':
                    local_path = metadata.get('local_file_path', 'N/A')
                    text_widget.insert(tk.END, f"\nLocal XML Path: ", "data")
                    text_widget.insert(tk.END, f"{local_path}\n", "success")

                # Metadata Update Timestamp
                if metadata.get('metadata_updated', 'N/A') != 'N/A':
                    text_widget.insert(tk.END, f"\nMetadata Last Updated: ", "data")
                    text_widget.insert(tk.END, f"{metadata.get('metadata_updated', 'N/A')}\n", "highlight")

                text_widget.configure(state="disabled")

        except Exception as e:
            logger.error(f"Error updating project details: {e}", exc_info=True)

    def create_project_tab(self, project_name):
        """Create or get a tab for a project"""
        if project_name not in self.project_tabs:
            self.project_tabs[project_name] = self.create_text_widget(project_name)
        return self.project_tabs[project_name]

    def create_text_widget(self, tab_name):
        """Create a new text widget in a tab"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text=tab_name)

        # Create text widget with scrollbar
        text_widget = tk.Text(frame, wrap=tk.WORD, padx=5, pady=5)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)

        # Configure tags for formatting
        text_widget.tag_configure("title", font=("Arial", 12, "bold"), foreground="#003366")
        text_widget.tag_configure("section", font=("Arial", 10, "bold"), foreground="#006699")
        text_widget.tag_configure("subsection", font=("Arial", 9, "bold"), foreground="#0099CC")
        text_widget.tag_configure("data", font=("Arial", 10))
        text_widget.tag_configure("highlight", font=("Arial", 10, "bold"), foreground="#CC6600")
        text_widget.tag_configure("url", font=("Arial", 10, "underline"), foreground="blue")
        text_widget.tag_configure("warning", font=("Arial", 10, "italic"), foreground="red")
        text_widget.tag_configure("success", font=("Arial", 10), foreground="green")

        # Pack widgets
        scrollbar.pack(side="right", fill="y")
        text_widget.pack(side="left", fill="both", expand=True)

        return text_widget

    def get_selected_project(self):
        """Get the currently selected project's metadata"""
        current_tab = self.notebook.select()
        if current_tab:
            tab_name = self.notebook.tab(current_tab, "text")
            if tab_name != "Overview":
                project_metadata = self.metadata.get_project(tab_name)
                return project_metadata
        return None

    def add_all_files_to_download(self):
        """Add all files from the current project to the download queue"""
        try:
            # Get the currently selected project
            current_tab = self.notebook.select()
            if current_tab:
                tab_name = self.notebook.tab(current_tab, "text")
                if tab_name != "Overview":
                    # Get all files for this project from the lidar downloader
                    project_files = [item for item in self.lidar_downloader.file_list.get_children()
                                   if self.lidar_downloader.file_list.item(item)["values"][-1] == tab_name]

                    # Select all these files
                    for item in project_files:
                        self.lidar_downloader.file_list.set(item, "Select", "✓")
                        self.lidar_downloader.selected_files.add(item)

                    # Add selected files to download
                    self.lidar_downloader.add_to_downloads()

                    logger.info(f"Added all files from project {tab_name} to download queue")
                else:
                    logger.warning("Please select a specific project tab to add files from")
        except Exception as e:
            logger.error(f"Error adding all files to download: {e}", exc_info=True)

    def _view_on_map(self):
        """Open Google Maps in a browser with a path between site coordinates"""
        try:
            selected = self.project_combobox.get()

            if not selected or selected == "Overview":
                messagebox.showwarning("No Selection", "Please select a specific project first.")
                return

            # Get site coordinates from tower_parameters.json
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    site_a = tower_params.get('site_A', {})
                    site_b = tower_params.get('site_B', {})

                    # Convert coordinates if needed

                    # Function to convert DMS to decimal if needed
                    def dms_to_decimal(dms_str):
                        # Check if already decimal
                        try:
                            return float(dms_str)
                        except ValueError:
                            pass

                        # Parse DMS format
                        try:
                            parts = dms_str.replace('°', ' ').replace('\'', ' ').replace('"', ' ').replace('″', ' ').replace('′', ' ').split()

                            # Extract degrees, minutes, seconds
                            degrees = float(parts[0])
                            minutes = float(parts[1]) if len(parts) > 1 else 0
                            seconds = float(parts[2]) if len(parts) > 2 else 0

                            # Handle direction
                            direction = parts[-1] if len(parts) > 1 and parts[-1] in ['N', 'S', 'E', 'W'] else None
                            sign = -1 if direction in ['S', 'W'] else 1

                            # Calculate decimal degrees
                            decimal = sign * (degrees + minutes/60 + seconds/3600)
                            return decimal
                        except Exception as e:
                            logger.error(f"Error converting DMS to decimal: {e}", exc_info=True)
                            return None

                    # Get coordinates
                    lat_a = dms_to_decimal(site_a.get('latitude', '0'))
                    lon_a = dms_to_decimal(site_a.get('longitude', '0'))
                    lat_b = dms_to_decimal(site_b.get('latitude', '0'))
                    lon_b = dms_to_decimal(site_b.get('longitude', '0'))

                    if lat_a is None or lon_a is None or lat_b is None or lon_b is None:
                        raise ValueError("Invalid coordinates")

                    # Open Google Maps with directions
                    url = f"https://www.google.com/maps/dir/?api=1&origin={lat_a},{lon_a}&destination={lat_b},{lon_b}&travelmode=driving"
                    webbrowser.open(url)

            except FileNotFoundError:
                messagebox.showerror("Error", "Could not find tower_parameters.json. Please drop a file with site coordinates first.")
            except Exception as e:
                messagebox.showerror("Error", f"Error opening map: {str(e)}")

        except Exception as e:
            logger.error(f"Error in _view_on_map: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to open map: {str(e)}")