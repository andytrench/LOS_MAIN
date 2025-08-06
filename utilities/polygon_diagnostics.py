"""
Polygon Diagnostics Utility

This module provides diagnostic functions to verify polygon search area calculations
and help troubleshoot turbine search issues.
"""

import math
import json
import logging
from typing import List, Tuple, Dict, Any
from utilities.coordinates import convert_dms_to_decimal, calculate_distance_meters
from utilities.geometry import calculate_polygon_points

logger = logging.getLogger(__name__)

def diagnose_polygon_search_area(polygon_width_ft: float, site_a: Dict, site_b: Dict) -> Dict[str, Any]:
    """
    Diagnose and verify polygon search area calculations.
    
    Args:
        polygon_width_ft: Polygon width in feet
        site_a: Site A data dictionary
        site_b: Site B data dictionary
        
    Returns:
        Dict containing diagnostic information
    """
    try:
        # Convert coordinates to decimal
        lat_a, lon_a = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
        lat_b, lon_b = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
        
        # Calculate polygon points
        polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), polygon_width_ft)
        
        # Calculate path length
        path_length_meters = calculate_distance_meters((lat_a, lon_a), (lat_b, lon_b))
        path_length_ft = path_length_meters * 3.28084
        
        # Calculate polygon area (approximate)
        polygon_area_sq_ft = polygon_width_ft * path_length_ft
        
        # Calculate expected distances from centerline
        expected_distance_from_centerline_ft = polygon_width_ft / 2
        
        # Analyze polygon bounds
        lats = [p[0] for p in polygon_points]
        lons = [p[1] for p in polygon_points]
        
        bounds = {
            'min_lat': min(lats),
            'max_lat': max(lats),
            'min_lon': min(lons),
            'max_lon': max(lons)
        }
        
        # Calculate actual polygon dimensions for verification
        # Distance between left and right sides at start point
        start_left = polygon_points[0]
        start_right = polygon_points[3]
        actual_width_start_m = calculate_distance_meters(
            (start_left[0], start_left[1]), 
            (start_right[0], start_right[1])
        )
        actual_width_start_ft = actual_width_start_m * 3.28084
        
        # Distance between left and right sides at end point
        end_left = polygon_points[1]
        end_right = polygon_points[2]
        actual_width_end_m = calculate_distance_meters(
            (end_left[0], end_left[1]), 
            (end_right[0], end_right[1])
        )
        actual_width_end_ft = actual_width_end_m * 3.28084
        
        diagnostics = {
            'input_parameters': {
                'polygon_width_ft': polygon_width_ft,
                'site_a_coords': (lat_a, lon_a),
                'site_b_coords': (lat_b, lon_b)
            },
            'polygon_geometry': {
                'polygon_points': polygon_points,
                'num_points': len(polygon_points),
                'bounds': bounds
            },
            'calculated_dimensions': {
                'path_length_ft': path_length_ft,
                'expected_distance_from_centerline_ft': expected_distance_from_centerline_ft,
                'actual_width_start_ft': actual_width_start_ft,
                'actual_width_end_ft': actual_width_end_ft,
                'polygon_area_sq_ft': polygon_area_sq_ft
            },
            'verification': {
                'width_matches_input': abs(actual_width_start_ft - polygon_width_ft) < 10,  # Within 10ft tolerance
                'consistent_width': abs(actual_width_start_ft - actual_width_end_ft) < 10,
                'width_tolerance_ft': abs(actual_width_start_ft - polygon_width_ft)
            }
        }
        
        logger.info(f"Polygon diagnostics completed for {polygon_width_ft}ft corridor")
        return diagnostics
        
    except Exception as e:
        logger.error(f"Error in polygon diagnostics: {e}", exc_info=True)
        return {'error': str(e)}

def verify_turbine_in_polygon(turbine_lat: float, turbine_lon: float, 
                             polygon_points: List[Tuple[float, float]]) -> Dict[str, Any]:
    """
    Verify if a turbine is actually within the search polygon.
    
    Args:
        turbine_lat: Turbine latitude
        turbine_lon: Turbine longitude
        polygon_points: List of polygon coordinate tuples
        
    Returns:
        Dict containing verification results
    """
    try:
        from shapely.geometry import Point, Polygon
        
        # Create point and polygon
        turbine_point = Point(turbine_lon, turbine_lat)  # Note: lon, lat order for Shapely
        search_polygon = Polygon([(lon, lat) for lat, lon in polygon_points])
        
        # Check if point is in polygon
        is_in_polygon = search_polygon.contains(turbine_point)
        
        # Calculate distance to polygon boundary
        distance_to_boundary = search_polygon.distance(turbine_point)
        distance_to_boundary_ft = distance_to_boundary * 111320 * 3.28084  # Rough conversion to feet
        
        return {
            'turbine_coords': (turbine_lat, turbine_lon),
            'is_in_polygon': is_in_polygon,
            'distance_to_boundary_ft': distance_to_boundary_ft,
            'polygon_bounds': search_polygon.bounds
        }
        
    except Exception as e:
        logger.error(f"Error verifying turbine in polygon: {e}", exc_info=True)
        return {'error': str(e)}

