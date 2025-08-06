"""
Obstruction analysis module for the LOS application.
Handles distance and clearance calculations for obstructions.
"""

import math
import logging
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate the great circle distance between two points in miles"""
    # Convert decimal degrees to radians
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 3956  # Radius of earth in miles
    
    return c * r

def calculate_perpendicular_distance(point, line_start, line_end):
    """Calculate the perpendicular distance from a point to a line"""
    # Convert to radians
    lat1, lon1 = math.radians(line_start[0]), math.radians(line_start[1])
    lat2, lon2 = math.radians(line_end[0]), math.radians(line_end[1])
    lat3, lon3 = math.radians(point[0]), math.radians(point[1])
    
    # Calculate the bearing from start to end
    bearing = math.atan2(
        math.sin(lon2-lon1) * math.cos(lat2),
        math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(lon2-lon1)
    )
    
    # Calculate the distance from start to point
    dlon = lon3 - lon1
    dlat = lat3 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat3) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    distance = c * 3956  # Miles
    
    # Calculate the bearing from start to point
    bearing2 = math.atan2(
        math.sin(lon3-lon1) * math.cos(lat3),
        math.cos(lat1) * math.sin(lat3) - math.sin(lat1) * math.cos(lat3) * math.cos(lon3-lon1)
    )
    
    # Calculate the angle between the two bearings
    angle = bearing - bearing2
    
    # Calculate the perpendicular distance
    return abs(distance * math.sin(angle))

def calculate_clearance(turbine_height, turbine_distance, path_length, site_a_height, site_b_height):
    """Calculate the clearance between a turbine and the microwave path"""
    # Calculate the height of the path at the turbine's distance
    path_height_ratio = turbine_distance / path_length
    path_height = site_a_height + (site_b_height - site_a_height) * path_height_ratio
    
    # Calculate clearance
    clearance = path_height - turbine_height
    
    return clearance

def calculate_fresnel_zone_radius(frequency_ghz, distance_miles, path_length_miles):
    """Calculate the radius of the first Fresnel zone at a given distance"""
    # Convert to meters
    distance_meters = distance_miles * 1609.34
    path_length_meters = path_length_miles * 1609.34
    
    # Calculate the radius
    d1 = distance_meters
    d2 = path_length_meters - distance_meters
    wavelength = 0.3 / frequency_ghz  # Wavelength in meters
    
    radius = math.sqrt((wavelength * d1 * d2) / (d1 + d2))
    
    # Convert back to feet
    return radius * 3.28084

def calculate_earth_curvature_correction(distance_miles, path_length_miles):
    """Calculate the earth curvature correction at a given distance"""
    # Earth radius in miles
    earth_radius = 3956
    
    # Calculate the correction
    k = 1.33  # Refraction coefficient (4/3 earth)
    correction_miles = (distance_miles * (path_length_miles - distance_miles)) / (2 * k * earth_radius)
    
    # Convert to feet
    return correction_miles * 5280

def find_closest_obstruction(obstructions, site_a, site_b):
    """Find the closest obstruction to the path"""
    if not obstructions:
        return None
        
    closest = None
    min_distance = float('inf')
    
    for obstruction in obstructions:
        # Get coordinates
        lat = obstruction.get('latitude') or obstruction.get('ylat')
        lon = obstruction.get('longitude') or obstruction.get('xlong')
        
        if not lat or not lon:
            continue
            
        # Calculate perpendicular distance
        distance = calculate_perpendicular_distance(
            (lat, lon),
            (site_a['adjusted_latitude'], site_a['adjusted_longitude']),
            (site_b['adjusted_latitude'], site_b['adjusted_longitude'])
        )
        
        if distance < min_distance:
            min_distance = distance
            closest = obstruction
            closest['distance_to_path'] = distance
    
    return closest

def analyze_obstruction(obstruction, site_a, site_b, frequency_ghz):
    """Analyze an obstruction for clearance and interference"""
    if not obstruction:
        return None
        
    try:
        # Get coordinates
        lat = obstruction.get('latitude') or obstruction.get('ylat')
        lon = obstruction.get('longitude') or obstruction.get('xlong')
        
        if not lat or not lon:
            return None
            
        # Calculate path length
        path_length = calculate_distance(
            site_a['adjusted_latitude'], site_a['adjusted_longitude'],
            site_b['adjusted_latitude'], site_b['adjusted_longitude']
        )
        
        # Calculate distance from site A along the path
        distance_from_a = calculate_distance(
            site_a['adjusted_latitude'], site_a['adjusted_longitude'],
            lat, lon
        )
        
        # Calculate perpendicular distance
        perp_distance = calculate_perpendicular_distance(
            (lat, lon),
            (site_a['adjusted_latitude'], site_a['adjusted_longitude']),
            (site_b['adjusted_latitude'], site_b['adjusted_longitude'])
        )
        
        # Calculate distance along the path
        distance_along_path = math.sqrt(distance_from_a**2 - perp_distance**2)
        
        # Get heights
        site_a_height = site_a['elevation_ft'] + site_a['antenna_cl_ft']
        site_b_height = site_b['elevation_ft'] + site_b['antenna_cl_ft']
        
        # Get obstruction height
        obstruction_height = 0
        if 'total_height_m' in obstruction:
            obstruction_height = obstruction['total_height_m'] * 3.28084  # Convert to feet
        elif 't_ttlh' in obstruction:
            obstruction_height = obstruction['t_ttlh'] * 3.28084  # Convert to feet
        
        # Calculate path height at obstruction
        path_height_ratio = distance_along_path / path_length
        path_height = site_a_height + (site_b_height - site_a_height) * path_height_ratio
        
        # Calculate earth curvature correction
        earth_curve = calculate_earth_curvature_correction(distance_along_path, path_length)
        
        # Calculate Fresnel zone radius
        fresnel_radius = calculate_fresnel_zone_radius(frequency_ghz, distance_along_path, path_length)
        
        # Calculate clearances
        straight_clearance = path_height - obstruction_height
        earth_adjusted_clearance = straight_clearance - earth_curve
        fresnel_adjusted_clearance = earth_adjusted_clearance - fresnel_radius
        
        # Prepare result
        result = {
            'obstruction_id': obstruction.get('id') or obstruction.get('case_id'),
            'distance_to_path_miles': perp_distance,
            'distance_to_path_feet': perp_distance * 5280,
            'distance_along_path_miles': distance_along_path,
            'distance_along_path_feet': distance_along_path * 5280,
            'path_height_feet': path_height,
            'obstruction_height_feet': obstruction_height,
            'earth_curve_feet': earth_curve,
            'fresnel_radius_feet': fresnel_radius,
            'straight_clearance_feet': straight_clearance,
            'earth_adjusted_clearance_feet': earth_adjusted_clearance,
            'fresnel_adjusted_clearance_feet': fresnel_adjusted_clearance,
            'has_clearance': fresnel_adjusted_clearance > 0
        }
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing obstruction: {str(e)}", exc_info=True)
        return None

def format_distance(distance_miles):
    """Format distance in miles, feet, and meters"""
    miles = distance_miles
    feet = distance_miles * 5280
    meters = distance_miles * 1609.34
    
    return f"{miles:.2f} miles ({feet:.2f} ft / {meters:.2f} m)"

def format_clearance(clearance_feet):
    """Format clearance in feet and meters"""
    feet = clearance_feet
    meters = clearance_feet / 3.28084
    
    return f"{feet:.2f} ft ({meters:.2f} m)"
