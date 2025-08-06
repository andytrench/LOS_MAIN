# LOS Tool Application Structure

This document provides an overview of the LOS Tool application structure, including main files, directories, and their purposes.

## Overview

The LOS Tool (Line of Sight Tool) is a comprehensive application for analyzing microwave line of sight paths, processing LIDAR data, and generating project documentation. The application is built with Python and uses a modular architecture with functionality distributed across multiple files and directories.

## Main Entry Points

| File | Description |
|------|-------------|
| `dropmap.py` | Main entry point and core application file containing the main application logic |
| `run_ai_path_analysis.py` | Standalone script to run AI path analysis without the main application |
| `run_dropmap.py` | Alternative entry point script (not recommended for direct use) |
| `fix_json_structure.py` | Utility script to verify and fix JSON structure before launching the application |

## Directory Structure

### Root Directory

The root directory contains the main application files, configuration files, and entry points.

### `/utilities`

The utilities directory contains modular components that provide specific functionality to the main application.

| Category | Files | Description |
|----------|-------|-------------|
| **UI Components** | `UI_main.py`, `ui_components.py`, `ui_panels.py`, `ui_dialogs.py` | User interface components and layouts |
| **LIDAR Processing** | `lidar_downloader.py`, `lidar_processor.py`, `lidar_search.py`, `lidar_visualization.py` | LIDAR data processing and visualization |
| **LIDAR Indexing** | `lidar_index_db.py`, `lidar_index_search.py`, `lidar_crawler.py` | LIDAR index database management and search |
| **AWS Integration** | `aws_search.py`, `aws_downloader.py`, `aws_download_handler.py`, `aws_search_with_index.py` | AWS S3 integration for LIDAR data |
| **Mapping** | `map_manager.py`, `lidar_map.py`, `lidar_map_visualization.py` | Map visualization and management |
| **Geometry** | `geometry.py`, `geometry_utils.py`, `coordinates.py` | Geometric calculations and coordinate transformations |
| **AI Analysis** | `ai_path_analyze.py`, `ai_processor.py` | AI-based path analysis and document processing |
| **Certificate Generation** | `certificate_generator.py`, `pdf_utils.py` | Certificate and PDF generation |
| **Data Management** | `file_handler.py`, `json_utils.py`, `json_loader.py`, `metadata.py` | File and data management utilities |
| **Site Management** | `site_manager.py` | Site data management |
| **Elevation Analysis** | `elevation.py`, `obstruction_analyzer.py` | Elevation profile and obstruction analysis |
| **Export Utilities** | `export_utils.py` | Data export utilities |
| **Turbine Processing** | `turbine_processor.py` | Wind turbine data processing |

### `/data`

Contains database files and persistent data storage.

| File/Directory | Description |
|----------------|-------------|
| `lidar_index.db` | SQLite database for LIDAR index |

### `/logs`

Contains application log files.

### `/temp`

Temporary files directory for processing data.

### `/XML_Temp`

Temporary directory for XML file processing.

### `/test_scripts`

Contains test scripts for various application components.

### `/test_output`

Output directory for test results and generated files.

### `/ARCHIVE`

Archive directory for unused or deprecated files, organized by category:

| Subdirectory | Description |
|--------------|-------------|
| `/ARCHIVE/indexers` | Archived LIDAR indexing scripts |
| `/ARCHIVE/exploration` | Exploration and examination scripts |
| `/ARCHIVE/visualization` | Visualization scripts |
| `/ARCHIVE/backups` | Backup files |
| `/ARCHIVE/logs` | Archived log files |
| `/ARCHIVE/temp_data` | Archived temporary data files |
| `/ARCHIVE/utilities` | Archived utility modules not used in the main application |

### `/lidar_data`

Directory for downloaded LIDAR data files.

### `/pdal_pipelines`

Contains PDAL pipeline configurations for LIDAR processing.

### `/ai_analysis_images`

Contains images generated during AI path analysis.

### `/turbine_db`

Database of wind turbine information.

### `/state_specific`

State-specific data and configurations.

## Key Files

### Core Application Files

| File | Description |
|------|-------------|
| `dropmap.py` | Main application file with the core application logic |
| `DL2.py` | UltraVerboseDownloaderer class for handling downloads |
| `certificates.py` | Certificate generation functionality |
| `metadata.py` | Metadata handling and processing |
| `projects.py` | Project management functionality |
| `turbines.py` | Turbine processing functionality |
| `state_search.py` | State boundary search functionality |
| `state_boundaries.py` | State boundary handling |
| `map_server.py` | Map server functionality |
| `LOS_map_view.py` | Map view functionality |
| `manual_sites.py` | Manual site management |
| `vegetation_profile.py` | Vegetation profile analysis |
| `certify.py` | Certificate generation utility |
| `log_config.py` | Centralized logging configuration with lazy initialization |

### LIDAR Index Management

| File | Description |
|------|-------------|
| `production_lidar_indexer.py` | Production LIDAR indexer for creating a comprehensive index |
| `init_lidar_index.py` | Initialize LIDAR index |
| `update_lidar_index.py` | Update LIDAR index with new data |
| `lidar_index_manager.py` | Command-line interface for LIDAR index management |
| `download_lidar_data.py` | Download LIDAR data utility |

### Configuration Files

| File | Description |
|------|-------------|
| `requirements.txt` | Python package dependencies |
| `.env` | Environment variables (API keys, credentials) |
| `tower_parameters.json` | Project configuration and parameters |

## Application Flow

1. The user runs `run_dropmap.py` to start the application
2. `fix_json_structure.py` verifies and fixes the JSON structure if needed
3. The main application (`dropmap.py`) is launched
4. The user can:
   - Drop a PDF file to extract site information
   - Manually enter site information
   - Search for LIDAR data using the index or AWS
   - Download and visualize LIDAR data
   - Generate certificates and reports
   - Perform AI path analysis

## Module Dependencies

The application uses a modular architecture with clear separation of concerns:

- UI components are in the `utilities` directory with `UI_` or `ui_` prefix
- LIDAR processing is handled by modules with `lidar_` prefix
- AWS integration is handled by modules with `aws_` prefix
- Certificate generation is handled by `certificates.py` and `certificate_generator.py`
- Elevation analysis is handled by `elevation.py`
- Turbine processing is handled by `turbines.py` and `turbine_processor.py`
- Site management is handled by `manual_sites.py` and `site_manager.py`

## External Dependencies

The application relies on several external libraries:

- **tkinter/tkinterdnd2**: For the GUI
- **tkintermapview**: For map visualization
- **geopandas/shapely**: For geospatial data processing
- **matplotlib**: For plotting and visualization
- **requests**: For API calls
- **boto3**: For AWS S3 access
- **reportlab**: For PDF generation
- **PIL/Pillow**: For image processing
- **numpy/pandas**: For data processing
- **earthengine-api**: For Google Earth Engine integration

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
9. Avoid duplicate code and unnecessary initialization
