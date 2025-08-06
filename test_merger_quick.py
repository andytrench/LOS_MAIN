#!/usr/bin/env python3
"""
Quick Test: Merger Launcher with Test Files

This script quickly tests the merger launcher by using LAS/LAZ files 
from a specified directory, bypassing the download process entirely.
"""

import os
import sys
import logging
from pathlib import Path

# Add utilities to path
sys.path.append('utilities')

def find_las_laz_files(directory):
    """Find all LAS/LAZ files in the specified directory"""
    test_dir = Path(directory)
    if not test_dir.exists():
        print(f"❌ Test directory not found: {directory}")
        return []
    
    las_files = list(test_dir.glob("*.las")) + list(test_dir.glob("*.laz"))
    
    print(f"📁 Found {len(las_files)} LAS/LAZ files in {directory}:")
    for file_path in las_files:
        print(f"   📄 {file_path.name}")
        
    return [str(f) for f in las_files]

def test_merger_launcher(test_directory):
    """Test the merger launcher with files from test directory"""
    
    # Set up logging
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🚀 Quick Merger Test Starting...")
    print(f"📂 Test Directory: {test_directory}")
    print()
    
    # Find test files
    file_paths = find_las_laz_files(test_directory)
    
    if not file_paths:
        print("❌ No LAS/LAZ files found. Please add some test files to the directory.")
        return False
    
    print()
    
    # Analyze expected projects before launching
    expected_projects = analyze_expected_projects(file_paths)
    
    print()
    print("🔧 Testing merger launcher...")
    
    try:
        # Import and test the merger launcher
        from utilities.merger_launcher import launch_merger_with_files
        
        # Launch merger with test files
        success = launch_merger_with_files(
            file_paths=file_paths,
            project_name=None,  # Let merger2.py auto-detect projects
            auto_analyze=True,
            output_dir=test_directory,
            use_file_list=True
        )
        
        if success:
            print("✅ Merger launcher test completed successfully!")
            print("🎯 merger2.py should now be running with your test files")
            print(f"📊 Expected {len(expected_projects)} projects for auto-detection")
            print("🔍 Check merger2.py interface for project groupings")
        else:
            print("❌ Merger launcher test failed")
            
        return success
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

def analyze_expected_projects(file_paths):
    """Analyze filenames to show expected project groupings"""
    projects = {}
    
    for file_path in file_paths:
        filename = os.path.basename(file_path)
        
        # Skip merged files
        if filename.startswith('merged'):
            continue
            
        # Extract project identifier from filename
        if 'LincolnCo' in filename or 'LINCOLNCO' in filename:
            project_key = 'LincolnCo'
        elif 'OneidaCo' in filename:
            project_key = 'OneidaCo'  
        elif '12County' in filename:
            project_key = '12County'
        else:
            # Try to extract from USGS pattern
            parts = filename.split('_')
            if len(parts) >= 4:
                project_key = f"{parts[2]}_{parts[3]}"
            else:
                project_key = 'Unknown'
        
        if project_key not in projects:
            projects[project_key] = []
        projects[project_key].append(filename)
    
    print("🔍 Expected Project Detection:")
    for project, files in projects.items():
        print(f"   📊 {project}: {len(files)} files")
        for file in files[:3]:  # Show first 3 files
            print(f"      📄 {file}")
        if len(files) > 3:
            print(f"      ... and {len(files) - 3} more")
    
    print(f"\n🎯 Total Expected Projects: {len(projects)}")
    return projects

def main():
    """Main test function"""
    
    # Test directory specified by user
    test_directory = "/Users/master15/Desktop/newtest"
    
    print("=" * 60)
    print("🧪 QUICK MERGER LAUNCHER TEST")
    print("=" * 60)
    print()
    
    # Run the test
    success = test_merger_launcher(test_directory)
    
    print()
    print("=" * 60)
    if success:
        print("✅ TEST PASSED - Merger should be running with auto-detected projects!")
    else:
        print("❌ TEST FAILED - Check the output above for errors")
    print("=" * 60)

if __name__ == "__main__":
    main() 