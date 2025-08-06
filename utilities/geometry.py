import math
import numpy as np
import logging
import os
from tkinter import filedialog, messagebox
from log_config import setup_logging
from utilities.coordinates import convert_dms_to_decimal, calculate_bearing, destination_point
from utilities.lidar_map import export_polygon_as_kml, export_polygon_as_shapefile, export_polygon

# Create logger
logger = setup_logging(__name__)

def calculate_polygon_points(start, end, width_ft, extension_ft=1000):
    """
    Calculate polygon points around a path with specified width, extending past both sites.

    Args:
        start: Tuple of (lat, lon) for start point
        end: Tuple of (lat, lon) for end point
        width_ft: Search distance in feet from path centerline (±width_ft creates total width of 2*width_ft)
        extension_ft: Distance in feet to extend the polygon past both sites (default: 1000 feet)

    Returns:
        List of (lat, lon) tuples forming the polygon
        
    Note: Total polygon width = 2 * width_ft (width_ft extends in each direction from centerline)
    """
    try:
        # Convert width and extension from feet to meters
        width_m = width_ft * 0.3048
        extension_m = extension_ft * 0.3048

        # Ensure coordinates are in decimal degrees
        if isinstance(start[0], str) or isinstance(start[1], str):
            start = convert_dms_to_decimal(start[0], start[1])

        if isinstance(end[0], str) or isinstance(end[1], str):
            end = convert_dms_to_decimal(end[0], end[1])

        # Calculate bearing from start to end
        forward_bearing = calculate_bearing(start[0], start[1], end[0], end[1])
        # Calculate reverse bearing (from end to start)
        reverse_bearing = (forward_bearing + 180) % 360

        # Calculate perpendicular bearings (90 degrees to left and right)
        left_bearing = (forward_bearing - 90) % 360
        right_bearing = (forward_bearing + 90) % 360

        # Extend the start and end points by the extension distance
        extended_start = destination_point(start[0], start[1], reverse_bearing, extension_m)
        extended_end = destination_point(end[0], end[1], forward_bearing, extension_m)

        # Calculate the four corners of the polygon using the extended points
        # Extended start point left and right (using full width_m as distance from centerline)
        start_left = destination_point(extended_start[0], extended_start[1], left_bearing, width_m)
        start_right = destination_point(extended_start[0], extended_start[1], right_bearing, width_m)

        # Extended end point left and right (using full width_m as distance from centerline)
        end_left = destination_point(extended_end[0], extended_end[1], left_bearing, width_m)
        end_right = destination_point(extended_end[0], extended_end[1], right_bearing, width_m)

        # Return polygon points in clockwise order
        polygon = [start_left, end_left, end_right, start_right]

        logger.info(f"Generated polygon with ±{width_ft}ft (total width {width_ft*2}ft) around path from {start} to {end}, extended by {extension_ft}ft")
        return polygon

    except Exception as e:
        logger.error(f"Error calculating polygon points: {e}", exc_info=True)
        raise

def generate_ring_points(x, y, z, radius, ring_height, num_points=360):
    """
    Generate points for a ring at specified coordinates.

    Args:
        x, y, z: Center coordinates of the ring
        radius: Radius of the ring
        ring_height: Height of the ring
        num_points: Number of points to generate around the ring

    Returns:
        List of dictionaries with x, y, z coordinates and RGB color values
    """
    try:
        points = []
        angles = np.linspace(0, 2*np.pi, num_points, endpoint=False)

        for angle in angles:
            px = x + radius * np.cos(angle)
            py = y + radius * np.sin(angle)

            points.append({
                'x': px, 'y': py, 'z': z + ring_height,
                'r': 255, 'g': 255, 'b': 255  # Default white color
            })

        logger.debug(f"Generated {len(points)} points for ring at ({x}, {y}, {z})")
        return points

    except Exception as e:
        logger.error(f"Error generating ring points: {e}", exc_info=True)
        return []

