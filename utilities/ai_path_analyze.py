"""
Module for analyzing the map path between two sites using AI vision models.
"""

import tkinter as tk
from tkinter import messagebox, Toplevel, ttk
import tkintermapview
import os
import time
import math
import threading
import json
from PIL import ImageGrab, Image
import base64
import requests
from log_config import setup_logging
import io # Explicit import

# Create logger
logger = setup_logging(__name__)

# --- Configuration ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
MAPBOX_ACCESS_TOKEN = os.environ.get("MAPBOX_ACCESS_TOKEN")
ANALYSIS_WINDOW_WIDTH = 1400
ANALYSIS_WINDOW_HEIGHT = 800
CONTROL_SIDEBAR_WIDTH = 180
MAP_CAPTURE_DELAY_SECONDS = 3.0

# Define Map Sources (Ensure Mapbox token check)
_MAP_SOURCES_RAW = {
    "google_satellite": {
        "name": "Google Satellite",
        "tile_server": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga",
        "max_zoom": 22,
        "zoom_offset": 0,  # No adjustment needed
        "load_delay": MAP_CAPTURE_DELAY_SECONDS,  # Default delay
        "view_padding": 0.2,  # 20% padding for image overlap
        "attribution": "Google"
    },
    "esri_world_imagery": {
        "name": "Esri World Imagery",
        "tile_server": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "max_zoom": 23,
        "zoom_offset": -1,  # Zoom out one level for ESRI
        "load_delay": MAP_CAPTURE_DELAY_SECONDS,  # Default delay
        "view_padding": 0.2,  # 20% padding for image overlap
        "attribution": "Esri, Maxar, Earthstar Geographics, CNES/Airbus DS, USDA, USGS, AeroGRID, IGN, and the GIS User Community"
    },
    "mapbox_satellite": {
        "name": "Mapbox Satellite",
        # Standard Mapbox raster tiles URL (more stable than styles API)
        "tile_server_template": "https://api.mapbox.com/v4/mapbox.satellite/{z}/{x}/{y}.jpg90?access_token={token}",
        "max_zoom": 22,  # Allow higher zoom levels
        "zoom_offset": 0,  # No offset to allow zoom level 19 as default
        "load_delay": MAP_CAPTURE_DELAY_SECONDS * 2.5,  # Even longer delay for Mapbox
        "view_padding": 0.25,  # 25% padding for image overlap (more for Mapbox)
        "attribution": "Mapbox, OpenStreetMap",
        "requires_token": True
    }
}

def get_active_map_sources():
    """Returns a dictionary of map sources that are properly configured."""
    active_sources = {}
    map_sources_to_process = json.loads(json.dumps(_MAP_SOURCES_RAW)) # Deep copy

    for key, config in map_sources_to_process.items():
        # Store the source key in the config for later reference
        config["source_key"] = key
        if config.get("requires_token"):
            if key == "mapbox_satellite" and MAPBOX_ACCESS_TOKEN:
                try:
                    config["tile_server"] = config["tile_server_template"].replace("{token}", MAPBOX_ACCESS_TOKEN)
                    active_sources[key] = config
                    logger.debug(f"Mapbox source activated with tile server.")
                except Exception as e:
                    logger.error(f"Error processing Mapbox tile server template: {e}", exc_info=True)
            else:
                logger.warning(f"Skipping map source '{config.get('name', key)}' because required token (MAPBOX_ACCESS_TOKEN) is missing.")
        else:
            if config.get("tile_server"):
                active_sources[key] = config
            elif config.get("tile_server_template"):
                config["tile_server"] = config["tile_server_template"]
                active_sources[key] = config
                logger.warning(f"Activated source '{config.get('name', key)}' using template directly as no token required.")
            else:
                logger.warning(f"Skipping map source '{config.get('name', key)}' due to missing tile server URL or template.")

    logger.info(f"Active map sources available for analysis: {list(active_sources.keys())}")
    if not active_sources:
        logger.error("No map sources are active. Analysis cannot proceed. Check configuration and API keys.")
    return active_sources

# --- Analysis Window Class ---
class AnalysisWindow(Toplevel):
    """A dedicated window with controls for the AI analysis process."""
    def __init__(self, parent, start_coords, end_coords):
        super().__init__(parent)
        self.title("AI Path Analysis - Capture & Control")
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        win_x = min(max(0, parent_x + 50), screen_width - ANALYSIS_WINDOW_WIDTH - 20)
        win_y = min(max(0, parent_y + 50), screen_height - ANALYSIS_WINDOW_HEIGHT - 50)
        self.geometry(f"{ANALYSIS_WINDOW_WIDTH}x{ANALYSIS_WINDOW_HEIGHT}+{win_x}+{win_y}")
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self.cancel_analysis) # Use cancel on close
        self.resizable(True, True) # Allow resizing

        # Store coordinates for restart functionality
        self.start_coords = start_coords
        self.end_coords = end_coords

        # State variables
        self.paused = True # Start paused
        self.started = False # Track if Start has been clicked
        self.cancelled = False
        self.step_mode = False
        self.go_back = False    # Flag for Previous Step
        self.back_mode = False  # Flag to track if we're in back navigation mode
        self.skip_map = False   # Flag for Next Map
        self.current_step = 0   # Track current step index (0-based)
        self.total_steps = 0    # Total steps for current source
        self.current_source = "" # Current map source being processed

