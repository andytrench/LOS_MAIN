#!/usr/bin/env python3
"""
Search for LIDAR files using KML polygon coordinates

This script extracts coordinates from the ML93170A_ML89035A_LidarPolygon.kml file
and searches for LIDAR data using both USGS and NOAA sources.
"""

import xml.etree.ElementTree as ET
import requests
import json
import sys
import os
from datetime import date
from typing import List, Tuple, Dict, Any

def parse_kml_polygon(kml_file: str) -> List[Tuple[float, float]]:
    """
    Parse KML file and extract polygon coordinates
    
    Args:
        kml_file: Path to KML file
        
    Returns:
        List of (lat, lon) coordinate tuples
    """
    try:
        tree = ET.parse(kml_file)
        root = tree.getroot()
        
        # Find coordinates element
        coords_elem = root.find('.//{http://www.opengis.net/kml/2.2}coordinates')
        if coords_elem is None:
            # Try without namespace
            coords_elem = root.find('.//coordinates')
        
        if coords_elem is None:
            raise ValueError("No coordinates found in KML file")
        
        coords_text = coords_elem.text.strip()
        print(f"Raw coordinates: {coords_text}")
        
        # Parse coordinates (format: lon,lat,elevation lon,lat,elevation ...)
        coord_pairs = coords_text.split()
        polygon_points = []
        
        for coord_pair in coord_pairs:
            parts = coord_pair.split(',')
            if len(parts) >= 2:
                lon = float(parts[0])
                lat = float(parts[1])
                polygon_points.append((lat, lon))  # Return as (lat, lon)
        
        print(f"Parsed {len(polygon_points)} polygon points:")
        for i, (lat, lon) in enumerate(polygon_points):
            print(f"  Point {i+1}: {lat:.6f}, {lon:.6f}")
        
        return polygon_points
        
    except Exception as e:
        print(f"Error parsing KML file: {e}")
        return []

def search_usgs_lidar(polygon_points: List[Tuple[float, float]], 
                     start_date: str = "2000-01-01", 
                     end_date: str = None) -> Dict[str, Any]:
    """
    Search USGS LIDAR data using polygon coordinates
    
    Args:
        polygon_points: List of (lat, lon) tuples
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with search results
    """
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    
    print(f"\n=== USGS LIDAR Search ===")
    print(f"Date range: {start_date} to {end_date}")
    
    # Format polygon for USGS API (lon lat, lon lat, ...)
    polygon_str = ",".join([f"{lon} {lat}" for lat, lon in polygon_points])
    print(f"Polygon string: {polygon_str}")
    
    base_url = "https://tnmaccess.nationalmap.gov/api/v1/products"
    
    params = {
        "polygon": polygon_str,
        "datasets": "Lidar Point Cloud (LPC)",
        "prodFormats": "LAZ",
        "outputFormat": "JSON",
        "dateType": "dateCreated",
        "start": start_date,
        "end": end_date,
        "maxResults": "50"
    }
    
    try:
        print("Making USGS API request...")
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        total_results = data.get('total', 0)
        items = data.get('items', [])
        
        print(f"Found {total_results} total USGS LIDAR files")
        print(f"Retrieved {len(items)} files in this batch")
        
        # Display sample results
        if items:
            print("\nSample USGS results:")
            for i, item in enumerate(items[:3]):  # Show first 3
                print(f"  {i+1}. {item.get('title', 'Unknown')}")
                print(f"     Size: {item.get('sizeInBytes', 'Unknown')} bytes")
                print(f"     URL: {item.get('downloadURL', 'No URL')}")
                if 'boundingBox' in item:
                    bbox = item['boundingBox']
                    print(f"     Bounds: {bbox.get('minY'):.4f},{bbox.get('minX'):.4f} to {bbox.get('maxY'):.4f},{bbox.get('maxX'):.4f}")
                print()
        
        return data
        
    except Exception as e:
        print(f"Error searching USGS LIDAR: {e}")
        return {"items": [], "total": 0, "error": str(e)}

