# LIDAR Index System

This system provides a comprehensive index of LIDAR data available in the USGS AWS S3 bucket, with detailed metadata extraction and optimization for production use.

## Features

- Indexes all available LIDAR projects in the USGS AWS S3 bucket
- Extracts detailed metadata from EPT sources
- Provides precise spatial information for each file
- Optimizes the database for performance
- Supports spatial queries to find LIDAR data by location
- Includes progress reporting and error handling

## Requirements

- Python 3.10 or higher
- Required Python packages:
  - boto3
  - sqlite3
  - logging
  - json
  - datetime
  - concurrent.futures

## Installation

1. Clone the repository:
   ```
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

3. Set up AWS credentials:
   ```
   export AWS_ACCESS_KEY_ID=<your-access-key>
   export AWS_SECRET_ACCESS_KEY=<your-secret-key>
   export AWS_REGION=us-west-2
   ```

## Usage

### Creating a Production LIDAR Index

To create a comprehensive index of all LIDAR data:

```
python production_lidar_indexer.py
```

Options:
- `--region REGION`: Region to index (e.g., 'CO' for Colorado, 'all' for all regions)
- `--limit LIMIT`: Limit the number of projects to index (for testing)
- `--db-path DB_PATH`: Path to the database file

Examples:
```
# Index all LIDAR data
python production_lidar_indexer.py

# Index only Colorado LIDAR data
python production_lidar_indexer.py --region CO

# Index 5 projects for testing
python production_lidar_indexer.py --limit 5

# Specify a custom database path
python production_lidar_indexer.py --db-path ../DATABASE/lidar_index.db
```

### Searching for LIDAR Data

To search for LIDAR data by location:

```python
from utilities.lidar_index_search import search_lidar_index

# Define a polygon for the search area
polygon_points = [
    (37.59, -104.82),  # Bottom-left
    (37.59, -104.35),  # Bottom-right
    (37.83, -104.35),  # Top-right
    (37.83, -104.82),  # Top-left
    (37.59, -104.82)   # Back to start to close the polygon
]

# Search for LIDAR data
results = search_lidar_index(polygon_points, retrieve_metadata=True)

# Print results
print(f"Found {len(results.get('items', []))} LIDAR files")
```

## Database Schema

The LIDAR index database has the following tables:

### Projects Table

- `id`: Project ID (primary key)
- `name`: Project name
- `prefix`: Project prefix in the S3 bucket
- `year`: Project year
- `description`: Project description
- `source`: Project source
- `date_added`: Date the project was added to the index
- `date_updated`: Date the project was last updated
- `metadata`: Project metadata (JSON)

### Files Table

- `id`: File ID (primary key)
- `project_id`: Project ID (foreign key)
- `bucket`: S3 bucket name
- `key`: S3 key
- `filename`: File name
- `size`: File size in bytes
- `last_modified`: Date the file was last modified
- `format`: File format
- `min_x`: Minimum X coordinate (longitude)
- `min_y`: Minimum Y coordinate (latitude)
- `max_x`: Maximum X coordinate (longitude)
- `max_y`: Maximum Y coordinate (latitude)
- `polygon`: Polygon points (JSON)
- `metadata_source`: Source of the metadata
- `date_added`: Date the file was added to the index
- `date_updated`: Date the file was last updated
- `metadata`: File metadata (JSON)

### Crawl History Table

- `id`: Crawl ID (primary key)
- `start_time`: Crawl start time
- `end_time`: Crawl end time
- `status`: Crawl status
- `projects_added`: Number of projects added
- `projects_updated`: Number of projects updated
- `files_added`: Number of files added
- `files_updated`: Number of files updated
- `error`: Error message

## Metadata

The LIDAR index includes detailed metadata for each file, extracted from the EPT sources:

- **Bounds**: The bounding box of the file in WGS84 coordinates
- **Points**: The number of points in the file
- **Schema**: The schema of the point data, including the dimensions, types, scales, and offsets
- **SRS**: The spatial reference system information, including the EPSG code and WKT

## Performance Optimization

The LIDAR index is optimized for performance with the following features:

- **Spatial Indexing**: The database uses spatial indexes to efficiently find files by location
- **Batch Processing**: Files are processed in batches to reduce memory usage
- **Multithreading**: Multiple threads are used to process files in parallel
- **Database Optimization**: The database is optimized with VACUUM and ANALYZE commands
- **Index Optimization**: Indexes are created for common queries

## Maintenance

To optimize the database for performance:

```python
from utilities.lidar_index_db import optimize_database

# Optimize the database
optimize_database()
```

To get statistics about the database:

```python
from utilities.lidar_index_db import get_database_stats

# Get database statistics
stats = get_database_stats()
print(f"Projects: {stats['project_count']}")
print(f"Files: {stats['file_count']}")
print(f"Database size: {stats['db_size'] / (1024 * 1024):.2f} MB")
```

## Troubleshooting

If you encounter any issues, check the log file for details:

```
cat lidar_indexer_<timestamp>.log
```

Common issues:
- **AWS Credentials**: Make sure your AWS credentials are set correctly
- **Network Issues**: Check your internet connection
- **Memory Issues**: If you run out of memory, try reducing the batch size or number of worker threads
- **Database Issues**: If the database is corrupted, try rebuilding it from scratch

## License

This project is licensed under the MIT License - see the LICENSE file for details.
