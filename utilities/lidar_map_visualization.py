import logging
import tkinter as tk
from tkinter import ttk, messagebox
import tkintermapview
import traceback

# Configure logging
logger = logging.getLogger(__name__)


def initialize_map_widget(map_frame, width=600, height=400, initial_zoom=7):
    """
    Initialize a tkintermapview map widget in the given frame.

    Args:
        map_frame: The frame to place the map widget in
        width: Initial width of the map frame
        height: Initial height of the map frame
        initial_zoom: Initial zoom level for the map

    Returns:
        The initialized map widget
    """
    # Set minimum size for map frame
    map_frame.configure(width=width, height=height)
    map_frame.pack_propagate(False)  # Prevent frame from shrinking

    # Create map widget
    map_widget = tkintermapview.TkinterMapView(map_frame, corner_radius=0)
    map_widget.pack(fill="both", expand=True, padx=5, pady=5)
    map_widget.set_zoom(initial_zoom)

    # Initialize tracking variable for mouse position
    map_widget.last_mouse_down_position = None

    return map_widget

class MapStyleManager:
    """
    Class for managing map styles and style changes.
    """
    def __init__(self, map_widget):
        """
        Initialize the map style manager.

        Args:
            map_widget: The tkintermapview map widget to manage styles for
        """
        self.map_widget = map_widget
        self.style_var = tk.StringVar(value="OpenStreetMap")

        # Define available map styles
        self.map_styles = {
            "OpenStreetMap": {
                "url": "https://a.tile.openstreetmap.org/{z}/{x}/{y}.png",
                "max_zoom": 19
            },
            "Satellite": {
                "url": "https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 22
            },
            "Hybrid": {
                "url": "https://mt0.google.com/vt/lyrs=y&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 22
            },
            "Terrain": {
                "url": "https://mt0.google.com/vt/lyrs=p&hl=en&x={x}&y={y}&z={z}",
                "max_zoom": 20
            }
        }

    def create_style_controls(self, parent_frame):
        """
        Create map style control UI elements.

        Args:
            parent_frame: The parent frame to add the controls to

        Returns:
            The style dropdown widget
        """
        # Add style label
        style_label = ttk.Label(parent_frame, text="Map Style:")
        style_label.pack(side="left", padx=5)

        # Add style dropdown
        style_dropdown = ttk.Combobox(
            parent_frame,
            textvariable=self.style_var,
            values=list(self.map_styles.keys()),
            state="readonly",
            width=15
        )
        style_dropdown.pack(side="left", padx=5)

        # Bind the dropdown to style change handler
        style_dropdown.bind('<<ComboboxSelected>>', self.on_style_change)

        return style_dropdown

    def on_style_change(self, event):
        """
        Handle map style change.

        Args:
            event: The event that triggered the style change
        """
        try:
            style_name = self.style_var.get()
            style = self.map_styles[style_name]

            # Set tile server
            logger.info(f"Changing map style to {style_name} with URL: {style['url']}")
            self.map_widget.set_tile_server(
                style["url"],
                max_zoom=style["max_zoom"]
            )
            logger.info(f"Switched to {style_name} view")

        except Exception as e:
            logger.error(f"Error changing map style: {e}")
            messagebox.showerror("Error", f"Failed to change map style: {str(e)}")