# Coordinates already stored above

        # --- Layout ---
        # Main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Left Sidebar (Controls)
        control_frame = ttk.Frame(main_frame, width=CONTROL_SIDEBAR_WIDTH, relief=tk.SUNKEN, borderwidth=1)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5,0), pady=5)
        control_frame.pack_propagate(False) # Prevent sidebar from resizing to content

        # Right Sidebar (Map Settings)
        self.settings_frame = ttk.Frame(main_frame, width=CONTROL_SIDEBAR_WIDTH, relief=tk.SUNKEN, borderwidth=1)
        self.settings_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(0,5), pady=5)
        self.settings_frame.pack_propagate(False) # Prevent sidebar from resizing to content

        # Center Area (Map)
        map_frame = ttk.Frame(main_frame)
        map_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        # --- End Layout ---

        logger.info(f"Creating AI Analysis window ({ANALYSIS_WINDOW_WIDTH}x{ANALYSIS_WINDOW_HEIGHT})")
        try:
            # --- Map Widget ---
            # Calculate width accounting for both sidebars
            map_width = ANALYSIS_WINDOW_WIDTH - (CONTROL_SIDEBAR_WIDTH * 2) - 30
            self.map_widget = tkintermapview.TkinterMapView(map_frame,
                                                           width=map_width,
                                                           height=ANALYSIS_WINDOW_HEIGHT - 20,
                                                           corner_radius=0)
            self.map_widget.pack(fill="both", expand=True)
            # Disable map's internal zoom controls
            self.map_widget.mouse_wheel_zoom = False

            # Add a timer to periodically check and update the zoom level
            def check_zoom_level():
                if self.winfo_exists() and hasattr(self, 'map_widget'):
                    current_zoom = self.map_widget.zoom
                    # Check if zoom has changed and analysis hasn't started
                    if (hasattr(self, 'last_zoom') and self.last_zoom != current_zoom and
                        (not hasattr(self, 'started') or not self.started)):
                        # Zoom has changed and analysis hasn't started, redraw polygons
                        self.draw_capture_area_polygons()
                    # Store current zoom for next comparison
                    self.last_zoom = current_zoom
                    # Update the zoom display
                    self._update_zoom_display()
                    self.after(500, check_zoom_level)

            # Start the periodic zoom check
            self.after(500, check_zoom_level)
            logger.info("Analysis map widget created successfully.")

            # Create a variable to track current zoom level
            self.current_zoom_var = tk.StringVar(value=f"Current Zoom: {self.map_widget.zoom}")

            # Setup map change callback to update zoom display
            self.map_widget.add_right_click_menu_command("Get Current Zoom",
                                                       self._update_zoom_display,
                                                       pass_coords=False)

            # We're using a periodic check instead of event bindings
            # This is more reliable across different versions of tkintermapview

            # --- Sidebar Controls ---
            # Status Labels
            ttk.Label(control_frame, text="Status:", font=("TkDefaultFont", 10, "bold")).pack(pady=(5,0), anchor="w", padx=5)
            self.status_label = ttk.Label(control_frame, text="Ready (Paused)", wraplength=CONTROL_SIDEBAR_WIDTH-10)
            self.status_label.pack(pady=2, anchor="w", padx=5)
            self.source_label = ttk.Label(control_frame, text="Source: -", wraplength=CONTROL_SIDEBAR_WIDTH-10)
            self.source_label.pack(pady=(0,5), anchor="w", padx=5)
            self.step_label = ttk.Label(control_frame, text="Step: -/-", wraplength=CONTROL_SIDEBAR_WIDTH-10)
            self.step_label.pack(pady=(0,10), anchor="w", padx=5)

            # Action Buttons - One button per row
            self.start_pause_button = ttk.Button(control_frame, text="Start", command=self.toggle_start_pause)
            self.start_pause_button.pack(fill="x", pady=3, padx=5)

            # Navigation buttons - each on its own row
            self.prev_button = ttk.Button(control_frame, text="Previous Step", command=self.previous_step, state=tk.DISABLED)
            self.prev_button.pack(fill="x", pady=3, padx=5)

            self.next_button = ttk.Button(control_frame, text="Next Step", command=self.next_step, state=tk.DISABLED)
            self.next_button.pack(fill="x", pady=3, padx=5)

            self.next_map_button = ttk.Button(control_frame, text="Next Map", command=self.next_map, state=tk.NORMAL)
            self.next_map_button.pack(fill="x", pady=3, padx=5)

            # Separator
            ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10, padx=5)

            # Zoom Buttons - each on its own row
            self.zoom_in_button = ttk.Button(control_frame, text="Zoom In", command=self.zoom_in)
            self.zoom_in_button.pack(fill="x", pady=3, padx=5)

            self.zoom_out_button = ttk.Button(control_frame, text="Zoom Out", command=self.zoom_out)
            self.zoom_out_button.pack(fill="x", pady=3, padx=5)

            # Separator
            ttk.Separator(control_frame, orient="horizontal").pack(fill="x", pady=10, padx=5)

            # Restart Button (above Cancel)
            self.restart_button = ttk.Button(control_frame, text="Restart Analysis", command=self.restart_analysis)
            self.restart_button.pack(side=tk.BOTTOM, fill="x", pady=5, padx=5)

            # Cancel Button (at the bottom)
            self.cancel_button = ttk.Button(control_frame, text="Cancel Analysis", command=self.cancel_analysis)
            self.cancel_button.pack(side=tk.BOTTOM, fill="x", pady=5, padx=5)

            # --- Right Sidebar (Map Settings) ---
            self._setup_map_settings_sidebar()

        except Exception as e:
            logger.error(f"Failed to create TkinterMapView or controls in AnalysisWindow: {e}", exc_info=True)
            self.destroy()
            raise

        self.update_idletasks() # Ensure layout is calculated
        self._update_button_states() # Set initial states (Start enabled, others disabled/correct)

    def update_status(self, status_msg="", source_msg="", step_idx=-1, total_steps=-1):
        """Updates the status labels in the sidebar."""
        if not self.winfo_exists(): return
        def do_update():
            if self.winfo_exists():
                if status_msg: self.status_label.config(text=status_msg)
                if source_msg: self.source_label.config(text=f"Source: {source_msg}")
                if step_idx >= 0 and total_steps > 0:
                    self.step_label.config(text=f"Step: {step_idx+1}/{total_steps}")
                    # Update step button state based on index
                    self.current_step = step_idx
                    self.total_steps = total_steps
                    self._update_button_states() # Update button enable/disable state
                elif step_idx == -1 and total_steps == -1: # Clear step info
                    self.step_label.config(text="Step: -/-")
        self.after(0, do_update) # Schedule in main thread

    def toggle_start_pause(self):
        """Handles Start/Pause/Continue button clicks."""
        if not self.started:
            # Apply global settings before starting to ensure they're used for the analysis
            if hasattr(self, 'global_steps_var') and hasattr(self, 'global_zoom_var'):
                try:
                    # Get and validate the global settings
                    steps = int(self.global_steps_var.get())
                    zoom_level = int(self.global_zoom_var.get())

                    if (5 <= steps <= 50) and (1 <= zoom_level <= 22):
                        # Settings are valid, apply them
                        logger.info(f"Applying global settings before start: Steps={steps}, Zoom={zoom_level}")

                        # Force regeneration of capture points with the current settings
                        if hasattr(self, 'capture_points'):
                            delattr(self, 'capture_points')

                        # Generate new capture points with current settings
                        self._generate_capture_points()

                        # Apply zoom level to current map view
                        if hasattr(self, 'map_widget'):
                            self.map_widget.set_zoom(zoom_level)
                    else:
                        logger.warning("Invalid global settings, using existing capture points")
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Could not apply global settings before start: {e}")

            # Now start the analysis
            self.started = True
            self.paused = False
            logger.info("AI Analysis Started by user.")

            # Hide the polygons when starting the analysis
            if hasattr(self, 'map_widget') and self.map_widget:
                # Ensure we have capture points for camera positioning
                if not hasattr(self, 'capture_points'):
                    # Generate the capture points if they don't exist yet
                    self._generate_capture_points()

                self.map_widget.delete_all_polygon()
                logger.info("Removed capture area polygons for analysis start")

            self._update_button_states()
        else:
            self.toggle_pause()

    def _update_button_states(self):
        """Internal method to update button states based on current flags."""
        if not self.winfo_exists(): return

        is_paused_state = self.paused
        is_cancelled_state = self.cancelled
        is_started_state = self.started

        if not is_started_state:
            start_pause_text = "Start"
        elif is_paused_state:
            start_pause_text = "Continue"
        else:
            start_pause_text = "Pause"

        # Enable Next Step only when paused AND started
        next_state = tk.NORMAL if (is_paused_state and is_started_state) else tk.DISABLED
        # Enable Prev Step only when paused AND started AND not on the first step
        prev_state = tk.NORMAL if (is_paused_state and is_started_state and self.current_step > 0) else tk.DISABLED
        # Enable Next Map always unless cancelled
        next_map_state = tk.NORMAL

        cancel_text = "Cancel Analysis" if not is_cancelled_state else "Cancelled"
        # Disable all interactive buttons if cancelled
        global_state = tk.DISABLED if is_cancelled_state else tk.NORMAL

        widgets_to_update = [
            (self.start_pause_button, {"text": start_pause_text, "state": global_state}),
            (self.prev_button, {"state": prev_state if not is_cancelled_state else tk.DISABLED}),
            (self.next_button, {"state": next_state if not is_cancelled_state else tk.DISABLED}),
            (self.next_map_button, {"state": next_map_state if not is_cancelled_state else tk.DISABLED}),
            (self.restart_button, {"state": global_state}), # Restart always enabled unless cancelled
            (self.cancel_button, {"text": cancel_text, "state": global_state}),
            (self.zoom_in_button, {"state": global_state}), # Zoom always enabled unless cancelled
            (self.zoom_out_button, {"state": global_state}) # Zoom always enabled unless cancelled
        ]

        for widget, config in widgets_to_update:
            try:
                if widget and widget.winfo_exists():
                    widget.config(**config)
            except tk.TclError:
                pass
            except Exception as e:
                logger.error(f"Error updating button {widget}: {e}")

    def toggle_pause(self):
        """Toggles the paused state (only if started) and updates buttons."""
        if not self.started: return
        self.paused = not self.paused
        logger.info(f"AI Analysis Paused state set to: {self.paused}")
        if not self.paused:
            self.step_mode = False
        self._update_button_states()

    def next_step(self):
        """Signals the capture loop to proceed by one step."""
        if self.paused and self.started:
            logger.info("AI Analysis: Next Step requested.")
            self.step_mode = True
            self.back_mode = False  # Clear back mode flag when moving forward
            self.paused = False
            self._update_button_states()

    def previous_step(self):
        """Signals the capture loop to go back one step."""
        if self.paused and self.started and self.current_step > 0:
            logger.info("AI Analysis: Previous Step requested.")
            self.go_back = True
            self.back_mode = True  # Set back mode flag to prevent redoing captures
            self.paused = False # Allow loop to run once to process go_back
            self._update_button_states()

    def next_map(self):
        """Signals the main analysis loop to skip to the next map source."""
        if not self.cancelled:
            logger.info("AI Analysis: Next Map requested.")
            self.skip_map = True
            self.paused = False # Ensure loop continues to check skip_map flag
            # Update UI to show we're skipping
            self.update_status(status_msg="Skipping to next map source...")
            self._update_button_states()

    def cancel_analysis(self):
        """Sets the cancelled flag, disables controls, and closes window."""
        if not self.cancelled:
            logger.warning("AI Analysis Cancelled by user.")
            self.cancelled = True
            self._update_button_states()
            self.after(100, self.destroy)

    def restart_analysis(self):
        """Restarts the analysis by closing and reopening the window."""
        logger.info("AI Analysis: Restarting analysis.")
        # Store the current coordinates
        start_coords = self.start_coords
        end_coords = self.end_coords
        parent = self.master

        # Close the current window
        self.destroy()

        # Create a new analysis window with the same coordinates
        new_window = AnalysisWindow(parent, start_coords, end_coords)

        # Start the analysis in the new window
        threading.Thread(target=run_multi_source_analysis,
                         args=(None, start_coords, end_coords, new_window),
                         daemon=True).start()

    def setup_map(self):
        """Draws markers, path and sets initial zoom."""
        if not self.winfo_exists() or not hasattr(self, 'map_widget'):
            logger.warning("setup_map called but window or map_widget doesn't exist.")
            return
        logger.info("Setting up analysis map with path and markers.")

        try:
            self.map_widget.delete_all_marker()
            self.map_widget.delete_all_path()
            self.map_widget.delete_all_polygon()

            # Add markers for start and end points
            self.map_widget.set_marker(
                self.start_coords[0], self.start_coords[1],
                text="Start", marker_color_outside="blue", text_color="blue"
            )
            self.map_widget.set_marker(
                self.end_coords[0], self.end_coords[1],
                text="End", marker_color_outside="red", text_color="red"
            )

            # Draw the path line
            self.map_widget.set_path(
                [self.start_coords, self.end_coords],
                color="#FFFF00", width=3
            )

            # Draw capture area polygons only if analysis hasn't started yet
            if not hasattr(self, 'started') or not self.started:
                self.draw_capture_area_polygons()
            else:
                logger.debug("Skipping polygon drawing because analysis has already started")

            lat_min = min(self.start_coords[0], self.end_coords[0])
            lat_max = max(self.start_coords[0], self.end_coords[0])
            lon_min = min(self.start_coords[1], self.end_coords[1])
            lon_max = max(self.start_coords[1], self.end_coords[1])
            lat_span = max(abs(lat_max - lat_min), 0.001)
            lon_span = max(abs(lon_max - lon_min), 0.001)
            padding_factor = 0.15
            lat_min_bound = lat_min - lat_span * padding_factor
            lat_max_bound = lat_max + lat_span * padding_factor
            lon_min_bound = lon_min - lon_span * padding_factor
            lon_max_bound = lon_max + lon_span * padding_factor

            top_left = (lat_max_bound, lon_min_bound)
            bottom_right = (lat_min_bound, lon_max_bound)

            logger.debug(f"Fitting bounding box: TL={top_left}, BR={bottom_right}")
            if self.map_widget.fit_bounding_box(top_left, bottom_right):
                initial_zoom = self.map_widget.zoom
                logger.info(f"Analysis map initial overview zoom set to: {initial_zoom}")
            else:
                logger.warning("fit_bounding_box failed, trying center position fallback.")
                center_lat = (self.start_coords[0] + self.end_coords[0]) / 2
                center_lon = (self.start_coords[1] + self.end_coords[1]) / 2
                self.map_widget.set_position(center_lat, center_lon)
                self.map_widget.set_zoom(10)
                logger.info("Set fallback zoom to 10")

            self.update()
            time.sleep(1.0)

            # Initialize the current source for polygon drawing
            if not hasattr(self, 'current_source') or not self.current_source:
                # Set a default source if none is set
                active_sources = get_active_map_sources()
                if active_sources:
                    self.current_source = next(iter(active_sources.keys()))

            # Schedule polygon drawing after a short delay to ensure map is fully initialized
            # but only if analysis hasn't started yet
            if not hasattr(self, 'started') or not self.started:
                # Use a lambda to check again at the time of execution
                self.after(1000, lambda: self._safe_draw_polygons())
            else:
                logger.debug("Skipping scheduled polygon drawing because analysis has already started")

            logger.info("Analysis map setup complete.")
        except Exception as e:
            logger.error(f"Error during analysis map setup: {e}", exc_info=True)

    def show_and_update(self):
        """Make window visible and update it."""
        if not self.winfo_exists(): return
        self.deiconify() # Make visible if hidden
        self.lift()      # Bring to front
        self.update()    # Process pending events
        logger.debug("Analysis window shown and updated.")

    def zoom_in(self):
        if self.map_widget and self.winfo_exists():
            try:
                current_zoom = self.map_widget.zoom
                target_zoom = current_zoom + 1
                if target_zoom <= 22:
                    self.map_widget.set_zoom(target_zoom)
                    logger.debug(f"Zoomed in to {target_zoom}")
                    self._update_zoom_display()
                    # Redraw the capture area polygons with the new zoom level
                    self.draw_capture_area_polygons()
                else:
                    logger.debug(f"Already at max zoom ({current_zoom})")
            except Exception as e:
                logger.error(f"Error zooming in: {e}")

    def zoom_out(self):
        if self.map_widget and self.winfo_exists():
            try:
                current_zoom = self.map_widget.zoom
                target_zoom = current_zoom - 1
                if target_zoom >= 1:
                    self.map_widget.set_zoom(target_zoom)
                    logger.debug(f"Zoomed out to {target_zoom}")
                    self._update_zoom_display()
                    # Redraw the capture area polygons with the new zoom level
                    self.draw_capture_area_polygons()
                else:
                    logger.debug("Already at min zoom.")
            except Exception as e:
                logger.error(f"Error zooming out: {e}")

    def _safe_draw_polygons(self):
        """Safely draws polygons only if analysis hasn't started."""
        if not hasattr(self, 'started') or not self.started:
            self.draw_capture_area_polygons()
        else:
            logger.debug("Skipping safe polygon draw because analysis has already started")

    def _update_zoom_display(self):
        """Updates the zoom level display."""
        if hasattr(self, 'map_widget') and self.map_widget and self.winfo_exists():
            try:
                current_zoom = self.map_widget.zoom
                self.current_zoom_var.set(f"Current Zoom: {current_zoom}")
            except Exception as e:
                logger.error(f"Error updating zoom display: {e}")

    def _generate_capture_points(self):
        """Generates the capture points along the path based on current settings.
        These points will be used for camera positioning during analysis.
        """
        # Get the number of steps from the UI settings
        num_steps = 15  # Default

        # Try to get the number of steps from the global settings
        if hasattr(self, 'global_steps_var'):
            try:
                user_steps = int(self.global_steps_var.get())
                if 5 <= user_steps <= 50:  # Reasonable range check
                    num_steps = user_steps
            except (ValueError, AttributeError):
                pass

        # Calculate path points
        self.capture_points = []
        for i in range(num_steps + 1):
            t = i / max(1, num_steps)
            lat = self.start_coords[0] + t * (self.end_coords[0] - self.start_coords[0])
            lon = self.start_coords[1] + t * (self.end_coords[1] - self.start_coords[1])
            self.capture_points.append((lat, lon))

        logger.info(f"Generated {len(self.capture_points)} capture points for analysis")
        return self.capture_points

    def draw_capture_area_polygons(self):
        """Draws polygons representing the image capture areas along the path."""
        # Skip polygon drawing if analysis has started
        if hasattr(self, 'started') and self.started:
            logger.debug("Skipping polygon drawing because analysis has already started")
            return

        if not hasattr(self, 'map_widget') or not self.map_widget:
            return

        # Make sure the map widget is fully initialized
        try:
            # Check if the map widget has a position set
            position = self.map_widget.get_position()
            if not position or len(position) != 2:
                logger.debug("Map position not set yet, skipping polygon drawing")
                return
        except Exception as e:
            logger.debug(f"Map widget not ready for polygon drawing: {e}")
            return

        try:
            # Clear existing polygons
            self.map_widget.delete_all_polygon()

            # Generate the capture points if needed
            if not hasattr(self, 'capture_points') or not self.capture_points:
                self._generate_capture_points()

            # Use the capture points for drawing polygons
            path_points = self.capture_points

            # Get map dimensions
            map_width = self.map_widget.winfo_width()
            map_height = self.map_widget.winfo_height()

            # Get current zoom level
            current_zoom = self.map_widget.zoom

            # Get the target zoom level for image capture
            # This is the zoom level that will be used during actual image capture
            target_zoom = 19  # Default for satellite imagery

            # Try to get the target zoom level from the current source settings
            if hasattr(self, 'current_source') and self.current_source and hasattr(self, 'map_settings'):
                if self.current_source in self.map_settings:
                    try:
                        zoom_var = self.map_settings[self.current_source].get('zoom_var')
                        if zoom_var:
                            user_zoom = int(zoom_var.get())
                            if 1 <= user_zoom <= 22:  # Valid zoom range
                                target_zoom = user_zoom
                    except (ValueError, AttributeError):
                        pass

            logger.debug(f"Drawing capture polygons for target zoom level: {target_zoom}")

            # We need to calculate the size of the capture area at the target zoom level (19)
            # The size of the visible area changes with zoom level
            # At each zoom level increase, the visible area is reduced by half in each dimension

            # First, calculate the current degrees per pixel
            try:
                # Get the current map bounds
                upper_left = self.map_widget.convert_canvas_coords_to_decimal_coords(-map_width/2, -map_height/2)
                lower_right = self.map_widget.convert_canvas_coords_to_decimal_coords(map_width/2, map_height/2)

                # Calculate the degrees per pixel at the current zoom level
                current_degrees_per_pixel_lat = (lower_right[0] - upper_left[0]) / map_height
                current_degrees_per_pixel_lon = (lower_right[1] - upper_left[1]) / map_width

                # Adjust for the difference between current zoom and target zoom
                # Each zoom level difference means a factor of 2 in scale
                zoom_difference = target_zoom - current_zoom
                # Limit the zoom difference to prevent math domain errors with very large scale factors
                zoom_difference = max(-10, min(10, zoom_difference))  # Limit to reasonable range
                scale_factor = 2 ** zoom_difference

                # Calculate the degrees per pixel at the target zoom level
                degrees_per_pixel_lat = current_degrees_per_pixel_lat / scale_factor
                degrees_per_pixel_lon = current_degrees_per_pixel_lon / scale_factor

                logger.debug(f"Current zoom: {current_zoom}, Target zoom: {target_zoom}, Scale factor: {scale_factor}")
                logger.debug(f"Degrees per pixel at target zoom - Lat: {degrees_per_pixel_lat}, Lon: {degrees_per_pixel_lon}")

                # Draw a polygon for each capture point
                for i, (lat, lon) in enumerate(path_points):
                    # Calculate the corners of the capture area in geo coordinates
                    # based on the current scale
                    top_left_geo = (lat + degrees_per_pixel_lat * (-map_height/2), lon + degrees_per_pixel_lon * (-map_width/2))
                    top_right_geo = (lat + degrees_per_pixel_lat * (-map_height/2), lon + degrees_per_pixel_lon * (map_width/2))
                    bottom_right_geo = (lat + degrees_per_pixel_lat * (map_height/2), lon + degrees_per_pixel_lon * (map_width/2))
                    bottom_left_geo = (lat + degrees_per_pixel_lat * (map_height/2), lon + degrees_per_pixel_lon * (-map_width/2))

                    # Create polygon corners (clockwise from top-left)
                    polygon_points = [
                        top_left_geo,
                        top_right_geo,
                        bottom_right_geo,
                        bottom_left_geo
                    ]

                    # Add the polygon to the map with more visible colors
                    # First polygon is red, last polygon is blue, others are green
                    if i == 0:
                        fill_color = "#FFCCCC"  # Light red
                        outline_color = "#FF0000"  # Red
                    elif i == len(path_points) - 1:
                        fill_color = "#CCCCFF"  # Light blue
                        outline_color = "#0000FF"  # Blue
                    else:
                        fill_color = "#CCFFCC"  # Light green
                        outline_color = "#00FF00"  # Green

                    self.map_widget.set_polygon(polygon_points,
                                               fill_color=fill_color,
                                               outline_color=outline_color,
                                               border_width=2,
                                               name=f"capture_area_{i}")
            except Exception as e:
                logger.error(f"Error calculating map scale: {e}")
                # Fallback to the old method if the new approach fails
                for i, (lat, lon) in enumerate(path_points):
                    # Use a simple approximation
                    degrees_per_pixel = 0.0025 / (2 ** current_zoom)
                    capture_width_deg = degrees_per_pixel * map_width * 0.8
                    capture_height_deg = degrees_per_pixel * map_height * 0.8

                    half_width = capture_width_deg / 2
                    half_height = capture_height_deg / 2

                    polygon_points = [
                        (lat + half_height, lon - half_width),  # Top-left
                        (lat + half_height, lon + half_width),  # Top-right
                        (lat - half_height, lon + half_width),  # Bottom-right
                        (lat - half_height, lon - half_width)   # Bottom-left
                    ]

                    # Add the polygon to the map with more visible colors
                    if i == 0:
                        fill_color = "#FFCCCC"  # Light red
                        outline_color = "#FF0000"  # Red
                    elif i == len(path_points) - 1:
                        fill_color = "#CCCCFF"  # Light blue
                        outline_color = "#0000FF"  # Blue
                    else:
                        fill_color = "#CCFFCC"  # Light green
                        outline_color = "#00FF00"  # Green

                    self.map_widget.set_polygon(polygon_points,
                                               fill_color=fill_color,
                                               outline_color=outline_color,
                                               border_width=2,
                                               name=f"capture_area_{i}")

            logger.info(f"Drew {len(path_points)} capture area polygons")
        except Exception as e:
            logger.error(f"Error drawing capture area polygons: {e}", exc_info=True)

    def _on_global_settings_changed(self):
        """Called when global settings are changed by the user."""
        # Only redraw polygons if the values are valid and analysis hasn't started
        if hasattr(self, 'started') and self.started:
            logger.debug("Skipping polygon redraw because analysis has already started")
            return

        try:
            # Check if steps value is valid
            steps = int(self.global_steps_var.get())
            if not (5 <= steps <= 50):
                return  # Invalid steps value, don't redraw

            # Check if zoom value is valid
            zoom = int(self.global_zoom_var.get())
            if not (1 <= zoom <= 22):
                return  # Invalid zoom value, don't redraw

            # Regenerate capture points with new number of steps
            if hasattr(self, 'capture_points'):
                delattr(self, 'capture_points')  # Force regeneration with new steps value

            # Redraw the polygons with the new settings
            self.draw_capture_area_polygons()

            logger.debug(f"Polygons redrawn due to settings change: Steps={steps}, Zoom={zoom}")
        except (ValueError, AttributeError):
            # Invalid input, ignore
            pass

    def _apply_global_settings(self):
        """Applies the global settings to all map sources and the current view."""
        try:
            # Get the global settings
            try:
                steps = int(self.global_steps_var.get())
                zoom_level = int(self.global_zoom_var.get())

                # Validate ranges
                if not (5 <= steps <= 50):
                    self.update_status(status_msg="Error: Steps must be between 5 and 50")
                    return

                if not (1 <= zoom_level <= 22):
                    self.update_status(status_msg="Error: Zoom must be between 1 and 22")
                    return
            except (ValueError, AttributeError) as e:
                self.update_status(status_msg="Error: Invalid settings values")
                logger.warning(f"Could not parse global settings: {e}")
                return

            # Apply zoom level to current map view
            self.map_widget.set_zoom(zoom_level)
            logger.info(f"Applied zoom level {zoom_level} to current map")

            # Redraw the capture area polygons with the new settings, but only if analysis hasn't started
            if not hasattr(self, 'started') or not self.started:
                # Regenerate capture points with new number of steps
                if hasattr(self, 'capture_points'):
                    delattr(self, 'capture_points')  # Force regeneration with new steps value

                self.draw_capture_area_polygons()
            else:
                logger.debug("Skipping polygon redraw because analysis has already started")

            # Show confirmation
            self.update_status(status_msg=f"Global settings applied: Steps={steps}, Zoom={zoom_level}")
            logger.info(f"Applied global settings: Steps={steps}, Zoom={zoom_level}")
        except Exception as e:
            logger.error(f"Error applying global settings: {e}")
            self.update_status(status_msg="Error applying settings")

    def _apply_source_settings(self, source_key):
        """Applies the settings for a specific map source."""
        if not hasattr(self, 'map_settings') or source_key not in self.map_settings:
            return

        try:
            # Get the settings for this source
            settings = self.map_settings[source_key]

            # Update the zoom level if we're currently viewing this source
            if hasattr(self, 'current_source') and self.current_source == source_key:
                try:
                    zoom_var = settings.get('zoom_var')
                    if zoom_var:
                        zoom_level = int(zoom_var.get())
                        if 1 <= zoom_level <= 22:
                            self.map_widget.set_zoom(zoom_level)
                            logger.info(f"Applied zoom level {zoom_level} to current map")

                    # Update the current source so the polygons use the right settings
                    self.current_source = source_key

                    # Redraw the capture area polygons with the new settings
                    self.draw_capture_area_polygons()

                except (ValueError, AttributeError) as e:
                    logger.warning(f"Could not apply zoom level: {e}")

            # Show confirmation
            self.update_status(status_msg=f"Settings applied for {source_key}")
            logger.info(f"Applied settings for source {source_key}")
        except Exception as e:
            logger.error(f"Error applying source settings: {e}")

    def _setup_map_settings_sidebar(self):
        """Sets up the right sidebar with map settings."""
        if not hasattr(self, 'settings_frame') or not self.settings_frame:
            return

        # Title
        ttk.Label(self.settings_frame, text="Map Settings", font=("TkDefaultFont", 10, "bold")).pack(pady=(5,10), padx=5)

        # Create a global settings section at the top
        global_settings_frame = ttk.LabelFrame(self.settings_frame, text="Global Settings")
        global_settings_frame.pack(fill="x", padx=5, pady=5)

        # Global number of steps input
        ttk.Label(global_settings_frame, text="Number of Steps:").pack(anchor="w", padx=5, pady=(5,0))
        self.global_steps_var = tk.StringVar(value="15")
        steps_entry = ttk.Entry(global_settings_frame, textvariable=self.global_steps_var, width=10)
        steps_entry.pack(fill="x", padx=5, pady=(0,5))

        # Add trace to update polygons when steps value changes
        self.global_steps_var.trace_add("write", lambda *_: self._on_global_settings_changed())

        # Global zoom level input
        ttk.Label(global_settings_frame, text="Zoom Level (1-22):").pack(anchor="w", padx=5, pady=(5,0))
        self.global_zoom_var = tk.StringVar(value="19")  # Default to 19 for satellite imagery
        zoom_entry = ttk.Entry(global_settings_frame, textvariable=self.global_zoom_var, width=10)
        zoom_entry.pack(fill="x", padx=5, pady=(0,5))

        # Add trace to update polygons when zoom value changes
        self.global_zoom_var.trace_add("write", lambda *_: self._on_global_settings_changed())

        # Add apply button for global settings
        apply_button = ttk.Button(global_settings_frame, text="Apply to All Sources",
                                command=self._apply_global_settings)
        apply_button.pack(fill="x", padx=5, pady=5)

        # Add a separator
        ttk.Separator(self.settings_frame, orient="horizontal").pack(fill="x", pady=10, padx=5)

        # Map Sources section
        ttk.Label(self.settings_frame, text="Map Sources", font=("TkDefaultFont", 10, "bold")).pack(pady=(5,10), padx=5)

        # Get active map sources
        active_sources = get_active_map_sources()

        # Create a frame for each map source (just to display info, not for settings)
        self.map_settings = {}
        for source_key, source_config in active_sources.items():
            source_name = source_config.get("name", source_key)

            # Create a frame for this source
            source_frame = ttk.LabelFrame(self.settings_frame, text=source_name)
            source_frame.pack(fill="x", padx=5, pady=5)

            # Display max zoom level for this source
            max_zoom = source_config.get("max_zoom", 22)
            ttk.Label(source_frame, text=f"Max Zoom Level: {max_zoom}").pack(anchor="w", padx=5, pady=5)

            # Store source info for later access
            self.map_settings[source_key] = {
                "steps_var": self.global_steps_var,  # Use global settings for all sources
                "zoom_var": self.global_zoom_var    # Use global settings for all sources
            }

        # Add a separator
        ttk.Separator(self.settings_frame, orient="horizontal").pack(fill="x", pady=10, padx=5)

        # Current zoom level display at the bottom
        self.zoom_display = ttk.Label(self.settings_frame, textvariable=self.current_zoom_var)
        self.zoom_display.pack(side=tk.BOTTOM, pady=10, padx=5)

        # Update the zoom display initially
        self._update_zoom_display()