def search_noaa_lidar(polygon_points: List[Tuple[float, float]], 
                     start_date: str = "2000-01-01", 
                     end_date: str = None) -> Dict[str, Any]:
    """
    Search NOAA LIDAR data using polygon coordinates
    
    Args:
        polygon_points: List of (lat, lon) tuples
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        
    Returns:
        Dictionary with search results
    """
    if end_date is None:
        end_date = date.today().strftime("%Y-%m-%d")
    
    print(f"\n=== NOAA LIDAR Search ===")
    print(f"Date range: {start_date} to {end_date}")
    
    try:
        # Add the NOAA directory to Python path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'NOAA'))
        
        from noaa_index_search import search_noaa_index
        from noaa_index_db import database_exists
        
        # Check if NOAA database exists
        if not database_exists():
            print("NOAA index database not found!")
            print("To create the database, run:")
            print("  python NOAA/noaa_data_crawler.py --init --crawl-all")
            return {"items": [], "total": 0, "error": "NOAA database not found"}
        
        print("Searching NOAA index database...")
        
        # Convert start_date and end_date to date objects
        from datetime import datetime
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        
        # Search NOAA index (include all LIDAR-related data types)
        result = search_noaa_index(
            polygon_points=polygon_points,
            start_date=start_date_obj,
            end_date=end_date_obj,
            data_type=None,  # Accept all data types (lidar, topobathy, etc.)
            format=None,  # Accept all formats
            coordinate_order="latlon"
        )
        
        if result and result.get('items'):
            items = result['items']
            print(f"Found {len(items)} NOAA LIDAR files")
            
            # Display sample results
            print("\nSample NOAA results:")
            for i, item in enumerate(items[:3]):  # Show first 3
                # Use the correct field names for NOAA data
                filename = item.get('title', item.get('filename', 'Unknown'))
                project = item.get('projectName', item.get('project_name', 'Unknown'))
                format_type = item.get('format', 'Unknown')
                url = item.get('downloadURL', item.get('url', item.get('file_path', 'No URL')))
                
                print(f"  {i+1}. {filename}")
                print(f"     Project: {project}")
                print(f"     Format: {format_type}")
                print(f"     URL: {url}")
                
                # Check for bounding box in the correct format
                bbox = item.get('boundingBox')
                if bbox and all(k in bbox for k in ['minX', 'minY', 'maxX', 'maxY']):
                    print(f"     Bounds: {bbox['minY']:.4f},{bbox['minX']:.4f} to {bbox['maxY']:.4f},{bbox['maxX']:.4f}")
                elif all(k in item for k in ['min_x', 'min_y', 'max_x', 'max_y']):
                    print(f"     Bounds: {item['min_y']:.4f},{item['min_x']:.4f} to {item['max_y']:.4f},{item['max_x']:.4f}")
                print()
        else:
            print("No NOAA LIDAR files found")
            
        return result or {"items": [], "total": 0}
        
    except ImportError as e:
        print(f"NOAA modules not available: {e}")
        return {"items": [], "total": 0, "error": f"NOAA modules not available: {e}"}
    except Exception as e:
        print(f"Error searching NOAA LIDAR: {e}")
        return {"items": [], "total": 0, "error": str(e)}

def save_results_to_json(usgs_results: Dict[str, Any], 
                        noaa_results: Dict[str, Any], 
                        output_file: str = "lidar_search_results.json"):
    """
    Save search results to JSON file
    
    Args:
        usgs_results: USGS search results
        noaa_results: NOAA search results
        output_file: Output file path
    """
    try:
        combined_results = {
            "search_metadata": {
                "timestamp": date.today().isoformat(),
                "polygon_source": "ML93170A_ML89035A_LidarPolygon.kml",
                "usgs_count": len(usgs_results.get('items', [])),
                "noaa_count": len(noaa_results.get('items', [])),
                "total_count": len(usgs_results.get('items', [])) + len(noaa_results.get('items', []))
            },
            "usgs_results": usgs_results,
            "noaa_results": noaa_results
        }
        
        with open(output_file, 'w') as f:
            json.dump(combined_results, f, indent=2)
        
        print(f"\nResults saved to: {output_file}")
        
    except Exception as e:
        print(f"Error saving results: {e}")

def main():
    """Main function to run the LIDAR search"""
    print("LIDAR Search using KML Polygon")
    print("=" * 40)
    
    # Parse KML polygon - back to original Wisconsin polygon
    kml_file = "NOAA/ML93170A_ML89035A_LidarPolygon.kml"
    
    if not os.path.exists(kml_file):
        print(f"Error: KML file not found: {kml_file}")
        return
    
    polygon_points = parse_kml_polygon(kml_file)
    
    if not polygon_points:
        print("Error: Could not extract polygon coordinates from KML file")
        return
    
    # Calculate polygon bounds for reference
    lats = [lat for lat, lon in polygon_points]
    lons = [lon for lat, lon in polygon_points]
    
    print(f"\nPolygon bounds:")
    print(f"  Latitude: {min(lats):.6f} to {max(lats):.6f}")
    print(f"  Longitude: {min(lons):.6f} to {max(lons):.6f}")
    print(f"  Area: Wisconsin region")
    
    # Search USGS LIDAR
    usgs_results = search_usgs_lidar(polygon_points)
    
    # Search NOAA LIDAR
    noaa_results = search_noaa_lidar(polygon_points)
    
    # Summary
    print(f"\n=== Search Summary ===")
    print(f"USGS LIDAR files found: {len(usgs_results.get('items', []))}")
    print(f"NOAA LIDAR files found: {len(noaa_results.get('items', []))}")
    print(f"Total LIDAR files found: {len(usgs_results.get('items', [])) + len(noaa_results.get('items', []))}")
    
    # Save results
    save_results_to_json(usgs_results, noaa_results)
    
    # Instructions for using in the main application
    print(f"\n=== Using Results in Main Application ===")
    print("To use these results in the main LOStool application:")
    print("1. Load the application: python dropmap.py")
    print("2. Load a project with sites in the Wisconsin area")
    print("3. Click 'Load JSON Results' button")
    print("4. Select the generated 'lidar_search_results.json' file")
    print("5. The LIDAR tiles will be displayed on the map")

if __name__ == "__main__":
    main() 