def calculate_turbine_distance_from_path(turbine_lat: float, turbine_lon: float,
                                       path_start: Tuple[float, float], 
                                       path_end: Tuple[float, float]) -> float:
    """
    Calculate the perpendicular distance from a turbine to the path centerline.
    
    Args:
        turbine_lat: Turbine latitude
        turbine_lon: Turbine longitude
        path_start: (lat, lon) of path start
        path_end: (lat, lon) of path end
        
    Returns:
        Distance in feet from turbine to path centerline
    """
    try:
        # Convert coordinates to a local coordinate system for more accurate calculations
        # Use the start point as origin
        start_lat, start_lon = path_start
        end_lat, end_lon = path_end
        
        # Calculate path vector (in degrees, approximate for small distances)
        path_lat_diff = end_lat - start_lat
        path_lon_diff = end_lon - start_lon
        
        # Calculate turbine vector from path start
        turbine_lat_diff = turbine_lat - start_lat
        turbine_lon_diff = turbine_lon - start_lon
        
        # Calculate path length squared
        path_length_sq = path_lat_diff**2 + path_lon_diff**2
        
        if path_length_sq == 0:
            # Path has zero length, return distance to start point
            distance_m = calculate_distance_meters((turbine_lat, turbine_lon), (start_lat, start_lon))
            return distance_m * 3.28084
        
        # Calculate projection of turbine vector onto path vector
        projection = (turbine_lat_diff * path_lat_diff + turbine_lon_diff * path_lon_diff) / path_length_sq
        
        # Calculate closest point on path
        closest_lat = start_lat + projection * path_lat_diff
        closest_lon = start_lon + projection * path_lon_diff
        
        # Calculate distance from turbine to closest point on path
        distance_m = calculate_distance_meters((turbine_lat, turbine_lon), (closest_lat, closest_lon))
        distance_ft = distance_m * 3.28084
        
        return distance_ft
        
    except Exception as e:
        logger.error(f"Error calculating turbine distance from path: {e}", exc_info=True)
        return float('inf')

def generate_diagnostic_report(polygon_width_ft: float = 2000) -> str:
    """
    Generate a diagnostic report for polygon search area calculations.
    
    Args:
        polygon_width_ft: Polygon width to test
        
    Returns:
        Formatted diagnostic report string
    """
    try:
        # Load current tower parameters
        try:
            with open('tower_parameters.json', 'r') as f:
                tower_data = json.load(f)
                site_a = tower_data['site_A']
                site_b = tower_data['site_B']
        except:
            return "Error: Could not load tower_parameters.json. Please load a project first."
        
        # Run diagnostics
        diagnostics = diagnose_polygon_search_area(polygon_width_ft, site_a, site_b)
        
        if 'error' in diagnostics:
            return f"Error in diagnostics: {diagnostics['error']}"
        
        # Format report
        report = f"""
=== POLYGON SEARCH AREA DIAGNOSTIC REPORT ===

INPUT PARAMETERS:
- Polygon Width Setting: {polygon_width_ft} ft
- Site A: {diagnostics['input_parameters']['site_a_coords']}
- Site B: {diagnostics['input_parameters']['site_b_coords']}

CALCULATED DIMENSIONS:
- Path Length: {diagnostics['calculated_dimensions']['path_length_ft']:.1f} ft
- Expected Distance from Centerline: ±{diagnostics['calculated_dimensions']['expected_distance_from_centerline_ft']:.1f} ft
- Actual Corridor Width (Start): {diagnostics['calculated_dimensions']['actual_width_start_ft']:.1f} ft
- Actual Corridor Width (End): {diagnostics['calculated_dimensions']['actual_width_end_ft']:.1f} ft
- Polygon Area: {diagnostics['calculated_dimensions']['polygon_area_sq_ft']:.0f} sq ft

VERIFICATION:
- Width Matches Input: {'✅ PASS' if diagnostics['verification']['width_matches_input'] else '❌ FAIL'}
- Consistent Width: {'✅ PASS' if diagnostics['verification']['consistent_width'] else '❌ FAIL'}
- Width Tolerance: {diagnostics['verification']['width_tolerance_ft']:.1f} ft

POLYGON BOUNDS:
- Latitude Range: {diagnostics['polygon_geometry']['bounds']['min_lat']:.6f} to {diagnostics['polygon_geometry']['bounds']['max_lat']:.6f}
- Longitude Range: {diagnostics['polygon_geometry']['bounds']['min_lon']:.6f} to {diagnostics['polygon_geometry']['bounds']['max_lon']:.6f}

INTERPRETATION:
- Setting polygon width to {polygon_width_ft} ft creates a corridor that is {polygon_width_ft} ft total width
- Turbines within ±{polygon_width_ft/2:.0f} ft of the path centerline should be included
- Turbines beyond ±{polygon_width_ft/2:.0f} ft of the path centerline should be excluded

=== END DIAGNOSTIC REPORT ===
        """
        
        return report.strip()
        
    except Exception as e:
        logger.error(f"Error generating diagnostic report: {e}", exc_info=True)
        return f"Error generating diagnostic report: {str(e)}" 