#!/usr/bin/env python3
"""
Search all downloaded tile index shapefiles for intersecting LIDAR files
"""

import geopandas as gpd
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon
import os
import glob
from collections import defaultdict
import pandas as pd

def parse_kml_polygon(kml_file):
    """Parse KML polygon coordinates"""
    tree = ET.parse(kml_file)
    root = tree.getroot()
    coords_elem = root.find('.//{http://www.opengis.net/kml/2.2}coordinates')
    coords_text = coords_elem.text.strip()
    coord_pairs = coords_text.split()
    polygon_points = []
    for coord_pair in coord_pairs:
        parts = coord_pair.split(',')
        if len(parts) >= 2:
            lon, lat = float(parts[0]), float(parts[1])
            polygon_points.append((lon, lat))
    return polygon_points

def find_all_shapefiles(base_dir):
    """Find all shapefiles in the tile indices directory"""
    shapefiles = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.shp'):
                shp_path = os.path.join(root, file)
                # Extract project info from path
                path_parts = shp_path.split(os.sep)
                project_id = None
                for part in path_parts:
                    if part.startswith('project_'):
                        project_id = part.replace('project_', '')
                        break
                
                shapefiles.append({
                    'path': shp_path,
                    'filename': file,
                    'project_id': project_id,
                    'relative_path': os.path.relpath(shp_path, base_dir)
                })
    
    return shapefiles

def search_shapefile_for_intersections(shp_info, search_polygon_wgs84):
    """Search a single shapefile for intersecting tiles"""
    try:
        # Load shapefile
        gdf = gpd.read_file(shp_info['path'])
        
        if len(gdf) == 0:
            return []
        
        # Convert search polygon to shapefile CRS
        search_gdf = gpd.GeoDataFrame([1], geometry=[search_polygon_wgs84], crs='EPSG:4326')
        search_gdf_proj = search_gdf.to_crs(gdf.crs)
        
        # Find intersections
        intersecting = gdf[gdf.geometry.intersects(search_gdf_proj.geometry.iloc[0])]
        
        results = []
        for idx, row in intersecting.iterrows():
            # Get file info
            result = {
                'project_id': shp_info['project_id'],
                'shapefile': shp_info['filename'],
                'shapefile_path': shp_info['relative_path']
            }
            
            # Add all columns from the shapefile
            for col in gdf.columns:
                if col != 'geometry':
                    result[col] = row[col]
            
            # Add bounding box in WGS84
            geom_wgs84 = gpd.GeoSeries([row.geometry], crs=gdf.crs).to_crs('EPSG:4326').iloc[0]
            bounds = geom_wgs84.bounds
            result['bounds_wgs84'] = f"{bounds[1]:.6f},{bounds[0]:.6f} to {bounds[3]:.6f},{bounds[2]:.6f}"
            
            results.append(result)
        
        return results
        
    except Exception as e:
        print(f"    ✗ Error processing {shp_info['filename']}: {e}")
        return []

def main():
    print("Search All Tile Index Shapefiles")
    print("=" * 50)
    
    # Parse KML polygon
    kml_file = 'NOAA/ML93170A_ML89035A_LidarPolygon.kml'
    if not os.path.exists(kml_file):
        print(f"Error: KML file not found: {kml_file}")
        return
    
    polygon_points = parse_kml_polygon(kml_file)
    search_polygon = Polygon(polygon_points)
    
    print(f"Search polygon loaded with {len(polygon_points)} points")
    
    # Find all shapefiles
    tile_indices_dir = 'NOAA/tile_indices'
    if not os.path.exists(tile_indices_dir):
        print(f"Error: Tile indices directory not found: {tile_indices_dir}")
        return
    
    shapefiles = find_all_shapefiles(tile_indices_dir)
    print(f"Found {len(shapefiles)} shapefiles to search")
    
    # Search each shapefile
    all_results = []
    projects_with_hits = defaultdict(int)
    
    for i, shp_info in enumerate(shapefiles):
        print(f"Searching {i+1}/{len(shapefiles)}: {shp_info['filename']}")
        
        results = search_shapefile_for_intersections(shp_info, search_polygon)
        
        if results:
            print(f"    ✓ Found {len(results)} intersecting files")
            all_results.extend(results)
            projects_with_hits[shp_info['project_id']] += len(results)
        else:
            print(f"    - No intersections")
    
    # Summary
    print(f"\n" + "=" * 50)
    print(f"SEARCH SUMMARY")
    print(f"=" * 50)
    print(f"Shapefiles searched: {len(shapefiles)}")
    print(f"Projects with hits: {len(projects_with_hits)}")
    print(f"Total intersecting files: {len(all_results)}")
    
    if projects_with_hits:
        print(f"\nProjects with intersecting files:")
        for project_id, count in sorted(projects_with_hits.items()):
            print(f"  Project {project_id}: {count} files")
    
    # Show sample results
    if all_results:
        print(f"\nSample intersecting files:")
        for i, result in enumerate(all_results[:10]):
            filename = result.get('filename', result.get('FILENAME', 'Unknown'))
            project = result.get('project_id', 'Unknown')
            bounds = result.get('bounds_wgs84', 'Unknown bounds')
            url = result.get('url', result.get('URL', 'No URL'))
            
            print(f"  {i+1}. {filename}")
            print(f"     Project: {project}")
            print(f"     Bounds: {bounds}")
            if url != 'No URL':
                print(f"     URL: {url}")
            print()
    
    # Save results to CSV
    if all_results:
        results_file = 'NOAA/all_tile_intersections.csv'
        df = pd.DataFrame(all_results)
        df.to_csv(results_file, index=False)
        print(f"📄 Results saved to: {results_file}")
        
        # Save summary
        summary_file = 'NOAA/tile_search_summary.txt'
        with open(summary_file, 'w') as f:
            f.write(f"Tile Index Search Summary\n")
            f.write(f"========================\n")
            f.write(f"Search polygon: Wisconsin area\n")
            f.write(f"Shapefiles searched: {len(shapefiles)}\n")
            f.write(f"Projects with hits: {len(projects_with_hits)}\n")
            f.write(f"Total intersecting files: {len(all_results)}\n\n")
            
            f.write("Projects with intersecting files:\n")
            for project_id, count in sorted(projects_with_hits.items()):
                f.write(f"  Project {project_id}: {count} files\n")
            
            f.write(f"\nDetailed results saved to: {results_file}\n")
        
        print(f"📝 Summary saved to: {summary_file}")
    
    else:
        print("\nNo intersecting files found in any tile index.")

if __name__ == "__main__":
    main() 