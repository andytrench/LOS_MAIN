# LOStool (Line of Sight Tool) - Technical Summary

## 1. Project Overview

### Primary Purpose
LOStool is a comprehensive desktop application for **microwave line-of-sight (LOS) path analysis** in telecommunications. It automates the process of analyzing radio frequency propagation paths between two sites by integrating LIDAR elevation data, obstruction analysis, and regulatory compliance documentation.

### Target Users
- **RF Engineers**: Designing microwave communication links
- **Telecommunications Consultants**: Performing path studies for clients
- **Regulatory Compliance Teams**: Generating documentation for FCC/regulatory submissions
- **Network Planning Teams**: Site selection and link feasibility analysis

### Technology Stack
- **Language**: Python 3.10+
- **GUI Framework**: Tkinter with tkinterdnd2 for drag-drop
- **Mapping**: tkintermapview, Leaflet.js integration
- **Geospatial**: GeoPandas, Shapely, PyProj for coordinate transformations
- **Data Processing**: NumPy, Pandas for data manipulation
- **Visualization**: Matplotlib for elevation profiles and charts
- **PDF Processing**: PyMuPDF, ReportLab for document generation
- **Cloud Integration**: Boto3 for AWS S3 LIDAR data access
- **AI Integration**: Custom AI processor for PDF document extraction
- **Database**: SQLite for LIDAR indexing and tower databases

### Deployment Type
**Desktop Application** with hybrid cloud integration for data sources

## 2. Folder Structure & Architecture

```
LOStool/
├── dropmap.py                    # Main application entry point (6,062 lines)
├── DL2.py                        # Download manager (2,041 lines)
├── tower_parameters.json         # Project data storage
├── utilities/                    # Modular components (50+ files)
│   ├── UI_main.py               # Main UI framework
│   ├── ai_processor.py          # PDF document AI extraction
│   ├── lidar_*.py               # LIDAR processing modules
│   ├── aws_*.py                 # AWS S3 integration
│   ├── turbine_processor.py     # Wind turbine analysis
│   ├── elevation.py             # Elevation profile analysis
│   ├── certificate_generator.py # PDF report generation
│   └── map_manager.py           # Interactive mapping
├── NOAA/                        # NOAA LIDAR data integration
│   ├── noaa_index_db.py         # NOAA database management
│   ├── noaa_data_crawler.py     # Data discovery crawler
│   └── noaa_shapefile_indexer.py # Shapefile processing
├── data/                        # SQLite databases
├── docs/                        # Technical documentation
└── temp/                        # Temporary processing files
```

### Entry Points
- **Primary**: `dropmap.py` - Main GUI application
- **Utilities**: Various standalone scripts for specific tasks
- **Configuration**: `tower_parameters.json` - Project state persistence

## 3. Core User Functions

### 3.1 Project Initialization
**Function**: PDF Document Processing and Site Extraction
- **User Journey**: Drag-drop PDF → AI extraction → Site coordinates populated
- **Key Files**: `utilities/ai_processor.py`, `dropmap.py:on_file_drop()`
- **Input**: PDF documents (engineering drawings, site surveys)
- **Output**: Structured site data (coordinates, elevations, antenna heights)

### 3.2 LIDAR Data Discovery and Download
**Function**: Multi-source LIDAR search and acquisition
- **User Journey**: Define search area → Search multiple sources → Download tiles
- **Key Files**: 
  - `utilities/lidar_index_search.py` - USGS data search
  - `utilities/aws_search.py` - AWS S3 integration  
  - `NOAA/noaa_index_search.py` - NOAA data search
  - `DL2.py` - Download management
- **External Dependencies**: 
  - USGS TNM API
  - AWS S3 (rockyweb.usgs.gov)
  - NOAA Digital Coast S3 bucket
- **Input**: Polygon coordinates around LOS path
- **Output**: LAZ/LAS point cloud files with spatial indexing

### 3.3 Elevation Profile Analysis
**Function**: Line-of-sight obstruction analysis
- **User Journey**: Load LIDAR → Generate profile → Identify obstructions
- **Key Files**: `utilities/elevation.py`, `utilities/obstruction_analyzer.py`
- **Input**: Site coordinates, LIDAR point clouds
- **Output**: Elevation profiles, clearance analysis, Fresnel zone calculations

