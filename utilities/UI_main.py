"""
Main UI module for the LOS Tool application.
This module handles the creation and configuration of the main UI components.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkintermapview
import os
import time
import logging
import math
import json
from datetime import date
from tkcalendar import DateEntry
import requests

from log_config import setup_logging
from utilities.turbine_processor import TurbineProcessor
from utilities.elevation import ElevationProfile
from utilities.geometry import calculate_polygon_points
from utilities.coordinates import convert_dms_to_decimal

# Create logger
logger = setup_logging(__name__)

class MainUI:
    def __init__(self, root=None):
        """Initialize the main UI components"""
        if root is None:
            # Create main window if not provided
            self.root = TkinterDnD.Tk()
        else:
            self.root = root

        self.root.title("Microwave Line of Sight Project Viewer")
        self.root.geometry("1800x1000")

        # Initialize variables
        self.initialize_variables()

        # Create UI components
        self.create_layout()

        # Setup components
        self.setup_map_widget()
        self.setup_map_controls()
        self.setup_site_details()
        self.setup_legend()
        self.setup_lidar_search()

        # Reference to LidarDownloader and other components (to be set later)
        self.lidar_downloader = None
        self.downloader = None
        self.elevation_profile = None
        self.turbine_processor = None

    def initialize_variables(self):
        """Initialize all tkinter variables used in the UI"""
        # Project details variables
        self.project_link_id = tk.StringVar()
        self.project_link_name = tk.StringVar()
        self.project_path_length = tk.StringVar()

        # Donor site variables
        self.donor_site_name = tk.StringVar()
        self.donor_latitude = tk.StringVar()
        self.donor_longitude = tk.StringVar()
        self.donor_azimuth = tk.StringVar()
        self.donor_elevation = tk.StringVar()
        self.donor_antenna_cl = tk.StringVar()
        self.donor_address = tk.StringVar()

        # Recipient site variables
        self.recipient_site_name = tk.StringVar()
        self.recipient_latitude = tk.StringVar()
        self.recipient_longitude = tk.StringVar()
        self.recipient_azimuth = tk.StringVar()
        self.recipient_elevation = tk.StringVar()
        self.recipient_antenna_cl = tk.StringVar()
        self.recipient_address = tk.StringVar()

        # Control variables
        self.map_style_var = tk.StringVar(value="OpenStreetMap")
        self.labels_var = tk.BooleanVar(value=False)
        self.tile_ids_var = tk.BooleanVar(value=False)
        self.polygon_width_ft = tk.IntVar(value=2000)

        # Map styles definition
        self.map_styles = {
            "OpenStreetMap": {
                "url": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "max_zoom": 19
            },
            "Satellite": {
                "url": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 22
            },
            "Hybrid": {
                "url": "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 22
            },
            "Terrain": {
                "url": "https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 20
            }
        }

    def create_layout(self):
        """Create the main layout with three panels"""
        # Create a PanedWindow for three equal columns
        self.paned_window = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Create main frames for three columns
        self.left_frame = ttk.Frame(self.paned_window, width=600)
        self.center_frame = ttk.Frame(self.paned_window, width=600)
        self.right_frame = ttk.Frame(self.paned_window, width=600)

        self.paned_window.add(self.left_frame)
        self.paned_window.add(self.center_frame)
        self.paned_window.add(self.right_frame)

        # Ensure the frames maintain their size
        self.left_frame.pack_propagate(False)
        self.center_frame.pack_propagate(False)
        self.right_frame.pack_propagate(False)

        # Bind resize event to adjust sash positions
        self.root.bind("<Configure>", self.set_sash_positions)

    def setup_site_details(self):
        """Set up the site details frames in the left panel"""
        # Create a frame to hold all site details in a more compact format
        site_details_frame = ttk.Frame(self.left_frame)
        site_details_frame.pack(fill="x", padx=5, pady=5)

        # Project Details - More compact layout
        project_frame = ttk.LabelFrame(site_details_frame, text="Project Details")
        project_frame.pack(fill="x", padx=5, pady=2)

        # Use grid layout for more compact display
        ttk.Label(project_frame, textvariable=self.project_link_id).grid(row=0, column=0, sticky="w", padx=5)
        ttk.Label(project_frame, textvariable=self.project_link_name).grid(row=0, column=1, sticky="w", padx=5)
        ttk.Label(project_frame, textvariable=self.project_path_length).grid(row=0, column=2, sticky="w", padx=5)

        # Sites Frame - Contains both donor and recipient details
        sites_frame = ttk.Frame(site_details_frame)
        sites_frame.pack(fill="x", padx=5, pady=2)

        # Donor Site Details - More compact layout using grid
        donor_frame = ttk.LabelFrame(sites_frame, text="Donor Site")
        donor_frame.pack(side="left", fill="x", expand=True, padx=2)

        ttk.Label(donor_frame, text="Donor", font=("Arial", 10, "bold"), foreground="blue").grid(row=0, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_site_name).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_latitude).grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_longitude).grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_azimuth).grid(row=3, column=0, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_elevation).grid(row=3, column=1, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_antenna_cl).grid(row=4, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(donor_frame, textvariable=self.donor_address).grid(row=5, column=0, columnspan=2, sticky="w", padx=5)

        # Recipient Site Details - More compact layout using grid
        recipient_frame = ttk.LabelFrame(sites_frame, text="Recipient Site")
        recipient_frame.pack(side="left", fill="x", expand=True, padx=2)

        ttk.Label(recipient_frame, text="Recipient", font=("Arial", 10, "bold"), foreground="red").grid(row=0, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_site_name).grid(row=1, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_latitude).grid(row=2, column=0, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_longitude).grid(row=2, column=1, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_azimuth).grid(row=3, column=0, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_elevation).grid(row=3, column=1, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_antenna_cl).grid(row=4, column=0, columnspan=2, sticky="w", padx=5)
        ttk.Label(recipient_frame, textvariable=self.recipient_address).grid(row=5, column=0, columnspan=2, sticky="w", padx=5)

    def setup_map_widget(self):
        """Set up the map widget in the left panel"""
        # Create a frame to hold both map and elevation profile
        map_and_profile_frame = ttk.Frame(self.left_frame)
        map_and_profile_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Map frame in a LabelFrame
        self.map_frame = ttk.LabelFrame(map_and_profile_frame, text="Map View")
        self.map_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create a frame for the map header
        map_header_frame = ttk.Frame(self.map_frame)
        map_header_frame.pack(fill="x", padx=5, pady=2)

        # Add "Edit Sites" button in the header (to be configured later with command)
        self.edit_sites_button = ttk.Button(
            map_header_frame,
            text="Edit Sites"
        )
        self.edit_sites_button.pack(side="right", padx=5)

        # Add View on Map button in the header (to be configured later)
        self.view_on_map_button = ttk.Button(
            map_header_frame,
            text="View on Map"
        )
        self.view_on_map_button.pack(side="right", padx=5)

        # Set minimum size for map frame
        self.map_frame.configure(width=600, height=400)
        self.map_frame.pack_propagate(False)  # Prevent frame from shrinking

        # Create the map widget
        self.map_widget = tkintermapview.TkinterMapView(self.map_frame, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.map_widget.last_mouse_down_position = None  # Initialize the tracking variable

        # Setup elevation profile
        elevation_frame = ttk.Frame(map_and_profile_frame)
        elevation_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Create elevation profile (will be fully configured later)
        self.elevation_profile = ElevationProfile(elevation_frame)
        self.elevation_profile.frame.pack(fill="both", expand=True)

        # Add button frame under elevation profile (reserved for future use)
        elevation_button_frame = ttk.Frame(elevation_frame)
        elevation_button_frame.pack(fill="x", padx=5, pady=5)

    def setup_map_controls(self):
        """Set up the map control widgets"""
        # Create map control frame
        map_control_frame = ttk.Frame(self.map_frame)
        map_control_frame.pack(fill="x", padx=5, pady=2)

        # Add map style dropdown
        style_label = ttk.Label(map_control_frame, text="Map Style:")
        style_label.pack(side="left", padx=5)

        self.style_dropdown = ttk.Combobox(
            map_control_frame,
            textvariable=self.map_style_var,
            values=list(self.map_styles.keys()),
            state="readonly",
            width=15
        )
        self.style_dropdown.pack(side="left", padx=5)

        # Add labels toggle button
        self.labels_button = ttk.Checkbutton(
            map_control_frame,
            text="Show Labels",
            variable=self.labels_var
        )
        self.labels_button.pack(side="left", padx=5)

        # Add tile IDs toggle button
        self.tile_ids_button = ttk.Checkbutton(
            map_control_frame,
            text="Show Tile IDs",
            variable=self.tile_ids_var
        )
        self.tile_ids_button.pack(side="left", padx=5)

        # Store the reference to tile_ids_var in the root object for accessibility
        self.root.tile_ids_var = self.tile_ids_var

    def setup_legend(self):
        """Set up the project legend frame"""
        # Project Legend with proper sizing and placement
        self.legend_frame = ttk.LabelFrame(self.center_frame, text="Project Legend")
        self.legend_frame.pack(fill="x", padx=5, pady=5)  # Pack at top of center frame

        # Create scrollable frame for legend
        self.legend_canvas = tk.Canvas(self.legend_frame, height=150)
        self.legend_scrollbar = ttk.Scrollbar(self.legend_frame, orient="vertical", command=self.legend_canvas.yview)

        # Pack scrollbar and canvas
        self.legend_scrollbar.pack(side="right", fill="y")
        self.legend_canvas.pack(side="left", fill="both", expand=True)
        self.legend_canvas.configure(yscrollcommand=self.legend_scrollbar.set)

        # Create frame for legend items
        self.legend_items_frame = ttk.Frame(self.legend_canvas)
        self.legend_canvas_window = self.legend_canvas.create_window(
            (0, 0),
            window=self.legend_items_frame,
            anchor="nw",
            width=self.legend_canvas.winfo_width()
        )

        # Configure scrolling and resizing
        self.legend_items_frame.bind("<Configure>", self.configure_legend_scroll)
        self.legend_canvas.bind("<Configure>", self.on_canvas_configure)

        # Bind mousewheel for scrolling
        self.legend_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Add initial "No LIDAR data" label
        ttk.Label(
            self.legend_items_frame,
            text="No LIDAR data loaded",
            foreground="gray"
        ).pack(anchor="w", padx=5, pady=2)

    def setup_lidar_search(self):
        """Set up the LIDAR search controls"""
        # LIDAR Search Frame at top of center column
        self.lidar_frame = ttk.LabelFrame(self.center_frame, text="LIDAR Search")
        self.lidar_frame.pack(fill="x", padx=10, pady=5)

        # Configure ttk styles for better date picker appearance
        style = ttk.Style()
        style.configure('DateEntry', relief='solid', borderwidth=2, padx=4, pady=4)
        style.map('DateEntry', relief=[('active', 'solid'), ('focus', 'solid')])

        # Date selection
        ttk.Label(self.lidar_frame, text="Start Date:").grid(row=0, column=0, padx=5, pady=5)
        self.start_date = DateEntry(self.lidar_frame, width=12, background='darkblue',
                                  foreground='white', date_pattern='yyyy-mm-dd',
                                  borderwidth=2, relief="solid",
                                  selectmode='day',
                                  cursor="hand2",
                                  style='DateEntry')
        self.start_date.set_date(date(2000, 1, 1))
        self.start_date.grid(row=0, column=1, padx=5, pady=5, sticky='ew')

        ttk.Label(self.lidar_frame, text="End Date:").grid(row=0, column=2, padx=5, pady=5)
        self.end_date = DateEntry(self.lidar_frame, width=12, background='darkblue',
                                foreground='white', date_pattern='yyyy-mm-dd',
                                borderwidth=2, relief="solid",
                                selectmode='day',
                                cursor="hand2",
                                style='DateEntry')
        self.end_date.set_date(date.today())
        self.end_date.grid(row=0, column=3, padx=5, pady=5, sticky='ew')

        # Search button
        self.search_button = ttk.Button(self.lidar_frame, text="Search LIDAR")
        self.search_button.grid(row=0, column=4, padx=5, pady=5)

        # Clear Data button
        self.clear_data_button = ttk.Button(self.lidar_frame, text="Clear Data")
        self.clear_data_button.grid(row=0, column=5, padx=5, pady=5)

        # Add width spinbox in second row
        ttk.Label(self.lidar_frame, text="Search Width (ft):").grid(row=1, column=0, padx=5, pady=5)
        self.width_spinbox = ttk.Spinbox(
            self.lidar_frame,
            from_=500,
            to=10000,
            increment=100,
            width=8,
            textvariable=self.polygon_width_ft
        )
        self.width_spinbox.grid(row=1, column=1, padx=5, pady=5)

        # Add "Add All Project Files to Download" button in second row
        self.add_all_button = ttk.Button(
            self.lidar_frame,
            text="Add All Project Files to Download"
        )
        self.add_all_button.grid(row=1, column=2, columnspan=3, padx=5, pady=5, sticky="ew")

    def set_sash_positions(self, event=None):
        """Adjust the sash positions to divide the window equally"""
        # Only process events from the root window to avoid infinite loops
        if event and event.widget != self.root:
            return

        width = self.paned_window.winfo_width()
        if width > 0:  # Ensure the width is valid
            third = width // 3
            self.paned_window.sash_place(0, third, 0)
            self.paned_window.sash_place(1, third * 2, 0)

    def configure_legend_scroll(self, event=None):
        """Update the scroll region when the legend content changes"""
        self.legend_canvas.configure(scrollregion=self.legend_canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """Update the legend frame width when canvas resizes"""
        self.legend_canvas.itemconfig(self.legend_canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling for the legend"""
        self.legend_canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def set_lidar_downloader(self, lidar_downloader):
        """Set the LidarDownloader instance and configure event handlers"""
        self.lidar_downloader = lidar_downloader

        # Connect buttons to their respective functions
        if lidar_downloader:
            # Connect search button
            self.search_button.configure(command=lidar_downloader.search_lidar)

            # Connect clear data button
            self.clear_data_button.configure(command=lidar_downloader.clear_all_data)

            # Connect add all files button
            self.add_all_button.configure(command=lidar_downloader.add_all_files_to_download)

            # Connect view on map button
            self.view_on_map_button.configure(command=lidar_downloader._view_on_map)

            # Configure style dropdown
            self.style_dropdown.bind('<<ComboboxSelected>>', self.on_style_change)

            # Configure label toggles
            self.labels_button.configure(command=lambda: self.toggle_labels(self.labels_var))
            self.tile_ids_button.configure(command=lambda: self.toggle_tile_ids(self.tile_ids_var))

    def toggle_tile_ids(self, var):
        """Toggle visibility of tile ID labels"""
        try:
            show_tile_ids = var.get()
            logger.info(f"Tile ID labels {'shown' if show_tile_ids else 'hidden'}")

            if not self.lidar_downloader:
                logger.warning("No lidar_downloader available")
                return

            # First check if there are any polygons to work with
            if not hasattr(self.lidar_downloader, 'lidar_polygons'):
                logger.warning("No lidar_polygons attribute found")
                return

            visible_polygons = len(self.lidar_downloader.lidar_polygons)
            logger.info(f"Found {visible_polygons} visible polygons for tile labeling")

            if visible_polygons == 0:
                # Check if we have any polygons at all in the backup
                all_polygons = 0
                if hasattr(self.lidar_downloader, '_all_project_polygons'):
                    for project, polygons in self.lidar_downloader._all_project_polygons.items():
                        all_polygons += len(polygons)

                logger.info(f"Found {all_polygons} total polygons in all projects (including hidden)")

                # Set toggle back to off if we can't show labels
                if all_polygons == 0:
                    var.set(False)
                    return

            # Use the direct methods to show/hide tile labels
            if show_tile_ids:
                # Create and show tile labels
                count = self.lidar_downloader.create_and_show_tile_labels()
                logger.info(f"Created {count} tile number markers")
                if count == 0:
                    var.set(False)
            else:
                # Hide all tile labels
                self.lidar_downloader.hide_tile_labels()
                logger.info("Removed all tile markers")

        except Exception as e:
            logger.error(f"Error toggling tile IDs: {e}", exc_info=True)

    def toggle_labels(self, var):
        """Toggle visibility of turbine labels"""
        try:
            show_labels = var.get()
            logger.info(f"Toggle Labels button clicked, setting to {show_labels}")

            # Check if lidar_downloader exists and has the necessary attributes
            if not self.lidar_downloader or not hasattr(self.lidar_downloader, 'show_turbine_labels'):
                logger.error("LidarDownloader not initialized or missing show_turbine_labels attribute")
                var.set(not show_labels)  # Revert the toggle
                return

            # Check if there are any turbines to label
            if not hasattr(self.lidar_downloader, 'turbine_processor') or not self.lidar_downloader.turbine_processor.last_turbines:
                logger.warning("No turbines available to label")
                var.set(not show_labels)  # Revert the toggle
                return

            # Set the show_turbine_labels variable in the TurbineProcessor instance
            self.lidar_downloader.show_turbine_labels.set(show_labels)

            # Call the toggle_turbine_labels method to handle the visibility change
            self.lidar_downloader.toggle_turbine_labels()

            # Log the success
            turbine_count = len(self.lidar_downloader.turbine_processor.last_turbines)
            logger.info(f"Turbine labels toggled successfully to {'visible' if show_labels else 'hidden'} for {turbine_count} turbines")

        except Exception as e:
            logger.error(f"Error toggling labels: {e}", exc_info=True)
            var.set(not show_labels)  # Revert the toggle

    def on_style_change(self, event):
        """Handle map style change"""
        try:
            style_name = self.style_dropdown.get()
            style = self.map_styles[style_name]

            # Set tile server without 'name' parameter
            logger.info(f"Changing map style to {style_name} with URL: {style['url']}")
            self.map_widget.set_tile_server(
                style["url"],
                max_zoom=style["max_zoom"]
            )
            logger.info(f"Switched to {style_name} view")

        except Exception as e:
            logger.error(f"Error changing map style: {e}")

    def set_edit_sites_command(self, command):
        """Set the command for the Edit Sites button"""
        self.edit_sites_button.configure(command=command)

