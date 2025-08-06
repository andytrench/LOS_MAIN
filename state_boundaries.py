"""
State Boundaries Module

This module provides functions for working with US state boundaries.
It can download and process TIGER/Line shapefiles from the US Census Bureau,
and provides functions for determining which state a point falls within.
"""

import os
import logging
import json
import tempfile
import zipfile
from urllib.request import urlretrieve
import geopandas as gpd
from shapely.geometry import Point, shape
import pandas as pd

logger = logging.getLogger(__name__)

# Define regions for US states
STATE_REGIONS = {
    'AL': 'Southeast', 'AK': 'West', 'AZ': 'Southwest', 'AR': 'Southeast',
    'CA': 'West', 'CO': 'West', 'CT': 'Northeast', 'DE': 'Northeast',
    'FL': 'Southeast', 'GA': 'Southeast', 'HI': 'West', 'ID': 'West',
    'IL': 'Midwest', 'IN': 'Midwest', 'IA': 'Midwest', 'KS': 'Midwest',
    'KY': 'Southeast', 'LA': 'Southeast', 'ME': 'Northeast', 'MD': 'Northeast',
    'MA': 'Northeast', 'MI': 'Midwest', 'MN': 'Midwest', 'MS': 'Southeast',
    'MO': 'Midwest', 'MT': 'West', 'NE': 'Midwest', 'NV': 'West',
    'NH': 'Northeast', 'NJ': 'Northeast', 'NM': 'Southwest', 'NY': 'Northeast',
    'NC': 'Southeast', 'ND': 'Midwest', 'OH': 'Midwest', 'OK': 'Southwest',
    'OR': 'West', 'PA': 'Northeast', 'RI': 'Northeast', 'SC': 'Southeast',
    'SD': 'Midwest', 'TN': 'Southeast', 'TX': 'Southwest', 'UT': 'West',
    'VT': 'Northeast', 'VA': 'Southeast', 'WA': 'West', 'WV': 'Southeast',
    'WI': 'Midwest', 'WY': 'West', 'DC': 'Northeast', 'PR': 'Southeast'
}