### 3.4 Wind Turbine Detection
**Function**: Automated turbine identification and analysis
- **User Journey**: Search area → Detect turbines → Analyze impact
- **Key Files**: `utilities/turbine_processor.py`
- **External Dependencies**: FAA turbine database, state-specific databases
- **Input**: Search polygon
- **Output**: Turbine locations, heights, potential interference analysis

### 3.5 Certificate Generation
**Function**: Regulatory compliance documentation
- **User Journey**: Complete analysis → Generate reports → Export certificates
- **Key Files**: `utilities/certificate_generator.py`, `utilities/pdf_utils.py`
- **Input**: Project data, analysis results
- **Output**: PDF certificates, compliance documentation

## 4. Technical Components (Reusable Elements)

### 4.1 Data Models/Schemas
```python
# Project Data Structure (tower_parameters.json)
{
  "site_A": {
    "site_id": str,
    "latitude": str,  # DMS format
    "longitude": str,
    "elevation_ft": float,
    "antenna_cl_ft": float,
    "azimuth_deg": float
  },
  "site_B": { /* same structure */ },
  "general_parameters": {
    "link_id": str,
    "link_name": str,
    "frequency_ghz": float,
    "path_length_mi": float
  },
  "turbines": [],
  "lidar_data": {}
}
```

### 4.2 API Endpoints/Integration Points
- **USGS TNM API**: `https://tnmaccess.nationalmap.gov/api/v1/products`
- **AWS S3 LIDAR**: `https://rockyweb.usgs.gov/vdelivery/Datasets/`
- **NOAA S3**: `https://noaa-nos-coastal-lidar-pds.s3.amazonaws.com/`
- **FAA Turbine Database**: State-specific endpoints

### 4.3 UI Components
```python
# Reusable UI Components
class ApplicationController:
    def search_lidar(self)           # USGS search interface
    def search_lidar_aws(self)       # AWS search interface  
    def search_noaa_data(self)       # NOAA search interface
    def export_project_certificates() # Report generation
    def find_turbines(self)          # Turbine detection
```

### 4.4 Utility Functions
```python
# Coordinate Transformations
def convert_dms_to_decimal(lat_dms, lon_dms)
def calculate_distance_meters(lat1, lon1, lat2, lon2)

# Geometry Calculations  
def calculate_polygon_points(start, end, width, extension)
def generate_fresnel_zone(site_a, site_b, frequency)

# File Operations
def safe_copy_file(source, destination)
def export_polygon_as_kml(polygon_points)
```

### 4.5 Business Logic
- **Path Loss Calculations**: Fresnel zone analysis, clearance calculations
- **Spatial Indexing**: R-tree indexing for LIDAR tile selection
- **Coordinate Systems**: UTM ↔ WGS84 transformations
- **Data Validation**: Site coordinate validation, elevation consistency checks

## 5. External Integrations

### 5.1 Third-party APIs
- **USGS TNM API**: LIDAR data discovery, metadata retrieval
- **AWS S3**: Direct file downloads, bucket listing
- **NOAA Digital Coast**: Coastal LIDAR data access
- **Google Earth Engine**: Vegetation analysis (lazy-loaded)

### 5.2 Database Connections
- **SQLite Databases**:
  - `data/lidar_index.db` - USGS LIDAR spatial index
  - `NOAA/data/noaa_index.db` - NOAA LIDAR spatial index
  - `turbine_db/` - Wind turbine databases

### 5.3 File System Operations
- **LIDAR Processing**: LAZ/LAS file handling with PDAL integration
- **PDF Generation**: ReportLab for certificates, PyMuPDF for parsing
- **Temporary Files**: Managed temp directory system with cleanup
- **Export Formats**: KML, Shapefile, JSON, CSV export capabilities

## 6. Data Flow & State Management

### 6.1 Data Sources
- **User Input**: PDF documents, manual coordinate entry
- **External APIs**: USGS, NOAA, AWS S3 data services
- **Local Databases**: Cached spatial indexes, turbine databases
- **File System**: Downloaded LIDAR files, generated reports

### 6.2 Data Transformations
```python
# Coordinate Processing Pipeline
PDF → AI Extraction → DMS Coordinates → Decimal Degrees → UTM Projection → Spatial Query

# LIDAR Processing Pipeline  
Search Polygon → Spatial Index Query → File Discovery → Download → Point Cloud Processing → Elevation Profile
```

