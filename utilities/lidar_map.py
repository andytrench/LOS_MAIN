import os
import math
import logging
import simplekml
import geopandas as gpd
from shapely.geometry import Polygon
from tkinter import filedialog, messagebox
import tkinter as tk
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def export_polygon_as_kml(polygon_points, output_path=None):
    """
    Export polygon points as KML file

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        output_path: Optional path to save the KML file. If None, a file dialog will be shown.

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.error("Cannot export KML: Not enough polygon points")
            messagebox.showerror("Export Error", "Not enough points to create a polygon (minimum 3 required)")
            return False

        # Create KML object
        kml = simplekml.Kml()

        # Create polygon
        pol = kml.newpolygon(name="LIDAR Search Area")

        # Set polygon properties
        pol.outerboundaryis = [(point[1], point[0], 0) for point in polygon_points]  # KML uses (lon, lat) format
        pol.style.linestyle.color = simplekml.Color.blue
        pol.style.linestyle.width = 3
        pol.style.polystyle.color = simplekml.Color.changealphaint(100, simplekml.Color.lightblue)

        # If no output path provided, show file dialog
        if not output_path:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".kml",
                filetypes=[("KML files", "*.kml"), ("All files", "*.*")],
                title="Save KML File"
            )

        if not output_path:
            logger.info("KML export cancelled by user")
            return False

        # Save KML file
        kml.save(output_path)
        logger.info(f"KML file exported successfully to: {output_path}")
        messagebox.showinfo("Export Successful", f"KML file exported to:\n{output_path}")
        return True

    except Exception as e:
        logger.error(f"Error exporting KML: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export KML file: {str(e)}")
        return False

def export_polygon_as_shapefile(polygon_points, output_path=None):
    """
    Export polygon points as Shapefile

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        output_path: Optional path to save the Shapefile. If None, a file dialog will be shown.

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.error("Cannot export Shapefile: Not enough polygon points")
            messagebox.showerror("Export Error", "Not enough points to create a polygon (minimum 3 required)")
            return False

        # Create a shapely polygon from the points
        # Shapefile uses (lon, lat) format
        poly = Polygon([(point[1], point[0]) for point in polygon_points])

        # Create a GeoDataFrame
        gdf = gpd.GeoDataFrame(
            {'name': ['LIDAR Search Area']},
            geometry=[poly],
            crs="EPSG:4326"  # WGS84 coordinate system
        )

        # If no output path provided, show file dialog
        if not output_path:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".shp",
                filetypes=[("Shapefiles", "*.shp"), ("All files", "*.*")],
                title="Save Shapefile"
            )

        if not output_path:
            logger.info("Shapefile export cancelled by user")
            return False

        # Save Shapefile
        gdf.to_file(output_path)
        logger.info(f"Shapefile exported successfully to: {output_path}")
        messagebox.showinfo("Export Successful", f"Shapefile exported to:\n{output_path}")
        return True

    except Exception as e:
        logger.error(f"Error exporting Shapefile: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export Shapefile: {str(e)}")
        return False