# --- Helper Functions ---

# --- Core Analysis Logic ---

def capture_images_for_source(analysis_window, path_points, source_config):
    """Captures images along the path using the AnalysisWindow, handling pause/step/cancel."""
    images_data = []
    is_cancelled = False

    if not analysis_window or not analysis_window.winfo_exists():
        logger.error("Analysis window is not valid at start of image capture.")
        return [], True

    map_widget = analysis_window.map_widget
    source_name = source_config.get("name", "Unknown Source")
    source_key = source_config.get("source_key", "")
    tile_server = source_config.get("tile_server")

    # Store current source in the analysis window for settings application
    if hasattr(analysis_window, 'current_source'):
        analysis_window.current_source = source_key

        # Only redraw polygons if analysis hasn't started yet
        if not hasattr(analysis_window, 'started') or not analysis_window.started:
            # Redraw the capture area polygons for the new source
            analysis_window.draw_capture_area_polygons()
        else:
            logger.debug(f"Skipping polygon redraw for {source_key} because analysis has already started")

    # Get source-specific settings
    max_source_zoom = source_config.get("max_zoom", 18)
    zoom_offset = source_config.get("zoom_offset", 0)  # Source-specific zoom adjustment
    load_delay = source_config.get("load_delay", MAP_CAPTURE_DELAY_SECONDS)  # Source-specific delay

    # Set default zoom level based on source
    if source_key == "mapbox_satellite":
        # Default to zoom level 19 for Mapbox
        capture_zoom_level = 19
        logger.info("Using default zoom level 19 for Mapbox Satellite")
    else:
        # Default calculation for other sources
        capture_zoom_level = max(1, max_source_zoom - 3 + zoom_offset)

    # Try to get global zoom level
    if hasattr(analysis_window, 'global_zoom_var'):
        try:
            user_zoom = int(analysis_window.global_zoom_var.get())
            if 1 <= user_zoom <= max_source_zoom:  # Valid zoom range check
                capture_zoom_level = user_zoom
                logger.info(f"Using global zoom level: {capture_zoom_level}")
        except (ValueError, AttributeError) as e:
            logger.warning(f"Could not parse global zoom level, using default: {e}")

    analysis_window.total_steps = len(path_points) # Update total steps

    logger.info(f"Starting image capture for source: {source_name} (Max Source Zoom: {max_source_zoom}, Capture Zoom: {capture_zoom_level}, Delay: {load_delay}s)")
    analysis_window.update_status(source_msg=source_name)

    if not tile_server:
        logger.error(f"Tile server URL missing for {source_name}.")
        analysis_window.update_status(status_msg=f"Error: Missing URL for {source_name}")
        return [], False

    try:
        logger.debug(f"Setting tile server for {source_name}")

        # For Mapbox, clear the tile cache first to prevent mixed zoom levels
        if "mapbox" in source_name.lower():
            # Access the internal tile cache if possible
            try:
                if hasattr(map_widget, "_tile_image_cache"):
                    map_widget._tile_image_cache.clear()
                    logger.debug("Cleared tile image cache for Mapbox")
            except Exception as cache_err:
                logger.warning(f"Could not clear tile cache: {cache_err}")

        # Set max_zoom for the tile server itself
        map_widget.set_tile_server(tile_server, max_zoom=max_source_zoom)
        analysis_window.show_and_update()

        # Give Mapbox sources extra time to initialize
        if "mapbox" in source_name.lower():
            # Much longer initialization for Mapbox to ensure proper loading
            init_delay = 3.0  # Increased delay
            logger.debug(f"Using extended initialization delay for Mapbox: {init_delay}s")

            # Start with a very low zoom level and gradually increase
            # This forces a complete refresh of the tiles
            start_zoom = 5
            map_widget.set_zoom(start_zoom)
            analysis_window.update()
            time.sleep(0.5)

            # Gradually increase zoom to target level
            for z in range(start_zoom + 1, capture_zoom_level + 1):
                map_widget.set_zoom(z)
                analysis_window.update()
                time.sleep(0.2)

            # Final update at target zoom
            analysis_window.update()
        else:
            init_delay = 0.7

        time.sleep(init_delay)
    except Exception as e:
        logger.error(f"Failed to set tile server for {source_name}: {e}", exc_info=True)
        analysis_window.update_status(status_msg=f"Error setting map for {source_name}")
        return [], False

    # Initial geometry calculation (might be slightly off before first positioning)
    # We will recalculate inside the loop just before capture for accuracy.
    initial_w = map_widget.winfo_width()
    initial_h = map_widget.winfo_height()
    logger.debug(f"Initial map widget dimensions: w={initial_w}, h={initial_h}")
    if initial_w <= 1 or initial_h <= 1:
        logger.error(f"Analysis map widget initial dimensions invalid ({initial_w}x{initial_h}).")
        analysis_window.update_status(status_msg=f"Error: Invalid map size for {source_name}")
        return [], False

    num_points = len(path_points)
    i = 0
    while 0 <= i < num_points:
        # --- Handle Go Back Flag --- START
        if analysis_window.go_back:
            analysis_window.go_back = False
            if i > 0 and len(images_data) >= i:
                try:
                    images_data.pop(i-1)
                    logger.debug(f"Removed image data for step {i} due to 'Previous Step'.")
                except IndexError:
                    logger.warning(f"Could not pop image data for index {i-1}")
            i = max(0, i - 1)
            logger.info(f"Going back to step {i+1}")
            analysis_window.paused = True
            analysis_window.after(0, analysis_window._update_button_states)
            continue
        # --- Handle Go Back Flag --- END

        # Skip capture if we're in back mode and already have this image
        if analysis_window.back_mode and i < len(images_data):
            logger.debug(f"Skipping recapture for step {i+1} in back mode")
            i += 1
            if i >= num_points:
                analysis_window.back_mode = False  # Reset back mode at end
            continue

        # --- Pause/Cancel/Skip Check ---
        while analysis_window.paused and not analysis_window.cancelled and not analysis_window.skip_map:
            if not analysis_window.winfo_exists():
                is_cancelled = True; break
            analysis_window.update_status(status_msg=f"Paused at step {i+1}/{num_points}", step_idx=i, total_steps=num_points)
            analysis_window.update()
            time.sleep(0.1)

        # Check if we need to skip to next map
        if analysis_window.skip_map:
            logger.info(f"Next Map requested during capture at step {i+1}/{num_points}")
            return images_data, False  # Return current images but don't mark as cancelled

        if analysis_window.cancelled or not analysis_window.winfo_exists():
            is_cancelled = True; break
        # --- End Check ---

        lat, lon = path_points[i]
        analysis_window.update_status(status_msg=f"Processing point {i+1}/{num_points}...", step_idx=i, total_steps=num_points)

        logger.debug(f"[{source_name}] Positioning map: ({lat:.6f}, {lon:.6f}), zoom: {capture_zoom_level}")
        try:
            # Position the map at the current point
            map_widget.set_position(lat, lon)
            map_widget.set_zoom(capture_zoom_level) # Use the adjusted zoom level
            analysis_window.update() # Render position change FIRST

            # For Mapbox, use a special loading technique to prevent blocky/glitchy tiles
            if "mapbox" in source_name.lower():
                # Clear any existing tiles to prevent mixed zoom levels
                try:
                    if hasattr(map_widget, "_tile_image_cache"):
                        map_widget._tile_image_cache.clear()
                except Exception:
                    pass

                # First load at a lower zoom level to force proper tile loading
                temp_zoom = max(1, capture_zoom_level - 2)
                map_widget.set_zoom(temp_zoom)
                analysis_window.update()
                time.sleep(0.3)

                # Gradually increase zoom to target level
                mid_zoom = max(1, capture_zoom_level - 1)
                map_widget.set_zoom(mid_zoom)
                analysis_window.update()
                time.sleep(0.3)

                # Then set to the target zoom level
                map_widget.set_zoom(capture_zoom_level)
                analysis_window.update()

                # Force multiple updates to ensure tiles are loaded
                for _ in range(3):
                    analysis_window.update()
                    time.sleep(0.1)

            # Use source-specific delay time
            source_delay = source_config.get("load_delay", MAP_CAPTURE_DELAY_SECONDS)
            logger.debug(f"Waiting {source_delay}s for tiles...")

            # Progressive update approach for smoother tile loading
            start_wait = time.monotonic()
            while time.monotonic() - start_wait < source_delay:
                 if not analysis_window.winfo_exists(): is_cancelled = True; break
                 analysis_window.update() # Full update instead of just idletasks
                 time.sleep(0.05) # Short sleep to yield control
                 if analysis_window.cancelled: is_cancelled = True; break
                 # Check for Next Map request during tile loading
                 if analysis_window.skip_map:
                     logger.info(f"Next Map requested during tile loading at step {i+1}/{num_points}")
                     return images_data, False  # Return current images but don't mark as cancelled
            if is_cancelled: break

        except Exception as e:
            logger.error(f"Error positioning map at step {i+1}: {e}", exc_info=True)
            analysis_window.update_status(status_msg=f"Error positioning map {i+1}", step_idx=i, total_steps=num_points)
            i += 1; continue

        try:
            # Recalculate geometry right before grabbing
            analysis_window.update()
            time.sleep(0.2) # Longer delay after update for better rendering
            x_map = map_widget.winfo_rootx()
            y_map = map_widget.winfo_rooty()
            width_map = map_widget.winfo_width()
            height_map = map_widget.winfo_height()
            if width_map <= 1 or height_map <= 1:
                 logger.warning(f"Recalculated map dimensions invalid ({width_map}x{height_map}) before grab at step {i+1}. Skipping grab.")
                 i += 1; continue

            logger.debug(f"[{source_name}] Capturing screenshot ({width_map}x{height_map}) at {x_map},{y_map}")

            # For Mapbox, ensure all tiles are fully loaded before capture
            if "mapbox" in source_name.lower():
                # Force multiple updates with delays to ensure complete rendering
                for _ in range(5):
                    analysis_window.update()
                    time.sleep(0.1)
                    # Check for Next Map request during final rendering
                    if analysis_window.skip_map:
                        logger.info(f"Next Map requested during final rendering at step {i+1}/{num_points}")
                        return images_data, False

                # Check if we need to redraw the map due to incomplete tiles
                # This is a last resort to fix blocky/glitchy tiles
                try:
                    # Force a tiny zoom change to refresh tiles if needed
                    current_zoom = map_widget.zoom
                    map_widget.set_zoom(current_zoom + 0.01)
                    analysis_window.update()
                    # Check for Next Map request during refresh
                    if analysis_window.skip_map:
                        return images_data, False
                    time.sleep(0.1)
                    map_widget.set_zoom(current_zoom)
                    analysis_window.update()
                    time.sleep(0.2)
                except Exception as e:
                    logger.warning(f"Failed to perform final tile refresh: {e}")

            img = ImageGrab.grab(bbox=(x_map, y_map, x_map + width_map, y_map + height_map))
            buffered = io.BytesIO()
            img.save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

            if len(images_data) <= i:
                 images_data.append({
                     "type": "image",
                     "source": {"type": "base64", "media_type": "image/png", "data": img_base64}
                 })
            else:
                 images_data[i] = {
                      "type": "image",
                     "source": {"type": "base64", "media_type": "image/png", "data": img_base64}
                 }
            logger.debug(f"[{source_name}] Captured image {i+1}.")
        except Exception as capture_err:
            logger.error(f"[{source_name}] Error capturing/encoding image {i+1}: {capture_err}", exc_info=True)
            analysis_window.update_status(status_msg=f"Error capturing image {i+1}", step_idx=i, total_steps=num_points)
            i += 1; continue

        if analysis_window.step_mode:
            logger.info("Step mode: Pausing after capture.")
            analysis_window.step_mode = False
            analysis_window.paused = True
            analysis_window.after(0, analysis_window._update_button_states)

        i += 1

    if is_cancelled:
        logger.warning(f"Image capture for {source_name} cancelled.")
        analysis_window.update_status(status_msg="Capture Cancelled")
        return [], True
    else:
        logger.info(f"Completed image capture for {source_name}. Captured {len(images_data)} images.")
        analysis_window.update_status(status_msg=f"Capture Complete for {source_name}", step_idx=-1, total_steps=-1) # Clear step info
        return images_data, False

