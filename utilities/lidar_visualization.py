import logging
import tkinter as tk
from tkinter import ttk

# Configure logging
logger = logging.getLogger(__name__)

class LidarVisualizer:
    """
    Class for visualizing LIDAR data on a map widget.
    """
    def __init__(self, map_widget):
        """
        Initialize the visualizer.
        
        Args:
            map_widget: The tkintermapview map widget to display data on
        """
        self.map_widget = map_widget
        self.lidar_polygons = []
        self.project_polygons = {}
        self._all_project_polygons = {}
        self.project_colors = {}
        self.project_visibility = {}
        self.project_tile_counts = {}
        self.project_tile_count_labels = {}
        
        # Define a color series for different projects
        self.color_series = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
            "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
            "#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5"
        ]
    
    def clear_lidar_display(self):
        """
        Clear all LIDAR data from the map.
        """
        self.clear_lidar_polygons()
        self.project_polygons = {}
        self._all_project_polygons = {}
        self.project_colors = {}
        self.project_visibility = {}
        self.project_tile_counts = {}
        
    def clear_lidar_polygons(self):
        """
        Remove all LIDAR polygons from the map.
        """
        for polygon in self.lidar_polygons:
            self.map_widget.delete(polygon)
        self.lidar_polygons = []
    
    def create_original_polygon_data(self, project_name, polygon_points, color):
        """
        Store original polygon data for visibility toggling.
        
        Args:
            project_name: Name of the project
            polygon_points: List of (lat, lon) tuples defining the polygon
            color: Color of the polygon
        """
        if not hasattr(self, '_original_polygon_data'):
            self._original_polygon_data = {}
            
        if project_name not in self._original_polygon_data:
            self._original_polygon_data[project_name] = []
            
        self._original_polygon_data[project_name].append({
            'points': polygon_points,
            'color': color
        })
    
    def toggle_project_visibility(self, project_name):
        """
        Toggle the visibility of a project's polygons.
        
        Args:
            project_name: Name of the project to toggle
        """
        if project_name not in self.project_visibility:
            logger.warning(f"Project {project_name} not found in visibility tracking")
            return
            
        is_visible = self.project_visibility[project_name].get()
        logger.info(f"Toggling visibility of project {project_name} to {is_visible}")
        
        if project_name in self.project_polygons:
            if is_visible:
                # Show polygons - recreate them if they don't exist
                if not self.project_polygons[project_name] and project_name in self._original_polygon_data:
                    logger.info(f"Recreating polygons for project {project_name}")
                    for poly_data in self._original_polygon_data[project_name]:
                        polygon = self.map_widget.set_polygon(
                            poly_data['points'],
                            fill_color="",
                            outline_color=poly_data['color'],
                            border_width=2
                        )
                        self.lidar_polygons.append(polygon)
                        self.project_polygons[project_name].append(polygon)
                else:
                    # Make existing polygons visible
                    for polygon in self.project_polygons[project_name]:
                        polygon.visible = True
            else:
                # Hide polygons
                for polygon in self.project_polygons[project_name]:
                    polygon.visible = False
                    
    def display_lidar_results(self, data, project_metadata=None, legend_frame=None):
        """
        Display LIDAR search results on the map.
        
        Args:
            data: Dictionary containing LIDAR search results
            project_metadata: Optional ProjectMetadata object to store project data
            legend_frame: Optional frame to display the legend in
        """
        from utilities.metadata import get_project_name
        
        try:
            logger.info(f"Displaying LIDAR results - {len(data['items'])} items found")
            
            # Clear existing LIDAR display
            self.clear_lidar_display()
            
            # Extract data from results
            items = data['items']
            
            # Initialize tracking variables
            files_within_polygon = 0
            project_items = {}
            tile_counter = 1
            
            # First pass - collect metadata and group items by project
            logger.info("Starting first pass - collecting unique projects")
            for item in items:
                url = item.get('downloadURL')
                item_id = item.get('sourceId')
                
                if url and item_id:
                    filename = url.split('/')[-1]
                    project_name = get_project_name(filename)
                    
                    # Initialize project group if needed
                    if project_name not in project_items:
                        project_items[project_name] = []
                        # Assign color if not already assigned
                        if project_name not in self.project_colors:
                            color_index = len(self.project_colors) % len(self.color_series)
                            self.project_colors[project_name] = self.color_series[color_index]
                        logger.info(f"Processing metadata for project: {project_name}")
                        
                        # Process metadata for first item in project
                        if project_metadata:
                            project_metadata.add_project(project_name, item)
                            
                        # Initialize project visibility tracking
                        self.project_visibility[project_name] = tk.BooleanVar(value=True)
                        
                        # Initialize project polygons list
                        self.project_polygons[project_name] = []
                        
                    else:
                        # Add this file to the existing project in project_metadata
                        if project_metadata:
                            project_metadata.add_file_to_project(project_name, item)
                            
                    project_items[project_name].append(item)
                    files_within_polygon += 1
                    
            # Create legend if frame is provided
            if legend_frame:
                self.create_legend(legend_frame, project_items)
                
            # Second pass - process items and update map
            logger.info("Starting second pass - updating map")
            for project_name, items in project_items.items():
                # Track unique tile boundaries
                unique_tile_bounds = {}
                
                # First identify unique tiles in this project
                for item in items:
                    bbox = item.get('boundingBox')
                    if bbox:
                        # Create a tuple key from the bounding box
                        bbox_key = (
                            round(bbox['minY'], 6),
                            round(bbox['minX'], 6),
                            round(bbox['maxY'], 6),
                            round(bbox['maxX'], 6)
                        )
                        
                        if bbox_key not in unique_tile_bounds:
                            tile_id = f"Tile {tile_counter}"
                            unique_tile_bounds[bbox_key] = tile_id
                            tile_counter += 1
                            
                            # Draw LIDAR polygons on map
                            try:
                                # Log the original bounding box coordinates
                                logger.debug(f"Original bounding box for {tile_id}: minY={bbox['minY']}, minX={bbox['minX']}, maxY={bbox['maxY']}, maxX={bbox['maxX']}")
                                
                                polygon_points = [
                                    (bbox['minY'], bbox['minX']),
                                    (bbox['minY'], bbox['maxX']),
                                    (bbox['maxY'], bbox['maxX']),
                                    (bbox['maxY'], bbox['minX']),
                                    (bbox['minY'], bbox['minX'])  # Closing point to complete the polygon
                                ]
                                
                                # Log the polygon points being sent to the map widget
                                logger.debug(f"Setting polygon for {tile_id} with points: {polygon_points}")
                                
                                polygon = self.map_widget.set_polygon(
                                    polygon_points,
                                    fill_color="",
                                    outline_color=self.project_colors[project_name],
                                    border_width=2
                                )
                                
                                # Store attributes directly on the polygon object for tracking
                                polygon.position_list = polygon_points
                                polygon.outline_color = self.project_colors[project_name]
                                polygon.tile_id = tile_id
                                polygon.tile_number = tile_counter - 1
                                polygon.project_name = project_name
                                
                                # Store original polygon data for visibility toggling
                                self.create_original_polygon_data(project_name, polygon_points, self.project_colors[project_name])
                                
                                # Add polygon to tracking structures
                                self.lidar_polygons.append(polygon)
                                self.project_polygons[project_name].append(polygon)
                                
                                # Log the addition for debugging
                                if len(self.project_polygons[project_name]) % 5 == 0:
                                    logger.info(f"Added polygon to project {project_name}, now tracking {len(self.project_polygons[project_name])} polygons")
                                    
                                # Also save to all_project_polygons for visibility toggling
                                if project_name not in self._all_project_polygons:
                                    self._all_project_polygons[project_name] = []
                                    
                                # Store the polygon in the master list
                                self._all_project_polygons[project_name].append(polygon)
                            except Exception as e:
                                logger.error(f"Error drawing polygon: {e}")
                                
                # Update tile count
                tile_count = len(unique_tile_bounds)
                # Store the actual tile count separately so we don't lose it
                self.project_tile_counts[project_name] = tile_count
                logger.info(f"Project {project_name} has {tile_count} unique tiles")
                
                # Update tile count label if it exists
                if project_name in self.project_tile_count_labels:
                    self.project_tile_count_labels[project_name].config(text=f"Tiles: {tile_count}")
                    logger.info(f"Updated tile count label for {project_name} to {tile_count}")
                    
                logger.info(f"Project {project_name} has {tile_count} unique tiles and {len(items)} files")
                
            # Show results message with tile count information
            result_message = f"Found {files_within_polygon} LIDAR files across {len(project_items)} projects ({tile_counter-1} unique tiles)"
            logger.info(result_message)
            
            return {
                "message": result_message,
                "file_count": files_within_polygon,
                "project_count": len(project_items),
                "tile_count": tile_counter-1,
                "projects": project_items
            }
            
        except Exception as e:
            logger.error(f"Error displaying LIDAR results: {str(e)}", exc_info=True)
            return {"error": str(e)}
            
    def create_legend(self, parent_frame, project_items):
        """
        Create a legend showing the projects and their colors.
        
        Args:
            parent_frame: The parent frame to add the legend to
            project_items: Dictionary mapping project names to lists of items
        """
        # Clear any existing legend items
        for widget in parent_frame.winfo_children():
            widget.destroy()
            
        # Create a frame for the legend items
        legend_items_frame = ttk.Frame(parent_frame)
        legend_items_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Add a title
        title_label = ttk.Label(
            legend_items_frame,
            text="LIDAR Projects",
            font=("Helvetica", 12, "bold")
        )
        title_label.pack(fill='x', padx=5, pady=(5, 10))
        
        # Add a project entry for each project
        for project_name in project_items.keys():
            # Create project frame
            project_frame = ttk.Frame(legend_items_frame)
            project_frame.pack(fill='x', padx=5, pady=2)
            
            # Add project label
            label = ttk.Label(
                project_frame,
                text=project_name,
                foreground=self.project_colors[project_name]
            )
            label.pack(side='left', padx=(0, 5))
            
            # Add visibility toggle button
            toggle_btn = ttk.Checkbutton(
                project_frame,
                text="Show Tiles",
                variable=self.project_visibility[project_name],
                command=lambda p=project_name: self.toggle_project_visibility(p)
            )
            toggle_btn.pack(side='right', padx=5)
            
            # Add tile count label
            project_tile_count_label = ttk.Label(
                project_frame,
                text=f"Tiles: {self.project_tile_counts.get(project_name, 0)}"
            )
            project_tile_count_label.pack(side='right', padx=5)
            
            # Store the label for this project
            self.project_tile_count_labels[project_name] = project_tile_count_label