def export_polygon(polygon_points, site_a_id=None, site_b_id=None):
    """
    Export polygon as both KML and Shapefile with filenames using site IDs

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        site_a_id: Identifier for Site A (donor)
        site_b_id: Identifier for Site B (recipient)

    Returns:
        tuple: (kml_success, shp_success) indicating if each export was successful
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.error("Cannot export polygon: Not enough polygon points")
            messagebox.showerror("Export Error", "Not enough points to create a polygon (minimum 3 required)")
            return False, False

        # Format site IDs for filename
        site_a_str = site_a_id.replace(" ", "_") if site_a_id else "SiteA"
        site_b_str = site_b_id.replace(" ", "_") if site_b_id else "SiteB"

        # Create base filename
        base_filename = f"{site_a_str}_{site_b_str}_LidarPolygon"

        # Ask for directory to save files
        output_dir = filedialog.askdirectory(
            title="Select folder to save export files",
            initialdir=os.path.expanduser("~")
        )

        if not output_dir:
            logger.info("Export cancelled by user")
            return False, False

        # Set full paths for both file types
        kml_path = os.path.join(output_dir, f"{base_filename}.kml")
        shp_path = os.path.join(output_dir, f"{base_filename}.shp")

        # Export both formats
        kml_success = export_polygon_as_kml(polygon_points, kml_path)
        shp_success = export_polygon_as_shapefile(polygon_points, shp_path)

        # Show combined result message
        if kml_success and shp_success:
            messagebox.showinfo("Export Successful",
                               f"Files exported successfully to:\n{output_dir}\n\nFiles:\n- {base_filename}.kml\n- {base_filename}.shp")
        elif kml_success or shp_success:
            messagebox.showinfo("Partial Export Success",
                               f"Some files were exported successfully:\n"
                               f"KML: {'Success' if kml_success else 'Failed'}\n"
                               f"Shapefile: {'Success' if shp_success else 'Failed'}")

        return kml_success, shp_success

    except Exception as e:
        logger.error(f"Error in export_polygon: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export polygon: {str(e)}")
        return False, False

# Additional utility function to draw polygon on map
def draw_polygon_on_map(map_widget, polygon_points, outline_color="#3080FF",
                       fill_color="#3080FF80", width=3, delete_existing=True):
    """
    Draw a polygon on a tkintermapview map widget

    Args:
        map_widget: tkintermapview.TkinterMapView instance
        polygon_points: List of (lat, lon) tuples forming the polygon
        outline_color: Hex color code for polygon outline
        fill_color: Hex color code for polygon fill
        width: Width of the polygon outline
        delete_existing: Whether to delete existing polygons with the same tag

    Returns:
        polygon: The map polygon object that was created
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.error("Cannot draw polygon: Not enough polygon points")
            return None

        # Create polygon on map
        polygon = map_widget.set_polygon(
            polygon_points,
            outline_color=outline_color,
            fill_color=fill_color,
            width=width,
            command=lambda: None,  # No click action
            name="lidar_search_area"
        )

        logger.info(f"Polygon drawn on map with {len(polygon_points)} points")
        return polygon

    except Exception as e:
        logger.error(f"Error drawing polygon on map: {e}", exc_info=True)
        return None

def haversine_distance(coord1, coord2):
    """
    Calculate distance between two coordinates using the Haversine formula.

    Args:
        coord1: Tuple of (lat, lon) for first point
        coord2: Tuple of (lat, lon) for second point

    Returns:
        float: Distance in meters
    """
    try:
        # Import the calculate_distance_meters function from coordinates module
        from utilities.coordinates import calculate_distance_meters

        # Use the imported function to calculate distance in meters
        distance = calculate_distance_meters(coord1, coord2)
        logger.debug(f"Calculated distance between {coord1} and {coord2}: {distance:.2f}m")
        return distance

    except Exception as e:
        logger.error(f"Error calculating haversine distance: {e}", exc_info=True)
        return 0