def call_llm_for_analysis(images_data, start_coords, end_coords, source_name):
    """Sends images to the LLM and requests JSON analysis."""
    logger.info(f"Sending {len(images_data)} images from {source_name} to Anthropic API.")

    if not ANTHROPIC_API_KEY:
        logger.error("Anthropic API key not found.")
        return {"error": "Anthropic API key not configured."}

    if not images_data:
        logger.warning(f"No images provided for analysis from {source_name}.")
        return {"error": "No images captured for this source."}

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }

    prompt_text = (
        f"Analyze the following sequence of map images ({source_name}) captured along a path.\n"
        f"The approximate start coordinates are {start_coords} and end coordinates are {end_coords}.\n"
        "Identify potential obstructions for a line-of-sight path, focusing on:\n"
        "- Tall buildings\n"
        "- Communication towers (radio, cell, etc.)\n"
        "- High-voltage power lines and their towers\n"
        "- Wind turbines\n"
        "- Large cranes or other tall temporary structures\n"
        "- Significant hills/ridges directly on the path\n"
        "- Dense forest areas potentially tall enough to obstruct\n\n"
        "For each potential obstruction, provide:\n"
        "1. A brief description (e.g., 'tall office building', 'cluster of wind turbines').\n"
        "2. An estimated location relative to the path shown in the image sequence (e.g., 'near start', 'mid-path, slightly left', 'crossing path near end').\n"
        "3. An estimated height category (e.g., 'low', 'medium', 'tall', 'very tall').\n"
        "4. A confidence score (e.g., 'low', 'medium', 'high') for whether it's a likely obstruction.\n\n"
        "Return the results STRICTLY in the following JSON format:\n\n"
        "{\n"
        f"  \"source_name\": \"{source_name}\",\n"
        "  \"analysis_summary\": \"A brief one-sentence summary of the findings.\",\n"
        "  \"potential_obstructions\": [\n"
        "    {\n"
        "      \"description\": \"string\",\n"
        "      \"location_estimate\": \"string\",\n"
        "      \"height_category\": \"string\",\n"
        "      \"confidence\": \"string\"\n"
        "    }\n"
        "    // ... more obstructions\n"
        "  ]\n"
        "}\n\n"
        "If no significant obstructions are found, return an empty 'potential_obstructions' list and state that in the summary.\n"
        "Do not include any text outside the JSON structure."
    )

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": prompt_text}
            ] + images_data
        }
    ]

    payload = {
        "model": "claude-3-5-sonnet-20240620",
        "max_tokens": 2048,
        "messages": messages,
    }

    try:
        response = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=180)
        response.raise_for_status()
        result = response.json()
        logger.debug(f"Anthropic API raw response for {source_name}: {result}")

        json_string = "{}"
        if result.get("content") and isinstance(result["content"], list) and len(result["content"]) > 0:
             if result["content"][0].get("type") == "text":
                json_string = result["content"][0].get("text", "{}")

        if json_string.strip().startswith("```json"):
            json_string = json_string.strip()[7:-3].strip()
        elif json_string.strip().startswith("```"):
            json_string = json_string.strip()[3:-3].strip()

        try:
            analysis_json = json.loads(json_string)
            logger.info(f"AI analysis for {source_name} successful and parsed as JSON.")
            return analysis_json
        except json.JSONDecodeError as json_err:
            logger.error(f"Failed to parse LLM response as JSON for {source_name}: {json_err}")
            logger.error(f"LLM Raw (cleaned) Output: {json_string}")
            return {"error": f"LLM response was not valid JSON. See logs.", "raw_output": json_string}

    except requests.exceptions.RequestException as api_err:
        logger.error(f"Anthropic API request failed for {source_name}: {api_err}", exc_info=True)
        error_msg = f"Error: API request failed for {source_name}. Check logs."
        if hasattr(api_err, 'response') and api_err.response is not None:
             error_msg = f"Error: API request for {source_name} failed with status {api_err.response.status_code}. Check logs."
        return {"error": error_msg}
    except Exception as e:
         logger.error(f"An unexpected error occurred during API call for {source_name}: {e}", exc_info=True)
         return {"error": f"Error during API call for {source_name}: {e}. Check logs."}

