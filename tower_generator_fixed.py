"""
Tower generator module for creating synthetic tower structures.
"""
import logging
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import traceback

logger = logging.getLogger("SynthTowerApp.TowerGenerator")

class TowerGenerator:
    """
    Class for generating synthetic tower structures.
    """
    def __init__(self, point_cloud_unit_mode="feet", input_unit_mode="ft", transformer=None):
        """
        Initialize the tower generator.
        
        Parameters:
        point_cloud_unit_mode (str): Unit mode for point cloud data ("feet" or "meters")
        input_unit_mode (str): Unit mode for input data ("ft" or "m")
        transformer: Coordinate transformer object for converting lat/lon to projected coordinates
        """
        self.point_cloud_unit_mode = point_cloud_unit_mode
        self.input_unit_mode = input_unit_mode
        self.transformer = transformer
        logger.info(f"Initialized TowerGenerator with units: {point_cloud_unit_mode}")
        
    def convert_units(self, value, from_unit, to_unit):
        """
        Convert value between different units
        
        Parameters:
        value (float): Value to convert
        from_unit (str): Source unit ("feet" or "meters")
        to_unit (str): Target unit ("feet" or "meters")
        
        Returns:
        float: Converted value
        """
        if from_unit == to_unit:
            return value
            
        if from_unit == "feet" and to_unit == "meters":
            return value * 0.3048
        elif from_unit == "meters" and to_unit == "feet":
            return value / 0.3048
        else:
            logger.warning(f"Unsupported unit conversion: {from_unit} to {to_unit}")
            return value
            
    def get_ground_location(self, data):
        """
        Get the ground location for a tower site.
        
        Parameters:
        data (dict): Site data dictionary
        
        Returns:
        list: [x, y, z] coordinates of the ground location
        """
        if isinstance(data.get('ground_samples'), np.ndarray) and len(data['ground_samples']) > 0:
            # Use the average of ground samples
            return np.mean(data['ground_samples'], axis=0)
        else:
            # Use the site's latitude, longitude, and elevation
            lon, lat = data['longitude'], data['latitude']
            
            # Use the transformer from data if available, otherwise use the class transformer
            transformer = data.get('transformer', self.transformer)
            
            if transformer is None:
                logger.warning("No transformer available for coordinate conversion. Using (0,0) as default.")
                x, y = 0, 0
            else:
                try:
                    x, y = transformer.transform(lon, lat)
                except Exception as e:
                    logger.error(f"Error transforming coordinates: {e}")
                    x, y = 0, 0
                    
            return [x, y, data['elevation']]
            
    def generate_cylinder_points(self, location, diameter, height, ring_spacing, point_density):
        """
        Generate cylinder points for the tower body.
        
        Parameters:
        location (list): [x, y, z] coordinates of the base location
        diameter (float): Diameter of the tower
        height (float): Height of the tower
        ring_spacing (float): Spacing between rings
        point_density (int): Number of points per ring
        
        Returns:
        array: Array of points forming the cylinder
        """
        points = []
        for h in np.arange(0, height, ring_spacing):
            points.extend(self.generate_ring_points(location, diameter, h, point_density))
        return np.array(points)
        
    def generate_ring_points(self, location, diameter, height, point_density, color=(255, 255, 255)):
        """
        Generate points for a ring at the specified location.
        
        Parameters:
        location (list): [x, y, z] coordinates of the center location
        diameter (float): Diameter of the ring
        height (float): Height offset from the base location
        point_density (int): Number of points in the ring
        color (tuple): RGB color for the ring points (default: white)
        
        Returns:
        array: Array of points forming the ring
        """
        points = []
        for angle in np.linspace(0, 2*np.pi, point_density, endpoint=False):
            x = location[0] + (diameter / 2) * np.cos(angle)
            y = location[1] + (diameter / 2) * np.sin(angle)
            z = location[2] + height
            points.append([x, y, z, *color])
        return np.array(points)
        
    def generate_base_disc(self, location, diameter, num_points):
        """
        Generate points for the base disc.
        
        Parameters:
        location (list): [x, y, z] coordinates of the center location
        diameter (float): Diameter of the disc
        num_points (int): Number of points in the disc
        
        Returns:
        array: Array of points forming the disc
        """
        points = []
        for _ in range(num_points):
            r = np.sqrt(np.random.uniform(0, 1)) * (diameter / 2)
            theta = np.random.uniform(0, 2*np.pi)
            x = location[0] + r * np.cos(theta)
            y = location[1] + r * np.sin(theta)
            z = location[2]
            points.append([x, y, z, 0, 255, 0])  # Green color for base disc
        return np.array(points)
        
    def generate_center_line_points(self, location, height, ring_spacing, is_donor):
        """
        Generate a vertical line of points through the center of the tower.
        
        Parameters:
        location (list): [x, y, z] coordinates of the base location
        height (float): Height of the tower
        ring_spacing (float): Spacing between points
        is_donor (bool): Whether this is a donor tower
        
        Returns:
        array: Array of points forming the center line
        """
        logger.info(f"Generating center line points for {'donor' if is_donor else 'recipient'} tower")
        
        # Extend 20 feet above tower height
        extended_height = height + 20
        
        # Generate points along the center line
        center_points = []
        for h in np.arange(0, extended_height, ring_spacing):
            # Blue (0,0,255) for donor, Red (255,0,0) for recipient
            color = (0, 0, 255) if is_donor else (255, 0, 0)
            point = [location[0], location[1], location[2] + h, *color]
            center_points.append(point)
        
        return np.array(center_points)
        
    def generate_tower(self, site_key, data):
        """
        Generate a complete tower structure.
        
        Parameters:
        site_key (str): Site identifier
        data (dict): Site data dictionary
        
        Returns:
        array: Array of points forming the complete tower
        """
        try:
            logger.info(f"Generating tower for site: {site_key}")

            # Extract tower parameters
            diameter = float(data['diameter_entry'].get())
            ring_spacing = float(data['ring_spacing_entry'].get())
            
            # Convert height if needed
            height = float(data['height_entry'].get())
            if hasattr(self, 'convert_to_point_cloud_units'):
                height = self.convert_to_point_cloud_units(height, is_height=True)
                
            point_density = int(data['point_density_entry'].get())

            logger.debug(f"Tower parameters: diameter={diameter}, height={height}, ring_spacing={ring_spacing}, point_density={point_density}")

            # Get ground location
            ground_location = self.get_ground_location(data)

            # Generate tower points
            tower_points = self.generate_cylinder_points(ground_location, diameter, height, ring_spacing, point_density)

            # Generate HOI points
            hoi_heights = []
            for h in data['hoi_listbox'].get(0, 'end'):
                h_value = float(h)
                if hasattr(self, 'convert_to_point_cloud_units'):
                    h_value = self.convert_to_point_cloud_units(h_value, is_height=True)
                hoi_heights.append(h_value)
                
            hoi_points = []
            for hoi in hoi_heights:
                hoi_ring = self.generate_ring_points(ground_location, diameter + 0.5, hoi, point_density * 2, color=(255, 0, 0))
                hoi_points.append(hoi_ring)
                
            # Flatten the list of arrays
            if hoi_points:
                hoi_points = np.vstack(hoi_points)
            else:
                hoi_points = np.empty((0, 6))  # Empty array with 6 columns

            # Generate base disc
            base_disc_points = self.generate_base_disc(ground_location, diameter, point_density * 2)

            # Generate center line points
            is_donor = data['type'] == 'DONOR'
            center_line_points = self.generate_center_line_points(
                ground_location,
                height,
                ring_spacing,
                is_donor
            )

            # Combine all points
            all_points = np.vstack((
                tower_points,
                hoi_points,
                base_disc_points,
                center_line_points
            ))

            logger.info(f"Tower points generated for site {site_key}. Total points: {len(all_points)}")
            return all_points
            
        except Exception as e:
            logger.error(f"Error generating tower for site {site_key}: {str(e)}")
            logger.error(f"Detailed traceback: {traceback.format_exc()}")
            raise
            
    def visualize_tower(self, site_id, points):
        """
        Visualize the tower in a 3D plot.
        
        Parameters:
        site_id (str): Site identifier
        points (array): Array of points forming the tower
        
        Returns:
        tuple: (fig, ax) Matplotlib figure and axes objects
        """
        logger.info(f"Visualizing tower for site: {site_id}")
        fig = plt.figure(figsize=(8, 6))
        ax = fig.add_subplot(111, projection='3d')

        x, y, z, r, g, b = points.T
        colors = np.column_stack((r, g, b)) / 255.0

        ax.scatter(x, y, z, c=colors, s=1)

        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        ax.set_title(f'Synthetic Tower for Site {site_id}')

        max_range = np.array([x.max()-x.min(), y.max()-y.min(), z.max()-z.min()]).max() / 2.0
        mid_x = (x.max()+x.min()) * 0.5
        mid_y = (y.max()+y.min()) * 0.5
        mid_z = (z.max()+z.min()) * 0.5
        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

        plt.tight_layout()
        return fig, ax