def generate_ring_stack(x, y, base_z, radius, color, vertical_spacing=10, num_rings=5):
    """
    Generate a stack of rings at specified coordinates.

    Args:
        x, y: Center coordinates
        base_z: Base height
        radius: Radius of rings
        color: RGB tuple for ring color
        vertical_spacing: Spacing between rings
        num_rings: Number of rings to generate

    Returns:
        List of dictionaries with x, y, z coordinates and RGB color values
    """
    try:
        all_points = []

        for i in range(num_rings):
            z = base_z + i * vertical_spacing
            ring_points = generate_ring_points(x, y, z, radius, 0)

            # Apply color to all points
            for point in ring_points:
                point['r'] = color[0]
                point['g'] = color[1]
                point['b'] = color[2]

            all_points.extend(ring_points)

        logger.debug(f"Generated stack of {num_rings} rings with {len(all_points)} total points")
        return all_points

    except Exception as e:
        logger.error(f"Error generating ring stack: {e}", exc_info=True)
        return []

def point_in_polygon(point, polygon):
    """
    Check if a point is inside a polygon using ray casting algorithm.

    Args:
        point: Tuple of (lat, lon)
        polygon: List of (lat, lon) tuples forming the polygon

    Returns:
        Boolean indicating if point is inside polygon
    """
    try:
        x, y = point
        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
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
        logger.error(f"Error checking if point is in polygon: {e}")
        return False

def calculate_perpendicular_distance(point, line_start, line_end):
    """
    Calculate the perpendicular distance from a point to a line.

    Args:
        point: Tuple of (lat, lon)
        line_start: Tuple of (lat, lon) for line start
        line_end: Tuple of (lat, lon) for line end

    Returns:
        Distance in meters
    """
    try:
        # Convert to radians for spherical calculations
        lat1, lon1 = map(math.radians, line_start)
        lat2, lon2 = map(math.radians, line_end)
        lat3, lon3 = map(math.radians, point)

        # Earth radius in meters
        R = 6371000

        # Calculate the bearing from start to end
        bearing12 = math.atan2(
            math.sin(lon2 - lon1) * math.cos(lat2),
            math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
        )

        # Calculate the bearing from start to point
        bearing13 = math.atan2(
            math.sin(lon3 - lon1) * math.cos(lat3),
            math.cos(lat1) * math.sin(lat3) - math.sin(lat1) * math.cos(lat3) * math.cos(lon3 - lon1)
        )

        # Calculate the distance from start to point
        d13 = math.acos(
            math.sin(lat1) * math.sin(lat3) +
            math.cos(lat1) * math.cos(lat3) * math.cos(lon3 - lon1)
        ) * R

        # Calculate the cross-track distance
        dxt = math.asin(math.sin(d13 / R) * math.sin(bearing13 - bearing12)) * R

        return abs(dxt)

    except Exception as e:
        logger.error(f"Error calculating perpendicular distance: {e}")
        return 0

