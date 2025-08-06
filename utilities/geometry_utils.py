import math
import logging

# Configure logging
logger = logging.getLogger(__name__)

def calculate_polygon_points(start, end, width_ft, extension_ft=0):
    """
    Calculate a polygon that represents a corridor of specified width
    between start and end points, with optional extension beyond the endpoints.
    
    Args:
        start: Tuple of (lat, lon) for start point
        end: Tuple of (lat, lon) for end point
        width_ft: Width of corridor in feet
        extension_ft: Optional extension beyond endpoints in feet
        
    Returns:
        List of (lat, lon) tuples representing the polygon vertices
    """
    logger.info(f"Calculating polygon points: start={start}, end={end}, width={width_ft}ft")

    def haversine_distance(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)

        a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
            math.cos(phi1) * math.cos(phi2) * \
            math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

    def destination_point(lat, lon, bearing, distance):
        """
        Calculate destination point given start point, bearing and distance
        """
        R = 6371000  # Earth radius in meters
        lat1 = math.radians(lat)
        lon1 = math.radians(lon)
        
        angular_distance = distance / R
        
        lat2 = math.asin(math.sin(lat1) * math.cos(angular_distance) + 
                         math.cos(lat1) * math.sin(angular_distance) * math.cos(bearing))
        
        lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(angular_distance) * math.cos(lat1),
                                 math.cos(angular_distance) - math.sin(lat1) * math.sin(lat2))
        
        return math.degrees(lat2), math.degrees(lon2)

    # Convert width from feet to meters
    width_m = width_ft * 0.3048
    extension_m = extension_ft * 0.3048
    
    # Calculate bearing from start to end
    lat1, lon1 = math.radians(start[0]), math.radians(start[1])
    lat2, lon2 = math.radians(end[0]), math.radians(end[1])
    
    y = math.sin(lon2 - lon1) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2 - lon1)
    path_bearing = math.atan2(y, x)
    
    # Calculate perpendicular bearings
    perpendicular_bearing1 = path_bearing + math.pi/2
    perpendicular_bearing2 = path_bearing - math.pi/2

    # Calculate the four corners of the rectangle
    start1 = destination_point(start[0], start[1], perpendicular_bearing1, width_m/2)
    start2 = destination_point(start[0], start[1], perpendicular_bearing2, width_m/2)
    end1 = destination_point(end[0], end[1], perpendicular_bearing1, width_m/2)
    end2 = destination_point(end[0], end[1], perpendicular_bearing2, width_m/2)

    # Calculate the extended points
    extended_start = destination_point(start[0], start[1], path_bearing + math.pi, extension_m)
    extended_end = destination_point(end[0], end[1], path_bearing, extension_m)
    
    # Calculate the extended corners if extension is specified
    if extension_m > 0:
        ext_start1 = destination_point(extended_start[0], extended_start[1], perpendicular_bearing1, width_m/2)
        ext_start2 = destination_point(extended_start[0], extended_start[1], perpendicular_bearing2, width_m/2)
        ext_end1 = destination_point(extended_end[0], extended_end[1], perpendicular_bearing1, width_m/2)
        ext_end2 = destination_point(extended_end[0], extended_end[1], perpendicular_bearing2, width_m/2)
        
        # Return polygon with extensions
        return [ext_start1, ext_start2, ext_end2, ext_end1, ext_start1]
    else:
        # Return basic rectangle
        return [start1, start2, end2, end1, start1]

def get_search_ring_points(center, radius_ft):
    """
    Calculate points for a circular search ring around a center point.
    
    Args:
        center: Tuple of (lat, lon) for center point
        radius_ft: Radius in feet
        
    Returns:
        List of (lat, lon) tuples representing the circle
    """
    # Convert radius from feet to meters
    radius_m = radius_ft * 0.3048
    
    # Earth's radius in meters
    earth_radius = 6371000
    
    # Angular radius
    angular_radius = radius_m / earth_radius
    
    # Convert center to radians
    lat1 = math.radians(center[0])
    lon1 = math.radians(center[1])
    
    # Generate points around the circle
    points = []
    num_points = 36  # Number of points to generate (10-degree intervals)
    
    for i in range(num_points + 1):  # +1 to close the circle
        bearing = math.radians(i * (360 / num_points))
        
        # Calculate point at given bearing and distance
        lat2 = math.asin(math.sin(lat1) * math.cos(angular_radius) + 
                         math.cos(lat1) * math.sin(angular_radius) * math.cos(bearing))
        
        lon2 = lon1 + math.atan2(math.sin(bearing) * math.sin(angular_radius) * math.cos(lat1),
                                 math.cos(angular_radius) - math.sin(lat1) * math.sin(lat2))
        
        # Convert back to degrees and add to points list
        points.append((math.degrees(lat2), math.degrees(lon2)))
    
    return points

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    
    Args:
        lat1, lon1: Coordinates of first point in decimal degrees
        lat2, lon2: Coordinates of second point in decimal degrees
        
    Returns:
        Distance in meters
    """
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    
    # Earth radius in meters
    r = 6371000
    
    # Calculate distance
    distance = c * r
    return distance

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Calculate initial bearing between two points.
    
    Args:
        lat1, lon1: Coordinates of first point in decimal degrees
        lat2, lon2: Coordinates of second point in decimal degrees
        
    Returns:
        Bearing in degrees (0-360)
    """
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
    
    return bearing_deg

def destination_point(lat, lon, bearing_deg, distance_m):
    """
    Calculate destination point given starting point, bearing and distance.
    
    Args:
        lat, lon: Starting point coordinates in decimal degrees
        bearing_deg: Bearing in degrees
        distance_m: Distance in meters
        
    Returns:
        Tuple of (lat, lon) coordinates of destination point
    """
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
    
    return lat2, lon2
