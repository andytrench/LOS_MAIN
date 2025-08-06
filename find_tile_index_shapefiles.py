#!/usr/bin/env python3
"""
Find and download tile index shapefiles from USGS and NOAA databases
"""

import requests
import re
import os
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import time
import zipfile
from datetime import datetime

def search_usgs_tile_indices():
    """Search USGS for tile index shapefiles"""
    print("🔍 Searching USGS for tile index shapefiles...")
    
    # USGS project directories often contain tileindex shapefiles
    usgs_base_urls = [
        "https://rockyweb.usgs.gov/vdelivery/Datasets/Staged/Elevation/LPC/Projects/",
        "https://cloud.sdsc.edu/v1/AUTH_opentopography/Raster/",
        "https://prd-tnm.s3.amazonaws.com/index.html?prefix=StagedProducts/Elevation/LPC/Projects/"
    ]
    
    tile_indices = []
    
    for base_url in usgs_base_urls:
        try:
            print(f"  Checking: {base_url}")
            response = requests.get(base_url, timeout=30)
            if response.status_code == 200:
                # Look for project directories
                soup = BeautifulSoup(response.content, 'html.parser')
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link['href']
                    if any(keyword in href.lower() for keyword in ['tileindex', 'index', 'shapefile']):
                        full_url = urljoin(base_url, href)
                        tile_indices.append({
                            'source': 'USGS',
                            'url': full_url,
                            'name': href,
                            'base_url': base_url
                        })
                        
        except Exception as e:
            print(f"    Error accessing {base_url}: {e}")
    
    return tile_indices

def search_noaa_tile_indices():
    """Search NOAA for tile index shapefiles"""
    print("🔍 Searching NOAA for tile index shapefiles...")
    
    tile_indices = []
    
    # NOAA Digital Coast LIDAR projects
    noaa_base_urls = [
        "https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/",
        "https://coast.noaa.gov/htdata/lidar1_z/",
        "https://coast.noaa.gov/htdata/lidar2_z/",
        "https://coast.noaa.gov/htdata/lidar3_z/"
    ]
    
    for base_url in noaa_base_urls:
        try:
            print(f"  Checking: {base_url}")
            
            if 's3.amazonaws.com' in base_url:
                # For S3 bucket, we need to check known project patterns
                # Based on the structure we found: /laz/geoid18/PROJECT_ID/
                for project_id in range(10000, 10100):  # Sample range
                    project_url = f"{base_url}laz/geoid18/{project_id}/"
                    try:
                        response = requests.head(project_url, timeout=10)
                        if response.status_code == 200:
                            # Check for tileindex files
                            index_url = f"{project_url}tileindex_{project_id}.zip"
                            index_response = requests.head(index_url, timeout=10)
                            if index_response.status_code == 200:
                                tile_indices.append({
                                    'source': 'NOAA',
                                    'url': index_url,
                                    'name': f'tileindex_{project_id}.zip',
                                    'project_id': project_id,
                                    'base_url': base_url
                                })
                    except:
                        continue
            else:
                # For regular HTTP directories
                response = requests.get(base_url, timeout=30)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    links = soup.find_all('a', href=True)
                    
                    for link in links:
                        href = link['href']
                        if any(keyword in href.lower() for keyword in ['tileindex', 'index.zip', 'shapefile']):
                            full_url = urljoin(base_url, href)
                            tile_indices.append({
                                'source': 'NOAA',
                                'url': full_url,
                                'name': href,
                                'base_url': base_url
                            })
                            
        except Exception as e:
            print(f"    Error accessing {base_url}: {e}")
    
    return tile_indices

def search_known_noaa_projects():
    """Search known NOAA project IDs for tile indices"""
    print("🔍 Searching known NOAA project IDs...")
    
    # Known NOAA project IDs from our database
    known_projects = []
    
    try:
        import sqlite3
        conn = sqlite3.connect('data/noaa_index.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT project_name FROM files WHERE project_name IS NOT NULL')
        projects = cursor.fetchall()
        conn.close()
        
        for project in projects:
            project_name = project[0]
            # Extract project ID if it follows pattern
            match = re.search(r'(\d{5})', project_name)
            if match:
                known_projects.append(match.group(1))
                
    except Exception as e:
        print(f"    Could not access NOAA database: {e}")
        # Fallback to common project IDs
        known_projects = ['10005', '10006', '10007', '10008', '10009', '10010']
    
    tile_indices = []
    base_url = "https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/"
    
    for project_id in known_projects:
        try:
            # Try different tileindex naming patterns
            patterns = [
                f"laz/geoid18/{project_id}/tileindex_{project_id}.zip",
                f"laz/geoid18/{project_id}/tileindex_2016_forest_m{project_id}.zip",
                f"laz/geoid18/{project_id}/index.zip",
                f"laz/geoid18/{project_id}/shapefile.zip"
            ]
            
            for pattern in patterns:
                url = base_url + pattern
                response = requests.head(url, timeout=10)
                if response.status_code == 200:
                    tile_indices.append({
                        'source': 'NOAA',
                        'url': url,
                        'name': os.path.basename(pattern),
                        'project_id': project_id,
                        'base_url': base_url
                    })
                    print(f"    ✓ Found: {url}")
                    break
                    
        except Exception as e:
            continue
    
    return tile_indices

