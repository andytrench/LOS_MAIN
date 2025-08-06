#!/usr/bin/env python3
"""
Download all LIDAR files that intersect with Wisconsin polygon
"""

import geopandas as gpd
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon
import requests
import os
from urllib.parse import urlparse
import time
from datetime import datetime

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

def download_file(url, local_path, filename):
    """Download a file with progress tracking"""
    try:
        print(f"Downloading {filename}...")
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    if total_size > 0:
                        progress = (downloaded_size / total_size) * 100
                        print(f"  Progress: {progress:.1f}% ({downloaded_size:,} / {total_size:,} bytes)", end='\r')
        
        print(f"  ✓ Downloaded {filename} ({downloaded_size:,} bytes)")
        return True
        
    except Exception as e:
        print(f"  ✗ Error downloading {filename}: {e}")
        return False

def main():
    print("NOAA LIDAR File Downloader")
    print("=" * 40)
    
    # Parse KML polygon
    kml_file = 'NOAA/ML93170A_ML89035A_LidarPolygon.kml'
    polygon_points = parse_kml_polygon(kml_file)
    
    # Create polygon in WGS84
    search_polygon = Polygon(polygon_points)
    search_gdf = gpd.GeoDataFrame([1], geometry=[search_polygon], crs='EPSG:4326')
    
    print(f'Search polygon bounds: {search_gdf.total_bounds}')
    
    # Load tile index
    tile_gdf = gpd.read_file('NOAA/tileindex_2016_forest_m10005/tileindex_2016_forest_m10005.shp')
    
    # Convert search polygon to same CRS as tile index
    search_gdf_utm = search_gdf.to_crs(tile_gdf.crs)
    
    # Find intersecting tiles
    intersecting = tile_gdf[tile_gdf.geometry.intersects(search_gdf_utm.geometry.iloc[0])]
    
    print(f'Found {len(intersecting)} intersecting tiles to download')
    
    if len(intersecting) == 0:
        print("No files to download.")
        return
    
    # Create download directory
    download_dir = 'NOAA/downloaded_lidar_files'
    os.makedirs(download_dir, exist_ok=True)
    
    # Download each file
    successful_downloads = 0
    failed_downloads = 0
    start_time = datetime.now()
    
    for i, row in intersecting.iterrows():
        filename = row['filename']
        url = row['url']
        
        # Create local file path
        local_path = os.path.join(download_dir, filename)
        
        # Skip if file already exists
        if os.path.exists(local_path):
            file_size = os.path.getsize(local_path)
            print(f"  ⏭ Skipping {filename} (already exists, {file_size:,} bytes)")
            successful_downloads += 1
            continue
        
        # Download the file
        if download_file(url, local_path, filename):
            successful_downloads += 1
        else:
            failed_downloads += 1
        
        # Small delay between downloads to be respectful
        time.sleep(1)
    
    # Summary
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"\n" + "=" * 40)
    print(f"Download Summary:")
    print(f"  Total files: {len(intersecting)}")
    print(f"  Successful: {successful_downloads}")
    print(f"  Failed: {failed_downloads}")
    print(f"  Duration: {duration}")
    print(f"  Download directory: {download_dir}")
    
    # Calculate total size
    if successful_downloads > 0:
        total_size = 0
        for filename in os.listdir(download_dir):
            if filename.endswith('.laz'):
                file_path = os.path.join(download_dir, filename)
                total_size += os.path.getsize(file_path)
        
        print(f"  Total size: {total_size:,} bytes ({total_size / (1024*1024):.1f} MB)")
    
    # List downloaded files
    print(f"\nDownloaded files in {download_dir}:")
    for filename in sorted(os.listdir(download_dir)):
        if filename.endswith('.laz'):
            file_path = os.path.join(download_dir, filename)
            file_size = os.path.getsize(file_path)
            print(f"  {filename} ({file_size:,} bytes)")

if __name__ == "__main__":
    main() 