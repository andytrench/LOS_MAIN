"""
Unified Turbine Clearance Calculator

This module provides a single, authoritative source for all turbine clearance calculations.
It consolidates the best mathematical methods from across the codebase and ensures
consistent, accurate results regardless of the entry point used.

Key Features:
- 4/3 earth radius model for earth curvature
- Proper Fresnel zone calculations with frequency consideration  
- 3D distance calculations considering horizontal and vertical components
- Rotor sweep area consideration for obstruction analysis
- Comprehensive validation and error handling
"""

import math
import logging
import json
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class TurbineData:
    """Standardized turbine data structure"""
    id: str
    latitude: float
    longitude: float
    total_height_m: float
    hub_height_m: Optional[float] = None
    rotor_diameter_m: Optional[float] = None
    project_name: Optional[str] = None
    capacity_kw: Optional[float] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    
    @property
    def total_height_ft(self) -> float:
        """Total height in feet"""
        return self.total_height_m * 3.28084
    
    @property 
    def hub_height_ft(self) -> float:
        """Hub height in feet"""
        if self.hub_height_m is not None:
            return self.hub_height_m * 3.28084
        else:
            # Calculate as total height minus rotor radius
            return self.total_height_ft - self.rotor_radius_ft
    
    @property
    def rotor_diameter_ft(self) -> float:
        """Rotor diameter in feet"""
        diameter_m = self.rotor_diameter_m if self.rotor_diameter_m is not None else 100.0  # Default 100m
        return diameter_m * 3.28084
    
    @property
    def rotor_radius_ft(self) -> float:
        """Rotor radius in feet"""
        return self.rotor_diameter_ft / 2

@dataclass
class PathData:
    """Standardized path data structure"""
    start_lat: float
    start_lon: float  
    end_lat: float
    end_lon: float
    start_elevation_ft: float
    end_elevation_ft: float
    start_antenna_height_ft: float
    end_antenna_height_ft: float
    frequency_ghz: float = 11.0  # Default frequency
    
    @property
    def start_total_height_ft(self) -> float:
        """Total height at start (elevation + antenna)"""
        return self.start_elevation_ft + self.start_antenna_height_ft
    
    @property
    def end_total_height_ft(self) -> float:
        """Total height at end (elevation + antenna)"""
        return self.end_elevation_ft + self.end_antenna_height_ft

@dataclass
class ClearanceResult:
    """Comprehensive clearance calculation result"""
    turbine_id: str
    
    # Distance measurements
    distance_to_path_m: float
    distance_to_path_ft: float
    distance_along_path_m: float
    distance_along_path_ft: float
    
    # Height measurements
    ground_elevation_ft: float
    turbine_center_height_ft: float
    path_height_straight_ft: float
    path_height_curved_ft: float
    
    # Earth curvature
    earth_curvature_bulge_ft: float
    
    # Fresnel zone
    fresnel_radius_ft: float
    
    # Clearance calculations
    clearance_straight_ft: float  # Straight line path clearance
    clearance_curved_ft: float    # Earth curvature adjusted clearance  
    clearance_fresnel_ft: float   # Fresnel zone clearance
    
    # 3D clearances (accounting for both horizontal and vertical separation)
    clearance_3d_straight_ft: float
    clearance_3d_curved_ft: float
    clearance_3d_fresnel_ft: float
    
    # Status flags
    has_los_clearance: bool       # Clear of direct line of sight
    has_earth_clearance: bool     # Clear with earth curvature 
    has_fresnel_clearance: bool   # Clear of Fresnel zone
    
    # Side of path (positive = right side, negative = left side when looking from start to end)
    path_side: int
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'turbine_id': self.turbine_id,
            'distance_to_path_m': self.distance_to_path_m,
            'distance_to_path_ft': self.distance_to_path_ft,
            'distance_along_path_m': self.distance_along_path_m,
            'distance_along_path_ft': self.distance_along_path_ft,
            'ground_elevation_ft': self.ground_elevation_ft,
            'turbine_center_height_ft': self.turbine_center_height_ft,
            'path_height_straight_ft': self.path_height_straight_ft,
            'path_height_curved_ft': self.path_height_curved_ft,
            'earth_curvature_bulge_ft': self.earth_curvature_bulge_ft,
            'fresnel_radius_ft': self.fresnel_radius_ft,
            'clearance_straight_ft': self.clearance_straight_ft,
            'clearance_curved_ft': self.clearance_curved_ft,
            'clearance_fresnel_ft': self.clearance_fresnel_ft,
            'clearance_3d_straight_ft': self.clearance_3d_straight_ft,
            'clearance_3d_curved_ft': self.clearance_3d_curved_ft,
            'clearance_3d_fresnel_ft': self.clearance_3d_fresnel_ft,
            'has_los_clearance': self.has_los_clearance,
            'has_earth_clearance': self.has_earth_clearance,
            'has_fresnel_clearance': self.has_fresnel_clearance,
            'path_side': self.path_side
        }