def run_multi_source_analysis(root_window, start_coords, end_coords, existing_window=None):
    """Orchestrates the analysis across multiple map sources in a dedicated window.

    Args:
        root_window: The parent window (can be None if existing_window is provided)
        start_coords: Tuple of (latitude, longitude) for the start point
        end_coords: Tuple of (latitude, longitude) for the end point
        existing_window: Optional existing AnalysisWindow instance
    """
    logger.info("Starting multi-source AI visual path analysis with dedicated window.")

    if not start_coords or not end_coords:
        logger.error("Start and end coordinates are required for analysis.")
        if root_window:
            root_window.after(0, lambda: messagebox.showerror("Error", "Site coordinates missing for analysis."))
        return

    if not ANTHROPIC_API_KEY:
        logger.error("Anthropic API key is missing.")
        if root_window:
            root_window.after(0, lambda: messagebox.showerror("API Key Error", "Anthropic API key (ANTHROPIC_API_KEY) not found. Please set the environment variable."))
        return

    results = {}
    analysis_successful = False
    analysis_cancelled = False

    try:
        # Use existing window if provided, otherwise create a new one
        analysis_window = existing_window
        if analysis_window is None and root_window is not None:
            try:
                analysis_window = AnalysisWindow(root_window, start_coords, end_coords)
                logger.info("Analysis window created.")
            except Exception as window_err:
                logger.error(f"Failed to create Analysis Window: {window_err}", exc_info=True)
                if root_window:
                    root_window.after(0, lambda: messagebox.showerror("UI Error", "Could not create the dedicated map window for analysis."))
                return # Cannot proceed without analysis window

        if analysis_window is None:
            logger.error("No analysis window available.")
            return # Cannot proceed without analysis window

        analysis_window.update_status(status_msg="Initializing...")

        # Get user-specified number of steps if available
        num_steps = 15  # Default value

        # Calculate distance between points
        lat_diff = abs(end_coords[0] - start_coords[0])
        lon_diff = abs(end_coords[1] - start_coords[1])
        distance = math.sqrt(lat_diff**2 + lon_diff**2)

        # Check if we have global settings
        if hasattr(analysis_window, 'global_steps_var'):
            # Try to get user-specified number of steps from global settings
            try:
                user_steps = int(analysis_window.global_steps_var.get())
                if 5 <= user_steps <= 50:  # Reasonable range check
                    num_steps = user_steps
                    logger.info(f"Using global number of steps: {num_steps}")
            except (ValueError, AttributeError) as e:
                logger.warning(f"Could not parse global steps setting, using default: {e}")

        # Fallback to distance-based adjustment if needed
        if num_steps == 15:  # If still using default
            if distance > 0.5:  # For longer paths, add more points
                num_steps = 20
            elif distance < 0.1:  # For very short paths, reduce points
                num_steps = 10

        logger.info(f"Path distance: {distance:.6f} degrees, using {num_steps} steps")
        path_points = []

        # Generate points with slight perpendicular offset to create a wider coverage
        for i in range(num_steps + 1):
            t = i / max(1, num_steps)
            lat = start_coords[0] + t * (end_coords[0] - start_coords[0])
            lon = start_coords[1] + t * (end_coords[1] - start_coords[1])
            path_points.append((lat, lon))

        logger.debug(f"Generated {len(path_points)} points for analysis.")

        logger.info("Setting up analysis map content...")
        analysis_window.setup_map()
        analysis_window.show_and_update()
        analysis_window.update_status(status_msg="Ready (Paused). Click Start.") # Update status after setup
        logger.info("Analysis map setup complete. Process paused. Click Start.")

        active_sources = get_active_map_sources()
        total_sources = len(active_sources)
        if total_sources == 0:
            logger.error("No valid map sources configured or available.")
            analysis_window.update_status(status_msg="Error: No map sources available")
            if root_window:
                root_window.after(0, lambda: messagebox.showerror("Configuration Error", "No map sources configured. Check logs/API keys."))
            raise ValueError("No map sources available")

        source_keys = list(active_sources.keys())
        current_source_index = 0
        while 0 <= current_source_index < total_sources:
            # Check global cancellation flag
            if analysis_cancelled or analysis_window.cancelled:
                analysis_cancelled = True; break

            source_key = source_keys[current_source_index]
            source_config = active_sources[source_key]
            source_name = source_config.get("name", source_key)
            analysis_window.update_status(status_msg=f"Starting: {source_name}", source_msg=source_name, step_idx=-1, total_steps=-1)

            # Use the stored capture points if available, otherwise use the generated path points
            capture_points = path_points
            if hasattr(analysis_window, 'capture_points') and analysis_window.capture_points:
                capture_points = analysis_window.capture_points
                logger.info(f"Using {len(capture_points)} pre-generated capture points from polygon positions")

            images, cancelled_during_capture = capture_images_for_source(
                analysis_window, capture_points, source_config
            )

            # Handle flags set during capture
            if analysis_window.cancelled:
                analysis_cancelled = True

            # Handle Next Map request
            if analysis_window.skip_map:
                analysis_window.skip_map = False # Reset flag
                logger.info(f"Skipping map source '{source_name}' due to user request.")
                results[source_name] = {"status": "Skipped by user"}
                current_source_index += 1
                # Update UI to show we've moved to the next map
                if current_source_index < total_sources:
                    next_source = active_sources[source_keys[current_source_index]].get("name", source_keys[current_source_index])
                    analysis_window.update_status(status_msg=f"Skipped to {next_source}")
                continue # Move to next source

            if cancelled_during_capture:
                logger.warning(f"Capture cancelled for {source_name}.")
                analysis_cancelled = True
                results[source_name] = {"error": "Cancelled during capture."}
                break # Exit outer loop

            if not images:
                logger.warning(f"Failed to capture images for {source_name}.")
                analysis_window.update_status(status_msg=f"Capture failed for {source_name}")
                results[source_name] = {"error": "Failed to capture images."}
                time.sleep(1)
                current_source_index += 1
                continue

            if analysis_window.cancelled: analysis_cancelled = True; break

            # Save images for potential stitching
            stitch_dir = save_images_for_stitching(images, source_name)
            if stitch_dir:
                analysis_window.update_status(status_msg=f"Images saved to {os.path.basename(stitch_dir)}")
                time.sleep(0.5)

            analysis_window.update_status(status_msg=f"Sending {source_name} to AI...")
            analysis_json = call_llm_for_analysis(images, start_coords, end_coords, source_name)
            results[source_name] = analysis_json

            if analysis_window.cancelled:
                analysis_cancelled = True; break

            analysis_window.update_status(status_msg=f"Analysis complete for {source_name}")
            logger.info(f"Finished analysis for {source_name}")
            time.sleep(0.5)

            current_source_index += 1 # Move to next source index

        # End of source loop
        if not analysis_cancelled:
            analysis_window.update_status(status_msg="All sources analyzed.")
            analysis_successful = True

    except Exception as e:
        logger.error(f"Error during multi-source analysis: {e}", exc_info=True)
        if analysis_window and analysis_window.winfo_exists():
            analysis_window.update_status(status_msg=f"Error: {e}")
        should_show_error = True
        if isinstance(e, ValueError) and "No map sources available" in str(e): should_show_error = False
        elif "AnalysisWindow" in str(e): should_show_error = False
        if should_show_error:
            root_window.after(0, lambda msg=str(e): messagebox.showerror("Analysis Error", f"Unexpected error: {msg}"))

    finally:
        # Destroy analysis window safely in main thread
        def safe_destroy(widget):
            try:
                if widget and widget.winfo_exists():
                    widget.destroy()
                    logger.info(f"Widget {widget} destroyed.")
            except Exception as e:
                logger.error(f"Error destroying widget {widget}: {e}", exc_info=True)

        if analysis_window:
            logger.info("Scheduling analysis window destruction.")
            root_window.after(10, lambda w=analysis_window: safe_destroy(w))

    # Display final report (scheduled in main thread)
    def display_final_report():
        report_title = "AI Analysis Report"
        if analysis_cancelled:
            report_title += " (Cancelled)"
        elif not analysis_successful and results:
            report_title += " (Incomplete)"

        if results:
            report = compile_analysis_report(results, report_title)
            if root_window:
                root_window.after(0, lambda: display_analysis_report(root_window, report))
        elif analysis_cancelled:
            if root_window:
                root_window.after(0, lambda: messagebox.showinfo("Analysis Cancelled", "AI path analysis was cancelled."))
        else:
            logger.info("No results generated and not cancelled.")
            if not analysis_successful and root_window:
                root_window.after(0, lambda: messagebox.showwarning("Analysis Failed", "AI analysis failed to produce results. Check logs."))

    if root_window:
        root_window.after(150, display_final_report)
    else:
        # If no root window, call directly
        display_final_report()