def export_search_polygon_as_kml(polygon_points, donor_site=None, recipient_site=None):
    """
    Export the LIDAR search polygon as a KML file

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        donor_site: Dictionary containing donor site information (optional)
        recipient_site: Dictionary containing recipient site information (optional)

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.warning("No polygon points available for KML export")
            messagebox.showinfo("Export Error", "No LIDAR search area defined. Please set donor and recipient sites first.")
            return False

        # Get site IDs if available
        site_a_id = donor_site.get('site_id', 'SiteA') if donor_site else 'SiteA'
        site_b_id = recipient_site.get('site_id', 'SiteB') if recipient_site else 'SiteB'

        logger.info(f"Exporting search polygon as KML with {len(polygon_points)} points")

        # Create filename based on site IDs
        site_a_str = site_a_id.replace(" ", "_")
        site_b_str = site_b_id.replace(" ", "_")
        base_filename = f"{site_a_str}_{site_b_str}_LidarPolygon"

        # Ask for directory to save file
        output_dir = filedialog.askdirectory(
            title="Select folder to save KML file",
            initialdir=os.path.expanduser("~")
        )

        if not output_dir:
            logger.info("KML export cancelled by user")
            return False

        # Set full path for KML file
        kml_path = os.path.join(output_dir, f"{base_filename}.kml")

        # Export KML
        return export_polygon_as_kml(polygon_points, kml_path)

    except Exception as e:
        logger.error(f"Error exporting search polygon as KML: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export KML: {str(e)}")
        return False

def export_search_polygon_as_shapefile(polygon_points, donor_site=None, recipient_site=None):
    """
    Export the LIDAR search polygon as a shapefile

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        donor_site: Dictionary containing donor site information (optional)
        recipient_site: Dictionary containing recipient site information (optional)

    Returns:
        bool: True if export was successful, False otherwise
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.warning("No polygon points available for shapefile export")
            messagebox.showinfo("Export Error", "No LIDAR search area defined. Please set donor and recipient sites first.")
            return False

        # Get site IDs if available
        site_a_id = donor_site.get('site_id', 'SiteA') if donor_site else 'SiteA'
        site_b_id = recipient_site.get('site_id', 'SiteB') if recipient_site else 'SiteB'

        logger.info(f"Exporting search polygon as shapefile with {len(polygon_points)} points")

        # Create filename based on site IDs
        site_a_str = site_a_id.replace(" ", "_")
        site_b_str = site_b_id.replace(" ", "_")
        base_filename = f"{site_a_str}_{site_b_str}_LidarPolygon"

        # Ask for directory to save file
        output_dir = filedialog.askdirectory(
            title="Select folder to save shapefile",
            initialdir=os.path.expanduser("~")
        )

        if not output_dir:
            logger.info("Shapefile export cancelled by user")
            return False

        # Set full path for shapefile
        shp_path = os.path.join(output_dir, f"{base_filename}.shp")

        # Export shapefile
        return export_polygon_as_shapefile(polygon_points, shp_path)

    except Exception as e:
        logger.error(f"Error exporting search polygon as shapefile: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export shapefile: {str(e)}")
        return False

def export_search_polygon(polygon_points, donor_site=None, recipient_site=None):
    """
    Export the LIDAR search polygon as both KML and shapefile

    Args:
        polygon_points: List of (lat, lon) tuples forming the polygon
        donor_site: Dictionary containing donor site information (optional)
        recipient_site: Dictionary containing recipient site information (optional)

    Returns:
        tuple: (kml_success, shp_success) indicating if each export was successful
    """
    try:
        if not polygon_points or len(polygon_points) < 3:
            logger.warning("No polygon points available for export")
            messagebox.showinfo("Export Error", "No LIDAR search area defined. Please set donor and recipient sites first.")
            return False, False

        # Get site IDs if available
        site_a_id = donor_site.get('site_id', 'SiteA') if donor_site else 'SiteA'
        site_b_id = recipient_site.get('site_id', 'SiteB') if recipient_site else 'SiteB'

        logger.info(f"Exporting search polygon with {len(polygon_points)} points")
        logger.info(f"Using site IDs for export: {site_a_id} and {site_b_id}")

        # Pass site IDs to export function
        return export_polygon(polygon_points, site_a_id, site_b_id)

    except Exception as e:
        logger.error(f"Error exporting search polygon: {e}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export polygon: {str(e)}")
        return False, False

def create_and_display_polygon(map_widget, site_a, site_b, width_ft, extension_ft=200):
    """
    Create and display a polygon on the map around a path between two sites,
    extending past both sites by the specified distance.

    Args:
        map_widget: The tkintermapview map widget to display the polygon on
        site_a: Dictionary containing donor site information
        site_b: Dictionary containing recipient site information
        width_ft: Width of the polygon in feet
        extension_ft: Distance in feet to extend the polygon past both sites (default: 200 feet)

    Returns:
        tuple: (polygon_points, polygon_object) - the polygon points and the map polygon object
    """
    try:
        # Convert coordinates from DMS to decimal
        lat_a, lon_a = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
        lat_b, lon_b = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])

        # Calculate polygon points using width and extension
        polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), width_ft, extension_ft)

        # Create polygon on map
        polygon_around_path = map_widget.set_polygon(
            polygon_points,
            fill_color=None,
            outline_color="black",
            border_width=1,  # Thinner line
            name="LOS Polygon")

        logger.info(f"Created polygon with width {width_ft}ft between sites, extended by {extension_ft}ft")
        return polygon_points, polygon_around_path

    except Exception as e:
        logger.error(f"Error creating and displaying polygon: {e}", exc_info=True)
        return None, None