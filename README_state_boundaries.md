# State Boundaries Module for LIDAR Data Localization

This module provides accurate state boundary lookups for LIDAR data localization in the LOStool application.

## Overview

The `state_boundaries.py` module provides functions for determining which US state a set of coordinates falls within. It uses the US Census Bureau's TIGER/Line shapefiles for accurate state boundaries.

## Features

- **Accurate State Determination**: Uses precise state boundary polygons from the US Census Bureau
- **Automatic Data Download**: Automatically downloads state boundary data when needed
- **Simplified Storage**: Creates a simplified version of the boundaries for faster lookups
- **Fallback Mechanisms**: Includes multiple fallback methods if the primary lookup fails
- **Region Information**: Provides region information (Northeast, Southeast, etc.) for each state

## Usage

### Basic Usage

```python
from state_boundaries import get_state_from_coordinates

# Example with New York City coordinates
lat, lon = 40.7128, -74.0060
state_info = get_state_from_coordinates(lat, lon)

print(f"State: {state_info['state_code']} ({state_info['state_name']})")
print(f"Region: {state_info['region']}")
```

### Integration with Metadata Processing

The module is integrated with the metadata processing in `metadata.py` to provide accurate state and region information for LIDAR data:

```python
# In metadata.py
from state_boundaries import get_state_from_coordinates

# When processing LIDAR metadata
if center_lat is not None and center_lon is not None:
    state_info = get_state_from_coordinates(center_lat, center_lon)
    if state_info:
        state = state_info['state_code']
        region = state_info['region']
```

## Data Sources

- **US Census Bureau TIGER/Line Shapefiles**: The module downloads state boundary data from the US Census Bureau's TIGER/Line shapefiles.
- **Default Year**: By default, it uses the 2022 version of the TIGER/Line shapefiles.
- **Data Storage**: The downloaded data is stored in a `data` directory within the application.

## Technical Details

### Data Processing

1. The module downloads the TIGER/Line shapefiles as a ZIP file
2. It extracts the shapefile and loads it using GeoPandas
3. It creates a simplified version of the boundaries for faster lookups
4. It saves both the full GeoJSON and simplified JSON versions

### Lookup Methods

The module uses multiple methods for state lookups:

1. **Point-in-Polygon**: Checks if the coordinates fall within a state polygon
2. **Spatial Join**: Uses GeoPandas spatial join for accurate lookups
3. **Closest State**: If the point is not within any state, finds the closest state

## Dependencies

- **GeoPandas**: For handling geospatial data
- **Shapely**: For geometric operations
- **Pandas**: For data manipulation
- **Requests**: For downloading data

## Installation

Ensure you have the required dependencies installed:

```bash
pip install -r requirements.txt
```

## First-Time Usage

The first time you use the module, it will automatically download the state boundary data. This may take a few moments, but subsequent uses will be much faster as it will use the cached data.

## Troubleshooting

If you encounter issues with the state boundary lookups:

1. Check that the `data` directory exists and is writable
2. Verify that the required dependencies are installed
3. Check the logs for any error messages
4. Try manually downloading the state boundaries using `state_boundaries.download_state_boundaries()`

## License

This module is part of the LOStool application and is subject to the same license terms. 