def save_images_for_stitching(images_data, source_name):
    """Saves captured images to disk for potential stitching."""
    if not images_data:
        logger.warning(f"No images to save for {source_name}")
        return

    try:
        # Create directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
        stitch_dir = os.path.join(output_dir, "ai_analysis_images")
        source_dir = os.path.join(stitch_dir, source_name.replace(" ", "_"))

        os.makedirs(source_dir, exist_ok=True)

        # Save each image
        saved_images = []
        for i, img_data in enumerate(images_data):
            if img_data.get("type") == "image" and img_data.get("source", {}).get("type") == "base64":
                img_base64 = img_data["source"]["data"]
                img_bytes = base64.b64decode(img_base64)
                img = Image.open(io.BytesIO(img_bytes))

                # Save the image
                img_path = os.path.join(source_dir, f"path_image_{i:03d}.png")
                img.save(img_path)
                saved_images.append(img_path)
                logger.debug(f"Saved image {i} to {img_path}")

        logger.info(f"Saved {len(saved_images)} images for {source_name} to {source_dir}")

        # Create a stitched image if we have multiple images
        if len(saved_images) > 1:
            try:
                create_stitched_image(saved_images, source_dir, source_name)
            except Exception as stitch_err:
                logger.error(f"Error creating stitched image: {stitch_err}", exc_info=True)

        return source_dir
    except Exception as e:
        logger.error(f"Error saving images for stitching: {e}", exc_info=True)
        return None

