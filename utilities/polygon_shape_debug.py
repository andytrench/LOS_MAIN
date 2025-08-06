"""
Polygon Shape Debug Tool

This module helps debug polygon shape issues by providing detailed analysis
of polygon geometry and point-in-polygon calculations.
"""

import json
import logging
import math
from typing import List, Tuple, Dict, Any
from utilities.coordinates import convert_dms_to_decimal, calculate_distance_meters
from utilities.geometry import calculate_polygon_points

logger = logging.getLogger(__name__)

def analyze_polygon_shape() -> Dict[str, Any]:
    """
    Analyze the polygon shape to understand why certain points might be excluded.
    """
    try:
        # Load current tower parameters
        with open('tower_parameters.json', 'r') as f:
            tower_data = json.load(f)
            site_a = tower_data['site_A']
            site_b = tower_data['site_B']
        
        # Convert coordinates
        lat_a, lon_a = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
        lat_b, lon_b = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
        
        print(f"Path endpoints:")
        print(f"  Site A: ({lat_a:.6f}, {lon_a:.6f})")
        print(f"  Site B: ({lat_b:.6f}, {lon_b:.6f})")
        
        # Calculate polygon for 3000ft width
        polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), 3000)
        
        print(f"\nPolygon shape (3000ft width):")
        for i, point in enumerate(polygon_points):
            print(f"  Point {i+1}: ({point[0]:.6f}, {point[1]:.6f})")
        
        # Test the problematic turbine
        turbine_lat, turbine_lon = 43.420000, -84.481000  # Turbine 3045928
        
        print(f"\nTesting turbine 3045928:")
        print(f"  Location: ({turbine_lat:.6f}, {turbine_lon:.6f})")
        
        # Check if it's in the polygon
        from utilities.turbine_diagnostics import point_in_polygon
        in_polygon = point_in_polygon((turbine_lat, turbine_lon), polygon_points)
        print(f"  In polygon: {in_polygon}")
        
        # Calculate distance from each polygon edge
        print(f"\nDistances from polygon edges:")
        for i in range(len(polygon_points)):
            p1 = polygon_points[i]
            p2 = polygon_points[(i + 1) % len(polygon_points)]
            
            # Calculate distance from turbine to edge
            edge_dist = point_to_line_distance(turbine_lat, turbine_lon, p1[0], p1[1], p2[0], p2[1])
            print(f"  Edge {i+1}-{i+2 if i+1 < len(polygon_points) else 1}: {edge_dist:.1f}ft")
        
        # Calculate distance from path centerline
        distance_from_center = calculate_distance_from_path_centerline(
            turbine_lat, turbine_lon, (lat_a, lon_a), (lat_b, lon_b)
        )
        print(f"  Distance from centerline: {distance_from_center:.1f}ft")
        
        # Test with manual rectangular bounds
        print(f"\nManual rectangular bounds check:")
        
        # Calculate path bearing
        lat_diff = lat_b - lat_a
        lon_diff = lon_b - lon_a
        bearing = math.atan2(lon_diff, lat_diff)
        
        # Perpendicular bearing (90 degrees)
        perp_bearing = bearing + math.pi/2
        
        # Calculate width in degrees (approximate)
        width_deg = (3000 * 0.3048) / 111111  # 3000ft to degrees
        
        # Calculate perpendicular offset
        offset_lat = width_deg * math.cos(perp_bearing) / 2
        offset_lon = width_deg * math.sin(perp_bearing) / 2
        
        # Create simple rectangular bounds
        min_offset_lat = min(-offset_lat, offset_lat)
        max_offset_lat = max(-offset_lat, offset_lat)
        min_offset_lon = min(-offset_lon, offset_lon)
        max_offset_lon = max(-offset_lon, offset_lon)
        
        # Check if turbine is within simple rectangular bounds around the path
        path_min_lat = min(lat_a, lat_b) + min_offset_lat
        path_max_lat = max(lat_a, lat_b) + max_offset_lat
        path_min_lon = min(lon_a, lon_b) + min_offset_lon
        path_max_lon = max(lon_a, lon_b) + max_offset_lon
        
        in_simple_bounds = (path_min_lat <= turbine_lat <= path_max_lat and 
                           path_min_lon <= turbine_lon <= path_max_lon)
        
        print(f"  Simple rectangular bounds: ({path_min_lat:.6f}, {path_min_lon:.6f}) to ({path_max_lat:.6f}, {path_max_lon:.6f})")
        print(f"  In simple bounds: {in_simple_bounds}")
        
        return {
            'polygon_points': polygon_points,
            'turbine_location': (turbine_lat, turbine_lon),
            'in_polygon': in_polygon,
            'distance_from_center': distance_from_center
        }
        
    except Exception as e:
        logger.error(f"Error analyzing polygon shape: {e}", exc_info=True)
        return {"error": str(e)}

def point_to_line_distance(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    """
    Calculate the shortest distance from a point to a line segment.
    """
    try:
        # Vector from line start to point
        A = px - x1
        B = py - y1
        
        # Vector of the line
        C = x2 - x1
        D = y2 - y1
        
        # Calculate dot product and line length squared
        dot = A * C + B * D
        len_sq = C * C + D * D
        
        if len_sq == 0:
            # Line is actually a point
            distance_m = calculate_distance_meters((px, py), (x1, y1))
            return distance_m * 3.28084
        
        # Calculate parameter t
        param = dot / len_sq
        
        # Find the closest point on the line
        if param < 0:
            # Closest to start point
            xx, yy = x1, y1
        elif param > 1:
            # Closest to end point
            xx, yy = x2, y2
        else:
            # On the line segment
            xx = x1 + param * C
            yy = y1 + param * D
        
        # Calculate distance
        distance_m = calculate_distance_meters((px, py), (xx, yy))
        return distance_m * 3.28084
        
    except Exception as e:
        logger.error(f"Error calculating point to line distance: {e}")
        return float('inf')

def calculate_distance_from_path_centerline(turbine_lat: float, turbine_lon: float,
                                          path_start: Tuple[float, float], 
                                          path_end: Tuple[float, float]) -> float:
    """Calculate perpendicular distance from turbine to path centerline"""
    try:
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
        logger.error(f"Error calculating distance from path centerline: {e}")
        return None 