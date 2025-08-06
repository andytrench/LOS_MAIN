# Vegetation Data Processing

This document describes the vegetation data processing in the LOS Tool application.

## Overview

The application uses Google Earth Engine to access vegetation height data for the line of sight path analysis. This data is used to visualize vegetation along the path between two sites and to identify potential obstructions.

## Data Sources

The application uses multiple vegetation data sources in a fallback sequence:

1. **GEDI (Global Ecosystem Dynamics Investigation)** - Primary data source
   - Dataset: `LARSE/GEDI/GEDI02_A_002_MONTHLY`
   - Date range: 2019-01-01 to 2024-12-31
   - Resolution: 90m
   - Provides the most accurate vegetation height data when available
   - Limited coverage in some regions

2. **Hansen Global Forest Change** - First fallback
   - Dataset: `UMD/hansen/global_forest_change_2021_v1_9`
   - Uses tree cover percentage from 2000 as a proxy for vegetation height
   - Converts percentage to approximate height (1% ≈ 0.3m)
   - Better global coverage than GEDI

3. **MODIS Vegetation Continuous Fields (VCF)** - Second fallback
   - Dataset: `MODIS/006/MOD44B`
   - Date range: 2020-01-01 to 2023-12-31
   - Resolution: 250m
   - Uses tree cover percentage as a proxy for vegetation height
   - Converts percentage to approximate height (1% ≈ 0.25m)
   - Excellent global coverage but lower resolution

## Implementation Details

The vegetation data processing is implemented in the `vegetation_profile.py` file:

1. The `VegetationProfiler` class handles all vegetation data processing
2. Earth Engine is initialized only when needed (lazy loading)
3. The `get_vegetation_profile` method attempts to get vegetation data from each source in sequence
4. If all sources fail, zeros are returned (no vegetation)

## Troubleshooting

If vegetation data is not appearing in the profile:

1. **Check Earth Engine Authentication**
   - Ensure the `.env` file contains valid `EE_SERVICE_ACCOUNT` and `EE_PRIVATE_KEY_PATH` values
   - Verify that the service account key file exists and is valid

2. **Check Internet Connection**
   - Earth Engine requires an active internet connection

3. **Check Region Coverage**
   - Some regions may have limited or no GEDI data
   - The application will fall back to Hansen and MODIS data in these cases

4. **Check Log Files**
   - Look for errors related to "vegetation" or "Earth Engine" in the log files

## Improving Vegetation Data

To improve vegetation data quality:

1. **Increase Buffer Size**
   - The current buffer around the line is 1000m
   - Increasing this value may capture more data points but will slow down processing

2. **Add More Data Sources**
   - Additional Earth Engine datasets could be added as fallbacks
   - Local or regional vegetation datasets could be integrated

3. **Improve Height Estimation**
   - The current conversion from tree cover percentage to height is a simple approximation
   - More sophisticated models could be implemented based on region, climate, etc.