def create_stitched_image(image_paths, output_dir, source_name):
    """Creates a simple stitched image from the captured path images."""
    if not image_paths or len(image_paths) < 2:
        return

    try:
        logger.info(f"Creating stitched image from {len(image_paths)} images for {source_name}")

        # Load all images
        images = [Image.open(path) for path in image_paths]

        # Get dimensions
        width = max(img.width for img in images)
        total_height = sum(img.height for img in images)

        # Create a new blank image
        stitched = Image.new('RGB', (width, total_height))

        # Paste images vertically
        y_offset = 0
        for img in images:
            stitched.paste(img, (0, y_offset))
            y_offset += img.height

        # Save the stitched image
        stitch_path = os.path.join(output_dir, f"{source_name.replace(' ', '_')}_stitched.png")
        stitched.save(stitch_path)
        logger.info(f"Saved stitched image to {stitch_path}")

        # Create a horizontal stitch as well (side by side)
        total_width = sum(img.width for img in images)
        height = max(img.height for img in images)

        h_stitched = Image.new('RGB', (total_width, height))

        # Paste images horizontally
        x_offset = 0
        for img in images:
            h_stitched.paste(img, (x_offset, 0))
            x_offset += img.width

        # Save the horizontal stitched image
        h_stitch_path = os.path.join(output_dir, f"{source_name.replace(' ', '_')}_stitched_horizontal.png")
        h_stitched.save(h_stitch_path)
        logger.info(f"Saved horizontal stitched image to {h_stitch_path}")

        return stitch_path
    except Exception as e:
        logger.error(f"Error creating stitched image: {e}", exc_info=True)
        return None

