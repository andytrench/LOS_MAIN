"""
Turbine Search Diagnostics

This module provides diagnostic tools to understand why turbines might be excluded
from search results and help troubleshoot polygon filtering issues.
"""

import json
import logging
import math
from typing import List, Tuple, Dict, Any
from utilities.coordinates import convert_dms_to_decimal, calculate_distance_meters
from utilities.geometry import calculate_polygon_points

logger = logging.getLogger(__name__)

def diagnose_turbine_search(polygon_width_ft: float = 2000) -> Dict[str, Any]:
    """
    Diagnose turbine search results by analyzing all turbines in the bounding box
    and showing why they were included or excluded.
    
    Args:
        polygon_width_ft: Polygon width in feet for the search area
        
    Returns:
        Dict containing diagnostic information
    """
    try:
        # Load current tower parameters
        try:
            with open('tower_parameters.json', 'r') as f:
                tower_data = json.load(f)
                site_a = tower_data['site_A']
                site_b = tower_data['site_B']
        except:
            return {"error": "Could not load tower_parameters.json. Please load a project first."}
        
        # Convert coordinates
        lat_a, lon_a = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
        lat_b, lon_b = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
        
        # Calculate polygon
        polygon_points = calculate_polygon_points((lat_a, lon_a), (lat_b, lon_b), polygon_width_ft)
        
        # Calculate bounding box with padding (same as turbine processor)
        lats = [point[0] for point in polygon_points]
        lons = [point[1] for point in polygon_points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        
        padding = 0.05  # Same as turbine processor
        min_lat -= padding
        max_lat += padding
        min_lon -= padding
        max_lon += padding
        
        # Load turbines from GeoJSON file (same as turbine processor fallback)
        geojson_file = "turbine_db/uswtdbGeoJSON/uswtdb_V8_0_20250225.geojson"
        
        try:
            with open(geojson_file, 'r') as f:
                geojson_data = json.load(f)
            
            features = geojson_data.get('features', [])
            logger.info(f"Loaded {len(features)} total turbines from GeoJSON")
            
            # Convert and filter by bounding box
            turbines_in_bbox = []
            for feature in features:
                coords = feature.get('geometry', {}).get('coordinates', [])
                properties = feature.get('properties', {})
                
                if coords and len(coords) >= 2:
                    lat, lon = coords[1], coords[0]  # GeoJSON is [lon, lat]
                    
                    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                        turbine = {
                            'case_id': properties.get('case_id'),
                            'ylat': lat,
                            'xlong': lon,
                            't_state': properties.get('t_state'),
                            'p_name': properties.get('p_name'),
                            't_ttlh': properties.get('t_ttlh'),
                            't_rd': properties.get('t_rd')
                        }
                        turbines_in_bbox.append(turbine)
            
            logger.info(f"Found {len(turbines_in_bbox)} turbines in bounding box")
            
            # Analyze each turbine
            analysis_results = []
            turbines_in_polygon = 0
            
            for turbine in turbines_in_bbox:
                # Check if in polygon
                point = (turbine['ylat'], turbine['xlong'])
                in_polygon = point_in_polygon(point, polygon_points)
                
                # Calculate distance from path centerline
                distance_from_path = calculate_distance_from_path_centerline(
                    turbine['ylat'], turbine['xlong'], 
                    (lat_a, lon_a), (lat_b, lon_b)
                )
                
                if in_polygon:
                    turbines_in_polygon += 1
                
                analysis_results.append({
                    'case_id': turbine.get('case_id'),
                    'location': (turbine['ylat'], turbine['xlong']),
                    'state': turbine.get('t_state'),
                    'project': turbine.get('p_name'),
                    'height_m': turbine.get('t_ttlh'),
                    'in_polygon': in_polygon,
                    'distance_from_path_ft': distance_from_path,
                    'distance_from_path_reasonable': distance_from_path <= (polygon_width_ft + 500)  # Allow some buffer
                })
            
            # Sort by distance from path
            analysis_results.sort(key=lambda x: x['distance_from_path_ft'] if x['distance_from_path_ft'] is not None else float('inf'))
            
            # Find the closest turbines that should be in the polygon
            # With new interpretation: polygon_width_ft is the distance from centerline in each direction
            expected_turbines = [
                t for t in analysis_results 
                if t['distance_from_path_ft'] is not None and t['distance_from_path_ft'] <= polygon_width_ft
            ]
            
            return {
                'search_parameters': {
                    'polygon_width_ft': polygon_width_ft,
                    'path_endpoints': [(lat_a, lon_a), (lat_b, lon_b)],
                    'bounding_box': {
                        'min_lat': min_lat, 'max_lat': max_lat,
                        'min_lon': min_lon, 'max_lon': max_lon
                    }
                },
                'turbine_counts': {
                    'total_in_bbox': len(turbines_in_bbox),
                    'found_in_polygon': turbines_in_polygon,
                    'expected_in_polygon': len(expected_turbines)
                },
                'closest_turbines': analysis_results[:10],  # Show 10 closest
                'expected_but_missing': [
                    t for t in expected_turbines if not t['in_polygon']
                ],
                'polygon_points': polygon_points
            }
            
        except Exception as e:
            logger.error(f"Error loading GeoJSON file: {e}")
            return {"error": f"Could not load turbine data: {str(e)}"}
        
    except Exception as e:
        logger.error(f"Error in turbine search diagnosis: {e}", exc_info=True)
        return {"error": str(e)}

def point_in_polygon(point, polygon):
    """Check if a point is inside a polygon using ray casting algorithm (same as turbine processor)"""
    x, y = point
    n = len(polygon)
    inside = False

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

def generate_turbine_diagnostic_report() -> str:
    """Generate a detailed report of turbine search diagnostics"""
    try:
        # Run the diagnosis
        results = diagnose_turbine_search(2000)
        
        if 'error' in results:
            return f"Error: {results['error']}"
        
        # Format the report
        report = f"""
=== TURBINE SEARCH DIAGNOSTIC REPORT ===

SEARCH PARAMETERS:
- Search Distance from Centerline: ±{results['search_parameters']['polygon_width_ft']} ft
- Total Polygon Width: {results['search_parameters']['polygon_width_ft']*2} ft
- Path: {results['search_parameters']['path_endpoints'][0]} to {results['search_parameters']['path_endpoints'][1]}

TURBINE COUNTS:
- Total in Bounding Box: {results['turbine_counts']['total_in_bbox']}
- Found in Polygon: {results['turbine_counts']['found_in_polygon']}
- Expected in Polygon: {results['turbine_counts']['expected_in_polygon']}

ANALYSIS: {'✅ CORRECT' if results['turbine_counts']['found_in_polygon'] == results['turbine_counts']['expected_in_polygon'] else '❌ MISMATCH'}

CLOSEST TURBINES (by distance from path centerline):"""
        
        for i, turbine in enumerate(results['closest_turbines'], 1):
            in_poly_symbol = "✅ IN" if turbine['in_polygon'] else "❌ OUT"
            dist = turbine['distance_from_path_ft']
            dist_str = f"{dist:.1f}ft" if dist is not None else "N/A"
            
            report += f"""
{i:2d}. ID: {turbine['case_id']} | Distance: {dist_str} | {in_poly_symbol} | Location: ({turbine['location'][0]:.6f}, {turbine['location'][1]:.6f})"""
        
        if results['expected_but_missing']:
            report += f"""

❌ MISSING TURBINES (should be in polygon but aren't):"""
            for turbine in results['expected_but_missing']:
                dist = turbine['distance_from_path_ft']
                dist_str = f"{dist:.1f}ft" if dist is not None else "N/A"
                report += f"""
   ID: {turbine['case_id']} | Distance: {dist_str} | Location: ({turbine['location'][0]:.6f}, {turbine['location'][1]:.6f})"""
        
        report += f"""

=== POSSIBLE ISSUES ===
1. If 'Expected' > 'Found': Polygon algorithm may be incorrect
2. If distances look right but turbines are excluded: Check point-in-polygon logic
3. If distances are wrong: Check coordinate system or distance calculation

=== END DIAGNOSTIC REPORT ===
        """
        
        return report.strip()
        
    except Exception as e:
        logger.error(f"Error generating turbine diagnostic report: {e}", exc_info=True)
        return f"Error generating report: {str(e)}" 