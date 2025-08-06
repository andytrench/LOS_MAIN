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

### Prerequisites

- Python 3.8+
- GDAL library
- Git

### Setup

1. Clone the repository:
```bash
git clone https://github.com/andytrench/LOS_MAIN.git
cd LOS_MAIN
```

2. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
python dropmap.py
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