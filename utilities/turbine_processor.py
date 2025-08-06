"""
Turbine detection and visualization module for microwave link path analysis.
This module provides functionality to search for wind turbines within a specified area
and visualize them on a map.

UPDATED: Now uses the unified turbine clearance calculator for consistent, accurate results.
"""

import os
import json
import logging
import math
import requests
import tkinter as tk
from tkinter import messagebox
import zipfile
import shutil
import time
from log_config import setup_logging

# Import the unified clearance calculator
from .turbine_clearance_calculator import (
    TurbineClearanceCalculator,
    TurbineData,
    PathData,
    create_turbine_from_dict,
    create_path_from_tower_params
)

# Create logger
logger = setup_logging(__name__)

class TurbineProcessor:
    # URL for the USGS Wind Turbine Database GeoJSON file
    TURBINE_DB_URL = "https://energy.usgs.gov/uswtdb/assets/data/uswtdbGeoJSON.zip"

    def __init__(self, map_widget=None, root=None, elevation_profile=None):
        """Initialize the turbine processor with the required components"""
        self.map_widget = map_widget
        self.root = root
        self.elevation_profile = elevation_profile
        self.show_turbine_labels = tk.BooleanVar(value=False)
        self.turbine_markers = []
        self.last_turbines = []
        self.polygon_points = None

        # Initialize the unified clearance calculator
        self.clearance_calculator = TurbineClearanceCalculator()
        self.last_clearance_results = []  # Store detailed clearance results

        # Set up paths for turbine database files
        self.turbine_db_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "turbine_db")
        self.geojson_dir = os.path.join(self.turbine_db_dir, "uswtdbGeoJSON")
        self.geojson_file = None  # Will be set when needed

        # Find the most recent GeoJSON file
        self._find_latest_geojson_file()

        # Initialize file_list reference
        self.file_list = None

    def set_map_widget(self, map_widget):
        """Set the map widget for visualization"""
        self.map_widget = map_widget

    def set_root(self, root):
        """Set the root window for UI updates"""
        self.root = root

    def set_file_list(self, file_list):
        """Set the file list for UI updates"""
        self.file_list = file_list

    def _find_latest_geojson_file(self):
        """Find the most recent GeoJSON file in the turbine database directory"""
        try:
            # Check if the geojson directory exists
            if not os.path.exists(self.geojson_dir):
                logger.warning(f"GeoJSON directory does not exist: {self.geojson_dir}")
                return

            # Look for GeoJSON files
            geojson_files = []
            for filename in os.listdir(self.geojson_dir):
                if filename.endswith('.geojson'):
                    filepath = os.path.join(self.geojson_dir, filename)
                    # Get modification time
                    mtime = os.path.getmtime(filepath)
                    geojson_files.append((mtime, filepath))

            if geojson_files:
                # Sort by modification time and get the latest
                geojson_files.sort(reverse=True)
                self.geojson_file = geojson_files[0][1]
                logger.info(f"Using GeoJSON file: {self.geojson_file}")
            else:
                logger.warning("No GeoJSON files found in directory")
        except Exception as e:
            logger.error(f"Error finding GeoJSON file: {e}")

    def _download_turbine_database(self):
        """Download and extract the turbine database if needed"""
        try:
            # Create directories if they don't exist
            os.makedirs(self.turbine_db_dir, exist_ok=True)
            os.makedirs(self.geojson_dir, exist_ok=True)

            zip_file_path = os.path.join(self.turbine_db_dir, "uswtdbGeoJSON.zip")

            # Download the zip file
            logger.info("Downloading turbine database...")
            response = requests.get(self.TURBINE_DB_URL, stream=True, timeout=30)
            response.raise_for_status()

            with open(zip_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Extract the zip file
            logger.info("Extracting turbine database...")
            with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
                zip_ref.extractall(self.geojson_dir)

            # Find the extracted GeoJSON file
            self._find_latest_geojson_file()

            # Clean up the zip file
            os.remove(zip_file_path)

            logger.info("Turbine database downloaded and extracted successfully")
            return True

        except Exception as e:
            logger.error(f"Error downloading turbine database: {e}")
            return False

    def _load_turbines_from_geojson(self, min_lat=None, max_lat=None, min_lon=None, max_lon=None, state_name=None):
        """Load turbines from the GeoJSON file with optional filtering

        Args:
            min_lat: Minimum latitude for bounding box filter
            max_lat: Maximum latitude for bounding box filter
            min_lon: Minimum longitude for bounding box filter
            max_lon: Maximum longitude for bounding box filter
            state_name: State abbreviation to filter by (e.g., 'CO')

        Returns:
            list: List of turbine dictionaries
        """
        # Make sure we have a GeoJSON file
        if not self.geojson_file:
            self._find_latest_geojson_file()

        if not self.geojson_file or not os.path.exists(self.geojson_file):
            logger.warning("No GeoJSON file found in expected locations")
            # Do not attempt to download - just return empty list
            return []

        # Load the GeoJSON file
        try:
            logger.info(f"Loading turbines from {self.geojson_file}")
            with open(self.geojson_file, 'r') as f:
                geojson_data = json.load(f)

            # Extract features
            features = geojson_data.get('features', [])
            logger.info(f"Loaded {len(features)} turbines from GeoJSON file")

            # Convert to the format expected by the rest of the code
            turbines = []
            for feature in features:
                # GeoJSON coordinates are [lon, lat]
                coords = feature.get('geometry', {}).get('coordinates', [])
                properties = feature.get('properties', {})

                if coords and len(coords) >= 2:
                    # Create a turbine dictionary with the expected fields
                    turbine = {
                        'case_id': properties.get('case_id'),
                        'ylat': coords[1],  # Latitude
                        'xlong': coords[0],  # Longitude
                        't_state': properties.get('t_state'),
                        'p_name': properties.get('p_name'),
                        'p_year': properties.get('p_year'),
                        't_manu': properties.get('t_manu'),
                        't_model': properties.get('t_model'),
                        't_cap': properties.get('t_cap'),
                        't_hh': properties.get('t_hh'),
                        't_rd': properties.get('t_rd'),
                        't_rsa': properties.get('t_rsa'),
                        't_ttlh': properties.get('t_ttlh')
                    }
                    turbines.append(turbine)

            logger.info(f"Converted {len(turbines)} turbines to the expected format")

            # Apply filters
            filtered_turbines = turbines

            # Filter by bounding box if provided
            if min_lat is not None and max_lat is not None and min_lon is not None and max_lon is not None:
                filtered_turbines = [
                    t for t in filtered_turbines
                    if min_lat <= t['ylat'] <= max_lat and min_lon <= t['xlong'] <= max_lon
                ]
                logger.info(f"Filtered to {len(filtered_turbines)} turbines in bounding box")

            # Filter by state if provided
            if state_name:
                filtered_turbines = [
                    t for t in filtered_turbines
                    if t['t_state'] == state_name
                ]
                logger.info(f"Filtered to {len(filtered_turbines)} turbines in state {state_name}")

            return filtered_turbines

        except Exception as e:
            logger.error(f"Error loading turbines from GeoJSON file: {e}")
            return []

    def set_elevation_profile(self, elevation_profile):
        """Set the elevation profile for displaying turbines on the profile"""
        self.elevation_profile = elevation_profile

    def set_polygon_points(self, polygon_points):
        """Set the polygon points defining the search area"""
        self.polygon_points = polygon_points

    def find_turbines(self, polygon_points=None, obstruction_text=None):
        """
        Search for wind turbines within the LIDAR path area using unified clearance calculator.
        
        This method now provides consistent, accurate clearance calculations regardless
        of the entry point used.
        """
        try:
            # Use provided polygon points or the stored ones
            if polygon_points:
                self.polygon_points = polygon_points

            if not self.polygon_points:
                if self.root:
                    messagebox.showwarning("No Search Area",
                                         "Please load a project first to define the search area.")
                return []

            logger.info("Starting turbine search with unified clearance calculator...")

            # Get bounding box from polygon points with extra padding
            lats = [point[0] for point in self.polygon_points]
            lons = [point[1] for point in self.polygon_points]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)

            # Use reasonable padding (0.05 degrees ≈ 3 miles) to reduce unnecessary API data
            padding = 0.05
            min_lat -= padding
            max_lat += padding
            min_lon -= padding
            max_lon += padding

            logger.info(f"Search bounds: Lat [{min_lat:.6f}, {max_lat:.6f}], Lon [{min_lon:.6f}, {max_lon:.6f}]")

            # Find which state contains the center point
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)

            # State boundary definitions
            state_bounds = {
                'WY': {'min_lat': 41.00, 'max_lat': 45.01, 'min_lon': -111.06, 'max_lon': -104.05},
                'CO': {'min_lat': 36.99, 'max_lat': 41.00, 'min_lon': -109.05, 'max_lon': -102.04},
                'NE': {'min_lat': 40.00, 'max_lat': 43.00, 'min_lon': -104.05, 'max_lon': -95.31},
                'SD': {'min_lat': 42.48, 'max_lat': 45.94, 'min_lon': -104.06, 'max_lon': -96.44},
                'MT': {'min_lat': 44.36, 'max_lat': 49.00, 'min_lon': -116.05, 'max_lon': -104.04},
                # Add more states as needed
            }

            # Find which state contains the center point
            state_name = None
            for state, bounds in state_bounds.items():
                if (bounds['min_lat'] <= center_lat <= bounds['max_lat'] and
                    bounds['min_lon'] <= center_lon <= bounds['max_lon']):
                    state_name = state
                    break

            logger.info(f"Detected state: {state_name if state_name else 'Unknown'}")

            # Primary USWTDB API endpoint (updated 2025)
            primary_url = "https://energy.usgs.gov/api/uswtdb/v1/turbines"
            # Backup endpoint (updated 2025)
            backup_url = "https://energy.usgs.gov/arcgis/rest/services/Hosted/uswtdbDyn/FeatureServer/0/query"

            # Query parameters
            params = {
                "select": "*",
                "and": f"(ylat.gte.{min_lat},ylat.lte.{max_lat},xlong.gte.{min_lon},xlong.lte.{max_lon})"
            }

            # Reduced timeout to 5 seconds
            timeout = 5
            turbines = None

            # Try primary endpoint first
            try:
                logger.info(f"Querying turbines with {timeout}s timeout")
                response = requests.get(primary_url, params=params, timeout=timeout)
                response.raise_for_status()
                turbines = response.json()
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Found {len(turbines)} turbines in bounding box")
            except Exception as e:
                logger.warning(f"Primary endpoint failed: {e}, trying backup endpoint")

                # Try backup endpoint (ArcGIS REST API has different parameters)
                try:
                    logger.info(f"Querying turbines from backup endpoint with {timeout}s timeout")
                    # ArcGIS REST API uses different parameters
                    arcgis_params = {
                        "where": f"ylat >= {min_lat} AND ylat <= {max_lat} AND xlong >= {min_lon} AND xlong <= {max_lon}",
                        "outFields": "*",
                        "returnGeometry": "true",
                        "f": "json"
                    }
                    response = requests.get(backup_url, params=arcgis_params, timeout=timeout)
                    response.raise_for_status()
                    arcgis_response = response.json()

                    # Convert ArcGIS format to match the API format
                    if 'features' in arcgis_response:
                        turbines = [feature['attributes'] for feature in arcgis_response['features']]
                        logger.info(f"Backup endpoint response status: {response.status_code}, found {len(turbines)} turbines")
                except Exception as e:
                    logger.warning(f"Backup endpoint failed: {e}, trying GeoJSON file fallback")

                    # Try GeoJSON file fallback
                    try:
                        logger.info("Trying GeoJSON file fallback")
                        # Try to load turbines from the GeoJSON file
                        turbines = self._load_turbines_from_geojson(
                            min_lat=min_lat, max_lat=max_lat,
                            min_lon=min_lon, max_lon=max_lon
                        )

                        if turbines:
                            logger.info(f"GeoJSON file fallback successful, found {len(turbines)} turbines in bounding box")
                        else:
                            # Show a message to the user
                            if obstruction_text:
                                obstruction_text.config(state="normal")
                                obstruction_text.delete("1.0", tk.END)
                                obstruction_text.insert(tk.END, f"Turbine data service is currently unavailable.\n\nPlease check your internet connection or try again later.")
                                obstruction_text.config(state="disabled")
                            logger.warning("No turbines found in GeoJSON file and not attempting to download")
                    except Exception as e:
                        logger.error(f"All endpoints and GeoJSON fallback failed. Error: {str(e)}")
                        raise Exception("Failed to fetch turbine data. Please check your internet connection or try again later.")

            # If we still don't have turbines, raise an error
            if turbines is None:
                raise Exception("Failed to fetch turbine data from all endpoints")

            # Filter turbines within the actual polygon
            filtered_turbines = []
            for turbine in turbines:
                point = (turbine['ylat'], turbine['xlong'])
                if self.point_in_polygon(point, self.polygon_points):
                    filtered_turbines.append(turbine)
                    logger.info(f"Found turbine: ID={turbine.get('case_id')}, "
                              f"Location=({turbine['ylat']}, {turbine['xlong']}), "
                              f"Height={turbine.get('t_ttlh')}m")

            logger.info(f"Found {len(filtered_turbines)} turbines within polygon")

            # Calculate detailed clearances using unified calculator
            try:
                logger.info("Calculating detailed clearances with unified calculator...")
                clearance_results = self._calculate_unified_clearances(filtered_turbines)
                self.last_clearance_results = clearance_results
                logger.info(f"Calculated clearances for {len(clearance_results)} turbines")
            except Exception as e:
                logger.error(f"Error calculating unified clearances: {e}", exc_info=True)
                clearance_results = []

            # Save turbines to tower_parameters.json
            try:
                self.save_turbines_to_json(filtered_turbines)
            except Exception as e:
                logger.error(f"Error saving turbines to JSON: {e}", exc_info=True)
                if self.root:
                    messagebox.showerror("Error", f"Failed to save turbines to JSON: {str(e)}")

            # Store turbines for label refresh
            self.last_turbines = filtered_turbines

            # Clear any existing turbine markers
            self.clear_turbine_markers()

            # Add visualization for each turbine
            logger.info(f"Adding visualization for {len(filtered_turbines)} turbines")
            for turbine in filtered_turbines:
                polygon, marker = self._add_turbine_visualization(turbine)

            # Check if labels should be visible
            if self.show_turbine_labels.get():
                logger.info("Labels are enabled, ensuring all markers are visible")
                self.toggle_turbine_labels()  # This will recreate any missing markers

            # Update elevation profile with turbines
            if self.elevation_profile:
                logger.info(f"Setting {len(filtered_turbines)} turbines in elevation profile")
                self.elevation_profile.set_turbines(filtered_turbines)
                logger.info("Turbines set in elevation profile")

                # Force a refresh of the profile with turbines
                logger.info("Forcing profile refresh with turbines")
                self.elevation_profile.refresh_with_turbines()
                logger.info("Profile refresh complete")

            # After finding turbines, update obstruction info with unified clearances
            if len(self.polygon_points) >= 2 and obstruction_text:
                path_start = self.polygon_points[0]
                path_end = self.polygon_points[-1]
                self._update_obstruction_info_unified(clearance_results, obstruction_text)

            if self.root:
                messagebox.showinfo("Search Complete",
                                  f"Found {len(filtered_turbines)} wind turbines within the search area.")

            return filtered_turbines

        except Exception as e:
            logger.error(f"Error fetching turbine data: {e}", exc_info=True)
            if self.root:
                messagebox.showerror("Error", f"Failed to find turbines: {str(e)}")
            return []

    def _calculate_unified_clearances(self, turbines):
        """Calculate clearances using the unified clearance calculator"""
        try:
            # Create path data from tower parameters
            path_data = create_path_from_tower_params()
            
            # Convert turbine data to unified format
            turbine_objects = []
            for turbine in turbines:
                try:
                    turbine_obj = create_turbine_from_dict(turbine)
                    turbine_objects.append(turbine_obj)
                except Exception as e:
                    logger.warning(f"Error converting turbine {turbine.get('case_id', 'Unknown')}: {e}")
                    continue
            
            # Get elevation data if available
            elevation_data = None
            elevation_distances = None
            if self.elevation_profile and hasattr(self.elevation_profile, 'elevation_data'):
                elevation_data = self.elevation_profile.elevation_data
                if hasattr(self.elevation_profile, 'distances'):
                    elevation_distances = self.elevation_profile.distances
            
            # Calculate clearances
            results = self.clearance_calculator.calculate_turbine_clearances(
                turbine_objects, path_data, elevation_data, elevation_distances
            )
            
            logger.info(f"Unified calculator processed {len(results)} turbines successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error in unified clearance calculation: {e}", exc_info=True)
            return []

    def _update_obstruction_info_unified(self, clearance_results, obstruction_text):
        """Update obstruction information using unified clearance results"""
        try:
            if not obstruction_text or not clearance_results:
                logger.warning("No obstruction_text widget or clearance results provided")
                return

            # Find closest turbine using unified results
            closest_result = None
            min_distance = float('inf')

            for result in clearance_results:
                if result.distance_to_path_ft < min_distance:
                    min_distance = result.distance_to_path_ft
                    closest_result = result

            # Update obstruction text
            obstruction_text.config(state="normal")
            obstruction_text.delete("1.0", tk.END)

            if closest_result:
                # Format distance values
                distance_ft = closest_result.distance_to_path_ft
                distance_m = closest_result.distance_to_path_m
                distance_miles = distance_ft / 5280

                # Create comprehensive obstruction info using unified results
                info_text = f"TURBINE OBSTRUCTION ANALYSIS (Unified Calculator)\n"
                info_text += f"="*60 + "\n\n"
                
                info_text += f"Closest Turbine: {closest_result.turbine_id}\n"
                info_text += f"Distance: {distance_ft:.1f} ft ({distance_m:.1f} m / {distance_miles:.2f} miles) from path\n"
                info_text += f"Distance along path: {closest_result.distance_along_path_ft:.1f} ft\n"
                info_text += f"Path side: {'Right' if closest_result.path_side > 0 else 'Left'}\n\n"
                
                info_text += f"HEIGHT ANALYSIS:\n"
                info_text += f"Ground elevation: {closest_result.ground_elevation_ft:.1f} ft\n"
                info_text += f"Turbine center height: {closest_result.turbine_center_height_ft:.1f} ft\n"
                info_text += f"Path height (straight): {closest_result.path_height_straight_ft:.1f} ft\n"
                info_text += f"Path height (curved): {closest_result.path_height_curved_ft:.1f} ft\n"
                info_text += f"Earth curvature bulge: {closest_result.earth_curvature_bulge_ft:.1f} ft\n\n"
                
                info_text += f"CLEARANCE ANALYSIS:\n"
                info_text += f"Fresnel radius: {closest_result.fresnel_radius_ft:.1f} ft\n"
                info_text += f"Clearance (straight): {closest_result.clearance_straight_ft:.1f} ft\n"
                info_text += f"Clearance (with earth curve): {closest_result.clearance_curved_ft:.1f} ft\n"
                info_text += f"Clearance (with Fresnel): {closest_result.clearance_fresnel_ft:.1f} ft\n\n"
                
                info_text += f"3D CLEARANCES:\n"
                info_text += f"3D straight: {closest_result.clearance_3d_straight_ft:.1f} ft\n"
                info_text += f"3D curved: {closest_result.clearance_3d_curved_ft:.1f} ft\n"
                info_text += f"3D Fresnel: {closest_result.clearance_3d_fresnel_ft:.1f} ft\n\n"
                
                info_text += f"STATUS:\n"
                info_text += f"LOS clearance: {'✅ Clear' if closest_result.has_los_clearance else '❌ Obstruction'}\n"
                info_text += f"Earth clearance: {'✅ Clear' if closest_result.has_earth_clearance else '❌ Obstruction'}\n"
                info_text += f"Fresnel clearance: {'✅ Clear' if closest_result.has_fresnel_clearance else '❌ Obstruction'}\n\n"
                
                # Summary of all turbines
                info_text += f"SUMMARY ({len(clearance_results)} turbines analyzed):\n"
                clear_count = sum(1 for r in clearance_results if r.has_fresnel_clearance)
                obstruction_count = len(clearance_results) - clear_count
                info_text += f"Clear of Fresnel zone: {clear_count}\n"
                info_text += f"Potential obstructions: {obstruction_count}\n"
                
                if obstruction_count > 0:
                    info_text += f"\nPOTENTIAL OBSTRUCTIONS:\n"
                    for result in clearance_results:
                        if not result.has_fresnel_clearance:
                            info_text += f"• {result.turbine_id}: {result.clearance_fresnel_ft:.1f} ft clearance\n"

                obstruction_text.insert(tk.END, info_text)
                
                logger.info(f"Updated obstruction info with unified results: {closest_result.turbine_id} "
                          f"at {distance_ft:.1f}ft, Fresnel clearance: {closest_result.clearance_fresnel_ft:.1f}ft")
            else:
                obstruction_text.insert(tk.END, "No turbines found for analysis.")

            obstruction_text.config(state="disabled")

        except Exception as e:
            logger.error(f"Error updating obstruction info with unified results: {e}", exc_info=True)

    def save_turbines_to_json(self, turbines):
        """Save turbine data to the tower_parameters.json file"""
        logger.info("Saving turbines to tower_parameters.json")
        # Read existing data
        with open('tower_parameters.json', 'r') as f:
            data = json.load(f)

        # Convert turbine data to serializable format
        serializable_turbines = []
        for turbine in turbines:
            turbine_data = {
                'id': turbine.get('case_id'),
                'latitude': turbine['ylat'],
                'longitude': turbine['xlong'],
                'total_height_m': turbine.get('t_ttlh'),  # Total height (tip height)
                'hub_height_m': turbine.get('t_hh'),      # Hub height
                'rotor_diameter_m': turbine.get('t_rd'),
                'rotor_swept_area_m2': turbine.get('t_rsa'),
                'project_name': turbine.get('p_name'),
                'capacity_kw': turbine.get('t_cap'),
                'manufacturer': turbine.get('t_manu'),
                'model': turbine.get('t_model'),
                'year_online': turbine.get('p_year'),
                'state': turbine.get('t_state'),
                'county': turbine.get('t_county'),
                'location_confidence': turbine.get('t_conf_loc'),
                'attribute_confidence': turbine.get('t_conf_attr')
            }
            serializable_turbines.append(turbine_data)

        # Add or update turbines in data
        data['turbines'] = serializable_turbines

        # Write back to file with proper indentation
        with open('tower_parameters.json', 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Successfully saved {len(serializable_turbines)} turbines to tower_parameters.json")

    def _show_turbine_details_popup(self, turbine):
        """Show a popup with detailed turbine information"""
        try:
            if not turbine:
                return

            # Get turbine details with fallbacks for missing data
            turbine_id = turbine.get('case_id', turbine.get('id', 'Unknown'))
            project_name = turbine.get('p_name', turbine.get('project_name', 'Unknown'))
            total_height = turbine.get('t_ttlh', turbine.get('total_height_m', 'Unknown'))
            hub_height = turbine.get('t_hh', turbine.get('hub_height_m', 'Unknown'))
            rotor_diameter = turbine.get('t_rd', turbine.get('rotor_diameter_m', 'Unknown'))
            capacity = turbine.get('t_cap', turbine.get('capacity_kw', 'Unknown'))
            manufacturer = turbine.get('t_manu', turbine.get('manufacturer', 'Unknown'))
            model = turbine.get('t_model', turbine.get('model', 'Unknown'))
            year = turbine.get('p_year', turbine.get('year_online', 'Unknown'))
            state = turbine.get('t_state', turbine.get('state', 'Unknown'))
            county = turbine.get('t_county', turbine.get('county', 'Unknown'))
            lat = turbine.get('ylat', turbine.get('latitude', 'Unknown'))
            lon = turbine.get('xlong', turbine.get('longitude', 'Unknown'))

            # Format the details for display
            details = f"""Turbine ID: {turbine_id}

Project: {project_name}
Year Online: {year}

Total Height: {total_height} m
Hub Height: {hub_height} m
Rotor Diameter: {rotor_diameter} m

Capacity: {capacity} kW
Manufacturer: {manufacturer}
Model: {model}

Location: {county}, {state}
Coordinates: {lat:.6f}°, {lon:.6f}°"""

            # Show the details in a messagebox
            messagebox.showinfo(f"Wind Turbine {turbine_id}", details)

        except Exception as e:
            logger.error(f"Error showing turbine details: {e}", exc_info=True)

    def _add_turbine_visualization(self, turbine):
        """Add visualization for a single turbine"""
        try:
            if not self.map_widget:
                logger.warning("No map widget available for turbine visualization")
                return None, None

            # Get rotor diameter with fallback value
            rotor_diameter = turbine.get('t_rd', turbine.get('rotor_diameter_m'))
            if rotor_diameter is None or rotor_diameter == 0:
                rotor_diameter = 100  # Default to 100m if no valid diameter

            # Create blade sweep circle
            radius_meters = rotor_diameter / 2
            lat_correction = math.cos(math.radians(turbine['ylat'] if 'ylat' in turbine else turbine['latitude']))
            radius_lat = radius_meters / 111111
            radius_lon = radius_meters / (111111 * lat_correction)

            # Get turbine coordinates
            turbine_lat = turbine.get('ylat', turbine.get('latitude'))
            turbine_lon = turbine.get('xlong', turbine.get('longitude'))

            # Generate blade sweep circle points
            blade_circle_points = []
            for angle in range(0, 360, 10):
                rad = math.radians(angle)
                lat = turbine_lat + (radius_lat * math.sin(rad))
                lon = turbine_lon + (radius_lon * math.cos(rad))
                blade_circle_points.append((lat, lon))

            # Draw blade sweep circle with transparent fill and purple outline
            turbine_id = turbine.get('case_id', turbine.get('id', 'unknown'))
            polygon = self.map_widget.set_polygon(
                blade_circle_points,
                outline_color="purple",
                fill_color=None,  # No fill to avoid opacity issues
                border_width=2
            )

            # Store the polygon for later reference
            if not hasattr(self, 'turbine_polygons'):
                self.turbine_polygons = []
            self.turbine_polygons.append(polygon)

            # Create a center dot marker for the turbine
            center_marker = None
            try:
                # Create a function to show turbine details when clicked
                def show_turbine_details(turbine=turbine):
                    self._show_turbine_details_popup(turbine)

                # Create the center dot marker
                logger.info(f"Creating center dot marker for turbine {turbine_id} at {turbine_lat}, {turbine_lon}")
                center_marker = self.map_widget.set_marker(
                    turbine_lat,
                    turbine_lon,
                    text="",  # No text on the marker itself
                    marker_color_outside="black",
                    marker_color_circle="white",
                    command=show_turbine_details,
                    marker_width=8  # Small dot
                )

                # Store the center marker
                if not hasattr(self, 'turbine_center_markers'):
                    self.turbine_center_markers = []
                self.turbine_center_markers.append(center_marker)
            except Exception as marker_error:
                logger.warning(f"Failed to create center dot marker: {marker_error}")

            # Create a label marker if labels are enabled
            marker = None
            if self.show_turbine_labels.get():
                try:
                    from PIL import Image, ImageTk

                    # Load the custom icon
                    icon_path = "assets/images/purp_turbine.png"
                    custom_icon = Image.open(icon_path)

                    # Resize to desired dimensions
                    custom_icon = custom_icon.resize((30, 30))  # Adjust size as needed
                    custom_icon_tk = ImageTk.PhotoImage(custom_icon)

                    # Store the icon to prevent garbage collection
                    if not hasattr(self, 'icon_references'):
                        self.icon_references = []
                    self.icon_references.append(custom_icon_tk)

                    # Create a marker for the turbine label using custom icon
                    logger.info(f"Creating label marker for turbine {turbine_id} at {turbine_lat}, {turbine_lon} with custom icon")
                    marker = self.map_widget.set_marker(
                        turbine_lat,
                        turbine_lon,
                        text=f"T{turbine_id}",
                        text_color="black",
                        font=("Arial", 12, "bold"),
                        icon=custom_icon_tk
                    )
                except Exception as icon_error:
                    # Fallback to default marker if custom icon fails
                    logger.warning(f"Failed to load custom icon, using default marker: {icon_error}")
                    marker = self.map_widget.set_marker(
                        turbine_lat,
                        turbine_lon,
                        text=f"T{turbine_id}",
                        text_color="black",
                        marker_color_outside="red",
                        marker_color_circle="yellow",
                        font=("Arial", 12, "bold")
                    )
            else:
                logger.info(f"Labels not enabled, not creating label marker for turbine {turbine_id}")

            # Store the marker for later reference if it exists
            if marker:
                self.turbine_markers.append(marker)

            return polygon, marker

        except Exception as e:
            logger.error(f"Error adding turbine visualization: {e}", exc_info=True)
            return None, None

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

    def find_state_turbines(self, state_name=None, site_a=None, site_b=None, obstruction_text=None):
        """Search for all wind turbines in the state containing the LOS path"""
        try:
            if not self.polygon_points and not state_name:
                if self.root:
                    messagebox.showwarning("No Search Area",
                                         "Please load a project first to define the search area.")
                return []

            # If state name not provided, determine it from polygon points
            if not state_name:
                # Get center point of LOS path
                lats = [point[0] for point in self.polygon_points]
                lons = [point[1] for point in self.polygon_points]
                center_lat = sum(lats) / len(lats)
                center_lon = sum(lons) / len(lons)

                logger.info(f"Finding state for coordinates: {center_lat:.6f}, {center_lon:.6f}")

                # State boundary definitions
                state_bounds = {
                    'WY': {'min_lat': 41.00, 'max_lat': 45.01, 'min_lon': -111.06, 'max_lon': -104.05},
                    'CO': {'min_lat': 36.99, 'max_lat': 41.00, 'min_lon': -109.05, 'max_lon': -102.04},
                    'NE': {'min_lat': 40.00, 'max_lat': 43.00, 'min_lon': -104.05, 'max_lon': -95.31},
                    'SD': {'min_lat': 42.48, 'max_lat': 45.94, 'min_lon': -104.06, 'max_lon': -96.44},
                    'MT': {'min_lat': 44.36, 'max_lat': 49.00, 'min_lon': -116.05, 'max_lon': -104.04},
                    # Add more states as needed
                }

                # Find which state contains the center point
                state_boundary = None
                for state, bounds in state_bounds.items():
                    if (bounds['min_lat'] <= center_lat <= bounds['max_lat'] and
                        bounds['min_lon'] <= center_lon <= bounds['max_lon']):
                        state_name = state
                        state_boundary = bounds
                        break
            else:
                # Use state name to get boundary
                state_bounds = {
                    'WY': {'min_lat': 41.00, 'max_lat': 45.01, 'min_lon': -111.06, 'max_lon': -104.05},
                    'CO': {'min_lat': 36.99, 'max_lat': 41.00, 'min_lon': -109.05, 'max_lon': -102.04},
                    'NE': {'min_lat': 40.00, 'max_lat': 43.00, 'min_lon': -104.05, 'max_lon': -95.31},
                    'SD': {'min_lat': 42.48, 'max_lat': 45.94, 'min_lon': -104.06, 'max_lon': -96.44},
                    'MT': {'min_lat': 44.36, 'max_lat': 49.00, 'min_lon': -116.05, 'max_lon': -104.04},
                    # Add more states as needed
                }
                state_boundary = state_bounds.get(state_name)

            if not state_name or not state_boundary:
                if self.root:
                    messagebox.showwarning("State Not Found",
                                         "Could not determine state for the given coordinates.")
                return []

            # Query turbine data for the state
            logger.info(f"Querying turbine data for state: {state_name}")

            # Primary USWTDB API endpoint (updated 2025)
            primary_url = "https://energy.usgs.gov/api/uswtdb/v1/turbines"
            # Backup endpoint (updated 2025)
            backup_url = "https://energy.usgs.gov/arcgis/rest/services/Hosted/uswtdbDyn/FeatureServer/0/query"

            # Query parameters for entire state
            params = {
                "select": "*",
                "and": (f"(ylat.gte.{state_boundary['min_lat']},"
                       f"ylat.lte.{state_boundary['max_lat']},"
                       f"xlong.gte.{state_boundary['min_lon']},"
                       f"xlong.lte.{state_boundary['max_lon']})")
            }

            # Reduced timeout to 5 seconds
            timeout = 5
            turbines = None

            # Try primary endpoint first
            try:
                logger.info(f"Querying turbines for {state_name} from primary endpoint with {timeout}s timeout")
                response = requests.get(primary_url, params=params, timeout=timeout)
                response.raise_for_status()
                turbines = response.json()
                logger.info(f"Primary endpoint response status: {response.status_code}")
            except Exception as e:
                logger.warning(f"Primary endpoint failed: {e}, trying backup endpoint")

            # If primary endpoint failed, try the backup (ArcGIS REST API has different parameters)
            if turbines is None:
                try:
                    logger.info(f"Querying turbines for {state_name} from backup endpoint with {timeout}s timeout")
                    # ArcGIS REST API uses different parameters
                    arcgis_params = {
                        "where": f"t_state = '{state_name}'",
                        "outFields": "*",
                        "returnGeometry": "true",
                        "f": "json"
                    }
                    response = requests.get(backup_url, params=arcgis_params, timeout=timeout)
                    response.raise_for_status()
                    arcgis_response = response.json()

                    # Convert ArcGIS format to match the API format
                    if 'features' in arcgis_response:
                        turbines = [feature['attributes'] for feature in arcgis_response['features']]
                        logger.info(f"Backup endpoint response status: {response.status_code}, found {len(turbines)} turbines")
                except Exception as e:
                    logger.warning(f"Backup endpoint failed: {e}, trying GeoJSON file fallback")

            # If both online endpoints failed, try the GeoJSON file fallback
            if turbines is None:
                try:
                    logger.info("Trying GeoJSON file fallback")
                    # Try to load turbines from the GeoJSON file
                    turbines = self._load_turbines_from_geojson(state_name=state_name)

                    if turbines:
                        logger.info(f"GeoJSON file fallback successful, found {len(turbines)} turbines for {state_name}")
                    else:
                        # Show a message to the user
                        if obstruction_text:
                            obstruction_text.config(state="normal")
                            obstruction_text.delete("1.0", tk.END)
                            obstruction_text.insert(tk.END, f"Turbine data service is currently unavailable.\n\nPlease check your internet connection or try again later.")
                            obstruction_text.config(state="disabled")
                        logger.warning("No turbines found in GeoJSON file and not attempting to download")
                except Exception as e:
                    logger.error(f"All endpoints and GeoJSON fallback failed. Error: {str(e)}")
                    raise Exception("Failed to fetch turbine data. Please check your internet connection or try again later.")

            # If we still don't have turbines, raise an error
            if turbines is None:
                raise Exception("Failed to fetch turbine data from all endpoints")

            logger.info(f"Found {len(turbines)} turbines in {state_name}")

            # Clear existing turbine visualizations
            self.clear_turbines()

            # Store turbines for label refresh
            self.last_turbines = turbines

            # Add visualization for each turbine if map widget is available
            if self.map_widget:
                for turbine in turbines:
                    self._add_turbine_visualization(turbine)

                # Adjust map view to show entire state
                self.map_widget.set_position(
                    (state_boundary['min_lat'] + state_boundary['max_lat']) / 2,
                    (state_boundary['min_lon'] + state_boundary['max_lon']) / 2)
                self.map_widget.set_zoom(7)  # Adjust zoom level to show state

            if self.root:
                messagebox.showinfo("Search Complete",
                                  f"Found {len(turbines)} wind turbines in {state_name}.")

            # After finding turbines, update obstruction info
            if self.polygon_points and len(self.polygon_points) >= 2 and obstruction_text:
                path_start = self.polygon_points[0]
                path_end = self.polygon_points[-1]
                self._update_obstruction_info(turbines, path_start, path_end, obstruction_text)

            # Update elevation profile with found turbines
            if self.elevation_profile and turbines:
                logger.info(f"Updating elevation profile with {len(turbines)} turbines")
                self.elevation_profile.set_turbines(turbines)

                # Trigger profile update if we have site coordinates
                if site_a and site_b:
                    self.elevation_profile.update_profile(
                        (site_a.get('latitude'), site_a.get('longitude')),
                        (site_b.get('latitude'), site_b.get('longitude')),
                        site_a.get('elevation_ft', 0),
                        site_b.get('elevation_ft', 0),
                        site_a.get('site_id', 'Site A'),
                        site_b.get('site_id', 'Site B')
                    )

            return turbines

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching state turbines: {str(e)}", exc_info=True)
            if self.root:
                messagebox.showerror("Error", f"Failed to search state turbines: {str(e)}")
            return []

        except Exception as e:
            logger.error(f"Error in find_state_turbines: {e}", exc_info=True)
            if self.root:
                messagebox.showerror("Error", f"Failed to find turbines: {str(e)}")
            return []

    def clear_turbines(self):
        """Clear all turbine visualizations from the map"""
        try:
            logger.info("Clearing all turbine visualizations")

            # Clear turbine polygons
            if hasattr(self, 'turbine_polygons') and self.turbine_polygons:
                for polygon in self.turbine_polygons:
                    try:
                        if polygon:
                            polygon.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting turbine polygon: {e}")
                self.turbine_polygons = []

            # Clear center dot markers
            if hasattr(self, 'turbine_center_markers') and self.turbine_center_markers:
                for marker in self.turbine_center_markers:
                    try:
                        if marker:
                            marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting turbine center marker: {e}")
                self.turbine_center_markers = []

            # Clear label markers
            self.clear_turbine_markers()

            # Clear any remaining turbine items from the canvas
            if self.map_widget and hasattr(self.map_widget, 'canvas'):
                for item in self.map_widget.canvas.find_withtag("turbine"):
                    try:
                        self.map_widget.canvas.delete(item)
                    except Exception as e:
                        logger.debug(f"Error deleting canvas item: {e}")

            # Clear the last_turbines list
            self.last_turbines = []

            logger.info("All turbine visualizations cleared")

        except Exception as e:
            logger.error(f"Error clearing turbines: {e}", exc_info=True)

    def clear_turbine_markers(self):
        """Clear just the turbine markers (not polygons)"""
        # Clear turbine markers
        if hasattr(self, 'turbine_markers') and self.turbine_markers:
            for marker in self.turbine_markers:
                try:
                    if marker:
                        marker.delete()
                except Exception as e:
                    logger.debug(f"Error deleting turbine marker: {e}")
            self.turbine_markers = []

    def toggle_turbine_labels(self):
        """Toggle visibility of turbine labels"""
        try:
            # Get the new visibility state
            show_labels = self.show_turbine_labels.get()
            logger.info(f"Toggling turbine labels to {'visible' if show_labels else 'hidden'}")

            # If we don't have any turbines, there's nothing to toggle
            if not self.last_turbines:
                logger.info("No turbine data available")
                return

            # Log the number of turbines
            logger.info(f"We have {len(self.last_turbines)} turbines to label")

            # Clear existing markers first
            self.clear_turbine_markers()

            # If we're showing labels, create new markers
            if show_labels:
                logger.info("Creating new markers for all turbines")

                # Try to load the custom icon
                custom_icon_tk = None
                try:
                    from PIL import Image, ImageTk

                    # Load the custom icon
                    icon_path = "assets/images/purp_turbine.png"
                    custom_icon = Image.open(icon_path)

                    # Resize to desired dimensions (half the original size)
                    custom_icon = custom_icon.resize((30, 30))  # Adjust size as needed
                    custom_icon_tk = ImageTk.PhotoImage(custom_icon)

                    # Store the icon to prevent garbage collection
                    if not hasattr(self, 'icon_references'):
                        self.icon_references = []
                    self.icon_references.append(custom_icon_tk)

                    logger.info("Successfully loaded custom turbine icon")
                except Exception as icon_error:
                    logger.warning(f"Failed to load custom icon: {icon_error}")
                    custom_icon_tk = None

                # Create markers for all turbines
                for turbine in self.last_turbines:
                    turbine_id = turbine.get('case_id', 'unknown')

                    if custom_icon_tk and self.map_widget:
                        # Use custom icon if available
                        marker = self.map_widget.set_marker(
                            turbine['ylat'],
                            turbine['xlong'],
                            text=f"T{turbine_id}",
                            text_color="black",
                            font=("Arial", 12, "bold"),
                            icon=custom_icon_tk
                        )
                    elif self.map_widget:
                        # Fallback to default marker
                        marker = self.map_widget.set_marker(
                            turbine['ylat'],
                            turbine['xlong'],
                            text=f"T{turbine_id}",
                            text_color="black",
                            marker_color_outside="red",
                            marker_color_circle="yellow",
                            font=("Arial", 12, "bold")
                        )
                    else:
                        logger.warning("No map widget available for marker creation")
                        continue

                    self.turbine_markers.append(marker)

                logger.info(f"Created {len(self.turbine_markers)} markers")
            else:
                logger.info("Labels are hidden, no markers created")

            # Force a UI update
            if self.map_widget:
                self.map_widget.update()

            if self.root:
                self.root.update()

        except Exception as e:
            logger.error(f"Error toggling turbine labels: {e}", exc_info=True)

    def _calculate_distance_to_path(self, point, path_start, path_end):
        """Calculate the shortest distance from a point to a line segment (path)"""
        try:
            # Convert coordinates to meters for accurate distance calculation
            def haversine_distance(lat1, lon1, lat2, lon2):
                R = 6371000  # Earth's radius in meters
                dlat = math.radians(lat2 - lat1)
                dlon = math.radians(lon2 - lon1)
                a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                return R * c

            # Extract coordinates
            px, py = point
            x1, y1 = path_start
            x2, y2 = path_end

            # Calculate distances
            line_length = haversine_distance(x1, y1, x2, y2)
            if line_length == 0:
                return haversine_distance(px, py, x1, y1)

            # Calculate projection
            t = ((px - x1) * (x2 - x1) + (py - y1) * (y2 - y1)) / (line_length ** 2)
            t = max(0, min(1, t))

            # Find nearest point on line
            nx = x1 + t * (x2 - x1)
            ny = y1 + t * (y2 - y1)

            # Calculate distance to nearest point
            distance = haversine_distance(px, py, nx, ny)
            return distance

        except Exception as e:
            logger.error(f"Error calculating distance to path: {e}")
            return float('inf')

    def _update_obstruction_info(self, turbines, path_start, path_end, obstruction_text):
        """Update the obstruction information display"""
        try:
            if not obstruction_text:
                logger.warning("No obstruction_text widget provided")
                return

            # Find closest turbine to path
            closest_turbine = None
            min_distance = float('inf')

            for turbine in turbines:
                try:
                    # Make sure we have valid coordinates
                    if 'ylat' not in turbine or 'xlong' not in turbine:
                        logger.warning(f"Turbine missing coordinates: {turbine.get('case_id', 'Unknown')}")
                        continue

                    # Calculate distance to path
                    distance = self._calculate_distance_to_path(
                        (turbine['ylat'], turbine['xlong']),
                        path_start,
                        path_end
                    )

                    logger.debug(f"Turbine {turbine.get('case_id', 'Unknown')} distance: {distance:.2f}m")

                    if distance < min_distance:
                        min_distance = distance
                        closest_turbine = turbine
                        logger.info(f"New closest turbine: ID={turbine.get('case_id', 'Unknown')}, distance={distance:.2f}m")
                except Exception as e:
                    logger.error(f"Error calculating distance for turbine {turbine.get('case_id', 'Unknown')}: {e}")
                    continue

            # Update obstruction text
            obstruction_text.config(state="normal")
            obstruction_text.delete("1.0", tk.END)

            if closest_turbine:
                # Convert distance to miles for display
                distance_miles = min_distance * 0.000621371  # Convert meters to miles

                info_text = (
                    f"Closest Obstruction:\n"
                    f"Wind Turbine (ID: {closest_turbine.get('case_id', 'Unknown')})\n"
                    f"Distance: {distance_miles:.2f} miles from path\n"
                    f"Height: {closest_turbine.get('t_ttlh', 'Unknown')}m\n"
                    f"Project: {closest_turbine.get('p_name', 'Unknown')}"
                )
            else:
                info_text = "No obstructions found near the path"

            obstruction_text.insert("1.0", info_text)
            obstruction_text.config(state="disabled")

        except Exception as e:
            logger.error(f"Error updating obstruction info: {e}")

    def add_turbine_visualization(self, turbine):
        """Add visualization for a single turbine"""
        try:
            if not self.map_widget:
                logger.warning("No map widget available for turbine visualization")
                return None, None

            # Get rotor diameter with fallback value
            rotor_diameter = turbine.get('t_rd')
            if rotor_diameter is None or rotor_diameter == 0:
                rotor_diameter = 100  # Default to 100m if no valid diameter

            # Create blade sweep circle
            radius_meters = rotor_diameter / 2
            lat_correction = math.cos(math.radians(turbine['ylat']))
            radius_lat = radius_meters / 111111
            radius_lon = radius_meters / (111111 * lat_correction)

            # Generate blade sweep circle points
            blade_circle_points = []
            for angle in range(0, 360, 10):
                rad = math.radians(angle)
                lat = turbine['ylat'] + (radius_lat * math.sin(rad))
                lon = turbine['xlong'] + (radius_lon * math.cos(rad))
                blade_circle_points.append((lat, lon))

            # Draw blade sweep circle as a filled purple circle
            turbine_id = turbine.get('case_id', 'unknown')
            polygon = self.map_widget.set_polygon(
                blade_circle_points,
                outline_color="purple",
                fill_color="purple",  # Fill with purple color
                border_width=1
            )

            # Store the polygon for later reference
            if not hasattr(self, 'turbine_polygons'):
                self.turbine_polygons = []
            self.turbine_polygons.append(polygon)

            # Create detailed tooltip text
            tooltip_text = (
                f"Turbine ID: {turbine.get('case_id', 'Unknown')}\n"
                f"Project: {turbine.get('p_name', 'Unknown')}\n"
                f"Height: {turbine.get('t_ttlh', 'Unknown')}m\n"
                f"Rotor Diameter: {rotor_diameter}m\n"
                f"Capacity: {turbine.get('t_cap', 'Unknown')}kW\n"
                f"Location: {turbine['ylat']:.6f}°N, {turbine['xlong']:.6f}°W"
            )

            # Add tooltip to the circle by adding a function to the polygon
            self.map_widget.add_right_click_menu_command(
                f"turbine_sweep_{turbine_id}",
                "Show Turbine Info",
                lambda: messagebox.showinfo(f"Turbine {turbine_id}", tooltip_text)
            )

            # Load and resize custom icon using PIL
            try:
                from PIL import Image, ImageTk

                # Load the custom icon
                icon_path = "assets/images/purp_turbine.png"
                custom_icon = Image.open(icon_path)

                # Resize to desired dimensions (half the original size)
                custom_icon = custom_icon.resize((30, 30))  # Adjust size as needed
                custom_icon_tk = ImageTk.PhotoImage(custom_icon)

                # Store the icon to prevent garbage collection
                if not hasattr(self, 'icon_references'):
                    self.icon_references = []
                self.icon_references.append(custom_icon_tk)

                # Create a marker for the turbine label using custom icon
                logger.info(f"Creating marker for turbine {turbine_id} at {turbine['ylat']}, {turbine['xlong']} with custom icon")
                marker = self.map_widget.set_marker(
                    turbine['ylat'],
                    turbine['xlong'],
                    text=f"T{turbine_id}",
                    text_color="black",
                    font=("Arial", 12, "bold"),
                    icon=custom_icon_tk
                )
            except Exception as icon_error:
                # Fallback to default marker if custom icon fails
                logger.warning(f"Failed to load custom icon, using default marker: {icon_error}")
                marker = self.map_widget.set_marker(
                    turbine['ylat'],
                    turbine['xlong'],
                    text=f"T{turbine_id}",
                    text_color="black",
                    marker_color_outside="red",
                    marker_color_circle="yellow",
                    font=("Arial", 12, "bold")
                )

            # Store the marker for later reference
            if not hasattr(self, 'turbine_markers'):
                self.turbine_markers = []
            self.turbine_markers.append(marker)

            # Hide the marker if labels are not enabled
            if not self.show_turbine_labels.get():
                logger.info(f"Labels not enabled, hiding marker for turbine {turbine_id}")
                marker.delete()
            else:
                logger.info(f"Labels enabled, showing marker for turbine {turbine_id}")

            return polygon, marker

        except Exception as e:
            logger.error(f"Error adding turbine visualization: {e}", exc_info=True)
            return None, None

    def add_turbine_visualizations(self, turbines):
        """Add visualization for all turbines in the list"""
        try:
            if not turbines:
                logger.warning("No turbines to visualize")
                return []

            # Store turbines for label refresh
            self.last_turbines = turbines

            # Clear any existing turbine markers
            self.clear_turbine_markers()

            # Add visualization for each turbine
            logger.info(f"Adding visualization for {len(turbines)} turbines")
            results = []
            for turbine in turbines:
                try:
                    polygon, marker = self.add_turbine_visualization(turbine)
                    if polygon:
                        results.append((polygon, marker, turbine))
                except Exception as e:
                    logger.error(f"Error adding visualization for turbine {turbine.get('case_id', 'unknown')}: {e}")

            # Check if labels should be visible
            if self.show_turbine_labels.get():
                logger.info("Labels are enabled, ensuring all markers are visible")
                self.toggle_turbine_labels()  # This will recreate any missing markers

            return results
        except Exception as e:
            logger.error(f"Error adding turbine visualizations: {e}", exc_info=True)
            return []