def point_in_polygon(point, polygon):
    """
    Check if a point is inside a polygon using ray casting algorithm.

    Args:
        point: Tuple of (lat, lon)
        polygon: List of (lat, lon) tuples forming the polygon

    Returns:
        bool: True if point is inside polygon, False otherwise
    """
    try:
        if not polygon or len(polygon) < 3:
            logger.warning("Not enough points to form a polygon")
            return False

        # Extract coordinates
        x, y = point

        # Initialize inside flag
        inside = False

        # Ray casting algorithm
        n = len(polygon)
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

    except Exception as e:
        logger.error(f"Error checking if point is in polygon: {e}", exc_info=True)
        return False

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate initial bearing between two points.

    Args:
        lat1, lon1: Coordinates of first point in decimal degrees
        lat2, lon2: Coordinates of second point in decimal degrees

    Returns:
        float: Bearing in degrees (0-360)
    """
    try:
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

        # Calculate bearing
        dlon = lon2 - lon1
        y = math.sin(dlon) * math.cos(lat2)
        x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)

        # Get bearing in radians
        bearing_rad = math.atan2(y, x)

        # Convert to degrees and normalize to 0-360
        bearing_deg = math.degrees(bearing_rad)
        bearing_deg = (bearing_deg + 360) % 360

        logger.debug(f"Calculated bearing from ({lat1}, {lon1}) to ({lat2}, {lon2}): {bearing_deg:.2f}°")
        return bearing_deg

    except Exception as e:
        logger.error(f"Error calculating bearing: {e}", exc_info=True)
        return 0

def destination_point(lat, lon, bearing_deg, distance_m):
    """
    Calculate destination point given starting point, bearing and distance.

    Args:
        lat, lon: Starting point coordinates in decimal degrees
        bearing_deg: Bearing in degrees
        distance_m: Distance in meters

    Returns:
        tuple: (lat, lon) coordinates of destination point
    """
    try:
        # Convert to radians
        lat = math.radians(lat)
        lon = math.radians(lon)
        bearing = math.radians(bearing_deg)

        # Earth's radius in meters
        R = 6371000

        # Angular distance
        angular_dist = distance_m / R

        # Calculate destination latitude
        lat2 = math.asin(
            math.sin(lat) * math.cos(angular_dist) +
            math.cos(lat) * math.sin(angular_dist) * math.cos(bearing)
        )

        # Calculate destination longitude
        lon2 = lon + math.atan2(
            math.sin(bearing) * math.sin(angular_dist) * math.cos(lat),
            math.cos(angular_dist) - math.sin(lat) * math.sin(lat2)
        )

        # Convert back to degrees
        lat2 = math.degrees(lat2)
        lon2 = math.degrees(lon2)

        logger.debug(f"Calculated destination point from ({math.degrees(lat)}, {math.degrees(lon)}) "
                    f"with bearing {bearing_deg}° and distance {distance_m}m: ({lat2}, {lon2})")
        return lat2, lon2

    except Exception as e:
        logger.error(f"Error calculating destination point: {e}", exc_info=True)
        return lat, lon

def calculate_polygon_points(start, end, width_ft):
    """
    Calculate polygon points around a path with specified width.

    Args:
        start: Tuple of (lat, lon) for start point
        end: Tuple of (lat, lon) for end point
        width_ft: Width of the polygon in feet

    Returns:
        List of (lat, lon) tuples forming the polygon
    """
    try:
        # Convert width from feet to meters
        width_m = width_ft * 0.3048

        # Calculate bearing from start to end
        forward_bearing = calculate_bearing(start[0], start[1], end[0], end[1])
        reverse_bearing = (forward_bearing + 180) % 360

        # Calculate perpendicular bearings
        left_bearing = (forward_bearing - 90) % 360
        right_bearing = (forward_bearing + 90) % 360

        # Calculate extension distance (using same width as corridor width)
        extension_m = width_m

        # Calculate extended points beyond start and end
        extended_start = destination_point(start[0], start[1], reverse_bearing, extension_m)
        extended_end = destination_point(end[0], end[1], forward_bearing, extension_m)

        # Calculate the corners of the polygon
        # Extended start corners
        start_left = destination_point(extended_start[0], extended_start[1], left_bearing, width_m/2)
        start_right = destination_point(extended_start[0], extended_start[1], right_bearing, width_m/2)

        # Extended end corners
        end_left = destination_point(extended_end[0], extended_end[1], left_bearing, width_m/2)
        end_right = destination_point(extended_end[0], extended_end[1], right_bearing, width_m/2)

        # Create polygon - clockwise order for correct orientation
        polygon_points = [
            start_left,
            start_right,
            end_right,
            end_left,
            start_left  # Close the polygon
        ]

        logger.info(f"Generated polygon with width {width_ft}ft around path from {start} to {end}")
        return polygon_points

    except Exception as e:
        logger.error(f"Error calculating polygon points: {e}", exc_info=True)
        return []