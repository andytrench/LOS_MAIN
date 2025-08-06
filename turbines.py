import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import logging
import json
import pandas as pd
import os
import sys
import subprocess
import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image as PILImage
import time
from log_config import setup_logging
from utilities.finder_utils import safe_open_directory, safe_open_file

# Set up logging
logger = setup_logging(__name__)

class TopDownVisualizer:
    """Class to create a top-down visualization of the path and turbines"""

    def __init__(self, elevation_analyzer):
        """Initialize with reference to the ElevationAnalyzer instance

        Args:
            elevation_analyzer: Instance of ElevationAnalyzer containing path and turbine data
        """
        self.elevation_analyzer = elevation_analyzer
        self.EARTH_RADIUS = 20902231  # Earth radius in feet (same as in ElevationAnalyzer)

    def generate_top_down_view(self, save_to_file=False, output_dir=None):
        """Generate a top-down view showing turbines relative to the path using Matplotlib.

        Args:
            save_to_file (bool): Whether to save the figure to a file
            output_dir (str): Directory to save the figure to, if save_to_file is True

        Returns:
            str: Path to the saved figure if save_to_file is True, None otherwise
        """
        try:
            # Create a new top-level window if we're not just saving to file
            if not save_to_file:
                view_window = tk.Toplevel()
                view_window.title("Top Down View")

            # Create matplotlib figure with horizontal layout (wider than tall)
            fig, ax = plt.subplots(figsize=(18, 9))  # Horizontal layout

            if not hasattr(self.elevation_analyzer, 'turbines') or not self.elevation_analyzer.turbines:
                logger.warning("No turbines available for top-down view")
                if save_to_file:
                    return None
                else:
                    messagebox.showwarning("No Data", "No turbine data available for visualization.")
                    return None

            # Get path data
            start_coords = self.elevation_analyzer.start_coords
            end_coords = self.elevation_analyzer.end_coords
            total_distance_m = self.elevation_analyzer.distances[-1]
            total_distance_ft = total_distance_m * 3.28084

            # Try to get frequency from tower parameters
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_params = json.load(f)
                    frequency_ghz = float(tower_params['general_parameters']['frequency_ghz'])
            except Exception as e:
                logger.warning(f"Could not load frequency from tower parameters: {e}")
                frequency_ghz = 11.0  # Default frequency

            # Process turbine data for plotting
            turbine_data = []
            max_distance_from_path = 0

            for turbine in self.elevation_analyzer.turbines:
                try:
                    # Get turbine parameters and convert to proper units
                    height_m = float(turbine.get('total_height_m', 100))
                    height_ft = height_m * 3.28084
                    rotor_diameter_m = float(turbine.get('rotor_diameter_m', 100))
                    rotor_diameter_ft = rotor_diameter_m * 3.28084
                    rotor_radius_ft = rotor_diameter_ft / 2

                    # Calculate hub height (use provided hub height if available)
                    if turbine.get('hub_height_m'):
                        hub_height_m = float(turbine['hub_height_m'])
                        hub_height_ft = hub_height_m * 3.28084
                    else:
                        # If no hub height provided, calculate it as total height minus rotor radius
                        hub_height_ft = height_ft - rotor_radius_ft

                    # Calculate turbine position along path
                    turbine_lat, turbine_lon = turbine['latitude'], turbine['longitude']
                    turbine_distance_along = self.elevation_analyzer._calculate_distance_along_path(
                        (turbine_lat, turbine_lon),
                        start_coords,
                        end_coords
                    )
                    distance_along_ft = turbine_distance_along * 3.28084
                    distance_ratio = turbine_distance_along / total_distance_m

                    # Calculate perpendicular distance from path
                    perpendicular_distance = self.elevation_analyzer._calculate_perpendicular_distance(
                        (turbine_lat, turbine_lon),
                        start_coords,
                        end_coords
                    )
                    perpendicular_distance_ft = perpendicular_distance * 3.28084  # Convert to feet

                    # Update maximum distance for plotting limits
                    max_distance_from_path = max(max_distance_from_path, abs(perpendicular_distance_ft))

                    # Calculate Fresnel radius at this position
                    d1_km = (distance_along_ft / 3280.84)  # Distance from start in km
                    d2_km = (total_distance_ft / 3280.84) - d1_km  # Distance from end in km
                    fresnel_radius = self.elevation_analyzer.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                    # Calculate clearances
                    # Calculate LOS height at turbine position (for reference)
                    if hasattr(self.elevation_analyzer, 'site_a_data') and hasattr(self.elevation_analyzer, 'site_b_data'):
                        los_height = self.elevation_analyzer.site_a_data[1] + (
                            self.elevation_analyzer.site_b_data[1] - self.elevation_analyzer.site_a_data[1]
                        ) * distance_ratio

                        # Calculate earth curvature bulge
                        bulge = (distance_along_ft * (total_distance_ft - distance_along_ft)) / (2 * self.EARTH_RADIUS)
                        los_height_curved = los_height - bulge

                        # Find ground elevation at turbine position
                        index = int(distance_ratio * (len(self.elevation_analyzer.elevation_data) - 1))
                        ground_elev = self.elevation_analyzer.elevation_data[index] if 0 <= index < len(self.elevation_analyzer.elevation_data) else 0

                        # Calculate center height
                        center_height = ground_elev + hub_height_ft

                        # Calculate shortest distance from rotor center to curved path
                        vertical_distance = abs(los_height_curved - center_height)
                        horizontal_distance = abs(perpendicular_distance_ft)
                        center_to_path = math.sqrt(horizontal_distance**2 + vertical_distance**2)

                        # Calculate clearances
                        clearance_straight = center_to_path - rotor_radius_ft
                        clearance_curved = center_to_path - rotor_radius_ft
                        clearance_fresnel = center_to_path - rotor_radius_ft - fresnel_radius
                    else:
                        clearance_straight = 'N/A'
                        clearance_curved = 'N/A'
                        clearance_fresnel = 'N/A'

                    # Store all the data we need for drawing
                    turbine_data.append({
                        'id': turbine.get('id', 'Unknown'),
                        'distance_along_ft': distance_along_ft,
                        'distance_from_path_ft': perpendicular_distance_ft,
                        'rotor_radius_ft': rotor_radius_ft,
                        'fresnel_radius': fresnel_radius,
                        'clearance_straight': clearance_straight,
                        'clearance_curved': clearance_curved,
                        'clearance_fresnel': clearance_fresnel
                    })
                except Exception as e:
                    logger.error(f"Error processing turbine for top-down view: {e}")
                    continue

            # Add padding to the maximum distance
            max_distance_from_path += max_distance_from_path * 0.25

            # Calculate compression factor based on path length vs display width
            # This ensures the path fits on the diagram
            horizontal_compression = min(1.0, 15000 / total_distance_ft)  # Limit compression to 1.0 max

            # Set up the plot for horizontal orientation
            ax.set_ylim(-max_distance_from_path, max_distance_from_path)
            ax.set_xlim(-total_distance_ft * horizontal_compression * 0.05, total_distance_ft * horizontal_compression * 1.05)
            ax.grid(True, linestyle='--', alpha=0.7)
            ax.set_ylabel('Distance from Path (ft)')
            ax.set_xlabel('Distance Along Path (ft)')
            ax.set_title('Top Down View of Path and Turbines')

            # Draw path as a horizontal line through the center
            ax.axhline(y=0, color='blue', linestyle='-', linewidth=2, label='Path')

            # Draw donor and recipient markers
            if hasattr(self.elevation_analyzer, 'site_a_data') and hasattr(self.elevation_analyzer, 'site_b_data'):
                # Get site IDs if available
                site_a_id = getattr(self.elevation_analyzer, 'site_a_id', 'Donor')
                site_b_id = getattr(self.elevation_analyzer, 'site_b_id', 'Recipient')

                # Donor site at left (0, 0)
                ax.scatter([0], [0], color='blue', s=100, zorder=5, label='Donor')
                ax.text(0, max_distance_from_path * 0.1, f"Site {site_a_id}",
                      fontsize=10, color='blue', ha='center', va='bottom',
                      bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))

                # Recipient site at right (compressed_distance, 0)
                compressed_end = total_distance_ft * horizontal_compression
                ax.scatter([compressed_end], [0], color='red', s=100, zorder=5, label='Recipient')
                ax.text(compressed_end, max_distance_from_path * 0.1, f"Site {site_b_id}",
                      fontsize=10, color='red', ha='center', va='bottom',
                      bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2'))

            # Calculate Fresnel zone width at various points along the path
            path_points = 100
            x_positions = np.linspace(0, total_distance_ft * horizontal_compression, path_points)
            fresnel_upper = []
            fresnel_lower = []

            total_dist_km = total_distance_ft / 3280.84  # Convert to km

            for i, x_pos in enumerate(x_positions):
                # Calculate actual distance ratio
                distance_ratio = x_pos / (total_distance_ft * horizontal_compression)

                # Calculate distance in feet and km
                actual_distance_ft = distance_ratio * total_distance_ft
                d1_km = (actual_distance_ft / 3280.84)
                d2_km = total_dist_km - d1_km

                # Calculate Fresnel radius
                radius = self.elevation_analyzer.calculate_fresnel_radius(d1_km, d2_km, frequency_ghz)

                fresnel_upper.append([x_pos, radius])
                fresnel_lower.append([x_pos, -radius])

            # Convert to numpy arrays for plotting
            fresnel_upper = np.array(fresnel_upper)
            fresnel_lower = np.array(fresnel_lower)

            # Plot Fresnel zone boundaries
            ax.plot(fresnel_upper[:, 0], fresnel_upper[:, 1], '#FF69B4', linewidth=2, label='Fresnel Zone')
            ax.plot(fresnel_lower[:, 0], fresnel_lower[:, 1], '#FF69B4', linewidth=2)

            # Draw turbines
            # Create a label manager to track label positions and prevent overlaps
            label_positions = []  # List to track all label bounding boxes

            def add_label_with_collision_avoidance(x, y, text, fontsize, color, ha, va, bbox_props, ax, max_attempts=10, offset_step=30):
                """Add a text label with collision avoidance

                Args:
                    x, y: Initial position
                    text: Label text
                    fontsize: Font size
                    color: Text color
                    ha, va: Horizontal and vertical alignment
                    bbox_props: Box properties dict
                    ax: Matplotlib axis
                    max_attempts: Maximum number of position attempts
                    offset_step: Distance to move for each attempt

                Returns:
                    Matplotlib text object
                """
                original_x, original_y = x, y

                # Try different positions until we find one that doesn't overlap
                for attempt in range(max_attempts):
                    # Calculate current position (move further with each attempt)
                    if attempt > 0:
                        # Alternate between moving up/down or left/right
                        if attempt % 2 == 1:  # Odd attempts: vertical shifts
                            if va == 'center':  # For horizontal lines
                                # Move up or down based on attempt number
                                y = original_y + (offset_step * ((attempt + 1) // 2) * (1 if attempt % 4 < 2 else -1))
                            else:  # For other alignments
                                # Increase offset in the direction consistent with alignment
                                offset = offset_step * ((attempt + 1) // 2)
                                if va == 'bottom':
                                    y = original_y + offset
                                elif va == 'top':
                                    y = original_y - offset
                        else:  # Even attempts: horizontal shifts
                            if ha == 'center':  # For vertical lines
                                # Move left or right based on attempt number
                                x = original_x + (offset_step * (attempt // 2) * (1 if attempt % 4 < 2 else -1))
                            else:  # For other alignments
                                # Increase offset in the direction consistent with alignment
                                offset = offset_step * (attempt // 2)
                                if ha == 'left':
                                    x = original_x + offset
                                elif ha == 'right':
                                    x = original_x - offset

                    # Create a temporary text object to check its bounding box
                    test_text = ax.text(x, y, text, fontsize=fontsize, color=color,
                                       horizontalalignment=ha, verticalalignment=va,
                                       bbox=bbox_props)

                    # Get the rendered bounding box
                    renderer = ax.figure.canvas.get_renderer()
                    bbox = test_text.get_window_extent(renderer=renderer).transformed(ax.transData.inverted())

                    # Check for collision with existing labels
                    collision = False
                    for existing_bbox in label_positions:
                        if bbox.overlaps(existing_bbox):
                            collision = True
                            break

                    if not collision:
                        # No collision, keep this position
                        label_positions.append(bbox)
                        return test_text
                    else:
                        # Remove the test text and try again
                        test_text.remove()

                # If we've exhausted all attempts, place it at original position anyway
                final_text = ax.text(original_x, original_y, text, fontsize=fontsize, color=color,
                                   horizontalalignment=ha, verticalalignment=va,
                                   bbox=bbox_props)

                # Get final bbox and add to positions list
                renderer = ax.figure.canvas.get_renderer()
                final_bbox = final_text.get_window_extent(renderer=renderer).transformed(ax.transData.inverted())
                label_positions.append(final_bbox)

                return final_text

            for i, turbine in enumerate(turbine_data):
                try:
                    # Get position data
                    distance_along = turbine['distance_along_ft'] * horizontal_compression  # Compress along path
                    distance_from_path = turbine['distance_from_path_ft']
                    rotor_radius = turbine['rotor_radius_ft']
                    fresnel_radius = turbine['fresnel_radius']
                    turbine_id = turbine['id']

                    # Draw turbine marker as a simple purple dot
                    ax.scatter([distance_along], [distance_from_path],
                              s=100,
                              marker='o',
                              color='purple',
                              label="Turbine" if i == 0 else "",
                              zorder=10)

                    # Draw rotor circle (will be an oval due to compression)
                    rotor_circle = plt.Circle((distance_along, distance_from_path),
                                             rotor_radius,
                                             fill=False,
                                             color='purple',
                                             linestyle='-',
                                             linewidth=1.5)
                    ax.add_patch(rotor_circle)

                    # Add turbine ID label with collision avoidance
                    turbine_id_bbox = dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.2')
                    add_label_with_collision_avoidance(
                        distance_along, distance_from_path + rotor_radius + 200,
                        f"{turbine_id}", 10, 'purple', 'center', 'bottom',
                        turbine_id_bbox, ax
                    )

                    # Calculate the endpoint for the measurement line at the edge of the rotor circle
                    # If the turbine is above the path, subtract the radius from the y-coordinate
                    # If the turbine is below the path, add the radius to the y-coordinate
                    if distance_from_path > 0:
                        line_end_y = distance_from_path - rotor_radius
                    else:
                        line_end_y = distance_from_path + rotor_radius

                    # Draw measurement line to path (vertical line) - terminate at rotor edge
                    ax.plot([distance_along, distance_along], [0, line_end_y],
                           color='cyan', linestyle='--', linewidth=1.5)

                    # Calculate initial positions for labels
                    horizontal_offset = 150 * (1 + i % 4)  # Cycle through 4 different positions
                    if i % 2 == 0:
                        text_x = distance_along + horizontal_offset
                        ha = 'left'
                    else:
                        text_x = distance_along - horizontal_offset
                        ha = 'right'

                    text_y = distance_from_path / 2  # Halfway between path and turbine

                    # Add straight clearance text with collision avoidance
                    if isinstance(turbine['clearance_straight'], (int, float)):
                        straight_clearance = f"{turbine['clearance_straight']:.0f}ft"
                        straight_bbox = dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3')
                        add_label_with_collision_avoidance(
                            text_x, text_y,
                            f"straight: {straight_clearance}", 8, 'black', ha, 'center',
                            straight_bbox, ax
                        )

                    # Add curved clearance with different offset - with collision avoidance
                    if isinstance(turbine['clearance_curved'], (int, float)):
                        curved_clearance = f"{turbine['clearance_curved']:.0f}ft"
                        curved_offset = 150 * (1 + (i + 1) % 4)  # Different pattern
                        if (i + 1) % 2 == 0:
                            curved_x = distance_along + curved_offset
                            curved_ha = 'left'
                        else:
                            curved_x = distance_along - curved_offset
                            curved_ha = 'right'

                        curved_bbox = dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.3')
                        add_label_with_collision_avoidance(
                            curved_x, text_y,
                            f"w/curve: {curved_clearance}", 8, 'black', curved_ha, 'center',
                            curved_bbox, ax
                        )

                    # Draw line from path to Fresnel zone at turbine position
                    fresnel_edge_y = fresnel_radius * (1 if distance_from_path > 0 else -1)
                    ax.plot([distance_along, distance_along], [0, fresnel_edge_y],
                           color='#FF69B4', linestyle=':', linewidth=1)

                    # Add Fresnel clearance with collision avoidance
                    if isinstance(turbine['clearance_fresnel'], (int, float)):
                        fresnel_clearance = f"{turbine['clearance_fresnel']:.0f}ft"
                        fresnel_offset = 150 * (1 + (i + 2) % 4)  # Different pattern

                        # Position the label further away from the Fresnel line
                        # If the turbine is above the path, place label above the Fresnel line
                        # If the turbine is below the path, place label below the Fresnel line
                        if distance_from_path >= 0:  # Turbine above path
                            fresnel_label_y = fresnel_edge_y + 100  # Above Fresnel line
                        else:  # Turbine below path
                            fresnel_label_y = fresnel_edge_y - 100  # Below Fresnel line

                        if (i + 2) % 2 == 0:
                            fresnel_x = distance_along + fresnel_offset
                            fresnel_ha = 'left'
                        else:
                            fresnel_x = distance_along - fresnel_offset
                            fresnel_ha = 'right'

                        # Use a more visible background with border
                        fresnel_bbox = dict(facecolor='white', alpha=0.9, boxstyle='round,pad=0.3',
                                         edgecolor='#FF69B4', linewidth=0.5)

                        fresnel_text = add_label_with_collision_avoidance(
                            fresnel_x, fresnel_label_y,
                            f"Fresnel: {fresnel_clearance}", 8, '#FF69B4', fresnel_ha, 'center',
                            fresnel_bbox, ax
                        )

                        # Get the final position of the label for the connecting line
                        fresnel_text_pos = fresnel_text.get_position()

                        # Add a small connecting line to show what the label refers to
                        ax.plot([fresnel_text_pos[0], distance_along], [fresnel_text_pos[1], fresnel_edge_y],
                               color='#FF69B4', linestyle=':', linewidth=0.5)

                except Exception as e:
                    logger.error(f"Error drawing turbine {turbine['id']}: {e}")

            # Add legend with better positioning
            ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))

            # Adjust layout to prevent label cutoff
            plt.tight_layout()

            # Save to file if requested
            if save_to_file:
                if output_dir is None:
                    output_dir = "temp"

                # Create output directory if it doesn't exist
                if not os.path.exists(output_dir):
                    os.makedirs(output_dir)

                # Generate filename
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filepath = os.path.join(output_dir, f"top_down_view_{timestamp}.png")

                # Save figure
                fig.savefig(filepath, dpi=100, bbox_inches='tight')
                logger.info(f"Saved top down view to {filepath}")
                plt.close(fig)
                return filepath

            # Display in window if not saving to file
            canvas = FigureCanvasTkAgg(fig, master=view_window)
            canvas.draw()
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(fill=tk.BOTH, expand=True)

            # Add scrollbars if needed
            if canvas_widget.winfo_reqwidth() > view_window.winfo_screenwidth():
                scrollbar = ttk.Scrollbar(view_window, orient="horizontal")
                scrollbar.pack(side="bottom", fill="x")
                canvas_widget.configure(xscrollcommand=scrollbar.set)
                scrollbar.configure(command=canvas_widget.xview)

            return None

        except Exception as e:
            logger.error(f"Error generating top down view: {e}", exc_info=True)
            if not save_to_file and 'view_window' in locals():
                view_window.destroy()
            return None

class TurbineDataViewer:
    def __init__(self, parent, turbines):
        """Initialize the turbine data viewer with turbines data"""
        self.parent = parent
        self.turbines = turbines

    def show_data(self):
        """Display turbine data in a tabbed popup window"""
        if not self.turbines:
            messagebox.showwarning("No Data", "No turbine data available to display")
            return

        # Create popup window
        self.popup = tk.Toplevel(self.parent)
        self.popup.title("Wind Turbine Data")
        self.popup.geometry("800x600")
        self.popup.transient(self.parent)
        self.popup.grab_set()

        # Create notebook (tabbed interface)
        notebook = ttk.Notebook(self.popup)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Create overview tab with all turbines
        overview_frame = ttk.Frame(notebook)
        notebook.add(overview_frame, text="Overview")

        # Add export button at the top
        export_frame = ttk.Frame(self.popup)
        export_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Button(
            export_frame,
            text="Export Turbine Data",
            command=self.export_turbine_data
        ).pack(side=tk.RIGHT, padx=5, pady=5)

        # Create a treeview for the overview
        columns = ("id", "lat", "lon", "height", "diameter", "project", "distance")
        overview_tree = ttk.Treeview(overview_frame, columns=columns, show="headings")

        # Configure column headings
        overview_tree.heading("id", text="ID")
        overview_tree.heading("lat", text="Latitude")
        overview_tree.heading("lon", text="Longitude")
        overview_tree.heading("height", text="Height (m)")
        overview_tree.heading("diameter", text="Rotor Ø (m)")
        overview_tree.heading("project", text="Project")
        overview_tree.heading("distance", text="Distance (m)")

        # Configure column widths
        overview_tree.column("id", width=80)
        overview_tree.column("lat", width=100)
        overview_tree.column("lon", width=100)
        overview_tree.column("height", width=80)
        overview_tree.column("diameter", width=80)
        overview_tree.column("project", width=150)
        overview_tree.column("distance", width=100)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(overview_frame, orient=tk.VERTICAL, command=overview_tree.yview)
        overview_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        overview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Populate overview treeview
        for i, turbine in enumerate(self.turbines):
            try:
                # Get basic turbine data
                turbine_id = turbine.get('id') or turbine.get('case_id', f"Turbine {i+1}")
                lat = turbine.get('latitude') or turbine.get('ylat', 'N/A')
                lon = turbine.get('longitude') or turbine.get('xlong', 'N/A')
                height = turbine.get('total_height_m') or turbine.get('t_ttlh', 'N/A')
                diameter = turbine.get('rotor_diameter_m') or turbine.get('t_rd', 'N/A')
                project = turbine.get('project_name') or turbine.get('p_name', 'N/A')

                # Calculate or retrieve distance information
                distance = 'N/A'
                if turbine.get('distance_from_path_ft'):
                    # Convert feet to meters
                    distance = f"{turbine['distance_from_path_ft'] * 0.3048:.1f}"

                overview_tree.insert("", "end", values=(
                    turbine_id, lat, lon, height, diameter, project, distance
                ))
            except Exception as e:
                logger.error(f"Error adding turbine to overview: {e}")

        # Create individual tabs for each turbine
        for i, turbine in enumerate(self.turbines):
            try:
                turbine_id = turbine.get('id') or turbine.get('case_id', f"Turbine {i+1}")
                turbine_frame = ttk.Frame(notebook)
                notebook.add(turbine_frame, text=f"Turbine {turbine_id}")

                # Create a scrollable frame for the turbine details
                canvas = tk.Canvas(turbine_frame)
                scrollbar = ttk.Scrollbar(turbine_frame, orient=tk.VERTICAL, command=canvas.yview)
                scrollable_frame = ttk.Frame(canvas)

                scrollable_frame.bind(
                    "<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
                )

                canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
                canvas.configure(yscrollcommand=scrollbar.set)

                canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Add all turbine properties as labels
                row = 0
                for key, value in sorted(turbine.items()):
                    # Skip internal keys or empty values
                    if key.startswith('_') or value is None:
                        continue

                    # Create a formatted key name
                    formatted_key = key.replace('_', ' ').title()

                    # Format certain values
                    formatted_value = value
                    if key.endswith('_m') and isinstance(value, (int, float)):
                        formatted_value = f"{value} m ({value * 3.28084:.1f} ft)"
                    elif key.endswith('_ft') and isinstance(value, (int, float)):
                        formatted_value = f"{value} ft ({value * 0.3048:.1f} m)"

                    # Create label and value
                    ttk.Label(
                        scrollable_frame,
                        text=formatted_key,
                        font=("Arial", 10, "bold")
                    ).grid(row=row, column=0, sticky="w", padx=10, pady=2)

                    ttk.Label(
                        scrollable_frame,
                        text=str(formatted_value),
                        wraplength=400
                    ).grid(row=row, column=1, sticky="w", padx=10, pady=2)

                    row += 1
            except Exception as e:
                logger.error(f"Error creating tab for turbine {i}: {e}")

    def export_turbine_data(self):
        """Export turbine data to CSV, JSON, and text files"""
        try:
            if not self.turbines:
                messagebox.showwarning("No Data", "No turbine data available to export")
                return

            # Ask for directory to save files
            output_dir = filedialog.askdirectory(
                title="Select folder to save turbine data",
                initialdir=os.path.expanduser("~")
            )

            if not output_dir:
                return

            # Create CSV file
            csv_path = os.path.join(output_dir, "turbine_data.csv")

            # Convert turbines to DataFrame
            df = pd.DataFrame(self.turbines)
            df.to_csv(csv_path, index=False)

            # Save JSON file with pretty formatting
            json_path = os.path.join(output_dir, "turbine_data.json")
            with open(json_path, 'w') as f:
                json.dump(self.turbines, f, indent=2)

            # Create nicely formatted text file
            text_path = os.path.join(output_dir, "turbine_data.txt")
            with open(text_path, 'w') as f:
                # Write header
                f.write("=" * 80 + "\n")
                f.write("WIND TURBINE DATA REPORT\n")
                f.write(f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")

                f.write(f"Total Turbines: {len(self.turbines)}\n\n")

                # Write summary table
                f.write("-" * 80 + "\n")
                f.write(f"{'ID':<12} {'Latitude':<12} {'Longitude':<12} {'Height (m)':<12} {'Diameter (m)':<12} {'Project':<20}\n")
                f.write("-" * 80 + "\n")

                for turbine in self.turbines:
                    # Get basic data with fallbacks
                    turbine_id = turbine.get('id') or turbine.get('case_id', 'Unknown')
                    lat = turbine.get('latitude') or turbine.get('ylat', 'N/A')
                    lon = turbine.get('longitude') or turbine.get('xlong', 'N/A')
                    height = turbine.get('total_height_m') or turbine.get('t_ttlh', 'N/A')
                    diameter = turbine.get('rotor_diameter_m') or turbine.get('t_rd', 'N/A')
                    project = turbine.get('project_name') or turbine.get('p_name', 'N/A')

                    # Format numeric values
                    try:
                        lat_fmt = f"{float(lat):.6f}" if isinstance(lat, (int, float)) else lat
                        lon_fmt = f"{float(lon):.6f}" if isinstance(lon, (int, float)) else lon
                        height_fmt = f"{float(height):.1f}" if isinstance(height, (int, float)) else height
                        diameter_fmt = f"{float(diameter):.1f}" if isinstance(diameter, (int, float)) else diameter
                    except (ValueError, TypeError):
                        lat_fmt, lon_fmt = lat, lon
                        height_fmt, diameter_fmt = height, diameter

                    # Write summary line
                    f.write(f"{str(turbine_id):<12} {lat_fmt:<12} {lon_fmt:<12} {height_fmt:<12} {diameter_fmt:<12} {str(project)[:19]:<20}\n")

                f.write("-" * 80 + "\n\n")

                # Write detailed information for each turbine
                for i, turbine in enumerate(self.turbines):
                    turbine_id = turbine.get('id') or turbine.get('case_id', f"Turbine {i+1}")
                    f.write(f"TURBINE DETAILS: {turbine_id}\n")
                    f.write("-" * 80 + "\n")

                    # Get location information
                    lat = turbine.get('latitude') or turbine.get('ylat', 'N/A')
                    lon = turbine.get('longitude') or turbine.get('xlong', 'N/A')
                    f.write(f"Location:      {lat}, {lon}\n")

                    # Get physical characteristics
                    height_m = turbine.get('total_height_m') or turbine.get('t_ttlh', 'N/A')
                    if isinstance(height_m, (int, float)):
                        f.write(f"Total Height:   {height_m:.1f} m ({height_m * 3.28084:.1f} ft)\n")
                    else:
                        f.write(f"Total Height:   {height_m}\n")

                    diameter_m = turbine.get('rotor_diameter_m') or turbine.get('t_rd', 'N/A')
                    if isinstance(diameter_m, (int, float)):
                        f.write(f"Rotor Diameter: {diameter_m:.1f} m ({diameter_m * 3.28084:.1f} ft)\n")
                    else:
                        f.write(f"Rotor Diameter: {diameter_m}\n")

                    hub_height_m = turbine.get('hub_height_m') or turbine.get('t_hh', 'N/A')
                    if isinstance(hub_height_m, (int, float)):
                        f.write(f"Hub Height:     {hub_height_m:.1f} m ({hub_height_m * 3.28084:.1f} ft)\n")
                    else:
                        f.write(f"Hub Height:     {hub_height_m}\n")

                    # Get project information
                    project = turbine.get('project_name') or turbine.get('p_name', 'N/A')
                    capacity = turbine.get('capacity_kw') or turbine.get('t_cap', 'N/A')
                    f.write(f"Project:        {project}\n")
                    f.write(f"Capacity:       {capacity} kW\n")

                    # Get manufacturer information
                    manufacturer = turbine.get('manufacturer') or turbine.get('t_manu', 'N/A')
                    model = turbine.get('model') or turbine.get('t_model', 'N/A')
                    f.write(f"Manufacturer:   {manufacturer}\n")
                    f.write(f"Model:          {model}\n")

                    # Get distance information if available
                    distance_ft = turbine.get('distance_from_path_ft', None)
                    if distance_ft is not None and isinstance(distance_ft, (int, float)):
                        distance_m = distance_ft * 0.3048
                        f.write(f"Path Distance:  {distance_m:.1f} m ({distance_ft:.1f} ft)\n")

                    # Add clearance information if available
                    clearance_straight = turbine.get('clearance_straight_ft', None)
                    if clearance_straight is not None and isinstance(clearance_straight, (int, float)):
                        f.write(f"Clearance:      {clearance_straight:.1f} ft ({clearance_straight * 0.3048:.1f} m)\n")

                    # Add a separator between turbines
                    f.write("\n" + "=" * 80 + "\n\n")

            # Build success message
            success_message = "Turbine data exported to:\n"
            success_message += f"CSV: {csv_path}\n"
            success_message += f"JSON: {json_path}\n"
            success_message += f"Text: {text_path}"

            # Show success message
            messagebox.showinfo(
                "Export Successful",
                success_message
            )

            # Open the directory using our safe utility
            safe_open_directory(output_dir)

        except Exception as e:
            logger.error(f"Error exporting turbine data: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to export turbine data: {str(e)}")

def display_turbine_data(parent, turbines):
    """Display turbine data in a tabbed popup window"""
    try:
        # Create and show the data viewer
        viewer = TurbineDataViewer(parent, turbines)
        viewer.show_data()
    except Exception as e:
        logger.error(f"Error displaying turbine data: {e}", exc_info=True)
        messagebox.showerror("Error", f"Failed to display turbine data: {str(e)}")

def generate_top_down_view(elevation_analyzer, save_to_file=False, output_dir=None):
    """Generate a top-down visualization of the path and turbines

    Args:
        elevation_analyzer: Instance of ElevationAnalyzer containing path and turbine data
        save_to_file (bool): Whether to save the figure to a file
        output_dir (str): Directory to save the figure to, if save_to_file is True

    Returns:
        str: Path to the saved figure if save_to_file is True, None otherwise
    """
    try:
        visualizer = TopDownVisualizer(elevation_analyzer)
        return visualizer.generate_top_down_view(save_to_file, output_dir)
    except Exception as e:
        logger.error(f"Error generating top-down view: {e}", exc_info=True)
        if not save_to_file:
            messagebox.showerror("Error", f"Failed to generate top-down view: {str(e)}")
        return None