class ManualSitesDialog(tk.Toplevel):
    """Dialog for manual entry of site coordinates"""
    def __init__(self, parent, callback, convert_func, distance_func):
        super().__init__(parent)
        self.title("Site Coordinates Entry")
        self.geometry("750x500")
        self.callback = callback
        self.convert_func = convert_func
        self.distance_func = distance_func

        # Create tabs for each site
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Create the site tabs
        self.site_a_frame = ttk.Frame(self.notebook)
        self.site_b_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.site_a_frame, text="Donor Site (A)")
        self.notebook.add(self.site_b_frame, text="Recipient Site (B)")

        # Create entry fields for each site
        self.site_a_fields = self.create_site_fields(self.site_a_frame, "A")
        self.site_b_fields = self.create_site_fields(self.site_b_frame, "B")

        # Create common parameters frame
        self.common_frame = ttk.Frame(self)
        self.common_frame.pack(fill="x", padx=10, pady=5)

        # Frequency field
        ttk.Label(self.common_frame, text="Frequency (GHz):").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.frequency_ghz = ttk.Entry(self.common_frame, width=10)
        self.frequency_ghz.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        # Don't insert a default value - let user enter the actual frequency
        # Add a tooltip or placeholder behavior
        self.frequency_ghz.insert(0, "Enter GHz (e.g., 11.0)")
        self.frequency_ghz.bind('<FocusIn>', self._on_frequency_focus_in)
        self.frequency_ghz.bind('<FocusOut>', self._on_frequency_focus_out)

        # Add path length display
        ttk.Label(self.common_frame, text="Path Length (mi):").grid(row=0, column=2, padx=5, pady=5, sticky="e")
        self.path_length = ttk.Label(self.common_frame, text="0")
        self.path_length.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Add buttons
        self.button_frame = ttk.Frame(self)
        self.button_frame.pack(fill="x", padx=10, pady=10)

        self.calculate_btn = ttk.Button(self.button_frame, text="Calculate Distance", command=self.calculate_path_length)
        self.calculate_btn.pack(side="left", padx=5)

        self.fetch_elev_btn = ttk.Button(self.button_frame, text="Fetch Elevations", command=self.fetch_all_elevations)
        self.fetch_elev_btn.pack(side="left", padx=5)

        self.use_adjusted_btn = ttk.Button(self.button_frame, text="Use Adjusted Coordinates", command=self.use_adjusted_coordinates)
        self.use_adjusted_btn.pack(side="left", padx=5)

        self.save_btn = ttk.Button(self.button_frame, text="Save", command=self.save_data)
        self.save_btn.pack(side="right", padx=5)

        self.cancel_btn = ttk.Button(self.button_frame, text="Cancel", command=self.destroy)
        self.cancel_btn.pack(side="right", padx=5)

        # Center the dialog on the parent window
        self.transient(parent)
        self.grab_set()

    def _on_frequency_focus_in(self, event):
        """Placeholder for frequency entry focus in behavior"""
        if self.frequency_ghz.get() == "Enter GHz (e.g., 11.0)":
            self.frequency_ghz.delete(0, tk.END)
            self.frequency_ghz.insert(0, "")

    def _on_frequency_focus_out(self, event):
        """Placeholder for frequency entry focus out behavior"""
        if self.frequency_ghz.get() == "":
            self.frequency_ghz.delete(0, tk.END)
            self.frequency_ghz.insert(0, "Enter GHz (e.g., 11.0)")

    def create_site_fields(self, frame, site_id):
        """Create entry fields for a site"""
        fields = {}

        # Site name
        ttk.Label(frame, text="Site Name:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        fields["site_id"] = ttk.Entry(frame, width=30)
        fields["site_id"].grid(row=0, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        if site_id == "A":
            fields["site_id"].insert(0, "Donor Site")
        else:
            fields["site_id"].insert(0, "Recipient Site")

        # Coordinate format selection
        ttk.Label(frame, text="Coordinate Format:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        fields["coord_format"] = ttk.Combobox(frame, values=["DMS (48-12-30.5 N)", "Decimal (48.12345)"],
                                        state="readonly", width=20)
        fields["coord_format"].grid(row=1, column=1, columnspan=3, padx=5, pady=5, sticky="w")
        fields["coord_format"].current(0)

        # Latitude and Longitude
        ttk.Label(frame, text="Latitude:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        fields["latitude"] = ttk.Entry(frame, width=30)
        fields["latitude"].grid(row=2, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        ttk.Label(frame, text="Longitude:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        fields["longitude"] = ttk.Entry(frame, width=30)
        fields["longitude"].grid(row=3, column=1, columnspan=3, padx=5, pady=5, sticky="w")

        # Site elevation
        ttk.Label(frame, text="Elevation (ft):").grid(row=4, column=0, padx=5, pady=5, sticky="e")
        fields["elevation_ft"] = ttk.Entry(frame, width=10)
        fields["elevation_ft"].grid(row=4, column=1, padx=5, pady=5, sticky="w")
        fields["elevation_ft"].insert(0, "0")

        # Fetch elevation button
        fields["fetch_elevation"] = ttk.Button(frame, text="Fetch",
                                         command=lambda: self.fetch_elevation(site_id))
        fields["fetch_elevation"].grid(row=4, column=2, padx=5, pady=5, sticky="w")

        # Antenna centerline
        ttk.Label(frame, text="Antenna CL (ft):").grid(row=5, column=0, padx=5, pady=5, sticky="e")
        fields["antenna_cl_ft"] = ttk.Entry(frame, width=10)
        fields["antenna_cl_ft"].grid(row=5, column=1, padx=5, pady=5, sticky="w")
        fields["antenna_cl_ft"].insert(0, "0")

        # Azimuth
        ttk.Label(frame, text="Azimuth (°):").grid(row=6, column=0, padx=5, pady=5, sticky="e")
        fields["azimuth_deg"] = ttk.Entry(frame, width=10)
        fields["azimuth_deg"].grid(row=6, column=1, padx=5, pady=5, sticky="w")
        fields["azimuth_deg"].insert(0, "0")

        return fields

    def fetch_elevation(self, site_id):
        """Fetch elevation data for a site"""
        if site_id == "A":
            fields = self.site_a_fields
        else:
            fields = self.site_b_fields

        # Get coordinates
        try:
            lat_str = fields["latitude"].get().strip()
            lon_str = fields["longitude"].get().strip()

            if not lat_str or not lon_str:
                messagebox.showwarning("Missing Data", "Please enter latitude and longitude first.")
                return

            # Convert to decimal if needed
            coord_format = fields["coord_format"].get()
            if coord_format.startswith("DMS"):
                try:
                    lat, lon = self.convert_func(lat_str, lon_str)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to convert coordinates: {str(e)}")
                    return
            else:
                try:
                    lat = float(lat_str)
                    lon = float(lon_str)
                except ValueError:
                    messagebox.showerror("Error", "Invalid decimal coordinates format.")
                    return

            # Fetch elevation
            try:
                url = f"https://epqs.nationalmap.gov/v1/json?x={lon}&y={lat}&units=Feet&output=json"
                response = requests.get(url, timeout=10)
                data = response.json()

                if "value" in data:
                    elevation = data["value"]
                    fields["elevation_ft"].delete(0, tk.END)
                    fields["elevation_ft"].insert(0, str(elevation))
                    return elevation
                else:
                    messagebox.showwarning("No Data", "Could not retrieve elevation data.")
                    return None
            except Exception as e:
                messagebox.showerror("Error", f"Failed to fetch elevation data: {str(e)}")
                return None
        except Exception as e:
            messagebox.showerror("Error", f"Error fetching elevation: {str(e)}")
            return None

    def fetch_all_elevations(self):
        """Fetch elevations for both sites"""
        elev_a = self.fetch_elevation("A")
        elev_b = self.fetch_elevation("B")

        if elev_a is not None and elev_b is not None:
            messagebox.showinfo("Success", "Elevations retrieved successfully.")

    def calculate_path_length(self):
        """Calculate the path length between the two sites"""
        try:
            # Get site A coordinates
            lat_a_str = self.site_a_fields["latitude"].get().strip()
            lon_a_str = self.site_a_fields["longitude"].get().strip()

            # Get site B coordinates
            lat_b_str = self.site_b_fields["latitude"].get().strip()
            lon_b_str = self.site_b_fields["longitude"].get().strip()

            if not lat_a_str or not lon_a_str or not lat_b_str or not lon_b_str:
                messagebox.showwarning("Missing Data", "Please enter coordinates for both sites.")
                return

            # Convert to decimal if needed
            coord_format_a = self.site_a_fields["coord_format"].get()
            if coord_format_a.startswith("DMS"):
                try:
                    lat_a, lon_a = self.convert_func(lat_a_str, lon_a_str)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to convert Site A coordinates: {str(e)}")
                    return
            else:
                try:
                    lat_a = float(lat_a_str)
                    lon_a = float(lon_a_str)
                except ValueError:
                    messagebox.showerror("Error", "Invalid decimal coordinates for Site A.")
                    return

            coord_format_b = self.site_b_fields["coord_format"].get()
            if coord_format_b.startswith("DMS"):
                try:
                    lat_b, lon_b = self.convert_func(lat_b_str, lon_b_str)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to convert Site B coordinates: {str(e)}")
                    return
            else:
                try:
                    lat_b = float(lat_b_str)
                    lon_b = float(lon_b_str)
                except ValueError:
                    messagebox.showerror("Error", "Invalid decimal coordinates for Site B.")
                    return

            # Calculate distance
            distance = self.distance_func((lat_a, lon_a), (lat_b, lon_b))

            # Update path length display
            self.path_length.config(text=f"{distance:.2f}")

            # Calculate and set azimuth values for both sites
            self.calculate_azimuths(lat_a, lon_a, lat_b, lon_b)

            return distance
        except Exception as e:
            messagebox.showerror("Error", f"Error calculating path length: {str(e)}")
            return None

    def calculate_azimuths(self, lat_a, lon_a, lat_b, lon_b):
        """Calculate azimuth values for both sites"""
        try:
            # Calculate azimuth from A to B
            y = math.sin(math.radians(lon_b - lon_a)) * math.cos(math.radians(lat_b))
            x = math.cos(math.radians(lat_a)) * math.sin(math.radians(lat_b)) - \
                math.sin(math.radians(lat_a)) * math.cos(math.radians(lat_b)) * \
                math.cos(math.radians(lon_b - lon_a))
            azimuth_a_to_b = math.degrees(math.atan2(y, x))
            azimuth_a_to_b = (azimuth_a_to_b + 360) % 360

            # Calculate azimuth from B to A (opposite direction)
            azimuth_b_to_a = (azimuth_a_to_b + 180) % 360

            # Update the azimuth fields
            self.site_a_fields["azimuth_deg"].delete(0, tk.END)
            self.site_a_fields["azimuth_deg"].insert(0, f"{azimuth_a_to_b:.1f}")

            self.site_b_fields["azimuth_deg"].delete(0, tk.END)
            self.site_b_fields["azimuth_deg"].insert(0, f"{azimuth_b_to_a:.1f}")
        except Exception as e:
            messagebox.showwarning("Warning", f"Failed to calculate azimuths: {str(e)}")

    def use_adjusted_coordinates(self):
        """Load adjusted coordinates from tower_parameters.json and set them as the actual coordinates"""
        try:
            # Get the path to the tower_parameters.json file
            tower_params_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tower_parameters.json')

            if not os.path.exists(tower_params_path):
                messagebox.showerror("Error", "tower_parameters.json file not found.")
                return

            # Load the tower parameters file
            with open(tower_params_path, 'r') as f:
                tower_data = json.load(f)

            # Ask if user wants to make adjusted coordinates permanent
            make_permanent = messagebox.askyesno(
                "Permanent Change?",
                "Do you want to make the adjusted coordinates permanent?\n\n"
                "If YES: Adjusted coordinates will become the new regular coordinates.\n"
                "If NO: Adjusted coordinates will be used in this dialog only."
            )

            # Check if adjusted coordinates exist for Site A (donor)
            if 'site_A' in tower_data and 'adjusted_latitude' in tower_data['site_A'] and 'adjusted_longitude' in tower_data['site_A']:
                adj_lat_a = tower_data['site_A']['adjusted_latitude']
                adj_lon_a = tower_data['site_A']['adjusted_longitude']

                # Update Site A fields - Make sure to set format to Decimal first
                self.site_a_fields["coord_format"].current(1)  # Set to Decimal format
                self.site_a_fields["latitude"].delete(0, tk.END)
                self.site_a_fields["latitude"].insert(0, str(adj_lat_a))
                self.site_a_fields["longitude"].delete(0, tk.END)
                self.site_a_fields["longitude"].insert(0, str(adj_lon_a))
                logger.info(f"Loaded adjusted coordinates for Site A: {adj_lat_a}, {adj_lon_a}")

                # If making permanent, update the tower_parameters.json file
                if make_permanent:
                    tower_data['site_A']['latitude'] = str(adj_lat_a)
                    tower_data['site_A']['longitude'] = str(adj_lon_a)
                    # Clear adjusted coordinates
                    tower_data['site_A'].pop('adjusted_latitude', None)
                    tower_data['site_A'].pop('adjusted_longitude', None)
                    logger.info("Made adjusted coordinates permanent for Site A")
            else:
                logger.warning("No adjusted coordinates found for Site A")

            # Check if adjusted coordinates exist for Site B (recipient)
            if 'site_B' in tower_data and 'adjusted_latitude' in tower_data['site_B'] and 'adjusted_longitude' in tower_data['site_B']:
                adj_lat_b = tower_data['site_B']['adjusted_latitude']
                adj_lon_b = tower_data['site_B']['adjusted_longitude']

                # Update Site B fields - Make sure to set format to Decimal first
                self.site_b_fields["coord_format"].current(1)  # Set to Decimal format
                self.site_b_fields["latitude"].delete(0, tk.END)
                self.site_b_fields["latitude"].insert(0, str(adj_lat_b))
                self.site_b_fields["longitude"].delete(0, tk.END)
                self.site_b_fields["longitude"].insert(0, str(adj_lon_b))
                logger.info(f"Loaded adjusted coordinates for Site B: {adj_lat_b}, {adj_lon_b}")

                # If making permanent, update the tower_parameters.json file
                if make_permanent:
                    tower_data['site_B']['latitude'] = str(adj_lat_b)
                    tower_data['site_B']['longitude'] = str(adj_lon_b)
                    # Clear adjusted coordinates
                    tower_data['site_B'].pop('adjusted_latitude', None)
                    tower_data['site_B'].pop('adjusted_longitude', None)
                    logger.info("Made adjusted coordinates permanent for Site B")
            else:
                logger.warning("No adjusted coordinates found for Site B")

            # If making permanent, save the changes
            if make_permanent:
                with open(tower_params_path, 'w') as f:
                    json.dump(tower_data, f, indent=2)
                logger.info("Saved permanent coordinate changes to tower_parameters.json")

            # Check if we loaded at least one set of adjusted coordinates
            if ('site_A' in tower_data and 'adjusted_latitude' in tower_data['site_A']) or \
               ('site_B' in tower_data and 'adjusted_latitude' in tower_data['site_B']):
                if make_permanent:
                    messagebox.showinfo("Success", "Adjusted coordinates loaded and made permanent.")
                else:
                    messagebox.showinfo("Success", "Adjusted coordinates loaded successfully.")

                # Recalculate path length and azimuths with the new coordinates
                self.calculate_path_length()
            else:
                messagebox.showwarning("Warning", "No adjusted coordinates found in tower_parameters.json.")

        except Exception as e:
            logger.error(f"Error loading adjusted coordinates: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load adjusted coordinates: {str(e)}")

    def save_data(self):
        """Save the entered data"""
        try:
            # Calculate distance first to make sure coordinates are valid
            distance = self.calculate_path_length()
            if distance is None:
                return

            # Handle frequency field with placeholder text
            frequency_text = self.frequency_ghz.get().strip()
            if frequency_text == "Enter GHz (e.g., 11.0)" or frequency_text == "":
                messagebox.showerror("Missing Frequency", 
                                   "Please enter the microwave link frequency in GHz.\n\n"
                                   "Common values are: 6, 11, 18, 23, 38")
                self.frequency_ghz.focus_set()
                return
            
            try:
                frequency_value = float(frequency_text)
                if frequency_value <= 0:
                    messagebox.showerror("Invalid Frequency", 
                                       "Frequency must be greater than 0 GHz.")
                    self.frequency_ghz.focus_set()
                    return
            except ValueError:
                messagebox.showerror("Invalid Frequency", 
                                   "Please enter a valid numeric frequency value in GHz.")
                self.frequency_ghz.focus_set()
                return

            # Construct the data structure
            data = {
                "site_A": {
                    "site_id": self.site_a_fields["site_id"].get(),
                    "latitude": self.site_a_fields["latitude"].get().strip(),
                    "longitude": self.site_a_fields["longitude"].get().strip(),
                    "elevation_ft": float(self.site_a_fields["elevation_ft"].get() or 0),
                    "antenna_cl_ft": float(self.site_a_fields["antenna_cl_ft"].get() or 0),
                    "azimuth_deg": float(self.site_a_fields["azimuth_deg"].get() or 0)
                },
                "site_B": {
                    "site_id": self.site_b_fields["site_id"].get(),
                    "latitude": self.site_b_fields["latitude"].get().strip(),
                    "longitude": self.site_b_fields["longitude"].get().strip(),
                    "elevation_ft": float(self.site_b_fields["elevation_ft"].get() or 0),
                    "antenna_cl_ft": float(self.site_b_fields["antenna_cl_ft"].get() or 0),
                    "azimuth_deg": float(self.site_b_fields["azimuth_deg"].get() or 0)
                },
                "general_parameters": {
                    "frequency_ghz": frequency_value,  # Use the validated frequency value
                    "path_length_mi": distance
                }
            }

            # Check if we need to preserve any adjusted coordinates from the existing file
            try:
                tower_params_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tower_parameters.json')
                if os.path.exists(tower_params_path):
                    with open(tower_params_path, 'r') as f:
                        existing_data = json.load(f)

                    # If the coordinates haven't changed, preserve the adjusted coordinates
                    # Otherwise, clear them as they no longer match
                    if 'site_A' in existing_data and 'adjusted_latitude' in existing_data['site_A']:
                        # Compare with existing coordinates, converting formats if needed
                        existing_coords_match = self._check_if_coords_match('A', existing_data)
                        if existing_coords_match:
                            # Keep adjusted coordinates
                            data['site_A']['adjusted_latitude'] = existing_data['site_A']['adjusted_latitude']
                            data['site_A']['adjusted_longitude'] = existing_data['site_A']['adjusted_longitude']
                            logger.info("Preserved adjusted coordinates for Site A")
                        else:
                            # Coordinates changed, ask user what to do with adjusted coordinates
                            preserve_a = messagebox.askyesno(
                                "Adjusted Coordinates",
                                "The coordinates for Site A have changed. Keep the existing adjusted coordinates?"
                            )
                            if preserve_a:
                                data['site_A']['adjusted_latitude'] = existing_data['site_A']['adjusted_latitude']
                                data['site_A']['adjusted_longitude'] = existing_data['site_A']['adjusted_longitude']
                                logger.info("User chose to preserve adjusted coordinates for Site A")
                            else:
                                logger.info("User chose to clear adjusted coordinates for Site A")

                    # Same for site B
                    if 'site_B' in existing_data and 'adjusted_latitude' in existing_data['site_B']:
                        existing_coords_match = self._check_if_coords_match('B', existing_data)
                        if existing_coords_match:
                            data['site_B']['adjusted_latitude'] = existing_data['site_B']['adjusted_latitude']
                            data['site_B']['adjusted_longitude'] = existing_data['site_B']['adjusted_longitude']
                            logger.info("Preserved adjusted coordinates for Site B")
                        else:
                            preserve_b = messagebox.askyesno(
                                "Adjusted Coordinates",
                                "The coordinates for Site B have changed. Keep the existing adjusted coordinates?"
                            )
                            if preserve_b:
                                data['site_B']['adjusted_latitude'] = existing_data['site_B']['adjusted_latitude']
                                data['site_B']['adjusted_longitude'] = existing_data['site_B']['adjusted_longitude']
                                logger.info("User chose to preserve adjusted coordinates for Site B")
                            else:
                                logger.info("User chose to clear adjusted coordinates for Site B")

                    # Preserve LIDAR data
                    if 'lidar_data' in existing_data:
                        data['lidar_data'] = existing_data['lidar_data']

                    # Preserve turbines
                    if 'turbines' in existing_data:
                        data['turbines'] = existing_data['turbines']
                else:
                    # Initialize empty collections for new file
                    data['lidar_data'] = {}
                    data['turbines'] = []
            except Exception as e:
                logger.error(f"Error handling adjusted coordinates: {e}", exc_info=True)
                # Continue with save anyway
                data['lidar_data'] = {}
                data['turbines'] = []

            # Call the callback with the data
            self.callback(data)

            # Close the dialog
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Error saving data: {str(e)}")

    def _check_if_coords_match(self, site_id, existing_data):
        """Check if the entered coordinates match the existing ones in the file"""
        try:
            if site_id == 'A':
                fields = self.site_a_fields
                site_key = 'site_A'
            else:
                fields = self.site_b_fields
                site_key = 'site_B'

            # Get the current values from the entry fields
            current_lat = fields["latitude"].get().strip()
            current_lon = fields["longitude"].get().strip()
            current_format = fields["coord_format"].get()

            # Get existing values from the file
            existing_lat = existing_data[site_key].get('latitude', '')
            existing_lon = existing_data[site_key].get('longitude', '')

            # Check if current coordinates are in decimal format
            is_current_decimal = current_format.startswith("Decimal") or (
                isinstance(current_lat, str) and current_lat.replace('.', '', 1).replace('-', '', 1).isdigit() and
                isinstance(current_lon, str) and current_lon.replace('.', '', 1).replace('-', '', 1).isdigit()
            )

            # Convert current coordinates to decimal for comparison if needed
            if is_current_decimal:
                try:
                    current_lat_dec = float(current_lat)
                    current_lon_dec = float(current_lon)
                except ValueError:
                    logger.error(f"Failed to convert current decimal coordinates: {current_lat}, {current_lon}")
                    return False
            else:
                # It's in DMS format
                try:
                    current_lat_dec, current_lon_dec = self.convert_func(current_lat, current_lon)
                except Exception as e:
                    logger.error(f"Failed to convert current DMS coordinates: {e}")
                    return False

            # Check if existing coordinates are in decimal format
            is_existing_decimal = (
                isinstance(existing_lat, (int, float)) or
                (isinstance(existing_lat, str) and existing_lat.replace('.', '', 1).replace('-', '', 1).isdigit())
            )

            # Convert existing coordinates to decimal for comparison
            if is_existing_decimal:
                try:
                    existing_lat_dec = float(existing_lat)
                    existing_lon_dec = float(existing_lon)
                except ValueError:
                    logger.error(f"Failed to convert existing decimal coordinates: {existing_lat}, {existing_lon}")
                    return False
            else:
                # Check if it's in DMS format with direction indicators
                try:
                    existing_lat_dec, existing_lon_dec = self.convert_func(existing_lat, existing_lon)
                except Exception as e:
                    logger.error(f"Failed to convert existing DMS coordinates: {e}")
                    return False

            # Compare with a small tolerance to account for floating point differences
            tolerance = 0.0000001  # About 1cm at the equator
            return (abs(current_lat_dec - existing_lat_dec) < tolerance and
                    abs(current_lon_dec - existing_lon_dec) < tolerance)
        except Exception as e:
            logger.error(f"Error checking coordinate match: {e}", exc_info=True)
            return False