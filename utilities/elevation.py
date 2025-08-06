import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import requests
import math
import os
import logging
from vegetation_profile import VegetationProfiler
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import ImageGrab
import time
import json
import sys
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import subprocess  # For opening files
from certificates import create_turbine_certificate
from log_config import setup_logging
import turbines  # Import the turbines module

# Set up logging
logger = setup_logging(__name__)

class ElevationProfile:
    def __init__(self, parent_frame):
        self.frame = ttk.LabelFrame(parent_frame, text="Elevation and Vegetation Profile")
        self.frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Create a container frame for the canvas
        self.canvas_frame = ttk.Frame(self.frame)
        self.canvas_frame.pack(fill="both", expand=True, padx=5, pady=(5, 25))  # Added bottom padding

        # Create canvas with explicit height
        self.canvas = tk.Canvas(self.canvas_frame, bg='white', height=400)
        self.canvas.pack(fill="both", expand=True)

        # Create button frame with grid layout
        self.button_frame = ttk.Frame(self.frame)
        self.button_frame.pack(fill="x", padx=5, pady=5)

        # Configure grid columns to have equal width
        for i in range(2):  # Two columns
            self.button_frame.columnconfigure(i, weight=1)

        # Create a style with smaller font and padding for buttons
        style = ttk.Style()
        style.configure('ElevProfile.TButton', padding=(2, 1), font=('TkDefaultFont', 9))

        # Row 1 buttons
        # Add "Draw Turbines in Profile" button (row 0, column 0)
        self.draw_turbines_button = ttk.Button(
            self.button_frame,
            text="Draw Turbines in Profile",
            command=self.refresh_with_turbines,
            style='ElevProfile.TButton'
        )
        self.draw_turbines_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

        # Add "Reset Profile" button (row 0, column 1)
        self.reset_profile_button = ttk.Button(
            self.button_frame,
            text="Reset Profile",
            command=self.clear_turbines,
            style='ElevProfile.TButton'
        )
        self.reset_profile_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # Row 2 buttons
        # Add "Generate Site to Site Profile" button (row 1, column 0)
        self.site_profile_button = ttk.Button(
            self.button_frame,
            text="Generate Site to Site Profile",
            command=self.generate_site_to_site_profile,
            style='ElevProfile.TButton'
        )
        self.site_profile_button.grid(row=1, column=0, padx=2, pady=2, sticky="ew")

        # Add "View Turbine Data" button (row 1, column 1)
        self.view_turbine_data_button = ttk.Button(
            self.button_frame,
            text="View Turbine Data",
            command=self.view_turbine_data,
            style='ElevProfile.TButton'
        )
        self.view_turbine_data_button.grid(row=1, column=1, padx=2, pady=2, sticky="ew")

        # Row 3 buttons
        # Add export distance certificate button
        self.export_certificate_button = ttk.Button(
            self.button_frame,
            text="Export Turbine Distance Certificate",
            command=self.export_distance_certificate,
            style='ElevProfile.TButton'
        )
        self.export_certificate_button.grid(row=2, column=0, padx=2, pady=2, sticky="ew")

        # Add generate top down view button
        self.generate_top_down_view_button = ttk.Button(
            self.button_frame,
            text="Generate Top Down View",
            command=self.generate_top_down_view,
            style='ElevProfile.TButton'
        )
        self.generate_top_down_view_button.grid(row=2, column=1, padx=2, pady=2, sticky="ew")

        # Bind resize event
        self.canvas.bind('<Configure>', self._on_resize)

        # Initialize variables
        self.elevation_data = None
        self.site_a_data = None
        self.site_b_data = None
        self.max_elevation = 0
        self.min_elevation = 0

        self.vegetation_profiler = VegetationProfiler()

        self.distances = None

        self.EARTH_RADIUS = 20902231  # Earth's radius in feet
        # Initialize logger
        self.logger = logging.getLogger(__name__)

        # Define padding constants
        self.side_padding = 40
        self.top_padding = 40
        self.bottom_padding = 60

        # Add turbine data storage
        self.turbines = []

    def update_profile(self, start_coords, end_coords, site_a_elev=0, site_b_elev=0, site_a_id="", site_b_id="", samples=100):
        """Update elevation and vegetation profile with new coordinates"""
        try:
            # Store coordinates for later use
            self.start_coords = start_coords
            self.end_coords = end_coords

            # Store current turbines if they exist
            current_turbines = self.turbines if hasattr(self, 'turbines') else []

            # Clear existing canvas
            self.canvas.delete("all")

            # Initialize site data first
            self.site_a_data = (0, site_a_elev)  # (distance, elevation)
            self.site_b_data = (1, site_b_elev)  # (distance, elevation)

            # Calculate distances array
            total_distance_meters = self.calculate_distance(start_coords, end_coords)
            self.distances = np.linspace(0, total_distance_meters, samples)

            # Generate points along the path
            lat_points = self._interpolate(start_coords[0], end_coords[0], samples)
            lon_points = self._interpolate(start_coords[1], end_coords[1], samples)

            # Get elevation data
            locations = "|".join([f"{lat},{lon}" for lat, lon in zip(lat_points, lon_points)])
            url = "https://maps.googleapis.com/maps/api/elevation/json"
            params = {
                "locations": locations,
                "key": os.getenv("GOOGLE_MAPS_API_KEY")
            }

            response = requests.get(url, params=params)
            data = response.json()

            if data.get("status") == "OK" and "results" in data:
                elevations = [result["elevation"] * 3.28084 for result in data["results"]]  # Convert to feet

                # Get vegetation heights
                vegetation_heights = self.vegetation_profiler.get_vegetation_profile(
                    start_coords,
                    end_coords,
                    self.distances,
                    elevations
                )

                # Store elevation data for turbine placement
                self.elevation_data = elevations

                # Update site B distance to actual distance
                self.site_b_data = (self.distances[-1], site_b_elev)

                # Restore turbines
                self.turbines = current_turbines

                # Draw the combined profile
                self._draw_profile_with_vegetation(elevations, vegetation_heights, site_a_id, site_b_id)

        except Exception as e:
            logger.error(f"Error updating elevation profile: {e}")
            messagebox.showerror("Error", f"Failed to update elevation profile: {e}")

    def calculate_distance(self, coord1, coord2):
        """Calculate distance between two points in meters"""
        # Import the calculate_distance_meters function from coordinates module
        from utilities.coordinates import calculate_distance_meters

        # Use the imported function to calculate distance in meters
        return calculate_distance_meters(coord1, coord2)

    def calculate_earth_curvature(self, distances, elevations):
        """Calculate earth curvature effect on the profile"""
        try:
            curved_elevations = []
            total_distance = distances[-1]  # Total distance in feet

            for i, distance in enumerate(distances):
                # Calculate bulge at this point using simplified formula
                t = distance / total_distance
                max_bulge = (total_distance**2) / (8 * self.EARTH_RADIUS)
                bulge = max_bulge * 4 * t * (1 - t)  # Parabolic curve

                # Add bulge to elevation
                curved_elevations.append(elevations[i] + bulge)

            return curved_elevations

        except Exception as e:
            self.logger.error(f"Error calculating earth curvature: {e}")
            return elevations.copy()

    def _calculate_distance_along_path(self, turbine_coords, start_coords, end_coords):
        """Calculate the projected distance along the path for a turbine"""
        try:
            # Convert all coordinates to radians
            lat1, lon1 = map(math.radians, start_coords)
            lat2, lon2 = map(math.radians, end_coords)
            lat_t, lon_t = map(math.radians, turbine_coords)

            # Calculate total path length
            path_length = self.calculate_distance(start_coords, end_coords)

            # Calculate vectors
            path_vector = (math.cos(lat2) * math.cos(lon2) - math.cos(lat1) * math.cos(lon1),
                         math.cos(lat2) * math.sin(lon2) - math.cos(lat1) * math.sin(lon1),
                         math.sin(lat2) - math.sin(lat1))

            turbine_vector = (math.cos(lat_t) * math.cos(lon_t) - math.cos(lat1) * math.cos(lon1),
                            math.cos(lat_t) * math.sin(lon_t) - math.cos(lat1) * math.sin(lon1),
                            math.sin(lat_t) - math.sin(lat1))

            # Calculate dot product
            dot_product = sum(p * t for p, t in zip(path_vector, turbine_vector))
            path_magnitude = math.sqrt(sum(x * x for x in path_vector))

            # Calculate projection distance ratio
            if path_magnitude == 0:
                return 0

            projection_ratio = dot_product / (path_magnitude * path_magnitude)

            # Calculate projected distance
            projected_distance = projection_ratio * path_length

            # Ensure distance is within path bounds
            return max(0, min(path_length, projected_distance))

        except Exception as e:
            logger.error(f"Error calculating distance along path: {e}")
            return 0

    def _draw_profile_with_vegetation(self, elevations, vegetation_heights, site_a_id, site_b_id):
        """Draw elevation profile with vegetation overlay and LOS path"""
        try:
            logger.info("Drawing profile with vegetation and turbines")
            if hasattr(self, 'turbines') and self.turbines:
                logger.info(f"Found {len(self.turbines)} turbines to draw")
                for turbine in self.turbines:
                    logger.info(f"Turbine data: ID={turbine.get('id')}, Height={turbine.get('total_height_m')}m")
            else:
                logger.info("No turbines available to draw")

            # Store last values for resize events
            self.last_elevations = elevations
            self.last_vegetation_heights = vegetation_heights
            self.last_site_a_id = site_a_id
            self.last_site_b_id = site_b_id

            # Clear existing canvas
            self.canvas.delete("all")

            # Get canvas dimensions
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height() - 30  # Reserve space for legend

            # Calculate actual plotting area
            plot_height = height - self.bottom_padding - self.top_padding
            plot_width = width - 2 * self.side_padding

            # Get site elevations and add antenna heights
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    antenna_a_height = float(tower_params['site_A']['antenna_cl_ft'])
                    antenna_b_height = float(tower_params['site_B']['antenna_cl_ft'])
                    site_a_elev = self.site_a_data[1] + antenna_a_height  # Total height including antenna
                    site_b_elev = self.site_b_data[1] + antenna_b_height  # Total height including antenna
                    frequency_ghz = float(tower_params['general_parameters']['frequency_ghz'])
                    logger.info(f"Loaded parameters: freq={frequency_ghz}GHz, A_height={antenna_a_height}ft, B_height={antenna_b_height}ft")
            except Exception as e:
                logger.warning(f"Could not load tower parameters: {e}")
                site_a_elev = self.site_a_data[1]
                site_b_elev = self.site_b_data[1]
                frequency_ghz = 11.0  # Default frequency if not found

            # Find elevation range including vegetation and turbines
            total_heights = [e + v for e, v in zip(elevations, vegetation_heights)]
            min_elev = min(min(elevations), self.site_a_data[1], self.site_b_data[1])
            max_elev = max(max(total_heights), site_a_elev, site_b_elev)

            # Add turbine heights to elevation range calculation
            if hasattr(self, 'turbines') and self.turbines:
                for turbine in self.turbines:
                    try:
                        # Get turbine dimensions
                        height_m = float(turbine.get('total_height_m', 100))
                        height_ft = height_m * 3.28084

                        # Calculate turbine position
                        turbine_lat, turbine_lon = turbine['latitude'], turbine['longitude']
                        turbine_distance = self._calculate_distance_along_path(
                            (turbine_lat, turbine_lon),
                            self.start_coords,
                            self.end_coords
                        )

                        # Find ground elevation at turbine position
                        distance_ratio = turbine_distance / self.distances[-1]
                        index = int(distance_ratio * (len(elevations) - 1))
                        if 0 <= index < len(elevations):
                            ground_elevation = elevations[index]
                            total_height = ground_elevation + height_ft
                            max_elev = max(max_elev, total_height)
                            min_elev = min(min_elev, ground_elevation)
                            logger.info(f"Turbine {turbine.get('id')}: ground_elev={ground_elevation:.1f}ft, total_height={total_height:.1f}ft")
                    except Exception as e:
                        logger.error(f"Error calculating turbine elevation range: {e}")

            # Add 10% padding to elevation range
            elev_range = max_elev - min_elev
            min_elev -= elev_range * 0.1
            max_elev += elev_range * 0.1

            # Calculate scales
            x_scale = plot_width / (len(elevations) - 1) if len(elevations) > 1 else 1
            elev_range = max_elev - min_elev
            y_scale = plot_height / elev_range if elev_range > 0 else 1

            # Calculate antenna point coordinates first - these are our reference points
            site_a_y = height - self.bottom_padding - ((site_a_elev - min_elev) * y_scale)
            site_b_y = height - self.bottom_padding - ((site_b_elev - min_elev) * y_scale)

            # Calculate and store LOS heights
            self.los_heights = []
            total_distance = self.distances[-1]  # This is in meters
            total_distance_km = total_distance / 1000  # Convert to kilometers

            for i, distance in enumerate(self.distances):
                distance_km = distance / 1000  # Convert to kilometers
                t = distance_km / total_distance_km
                los_height = site_a_elev + (site_b_elev - site_a_elev) * t
                self.los_heights.append(los_height)

            # Calculate and store curved path heights
            self.curved_heights = []
            for i, distance in enumerate(self.distances):
                distance_km = distance / 1000  # Convert to kilometers
                t = distance_km / total_distance_km

                # Linear interpolation between site elevations
                los_height = site_a_elev + (site_b_elev - site_a_elev) * t

                # Calculate earth bulge
                bulge = (distance_km * (total_distance_km - distance_km)) / (2 * self.EARTH_RADIUS / 3280.84)  # Convert Earth radius to feet

                # Store curved height
                curved_height = los_height - bulge
                self.curved_heights.append(curved_height)

            # Draw curved path
            curve_points = []
            for i, elev in enumerate(self.curved_heights):
                x = self.side_padding + i * x_scale
                y = height - self.bottom_padding - ((elev - min_elev) * y_scale)
                curve_points.extend([x, y])

            # Force curve endpoints to match antenna points exactly
            curve_points[0:2] = [self.side_padding, site_a_y]
            curve_points[-2:] = [width - self.side_padding, site_b_y]

            # Draw the earth curvature line
            self.canvas.create_line(
                curve_points,
                fill="black",
                width=1,
                dash=(2, 2),
                smooth=True,
                tags="earth_curve"
            )

            # Calculate and draw Fresnel zone
            fresnel_upper_points = []
            fresnel_lower_points = []

            for i, distance in enumerate(self.distances):
                x = self.side_padding + i * x_scale

                # For first and last points, use exact antenna points
                if i == 0:
                    y = site_a_y
                    fresnel_radius = 0
                elif i == len(self.distances) - 1:
                    y = site_b_y
                    fresnel_radius = 0
                else:
                    # Calculate curved path height
                    curved_height = self.curved_heights[i]
                    y = height - self.bottom_padding - ((curved_height - min_elev) * y_scale)

                    # Calculate Fresnel radius
                    distance_km = distance / 1000  # Convert to kilometers
                    d1_km = distance_km  # Distance from start in km
                    d2_km = total_distance_km - d1_km  # Distance from end in km
                    fresnel_radius = self.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                fresnel_radius_scaled = fresnel_radius * y_scale

                # Add points for upper and lower Fresnel bounds
                fresnel_upper_points.extend([x, y - fresnel_radius_scaled])
                fresnel_lower_points.extend([x, y + fresnel_radius_scaled])

            # Force Fresnel endpoints to match antenna points exactly
            fresnel_upper_points[0:2] = [self.side_padding, site_a_y]
            fresnel_upper_points[-2:] = [width - self.side_padding, site_b_y]
            fresnel_lower_points[0:2] = [self.side_padding, site_a_y]
            fresnel_lower_points[-2:] = [width - self.side_padding, site_b_y]

            # Draw Fresnel zone bounds
            self.canvas.create_line(
                fresnel_upper_points,
                fill='#FF69B4',  # Hot pink
                width=1,
                smooth=True,
                tags="fresnel_upper"
            )

            self.canvas.create_line(
                fresnel_lower_points,
                fill='#FF69B4',  # Hot pink
                width=1,
                smooth=True,
                tags="fresnel_lower"
            )

            # Draw ground profile
            ground_points = []
            for i, elev in enumerate(elevations):
                x = self.side_padding + i * x_scale
                y = height - self.bottom_padding - ((elev - min_elev) * y_scale)
                ground_points.extend([x, y])

            # Draw ground line
            self.canvas.create_line(ground_points, fill="blue", width=2, smooth=True)

            # Draw vegetation profile
            vegetation_points = []
            for i, (elev, veg) in enumerate(zip(elevations, vegetation_heights)):
                x = self.side_padding + i * x_scale
                y = height - self.bottom_padding - ((elev + veg - min_elev) * y_scale)
                vegetation_points.extend([x, y])

            # Draw vegetation line
            self.canvas.create_line(vegetation_points, fill="green", width=2, smooth=True)

            # Draw site A vertical line and labels
            if hasattr(self, 'site_a_data'):
                # Vertical line for site A
                self.canvas.create_line(
                    self.side_padding, site_a_y,
                    self.side_padding, height - self.bottom_padding,
                    fill="blue", width=2, dash=(5,5)
                )
                # Site A dot
                self.canvas.create_oval(
                    self.side_padding-3, site_a_y-3,
                    self.side_padding+3, site_a_y+3,
                    fill="blue", outline="blue"
                )
                # Site A label
                self.canvas.create_text(
                    self.side_padding, site_a_y-15,
                    text="Donor",
                    fill="blue",
                    font=("Arial", 8),
                    anchor="w"
                )

            # Draw site B vertical line and labels
            if hasattr(self, 'site_b_data'):
                # Vertical line for site B
                self.canvas.create_line(
                    width - self.side_padding, site_b_y,
                    width - self.side_padding, height - self.bottom_padding,
                    fill="red", width=2, dash=(5,5)
                )
                # Site B dot
                self.canvas.create_oval(
                    width-self.side_padding-3, site_b_y-3,
                    width-self.side_padding+3, site_b_y+3,
                    fill="red", outline="red"
                )
                # Site B label
                self.canvas.create_text(
                    width-self.side_padding, site_b_y-15,
                    text="Recipient",
                    fill="red",
                    font=("Arial", 8),
                    anchor="e"
                )

            # Draw LOS line between sites
            if hasattr(self, 'site_a_data') and hasattr(self, 'site_b_data'):
                self.canvas.create_line(
                    self.side_padding, site_a_y,
                    width - self.side_padding, site_b_y,
                    fill="#00FFFF",  # Cyan color
                    width=2, dash=(5,5)
                )

            # Draw legend
            legend_y = height - 15
            text_width = 80
            spacing = 10
            total_width = (text_width * 5) + (spacing * 4)  # Space for all legend items
            legend_start_x = (width - total_width) / 2

            # Draw legend background
            legend_bg_padding = 5
            self.canvas.create_rectangle(
                legend_start_x - legend_bg_padding,
                legend_y - legend_bg_padding,
                legend_start_x + total_width + legend_bg_padding,
                legend_y + legend_bg_padding,
                fill="white",
                outline="gray"
            )

            # Draw turbines if available
            if hasattr(self, 'turbines') and self.turbines:
                for turbine in self.turbines:
                    try:
                        # Get turbine dimensions
                        height_m = float(turbine.get('total_height_m', 100))
                        height_ft = height_m * 3.28084
                        rotor_diameter_m = float(turbine.get('rotor_diameter_m', 100))
                        rotor_diameter_ft = rotor_diameter_m * 3.28084
                        rotor_radius_ft = rotor_diameter_ft / 2

                        # Calculate hub height
                        if turbine.get('hub_height_m'):
                            hub_height_m = float(turbine['hub_height_m'])
                            hub_height_ft = hub_height_m * 3.28084
                        else:
                            hub_height_ft = height_ft - rotor_radius_ft

                        # Get turbine position
                        turbine_lat, turbine_lon = turbine['latitude'], turbine['longitude']
                        turbine_distance = self._calculate_distance_along_path(
                            (turbine_lat, turbine_lon),
                            self.start_coords,
                            self.end_coords
                        )

                        # Calculate distance from path
                        distance_from_path = self._calculate_perpendicular_distance(
                            (turbine_lat, turbine_lon),
                            self.start_coords,
                            self.end_coords
                        ) * 3.28084  # Convert to feet

                        # Calculate horizontal position
                        distance_ratio = turbine_distance / self.distances[-1]
                        x_pos = self.side_padding + (distance_ratio * plot_width)

                        # Find ground elevation at turbine position
                        index = int(distance_ratio * (len(elevations) - 1))
                        if 0 <= index < len(elevations):
                            ground_elevation = elevations[index]

                            # Calculate vertical positions
                            ground_y = height - self.bottom_padding - ((ground_elevation - min_elev) * y_scale)
                            hub_y = height - self.bottom_padding - ((ground_elevation + hub_height_ft - min_elev) * y_scale)

                            # Draw turbine tower
                            self.canvas.create_line(
                                x_pos, ground_y,
                                x_pos, hub_y,
                                fill="purple",
                                width=2
                            )

                            # Draw rotor circle
                            rotor_radius_scaled = rotor_radius_ft * y_scale
                            # Apply horizontal compression to x-radius only
                            rotor_radius_x_scaled = rotor_radius_ft * y_scale * 0.01  # Apply 1% horizontal compression
                            self.canvas.create_oval(
                                x_pos - rotor_radius_x_scaled, hub_y - rotor_radius_scaled,
                                x_pos + rotor_radius_x_scaled, hub_y + rotor_radius_scaled,
                                outline="purple",
                                width=2
                            )

                            # Add turbine ID label
                            self.canvas.create_text(
                                x_pos, hub_y - rotor_radius_scaled - 10,
                                text=f"Turbine {turbine.get('id', 'Unknown')}",
                                fill="purple",
                                font=("Arial", 8),
                                anchor="s"
                            )

                            # Add distance from path label
                            self.canvas.create_text(
                                x_pos, ground_y + 15,
                                text=f"Distance: {abs(distance_from_path):.0f}ft",
                                fill="purple",
                                font=("Arial", 8),
                                anchor="n"
                            )

                            logger.info(f"Drew turbine {turbine.get('id')}: ground={ground_elevation:.1f}ft, hub={hub_height_ft:.1f}ft, total={height_ft:.1f}ft")
                    except Exception as e:
                        logger.error(f"Error drawing turbine: {e}")

            # Ground elevation legend
            self.canvas.create_line(
                legend_start_x, legend_y,
                legend_start_x + 15, legend_y,
                fill="blue",
                width=2
            )
            self.canvas.create_text(
                legend_start_x + 20, legend_y,
                text="Ground",
                anchor="w",
                fill="black",
                font=("Arial", 7)
            )

            # Vegetation height legend
            legend_start_x += text_width + spacing
            self.canvas.create_line(
                legend_start_x, legend_y,
                legend_start_x + 15, legend_y,
                fill="green",
                width=2
            )
            self.canvas.create_text(
                legend_start_x + 20, legend_y,
                text="Vegetation",
                anchor="w",
                fill="black",
                font=("Arial", 7)
            )

            # LOS path legend
            legend_start_x += text_width + spacing
            self.canvas.create_line(
                legend_start_x, legend_y,
                legend_start_x + 15, legend_y,
                fill="#00FFFF",
                width=2,
                dash=(5,5)
            )
            self.canvas.create_text(
                legend_start_x + 20, legend_y,
                text="LOS Path",
                anchor="w",
                fill="black",
                font=("Arial", 7)
            )

            # Earth curve legend
            legend_start_x += text_width + spacing
            self.canvas.create_line(
                legend_start_x, legend_y,
                legend_start_x + 15, legend_y,
                fill="black",
                width=1,
                dash=(2,2)
            )
            self.canvas.create_text(
                legend_start_x + 20, legend_y,
                text="Earth Curve",
                anchor="w",
                fill="black",
                font=("Arial", 7)
            )

            # Fresnel zone legend
            legend_start_x += text_width + spacing
            self.canvas.create_line(
                legend_start_x, legend_y,
                legend_start_x + 15, legend_y,
                fill="#FF69B4",
                width=1
            )
            self.canvas.create_text(
                legend_start_x + 20, legend_y,
                text="Fresnel Zone",
                anchor="w",
                fill="black",
                font=("Arial", 7)
            )

        except Exception as e:
            logger.error(f"Error in _draw_profile_with_vegetation: {e}")
            raise

    def _on_resize(self, event):
        """Handle canvas resize event"""
        if hasattr(self, 'last_elevations') and hasattr(self, 'last_vegetation_heights'):
            self._draw_profile_with_vegetation(
                self.last_elevations,
                self.last_vegetation_heights,
                self.last_site_a_id,
                self.last_site_b_id
            )

    def _draw_profile(self):
        """Draw the elevation profile"""
        self.canvas.delete("all")

        # Get canvas dimensions
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        padding = 40  # Padding for labels

        # Drawing area dimensions
        draw_width = width - 2 * padding
        draw_height = height - 2 * padding

        # Draw elevation range labels
        self.canvas.create_text(padding-30, padding, text=f"{int(self.max_elevation)}ft", anchor="e")
        self.canvas.create_text(padding-30, height-padding, text=f"{int(self.min_elevation)}ft", anchor="e")

        # Draw terrain profile
        points = []
        for i, elev in enumerate(self.elevation_data):
            x = padding + (i / (len(self.elevation_data) - 1)) * draw_width
            y = height - padding - ((elev - self.min_elevation) / (self.max_elevation - self.min_elevation)) * draw_height
            points.extend([x, y])

        # Draw terrain
        if len(points) >= 4:
            # Create terrain polygon
            terrain_points = [padding, height-padding] + points + [width-padding, height-padding]
            self.canvas.create_polygon(terrain_points, fill="#f0f0f0", outline="gray")

            # Draw LOS line
            site_a_y = height - padding - ((self.site_a_data[1] - self.min_elevation) /
                                        (self.max_elevation - self.min_elevation)) * draw_height
            site_b_y = height - padding - ((self.site_b_data[1] - self.min_elevation) /
                                        (self.max_elevation - self.min_elevation)) * draw_height
            self.canvas.create_line(padding, site_a_y, width-padding, site_b_y,
                                  fill="yellow", width=2)

            # Draw site markers with IDs
            self._draw_site_marker(padding, site_a_y, "Donor", "blue", self.site_a_id)
            self._draw_site_marker(width-padding, site_b_y, "Recipient", "red", self.site_b_id)

    def _draw_site_marker(self, x, y, label, color, site_id):
        """Draw a site marker with vertical line and label"""
        # Draw vertical line
        self.canvas.create_line(x, y, x, self.canvas.winfo_height()-40,
                              fill=color, width=2, dash=(5,5))
        # Draw site dot
        self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=color, outline=color)
        # Add labels
        self.canvas.create_text(x, y-15, text=label, fill=color, font=("Arial", 8))
        self.canvas.create_text(x, y-30, text=site_id, fill=color, font=("Arial", 8))

    def _interpolate(self, start, end, samples):
        """Generate evenly spaced points between start and end"""
        return [start + (end - start) * i / (samples - 1) for i in range(samples)]

    def capture_profile_image(self):
        """Capture elevation profile as image"""
        try:
            # Create temp directory if it doesn't exist
            temp_dir = "temp"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            # Save profile screenshot
            image_path = os.path.join(temp_dir, "elevation_profile.png")

            # Force update and wait for rendering
            self.canvas.update()
            time.sleep(0.5)

            # Get canvas coordinates
            x = self.canvas.winfo_rootx()
            y = self.canvas.winfo_rooty()
            width = self.canvas.winfo_width()
            height = self.canvas.winfo_height()

            # Capture screenshot
            image = ImageGrab.grab(bbox=(x, y, x+width, y+height))
            image.save(image_path)

            return image_path

        except Exception as e:
            logger.error(f"Error capturing elevation profile: {e}")
            return None

    def set_turbines(self, turbines):
        """Set the turbines to be displayed in the elevation profile."""
        logger.info(f"Setting {len(turbines)} turbines in elevation profile")
        self.turbines = turbines.copy()  # Make a copy to ensure we have our own version
        logger.info(f"Stored {len(self.turbines)} turbines in elevation profile")

    def refresh_with_turbines(self):
        """Refresh the elevation profile with turbines."""
        try:
            if not hasattr(self, 'start_coords') or not hasattr(self, 'end_coords'):
                logger.warning("No path coordinates available to refresh profile")
                return

            # Load turbines from JSON if not already in memory
            if not hasattr(self, 'turbines') or not self.turbines:
                logger.info("Loading turbines from tower_parameters.json")
                try:
                    with open('tower_parameters.json', 'r') as f:
                        data = json.load(f)
                        if 'turbines' in data and data['turbines']:
                            self.turbines = data['turbines']
                            logger.info(f"Loaded {len(self.turbines)} turbines from JSON file")
                        else:
                            logger.warning("No turbines found in JSON file")
                            return
                except Exception as e:
                    logger.error(f"Error loading turbines from JSON: {e}")
                    return

            if not self.turbines:
                logger.warning("No turbines available to draw in profile")
                return

            logger.info(f"Refreshing elevation profile with {len(self.turbines)} turbines")

            # Get the site elevations from the stored data
            site_a_elev = self.site_a_data[1] if hasattr(self, 'site_a_data') else 0
            site_b_elev = self.site_b_data[1] if hasattr(self, 'site_b_data') else 0

            # Get the site IDs
            site_a_id = self.last_site_a_id if hasattr(self, 'last_site_a_id') else "Site A"
            site_b_id = self.last_site_b_id if hasattr(self, 'last_site_b_id') else "Site B"

            logger.info(f"Updating profile with stored coordinates and data: {len(self.turbines)} turbines")
            # Update the profile with the stored coordinates and data
            self.update_profile(
                self.start_coords,
                self.end_coords,
                site_a_elev,
                site_b_elev,
                site_a_id,
                site_b_id
            )
            logger.info("Profile update complete")
        except Exception as e:
            logger.error(f"Error in refresh_with_turbines: {e}", exc_info=True)

    def clear_turbines(self):
        """Clear turbines from the profile view"""
        try:
            # Reset the turbines data
            self.turbines = []

            # Only redraw if we have elevation data and coordinates
            if hasattr(self, 'elevation_data') and self.elevation_data and hasattr(self, 'start_coords') and hasattr(self, 'end_coords'):
                # Get the site elevations from the stored data
                site_a_elev = self.site_a_data[1] if hasattr(self, 'site_a_data') else 0
                site_b_elev = self.site_b_data[1] if hasattr(self, 'site_b_data') else 0

                # Get the site IDs
                site_a_id = self.last_site_a_id if hasattr(self, 'last_site_a_id') else "Site A"
                site_b_id = self.last_site_b_id if hasattr(self, 'last_site_b_id') else "Site B"

                # Redraw the profile without turbines
                self.update_profile(
                    self.start_coords,
                    self.end_coords,
                    site_a_elev,
                    site_b_elev,
                    site_a_id,
                    site_b_id
                )
                logger.info("Profile redrawn without turbines")
            else:
                logger.warning("No profile data available to redraw")

        except Exception as e:
            logger.error(f"Error clearing turbines from profile: {e}", exc_info=True)

    def generate_site_to_site_profile(self, save_to_file=False, output_dir=None):
        """Generate a perpendicular view showing turbines relative to the path using Matplotlib.

        Args:
            save_to_file (bool): Whether to save the figure to a file
            output_dir (str): Directory to save the figure to, if save_to_file is True

        Returns:
            str: Path to the saved figure if save_to_file is True, None otherwise
        """
        try:
            # Create a new top-level window if we're not just saving to file
            if not save_to_file:
                profile_window = tk.Toplevel()
                profile_window.title("Site to Site Profile View")

            # Create matplotlib figure with larger size
            fig, ax = plt.subplots(figsize=(18, 6))  # Changed from (20, 12) to (18, 6) for 1800x600 size at 100dpi

            if not hasattr(self, 'turbines') or not self.turbines:
                logger.warning("No turbines available for site-to-site profile")
                return None

            # Get path length in feet
            total_distance_m = self.distances[-1]
            total_distance_ft = total_distance_m * 3.28084

            # Process turbine data
            turbine_data = []
            min_elev = float('inf')
            max_elev = float('-inf')
            max_distance_from_path = 0

            for turbine in self.turbines:
                try:
                    # Get turbine parameters and convert to proper units
                    height_m = float(turbine.get('total_height_m', 100))
                    height_ft = height_m * 3.28084
                    rotor_diameter_m = float(turbine.get('rotor_diameter_m', 100))
                    rotor_diameter_ft = rotor_diameter_m * 3.28084
                    rotor_radius_ft = rotor_diameter_ft / 2

                    # Calculate hub height (use provided hub height if available)
                    if turbine.get('hub_height_m'):
                        hub_height_m = float(turbine['hub_height_m'])
                        hub_height_ft = hub_height_m * 3.28084
                    else:
                        # If no hub height provided, calculate it as total height minus rotor radius
                        hub_height_ft = height_ft - rotor_radius_ft

                    # Calculate turbine position along path
                    turbine_lat, turbine_lon = turbine['latitude'], turbine['longitude']
                    turbine_distance_along = self._calculate_distance_along_path(
                        (turbine_lat, turbine_lon),
                        self.start_coords,
                        self.end_coords
                    )
                    distance_ratio = turbine_distance_along / self.distances[-1]

                    # Find ground elevation at turbine position
                    index = int(distance_ratio * (len(self.elevation_data) - 1))
                    ground_elevation = self.elevation_data[index] if 0 <= index < len(self.elevation_data) else 0

                    # Calculate perpendicular distance from path
                    perpendicular_distance = self._calculate_perpendicular_distance(
                        (turbine_lat, turbine_lon),
                        self.start_coords,
                        self.end_coords
                    )
                    perpendicular_distance_ft = perpendicular_distance * 3.28084  # Convert to feet
                    # Keep the sign of the perpendicular distance to determine which side of the path
                    distance_ft = perpendicular_distance_ft  # No abs() here to preserve the sign

                    # Update ranges using absolute value for plotting limits
                    max_distance_from_path = max(max_distance_from_path, abs(perpendicular_distance_ft))
                    min_elev = min(min_elev, ground_elevation)
                    max_elev = max(max_elev, ground_elevation + height_ft)

                    # Store all the data we need for drawing
                    turbine_data.append({
                        'id': turbine.get('id', 'Unknown'),
                        'ground_elev': ground_elevation,
                        'height_ft': height_ft,
                        'hub_height_ft': hub_height_ft,
                        'distance_ft': distance_ft,  # Keep the sign
                        'rotor_diameter_ft': rotor_diameter_ft,
                        'rotor_radius_ft': rotor_radius_ft,
                        'distance_along': distance_ratio,
                        'distance_along_ft': turbine_distance_along * 3.28084
                    })
                except Exception as e:
                    logger.error(f"Error processing turbine: {e}")
                    continue

            # Add padding to ranges
            elev_range = max_elev - min_elev
            min_elev -= elev_range * 0.25  # Increased vertical padding
            max_elev += elev_range * 0.25
            max_distance_from_path += max_distance_from_path * 0.25  # Increased horizontal padding

            # Calculate horizontal compression factor based on path length vs display width
            # For a 13-mile path (68,640 ft), we want to compress much more significantly
            # A typical rotor diameter is around 417 ft, so we want that to appear very narrow
            # in comparison to the path length
            horizontal_compression = 0.01  # This will compress the horizontal scale to 1% of actual distance

            # Set up the plot
            compressed_max_distance = max_distance_from_path * horizontal_compression
            ax.set_xlim(-compressed_max_distance, compressed_max_distance)
            ax.set_ylim(min_elev, max_elev)
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.set_xlabel('Distance from Path (ft)')
            ax.set_ylabel('Elevation (ft)')
            ax.set_title('Site to Site Profile View (Looking Down Path)')

            # Draw center line (path)
            ax.axvline(x=0, color='blue', linestyle='--', label='Path')

            # Draw donor and recipient markers and LOS path
            if hasattr(self, 'site_a_data') and hasattr(self, 'site_b_data'):
                # Draw donor site (blue dot)
                ax.scatter([0], [self.site_a_data[1]], color='blue', s=100, zorder=5, label=f'Donor ({self.site_a_data[1]:.0f}ft)')

                # Draw recipient site (red dot)
                ax.scatter([0], [self.site_b_data[1]], color='red', s=100, zorder=5, label=f'Recipient ({self.site_b_data[1]:.0f}ft)')

                # Draw line of sight path
                ax.plot([0, 0], [self.site_a_data[1], self.site_b_data[1]], 'r--', linewidth=1, alpha=0.8, label='Line of Sight')

                # Draw Fresnel zone
                try:
                    # Get frequency from tower parameters
                    with open('tower_parameters.json', 'r') as f:
                        tower_params = json.load(f)
                        frequency_ghz = float(tower_params['general_parameters']['frequency_ghz'])
                except Exception as e:
                    logger.warning(f"Could not load frequency from tower parameters: {e}")
                    frequency_ghz = 11.0  # Default frequency

                # Calculate Fresnel zone at various heights
                los_height_range = np.linspace(self.site_a_data[1], self.site_b_data[1], 100)
                total_dist_km = total_distance_ft / 3280.84  # Convert to km

                # Calculate Fresnel radius at midpoint
                midpoint_radius = self.calculate_fresnel_radius(total_dist_km/2, total_dist_km/2, frequency_ghz)

                # Create Fresnel zone boundary points
                fresnel_left = []
                fresnel_right = []

                for height in los_height_range:
                    # Calculate relative position along path
                    height_ratio = (height - self.site_a_data[1]) / (self.site_b_data[1] - self.site_a_data[1])
                    d1_km = height_ratio * total_dist_km
                    d2_km = total_dist_km - d1_km

                    # Calculate Fresnel radius at this point
                    radius = self.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                    # Apply horizontal compression
                    radius_compressed = radius * horizontal_compression

                    fresnel_left.append([-radius_compressed, height])
                    fresnel_right.append([radius_compressed, height])

                # Convert to numpy arrays for plotting
                fresnel_left = np.array(fresnel_left)
                fresnel_right = np.array(fresnel_right)

                # Plot Fresnel zone boundaries
                ax.plot(fresnel_left[:, 0], fresnel_left[:, 1], '#FF69B4', linewidth=1, label='Fresnel Zone')
                ax.plot(fresnel_right[:, 0], fresnel_right[:, 1], '#FF69B4', linewidth=1)

                # Add Fresnel zone measurements for each turbine
                for i, turbine in enumerate(turbine_data):
                    try:
                        # Get stored values
                        rotor_radius_ft = turbine['rotor_radius_ft']
                        hub_height_ft = turbine['hub_height_ft']
                        ground_elev = turbine['ground_elev']
                        distance_ft = turbine['distance_ft']
                        distance_ratio = turbine['distance_along']

                        # Calculate LOS height at turbine position
                        los_height = self.site_a_data[1] + (self.site_b_data[1] - self.site_a_data[1]) * distance_ratio

                        # Calculate earth curvature bulge
                        distance_along_ft = turbine['distance_along_ft']
                        bulge = (distance_along_ft * (total_distance_ft - distance_along_ft)) / (2 * self.EARTH_RADIUS)
                        los_height_curved = los_height - bulge

                        # Calculate distances to curved path and Fresnel zone
                        los_height_curved = los_height - bulge

                        # Calculate center height
                        center_height = ground_elev + hub_height_ft

                        # Calculate shortest distance from rotor edge to curved path
                        vertical_distance = abs(los_height_curved - center_height)
                        horizontal_distance = abs(distance_ft)
                        center_to_path = math.sqrt(horizontal_distance**2 + vertical_distance**2)

                        # Calculate Fresnel radius at this point
                        d1_km = (distance_along_ft / 3280.84)  # Distance from start in km
                        d2_km = total_dist_km - d1_km  # Distance from end in km
                        fresnel_radius = self.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                        # Calculate actual clearance (distance to path minus Fresnel radius and rotor radius)
                        clearance_fresnel = center_to_path - rotor_radius_ft - fresnel_radius

                        # Calculate compressed distance for plotting
                        compressed_distance = distance_ft * horizontal_compression

                        # Draw measurement line from curved path to closest rotor point
                        # Calculate angle to closest point
                        angle = math.atan2(vertical_distance, horizontal_distance)

                        # Calculate rotor intersection point (compressed)
                        rotor_x = compressed_distance
                        rotor_y = center_height

                        # Draw measurement line from LOS (curved) to turbine center
                        ax.plot([0, rotor_x], [los_height_curved, rotor_y],
                              color='#FF69B4', linestyle=':', linewidth=1)

                        # Add Fresnel zone clearance label with vertical offset to prevent overlapping
                        vertical_fresnel_offset = 35 * (1 + (i + 2) % 3)  # Different offset pattern from other labels
                        if (i + 2) % 2 == 0:
                            fresnel_y = (los_height_curved + rotor_y)/2 + vertical_fresnel_offset
                            va_fresnel = 'bottom'
                        else:
                            fresnel_y = (los_height_curved + rotor_y)/2 - vertical_fresnel_offset
                            va_fresnel = 'top'

                        ax.text(compressed_distance/2, fresnel_y,
                               f"Fresnel: {clearance_fresnel:.0f}ft",
                               fontsize=8, color='#FF69B4',
                               horizontalalignment='center',
                               verticalalignment=va_fresnel,
                               bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.3'))
                    except Exception as e:
                        logger.error(f"Error drawing Fresnel measurements for turbine: {e}")
                        continue

            # Draw turbines with compressed horizontal dimensions
            for i, turbine in enumerate(turbine_data):
                try:
                    # Get stored values in feet (including sign for correct side placement)
                    rotor_radius_ft = turbine['rotor_radius_ft']
                    hub_height_ft = turbine['hub_height_ft']
                    ground_elev = turbine['ground_elev']
                    distance_ft = turbine['distance_ft']  # This now includes the sign

                    # Compress horizontal position (keeping the sign)
                    compressed_distance = distance_ft * horizontal_compression

                    # Draw tower from ground to hub height at correct side of path
                    ax.vlines(x=compressed_distance,
                            ymin=ground_elev,
                            ymax=ground_elev + hub_height_ft,
                            colors=f'C{i}',
                            linewidth=2,
                            label=f"{turbine['id']}")

                    # Draw rotor ellipse centered at hub height
                    ellipse = plt.matplotlib.patches.Ellipse(
                        (compressed_distance, ground_elev + hub_height_ft),  # Center at hub height with correct side
                        rotor_radius_ft * 2 * horizontal_compression,  # Compress width
                        rotor_radius_ft * 2,  # Keep height the same
                        fill=False,
                        color=f'C{i}'
                    )
                    ax.add_patch(ellipse)

                    # Add height labels (adjust x position based on side)
                    ax.text(compressed_distance, ground_elev + hub_height_ft - rotor_radius_ft - 10,
                           f"Hub Height: {hub_height_ft:.0f}ft\nTotal Height: {turbine['height_ft']:.0f}ft\nRotor Ø: {turbine['rotor_diameter_ft']:.0f}ft",
                           fontsize=8, color='purple',
                           horizontalalignment='center',
                           verticalalignment='bottom')

                    # Add distance from path label at base (with sign preserved)
                    ax.text(compressed_distance, ground_elev - 20,
                           f"Distance from path: {distance_ft:.0f}ft",
                           fontsize=8, color='purple',
                           horizontalalignment='center',
                           verticalalignment='top')

                    # Calculate path height at turbine's horizontal position
                    distance_ratio = turbine['distance_along']
                    los_height = self.site_a_data[1] + (self.site_b_data[1] - self.site_a_data[1]) * distance_ratio

                    # Calculate earth curvature bulge at this point
                    distance_along_ft = turbine['distance_along_ft']
                    bulge = (distance_along_ft * (total_distance_ft - distance_along_ft)) / (2 * self.EARTH_RADIUS)
                    los_height_curved = los_height - bulge

                    # Calculate clearances
                    center_height = ground_elev + hub_height_ft

                    # Calculate straight-line clearance
                    vertical_distance_straight = abs(los_height - center_height)
                    horizontal_distance = abs(distance_ft)  # Use uncompressed distance
                    center_to_los_3d_straight = math.sqrt(horizontal_distance**2 + vertical_distance_straight**2)
                    clearance_straight = center_to_los_3d_straight - rotor_radius_ft

                    # Calculate earth curvature adjusted clearance
                    vertical_distance_curved = abs(los_height_curved - center_height)
                    center_to_los_3d_curved = math.sqrt(horizontal_distance**2 + vertical_distance_curved**2)
                    clearance_curved = center_to_los_3d_curved - rotor_radius_ft

                    # Draw clearance measurement lines if turbine is close enough to path
                    if abs(distance_ft) < max_distance_from_path * 0.8:
                        # Calculate intersection points on rotor sphere
                        if los_height > center_height:
                            angle_straight = math.atan2(los_height - center_height, -distance_ft)
                            angle_curved = math.atan2(los_height_curved - center_height, -distance_ft)
                        else:
                            angle_straight = math.atan2(los_height - center_height, -distance_ft)
                            angle_curved = math.atan2(los_height_curved - center_height, -distance_ft)

                        # Calculate rotor intersection points (compressed)
                        rotor_x_straight = compressed_distance + (rotor_radius_ft * math.cos(angle_straight) * horizontal_compression)
                        rotor_y_straight = center_height + rotor_radius_ft * math.sin(angle_straight)
                        rotor_x_curved = compressed_distance + (rotor_radius_ft * math.cos(angle_curved) * horizontal_compression)
                        rotor_y_curved = center_height + rotor_radius_ft * math.sin(angle_curved)

                        # Draw measurement lines from their respective LOS heights
                        # Straight line from straight LOS height
                        ax.plot([0, rotor_x_straight], [los_height, rotor_y_straight],
                               color='cyan', linestyle='--', linewidth=1.5)
                        # Curved line from curved LOS height
                        ax.plot([0, rotor_x_curved], [los_height_curved, rotor_y_curved],
                               color='cyan', linewidth=1.5)

                        # Add measurement points at each origin
                        ax.scatter([0], [los_height], color='cyan', s=50)  # Straight LOS point
                        ax.scatter([0], [los_height_curved], color='cyan', s=50)  # Curved LOS point

                        # Add clearance text with offset to prevent overlapping
                        # For straight line - calculate vertical offset based on turbine index
                        vertical_straight_offset = 25 * (1 + i % 3)  # Cycle through 3 different positions
                        if i % 2 == 0:
                            text_y_straight = (los_height + rotor_y_straight)/2 + vertical_straight_offset
                            va_straight = 'bottom'
                        else:
                            text_y_straight = (los_height + rotor_y_straight)/2 - vertical_straight_offset
                            va_straight = 'top'

                        ax.text(compressed_distance/2, text_y_straight,
                               f"straight: {clearance_straight:.0f}ft",
                               fontsize=8, color='black',
                               horizontalalignment='center',
                               verticalalignment=va_straight,
                               bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.3'))

                        # For curved line - use different offset pattern to avoid overlap with straight line
                        vertical_curved_offset = 25 * (1 + (i + 1) % 3)  # Offset pattern different from straight
                        if (i + 1) % 2 == 0:  # Alternate opposite to straight line
                            text_y_curved = (los_height_curved + rotor_y_curved)/2 + vertical_curved_offset
                            va_curved = 'bottom'
                        else:
                            text_y_curved = (los_height_curved + rotor_y_curved)/2 - vertical_curved_offset
                            va_curved = 'top'

                        ax.text(compressed_distance/2, text_y_curved,
                               f"w/curve: {clearance_curved:.0f}ft",
                               fontsize=8, color='black',
                               horizontalalignment='center',
                               verticalalignment=va_curved,
                               bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.3'))

                except Exception as e:
                    logger.error(f"Error drawing individual turbine: {e}")
                    continue

            # Add legend with better positioning
            ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))

            # Adjust layout to prevent label cutoff
            plt.tight_layout()

            # Save to file if requested
            if save_to_file:
                if output_dir is None:
                    output_dir = "temp"

                # Create output directory if it doesn't exist
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                # Generate filename
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filepath = os.path.join(output_dir, f"site_to_site_profile_{timestamp}.png")

                # Save figure
                fig.savefig(filepath, dpi=100, bbox_inches='tight')
                logger.info(f"Saved site to site profile to {filepath}")
                plt.close(fig)
                return filepath

            # Continue with displaying in window if not saving to file
            # Create canvas and add to window with scrolling if needed
            canvas = FigureCanvasTkAgg(fig, master=profile_window)
            canvas.draw()
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill=tk.BOTH, expand=True)

            # Add scrollbars if needed
            if canvas_widget.winfo_reqwidth() > profile_window.winfo_screenwidth():
                scrollbar = ttk.Scrollbar(profile_window, orient="horizontal")
                scrollbar.pack(side="bottom", fill="x")
                canvas_widget.configure(xscrollcommand=scrollbar.set)
                scrollbar.configure(command=canvas_widget.xview)

            return None

        except Exception as e:
            logger.error(f"Error generating site to site profile: {e}", exc_info=True)
            if not save_to_file and 'profile_window' in locals():
                profile_window.destroy()
            return None

    def _calculate_perpendicular_distance(self, point_coords, start_coords, end_coords):
        """Calculate the perpendicular distance from a point to the path line with sign indicating side."""
        try:
            # Convert coordinates to radians
            lat1, lon1 = map(math.radians, start_coords)
            lat2, lon2 = map(math.radians, end_coords)
            lat_p, lon_p = map(math.radians, point_coords)

            # Convert to Cartesian coordinates
            x1 = math.cos(lat1) * math.cos(lon1)
            y1 = math.cos(lat1) * math.sin(lon1)
            z1 = math.sin(lat1)

            x2 = math.cos(lat2) * math.cos(lon2)
            y2 = math.cos(lat2) * math.sin(lon2)
            z2 = math.sin(lat2)

            xp = math.cos(lat_p) * math.cos(lon_p)
            yp = math.cos(lat_p) * math.sin(lon_p)
            zp = math.sin(lat_p)

            # Calculate path vector
            path_vector = [x2 - x1, y2 - y1, z2 - z1]

            # Calculate vector from start to point
            point_vector = [xp - x1, yp - y1, zp - z1]

            # Calculate cross product (this gives us direction)
            cross_product = [
                path_vector[1] * point_vector[2] - path_vector[2] * point_vector[1],
                path_vector[2] * point_vector[0] - path_vector[0] * point_vector[2],
                path_vector[0] * point_vector[1] - path_vector[1] * point_vector[0]
            ]

            # Calculate magnitudes
            path_magnitude = math.sqrt(sum(x * x for x in path_vector))
            cross_magnitude = math.sqrt(sum(x * x for x in cross_product))

            # Calculate perpendicular distance (in meters)
            if path_magnitude == 0:
                return 0

            # Calculate the sign using the dot product of cross product with up vector [0, 0, 1]
            # This will tell us which side of the path the point is on
            sign = 1 if cross_product[2] > 0 else -1

            perpendicular_distance = (cross_magnitude / path_magnitude) * sign
            return perpendicular_distance * 6371000  # Convert to meters using Earth's radius

        except Exception as e:
            logger.error(f"Error calculating perpendicular distance: {e}")
            return 0

    def export_distance_certificate(self):
        """Generate and export a certificate explaining the turbine distance methodology."""
        try:
            if not hasattr(self, 'turbines') or not self.turbines:
                messagebox.showwarning("Warning", "No turbine data available. Please load turbines first.")
                return

            # Get output directory
            output_dir = filedialog.askdirectory(
                title="Select folder to save Turbine Distance Certificate",
                initialdir=os.path.expanduser("~")
            )
            if not output_dir:
                return

            # Create a temp directory for profile images
            temp_dir = os.path.join(output_dir, "temp")
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            # Generate the site-to-site profile image
            logger.info("Generating site-to-site profile image for certificate")
            profile_image_path = self.generate_site_to_site_profile(save_to_file=True, output_dir=temp_dir)

            # Generate the top-down view image
            logger.info("Generating top-down view image for certificate")
            import turbines
            top_down_image_path = turbines.generate_top_down_view(self, save_to_file=True, output_dir=temp_dir)

            # Generate map view with LOS path, sites and turbines
            logger.info("Generating map view for certificate")
            map_view_path = self.capture_map_view(temp_dir)

            # Prepare turbine data for certificate
            turbine_data = []
            for turbine in self.turbines:
                try:
                    # Get turbine parameters and convert to proper units
                    height_m = float(turbine.get('total_height_m', 100))
                    height_ft = height_m * 3.28084
                    rotor_diameter_m = float(turbine.get('rotor_diameter_m', 100))
                    rotor_diameter_ft = rotor_diameter_m * 3.28084
                    rotor_radius_ft = rotor_diameter_ft / 2

                    # Calculate hub height (use provided hub height if available)
                    if turbine.get('hub_height_m'):
                        hub_height_m = float(turbine['hub_height_m'])
                        hub_height_ft = hub_height_m * 3.28084
                    else:
                        # If no hub height provided, calculate it as total height minus rotor radius
                        hub_height_ft = height_ft - rotor_radius_ft

                    # Calculate turbine position and clearances
                    turbine_lat, turbine_lon = turbine['latitude'], turbine['longitude']
                    turbine_distance = self._calculate_distance_along_path(
                        (turbine_lat, turbine_lon),
                        self.start_coords,
                        self.end_coords
                    )
                    distance_ratio = turbine_distance / self.distances[-1]

                    # Calculate perpendicular distance
                    perpendicular_distance = self._calculate_perpendicular_distance(
                        (turbine_lat, turbine_lon),
                        self.start_coords,
                        self.end_coords
                    )
                    distance_from_path = perpendicular_distance * 3.28084  # Convert to feet

                    # Find ground elevation at turbine position
                    index = int(distance_ratio * (len(self.elevation_data) - 1))
                    ground_elevation = self.elevation_data[index] if 0 <= index < len(self.elevation_data) else 0

                    # Convert turbine distance to feet
                    distance_along_ft = turbine_distance * 3.28084
                    total_distance_ft = self.distances[-1] * 3.28084

                    # Get frequency from tower parameters
                    try:
                        with open('tower_parameters.json', 'r') as f:
                            tower_params = json.load(f)
                            frequency_ghz = float(tower_params['general_parameters']['frequency_ghz'])
                    except Exception as e:
                        logger.warning(f"Could not load frequency from tower parameters: {e}")
                        frequency_ghz = 11.0  # Default frequency

                    # Calculate LOS height at turbine position
                    los_height = self.site_a_data[1] + (self.site_b_data[1] - self.site_a_data[1]) * distance_ratio

                    # Calculate earth curvature bulge
                    bulge = (distance_along_ft * (total_distance_ft - distance_along_ft)) / (2 * self.EARTH_RADIUS)
                    los_height_curved = los_height - bulge

                    # Calculate center height
                    center_height = ground_elevation + hub_height_ft

                    # Calculate shortest distance from rotor center to curved path
                    vertical_distance = abs(los_height_curved - center_height)
                    horizontal_distance = abs(distance_from_path)
                    center_to_path = math.sqrt(horizontal_distance**2 + vertical_distance**2)

                    # Calculate Fresnel radius at this point
                    d1_km = (distance_along_ft / 3280.84)  # Distance from start in km
                    d2_km = (total_distance_ft / 3280.84) - d1_km  # Distance from end in km
                    fresnel_radius = self.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                    # Calculate clearances
                    clearance_straight = center_to_path - rotor_radius_ft  # Straight path clearance
                    clearance_curved = center_to_path - rotor_radius_ft    # Curved path clearance (same as straight in this calc)
                    clearance_fresnel = center_to_path - rotor_radius_ft - fresnel_radius  # Fresnel zone clearance

                    # Add turbine data
                    turbine_data.append({
                        'id': turbine.get('id', 'Unknown'),
                        'latitude': turbine_lat,
                        'longitude': turbine_lon,
                        'total_height_ft': height_ft,
                        'hub_height_ft': hub_height_ft,
                        'rotor_diameter_ft': rotor_diameter_ft,
                        'distance_from_path_ft': distance_from_path,
                        'clearance_straight_ft': clearance_straight,
                        'clearance_curved_ft': clearance_curved,
                        'clearance_fresnel_ft': clearance_fresnel
                    })
                except Exception as e:
                    logger.error(f"Error processing turbine for certificate: {e}")
                    continue

            # Prepare path data in the format expected by the new create_turbine_certificate function
            # Calculate path length in kilometers
            path_length_km = self.distances[-1] / 1000

            # Default frequency (can be made configurable in the future)
            frequency_ghz = 11.0

            # Calculate actual search distance from turbine data for analysis
            # Use the maximum distance found in the turbine data as the threshold
            max_distance_found = 0
            for turbine in turbine_data:
                distance_from_path = turbine.get('distance_from_path_ft', 0)
                if isinstance(distance_from_path, (int, float)):
                    max_distance_found = max(max_distance_found, abs(distance_from_path))
            
            # Use a reasonable buffer above the max distance found, or default to polygon width
            search_distance_ft = max(max_distance_found * 1.1, 2000) if max_distance_found > 0 else 2000
            
            # Save the turbine analysis results to tower_parameters.json
            self.save_turbine_analysis_results(turbine_data, search_distance_ft)

            # Prepare path data dictionary
            path_data = {
                'path_length_km': path_length_km,
                'frequency_ghz': frequency_ghz,
                'start_lat': self.start_coords[0],
                'start_lon': self.start_coords[1],
                'end_lat': self.end_coords[0],
                'end_lon': self.end_coords[1],
                'profile_image_path': profile_image_path,
                'top_down_image_path': top_down_image_path,
                'map_view_path': map_view_path
            }

            # Generate certificate using the certificates module
            logger.info("Generating turbine distance certificate")
            certificate_path = create_turbine_certificate(turbine_data, path_data, output_dir)

            # Open the generated PDF
            if sys.platform == "win32":
                os.startfile(certificate_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", certificate_path])
            else:
                subprocess.run(["xdg-open", certificate_path])

            messagebox.showinfo("Success", f"Certificate has been generated: {certificate_path}")

        except Exception as e:
            logger.error(f"Error generating distance certificate: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to generate certificate: {str(e)}")

    def capture_map_view(self, output_dir):
        """Capture a map view showing the LOS path, sites, and turbines"""
        try:
            # Try the Google Maps Static API approach first (more reliable)
            result = self.generate_google_maps_view(output_dir)
            if result:
                return result

            # Fall back to screenshot method if Google Maps approach fails
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"map_view_{timestamp}.png")

            # Find the map widget in the parent application
            # Since we don't have direct access to the map widget, we need to find it
            # First, get the tkinter root
            root = self.frame
            while not isinstance(root, tk.Tk) and root.master is not None:
                root = root.master

            # Try to find the map widget in the application
            map_widget = None

            # Look for a TkinterMapView instance in the application
            def find_map_widget(widget):
                if hasattr(widget, 'winfo_children'):
                    for child in widget.winfo_children():
                        # Check if this is likely a map widget
                        if child.__class__.__name__ == 'TkinterMapView':
                            return child
                        # Check if the child has a 'map_widget' attribute
                        if hasattr(child, 'map_widget'):
                            return child.map_widget
                        # Recurse into child widgets
                        result = find_map_widget(child)
                        if result:
                            return result
                return None

            # Try to find the map widget
            map_widget = find_map_widget(root)

            if map_widget:
                logger.info("Found map widget, capturing view")

                # Save current map state to restore later
                original_zoom = None
                original_position = None
                original_tile_server = None

                # Save map state if possible
                if hasattr(map_widget, 'get_zoom'):
                    original_zoom = map_widget.get_zoom()
                if hasattr(map_widget, 'get_position'):
                    original_position = map_widget.get_position()
                if hasattr(map_widget, 'tile_server'):
                    original_tile_server = map_widget.tile_server

                # Try to use a better map tile server if available (better contrast)
                try:
                    if hasattr(map_widget, 'set_tile_server'):
                        # Try to set a tile server with better contrast
                        available_servers = getattr(map_widget, 'TILE_SERVER', {})
                        if available_servers and "OPEN_STREET_MAP" in available_servers:
                            map_widget.set_tile_server("OPEN_STREET_MAP")
                except Exception as e:
                    logger.warning(f"Could not change tile server: {e}")

                # Direct approach to hide zoom buttons and controls - more aggressive
                hidden_widgets = []
                original_states = []

                def completely_hide_widget(widget):
                    if hasattr(widget, 'place_forget'):
                        widget.place_forget()
                    if hasattr(widget, 'pack_forget'):
                        widget.pack_forget()
                    if hasattr(widget, 'grid_forget'):
                        widget.grid_forget()
                    if hasattr(widget, 'lower'):
                        widget.lower()  # Put it below other widgets
                    if hasattr(widget, 'winfo_children'):
                        for child in widget.winfo_children():
                            completely_hide_widget(child)

                # First approach: Hide by widget type and using multiple methods
                def find_and_hide_controls(parent):
                    if not hasattr(parent, 'winfo_children'):
                        return

                    for child in parent.winfo_children():
                        # Look for controls by type or name hinting
                        if (isinstance(child, (tk.Button, ttk.Button, tk.Frame, ttk.Frame)) or
                            'button' in str(child).lower() or
                            'control' in str(child).lower() or
                            '+' in str(child) or
                            '-' in str(child)):

                            # Record widget and visibility state
                            hidden_widgets.append(child)
                            original_states.append({
                                'mapped': child.winfo_ismapped(),
                                'visible': child.winfo_viewable(),
                                'width': child.winfo_width(),
                                'height': child.winfo_height()
                            })

                            # Try every method to hide
                            completely_hide_widget(child)

                            # As a backup, make it zero size
                            child.configure(width=0, height=0)

                        # Recurse for all widgets
                        find_and_hide_controls(child)

                # Second approach: Direct access to canvas items for TkinterMapView specifically
                def hide_controls_in_canvas(map_widget):
                    if hasattr(map_widget, 'canvas'):
                        canvas = map_widget.canvas
                        # Try to find and hide zoom buttons directly
                        for item in canvas.find_all():
                            # Hide all non-map items (buttons, controls, etc.)
                            if canvas.type(item) in ('window', 'image'):
                                canvas.itemconfigure(item, state='hidden')

                # Hide all controls using both methods
                try:
                    # Method 1: Recursive widget hiding
                    find_and_hide_controls(map_widget)

                    # Method 2: Canvas-specific approach
                    hide_controls_in_canvas(map_widget)

                    logger.info(f"Hidden {len(hidden_widgets)} control widgets")
                except Exception as hide_error:
                    logger.warning(f"Error hiding controls: {hide_error}")

                # Calculate bounding box with MUCH larger padding
                try:
                    # Get the bounding box for the entire path
                    min_lat = min(self.start_coords[0], self.end_coords[0])
                    max_lat = max(self.start_coords[0], self.end_coords[0])
                    min_lon = min(self.start_coords[1], self.end_coords[1])
                    max_lon = max(self.start_coords[1], self.end_coords[1])

                    # Calculate path distance
                    path_distance_m = self.calculate_distance(
                        (min_lat, min_lon),
                        (max_lat, max_lon)
                    )
                    path_distance_km = path_distance_m / 1000

                    # Use much larger padding that scales with path length
                    padding_factor = 1.0  # 100% padding (doubled from previous)

                    # For very short paths, use even more padding
                    if path_distance_km < 5:
                        padding_factor = 1.5  # 150% padding
                    elif path_distance_km < 10:
                        padding_factor = 1.2  # 120% padding

                    lat_diff = max_lat - min_lat
                    lon_diff = max_lon - min_lon

                    # Use the larger of the two differences for both dimensions
                    # This ensures a more square view which is better for seeing context
                    max_diff = max(lat_diff, lon_diff)

                    # Apply padding
                    min_lat -= max_diff * padding_factor
                    max_lat += max_diff * padding_factor
                    min_lon -= max_diff * padding_factor
                    max_lon += max_diff * padding_factor

                    # Include turbines in the bounding box if available
                    if hasattr(self, 'turbines') and self.turbines:
                        for turbine in self.turbines:
                            try:
                                turbine_lat = float(turbine.get('latitude', 0))
                                turbine_lon = float(turbine.get('longitude', 0))
                                min_lat = min(min_lat, turbine_lat)
                                max_lat = max(max_lat, turbine_lat)
                                min_lon = min(min_lon, turbine_lon)
                                max_lon = max(max_lon, turbine_lon)
                            except (ValueError, TypeError):
                                pass

                    # Set up the map view
                    logger.info(f"Setting map view to bounds: ({min_lat},{min_lon}) to ({max_lat},{max_lon})")

                    # Try multiple approaches to set the view
                    success = False

                    # Method 1: fit_bounds
                    if hasattr(map_widget, 'fit_bounds') and not success:
                        try:
                            map_widget.fit_bounds((min_lat, min_lon), (max_lat, max_lon))
                            success = True
                        except Exception as e:
                            logger.warning(f"fit_bounds failed: {e}")

                    # Method 2: set_bounds
                    if hasattr(map_widget, 'set_bounds') and not success:
                        try:
                            map_widget.set_bounds((min_lat, min_lon), (max_lat, max_lon))
                            success = True
                        except Exception as e:
                            logger.warning(f"set_bounds failed: {e}")

                    # Method 3: set_position & set_zoom
                    if hasattr(map_widget, 'set_position') and hasattr(map_widget, 'set_zoom') and not success:
                        try:
                            # Calculate center
                            center_lat = (min_lat + max_lat) / 2
                            center_lon = (min_lon + max_lon) / 2

                            # Calculate appropriate zoom level
                            max_range = max(max_lat - min_lat, max_lon - min_lon) * 111  # km (approx)
                            zoom_level = max(1, min(int(14 - math.log(max_range, 2)), 18))

                            # Set both position and zoom
                            map_widget.set_position(center_lat, center_lon)
                            map_widget.set_zoom(zoom_level)
                            success = True
                        except Exception as e:
                            logger.warning(f"set_position/set_zoom failed: {e}")

                    # Wait longer for map to fully load and render
                    root.update()
                    time.sleep(2.0)  # Wait 2 full seconds for map tiles to load

                except Exception as e:
                    logger.warning(f"Error preparing map view: {e}")

                # Capture the map view
                try:
                    # One more update to ensure rendering is complete
                    root.update()

                    # Capture the map widget
                    x = map_widget.winfo_rootx()
                    y = map_widget.winfo_rooty()
                    width = map_widget.winfo_width()
                    height = map_widget.winfo_height()

                    # Take the screenshot
                    image = ImageGrab.grab(bbox=(x, y, x+width, y+height))

                    # Save the image
                    image.save(output_path)
                    logger.info(f"Saved map view to {output_path}")

                    # Restore hidden widgets
                    for i, widget in enumerate(hidden_widgets):
                        try:
                            # Restore original size
                            if 'width' in original_states[i] and 'height' in original_states[i]:
                                widget.configure(width=original_states[i]['width'],
                                              height=original_states[i]['height'])

                            # Repack/place/grid as needed
                            if original_states[i]['mapped']:
                                if hasattr(widget, 'pack'):
                                    widget.pack(side='top')
                                elif hasattr(widget, 'place'):
                                    widget.place(x=0, y=0)
                                elif hasattr(widget, 'grid'):
                                    widget.grid()
                        except Exception as restore_error:
                            logger.warning(f"Error restoring widget: {restore_error}")

                    # Restore map view
                    if original_zoom and hasattr(map_widget, 'set_zoom'):
                        map_widget.set_zoom(original_zoom)
                    if original_position and hasattr(map_widget, 'set_position'):
                        map_widget.set_position(*original_position)
                    if original_tile_server and hasattr(map_widget, 'set_tile_server'):
                        map_widget.set_tile_server(original_tile_server)

                    # Force update
                    root.update()

                    return output_path
                except Exception as e:
                    logger.error(f"Error capturing map screenshot: {e}")

                    # Restore state even if capture failed
                    for i, widget in enumerate(hidden_widgets):
                        try:
                            # Restore original size
                            if 'width' in original_states[i] and 'height' in original_states[i]:
                                widget.configure(width=original_states[i]['width'],
                                              height=original_states[i]['height'])

                            # Repack/place/grid as needed
                            if original_states[i]['mapped']:
                                if hasattr(widget, 'pack'):
                                    widget.pack(side='top')
                                elif hasattr(widget, 'place'):
                                    widget.place(x=0, y=0)
                                elif hasattr(widget, 'grid'):
                                    widget.grid()
                        except Exception as restore_error:
                            logger.warning(f"Error restoring widget: {restore_error}")

                    # Restore map view
                    if original_zoom and hasattr(map_widget, 'set_zoom'):
                        map_widget.set_zoom(original_zoom)
                    if original_position and hasattr(map_widget, 'set_position'):
                        map_widget.set_position(*original_position)
                    if original_tile_server and hasattr(map_widget, 'set_tile_server'):
                        map_widget.set_tile_server(original_tile_server)

                    # Force update
                    root.update()
            else:
                logger.warning("Map widget not found, cannot capture map view")

            # If we reach here, something went wrong
            # Try Google Maps Static API as a fallback
            result = self.generate_google_maps_view(output_dir)
            if result:
                return result

            # If all else fails, generate a fallback map view
            return self._generate_enhanced_fallback_map_view(output_dir)

        except Exception as e:
            logger.error(f"Error capturing map view: {e}")
            # Try Google Maps Static API as a fallback
            result = self.generate_google_maps_view(output_dir)
            if result:
                return result

            return self._generate_enhanced_fallback_map_view(output_dir)

    def generate_google_maps_view(self, output_dir):
        """Generate a map view using Google Maps Static API directly."""
        try:
            # Get API key from environment
            api_key = os.getenv("GOOGLE_MAPS_API_KEY")
            if not api_key:
                logger.warning("Google Maps API key not found in environment.")
                return None

            logger.info("Using Google Maps Static API to generate map view")

            # Create output filename
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"map_view_{timestamp}.png")

            # Calculate map bounds
            min_lat = min(self.start_coords[0], self.end_coords[0])
            max_lat = max(self.start_coords[0], self.end_coords[0])
            min_lon = min(self.start_coords[1], self.end_coords[1])
            max_lon = max(self.start_coords[1], self.end_coords[1])

            # Include turbines in the bounding box if available
            if hasattr(self, 'turbines') and self.turbines:
                for turbine in self.turbines:
                    try:
                        turbine_lat = float(turbine.get('latitude', 0))
                        turbine_lon = float(turbine.get('longitude', 0))
                        min_lat = min(min_lat, turbine_lat)
                        max_lat = max(max_lat, turbine_lat)
                        min_lon = min(min_lon, turbine_lon)
                        max_lon = max(max_lon, turbine_lon)
                    except (ValueError, TypeError):
                        pass

            # Add padding to the bounds (10% of width/height)
            lat_range = max_lat - min_lat
            lon_range = max_lon - min_lon
            min_lat -= lat_range * 0.15
            max_lat += lat_range * 0.15
            min_lon -= lon_range * 0.15
            max_lon += lon_range * 0.15

            # Set image size - wide rectangular shape to fit on first page
            img_width = 540
            img_height = 300

            # Get site names from tower_parameters.json if available
            donor_name = "Donor Site"
            recipient_name = "Recipient Site"

            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    site_a = tower_params.get('site_A', {})
                    site_b = tower_params.get('site_B', {})
                    donor_name = site_a.get('site_id', "Donor Site")
                    recipient_name = site_b.get('site_id', "Recipient Site")
            except Exception as e:
                logger.warning(f"Could not load site names from tower parameters: {e}")

            # Build the Google Maps Static API URL
            base_url = "https://maps.googleapis.com/maps/api/staticmap"

            # Initialize parameters
            params = {
                'size': f"{img_width}x{img_height}",
                'maptype': 'satellite',  # Changed from 'roadmap' to 'satellite'
                'key': api_key,
                'format': 'png',
                'scale': 2,  # High-resolution (2x)
            }

            # Define bounds
            params['visible'] = f"{min_lat},{min_lon}|{max_lat},{max_lon}"

            # Add markers
            # Blue marker for Donor site (small size)
            donor_marker = f"size:small|color:blue|label:D|{self.start_coords[0]},{self.start_coords[1]}"
            # Red marker for Recipient site (small size)
            recipient_marker = f"size:small|color:red|label:R|{self.end_coords[0]},{self.end_coords[1]}"

            params['markers'] = [donor_marker, recipient_marker]

            # Add purple markers for turbines
            if hasattr(self, 'turbines') and self.turbines:
                for i, turbine in enumerate(self.turbines):
                    try:
                        turbine_lat = float(turbine.get('latitude', 0))
                        turbine_lon = float(turbine.get('longitude', 0))
                        turbine_id = turbine.get('id', f"{i+1}")

                        # Create a marker for this turbine (use T label or number if multiple turbines)
                        label = "T" if len(self.turbines) == 1 else str((i % 9) + 1)  # Google only allows 1-9 labels
                        turbine_marker = f"color:purple|label:{label}|{turbine_lat},{turbine_lon}"
                        params['markers'].append(turbine_marker)
                    except Exception as e:
                        logger.warning(f"Error adding turbine marker: {e}")

            # Add path between sites
            path_color = "0x0000FF"  # Blue
            path_weight = 5
            path = f"color:{path_color}|weight:{path_weight}|{self.start_coords[0]},{self.start_coords[1]}|{self.end_coords[0]},{self.end_coords[1]}"
            params['path'] = path

            # Build the final URL
            url = base_url

            # Add all parameters to the request
            response = requests.get(url, params=params)

            if response.status_code == 200:
                # Save the image
                with open(output_path, 'wb') as f:
                    f.write(response.content)

                logger.info(f"Successfully generated Google Maps image: {output_path}")

                # Optionally add labels to the image
                try:
                    from PIL import Image, ImageDraw, ImageFont

                    # Open the image
                    img = Image.open(output_path)
                    draw = ImageDraw.Draw(img)

                    # Try to get a nice font (fall back to default if not available)
                    try:
                        # For MacOS
                        font_path = '/System/Library/Fonts/Helvetica.ttc'
                        if not os.path.exists(font_path):
                            # For Windows
                            font_path = 'C:/Windows/Fonts/Arial.ttf'
                        if not os.path.exists(font_path):
                            # For Linux
                            font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'

                        font = ImageFont.truetype(font_path, 20)
                        small_font = ImageFont.truetype(font_path, 16)
                    except Exception:
                        # Use default font if custom font fails
                        font = ImageFont.load_default()
                        small_font = ImageFont.load_default()

                    # Add title at the top (white box with black text)
                    title = f"{donor_name} to {recipient_name}"
                    # Measure text size
                    try:
                        title_width = draw.textlength(title, font=font)
                    except:
                        title_width = len(title) * 12  # Fallback estimate

                    # Draw background box
                    draw.rectangle(
                        [(img.width - title_width - 20) / 2, 10,
                         (img.width + title_width + 20) / 2, 40],
                        fill="white",
                        outline="black"
                    )

                    # Draw text
                    draw.text(
                        (img.width // 2, 25),
                        title,
                        fill="black",
                        font=font,
                        anchor="mm"  # Center aligned
                    )

                    # Add coordinates for donor site (bottom left)
                    donor_text = f"{donor_name}: {self.start_coords[0]:.6f}, {self.start_coords[1]:.6f}"
                    draw.rectangle(
                        [10, img.height - 50, 10 + len(donor_text) * 8, img.height - 10],
                        fill="rgba(255, 255, 255, 200)",
                        outline="blue"
                    )
                    draw.text(
                        (15, img.height - 30),
                        donor_text,
                        fill="blue",
                        font=small_font
                    )

                    # Add coordinates for recipient site (bottom right)
                    recipient_text = f"{recipient_name}: {self.end_coords[0]:.6f}, {self.end_coords[1]:.6f}"
                    try:
                        text_width = draw.textlength(recipient_text, font=small_font)
                    except:
                        text_width = len(recipient_text) * 8  # Fallback estimate

                    draw.rectangle(
                        [img.width - text_width - 20, img.height - 50,
                         img.width - 10, img.height - 10],
                        fill="rgba(255, 255, 255, 200)",
                        outline="red"
                    )
                    draw.text(
                        (img.width - 15, img.height - 30),
                        recipient_text,
                        fill="red",
                        font=small_font,
                        anchor="ra"  # Right aligned
                    )

                    # Save the modified image
                    img.save(output_path)
                    logger.info("Added labels to Google Maps image")

                except Exception as e:
                    logger.warning(f"Could not add labels to image: {e}")

                return output_path
            else:
                logger.error(f"Google Maps API request failed: {response.status_code}, {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error generating Google Maps view: {e}")
            return None

    def _generate_enhanced_fallback_map_view(self, output_dir):
        """Generate an enhanced fallback map view using matplotlib with better styling"""
        try:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            output_path = os.path.join(output_dir, f"map_view_{timestamp}.png")

            # Create a matplotlib figure with a nice size
            fig, ax = plt.subplots(figsize=(10, 8), dpi=100)

            # Add a light background color to simulate a map
            ax.set_facecolor('#f2f2f2')

            # Calculate lat/lon extents
            min_lat = min(self.start_coords[0], self.end_coords[0])
            max_lat = max(self.start_coords[0], self.end_coords[0])
            min_lon = min(self.start_coords[1], self.end_coords[1])
            max_lon = max(self.start_coords[1], self.end_coords[1])

            # Add padding
            lat_padding = (max_lat - min_lat) * 0.3
            lon_padding = (max_lon - min_lon) * 0.3
            min_lat -= lat_padding
            max_lat += lat_padding
            min_lon -= lon_padding
            max_lon += lon_padding

            # Create a thicker, nicer looking path line
            path_xs = [self.start_coords[1], self.end_coords[1]]
            path_ys = [self.start_coords[0], self.end_coords[0]]

            # Draw a thicker black line first for a nice border effect
            ax.plot(path_xs, path_ys, 'k-', linewidth=6, alpha=0.5)
            # Then draw the blue line on top
            ax.plot(path_xs, path_ys, 'b-', linewidth=4, label='Microwave Path')

            # Add a nice marker style for sites
            # Donor site (start) - Blue marker
            donor_scatter = ax.scatter([self.start_coords[1]], [self.start_coords[0]],
                                     color='blue', s=150, label='Donor Site',
                                     marker='o', edgecolor='white', linewidth=2, zorder=10)

            # Recipient site (end) - Red marker
            recip_scatter = ax.scatter([self.end_coords[1]], [self.end_coords[0]],
                                     color='red', s=150, label='Recipient Site',
                                     marker='o', edgecolor='white', linewidth=2, zorder=10)

            # Get site IDs if available
            donor_id = "Donor Site"
            recipient_id = "Recipient Site"

            try:
                # Try to load tower parameters for site details
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    # Extract site IDs
                    site_a = tower_params.get('site_A', {})
                    site_b = tower_params.get('site_B', {})
                    donor_id = site_a.get('site_id', "Donor Site")
                    recipient_id = site_b.get('site_id', "Recipient Site")
            except Exception as e:
                logger.warning(f"Could not load site IDs from tower parameters: {e}")

            # Add site labels with better positioning and style
            # Donor site
            # Calculate positions for the labels to avoid overlap
            donor_x, donor_y = self.start_coords[1], self.start_coords[0]
            recip_x, recip_y = self.end_coords[1], self.end_coords[0]

            # Add text boxes for the labels with nice styling
            donor_label = f"{donor_id}\n{donor_y:.6f}, {donor_x:.6f}"
            recip_label = f"{recipient_id}\n{recip_y:.6f}, {recip_x:.6f}"

            # Add donor site label
            ax.annotate(donor_label, (donor_x, donor_y),
                       xytext=(15, 15), textcoords='offset points',
                       bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="blue", alpha=0.8),
                       color='black', fontsize=9, ha='left', va='bottom')

            # Add recipient site label
            ax.annotate(recip_label, (recip_x, recip_y),
                       xytext=(15, 15), textcoords='offset points',
                       bbox=dict(boxstyle="round,pad=0.5", fc="white", ec="red", alpha=0.8),
                       color='black', fontsize=9, ha='left', va='bottom')

            # Add turbines with nicer styling
            if hasattr(self, 'turbines') and self.turbines:
                turbine_lats = [float(t['latitude']) for t in self.turbines]
                turbine_lons = [float(t['longitude']) for t in self.turbines]

                # Plot turbines with a distinctive style
                ax.scatter(turbine_lons, turbine_lats, color='purple',
                         marker='o', s=100, label='Wind Turbines',
                         edgecolor='white', linewidth=1, zorder=5, alpha=0.7)

                # Add nicer turbine labels
                for i, turbine in enumerate(self.turbines):
                    turbine_id = turbine.get('id', f"T{i+1}")
                    ax.annotate(f"Turbine {turbine_id}",
                              (float(turbine['longitude']), float(turbine['latitude'])),
                              xytext=(5, -15), textcoords='offset points',
                              bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="purple", alpha=0.7),
                              fontsize=8, color='black', ha='center', va='top')

            # Add a nice border
            for spine in ax.spines.values():
                spine.set_edgecolor('#cccccc')
                spine.set_linewidth(1)

            # Add subtle grid lines
            ax.grid(True, linestyle='--', alpha=0.4, color='#aaaaaa')

            # Set axis limits
            ax.set_xlim(min_lon, max_lon)
            ax.set_ylim(min_lat, max_lat)

            # Add labels and title
            ax.set_xlabel('Longitude', fontsize=10)
            ax.set_ylabel('Latitude', fontsize=10)

            # Create a cleaner legend
            legend = ax.legend(loc='upper right', framealpha=0.9, fontsize=9)
            legend.get_frame().set_edgecolor('#cccccc')

            # Save figure with tight layout and high quality
            plt.tight_layout()
            fig.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close(fig)

            logger.info(f"Generated enhanced fallback map view at {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Error generating enhanced fallback map view: {e}")
            return None

    def calculate_fresnel_radius(self, d1_km, d2_km, frequency_ghz=11):
        """Calculate Fresnel zone radius at a point along the path.

        Args:
            d1_km: Distance from start point in kilometers
            d2_km: Distance from end point in kilometers
            frequency_ghz: Frequency in GHz (default 11 GHz)

        Returns:
            Radius of Fresnel zone in feet
        """
        try:
            # Calculate Fresnel radius in meters
            # F1 = 17.32 * sqrt((d1 * d2)/(f * D))
            # where d1,d2 are distances in km, f is freq in GHz, D is total path length in km
            D = (d1_km + d2_km)  # Total path length
            F1 = 17.32 * math.sqrt((d1_km * d2_km)/(frequency_ghz * D))

            # Convert radius from meters to feet
            return F1 * 3.28084
        except Exception as e:
            logger.error(f"Error calculating Fresnel radius: {e}")
            return 0

    def view_turbine_data(self):
        """Display turbine data in a tabbed popup window"""
        try:
            if not hasattr(self, 'turbines') or not self.turbines:
                # Try loading turbines from tower_parameters.json
                try:
                    with open('tower_parameters.json', 'r') as f:
                        data = json.load(f)
                        if 'turbines' in data and data['turbines']:
                            self.turbines = data['turbines']
                            logger.info(f"Loaded {len(self.turbines)} turbines from JSON file")
                        else:
                            logger.warning("No turbines found in JSON file")
                            messagebox.showwarning("No Data", "No turbine data available. Search for turbines first.")
                            return
                except Exception as e:
                    logger.error(f"Error loading turbines from JSON: {e}")
                    messagebox.showwarning("No Data", "No turbine data available. Search for turbines first.")
                    return

            # Find the root window
            root = self.frame
            while not isinstance(root, tk.Tk) and not isinstance(root, tk.Toplevel):
                root = root.master
                if root is None:
                    break

            # Display turbine data using the turbines module
            turbines.display_turbine_data(root, self.turbines)

        except Exception as e:
            logger.error(f"Error viewing turbine data: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to view turbine data: {str(e)}")

    def generate_top_down_view(self):
        """Generate a top-down view of the path and turbines"""
        try:
            if not hasattr(self, 'turbines') or not self.turbines:
                messagebox.showwarning("Warning", "No turbine data available. Please load turbines first.")
                return

            # Import the turbines module at runtime to avoid circular imports
            import turbines

            # Call the function from the turbines module to generate the top-down view
            turbines.generate_top_down_view(self)

        except Exception as e:
            logger.error(f"Error generating top-down view: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to generate top-down view: {str(e)}")

    def save_turbine_analysis_results(self, turbine_data, distance_threshold_ft=None):
        """Save turbine analysis results to tower_parameters.json for use in reporting
        
        Args:
            turbine_data: List of turbine analysis data
            distance_threshold_ft: Distance threshold in feet for "nearby" turbines (default: calculate from data)
        """
        try:
            # First load the existing tower_parameters.json
            if os.path.exists('tower_parameters.json'):
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
            else:
                logger.warning("tower_parameters.json not found, creating new file")
                tower_params = {
                    "site_A": {},
                    "site_B": {},
                    "general_parameters": {},
                    "turbines": []
                }

            # Calculate summary statistics
            turbines_near_path = []
            closest_turbine_to_path = None
            closest_turbine_to_fresnel = None
            min_distance_to_path = float('inf')
            min_distance_to_fresnel = float('inf')
            
            # If no distance threshold provided, calculate a reasonable one from the data
            # or use the maximum distance found, or default to a large value
            if distance_threshold_ft is None:
                # Find the maximum distance in the data to avoid arbitrary cutoffs
                max_distance = 0
                for turbine in turbine_data:
                    distance_from_path = turbine.get('distance_from_path_ft', 0)
                    if isinstance(distance_from_path, (int, float)):
                        max_distance = max(max_distance, abs(distance_from_path))
                
                # Use maximum distance found, or default to 5000ft if no turbines
                distance_threshold_ft = max(max_distance, 5000) if max_distance > 0 else 5000

            for turbine in turbine_data:
                turbine_id = turbine.get('id', 'Unknown')
                distance_from_path = turbine.get('distance_from_path_ft', float('inf'))
                clearance_curved = turbine.get('clearance_curved_ft', float('inf'))  # "with curve" measurement
                clearance_fresnel = turbine.get('clearance_fresnel_ft', float('inf'))

                # Use absolute value to ensure positive numbers for display
                abs_distance = abs(distance_from_path) if isinstance(distance_from_path, (int, float)) else float('inf')
                abs_curved = abs(clearance_curved) if isinstance(clearance_curved, (int, float)) else float('inf')
                abs_clearance = abs(clearance_fresnel) if isinstance(clearance_fresnel, (int, float)) else float('inf')

                # Track turbines within the distance threshold from path (absolute distance)
                if isinstance(distance_from_path, (int, float)) and abs_distance <= distance_threshold_ft:
                    turbines_near_path.append(turbine_id)

                # Track closest turbine to path using the "with curve" measurement
                if isinstance(clearance_curved, (int, float)) and abs_curved < min_distance_to_path:
                    min_distance_to_path = abs_curved
                    closest_turbine_to_path = turbine_id

                # Track closest turbine to fresnel zone (absolute distance)
                if isinstance(clearance_fresnel, (int, float)) and abs_clearance < min_distance_to_fresnel:
                    min_distance_to_fresnel = abs_clearance
                    closest_turbine_to_fresnel = turbine_id

            # Create analysis results section if it doesn't exist
            if 'analysis_results' not in tower_params:
                tower_params['analysis_results'] = {}

            # Add the summary statistics with dynamic distance threshold
            distance_key = f'turbines_within_{int(distance_threshold_ft)}ft'
            tower_params['analysis_results'][distance_key] = turbines_near_path
            tower_params['analysis_results']['search_distance_ft'] = distance_threshold_ft
            tower_params['analysis_results']['closest_turbine_to_path'] = {
                'turbine_id': closest_turbine_to_path,
                'distance_ft': min_distance_to_path
            }
            tower_params['analysis_results']['closest_turbine_to_fresnel'] = {
                'turbine_id': closest_turbine_to_fresnel,
                'distance_ft': min_distance_to_fresnel
            }

            # Save full turbine analysis data
            tower_params['analysis_results']['turbine_analysis'] = turbine_data

            # Write updated data back to file
            with open('tower_parameters.json', 'w') as f:
                json.dump(tower_params, f, indent=2)

            logger.info("Saved turbine analysis results to tower_parameters.json")
            return True

        except Exception as e:
            logger.error(f"Error saving turbine analysis results: {e}", exc_info=True)
            return False