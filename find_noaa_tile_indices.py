#!/usr/bin/env python3
"""
Find NOAA tile index shapefiles for known projects
"""

import requests
import os
import zipfile
import sqlite3
import re
from datetime import datetime

def get_known_project_ids():
    """Get project IDs from our NOAA database and common patterns"""
    project_ids = set()
    
    # Try to get from database
    try:
        conn = sqlite3.connect('data/noaa_index.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT project_name FROM files WHERE project_name IS NOT NULL')
        projects = cursor.fetchall()
        conn.close()
        
        for project in projects:
            project_name = project[0]
            # Extract 5-digit project IDs
            matches = re.findall(r'\b(\d{5})\b', project_name)
            for match in matches:
                project_ids.add(match)
                
        print(f"Found {len(project_ids)} project IDs from database")
        
    except Exception as e:
        print(f"Could not access database: {e}")
    
    # Add common project ID ranges
    common_ranges = [
        range(10000, 10100),  # 2016-2017 projects
        range(10100, 10200),  # 2017-2018 projects  
        range(10200, 10300),  # 2018-2019 projects
        range(9000, 9100),    # Earlier projects
        range(8000, 8100),    # Even earlier projects
    ]
    
    for r in common_ranges:
        for pid in r:
            project_ids.add(str(pid))
    
    return sorted(list(project_ids))

def check_tile_index_exists(project_id):
    """Check if tile index exists for a project ID"""
    base_url = "https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/"
    
    # Try different naming patterns
    patterns = [
        f"laz/geoid18/{project_id}/tileindex_2016_forest_m{project_id}.zip",
        f"laz/geoid18/{project_id}/tileindex_{project_id}.zip", 
        f"laz/geoid18/{project_id}/tileindex.zip",
        f"laz/geoid18/{project_id}/index.zip",
        f"laz/geoid18/{project_id}/shapefile.zip",
        f"laz/geoid18/{project_id}/tiles.zip"
    ]
    
    for pattern in patterns:
        url = base_url + pattern
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                return url, os.path.basename(pattern)
        except:
            continue
    
    return None, None

def download_and_extract_tile_index(url, filename, project_id, download_dir):
    """Download and extract a tile index"""
    try:
        print(f"📥 Downloading {filename} for project {project_id}...")
        
        # Create project directory
        project_dir = os.path.join(download_dir, f"project_{project_id}")
        os.makedirs(project_dir, exist_ok=True)
        
        # Download
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        
        zip_path = os.path.join(project_dir, filename)
        with open(zip_path, 'wb') as f:
            f.write(response.content)
        
        # Extract
        extract_dir = os.path.join(project_dir, filename.replace('.zip', ''))
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find shapefiles
        shapefiles = []
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                if file.endswith('.shp'):
                    shp_path = os.path.join(root, file)
                    shapefiles.append(shp_path)
        
        print(f"    ✓ Downloaded and extracted to: {extract_dir}")
        print(f"    📄 Found {len(shapefiles)} shapefile(s)")
        
        for shp in shapefiles:
            print(f"      - {os.path.relpath(shp, download_dir)}")
        
        return True, shapefiles
        
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return False, []

def main():
    print("NOAA Tile Index Finder")
    print("=" * 40)
    
    # Get project IDs to check
    project_ids = get_known_project_ids()
    print(f"Checking {len(project_ids)} project IDs...")
    
    # Create download directory
    download_dir = 'NOAA/tile_indices'
    os.makedirs(download_dir, exist_ok=True)
    
    found_indices = []
    
    # Check each project ID
    for i, project_id in enumerate(project_ids):
        if i % 10 == 0:
            print(f"Progress: {i}/{len(project_ids)} ({i/len(project_ids)*100:.1f}%)")
        
        url, filename = check_tile_index_exists(project_id)
        if url:
            found_indices.append({
                'project_id': project_id,
                'url': url,
                'filename': filename
            })
            print(f"✓ Found tile index for project {project_id}: {filename}")
    
    print(f"\n📊 Summary:")
    print(f"  Checked: {len(project_ids)} projects")
    print(f"  Found: {len(found_indices)} tile indices")
    
    if not found_indices:
        print("No tile indices found.")
        return
    
    # Show found indices
    print(f"\n📋 Found tile indices:")
    for i, info in enumerate(found_indices):
        print(f"  {i+1}. Project {info['project_id']}: {info['filename']}")
    
    # Ask user what to download
    print(f"\n🔽 Download options:")
    print("1. Download all")
    print("2. Download first 5")
    print("3. Select specific projects")
    print("4. Skip downloads")
    
    choice = input("\nEnter choice (1-4): ").strip()
    
    to_download = []
    if choice == '1':
        to_download = found_indices
    elif choice == '2':
        to_download = found_indices[:5]
    elif choice == '3':
        projects = input("Enter project IDs to download (comma-separated): ").strip()
        try:
            selected_ids = [p.strip() for p in projects.split(',')]
            to_download = [info for info in found_indices if info['project_id'] in selected_ids]
        except:
            print("Invalid selection")
            return
    
    # Download selected indices
    if to_download:
        print(f"\n📥 Downloading {len(to_download)} tile indices...")
        successful = 0
        all_shapefiles = []
        
        for info in to_download:
            success, shapefiles = download_and_extract_tile_index(
                info['url'], info['filename'], info['project_id'], download_dir
            )
            if success:
                successful += 1
                all_shapefiles.extend(shapefiles)
        
        print(f"\n✅ Successfully downloaded {successful}/{len(to_download)} tile indices")
        print(f"📁 Files saved to: {download_dir}")
        print(f"📄 Total shapefiles: {len(all_shapefiles)}")
        
        # Create summary file
        summary_file = os.path.join(download_dir, 'tile_indices_summary.txt')
        with open(summary_file, 'w') as f:
            f.write(f"NOAA Tile Indices Summary\n")
            f.write(f"Generated: {datetime.now()}\n")
            f.write(f"Total projects checked: {len(project_ids)}\n")
            f.write(f"Tile indices found: {len(found_indices)}\n")
            f.write(f"Downloaded: {successful}\n\n")
            
            f.write("Downloaded Projects:\n")
            for info in to_download:
                f.write(f"  Project {info['project_id']}: {info['filename']}\n")
            
            f.write(f"\nShapefiles:\n")
            for shp in all_shapefiles:
                f.write(f"  {os.path.relpath(shp, download_dir)}\n")
        
        print(f"📝 Summary saved to: {summary_file}")
    else:
        print("\n⏭️ No downloads selected")

if __name__ == "__main__":
    main() 