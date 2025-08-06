import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import requests
import rasterio
from rasterio.warp import transform_bounds
import urllib.request
import os
from osgeo import gdal
from scipy.interpolate import interp1d
import ee
from dotenv import load_dotenv
from log_config import setup_logging
from pathlib import Path
import logging

# Get the directory containing the script
SCRIPT_DIR = Path(__file__).parent.absolute()

# Create logger
logger = setup_logging(__name__)

# Load environment variables with explicit path
env_path = SCRIPT_DIR / '.env'
load_dotenv(dotenv_path=env_path, override=True)

# Add debug logging for environment loading
logger.info(f"Loading .env file from: {env_path}")

# Debug: Print file contents (safely)
try:
    with open(env_path) as f:
        env_contents = f.read()
        logger.info(f"Environment file contents (first 50 chars): {env_contents[:50]}...")
except Exception as e:
    logger.error(f"Error reading .env file: {e}")

# Add this after the load_dotenv call
if not all(k in os.environ for k in ['GOOGLE_MAPS_API_KEY', 'EE_SERVICE_ACCOUNT', 'EE_PRIVATE_KEY_PATH']):
    logger.error("Direct environment check failed")
    logger.error(f"Current environment keys: {list(os.environ.keys())}")

class VegetationProfiler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._ee_initialized = False

    def initialize_ee(self):
        """Initialize Earth Engine only when needed"""
        # Skip if already initialized
        if self._ee_initialized:
            return
        try:
            # Load environment variables
            env_path = Path(__file__).parent.absolute() / '.env'
            load_dotenv(dotenv_path=env_path, override=True)

            # Initialize Earth Engine
            credentials = ee.ServiceAccountCredentials(
                os.environ.get('EE_SERVICE_ACCOUNT'),
                os.environ.get('EE_PRIVATE_KEY_PATH')
            )
            ee.Initialize(credentials)
            self._ee_initialized = True
            self.logger.info("Earth Engine initialized successfully")
        except Exception as e:
            self.logger.error(f"Error initializing Earth Engine: {str(e)}")
            raise

    def get_vegetation_profile(self, start_coords, end_coords, distances, elevations):
        """Get vegetation height profile between two points."""
        try:
            # Initialize Earth Engine if not already initialized
            if not self._ee_initialized:
                self.initialize_ee()

            # Create a buffer around the line
            roi = ee.Geometry.LineString([
                [start_coords[1], start_coords[0]],
                [end_coords[1], end_coords[0]]
            ]).buffer(1000)  # Increased from 500m to 1000m buffer for better coverage

            # Try to get vegetation data from multiple sources
            vegetation_heights = None

            # First try: GEDI dataset (most accurate when available)
            try:
                self.logger.info("Attempting to use GEDI dataset for vegetation data")
                # Load GEDI dataset with reduced resolution
                gedi = ee.ImageCollection('LARSE/GEDI/GEDI02_A_002_MONTHLY')\
                    .filterBounds(roi)\
                    .filterDate('2019-01-01', '2024-12-31')\
                    .limit(20)  # Increased limit for more data points

                # Get raw values with reduced resolution
                raw_values = gedi.select(['rh98']).getRegion(roi, 90).getInfo()  # Increased scale to 90m

                if len(raw_values) > 1:  # First row is headers
                    # Extract height values (skip header row)
                    values = [row[4] for row in raw_values[1:] if row[4] is not None and row[4] > 0]

                    if len(values) >= 2:
                        self.logger.info(f"Found {len(values)} GEDI data points")
                        # Create interpolation points
                        sample_distances = np.linspace(0, distances[-1], len(values))

                        # Interpolate to match elevation points
                        interp_func = interp1d(sample_distances, values,
                                            kind='linear',
                                            fill_value='extrapolate')

                        vegetation_heights = interp_func(distances)
                    else:
                        self.logger.warning("Insufficient GEDI data points for interpolation")
                else:
                    self.logger.warning("No GEDI data points found in region")
            except Exception as e:
                self.logger.error(f"Error accessing GEDI dataset: {e}")

            # Second try: Use Hansen Global Forest Change dataset as fallback
            if vegetation_heights is None:
                try:
                    self.logger.info("Attempting to use Hansen Forest dataset as fallback")
                    # Load Hansen Global Forest Change dataset
                    hansen = ee.Image('UMD/hansen/global_forest_change_2021_v1_9')
                    treeHeight = hansen.select(['treecover2000'])

                    # Sample points along the line
                    points = ee.FeatureCollection.multiPoint(
                        [ee.List([start_coords[1], start_coords[0]]),
                         ee.List([end_coords[1], end_coords[0]])]
                    )

                    # Get tree height values
                    tree_values = treeHeight.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=roi,
                        scale=30,
                        maxPixels=1e9
                    ).get('treecover2000').getInfo()

                    if tree_values is not None:
                        self.logger.info(f"Found Hansen tree cover data: {tree_values}")
                        # Convert percentage to approximate height (rough estimate: 1% = 0.3m)
                        avg_height = float(tree_values) * 0.3

                        # Create a simple height profile based on average height
                        vegetation_heights = np.ones_like(distances) * avg_height
                    else:
                        self.logger.warning("No Hansen tree cover data found")
                except Exception as e:
                    self.logger.error(f"Error accessing Hansen dataset: {e}")

            # Third try: Use MODIS Vegetation Continuous Fields as last resort
            if vegetation_heights is None:
                try:
                    self.logger.info("Attempting to use MODIS VCF dataset as last resort")
                    # Load MODIS Vegetation Continuous Fields
                    modis_vcf = ee.ImageCollection('MODIS/006/MOD44B')\
                        .filterDate('2020-01-01', '2023-12-31')\
                        .select('Percent_Tree_Cover')\
                        .mean()

                    # Get tree cover percentage
                    vcf_values = modis_vcf.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=roi,
                        scale=250,
                        maxPixels=1e9
                    ).get('Percent_Tree_Cover').getInfo()

                    if vcf_values is not None:
                        self.logger.info(f"Found MODIS VCF data: {vcf_values}")
                        # Convert percentage to approximate height (rough estimate: 1% = 0.25m)
                        avg_height = float(vcf_values) * 0.25

                        # Create a simple height profile based on average height
                        vegetation_heights = np.ones_like(distances) * avg_height
                    else:
                        self.logger.warning("No MODIS VCF data found")
                except Exception as e:
                    self.logger.error(f"Error accessing MODIS VCF dataset: {e}")

            # If all attempts failed, return zeros
            if vegetation_heights is None:
                self.logger.warning("All vegetation data sources failed, returning zeros")
                vegetation_heights = np.zeros_like(distances)

            # Clean up the data
            vegetation_heights[vegetation_heights < 0] = 0
            vegetation_heights *= 3.28084  # Convert meters to feet

            return vegetation_heights

        except Exception as e:
            self.logger.error(f"Error getting vegetation profile: {e}")
            return np.zeros_like(distances)