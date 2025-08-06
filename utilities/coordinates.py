import re
import math
import logging
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def parse_dms(dms_str):
    """Parse DMS coordinate string to decimal degrees"""
    try:
        # Handle various DMS formats
        dms_str = dms_str.strip().upper()

        # Extract direction
        direction = 'N' if 'N' in dms_str else 'S' if 'S' in dms_str else 'E' if 'E' in dms_str else 'W'

        # Remove direction and split remaining parts
        parts = dms_str.replace(direction, '').strip().split('-')

        if len(parts) != 3:
            raise ValueError(f"Invalid DMS format: {dms_str}")

        degrees = float(parts[0])
        minutes = float(parts[1])
        seconds = float(parts[2])

        decimal = degrees + minutes/60 + seconds/3600
        if direction in ['S', 'W']:
            decimal = -decimal

        logger.debug(f"Converted DMS '{dms_str}' to decimal degrees: {decimal}")
        return decimal

    except Exception as e:
        logger.error(f"Error parsing DMS coordinate '{dms_str}': {e}")
        raise

def convert_dms_to_decimal(lat_dms, lon_dms):
    """Convert DMS coordinates to decimal degrees, or pass through if already decimal"""
    try:
        # First, check if inputs are already decimal numbers
        if not isinstance(lat_dms, str) or (isinstance(lat_dms, str) and lat_dms.replace('.', '', 1).replace('-', '', 1).isdigit()):
            lat = float(lat_dms) if isinstance(lat_dms, str) else lat_dms
        else:
            # Try to parse as DMS format
            lat = parse_dms(lat_dms)

        if not isinstance(lon_dms, str) or (isinstance(lon_dms, str) and lon_dms.replace('.', '', 1).replace('-', '', 1).isdigit()):
            lon = float(lon_dms) if isinstance(lon_dms, str) else lon_dms
        else:
            # Try to parse as DMS format
            lon = parse_dms(lon_dms)

        return lat, lon
    except Exception as e:
        logger.error(f"Error converting coordinates: lat={lat_dms}, lon={lon_dms}, error={e}")
        raise ValueError(f"Invalid coordinate format. Lat: {lat_dms}, Lon: {lon_dms}")

def dms_to_decimal(dms_str):
    """Alternative DMS parser that handles different formats"""
    try:
        # Handle format like "40°26'46\"N"
        if '°' in dms_str:
            direction = dms_str[-1]
            dms = dms_str[:-1]  # Remove direction letter

            # Extract degrees, minutes, seconds
            parts = re.split('[°\'"]', dms)
            parts = [p for p in parts if p.strip()]  # Remove empty parts

            if len(parts) >= 3:
                degrees = float(parts[0])
                minutes = float(parts[1])
                seconds = float(parts[2])
            elif len(parts) == 2:
                degrees = float(parts[0])
                minutes = float(parts[1])
                seconds = 0
            else:
                degrees = float(parts[0])
                minutes = seconds = 0

            decimal = degrees + minutes/60 + seconds/3600
            if direction in ['S', 'W']:
                decimal = -decimal

            return decimal

        # If it's already a decimal number as string
        if dms_str.replace('.', '', 1).replace('-', '', 1).isdigit():
            return float(dms_str)

        # Fall back to the main parser
        return parse_dms(dms_str)

    except Exception as e:
        logger.error(f"Error in dms_to_decimal for '{dms_str}': {e}")
        # If all parsing fails, try to see if it's a simple float
        try:
            return float(dms_str)
        except:
            raise ValueError(f"Could not parse coordinate: {dms_str}")

def calculate_distance(coord1, coord2):
    """Calculate distance between two coordinates using Haversine formula

    Args:
        coord1: Tuple of (latitude, longitude) for first point
        coord2: Tuple of (latitude, longitude) for second point

    Returns:
        float: Distance in miles
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 3956  # Radius of earth in miles

    return c * r  # Return in miles

def calculate_distance_meters(coord1, coord2):
    """Calculate distance between two coordinates using Haversine formula

    Args:
        coord1: Tuple of (latitude, longitude) for first point
        coord2: Tuple of (latitude, longitude) for second point

    Returns:
        float: Distance in meters
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2

    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Radius of earth in kilometers

    return c * r * 1000  # Return in meters

def calculate_bearing(lat1, lon1, lat2, lon2):
    """Calculate bearing between two points"""
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])

    # Calculate bearing
    dlon = lon2 - lon1
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.atan2(y, x)

    # Convert to degrees
    bearing = math.degrees(bearing)
    bearing = (bearing + 360) % 360

    return bearing

def destination_point(lat, lon, bearing, distance_m):
    """Calculate destination point given start, bearing and distance"""
    # Convert to radians
    lat = math.radians(lat)
    lon = math.radians(lon)
    bearing = math.radians(bearing)

    # Earth radius in meters
    R = 6371000

    # Calculate destination point
    distance_rad = distance_m / R

    lat2 = math.asin(math.sin(lat) * math.cos(distance_rad) +
                     math.cos(lat) * math.sin(distance_rad) * math.cos(bearing))

    lon2 = lon + math.atan2(math.sin(bearing) * math.sin(distance_rad) * math.cos(lat),
                           math.cos(distance_rad) - math.sin(lat) * math.sin(lat2))

    # Convert back to degrees
    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return lat2, lon2