# LOS Tool Main Application Files

This document provides detailed information about the main application files in the LOS Tool, their functions, and how they interact with each other.

## Entry Points

### `dropmap.py`

The main entry point script that launches the application.

**Key Functions:**
- Launches the main application

**Usage:**
```bash
python dropmap.py
```

### `run_ai_path_analysis.py`

Standalone script to run AI path analysis without launching the full application.

**Key Functions:**
- Loads tower parameters from `tower_parameters.json`
- Extracts site coordinates
- Creates a Tkinter window for AI path analysis
- Launches the AI path analysis in a separate thread

**Usage:**
```bash
python run_ai_path_analysis.py
```

### `fix_json_structure.py`

Utility script to verify and fix the JSON structure before launching the application.

**Key Functions:**
- Checks if `tower_parameters.json` exists and has the correct structure
- Creates a backup of the file before modifying it
- Adds missing fields if necessary
- Ensures the file has the required structure for the application

## Core Application

### `dropmap.py`

The main application file containing the core application logic.

**Key Components:**
- `ApplicationController` class: Main controller for the application
- UI setup and configuration
- Event handlers for user interactions
- LIDAR search and download functionality
- Map visualization
- Certificate generation
- Elevation profile analysis

**Key Functions:**
- `on_file_drop`: Handles dropped PDF files
- `update_details_in_app`: Updates the application with extracted data
- `search_lidar_aws`: Searches for LIDAR data using AWS
- `download_selected_files`: Downloads selected LIDAR files
- `export_project_certificates`: Exports certificates for projects
- `write_project_metadata`: Writes project metadata to JSON

### `DL2.py`

Contains the `UltraVerboseDownloaderer` class for handling downloads with detailed progress reporting.

**Key Functions:**
- `download_file`: Downloads a file with progress reporting
- `download_files`: Downloads multiple files with progress reporting
- `download_with_retry`: Downloads a file with automatic retry on failure
- `infinite_retry_download`: Continuously retries downloading until successful

### `certificates.py`

Certificate generation functionality for creating project documentation.

**Key Functions:**
- `create_certificate`: Creates a PDF certificate for a project
- `create_json_certificate`: Creates a JSON certificate for a project
- `fetch_metadata`: Fetches metadata for a project
- `extract_metadata`: Extracts relevant information from metadata

### `metadata.py`

Metadata handling and processing for LIDAR projects.

**Key Functions:**
- `get_project_name`: Extracts project name from a filename
- `extract_metadata_from_xml`: Extracts metadata from XML files
- `extract_metadata_from_json`: Extracts metadata from JSON files
- `write_project_metadata`: Writes project metadata to JSON

### `projects.py`

Project management functionality for handling project data.

**Key Components:**
- `ProjectDetailsPane` class: UI component for displaying project details
- Project data loading and saving
- Project metadata extraction and processing

### `map_server.py`

Map server functionality for displaying interactive maps.

**Key Functions:**
- `start_server`: Starts the map server
- `stop_server`: Stops the map server
- `update_coordinates`: Updates the coordinates on the map
- `open_map`: Opens the map in a browser

### `LOS_map_view.py`

Map view functionality for displaying line of sight paths.

**Key Functions:**
- `view_on_map`: Opens a map view with site markers and a line between them
- `create_map_html`: Creates an HTML file for the map view
- `process_tower_data`: Processes tower data for map display

## LIDAR Index Management

### `production_lidar_indexer.py`

Production LIDAR indexer for creating a comprehensive index of all LIDAR data.

**Key Functions:**
- `get_projects`: Gets a list of projects from the USGS AWS S3 bucket
- `process_project`: Processes a project to extract files and metadata
- `index_projects`: Indexes multiple projects in parallel
- `optimize_database`: Optimizes the database for performance

**Usage:**
```bash
python production_lidar_indexer.py [--region REGION] [--limit LIMIT] [--db-path DB_PATH]
```

### `init_lidar_index.py`

Initializes the LIDAR index database with data from the USGS AWS S3 bucket.