### 6.3 State Management
- **Project State**: Persisted in `tower_parameters.json`
- **UI State**: Tkinter variable bindings, map widget state
- **Download State**: Queue management in `DL2.py`
- **Cache Management**: Temporary file lifecycle, database connections

## 7. Integration Readiness Assessment

### 7.1 Modular Components (High Reusability)
- **Coordinate Systems**: `utilities/coordinates.py` - Pure functions, no dependencies
- **Geometry Calculations**: `utilities/geometry.py` - Mathematical operations
- **LIDAR Indexing**: `utilities/lidar_index_*.py` - Database-driven spatial search
- **Download Management**: `DL2.py` - Generic file download with progress tracking
- **PDF Generation**: `utilities/certificate_generator.py` - Template-based reporting

### 7.2 Tightly Coupled Code (Refactoring Needed)
- **Main Application**: `dropmap.py` - Monolithic GUI controller (6,062 lines)
- **UI Integration**: Heavy Tkinter dependencies throughout
- **Global State**: Shared variables between modules
- **File Paths**: Hardcoded paths to `tower_parameters.json`

### 7.3 Shared Dependencies
- **Geospatial Stack**: GeoPandas, Shapely, PyProj (common across GIS applications)
- **Data Processing**: NumPy, Pandas (universal data science stack)
- **Cloud Integration**: Boto3 (standard AWS integration)
- **Database**: SQLite (lightweight, embeddable)

### 7.4 Migration Considerations
- **GUI Framework**: Tkinter → Modern web framework (React/Vue) or cross-platform (Electron)
- **State Management**: JSON file → Database or modern state management
- **API Architecture**: Monolithic → Microservices with REST/GraphQL APIs
- **Configuration**: Environment variables and config files vs hardcoded values

## 8. Key Code Examples

### 8.1 Core Search Function
```python
def search_lidar_index(polygon_points, start_date=None, end_date=None):
    """Search LIDAR index for files intersecting polygon"""
    polygon = Polygon(polygon_points)
    bounds = polygon.bounds
    files = search_files_by_bbox(*bounds, start_date, end_date)
    return convert_to_tnm_format(files)
```

### 8.2 Download Management
```python
class UltraVerboseDownloaderer:
    def add_urls_bulk(self, file_info_list):
        """Bulk add URLs with metadata for download"""
        for url, filename, info in file_info_list:
            self.file_info[url] = info
            self.download_queue.put((url, filename))
```

### 8.3 Coordinate Transformation
```python
def convert_dms_to_decimal(lat_dms, lon_dms):
    """Convert DMS coordinates to decimal degrees"""
    lat_decimal = parse_dms(lat_dms)
    lon_decimal = parse_dms(lon_dms)
    return lat_decimal, lon_decimal
```

## 9. V2 Integration Strategy

### 9.1 Immediate Reuse Candidates
1. **LIDAR Indexing System** - Spatial database with 50,000+ indexed files
2. **Download Management** - Robust multi-threaded downloader with retry logic
3. **Coordinate Utilities** - Battle-tested coordinate transformation functions
4. **PDF Generation** - Template-based certificate generation system
5. **Geometry Calculations** - RF propagation and spatial analysis functions

### 9.2 Modernization Priorities
1. **API Layer**: Extract business logic into REST/GraphQL services
2. **Frontend Separation**: Decouple UI from business logic
3. **Configuration Management**: Environment-based configuration system
4. **Database Migration**: SQLite → PostgreSQL/MongoDB for scalability
5. **Authentication**: Add user management and project sharing capabilities

### 9.3 Architecture Evolution
```
Current: Monolithic Desktop App
    ↓
V2: Microservices + Modern Frontend
    ├── LIDAR Service (spatial indexing, search)
    ├── Download Service (file management)
    ├── Analysis Service (RF calculations)
    ├── Report Service (PDF generation)
    └── Web Frontend (React/Vue SPA)
```

This LOStool represents a mature, feature-rich application with significant domain expertise embedded in its codebase. The modular utility functions and specialized algorithms make it an excellent candidate for service-oriented architecture migration while preserving the core intellectual property and functionality. 