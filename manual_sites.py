import tkinter as tk
from tkinter import ttk, messagebox
import logging
import re
import requests
import os
import json
from dotenv import load_dotenv

# Configure logger
logger = logging.getLogger(__name__)

# Load environment variables for API access
load_dotenv()

def fetch_elevation_data(lat, lon):
    """
    Fetch elevation data for a given coordinate using Google Maps Elevation API.
    
    Args:
        lat (float): Latitude in decimal degrees
        lon (float): Longitude in decimal degrees
        
    Returns:
        float: Elevation in feet, or None if fetching failed
    """
    try:
        api_key = os.getenv("GOOGLE_MAPS_API_KEY")
        if not api_key:
            logger.error("Google Maps API key not found in environment variables")
            return None
            
        url = f"https://maps.googleapis.com/maps/api/elevation/json?locations={lat},{lon}&key={api_key}"
        
        response = requests.get(url)
        if response.status_code != 200:
            logger.error(f"Error fetching elevation data: {response.status_code}")
            return None
            
        data = response.json()
        if data.get('status') != 'OK':
            logger.error(f"API returned error: {data.get('status')}")
            return None
            
        # Extract elevation in meters and convert to feet
        elevation_meters = data['results'][0]['elevation']
        elevation_feet = elevation_meters * 3.28084  # Convert meters to feet
        
        logger.info(f"Fetched elevation for {lat}, {lon}: {elevation_feet:.2f} feet")
        return elevation_feet
        
    except Exception as e:
        logger.error(f"Error in fetch_elevation_data: {str(e)}")
        return None

