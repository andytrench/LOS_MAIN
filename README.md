# LOS_MAIN - Line of Sight Analysis Tool

A comprehensive Python application for microwave line-of-sight (LOS) path analysis, LiDAR data processing, and obstruction analysis for telecommunications engineering.

## Features

- **Interactive Map Interface**: Visualize microwave paths and potential obstructions
- **LiDAR Data Integration**: Search, download, and process LiDAR point cloud data
- **Elevation Profile Analysis**: Generate detailed elevation profiles along microwave paths
- **Obstruction Detection**: Identify wind turbines and other potential RF obstructions
- **AI-Powered Document Processing**: Extract site parameters from engineering documents
- **Certificate Generation**: Create compliance certificates and reports
- **Multi-Source Data Support**: Integrate data from USGS, NOAA, and other sources

## Installation

### 🚀 Quick Start (Automated Installation)

**The easiest way to install LOS_MAIN is using our automated installation scripts:**

#### macOS
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
chmod +x install_macos.sh
./install_macos.sh
```

#### Windows
1. Download and run `install_windows.bat` as Administrator
2. The script will automatically install all dependencies
3. Double-click the desktop shortcut to run

#### Linux
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
chmod +x install_linux.sh
./install_linux.sh
```

### 📋 What the Automated Installers Do

- ✅ **Install system dependencies**: GDAL, PostgreSQL, Tesseract OCR
- ✅ **Set up Python environment**: Miniconda with conda-forge packages
- ✅ **Install all Python packages**: Geospatial, AI, GUI, and utility libraries
- ✅ **Configure database**: PostgreSQL with PostGIS extension
- ✅ **Create launchers**: Desktop shortcuts and activation scripts
- ✅ **Environment template**: `.env.template` for configuration

### 🔧 Manual Installation (Advanced Users)

If you prefer manual installation or need custom configuration:

#### Prerequisites
- Python 3.8+
- GDAL library
- PostgreSQL with PostGIS
- Tesseract OCR
- Git

#### Setup Steps

1. **Clone the repository:**
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
```

2. **Install system dependencies:**

**macOS:**
```bash
brew install gdal postgresql postgis tesseract
brew services start postgresql
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install gdal-bin libgdal-dev postgresql postgis tesseract-ocr
sudo systemctl start postgresql
```

**Windows:**
- Install PostgreSQL from [postgresql.org](https://www.postgresql.org/download/windows/)
- Install GDAL from [OSGeo4W](https://trac.osgeo.org/osgeo4w/)
- Install Tesseract from [GitHub releases](https://github.com/UB-Mannheim/tesseract/wiki)

3. **Create Python environment:**
```bash
# Using conda (recommended for geospatial packages)
conda create -n lostool python=3.11
conda activate lostool
conda install -c conda-forge gdal geopandas rasterio fiona shapely pyproj

# Or using venv
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

4. **Install Python dependencies:**
```bash
pip install -r requirements.txt
```

5. **Set up database:**
```sql
-- Connect to PostgreSQL as superuser
CREATE DATABASE lostool;
CREATE USER lostool WITH PASSWORD 'lostool';
GRANT ALL PRIVILEGES ON DATABASE lostool TO lostool;
\c lostool
CREATE EXTENSION postgis;
```

6. **Configure environment:**
```bash
cp .env.template .env
# Edit .env with your API keys and configuration
```

7. **Run the application:**
```bash
python dropmap.py
```

### 🔑 Configuration Required

After installation, you must configure your API keys and credentials:

1. **Copy environment template:**
```bash
cp .env.template .env
```

2. **Edit `.env` file with your credentials:**
- **Anthropic API key** (for AI features)
- **Google Maps API key** (for mapping)
- **AWS credentials** (for LiDAR data access)
- **Google Earth Engine credentials** (for satellite data)

3. **Add Google Earth Engine JSON credentials file** to your project directory

### 🐛 Troubleshooting

**GDAL Issues on macOS M1/M2:**
```bash
# Use conda-forge for ARM64 compatibility
conda install -c conda-forge gdal
```

**Permission Issues on Windows:**
- Run installation script as Administrator
- Ensure Python is in PATH

**Database Connection Issues:**
```bash
# Check PostgreSQL service
sudo systemctl status postgresql  # Linux
brew services list | grep postgresql  # macOS
```

**Missing GUI packages on Linux:**
```bash
# Install GUI packages if running in desktop environment
pip install tkinterdnd2 tkintermapview tkcalendar
```

## Usage

### Basic Workflow

1. **Load Project**: Drag and drop an engineering document (PDF) containing site coordinates
2. **Search LiDAR**: Use the search tools to find relevant LiDAR data for your path
3. **Analyze Path**: Review elevation profiles and identify potential obstructions
4. **Generate Reports**: Create certificates and export results

### Key Components

- `dropmap.py`: Main application entry point
- `projects.py`: Project metadata and details management
- `utilities/`: Core utility modules for various functions
- `DL2.py`: Download manager for LiDAR data

## Configuration

The application uses `tower_parameters.json` to store project configuration and site data. This file is automatically created and updated as you work with projects.

## Contributing

This is a specialized tool for telecommunications engineering. Contributions should maintain compatibility with existing workflows and data formats.

## License

[Add your license information here]

## Contact

For questions or support, contact: andytrench@gmail.com