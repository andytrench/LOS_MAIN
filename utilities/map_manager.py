"""
Map management module for the LOS application.
Handles map initialization, styling, and visualization.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkintermapview
import logging
import math
import os
from PIL import Image, ImageTk
from log_config import setup_logging
from utilities.coordinates import convert_dms_to_decimal
from utilities.geometry import calculate_polygon_points
from utilities.lidar_map import export_polygon_as_kml, export_polygon_as_shapefile, export_polygon

# Create logger
logger = setup_logging(__name__)

class MapManager:
    def __init__(self, map_frame):
        """Initialize the map manager with the map frame"""
        self.map_frame = map_frame


class MapController:
    """Controller class for map-related functionality"""

    def __init__(self, map_widget, root=None):
        """Initialize the map controller

        Args:
            map_widget: The map widget to control
            root: The root window
        """
        self.map_widget = map_widget
        self.root = root

        # Initialize variables
        self.polygon_width_ft = tk.IntVar(value=2000)
        self.polygon_points = []
        self.donor_site = None
        self.recipient_site = None
        self.site_markers = {}
        self.path_line = None
        self.polygon = None

        # Add trace to update polygon when width changes
        self.polygon_width_ft.trace_add('write', self._on_width_change)

    def set_polygon_points(self, points):
        """Set the polygon points for the search area"""
        logger.info(f"Setting polygon points: {len(points)} points")
        self.polygon_points = points
        self._update_map_display()

    def update_site_data(self, site_a, site_b):
        """Update the donor and recipient site data"""
        logger.info("Updating site data in MapController")
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
                self._update_map_display()
            except Exception as e:
                logger.error(f"Error updating polygon: {e}", exc_info=True)

    def center_map_on_path(self):
        """Center the map on the path between donor and recipient sites"""
        try:
            if not self.map_widget:
                logger.warning("No map widget available")
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

                self._update_map_display()
        except Exception as e:
            logger.error(f"Error updating polygon width: {e}", exc_info=True)

    def _update_map_display(self):
        """Update the map display with current data"""
        try:
            if not self.map_widget:
                return

            # Clear existing markers and lines
            if hasattr(self, 'site_markers'):
                for marker_id, marker in self.site_markers.items():
                    self.map_widget.delete(marker)
                self.site_markers = {}

            if hasattr(self, 'path_line') and self.path_line:
                self.map_widget.delete(self.path_line)
                self.path_line = None

            if hasattr(self, 'polygon') and self.polygon:
                self.map_widget.delete(self.polygon)
                self.polygon = None

            # Add donor site marker
            if self.donor_site:
                lat_a, lon_a = convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
                self.site_markers['donor'] = self.map_widget.set_marker(
                    lat_a, lon_a,
                    text=self.donor_site.get('site_id', 'Donor'),
                    text_color="blue",
                    marker_color_outside="blue",
                    marker_color_circle="white"
                )

            # Add recipient site marker
            if self.recipient_site:
                lat_b, lon_b = convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])
                self.site_markers['recipient'] = self.map_widget.set_marker(
                    lat_b, lon_b,
                    text=self.recipient_site.get('site_id', 'Recipient'),
                    text_color="red",
                    marker_color_outside="red",
                    marker_color_circle="white"
                )

            # Add path line
            if self.donor_site and self.recipient_site:
                lat_a, lon_a = convert_dms_to_decimal(self.donor_site['latitude'], self.donor_site['longitude'])
                lat_b, lon_b = convert_dms_to_decimal(self.recipient_site['latitude'], self.recipient_site['longitude'])
                self.path_line = self.map_widget.set_path([
                    (lat_a, lon_a),
                    (lat_b, lon_b)
                ])

            # Add polygon
            if self.polygon_points and len(self.polygon_points) > 2:
                self.polygon = self.map_widget.set_polygon(
                    self.polygon_points,
                    fill_color=None,
                    outline_color="black",
                    border_width=1,
                    name="LOS Polygon"
                )
        except Exception as e:
            logger.error(f"Error updating map display: {e}", exc_info=True)

    def export_search_polygon_as_kml(self):
        """Export the search polygon as a KML file"""
        logger.info("Exporting search polygon as KML")
        try:
            if not self.polygon_points or len(self.polygon_points) < 3:
                messagebox.showwarning("Warning", "No valid polygon to export")
                return

            # Get site IDs if available
            site_a_id = self.donor_site.get('site_id') if self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if self.recipient_site else None

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
            site_a_id = self.donor_site.get('site_id') if self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if self.recipient_site else None

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
            site_a_id = self.donor_site.get('site_id') if self.donor_site else None
            site_b_id = self.recipient_site.get('site_id') if self.recipient_site else None

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

    def clear_map(self):
        """Clear all map elements"""
        try:
            if not self.map_widget:
                return

            # Clear existing markers and lines
            if hasattr(self, 'site_markers'):
                for marker_id, marker in self.site_markers.items():
                    self.map_widget.delete(marker)
                self.site_markers = {}

            if hasattr(self, 'path_line') and self.path_line:
                self.map_widget.delete(self.path_line)
                self.path_line = None

            if hasattr(self, 'polygon') and self.polygon:
                self.map_widget.delete(self.polygon)
                self.polygon = None

            # Reset variables
            self.polygon_points = []
            self.donor_site = None
            self.recipient_site = None

            logger.info("Map cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing map: {e}", exc_info=True)
        self.map_widget = None
        self.markers = {}
        self.paths = {}
        self.polygons = {}
        self.site_a_marker = None
        self.site_b_marker = None
        self.path_line = None

        # Initialize map
        self.initialize_map()

    def initialize_map(self):
        """Initialize the map widget"""
        self.map_widget = tkintermapview.TkinterMapView(self.map_frame, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True, padx=5, pady=5)
        self.map_widget.set_zoom(7)

        # Initialize tracking variable for mouse position
        self.map_widget.last_mouse_down_position = None

        return self.map_widget

    def create_map_controls(self, parent_frame):
        """Create map control elements"""
        # Map control frame
        map_control_frame = ttk.Frame(parent_frame)
        map_control_frame.pack(fill="x", padx=5, pady=2)

        # Map style dropdown
        map_style_var = tk.StringVar(value="OpenStreetMap")
        style_label = ttk.Label(map_control_frame, text="Map Style:")
        style_label.pack(side="left", padx=5)

        map_style_dropdown = ttk.Combobox(
            map_control_frame,
            textvariable=map_style_var,
            values=["OpenStreetMap", "Google Normal", "Google Satellite", "Google Terrain", "Google Hybrid"],
            width=15
        )
        map_style_dropdown.pack(side="left", padx=5)
        map_style_dropdown.bind("<<ComboboxSelected>>", lambda e: self.change_map_style(map_style_var.get()))

        return map_control_frame

    def change_map_style(self, style_name):
        """Change the map style"""
        if not self.map_widget:
            return

        logger.info(f"Changing map style to: {style_name}")

        if style_name == "OpenStreetMap":
            self.map_widget.set_tile_server("https://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
        elif style_name == "Google Normal":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=m&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif style_name == "Google Satellite":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif style_name == "Google Terrain":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        elif style_name == "Google Hybrid":
            self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)

    def update_map(self, site_a, site_b):
        """Update the map with site markers and path"""
        if not self.map_widget:
            logger.error("Map widget not initialized")
            return

        try:
            # Clear existing markers and path
            self.clear_map_elements()

            # Add site markers
            self.add_site_markers(site_a, site_b)

            # Add path line
            self.add_path_line(site_a, site_b)

            # Center map on path
            self.center_map_on_path(site_a, site_b)

            logger.info("Map updated successfully")
            return True
        except Exception as e:
            logger.error(f"Error updating map: {str(e)}", exc_info=True)
            return False

    def clear_map_elements(self):
        """Clear existing markers and paths from the map"""
        # Clear site markers
        if self.site_a_marker:
            self.site_a_marker.delete()
            self.site_a_marker = None

        if self.site_b_marker:
            self.site_b_marker.delete()
            self.site_b_marker = None

        # Clear path line
        if self.path_line:
            self.path_line.delete()
            self.path_line = None

        # Clear other markers and paths
        for marker_id in list(self.markers.keys()):
            self.markers[marker_id].delete()
            del self.markers[marker_id]

        for path_id in list(self.paths.keys()):
            self.paths[path_id].delete()
            del self.paths[path_id]

        for polygon_id in list(self.polygons.keys()):
            self.polygons[polygon_id].delete()
            del self.polygons[polygon_id]

    def add_site_markers(self, site_a, site_b):
        """Add site markers to the map"""
        # Add site A marker
        self.site_a_marker = self.map_widget.set_marker(
            site_a["adjusted_latitude"],
            site_a["adjusted_longitude"],
            text=f"Site A: {site_a['site_id']}",
            icon=self.create_marker_icon("A", "blue")
        )

        # Add site B marker
        self.site_b_marker = self.map_widget.set_marker(
            site_b["adjusted_latitude"],
            site_b["adjusted_longitude"],
            text=f"Site B: {site_b['site_id']}",
            icon=self.create_marker_icon("B", "red")
        )

    def add_path_line(self, site_a, site_b):
        """Add path line between sites"""
        self.path_line = self.map_widget.set_path([
            (site_a["adjusted_latitude"], site_a["adjusted_longitude"]),
            (site_b["adjusted_latitude"], site_b["adjusted_longitude"])
        ])

    def center_map_on_path(self, site_a, site_b):
        """Center the map on the path between sites"""
        # Calculate center point
        center_lat = (site_a["adjusted_latitude"] + site_b["adjusted_latitude"]) / 2
        center_lon = (site_a["adjusted_longitude"] + site_b["adjusted_longitude"]) / 2

        # Calculate appropriate zoom level based on distance
        lat1, lon1 = site_a["adjusted_latitude"], site_a["adjusted_longitude"]
        lat2, lon2 = site_b["adjusted_latitude"], site_b["adjusted_longitude"]

        # Calculate distance in degrees
        distance = math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2)

        # Set zoom level based on distance
        if distance < 0.05:
            zoom = 12
        elif distance < 0.1:
            zoom = 11
        elif distance < 0.2:
            zoom = 10
        elif distance < 0.5:
            zoom = 9
        elif distance < 1.0:
            zoom = 8
        else:
            zoom = 7

        # Center and zoom map
        self.map_widget.set_position(center_lat, center_lon)
        self.map_widget.set_zoom(zoom)

    def add_polygon(self, polygon_points, color="#3388ff", width=2, fill_color=None, polygon_id=None):
        """Add a polygon to the map"""
        if not polygon_id:
            polygon_id = f"polygon_{len(self.polygons)}"

        # Create polygon
        polygon = self.map_widget.set_polygon(
            polygon_points,
            outline_color=color,
            width=width,
            fill_color=fill_color if fill_color else self.get_transparent_color(color)
        )

        # Store polygon
        self.polygons[polygon_id] = polygon

        return polygon

    def create_marker_icon(self, text, color="blue", size=20):
        """Create a custom marker icon with text"""
        # Create image
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))

        # Map color names to RGB
        color_map = {
            "blue": (51, 136, 255),
            "red": (255, 51, 51),
            "green": (51, 204, 51),
            "yellow": (255, 204, 0),
            "purple": (153, 51, 255),
            "orange": (255, 136, 0)
        }

        rgb_color = color_map.get(color, (51, 136, 255))

        # Draw circle
        import PIL.ImageDraw as ImageDraw
        import PIL.ImageFont as ImageFont

        draw = ImageDraw.Draw(image)
        draw.ellipse((0, 0, size-1, size-1), fill=rgb_color, outline="white")

        # Draw text
        try:
            font = ImageFont.truetype("Arial", size//2)
        except IOError:
            font = ImageFont.load_default()

        text_width, text_height = draw.textsize(text, font=font)
        position = ((size-text_width)//2, (size-text_height)//2)
        draw.text(position, text, fill="white", font=font)

        return ImageTk.PhotoImage(image)

    def get_transparent_color(self, color, alpha=0.2):
        """Convert color to transparent version for polygon fill"""
        # If color is in hex format (#RRGGBB)
        if color.startswith("#"):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return f"#{r:02x}{g:02x}{b:02x}{int(alpha*255):02x}"

        # If color is a named color, use default transparent blue
        return "#3388ff33"

    def capture_map_image(self):
        """Capture the current map view as an image"""
        try:
            # Get map widget's position and size
            x = self.map_widget.winfo_rootx()
            y = self.map_widget.winfo_rooty()
            width = self.map_widget.winfo_width()
            height = self.map_widget.winfo_height()

            # Capture screenshot
            from PIL import ImageGrab
            image = ImageGrab.grab((x, y, x+width, y+height))

            return image
        except Exception as e:
            logger.error(f"Error capturing map image: {str(e)}", exc_info=True)
            return None