class ManualSitesDialog(tk.Toplevel):
    """Dialog for manual entry of site coordinates"""
    def __init__(self, parent, callback, convert_dms_to_decimal, calculate_distance):
        super().__init__(parent)
        self.title("Manual Site Entry")
        self.resizable(False, False)
        self.callback = callback
        self.convert_dms_to_decimal = convert_dms_to_decimal
        self.calculate_distance = calculate_distance
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Center dialog
        self.geometry("550x520")  # Increased height to accommodate the new field
        
        # Create tabbed interface for Site A and Site B
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Site A frame
        self.site_a_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.site_a_frame, text="Donor Site (A)")
        
        # Site B frame
        self.site_b_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.site_b_frame, text="Recipient Site (B)")
        
        # Create input fields for Site A
        self.site_a_fields = self.create_site_fields(self.site_a_frame, "A")
        
        # Create input fields for Site B
        self.site_b_fields = self.create_site_fields(self.site_b_frame, "B")
        
        # Create general parameters frame
        general_frame = ttk.LabelFrame(self, text="General Parameters")
        general_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Frequency field
        ttk.Label(general_frame, text="Frequency (GHz):").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.frequency_ghz = ttk.Entry(general_frame, width=30)
        self.frequency_ghz.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        self.frequency_ghz.insert(0, "11.0")  # Default frequency value
        
        # Status bar for feedback
        self.status_var = tk.StringVar(value="")
        self.status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status_bar.pack(fill="x", padx=10, pady=(5, 0))
        
        # Button frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        # Add buttons
        ttk.Button(button_frame, text="Cancel", command=self.destroy).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Submit", command=self.submit).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Fetch Elevations", command=self.fetch_all_elevations).pack(side="right", padx=5)
    
    def create_site_fields(self, parent, site_label):
        """Create input fields for a site"""
        fields = {}
        
        # Create label frame
        site_frame = ttk.LabelFrame(parent, text=f"Site {site_label} Details")
        site_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Site ID
        ttk.Label(site_frame, text="Site ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        fields["site_id"] = ttk.Entry(site_frame, width=30)
        fields["site_id"].grid(row=0, column=1, sticky="w", padx=5, pady=5)
        if site_label == "A":
            fields["site_id"].insert(0, "Donor Site")
        else:
            fields["site_id"].insert(0, "Recipient Site")
        
        # Coordinate format selection
        ttk.Label(site_frame, text="Coordinate Format:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        fields["coord_format"] = ttk.Combobox(site_frame, width=28, values=["DMS (DD-MM-SS.S N/S)", "Decimal (±DD.DDDD)"], state="readonly")
        fields["coord_format"].grid(row=1, column=1, sticky="w", padx=5, pady=5)
        fields["coord_format"].current(0)  # Default to DMS format
        
        # Latitude
        ttk.Label(site_frame, text="Latitude:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        fields["latitude"] = ttk.Entry(site_frame, width=30)
        fields["latitude"].grid(row=2, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(site_frame, text="e.g. 41-24-28.2 N or 41.40783").grid(row=2, column=2, sticky="w", padx=5, pady=5)
        
        # Longitude
        ttk.Label(site_frame, text="Longitude:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        fields["longitude"] = ttk.Entry(site_frame, width=30)
        fields["longitude"].grid(row=3, column=1, sticky="w", padx=5, pady=5)
        ttk.Label(site_frame, text="e.g. 82-43-58.7 W or -82.73297").grid(row=3, column=2, sticky="w", padx=5, pady=5)
        
        # Elevation
        ttk.Label(site_frame, text="Elevation (ft):").grid(row=4, column=0, sticky="w", padx=5, pady=5)
        fields["elevation_ft"] = ttk.Entry(site_frame, width=30)
        fields["elevation_ft"].grid(row=4, column=1, sticky="w", padx=5, pady=5)
        fields["elevation_ft"].insert(0, "0")
        
        # Fetch elevation button for this site
        fetch_elev_btn = ttk.Button(
            site_frame, 
            text="Fetch Elevation",
            command=lambda: self.fetch_site_elevation(site_label)
        )
        fetch_elev_btn.grid(row=4, column=2, sticky="w", padx=5, pady=5)
        
        # Antenna CL
        ttk.Label(site_frame, text="Antenna CL (ft):").grid(row=5, column=0, sticky="w", padx=5, pady=5)
        fields["antenna_cl_ft"] = ttk.Entry(site_frame, width=30)
        fields["antenna_cl_ft"].grid(row=5, column=1, sticky="w", padx=5, pady=5)
        fields["antenna_cl_ft"].insert(0, "0")
        
        # Azimuth
        ttk.Label(site_frame, text="Azimuth (deg):").grid(row=6, column=0, sticky="w", padx=5, pady=5)
        fields["azimuth_deg"] = ttk.Entry(site_frame, width=30)
        fields["azimuth_deg"].grid(row=6, column=1, sticky="w", padx=5, pady=5)
        fields["azimuth_deg"].insert(0, "0")
        
        # Add validation to lat/long fields to auto-update elevation
        fields["latitude"].bind("<FocusOut>", lambda e: self.coordinate_changed(site_label))
        fields["longitude"].bind("<FocusOut>", lambda e: self.coordinate_changed(site_label))
        fields["coord_format"].bind("<<ComboboxSelected>>", lambda e: self.coordinate_format_changed(site_label))
        
        return fields
    
    def coordinate_format_changed(self, site_label):
        """Handle coordinate format change"""
        fields = self.site_a_fields if site_label == "A" else self.site_b_fields
        format_type = fields["coord_format"].get()
        
        # Update help text based on format
        if format_type == "DMS (DD-MM-SS.S N/S)":
            # Convert decimal to DMS if needed
            try:
                lat = fields["latitude"].get().strip()
                lon = fields["longitude"].get().strip()
                
                # Check if current values are likely decimal format
                if lat and lon and '-' not in lat and 'N' not in lat and 'S' not in lat:
                    # Try to convert
                    try:
                        lat_val = float(lat)
                        lon_val = float(lon)
                        
                        # Convert to DMS
                        lat_dms = self.format_dms_from_decimal(lat_val, True)
                        lon_dms = self.format_dms_from_decimal(lon_val, False)
                        
                        # Update fields
                        fields["latitude"].delete(0, tk.END)
                        fields["latitude"].insert(0, lat_dms)
                        
                        fields["longitude"].delete(0, tk.END)
                        fields["longitude"].insert(0, lon_dms)
                    except ValueError:
                        # Not numeric, don't attempt conversion
                        pass
            except Exception as e:
                logger.error(f"Error converting format: {e}")
        else:
            # Convert DMS to decimal if needed
            try:
                lat = fields["latitude"].get().strip()
                lon = fields["longitude"].get().strip()
                
                # Check if current values are likely DMS format
                if lat and lon and ('-' in lat or 'N' in lat or 'S' in lat):
                    # Try to convert
                    try:
                        lat_val, lon_val = self.convert_dms_to_decimal(lat, lon)
                        
                        # Update fields
                        fields["latitude"].delete(0, tk.END)
                        fields["latitude"].insert(0, str(lat_val))
                        
                        fields["longitude"].delete(0, tk.END)
                        fields["longitude"].insert(0, str(lon_val))
                    except Exception:
                        # Not DMS format, don't attempt conversion
                        pass
            except Exception as e:
                logger.error(f"Error converting format: {e}")
    
    def coordinate_changed(self, site_label):
        """Handle coordinate change event to auto-update elevation if needed"""
        fields = self.site_a_fields if site_label == "A" else self.site_b_fields
        
        # Check if elevation is empty or zero
        elevation_text = fields["elevation_ft"].get().strip()
        if not elevation_text or elevation_text == "0" or float(elevation_text or 0) == 0:
            # Auto-fetch elevation
            self.fetch_site_elevation(site_label)
    
    def fetch_site_elevation(self, site_label):
        """Fetch elevation data for a specific site"""
        fields = self.site_a_fields if site_label == "A" else self.site_b_fields
        
        try:
            # Parse coordinates
            format_type = fields["coord_format"].get()
            lat = fields["latitude"].get().strip()
            lon = fields["longitude"].get().strip()
            
            if not lat or not lon:
                self.status_var.set(f"Site {site_label}: Enter latitude and longitude first.")
                return
            
            # Convert to decimal coordinates
            try:
                if format_type == "DMS (DD-MM-SS.S N/S)":
                    lat_decimal, lon_decimal = self.convert_dms_to_decimal(lat, lon)
                else:
                    lat_decimal = float(lat)
                    lon_decimal = float(lon)
            except Exception as e:
                self.status_var.set(f"Site {site_label}: Invalid coordinates format.")
                return
            
            # Fetch elevation data
            self.status_var.set(f"Fetching elevation for Site {site_label}...")
            self.update_idletasks()
            
            elevation = fetch_elevation_data(lat_decimal, lon_decimal)
            
            if elevation is not None:
                # Update elevation field
                fields["elevation_ft"].delete(0, tk.END)
                fields["elevation_ft"].insert(0, f"{elevation:.2f}")
                self.status_var.set(f"Site {site_label}: Elevation fetched successfully: {elevation:.2f} ft")
            else:
                self.status_var.set(f"Site {site_label}: Failed to fetch elevation data.")
        
        except Exception as e:
            logger.error(f"Error in fetch_site_elevation: {e}")
            self.status_var.set(f"Site {site_label}: Error fetching elevation: {str(e)}")
    
    def fetch_all_elevations(self):
        """Fetch elevation data for both sites"""
        self.fetch_site_elevation("A")
        self.fetch_site_elevation("B")
    
    def parse_coordinates(self, lat, lon, format_type):
        """Parse coordinates based on the selected format"""
        try:
            if format_type == "DMS (DD-MM-SS.S N/S)":
                # Use the provided convert_dms_to_decimal function
                return self.convert_dms_to_decimal(lat, lon)
            else:  # Decimal format
                # Try to convert directly to float
                lat_val = float(lat)
                lon_val = float(lon)
                
                # Validate ranges
                if not (-90 <= lat_val <= 90):
                    raise ValueError("Latitude must be between -90 and 90 degrees")
                if not (-180 <= lon_val <= 180):
                    raise ValueError("Longitude must be between -180 and 180 degrees")
                    
                return lat_val, lon_val
        except ValueError as e:
            raise ValueError(f"Invalid coordinate format: {str(e)}")
    
    def validate_input(self):
        """Validate all input fields"""
        # Validate Site A
        site_a = self.get_site_data("A")
        site_b = self.get_site_data("B")
        
        # Validate latitude/longitude format for both sites
        try:
            format_a = self.site_a_fields["coord_format"].get()
            format_b = self.site_b_fields["coord_format"].get()
            
            lat_a, lon_a = self.parse_coordinates(site_a["latitude"], site_a["longitude"], format_a)
            lat_b, lon_b = self.parse_coordinates(site_b["latitude"], site_b["longitude"], format_b)
            
            if not all([lat_a is not None, lon_a is not None, lat_b is not None, lon_b is not None]):
                messagebox.showerror("Validation Error", "Invalid coordinate values.")
                return False
                
        except Exception as e:
            messagebox.showerror("Validation Error", f"Invalid coordinates: {str(e)}")
            return False
        
        # Validate frequency
        try:
            frequency = float(self.frequency_ghz.get())
            if frequency <= 0:
                messagebox.showerror("Validation Error", "Frequency must be greater than 0 GHz.")
                return False
        except ValueError:
            messagebox.showerror("Validation Error", "Frequency must be a number.")
            return False
            
        # Validate numeric fields
        for site_label, site_data in [("A", site_a), ("B", site_b)]:
            for field in ["elevation_ft", "antenna_cl_ft", "azimuth_deg"]:
                try:
                    float(site_data[field])
                except ValueError:
                    messagebox.showerror("Validation Error", f"Site {site_label} {field} must be a number.")
                    return False
        
        # Store the parsed coordinates for later use
        self.parsed_coords = {
            "lat_a": lat_a,
            "lon_a": lon_a,
            "lat_b": lat_b,
            "lon_b": lon_b
        }
        
        return True
    
    def get_site_data(self, site_label):
        """Get the data for a site"""
        fields = self.site_a_fields if site_label == "A" else self.site_b_fields
        
        return {
            "site_id": fields["site_id"].get(),
            "latitude": fields["latitude"].get(),
            "longitude": fields["longitude"].get(),
            "elevation_ft": float(fields["elevation_ft"].get() or 0),
            "antenna_cl_ft": float(fields["antenna_cl_ft"].get() or 0),
            "azimuth_deg": float(fields["azimuth_deg"].get() or 0)
        }
    
    def format_dms_from_decimal(self, decimal_val, is_latitude=True):
        """Convert decimal coordinates to DMS format for storing"""
        # Determine direction
        direction = 'N' if decimal_val >= 0 and is_latitude else 'S' if is_latitude else 'E' if decimal_val >= 0 else 'W'
        
        # Take absolute value for calculations
        decimal_val = abs(decimal_val)
        
        # Break into components
        degrees = int(decimal_val)
        minutes_full = (decimal_val - degrees) * 60
        minutes = int(minutes_full)
        seconds = (minutes_full - minutes) * 60
        
        # Format the DMS string
        return f"{degrees}-{minutes}-{seconds:.1f} {direction}"
    
    def submit(self):
        """Submit the form"""
        if not self.validate_input():
            return
            
        # Get the data
        site_a = self.get_site_data("A")
        site_b = self.get_site_data("B")
        
        # Use the parsed coordinates from validation
        lat_a = self.parsed_coords["lat_a"]
        lon_a = self.parsed_coords["lon_a"]
        lat_b = self.parsed_coords["lat_b"]
        lon_b = self.parsed_coords["lon_b"]
        
        # Convert decimal coordinates to DMS format for consistency
        format_a = self.site_a_fields["coord_format"].get()
        format_b = self.site_b_fields["coord_format"].get()
        
        if format_a == "Decimal (±DD.DDDD)":
            site_a["latitude"] = self.format_dms_from_decimal(lat_a, True)
            site_a["longitude"] = self.format_dms_from_decimal(lon_a, False)
            
        if format_b == "Decimal (±DD.DDDD)":
            site_b["latitude"] = self.format_dms_from_decimal(lat_b, True)
            site_b["longitude"] = self.format_dms_from_decimal(lon_b, False)
        
        # Calculate path length
        try:
            path_length_mi = self.calculate_distance((lat_a, lon_a), (lat_b, lon_b))
            # Distance is already in miles, no conversion needed
        except Exception as e:
            logger.error(f"Error calculating path length: {e}")
            path_length_mi = 0
        
        # Get frequency value
        try:
            frequency_ghz = float(self.frequency_ghz.get())
        except ValueError:
            # Try to read from tower_parameters.json first (user preference)
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    frequency_ghz = float(tower_params['general_parameters']['frequency_ghz'])
                    logger.info(f"Using frequency from tower_parameters.json: {frequency_ghz} GHz")
            except:
                frequency_ghz = 11.0  # Final fallback for manual input form
                logger.warning("Using default frequency 11.0 GHz for manual input")
            
        # Create the data structure
        data = {
            "site_A": site_a,
            "site_B": site_b,
            "general_parameters": {
                "frequency_ghz": frequency_ghz,
                "path_length_mi": path_length_mi
            }
        }
        
        # Close the dialog
        self.destroy()
        
        # Call the callback
        self.callback(data) 