def compile_analysis_report(results, title="AI Path Analysis Report"):
    """Compiles the JSON results from all sources into a text report."""
    report_lines = [title, "=" * len(title) + "\n"]

    # Add note about saved images
    output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    stitch_dir = os.path.join(output_dir, "ai_analysis_images")
    if os.path.exists(stitch_dir):
        report_lines.append(f"Note: Captured images have been saved to: {stitch_dir}")

        # Check for stitched images
        stitched_images = []
        for source_name in results.keys():
            source_dir = os.path.join(stitch_dir, source_name.replace(" ", "_"))
            if os.path.exists(source_dir):
                for filename in os.listdir(source_dir):
                    if "stitched" in filename:
                        stitched_images.append(os.path.join(source_dir, filename))

        if stitched_images:
            report_lines.append("Stitched images of the entire path have been created:")
            for img_path in stitched_images:
                report_lines.append(f"  - {os.path.basename(img_path)}")
        else:
            report_lines.append("Individual captured images can be used for manual stitching if needed.")

        report_lines.append("")

    for source_name, result_data in results.items():
        report_lines.append(f"--- Source: {source_name} ---")
        if isinstance(result_data, dict):
            if result_data.get("error"):
                report_lines.append(f"  Status: Error - {result_data['error']}")
                if result_data.get("raw_output"):
                     report_lines.append(f"  Raw Output (partial): {result_data['raw_output'][:200]}...")
            elif result_data.get("status") == "Skipped by user": # Handle skipped maps
                report_lines.append(f"  Status: Skipped by user")
            else:
                report_lines.append(f"  Status: Completed")
                report_lines.append(f"  Summary: {result_data.get('analysis_summary', 'N/A')}")
                obstructions = result_data.get('potential_obstructions', [])
                if obstructions:
                    report_lines.append("  Potential Obstructions:")
                    for i, obs in enumerate(obstructions):
                        report_lines.append(f"    {i+1}. Description: {obs.get('description', 'N/A')}")
                        report_lines.append(f"       Location: {obs.get('location_estimate', 'N/A')}")
                        report_lines.append(f"       Height: {obs.get('height_category', 'N/A')}")
                        report_lines.append(f"       Confidence: {obs.get('confidence', 'N/A')}")
                else:
                    report_lines.append("  No significant potential obstructions identified for this source.")
        else:
            report_lines.append(f"  Status: Error - Invalid result format received: {type(result_data)}")
        report_lines.append("") # Add space between sources

    return "\n".join(report_lines)

def display_analysis_report(root, report_text):
    """Displays the final analysis report in a new window."""
    try:
        report_window = Toplevel(root)
        report_window.title("AI Analysis Report")
        report_window.geometry("700x600")

        text_frame = ttk.Frame(report_window)
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        text_area = tk.Text(text_frame, wrap="word", font=("Courier New", 9))
        scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=text_area.yview)
        text_area.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        text_area.pack(side="left", fill="both", expand=True)

        text_area.insert("1.0", report_text)
        text_area.config(state="disabled") # Make read-only

        button_frame = ttk.Frame(report_window)
        button_frame.pack(fill="x", pady=(0, 10))
        close_button = ttk.Button(button_frame, text="Close", command=report_window.destroy)
        close_button.pack()

        report_window.transient(root)
        report_window.grab_set()
        root.wait_window(report_window)

    except Exception as e:
        logger.error(f"Failed to display analysis report window: {e}", exc_info=True)
        messagebox.showinfo("AI Analysis Report", report_text[:2000] + ("..." if len(report_text) > 2000 else ""))

# Example usage (for testing purposes)
if __name__ == '__main__':
    print("AI Path Analyze module - Test Runner")
    print("Requires ANTHROPIC_API_KEY environment variable.")
    print("MAPBOX_ACCESS_TOKEN is optional; Mapbox source will be skipped if missing.")

    root_tk = tk.Tk()
    root_tk.title("AI Analysis Test - Main Window")
    root_tk.geometry("300x150")

    start_coords = (40.0, -105.0) # Example Boulder, CO area
    end_coords = (40.1, -105.1)

    def start_test_analysis():
        if not ANTHROPIC_API_KEY:
            messagebox.showerror("API Key Missing", "ANTHROPIC_API_KEY environment variable not set.")
            return
        active_sources = get_active_map_sources()
        if not active_sources:
            messagebox.showerror("Configuration Error", "No map sources available. Check config/API keys.")
            return
        if "mapbox_satellite" not in active_sources:
            messagebox.showwarning("API Key Missing", "MAPBOX_ACCESS_TOKEN not set or invalid. Mapbox source will be skipped.")

        print("Starting test analysis in background thread...")
        analysis_thread = threading.Thread(target=run_multi_source_analysis,
                                           args=(root_tk, start_coords, end_coords, None),
                                           daemon=True)
        analysis_thread.start()

    test_button = ttk.Button(root_tk, text="Run AI Analysis Test", command=start_test_analysis)
    test_button.pack(pady=20)

    exit_button = ttk.Button(root_tk, text="Exit", command=root_tk.quit)
    exit_button.pack(pady=10)

    root_tk.mainloop()