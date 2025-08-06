# LOS Tool Folder Hierarchy

This document provides a detailed overview of the folder structure and organization of the LOS Tool application.

## Root Directory

The root directory contains the main application files, configuration files, and entry points.

```
/
├── .env                      # Environment variables (API keys, credentials)
├── .git                      # Git repository data
├── .gitignore                # Git ignore file
├── .venv                     # Python virtual environment
├── ARCHIVE/                  # Archive of unused or deprecated files
├── XML_Temp/                 # Temporary directory for XML file processing
├── __pycache__/              # Python bytecode cache
├── ai_analysis_images/       # Images generated during AI path analysis
├── assets/                   # Static assets for the application
├── cache/                    # Cache directory for temporary data
├── data/                     # Database files and persistent data storage
├── docs/                     # Documentation files
├── lidar_data/               # Downloaded LIDAR data files
├── logs/                     # Application log files
├── node_modules/             # Node.js modules for web components
├── pdal_pipelines/           # PDAL pipeline configurations for LIDAR processing
├── state_specific/           # State-specific data and configurations
├── static/                   # Static files for web components
├── temp/                     # Temporary files directory for processing data
├── templates/                # Template files for web components
├── test_output/              # Output directory for test results and generated files
├── test_samples/             # Sample files for testing
├── test_scripts/             # Test scripts for various application components
├── turbine_db/               # Database of wind turbine information
├── utilities/                # Utility modules and components
├── ~                         # Temporary directory
├── run_dropmap.py            # Main entry point script
├── run_ai_path_analysis.py   # Standalone script for AI path analysis
├── dropmap.py                # Main application file
├── fix_json_structure.py     # JSON structure verification and fixing
├── requirements.txt          # Python package dependencies
├── tower_parameters.json     # Project configuration and parameters
└── ... (other application files)
```

## Key Directories

### `/utilities`

The utilities directory contains modular components that provide specific functionality to the main application. These are organized by functionality:

```
/utilities/
├── __pycache__/              # Python bytecode cache
├── UI_main.py                # Main UI components and layout
├── ai_path_analyze.py        # AI-based path analysis
├── ai_processor.py           # AI document processing
├── aws_download_handler.py   # AWS download handler with UI integration
├── aws_downloader.py         # AWS S3 download functionality
├── aws_search.py             # AWS S3 search functionality
├── aws_search_with_index.py  # AWS search with index integration
├── certificate_generator.py  # Certificate generation functionality
├── coordinates.py            # Coordinate transformations and calculations
├── docs/                     # Documentation for utilities
├── elevation.py              # Elevation profile analysis
├── export_utils.py           # Data export utilities
├── file_handler.py           # File handling utilities
├── geometry.py               # Geometric calculations
├── geometry_utils.py         # Utility functions for geometry
├── json_loader.py            # JSON loading functionality
├── json_utils.py             # JSON processing utilities
├── lidar_crawler.py          # LIDAR data crawler for indexing
├── lidar_downloader.py       # LIDAR download functionality
├── lidar_index_db.py         # LIDAR index database management
├── lidar_index_search.py     # LIDAR index search functionality
├── lidar_map.py              # LIDAR map visualization
├── lidar_map_visualization.py # Advanced LIDAR map visualization
├── lidar_processor.py        # LIDAR data processing
├── lidar_search.py           # LIDAR search functionality
├── lidar_visualization.py    # LIDAR data visualization
├── map_manager.py            # Map management functionality
├── metadata.py               # Metadata processing
├── obstruction_analyzer.py   # Obstruction analysis
├── pdf_utils.py              # PDF generation utilities
├── point_search.py           # Point search functionality
├── search_rings.py           # Search ring generation
├── site_manager.py           # Site data management
├── tile_index_manager.py     # Tile index management
├── turbine_processor.py      # Wind turbine data processing
├── ui_components.py          # Reusable UI components
├── ui_dialogs.py             # Dialog boxes for user interaction
├── ui_panels.py              # UI panels for specific functionality
└── visualization_utils.py    # Visualization utilities
```

### `/ARCHIVE`

The ARCHIVE directory contains unused or deprecated files, organized by category:

