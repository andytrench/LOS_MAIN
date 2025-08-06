# Map Functions Documentation

This document provides comprehensive information about the map functions in the LOS Tool application, including the map server, visualization features, and integration with other components.

## Table of Contents

1. [Overview](#overview)
2. [Map Server](#map-server)
3. [Map Visualization](#map-visualization)
4. [Map Providers](#map-providers)
5. [Map Elements](#map-elements)
6. [Interaction Features](#interaction-features)
7. [Integration with Other Components](#integration-with-other-components)
8. [API Reference](#api-reference)
9. [Troubleshooting](#troubleshooting)

## Overview

The LOS Tool application provides a web-based map interface for visualizing line-of-sight paths, structures, and other relevant data. The map functionality is implemented through a combination of:

- A Python-based map server (`map_server.py`)
- A web interface using Leaflet.js
- Integration with various data sources (OSM, FCC, USGS)
- Custom visualization elements for paths, Fresnel zones, and structures

The map is accessible through the "Open on Map" button in the main application, which launches the map server and opens the map in a web browser.

## Map Server

The map server is implemented in the `map_server.py` file and provides a web interface for the map visualization.

### Server Architecture

The map server uses Python's `http.server` module to create a simple HTTP server that serves:
- Static files (HTML, CSS, JavaScript)
- Dynamic data (JSON responses for API endpoints)
- WebSocket connections for real-time updates

### Starting the Map Server

The map server can be started in several ways:

1. **From the Main Application**:
   - Click the "Open on Map" button in the main application
   - This launches the map server and opens the map in a web browser

2. **Programmatically**:
   ```python
   from map_server import start_server
   server_address = start_server()
   print(f"Map server started at {server_address}")
   ```

3. **Standalone Script**:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
   from map_server import start_server
   start_server()
   ```

### Server Configuration

The map server uses the following configuration:

- **Default Port**: 9000 (falls back to other ports if 9000 is in use)
- **Host**: 127.0.0.1 (localhost)
- **Tower Parameters File**: `tower_parameters.json` (configurable)
- **Static Files Directory**: `map_server_files/`
- **Temporary Files Directory**: `temp/`

## Map Visualization

The map visualization is implemented using Leaflet.js, a leading open-source JavaScript library for interactive maps.

### Map Interface

The map interface provides:
- Pan and zoom controls
- Layer selection (Mapbox, ESRI)
- Measurement tools
- Structure filtering
- Path visualization
- Fresnel zone display

### Map Initialization

The map is initialized with the following parameters:
- **Center**: Midpoint between donor and recipient sites
- **Zoom Level**: Automatically calculated based on path length
- **Default Layer**: Mapbox satellite imagery
- **Controls**: Zoom, layer control, scale, measurement

## Map Providers

The application supports multiple map providers:

### Mapbox

Mapbox provides high-quality satellite imagery and is the default map provider.

- **Layer Type**: Satellite with labels
- **API Key**: Loaded from `.env` file
- **URL Template**: `https://api.mapbox.com/styles/v1/{id}/tiles/{z}/{x}/{y}?access_token={accessToken}`

### ESRI

ESRI provides alternative imagery and topographic maps.

- **Layer Types**: 
  - World Imagery
  - World Topographic
  - World Street Map
- **URL Template**: `https://server.arcgisonline.com/ArcGIS/rest/services/{service}/MapServer/tile/{z}/{y}/{x}`

### OpenStreetMap

OpenStreetMap provides basic map tiles as a fallback option.

- **Layer Type**: Standard
- **URL Template**: `https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png`

## Map Elements

The map displays various elements to visualize the line-of-sight path and potential obstructions.

### Sites

Donor and recipient sites are displayed as markers with custom icons.

- **Donor Site**: Blue marker with "A" label
- **Recipient Site**: Red marker with "B" label
- **Popup Content**: Site details (ID, coordinates, elevation, antenna height)

### Path

The line-of-sight path is displayed as a polyline connecting the donor and recipient sites.

- **Style**: Solid line with customizable color (default: blue)
- **Width**: 3 pixels
- **Opacity**: 0.8
- **Popup Content**: Path details (length, azimuth)

### Fresnel Zone

The Fresnel zone is displayed as a polygon representing the area that should be clear for optimal signal transmission.

- **Style**: Thin white outline with no fill
- **Width**: 1 pixel
- **Opacity**: 0.7
- **Visualization**: Multiple ellipses representing different Fresnel zone radii

### Structures

Various structures from OSM, FCC, and other sources are displayed as markers.

- **Power Structures**: Yellow tower icons
- **Communication Structures**: Red antenna icons
- **Other Structures**: Gray building icons
- **Popup Content**: Structure details (type, height, operator)

### Towers

FCC towers are displayed as markers with custom icons.

- **Style**: Tower icon with height-based color coding
- **Popup Content**: Tower details (registration number, owner, height, structure type)

### Turbines

Wind turbines from the USGS database are displayed as circle markers.

- **Style**: Circle with center dot
- **Color**: Green
- **Popup Content**: Turbine details (ID, capacity, height, rotor diameter)

### Search Polygon

The search polygon used for querying structures is displayed as a polygon.

- **Style**: Dashed blue outline with light blue fill
- **Opacity**: 0.3
- **Behavior**: Disappears when analysis starts, reappears on reset

## Interaction Features

The map provides various interaction features for analyzing the line-of-sight path.

### Measurement Tool

The measurement tool allows measuring distances on the map.

- **Activation**: Click the ruler icon in the toolbar
- **Usage**: Click points on the map to measure distances
- **Units**: Both imperial (feet) and metric (meters) units are displayed

### Structure Filtering

Structures can be filtered by type using the control panel.

- **Power Structures**: Toggle power towers, poles, etc.
- **Communication Structures**: Toggle communication towers, masts, etc.
- **Other Structures**: Toggle water towers, chimneys, etc.

### Tower Search

The "Search Towers" button searches for FCC towers within the search polygon.

- **Activation**: Click the "Search Towers" button
- **Result**: Displays towers as markers on the map
- **Data Source**: FCC registration database

### Turbine Toggle

The "Show/Hide Turbines" button toggles the display of wind turbines.

- **Activation**: Click the "Show/Hide Turbines" button
- **Result**: Displays or hides turbine markers
- **Data Source**: USGS wind turbine database

### OSM Query

The map allows querying OSM structures within a custom polygon.

- **Activation**: Draw a polygon using the drawing tools
- **Result**: Displays structures within the polygon
- **Data Source**: PostgreSQL database or spatial index

## Integration with Other Components

The map functionality integrates with other components of the LOS Tool application.

### Integration with LidarDownloader

The map displays the LIDAR search polygon and allows visualizing LIDAR data.

- **Search Polygon**: Displayed as a polygon on the map
- **LIDAR Tiles**: Displayed as rectangles with metadata popups
- **Download Status**: Color-coded based on download status

### Integration with Elevation Profile

The map integrates with the elevation profile visualization.

- **Path Selection**: Clicking on the path shows the elevation profile
- **Obstruction Highlighting**: Obstructions in the profile are highlighted on the map
- **Fresnel Zone**: The Fresnel zone is visualized on both the map and profile

### Integration with AI Analysis

The map integrates with the AI path analysis functionality.

- **Analysis Results**: Displayed on the map with color coding
- **Obstruction Identification**: AI-identified obstructions are highlighted
- **Clearance Visualization**: Areas with insufficient clearance are highlighted

## API Reference

The map server provides several API endpoints for retrieving data.

### `/api/path`

Returns the line-of-sight path data.

- **Method**: GET
- **Response**: JSON object with path coordinates and metadata
- **Example Response**:
  ```json
  {
    "donor": {"lat": 42.5518, "lng": -75.2628},
    "recipient": {"lat": 42.7153, "lng": -75.1432},
    "length_km": 19.8,
    "azimuth": 28.3
  }
  ```

### `/api/fresnel`

Returns the Fresnel zone data for the path.

- **Method**: GET
- **Parameters**: `freq` (frequency in GHz)
- **Response**: JSON object with Fresnel zone coordinates
- **Example Response**:
  ```json
  {
    "zones": [
      {"radius": 0.6, "coordinates": [...]},
      {"radius": 0.8, "coordinates": [...]},
      {"radius": 1.0, "coordinates": [...]}
    ]
  }
  ```

### `/api/osm`

Queries OSM structures within a polygon.

- **Method**: POST
- **Request Body**:
  ```json
  {
    "polygon": [[-75.3, 42.5], [-75.1, 42.5], [-75.1, 42.8], [-75.3, 42.8], [-75.3, 42.5]],
    "types": ["power_tower", "mast"]
  }
  ```
- **Response**: GeoJSON FeatureCollection with structures

### `/api/towers`

Returns FCC tower data within the search polygon.

- **Method**: GET
- **Response**: GeoJSON FeatureCollection with tower features

### `/api/turbines`

Returns USGS wind turbine data within the search polygon.

- **Method**: GET
- **Response**: GeoJSON FeatureCollection with turbine features

## Troubleshooting

### Common Issues

1. **Map Server Won't Start**:
   - Check if another instance is already running
   - Verify the port is not in use
   - Check for errors in the server logs

2. **Map Won't Load**:
   - Verify the server is running
   - Check browser console for JavaScript errors
   - Ensure the tower parameters file exists and is valid

3. **Structures Not Displaying**:
   - Check if PostgreSQL is running and accessible
   - Verify the OSM data is imported correctly
   - Check for errors in the server logs

4. **Slow Map Performance**:
   - Reduce the number of displayed structures
   - Use a more efficient map provider
   - Check for memory leaks in the browser

### Diagnostic Tools

1. **Server Status Check**:
   ```python
   from map_server import is_server_running
   print(f"Map server running: {is_server_running()}")
   ```

2. **Manual Server Start**:
   ```python
   from map_server import start_server
   server_address = start_server()
   print(f"Map server started at {server_address}")
   ```

3. **Browser Developer Tools**:
   - Open browser developer tools (F12)
   - Check the Console tab for errors
   - Check the Network tab for failed requests

4. **Server Logs**:
   - Set logging level to DEBUG for more detailed information
   - Check for errors and warnings in the logs
