"""
Visualization utility functions for the LOS application.
Provides functions for generating 3D visualizations and search rings.
"""

import math
import logging
import numpy as np
from pyproj import Transformer
from log_config import setup_logging
from utilities.coordinates import convert_dms_to_decimal

# Create logger
logger = setup_logging(__name__)

def generate_ring_points(x, y, z, radius, ring_height, num_points=360):
    """
    Generate points for a ring at specified radius and height.
    
    Args:
        x, y: Center coordinates in UTM
        z: Base elevation in feet
        radius: Ring radius in feet
        ring_height: Height of this ring in feet
        num_points: Number of points to generate around the ring
        
    Returns:
        List of (x, y, z) tuples representing points around the ring
    """
    points = []
    actual_z = z + ring_height  # Stack rings vertically

    for i in range(num_points):
        angle = math.radians(i * (360/num_points))
        px = x + radius * math.cos(angle)
        py = y + radius * math.sin(angle)
        points.append((px, py, actual_z))
    
    return points

def generate_ring_stack(x, y, base_z, radius, color, vertical_spacing=10):
    """
    Generate a stack of rings at specified radius, extending 500ft up and down.
    
    Args:
        x, y: Center coordinates in UTM
        base_z: Center elevation in feet
        radius: Ring radius in feet (200ft)
        color: (R,G,B) color tuple
        vertical_spacing: Spacing between rings in feet
        
    Returns:
        List of (x, y, z, color) tuples representing points in the ring stack
    """
    points = []
    num_points = 360  # One point per degree

    # Generate rings from -500 to +500 feet relative to base_z
    for height in range(-500, 501, vertical_spacing):
        z = base_z + height

        # Generate points around the ring
        for i in range(num_points):
            angle = math.radians(i * (360/num_points))
            px = x + radius * math.cos(angle)
            py = y + radius * math.sin(angle)
            points.append((px, py, z, color))

    return points

def export_search_rings(site_location, output_path, is_donor=True, radius=100):
    """
    Export search rings for a site location.
    
    Args:
        site_location: Dictionary containing site location data
        output_path: Path to save the output file
        is_donor: Whether this is a donor site (True) or recipient site (False)
        radius: Radius of the search rings in feet
        
    Returns:
        Path to the created file or None if an error occurred
    """
    try:
        site_type = "donor" if is_donor else "recipient"
        logger.info(f"Exporting search rings for {site_type} site")
        logger.debug(f"Site location data: {site_location}")

        # Get site coordinates
        lat = site_location['latitude']
        lon = site_location['longitude']
        elevation_ft = float(site_location['elevation_ft'])
        antenna_cl_ft = float(site_location['antenna_cl_ft'])

        # Convert coordinates if needed
        if isinstance(lat, str) and 'N' in lat:
            logger.debug("Converting DMS coordinates to decimal")
            lat, lon = convert_dms_to_decimal(lat, lon)
            logger.debug(f"Converted coordinates: {lat}, {lon}")

        # Create transformer for coordinate conversion
        transformer = Transformer.from_crs(
            "EPSG:4326",  # WGS84
            "EPSG:32618", # UTM zone 18N
            always_xy=True
        )

        # Transform coordinates to UTM
        site_utm_x, site_utm_y = transformer.transform(lon, lat)
        logger.debug(f"UTM coordinates: {site_utm_x}, {site_utm_y}")

        # Convert heights to meters
        base_height = elevation_ft * 0.3048
        antenna_height = antenna_cl_ft * 0.3048
        logger.debug(f"Base height: {base_height}m, Antenna height: {antenna_height}m")

        # Generate rings at different heights
        rings = []
        heights = [
            base_height,                        # Ground level
            base_height + antenna_height,       # Antenna centerline
            base_height + antenna_height + 50,  # Above antenna
            base_height + antenna_height - 50   # Below antenna
        ]
        
        # Generate rings at each height
        for height in heights:
            ring = generate_ring_points(site_utm_x, site_utm_y, height, radius, 0)
            rings.extend(ring)
            
        # Export rings to file
        with open(output_path, 'w') as f:
            for point in rings:
                f.write(f"{point[0]},{point[1]},{point[2]}\n")
                
        logger.info(f"Search rings exported to {output_path}")
        return output_path
        
    except Exception as e:
        logger.error(f"Error exporting search rings: {e}", exc_info=True)
        return None

def generate_fresnel_zone(site_a, site_b, frequency_ghz=11, num_points=100):
    """
    Generate points representing the Fresnel zone between two sites.
    
    Args:
        site_a: Dictionary containing site A location data
        site_b: Dictionary containing site B location data
        frequency_ghz: Frequency in GHz
        num_points: Number of points to generate along the path
        
    Returns:
        List of (lat, lon, elevation, radius) tuples representing the Fresnel zone
    """
    try:
        # Get site coordinates
        lat1, lon1 = site_a['latitude'], site_a['longitude']
        lat2, lon2 = site_b['latitude'], site_b['longitude']
        
        # Convert coordinates if needed
        if isinstance(lat1, str) or isinstance(lon1, str):
            lat1, lon1 = convert_dms_to_decimal(lat1, lon1)
        if isinstance(lat2, str) or isinstance(lon2, str):
            lat2, lon2 = convert_dms_to_decimal(lat2, lon2)
            
        # Get elevations
        elev1 = float(site_a['elevation_ft'])
        elev2 = float(site_b['elevation_ft'])
        
        # Get antenna heights
        ant1 = float(site_a['antenna_cl_ft'])
        ant2 = float(site_b['antenna_cl_ft'])
        
        # Calculate total heights
        height1 = elev1 + ant1
        height2 = elev2 + ant2
        
        # Calculate distance in meters
        R = 6371000  # Earth radius in meters
        lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
        lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
        
        dlon = lon2_rad - lon1_rad
        dlat = lat2_rad - lat1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        distance_m = R * c
        logger.debug(f"Distance between sites: {distance_m:.2f} meters")
        
        # Generate points along the path
        points = []
        for i in range(num_points + 1):
            # Calculate position along the path (0 to 1)
            t = i / num_points
            
            # Interpolate position
            lat = lat1 + t * (lat2 - lat1)
            lon = lon1 + t * (lon2 - lon1)
            
            # Interpolate elevation (accounting for Earth curvature)
            # Simple linear interpolation for now
            elevation = height1 + t * (height2 - height1)
            
            # Calculate Fresnel zone radius at this point
            # Formula: r = 17.3 * sqrt(d1 * d2 / (frequency * D))
            # where d1 and d2 are distances from the endpoints, D is total distance
            d1 = t * distance_m
            d2 = (1 - t) * distance_m
            
            radius_m = 17.3 * math.sqrt((d1 * d2) / (frequency_ghz * distance_m))
            
            # Convert radius to feet
            radius_ft = radius_m * 3.28084
            
            points.append((lat, lon, elevation, radius_ft))
            
        return points
        
    except Exception as e:
        logger.error(f"Error generating Fresnel zone: {e}", exc_info=True)
        return []
