"""
LIDAR data processing module for the LOS application.
Handles LIDAR search, download, and visualization.
"""

import logging
import json
import requests
import random
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os
import threading
from log_config import setup_logging
from utilities.metadata import ProjectMetadata, get_project_name
from utilities.geometry import calculate_polygon_points

# Create logger
logger = setup_logging(__name__)

class LidarProcessor:
    def __init__(self, map_widget=None, downloader=None):
        """Initialize the LIDAR processor"""
        self.map_widget = map_widget
        self.downloader = downloader
        self.polygon_points = None
        self.lidar_polygons = []
        self.used_colors = set()
        self.selected_items = set()
        self.projects = {}
        self.spatial_reference_cache = {}
        self.transformer = None
        self.selected_lidar = None
        self.site_a = None
        self.site_b = None
        self.polygon_width_ft = 2000
        
        # Create metadata instance
        self.project_metadata = ProjectMetadata()
    
    def set_polygon_points(self, polygon_points):
        """Set the polygon points for LIDAR search"""
        self.polygon_points = polygon_points
        
    def update_site_data(self, site_a, site_b):
        """Update site data and recalculate polygon"""
        self.site_a = site_a
        self.site_b = site_b
        
        # Calculate polygon points based on site coordinates
        if site_a and site_b and 'adjusted_latitude' in site_a and 'adjusted_longitude' in site_a:
            try:
                # Calculate polygon points
                polygon_points = calculate_polygon_points(
                    (site_a['adjusted_latitude'], site_a['adjusted_longitude']),
                    (site_b['adjusted_latitude'], site_b['adjusted_longitude']),
                    self.polygon_width_ft
                )
                
                # Update polygon points
                self.set_polygon_points(polygon_points)
                
                logger.info("Updated site data and recalculated polygon")
                return True
            except Exception as e:
                logger.error(f"Error calculating polygon points: {str(e)}", exc_info=True)
                return False
        else:
            logger.warning("Incomplete site data, cannot calculate polygon")
            return False
    
    def search_lidar(self, start_date=None, end_date=None):
        """Search for LIDAR data within the polygon"""
        if not self.polygon_points:
            logger.warning("No polygon points available for LIDAR search")
            messagebox.showwarning("No Polygon", "Please load a project first to define the search area.")
            return
            
        try:
            # Format polygon for API request
            polygon_str = self._format_polygon_for_api()
            
            # Prepare date parameters
            date_params = ""
            if start_date and end_date:
                date_params = f"&dates={start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')}"
            
            # Construct API URL
            url = f"https://tnmaccess.nationalmap.gov/api/v1/products?datasets=Lidar%20Point%20Cloud%20(LPC)&polygon={polygon_str}{date_params}&outputFormat=JSON"
            
            logger.info(f"Searching for LIDAR data with URL: {url}")
            
            # Make request in a separate thread to avoid blocking UI
            threading.Thread(target=self._execute_lidar_search, args=(url,), daemon=True).start()
            
            return True
        except Exception as e:
            logger.error(f"Error searching for LIDAR data: {str(e)}", exc_info=True)
            messagebox.showerror("Search Error", f"Failed to search for LIDAR data: {str(e)}")
            return False
    
    def _execute_lidar_search(self, url):
        """Execute LIDAR search in background thread"""
        try:
            # Make request
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse response
            data = response.json()
            
            # Process results
            items = data.get('items', [])
            
            # Log results
            logger.info(f"Found {len(items)} LIDAR datasets")
            
            # Process results in main thread
            if hasattr(tk, 'Tk') and isinstance(self.map_widget, tk.Widget):
                self.map_widget.after(0, lambda: self._process_lidar_results(items))
            else:
                self._process_lidar_results(items)
                
        except Exception as e:
            logger.error(f"Error executing LIDAR search: {str(e)}", exc_info=True)
            if hasattr(tk, 'Tk') and isinstance(self.map_widget, tk.Widget):
                self.map_widget.after(0, lambda: messagebox.showerror("Search Error", f"Failed to search for LIDAR data: {str(e)}"))
    
    def _process_lidar_results(self, items):
        """Process LIDAR search results"""
        if not items:
            messagebox.showinfo("Search Results", "No LIDAR data found for the specified area and date range.")
            return
            
        # Clear existing results
        self._clear_lidar_results()
        
        # Process each item
        for item in items:
            # Generate a random color for this item
            color = self._generate_random_color()
            
            # Process the LIDAR file
            self.process_lidar_file(item, color)
    
    def _clear_lidar_results(self):
        """Clear existing LIDAR results"""
        # Clear polygons from map
        for polygon in self.lidar_polygons:
            if polygon and hasattr(polygon, 'delete'):
                polygon.delete()
                
        # Clear data structures
        self.lidar_polygons = []
        self.used_colors = set()
        self.selected_items = set()
        self.projects = {}
    
    def process_lidar_file(self, item, color):
        """Process a LIDAR file and add it to the map"""
        try:
            url = item.get('downloadURL')
            if url:
                filename = url.split('/')[-1]
                project_name = get_project_name(filename)
                
                # Log detailed information about the LIDAR file
                logger.info(f"Processing LIDAR file: {filename}")
                logger.info(f"Project name: {project_name}")
                logger.info(f"Download URL: {url}")
                logger.info(f"Source ID: {item.get('sourceId')}")
                logger.info(f"Size: {self.format_file_size(item.get('sizeInBytes', 'Unknown'))}")
                
                # Extract and log bounding box information
                bbox = item.get('boundingBox')
                if bbox:
                    logger.info(f"Bounding box: minX={bbox.get('minX')}, maxX={bbox.get('maxX')}, minY={bbox.get('minY')}, maxY={bbox.get('maxY')}")
                    
                    # Add polygon to map
                    self._add_lidar_polygon(bbox, color, item)
                    
                    # Store project information
                    self.projects[project_name] = {
                        'item': item,
                        'color': color,
                        'bbox': bbox
                    }
                    
                    # Update metadata
                    self._update_metadata(item, project_name)
                    
                    return True
            
            return False
        except Exception as e:
            logger.error(f"Error processing LIDAR file: {str(e)}", exc_info=True)
            return False
    
    def _add_lidar_polygon(self, bbox, color, item):
        """Add a LIDAR polygon to the map"""
        if not bbox or not self.map_widget:
            return None
            
        try:
            # Extract coordinates
            min_x = bbox.get('minX')
            max_x = bbox.get('maxX')
            min_y = bbox.get('minY')
            max_y = bbox.get('maxY')
            
            if min_x is None or max_x is None or min_y is None or max_y is None:
                return None
                
            # Create polygon points
            polygon_points = [
                (min_y, min_x),  # Bottom left
                (max_y, min_x),  # Top left
                (max_y, max_x),  # Top right
                (min_y, max_x),  # Bottom right
                (min_y, min_x)   # Back to start
            ]
            
            # Add polygon to map
            polygon = self.map_widget.set_polygon(
                polygon_points,
                outline_color=color,
                fill_color=self._get_transparent_color(color),
                width=2
            )
            
            # Store polygon
            self.lidar_polygons.append(polygon)
            
            # Add click event
            if hasattr(polygon, 'polygon_canvas_id'):
                self.map_widget.canvas.tag_bind(
                    polygon.polygon_canvas_id,
                    "<Button-1>",
                    lambda event, i=item: self._on_lidar_polygon_click(i)
                )
            
            return polygon
        except Exception as e:
            logger.error(f"Error adding LIDAR polygon: {str(e)}", exc_info=True)
            return None
    
    def _on_lidar_polygon_click(self, item):
        """Handle click on LIDAR polygon"""
        try:
            # Set as selected LIDAR
            self.selected_lidar = item
            
            # Update UI to show selection
            self._update_selection_ui()
            
            # Log selection
            url = item.get('downloadURL', 'Unknown')
            filename = url.split('/')[-1] if url != 'Unknown' else 'Unknown'
            logger.info(f"Selected LIDAR file: {filename}")
            
            return True
        except Exception as e:
            logger.error(f"Error handling LIDAR polygon click: {str(e)}", exc_info=True)
            return False
    
    def _update_selection_ui(self):
        """Update UI to reflect current selection"""
        # This would be implemented based on the UI structure
        pass
    
    def _update_metadata(self, item, project_name):
        """Update metadata with LIDAR information"""
        try:
            # Extract metadata
            url = item.get('downloadURL', '')
            filename = url.split('/')[-1] if url else 'Unknown'
            
            # Create metadata entry
            metadata = {
                'name': project_name,
                'title': item.get('title', 'Unknown'),
                'source_id': item.get('sourceId', 'Unknown'),
                'download_url': url,
                'size_bytes': item.get('sizeInBytes', 0),
                'publication_date': item.get('publicationDate', 'Unknown')
            }
            
            # Extract bounding box
            bbox = item.get('boundingBox')
            if bbox:
                metadata['bounds'] = {
                    'minX': bbox.get('minX'),
                    'maxX': bbox.get('maxX'),
                    'minY': bbox.get('minY'),
                    'maxY': bbox.get('maxY')
                }
            
            # Update project metadata
            self.project_metadata.update_lidar_metadata(project_name, metadata)
            
            return True
        except Exception as e:
            logger.error(f"Error updating metadata: {str(e)}", exc_info=True)
            return False
    
    def download_selected_lidar(self):
        """Download the selected LIDAR file"""
        if not self.selected_lidar:
            messagebox.showwarning("No Selection", "Please select a LIDAR dataset to download.")
            return False
            
        try:
            # Get download URL
            url = self.selected_lidar.get('downloadURL')
            if not url:
                messagebox.showerror("Download Error", "No download URL available for the selected LIDAR dataset.")
                return False
                
            # Get filename
            filename = url.split('/')[-1]
            
            # Get project name
            project_name = get_project_name(filename)
            
            # Create project directory if it doesn't exist
            project_dir = os.path.join("data", "lidar", project_name)
            os.makedirs(project_dir, exist_ok=True)
            
            # Set download path
            download_path = os.path.join(project_dir, filename)
            
            # Start download
            if self.downloader:
                self.downloader.download_file(url, download_path)
                logger.info(f"Started download of {filename} to {download_path}")
                return True
            else:
                messagebox.showerror("Download Error", "Downloader not initialized.")
                return False
        except Exception as e:
            logger.error(f"Error downloading LIDAR file: {str(e)}", exc_info=True)
            messagebox.showerror("Download Error", f"Failed to download LIDAR file: {str(e)}")
            return False
    
    def _format_polygon_for_api(self):
        """Format polygon points for API request"""
        if not self.polygon_points:
            return ""
            
        # Format as lon,lat pairs
        formatted_points = []
        for point in self.polygon_points:
            formatted_points.append(f"{point[1]},{point[0]}")
            
        # Join with commas
        return ",".join(formatted_points)
    
    def _generate_random_color(self):
        """Generate a random color that hasn't been used yet"""
        # List of distinct colors
        colors = [
            "#3388ff",  # Blue
            "#ff3333",  # Red
            "#33cc33",  # Green
            "#ff9900",  # Orange
            "#9933ff",  # Purple
            "#ff33cc",  # Pink
            "#33cccc",  # Teal
            "#ffcc00",  # Yellow
            "#cc6633",  # Brown
            "#66cc33"   # Lime
        ]
        
        # Try to find an unused color
        available_colors = [c for c in colors if c not in self.used_colors]
        
        if available_colors:
            color = random.choice(available_colors)
        else:
            # If all colors are used, generate a random one
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            color = f"#{r:02x}{g:02x}{b:02x}"
        
        # Add to used colors
        self.used_colors.add(color)
        
        return color
    
    def _get_transparent_color(self, color, alpha=0.2):
        """Convert color to transparent version for polygon fill"""
        # If color is in hex format (#RRGGBB)
        if color.startswith("#"):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            return f"#{r:02x}{g:02x}{b:02x}{int(alpha*255):02x}"
        
        # If color is a named color, use default transparent blue
        return "#3388ff33"
    
    def format_file_size(self, size_bytes):
        """Format file size in human-readable format"""
        if size_bytes == "Unknown":
            return "Unknown"
            
        try:
            size_bytes = int(size_bytes)
            for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                if size_bytes < 1024.0:
                    return f"{size_bytes:.2f} {unit}"
                size_bytes /= 1024.0
            return f"{size_bytes:.2f} PB"
        except (ValueError, TypeError):
            return "Unknown"
    
    def center_map_on_path(self):
        """Center the map on the path between sites"""
        if not self.site_a or not self.site_b or not self.map_widget:
            return False
            
        try:
            # Calculate center point
            center_lat = (self.site_a['adjusted_latitude'] + self.site_b['adjusted_latitude']) / 2
            center_lon = (self.site_a['adjusted_longitude'] + self.site_b['adjusted_longitude']) / 2
            
            # Set map position
            self.map_widget.set_position(center_lat, center_lon)
            
            # Calculate appropriate zoom level based on distance
            lat1, lon1 = self.site_a['adjusted_latitude'], self.site_a['adjusted_longitude']
            lat2, lon2 = self.site_b['adjusted_latitude'], self.site_b['adjusted_longitude']
            
            # Calculate distance in degrees
            distance = ((lat2 - lat1)**2 + (lon2 - lon1)**2)**0.5
            
            # Set zoom level based on distance
            if distance < 0.05:
                zoom = 12
            elif distance < 0.1:
                zoom = 11
            elif distance < 0.2:
                zoom = 10
            elif distance < 0.5:
                zoom = 9
            elif distance < 1.0:
                zoom = 8
            else:
                zoom = 7
                
            # Set zoom
            self.map_widget.set_zoom(zoom)
            
            return True
        except Exception as e:
            logger.error(f"Error centering map on path: {str(e)}", exc_info=True)
            return False