class TurbineClearanceCalculator:
    """
    Unified calculator for all turbine clearance calculations.
    
    This class implements the most accurate mathematical methods for:
    - Distance calculations using spherical coordinate geometry
    - Earth curvature corrections using 4/3 earth radius model
    - Fresnel zone calculations with proper RF propagation formulas
    - 3D clearance analysis considering rotor sweep volumes
    """
    
    # Physical constants
    EARTH_RADIUS_M = 6371000  # Earth radius in meters
    EARTH_RADIUS_FT = 20925646  # Earth radius in feet
    K_FACTOR = 4/3  # 4/3 earth radius model for radio propagation
    SPEED_OF_LIGHT = 299792458  # m/s
    
    def __init__(self):
        """Initialize the calculator"""
        self.logger = logging.getLogger(__name__)
        
    def calculate_turbine_clearances(self, 
                                   turbines: List[TurbineData], 
                                   path: PathData,
                                   elevation_data: Optional[List[float]] = None,
                                   elevation_distances: Optional[List[float]] = None) -> List[ClearanceResult]:
        """
        Calculate comprehensive clearance data for all turbines relative to the path.
        
        Args:
            turbines: List of turbine data
            path: Path data including start/end coordinates and heights
            elevation_data: Optional elevation profile data
            elevation_distances: Optional distances corresponding to elevation data
            
        Returns:
            List of clearance results for each turbine
        """
        results = []
        
        # Calculate total path distance
        path_length_m = self._haversine_distance(
            path.start_lat, path.start_lon,
            path.end_lat, path.end_lon
        )
        
        self.logger.info(f"Calculating clearances for {len(turbines)} turbines along {path_length_m/1000:.2f}km path")
        
        for turbine in turbines:
            try:
                result = self._calculate_single_turbine_clearance(turbine, path, path_length_m, elevation_data, elevation_distances)
                results.append(result)
                self.logger.debug(f"Calculated clearances for turbine {turbine.id}: Fresnel={result.clearance_fresnel_ft:.1f}ft")
            except Exception as e:
                self.logger.error(f"Error calculating clearance for turbine {turbine.id}: {e}", exc_info=True)
                continue
                
        return results
    
    def _calculate_single_turbine_clearance(self, 
                                          turbine: TurbineData, 
                                          path: PathData,
                                          path_length_m: float,
                                          elevation_data: Optional[List[float]] = None,
                                          elevation_distances: Optional[List[float]] = None) -> ClearanceResult:
        """Calculate clearance for a single turbine"""
        
        # 1. Calculate distance from turbine to path
        distance_to_path_m, distance_along_path_m, path_side = self._calculate_distance_to_path(
            turbine.latitude, turbine.longitude,
            path.start_lat, path.start_lon,
            path.end_lat, path.end_lon
        )
        
        # 2. Calculate distance along path ratio
        distance_ratio = distance_along_path_m / path_length_m if path_length_m > 0 else 0
        distance_ratio = max(0, min(1, distance_ratio))  # Clamp to [0,1]
        
        # 3. Get ground elevation at turbine position
        ground_elevation_ft = self._get_ground_elevation_at_position(
            distance_ratio, elevation_data, elevation_distances
        )
        
        # 4. Calculate path heights at turbine position
        path_height_straight_ft = path.start_total_height_ft + (
            path.end_total_height_ft - path.start_total_height_ft
        ) * distance_ratio
        
        # 5. Calculate earth curvature bulge
        distance_along_path_ft = distance_along_path_m * 3.28084
        path_length_ft = path_length_m * 3.28084
        earth_curvature_bulge_ft = self._calculate_earth_curvature_bulge(
            distance_along_path_ft, path_length_ft
        )
        
        # 6. Calculate curved path height
        path_height_curved_ft = path_height_straight_ft - earth_curvature_bulge_ft
        
        # 7. Calculate Fresnel radius at this position
        fresnel_radius_ft = self._calculate_fresnel_radius(
            distance_along_path_m / 1000,  # d1 in km
            (path_length_m - distance_along_path_m) / 1000,  # d2 in km  
            path.frequency_ghz
        )
        
        # 8. Calculate turbine center height
        turbine_center_height_ft = ground_elevation_ft + turbine.hub_height_ft
        
        # 9. Calculate clearances
        distance_to_path_ft = distance_to_path_m * 3.28084
        
        # Straight line clearances (vertical difference only)
        clearance_straight_ft = path_height_straight_ft - turbine_center_height_ft - turbine.rotor_radius_ft
        clearance_curved_ft = path_height_curved_ft - turbine_center_height_ft - turbine.rotor_radius_ft  
        clearance_fresnel_ft = clearance_curved_ft - fresnel_radius_ft
        
        # 3D clearances (considering both horizontal and vertical separation)
        vertical_distance_straight = abs(path_height_straight_ft - turbine_center_height_ft)
        vertical_distance_curved = abs(path_height_curved_ft - turbine_center_height_ft)
        horizontal_distance = distance_to_path_ft
        
        clearance_3d_straight_ft = math.sqrt(
            horizontal_distance**2 + vertical_distance_straight**2
        ) - turbine.rotor_radius_ft
        
        clearance_3d_curved_ft = math.sqrt(
            horizontal_distance**2 + vertical_distance_curved**2  
        ) - turbine.rotor_radius_ft
        
        clearance_3d_fresnel_ft = clearance_3d_curved_ft - fresnel_radius_ft
        
        # 10. Determine clearance status
        has_los_clearance = clearance_3d_straight_ft > 0
        has_earth_clearance = clearance_3d_curved_ft > 0
        has_fresnel_clearance = clearance_3d_fresnel_ft > 0
        
        return ClearanceResult(
            turbine_id=turbine.id,
            distance_to_path_m=distance_to_path_m,
            distance_to_path_ft=distance_to_path_ft,
            distance_along_path_m=distance_along_path_m,
            distance_along_path_ft=distance_along_path_ft,
            ground_elevation_ft=ground_elevation_ft,
            turbine_center_height_ft=turbine_center_height_ft,
            path_height_straight_ft=path_height_straight_ft,
            path_height_curved_ft=path_height_curved_ft,
            earth_curvature_bulge_ft=earth_curvature_bulge_ft,
            fresnel_radius_ft=fresnel_radius_ft,
            clearance_straight_ft=clearance_straight_ft,
            clearance_curved_ft=clearance_curved_ft,
            clearance_fresnel_ft=clearance_fresnel_ft,
            clearance_3d_straight_ft=clearance_3d_straight_ft,
            clearance_3d_curved_ft=clearance_3d_curved_ft,
            clearance_3d_fresnel_ft=clearance_3d_fresnel_ft,
            has_los_clearance=has_los_clearance,
            has_earth_clearance=has_earth_clearance,
            has_fresnel_clearance=has_fresnel_clearance,
            path_side=path_side
        )
    
    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate great circle distance between two points in meters"""
        R = self.EARTH_RADIUS_M
        
        # Convert to radians
        lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
        
        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _calculate_distance_to_path(self, 
                                  turbine_lat: float, turbine_lon: float,
                                  start_lat: float, start_lon: float,
                                  end_lat: float, end_lon: float) -> Tuple[float, float, int]:
        """
        Calculate perpendicular distance from turbine to path using spherical coordinate geometry.
        
        Returns:
            Tuple of (distance_to_path_m, distance_along_path_m, path_side)
            path_side: +1 for right side, -1 for left side when looking from start to end
        """
        # Convert coordinates to radians  
        lat1, lon1 = map(math.radians, [start_lat, start_lon])
        lat2, lon2 = map(math.radians, [end_lat, end_lon])
        lat_t, lon_t = map(math.radians, [turbine_lat, turbine_lon])
        
        # Convert to Cartesian coordinates
        x1 = math.cos(lat1) * math.cos(lon1)
        y1 = math.cos(lat1) * math.sin(lon1)
        z1 = math.sin(lat1)
        
        x2 = math.cos(lat2) * math.cos(lon2)
        y2 = math.cos(lat2) * math.sin(lon2)
        z2 = math.sin(lat2)
        
        xt = math.cos(lat_t) * math.cos(lon_t)
        yt = math.cos(lat_t) * math.sin(lon_t)
        zt = math.sin(lat_t)
        
        # Calculate path vector
        path_vector = [x2 - x1, y2 - y1, z2 - z1]
        
        # Calculate vector from start to turbine
        turbine_vector = [xt - x1, yt - y1, zt - z1]
        
        # Calculate path length
        path_magnitude = math.sqrt(sum(x * x for x in path_vector))
        if path_magnitude == 0:
            # Start and end are the same point
            distance_to_path = self._haversine_distance(turbine_lat, turbine_lon, start_lat, start_lon)
            return distance_to_path, 0, 0
        
        # Calculate projection along path
        dot_product = sum(p * t for p, t in zip(path_vector, turbine_vector))
        projection_ratio = dot_product / (path_magnitude * path_magnitude)
        
        # Calculate distance along path
        total_path_distance = self._haversine_distance(start_lat, start_lon, end_lat, end_lon)
        distance_along_path = projection_ratio * total_path_distance
        
        # Clamp to path bounds
        distance_along_path = max(0, min(total_path_distance, distance_along_path))
        
        # Calculate cross product to determine side and perpendicular distance
        cross_product = [
            path_vector[1] * turbine_vector[2] - path_vector[2] * turbine_vector[1],
            path_vector[2] * turbine_vector[0] - path_vector[0] * turbine_vector[2],
            path_vector[0] * turbine_vector[1] - path_vector[1] * turbine_vector[0]
        ]
        
        cross_magnitude = math.sqrt(sum(x * x for x in cross_product))
        
        # Calculate perpendicular distance
        perpendicular_distance = (cross_magnitude / path_magnitude) * self.EARTH_RADIUS_M
        
        # Determine which side of path (using z-component of cross product)
        path_side = 1 if cross_product[2] > 0 else -1
        
        return perpendicular_distance, distance_along_path, path_side
    
    def _get_ground_elevation_at_position(self, 
                                        distance_ratio: float,
                                        elevation_data: Optional[List[float]] = None,
                                        elevation_distances: Optional[List[float]] = None) -> float:
        """Get ground elevation at specified position along path"""
        if elevation_data is None or len(elevation_data) == 0:
            return 0.0  # Default ground level
            
        if len(elevation_data) == 1:
            return elevation_data[0]
            
        # Interpolate elevation at the specified distance ratio
        index = distance_ratio * (len(elevation_data) - 1)
        index_low = int(math.floor(index))
        index_high = int(math.ceil(index))
        
        # Clamp indices
        index_low = max(0, min(len(elevation_data) - 1, index_low))
        index_high = max(0, min(len(elevation_data) - 1, index_high))
        
        if index_low == index_high:
            return elevation_data[index_low]
            
        # Linear interpolation
        fraction = index - index_low
        return elevation_data[index_low] + (elevation_data[index_high] - elevation_data[index_low]) * fraction
    
    def _calculate_earth_curvature_bulge(self, distance_along_path_ft: float, total_path_ft: float) -> float:
        """Calculate earth curvature bulge using 4/3 earth radius model"""
        if total_path_ft <= 0:
            return 0.0
            
        # Calculate bulge at specified distance
        bulge_ft = (distance_along_path_ft * (total_path_ft - distance_along_path_ft)) / (
            2 * self.K_FACTOR * self.EARTH_RADIUS_FT
        )
        
        return bulge_ft
    
    def _calculate_fresnel_radius(self, d1_km: float, d2_km: float, frequency_ghz: float) -> float:
        """Calculate first Fresnel zone radius at specified position"""
        if d1_km <= 0 or d2_km <= 0 or frequency_ghz <= 0:
            return 0.0
            
        # Fresnel zone formula: r = 17.32 * sqrt((d1 * d2) / (f * (d1 + d2)))
        # where d1, d2 are in km, f is in GHz, result is in meters
        # This is the standard RF engineering formula
        
        radius_m = 17.32 * math.sqrt((d1_km * d2_km) / (frequency_ghz * (d1_km + d2_km)))
        
        # Convert to feet
        return radius_m * 3.28084

# Convenience functions for backward compatibility and ease of use

def create_turbine_from_dict(turbine_dict: Dict) -> TurbineData:
    """Create TurbineData from dictionary (e.g., from JSON)"""
    return TurbineData(
        id=str(turbine_dict.get('id') or turbine_dict.get('case_id', 'Unknown')),
        latitude=float(turbine_dict.get('latitude') or turbine_dict.get('ylat', 0)),
        longitude=float(turbine_dict.get('longitude') or turbine_dict.get('xlong', 0)),
        total_height_m=float(turbine_dict.get('total_height_m') or turbine_dict.get('t_ttlh', 100)),
        hub_height_m=turbine_dict.get('hub_height_m') or turbine_dict.get('t_hh'),
        rotor_diameter_m=turbine_dict.get('rotor_diameter_m') or turbine_dict.get('t_rd'),
        project_name=turbine_dict.get('project_name') or turbine_dict.get('p_name'),
        capacity_kw=turbine_dict.get('capacity_kw') or turbine_dict.get('t_cap'),
        manufacturer=turbine_dict.get('manufacturer') or turbine_dict.get('t_manu'),
        model=turbine_dict.get('model') or turbine_dict.get('t_model')
    )

def create_path_from_tower_params(tower_params_path: str = 'tower_parameters.json') -> PathData:
    """Create PathData from tower_parameters.json file"""
    try:
        with open(tower_params_path, 'r') as f:
            data = json.load(f)
            
        site_a = data['site_A']
        site_b = data['site_B']
        general = data['general_parameters']
        
        # Import coordinate conversion function
        from utilities.coordinates import convert_dms_to_decimal
        
        # Handle both DMS and decimal coordinate formats
        def parse_coordinate(coord_str):
            if isinstance(coord_str, (int, float)):
                return float(coord_str)
            elif isinstance(coord_str, str):
                # Try decimal first, then DMS
                try:
                    return float(coord_str)
                except ValueError:
                    # Must be DMS format, extract lat/lon pair from site data
                    return None  # Will be handled below
            return float(coord_str)
        
        # Convert coordinates properly
        if isinstance(site_a['latitude'], str) and ('N' in site_a['latitude'] or 'S' in site_a['latitude']):
            # DMS format - convert both lat and lon together
            start_lat, start_lon = convert_dms_to_decimal(site_a['latitude'], site_a['longitude'])
            end_lat, end_lon = convert_dms_to_decimal(site_b['latitude'], site_b['longitude'])
        else:
            # Already decimal format
            start_lat = float(site_a['latitude'])
            start_lon = float(site_a['longitude'])
            end_lat = float(site_b['latitude'])
            end_lon = float(site_b['longitude'])
        
        return PathData(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            start_elevation_ft=float(site_a['elevation_ft']),
            end_elevation_ft=float(site_b['elevation_ft']),
            start_antenna_height_ft=float(site_a['antenna_cl_ft']),
            end_antenna_height_ft=float(site_b['antenna_cl_ft']),
            frequency_ghz=float(general.get('frequency_ghz', 11.0))
        )
    except Exception as e:
        logger.error(f"Error loading path data from {tower_params_path}: {e}")
        raise

def calculate_turbine_clearances_from_json(tower_params_path: str = 'tower_parameters.json',
                                         elevation_data: Optional[List[float]] = None,
                                         elevation_distances: Optional[List[float]] = None) -> List[ClearanceResult]:
    """
    Convenience function to calculate clearances from tower_parameters.json
    
    Args:
        tower_params_path: Path to tower_parameters.json file
        elevation_data: Optional elevation profile data  
        elevation_distances: Optional distances corresponding to elevation data
        
    Returns:
        List of clearance results
    """
    try:
        with open(tower_params_path, 'r') as f:
            data = json.load(f)
            
        # Create path data
        path = create_path_from_tower_params(tower_params_path)
        
        # Create turbine data
        turbines = []
        if 'turbines' in data:
            for turbine_dict in data['turbines']:
                turbines.append(create_turbine_from_dict(turbine_dict))
        
        # Calculate clearances
        calculator = TurbineClearanceCalculator()
        return calculator.calculate_turbine_clearances(turbines, path, elevation_data, elevation_distances)
        
    except Exception as e:
        logger.error(f"Error calculating clearances from {tower_params_path}: {e}")
        raise 