class MapControlPanel:
    """
    Class for creating and managing map control UI elements.
    """
    def __init__(self, map_frame, map_widget):
        """
        Initialize the map control panel.

        Args:
            map_frame: The frame containing the map widget
            map_widget: The tkintermapview map widget
        """
        self.map_frame = map_frame
        self.map_widget = map_widget

        # Create map control frame
        self.control_frame = ttk.Frame(map_frame)
        self.control_frame.pack(fill="x", padx=5, pady=2)

        # Initialize style manager
        self.style_manager = MapStyleManager(map_widget)
        self.style_dropdown = self.style_manager.create_style_controls(self.control_frame)

        # Initialize variables for toggles
        self.labels_var = tk.BooleanVar(value=False)
        self.tile_ids_var = tk.BooleanVar(value=False)

        # Add labels toggle button
        self.labels_button = ttk.Checkbutton(
            self.control_frame,
            text="Show Labels",
            variable=self.labels_var
        )
        self.labels_button.pack(side="left", padx=5)

        # Add tile IDs toggle button
        self.tile_ids_button = ttk.Checkbutton(
            self.control_frame,
            text="Show Tile IDs",
            variable=self.tile_ids_var
        )
        self.tile_ids_button.pack(side="left", padx=5)

    def set_labels_command(self, command):
        """
        Set the command for the labels toggle button.

        Args:
            command: The function to call when the button is toggled
        """
        self.labels_button.configure(command=lambda: command(self.labels_var))

    def set_tile_ids_command(self, command):
        """
        Set the command for the tile IDs toggle button.

        Args:
            command: The function to call when the button is toggled
        """
        self.tile_ids_button.configure(command=lambda: command(self.tile_ids_var))


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

    def create_and_show_tile_labels(self):
        """
        Create and show numbered labels for each LIDAR tile on the map.

        Returns:
            int: Number of tile labels created
        """
        try:
            # Remove any existing tile labels first
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    try:
                        marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting marker: {e}")
                self.tile_markers = []
            else:
                self.tile_markers = []  # Initialize if it doesn't exist

            # Check if we have any polygons to label
            if not hasattr(self, 'lidar_polygons') or not self.lidar_polygons:
                logger.warning("No LIDAR polygons to label")
                return 0

            # Create a new marker for each tile
            logger.info(f"Creating tile labels for {len(self.lidar_polygons)} polygons")
            created_count = 0

            for polygon in self.lidar_polygons:
                # Skip if polygon is not visible
                if not polygon.visible:
                    continue

                # Calculate center point of polygon
                if hasattr(polygon, 'position_list') and len(polygon.position_list) > 0:
                    # Calculate center of polygon
                    lats = [p[0] for p in polygon.position_list]
                    lons = [p[1] for p in polygon.position_list]
                    center_lat = sum(lats) / len(lats)
                    center_lon = sum(lons) / len(lons)

                    # Get tile number if available
                    tile_text = f"#{polygon.tile_number}" if hasattr(polygon, 'tile_number') else "?"

                    # Create marker at center
                    marker = self.map_widget.set_marker(
                        center_lat,
                        center_lon,
                        text=tile_text,
                        text_color="black",
                        marker_color_outside=polygon.outline_color if hasattr(polygon, 'outline_color') else "red",
                        marker_color_circle="white",
                        font=("Helvetica", 8, "bold")
                    )

                    # Add to list of markers
                    self.tile_markers.append(marker)
                    created_count += 1

            logger.info(f"Created {created_count} tile number markers")
            return created_count

        except Exception as e:
            logger.error(f"Error creating tile labels: {e}", exc_info=True)
            traceback.print_exc()
            return 0

    def hide_tile_labels(self):
        """
        Hide all tile labels on the map.
        """
        try:
            if hasattr(self, 'tile_markers'):
                for marker in self.tile_markers:
                    try:
                        marker.delete()
                    except Exception as e:
                        logger.debug(f"Error deleting marker: {e}")
                self.tile_markers = []
                logger.info("Removed all tile markers")
        except Exception as e:
            logger.error(f"Error hiding tile labels: {e}", exc_info=True)

    def toggle_turbine_labels(self, show_labels, turbines):
        """
        Toggle visibility of turbine labels.

        Args:
            show_labels: Boolean indicating whether to show or hide labels
            turbines: List of turbine objects with markers
        """
        try:
            if not turbines:
                logger.warning("No turbines available to label")
                return

            logger.info(f"Toggling turbine labels to {'visible' if show_labels else 'hidden'} for {len(turbines)} turbines")

            for turbine in turbines:
                if hasattr(turbine, 'marker') and turbine.marker:
                    # Update marker text visibility
                    if show_labels:
                        # Show label with turbine info
                        turbine_id = turbine.get('id', 'Unknown')
                        height_ft = turbine.get('height_ft', 0)
                        label_text = f"ID: {turbine_id}\nH: {height_ft}ft"
                        turbine.marker.set_text(label_text)
                    else:
                        # Hide label
                        turbine.marker.set_text("")

            logger.info(f"Turbine labels toggled successfully to {'visible' if show_labels else 'hidden'}")

        except Exception as e:
            logger.error(f"Error toggling turbine labels: {e}", exc_info=True)

    def center_map_on_bounds(self, bounds):
        """
        Center the map on the given bounds.

        Args:
            bounds: Dictionary with minY, maxY, minX, maxX keys
        """
        try:
            if not bounds:
                logger.warning("No bounds provided for centering map")
                return

            # Calculate center point from bounds
            min_y = float(bounds.get('minY', 0) or bounds.get('south', 0))
            max_y = float(bounds.get('maxY', 0) or bounds.get('north', 0))
            min_x = float(bounds.get('minX', 0) or bounds.get('west', 0))
            max_x = float(bounds.get('maxX', 0) or bounds.get('east', 0))

            center_lat = (min_y + max_y) / 2
            center_lon = (min_x + max_x) / 2

            # Set map position to center of bounds
            self.map_widget.set_position(center_lat, center_lon)

            # Calculate appropriate zoom level based on bounds size
            lat_span = abs(max_y - min_y)
            lon_span = abs(max_x - min_x)

            # Add padding to ensure all bounds are visible
            lat_span *= 1.2  # Add 20% padding
            lon_span *= 1.2  # Add 20% padding

            # Determine zoom level based on the larger span
            max_span = max(lat_span, lon_span)

            # More granular zoom levels for better visibility
            if max_span < 0.005:  # Very small area
                zoom = 16
            elif max_span < 0.01:
                zoom = 15
            elif max_span < 0.02:
                zoom = 14
            elif max_span < 0.05:
                zoom = 13
            elif max_span < 0.1:
                zoom = 12
            elif max_span < 0.2:
                zoom = 11
            elif max_span < 0.5:
                zoom = 10
            elif max_span < 1.0:
                zoom = 9
            else:
                zoom = 8

            # Ensure zoom is not too high or too low
            zoom = max(min(zoom, 16), 6)

            self.map_widget.set_zoom(zoom)
            logger.info(f"Centered map on bounds: ({center_lat:.6f}, {center_lon:.6f}), zoom: {zoom}")
            logger.info(f"Bounds: minY={min_y}, maxY={max_y}, minX={min_x}, maxX={max_x}, span={max_span}")

        except Exception as e:
            logger.error(f"Error centering map on bounds: {e}", exc_info=True)