**Key Functions:**
- `initialize_database`: Initializes the database
- `run_indexer`: Runs the indexer in a separate process
- `run_indexer_in_background`: Runs the indexer in the background

**Usage:**
```bash
python init_lidar_index.py [--region REGION] [--verbose] [--background]
```

### `update_lidar_index.py`

Updates the LIDAR index with new data from the USGS AWS S3 bucket.

**Key Functions:**
- `update_index`: Updates the index with new data
- `initialize_index`: Initializes the index if it doesn't exist
- `force_initialize_index`: Forces reinitialization of the index

**Usage:**
```bash
python update_lidar_index.py [--init] [--force-init] [--max-projects MAX_PROJECTS] [--verbose]
```

### `lidar_index_manager.py`

Command-line interface for managing the LIDAR index.

**Key Commands:**
- `init`: Initializes the database
- `crawl`: Crawls the USGS AWS S3 bucket to populate the index
- `update`: Updates the index with new data
- `search`: Searches for LIDAR files by location
- `stats`: Views statistics about the index

**Usage:**
```bash
python lidar_index_manager.py <command> [options]
```

### `download_lidar_data.py`

Download LIDAR data utility for downloading files from the USGS AWS S3 bucket.

**Key Functions:**
- `download_file`: Downloads a single file
- `download_files`: Downloads multiple files
- `download_project`: Downloads all files for a project

**Usage:**
```bash
python download_lidar_data.py [--project PROJECT] [--output-dir OUTPUT_DIR]
```

## Utility Files

### `log_config.py`

Centralized logging configuration for the application.

**Key Functions:**
- `initialize_logging`: Initializes centralized logging for the entire application
- `setup_logging`: Sets up logging for a specific module using the centralized configuration
- `cleanup_logging`: Cleans up logging handlers on application exit

### `vegetation_profile.py`

Vegetation profile analysis for analyzing vegetation along a line of sight path with lazy loading of Earth Engine.

**Key Functions:**
- `initialize_ee`: Initializes Earth Engine only when needed (lazy loading)
- `get_vegetation_profile`: Gets vegetation height profile between two points
- `visualize_profile`: Visualizes the vegetation profile

### `certify.py`

Certificate generation utility for creating certificates from the command line.

**Key Functions:**
- `generate_certificate`: Generates a certificate for a project
- `fetch_metadata`: Fetches metadata for a project
- `extract_metadata`: Extracts relevant information from metadata

## Configuration Files

### `tower_parameters.json`

Project configuration and parameters for the application.

**Key Sections:**
- `site_A`: Information about site A
- `site_B`: Information about site B
- `general_parameters`: General project parameters
- `turbines`: Array of turbine information
- `lidar_data`: LIDAR data information

### `requirements.txt`

Python package dependencies for the application.

**Key Dependencies:**
- Core dependencies (numpy, pandas, requests)
- Geospatial dependencies (geopandas, shapely, pyproj)
- UI dependencies (tkinterdnd2, tkintermapview, tkcalendar)
- PDF generation dependencies (reportlab, PyMuPDF)
- AWS dependencies (boto3)

### `.env`

Environment variables for the application, including API keys and credentials.

**Key Variables:**
- `AWS_ACCESS_KEY_ID`: AWS access key ID
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key
- `GOOGLE_MAPS_API_KEY`: Google Maps API key
- `MAPBOX_ACCESS_TOKEN`: Mapbox access token

## Utilities Directory

The `utilities` directory contains modular components that provide specific functionality to the main application. These are organized by category:

### UI Components

- `UI_main.py`: Main UI components and layout
- `ui_components.py`: Reusable UI components
- `ui_panels.py`: UI panels for specific functionality
- `ui_dialogs.py`: Dialog boxes for user interaction

### LIDAR Processing

- `lidar_downloader.py`: LIDAR download functionality
- `lidar_processor.py`: LIDAR data processing
- `lidar_search.py`: LIDAR search functionality
- `lidar_visualization.py`: LIDAR data visualization

### LIDAR Indexing

- `lidar_index_db.py`: LIDAR index database management
- `lidar_index_search.py`: LIDAR index search functionality
- `lidar_crawler.py`: LIDAR data crawler for indexing