def download_tile_index(tile_info, download_dir):
    """Download and extract a tile index shapefile"""
    try:
        url = tile_info['url']
        filename = tile_info['name']
        source = tile_info['source']
        
        print(f"📥 Downloading {source} tile index: {filename}")
        
        # Create source-specific directory
        source_dir = os.path.join(download_dir, source.lower())
        os.makedirs(source_dir, exist_ok=True)
        
        # Download file
        response = requests.get(url, timeout=300)
        response.raise_for_status()
        
        local_path = os.path.join(source_dir, filename)
        with open(local_path, 'wb') as f:
            f.write(response.content)
        
        print(f"    ✓ Downloaded: {local_path}")
        
        # Extract if it's a zip file
        if filename.endswith('.zip'):
            extract_dir = os.path.join(source_dir, filename.replace('.zip', ''))
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(local_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            print(f"    ✓ Extracted to: {extract_dir}")
            
            # List extracted files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.endswith('.shp'):
                        shp_path = os.path.join(root, file)
                        print(f"      📄 Shapefile: {shp_path}")
        
        return True
        
    except Exception as e:
        print(f"    ✗ Error downloading {filename}: {e}")
        return False

def main():
    print("Tile Index Shapefile Finder")
    print("=" * 50)
    
    # Create download directory
    download_dir = 'NOAA/tile_indices'
    os.makedirs(download_dir, exist_ok=True)
    
    all_tile_indices = []
    
    # Search USGS
    usgs_indices = search_usgs_tile_indices()
    all_tile_indices.extend(usgs_indices)
    
    # Search NOAA
    noaa_indices = search_noaa_tile_indices()
    all_tile_indices.extend(noaa_indices)
    
    # Search known NOAA projects
    known_noaa_indices = search_known_noaa_projects()
    all_tile_indices.extend(known_noaa_indices)
    
    print(f"\n📊 Found {len(all_tile_indices)} tile index shapefiles:")
    
    # Group by source
    usgs_count = len([t for t in all_tile_indices if t['source'] == 'USGS'])
    noaa_count = len([t for t in all_tile_indices if t['source'] == 'NOAA'])
    
    print(f"  USGS: {usgs_count}")
    print(f"  NOAA: {noaa_count}")
    
    # Show found indices
    for i, tile_info in enumerate(all_tile_indices):
        print(f"\n{i+1}. {tile_info['source']}: {tile_info['name']}")
        print(f"   URL: {tile_info['url']}")
    
    # Ask user which ones to download
    print(f"\n🔽 Download options:")
    print("1. Download all")
    print("2. Download NOAA only")
    print("3. Download USGS only")
    print("4. Select specific indices")
    print("5. Skip downloads")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    to_download = []
    if choice == '1':
        to_download = all_tile_indices
    elif choice == '2':
        to_download = [t for t in all_tile_indices if t['source'] == 'NOAA']
    elif choice == '3':
        to_download = [t for t in all_tile_indices if t['source'] == 'USGS']
    elif choice == '4':
        indices = input("Enter indices to download (comma-separated, e.g., 1,3,5): ").strip()
        try:
            selected = [int(i.strip()) - 1 for i in indices.split(',')]
            to_download = [all_tile_indices[i] for i in selected if 0 <= i < len(all_tile_indices)]
        except:
            print("Invalid selection")
            return
    
    # Download selected indices
    if to_download:
        print(f"\n📥 Downloading {len(to_download)} tile indices...")
        successful = 0
        
        for tile_info in to_download:
            if download_tile_index(tile_info, download_dir):
                successful += 1
            time.sleep(1)  # Be respectful
        
        print(f"\n✅ Downloaded {successful}/{len(to_download)} tile indices")
        print(f"📁 Files saved to: {download_dir}")
    else:
        print("\n⏭️ No downloads selected")

if __name__ == "__main__":
    main() 