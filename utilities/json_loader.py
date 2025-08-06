import json
import os
import logging
from typing import Dict, List, Any, Tuple, Optional
import tkinter as tk
from tkinter import messagebox

logger = logging.getLogger(__name__)

def load_tower_parameters() -> Optional[Dict[str, Any]]:
    """
    Load the tower_parameters.json file
    
    Returns:
        Dictionary containing the tower parameters or None if the file doesn't exist or is invalid
    """
    try:
        if not os.path.exists('tower_parameters.json'):
            logger.warning("tower_parameters.json file not found")
            return None
            
        with open('tower_parameters.json', 'r') as f:
            data = json.load(f)
            
        logger.info(f"Successfully loaded tower_parameters.json with {len(data.keys())} top-level keys")
        return data
    except Exception as e:
        logger.error(f"Error loading tower_parameters.json: {e}", exc_info=True)
        return None

def extract_lidar_data_from_json() -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """
    Extract LIDAR data from tower_parameters.json
    
    Returns:
        Tuple containing:
        - List of all LIDAR items
        - Dictionary mapping project names to lists of LIDAR items
    """
    try:
        # Load tower parameters
        tower_data = load_tower_parameters()
        if not tower_data or 'lidar_data' not in tower_data:
            logger.warning("No LIDAR data found in tower_parameters.json")
            return [], {}
            
        lidar_data = tower_data['lidar_data']
        logger.info(f"Found {len(lidar_data)} LIDAR projects in tower_parameters.json")
        
        # Extract all items
        all_items = []
        project_items = {}
        
        for project_name, project_data in lidar_data.items():
            logger.info(f"Processing project: {project_name}")
            
            # Initialize project items list
            if project_name not in project_items:
                project_items[project_name] = []
                
            # Get files from project
            files = project_data.get('files', [])
            logger.info(f"Project {project_name} has {len(files)} files")
            
            # Process each file
            for file_data in files:
                # Create item structure similar to what would be returned from a search
                item = {
                    'title': file_data.get('title', ''),
                    'sourceId': file_data.get('source_id', ''),
                    'downloadURL': file_data.get('download_url', ''),
                    'sizeInBytes': file_data.get('size_bytes', 0),
                    'boundingBox': file_data.get('bounds', {}),
                    'project': project_name  # Add project name for reference
                }
                
                # Add to all items list
                all_items.append(item)
                
                # Add to project items
                project_items[project_name].append(item)
                
        logger.info(f"Extracted {len(all_items)} total LIDAR items from {len(project_items)} projects")
        return all_items, project_items
    except Exception as e:
        logger.error(f"Error extracting LIDAR data from JSON: {e}", exc_info=True)
        return [], {}

def load_json_results(application_controller):
    """
    Load LIDAR results from tower_parameters.json and display them in the application
    
    Args:
        application_controller: The main application controller (LidarDownloader instance)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info("Loading LIDAR results from tower_parameters.json")
        
        # Extract LIDAR data
        all_items, project_items = extract_lidar_data_from_json()
        
        if not all_items:
            messagebox.showinfo("No Data", "No LIDAR data found in tower_parameters.json. Please perform a search first.")
            return False
            
        # Create result structure similar to what would be returned from a search
        result = {"items": all_items}
        
        # Display results in the application
        logger.info(f"Displaying {len(all_items)} LIDAR items from JSON")
        application_controller.display_lidar_results(result)
        
        return True
    except Exception as e:
        logger.error(f"Error loading JSON results: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to load LIDAR data from JSON: {str(e)}")
        return False