### AWS Integration

- `aws_search.py`: AWS S3 search functionality
- `aws_downloader.py`: AWS S3 download functionality
- `aws_download_handler.py`: AWS download handler with UI integration
- `aws_search_with_index.py`: AWS search with index integration

### Mapping

- `map_manager.py`: Map management functionality
- `lidar_map.py`: LIDAR map visualization
- `lidar_map_visualization.py`: Advanced LIDAR map visualization

### Geometry

- `geometry.py`: Geometric calculations
- `geometry_utils.py`: Utility functions for geometry
- `coordinates.py`: Coordinate transformations and calculations

### AI Analysis

- `ai_path_analyze.py`: AI-based path analysis
- `ai_processor.py`: AI document processing

### Certificate Generation

- `certificate_generator.py`: Certificate generation functionality
- `pdf_utils.py`: PDF generation utilities

### Data Management

- `file_handler.py`: File handling utilities
- `json_utils.py`: JSON processing utilities
- `json_loader.py`: JSON loading functionality
- `metadata.py`: Metadata processing

### Site Management

- `site_manager.py`: Site data management

### Elevation Analysis

- `elevation.py`: Elevation profile analysis
- `obstruction_analyzer.py`: Obstruction analysis

### Export Utilities

- `export_utils.py`: Data export utilities

### Turbine Processing

- `turbine_processor.py`: Wind turbine data processing

### Archived Utility Modules

The following utility modules were not being used in the main application and have been moved to the ARCHIVE/utilities directory:

- `aircraft_analyze.py`: Aircraft analysis functionality (unused)
- `extract_dates.py`: Date extraction utilities (unused)
- `index_search_button.py`: Index search button functionality (unused)
- `shapefile_reader.py`: Shapefile reading functionality (unused)
- `simple_search.py`: Simple search functionality (unused)

## Data Flow

1. The user runs `run_dropmap.py` to start the application
2. `fix_json_structure.py` verifies and fixes the JSON structure if needed
3. The main application (`dropmap.py`) is launched
4. The user can:
   - Drop a PDF file to extract site information using `ai_processor.py`
   - Manually enter site information using `manual_sites.py`
   - Search for LIDAR data using `lidar_index_search.py` or `aws_search.py`
   - Download LIDAR data using `DL2.py` and `aws_download_handler.py`
   - Visualize LIDAR data using `lidar_map_visualization.py`
   - Generate certificates using `certificates.py` and `certificate_generator.py`
   - Perform AI path analysis using `ai_path_analyze.py`
5. The application stores project data in `tower_parameters.json`
6. The application generates certificates and reports in the `test_output` directory

## Application Startup Optimization

The application has been optimized for faster startup and more efficient resource usage:

### Centralized Logging

- The logging system has been centralized to use a single log file for all modules
- The `initialize_logging` function in `log_config.py` sets up logging once at application startup
- Each module uses the centralized logging configuration through the `setup_logging` function
- Log handlers are properly closed on application exit through the `cleanup_logging` function

### Lazy Loading

- Earth Engine is initialized only when needed (lazy loading) in `vegetation_profile.py`
- The `initialize_ee` function is called only when vegetation profile analysis is performed
- This reduces startup time and resource usage when Earth Engine functionality is not needed

### Error Handling

- The application includes proper error handling for missing or uninitialized attributes
- The `file_list` attribute in the `TurbineProcessor` class is properly initialized
- The `ProjectDetailsPane` class checks if attributes exist before accessing them

### Code Optimization

- Duplicate code has been removed, such as the duplicate downloader setting
- Unnecessary initialization has been deferred until needed
- Warning messages during startup have been eliminated

## Development Guidelines

When extending the application:

1. Follow the modular architecture pattern
2. Place utility functions in the appropriate module in the `utilities` directory
3. Use the centralized logging system for debugging and error reporting
4. Update the JSON structure when adding new data fields
5. Write test scripts in the `test_scripts` directory
6. Archive unused or deprecated files in the `ARCHIVE` directory
7. Use lazy loading for resource-intensive components
8. Properly initialize attributes before accessing them