```
/ARCHIVE/
├── LIDAR_INDEX_README.md     # Archived README file
├── backups/                  # Backup files
│   └── dropmap_backup.py     # Backup of the main application file
├── exploration/              # Exploration and examination scripts
│   ├── examine_ept_sources.py # EPT sources examination script
│   └── explore_usgs_lidar_bucket.py # USGS LIDAR bucket exploration script
├── indexers/                 # Archived LIDAR indexing scripts
│   ├── check_formats.py      # Format checking utility
│   ├── create_pdal_pipeline.py # PDAL pipeline creation utility
│   ├── fast_lidar_indexer.py # Fast LIDAR indexer
│   ├── high_performance_indexer.py # High performance LIDAR indexer
│   ├── improved_index_colorado_lidar.py # Colorado LIDAR indexer
│   ├── index_all_lidar_data.py # All LIDAR data indexer
│   ├── list_colorado_lidar.py # Colorado LIDAR listing utility
│   ├── query_lidar_index.py  # LIDAR index query utility
│   ├── query_lidar_index_db.py # LIDAR index database query utility
│   ├── search_las_animas_lidar_direct.py # Las Animas LIDAR search utility
│   └── update_lidar_bounding_boxes.py # LIDAR bounding box update utility
├── logs/                     # Archived log files
│   ├── TowerGenerator.log    # Tower generator log
│   ├── download.log          # Download log
│   ├── improved_colorado_lidar_index_20250404_141812.log # Indexer log
│   ├── lidar_manager_log.txt # LIDAR manager log
│   ├── smartmerge.log        # Smart merge log
│   └── startup_debug.log     # Startup debug log
├── temp_data/                # Archived temporary data files
│   ├── lidar_boundaries.json # LIDAR boundaries data
│   ├── lidar_boundaries_complete.json # Complete LIDAR boundaries data
│   ├── lidar_index_search_results.json # LIDAR index search results
│   ├── project_search_results.json # Project search results
│   ├── tile_indices_results.json # Tile indices results
│   └── updated_lidar_index_search_results.json # Updated search results
├── utilities/                # Archived utility modules
│   ├── aircraft_analyze.py   # Aircraft analysis functionality (unused)
│   ├── extract_dates.py      # Date extraction utilities (unused)
│   ├── index_search_button.py # Index search button functionality (unused)
│   ├── shapefile_reader.py   # Shapefile reading functionality (unused)
│   └── simple_search.py      # Simple search functionality (unused)
├── visualization/            # Visualization scripts
│   ├── simple_visualize.py   # Simple visualization utility
│   ├── visualize_ept_data.py # EPT data visualization utility
│   ├── visualize_lidar_coverage.py # LIDAR coverage visualization utility
│   └── visualize_lidar_data.py # LIDAR data visualization utility
└── write_project_metadata.py # Project metadata writing utility
```

### `/data`

Contains database files and persistent data storage:

```
/data/
└── lidar_index.db            # SQLite database for LIDAR index
```

### `/logs`

Contains application log files:

```
/logs/
└── ... (various log files)
```

### `/temp`

Temporary files directory for processing data:

```
/temp/
└── ... (temporary files)
```

### `/test_scripts`

Contains test scripts for various application components:

```
/test_scripts/
├── check_all_projects.py     # Script to check all projects
├── check_ee_auth.py          # Earth Engine authentication check
├── ee_auth_test.py           # Earth Engine authentication test
├── ee_sentinel_tile.py       # Sentinel tile test
├── fetch_sentinel_tile.sh    # Sentinel tile fetch script
├── get_sentinel_image.py     # Sentinel image retrieval script
├── run_ai_path_analysis.py   # AI path analysis test
├── setup_ee_auth.md          # Earth Engine authentication setup guide
├── test_aws_specific.py      # AWS-specific tests
├── test_ept_crawler.py       # EPT crawler test
├── test_las_animas_search.py # Las Animas search test
├── test_las_animas_search_with_file_bounds.py # Las Animas search with file bounds
├── test_lassen_area_search.py # Lassen area search test
├── test_lidar_index_search.py # LIDAR index search test
├── test_output/              # Test output directory
├── test_project_search.py    # Project search test
├── test_spatial_search.py    # Spatial search test
├── test_specific_area_search.py # Specific area search test
├── test_tnm_api.py           # TNM API test
├── update_map_view.py        # Map view update test
└── update_map_view_simple.py # Simple map view update test
```

### `/test_output`

Output directory for test results and generated files:

```
/test_output/
└── ... (generated files and test results)
```

### `/lidar_data`

Directory for downloaded LIDAR data files:

```
/lidar_data/
└── ... (downloaded LIDAR data files)
```

### `/pdal_pipelines`

Contains PDAL pipeline configurations for LIDAR processing:

```
/pdal_pipelines/
└── ... (PDAL pipeline configuration files)
```

### `/ai_analysis_images`

Contains images generated during AI path analysis:

```
/ai_analysis_images/
└── ... (AI analysis images)
```

### `/turbine_db`

Database of wind turbine information:

```
/turbine_db/
└── ... (turbine database files)
```

### `/state_specific`

State-specific data and configurations:

```
/state_specific/
└── ... (state-specific data files)
```

## File Organization Principles

The LOS Tool application follows several organizational principles:

1. **Modular Architecture**: Functionality is divided into modules that are organized by purpose.
2. **Separation of Concerns**: Different aspects of the application are handled by different modules.
3. **Utility-Based Organization**: Utility functions are organized in the `utilities` directory by their purpose.
4. **Clear Entry Points**: The application has clear entry points (`run_dropmap.py`, `run_ai_path_analysis.py`).
5. **Archiving Unused Files**: Unused or deprecated files are moved to the `ARCHIVE` directory.
6. **Temporary File Management**: Temporary files are stored in dedicated directories (`temp`, `XML_Temp`).
7. **Test Separation**: Test scripts are kept separate from the main application code.
8. **Documentation**: Documentation is stored in the `docs` directory.

## Best Practices for Adding New Files

When adding new files to the application:

1. **Follow the Existing Structure**: Place files in the appropriate directory based on their function.
2. **Use Descriptive Names**: File names should clearly indicate their purpose.
3. **Add Documentation**: Document the purpose and functionality of new files.
4. **Update Requirements**: Update `requirements.txt` if new dependencies are added.
5. **Write Tests**: Write test scripts for new functionality in the `test_scripts` directory.
6. **Archive Old Versions**: Move old versions of files to the `ARCHIVE` directory.
7. **Keep the Root Directory Clean**: Avoid adding new files to the root directory unless they are entry points or configuration files.

## Conclusion

The LOS Tool application has a well-organized folder structure that follows clear principles. By understanding this structure, developers can easily navigate the codebase, find relevant files, and add new functionality in a consistent manner.