class StateBoundaries:
    """Class for working with US state boundaries"""
    
    def __init__(self, data_dir=None):
        """Initialize the StateBoundaries class
        
        Args:
            data_dir (str, optional): Directory to store boundary data. Defaults to None.
        """
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), 'data')
        self.geojson_path = os.path.join(self.data_dir, 'us_states.geojson')
        self.simplified_path = os.path.join(self.data_dir, 'us_states_simplified.json')
        self.states_gdf = None
        self.simplified_states = None
        
        # Create data directory if it doesn't exist
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        # Load state boundaries if available
        self.load_boundaries()
    
    def load_boundaries(self):
        """Load state boundaries from file if available"""
        # First try to load the simplified JSON file (faster)
        if os.path.exists(self.simplified_path):
            try:
                with open(self.simplified_path, 'r') as f:
                    self.simplified_states = json.load(f)
                logger.info(f"Loaded simplified state boundaries from {self.simplified_path}")
                return True
            except Exception as e:
                logger.error(f"Error loading simplified state boundaries: {e}")
        
        # If simplified file not available, try loading GeoJSON
        if os.path.exists(self.geojson_path):
            try:
                self.states_gdf = gpd.read_file(self.geojson_path)
                logger.info(f"Loaded state boundaries from {self.geojson_path}")
                return True
            except Exception as e:
                logger.error(f"Error loading state boundaries: {e}")
        
        logger.warning("No state boundary files found")
        return False
    
    def download_state_boundaries(self, year=2022):
        """Download state boundaries from US Census TIGER/Line shapefiles
        
        Args:
            year (int, optional): Year of TIGER/Line data. Defaults to 2022.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # URL for state boundaries
            tiger_url = f"https://www2.census.gov/geo/tiger/TIGER{year}/STATE/tl_{year}_us_state.zip"
            
            logger.info(f"Downloading state boundaries from {tiger_url}")
            
            # Create a temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download the zip file
                zip_path = os.path.join(temp_dir, "states.zip")
                urlretrieve(tiger_url, zip_path)
                
                # Extract the zip file
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                
                # Find the shapefile
                shp_files = [f for f in os.listdir(temp_dir) if f.endswith('.shp')]
                if not shp_files:
                    logger.error("No shapefile found in downloaded data")
                    return False
                
                # Load the shapefile
                shp_path = os.path.join(temp_dir, shp_files[0])
                self.states_gdf = gpd.read_file(shp_path)
                
                # Save as GeoJSON
                self.states_gdf.to_file(self.geojson_path, driver='GeoJSON')
                logger.info(f"Saved state boundaries to {self.geojson_path}")
                
                # Create simplified version
                self.create_simplified_boundaries()
                
                return True
                
        except Exception as e:
            logger.error(f"Error downloading state boundaries: {e}", exc_info=True)
            return False
    
    def create_simplified_boundaries(self):
        """Create a simplified version of the state boundaries for faster lookups"""
        if self.states_gdf is None:
            logger.error("No state boundaries loaded")
            return False
        
        try:
            # Create a simplified version with just the data we need
            simplified = []
            
            for idx, row in self.states_gdf.iterrows():
                # Simplify the geometry to reduce file size
                # The tolerance parameter controls the level of simplification
                simple_geom = row.geometry.simplify(0.01).to_wkt()
                
                state_data = {
                    'state_code': row['STUSPS'],
                    'state_name': row['NAME'],
                    'region': STATE_REGIONS.get(row['STUSPS'], 'Unknown'),
                    'geometry': simple_geom
                }
                simplified.append(state_data)
            
            # Save to file
            with open(self.simplified_path, 'w') as f:
                json.dump(simplified, f)
                
            logger.info(f"Created simplified state boundaries at {self.simplified_path}")
            
            # Load the simplified data
            self.simplified_states = simplified
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating simplified boundaries: {e}", exc_info=True)
            return False
    
    def determine_state_from_coordinates(self, lat, lon):
        """Determine which state a point falls within
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            
        Returns:
            dict: State information or None if not found
        """
        # Create a Point object from coordinates
        point = Point(lon, lat)  # Note: Point takes (x, y) which is (lon, lat)
        
        # First try using the simplified boundaries (faster)
        if self.simplified_states is not None and len(self.simplified_states) > 0:
            for state in self.simplified_states:
                try:
                    # Convert WKT string back to geometry
                    state_geom = shape(state['geometry'])
                    
                    if state_geom.contains(point):
                        return {
                            'state_code': state['state_code'],
                            'state_name': state['state_name'],
                            'region': state['region']
                        }
                except Exception as e:
                    logger.error(f"Error checking point in state: {e}")
                    continue
        
        # If simplified boundaries didn't work, try using GeoPandas
        if self.states_gdf is not None:
            try:
                # Use GeoPandas spatial join to find which polygon contains the point
                point_gdf = gpd.GeoDataFrame([1], geometry=[point], crs=self.states_gdf.crs)
                joined = gpd.sjoin(point_gdf, self.states_gdf, how='left', predicate='within')
                
                if joined.shape[0] > 0 and pd.notna(joined.iloc[0].get('STUSPS')):
                    state_code = joined.iloc[0]['STUSPS']
                    state_name = joined.iloc[0]['NAME']
                    return {
                        'state_code': state_code,
                        'state_name': state_name,
                        'region': STATE_REGIONS.get(state_code, 'Unknown')
                    }
            except Exception as e:
                logger.error(f"Error using GeoPandas for state lookup: {e}")
        
        # If we still don't have a result, try finding the closest state
        return self.find_closest_state(lat, lon)
    
    def find_closest_state(self, lat, lon):
        """Find the closest state to the given coordinates
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            
        Returns:
            dict: State information or None if not found
        """
        import math
        
        def haversine_distance(lat1, lon1, lat2, lon2):
            """Calculate the great circle distance between two points in kilometers"""
            # Convert decimal degrees to radians
            lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
            
            # Haversine formula
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
            c = 2 * math.asin(math.sqrt(a))
            r = 6371  # Radius of earth in kilometers
            return c * r
        
        point = Point(lon, lat)
        min_distance = float('inf')
        closest_state = None
        
        # Try using the simplified boundaries first
        if self.simplified_states is not None and len(self.simplified_states) > 0:
            for state in self.simplified_states:
                try:
                    # Convert WKT string back to geometry
                    state_geom = shape(state['geometry'])
                    
                    # Calculate distance to state boundary
                    distance = state_geom.distance(point)
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_state = {
                            'state_code': state['state_code'],
                            'state_name': state['state_name'],
                            'region': state['region']
                        }
                except Exception as e:
                    logger.error(f"Error calculating distance to state: {e}")
                    continue
        
        # If simplified boundaries didn't work, try using GeoPandas
        elif self.states_gdf is not None and not self.states_gdf.empty:
            for idx, state in self.states_gdf.iterrows():
                try:
                    # Calculate distance to state boundary
                    distance = state.geometry.distance(point)
                    
                    if distance < min_distance:
                        min_distance = distance
                        closest_state = {
                            'state_code': state['STUSPS'],
                            'state_name': state['NAME'],
                            'region': STATE_REGIONS.get(state['STUSPS'], 'Unknown')
                        }
                except Exception as e:
                    logger.error(f"Error calculating distance to state: {e}")
                    continue
        
        if closest_state:
            logger.info(f"Found closest state: {closest_state['state_code']}")
            return closest_state
        
        return None

# Create a singleton instance
state_boundaries = StateBoundaries()

def get_state_from_coordinates(lat, lon):
    """Determine which state a point falls within
    
    Args:
        lat (float): Latitude
        lon (float): Longitude
        
    Returns:
        dict: State information or None if not found
    """
    # Make sure boundaries are loaded
    if (state_boundaries.simplified_states is None or len(state_boundaries.simplified_states) == 0) and \
       (state_boundaries.states_gdf is None or state_boundaries.states_gdf.empty):
        # Try to download boundaries if not available
        state_boundaries.download_state_boundaries()
    
    return state_boundaries.determine_state_from_coordinates(lat, lon)

# Example usage
if __name__ == "__main__":
    # Test with New York City coordinates
    nyc_lat, nyc_lon = 40.7128, -74.0060
    state = get_state_from_coordinates(nyc_lat, nyc_lon)
    print(f"New York City is in {state['state_name']} ({state['state_code']}), region: {state['region']}")
    
    # Test with Los Angeles coordinates
    la_lat, la_lon = 34.0522, -118.2437
    state = get_state_from_coordinates(la_lat, la_lon)
    print(f"Los Angeles is in {state['state_name']} ({state['state_code']}), region: {state['region']}") 