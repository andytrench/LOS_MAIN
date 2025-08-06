"""
LIDAR Index Database Module

This module provides functions to create, maintain, and query a comprehensive
index of LIDAR files available in the USGS AWS S3 bucket.
"""

import os
import sqlite3
import logging
import json
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Database file path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              '..', 'DATABASE', 'lidar_index.db')

def init_database(db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Initialize the LIDAR index database.

    Args:
        db_path: Path to the database file
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        logger.info(f"Initializing LIDAR index database at {db_path}")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create projects table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            prefix TEXT NOT NULL,
            year INTEGER,
            description TEXT,
            source TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT
        )
        """)

        # Create files table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            bucket TEXT NOT NULL,
            key TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            size INTEGER,
            last_modified TIMESTAMP,
            format TEXT,
            min_x REAL,
            min_y REAL,
            max_x REAL,
            max_y REAL,
            polygon TEXT,
            metadata_source TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            date_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            metadata TEXT,
            ept_json_url TEXT,
            ept_sources_url TEXT,
            ept_metadata_url TEXT,
            point_count INTEGER,
            resolution REAL,
            point_spacing REAL,
            coordinate_system TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
        )
        """)

        # Create spatial index on files
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_bbox ON files (min_x, min_y, max_x, max_y)
        """)

        # Create index on project_id
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_project_id ON files (project_id)
        """)

        # Create index on format
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_format ON files (format)
        """)

        # Create crawl_history table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_time TIMESTAMP NOT NULL,
            end_time TIMESTAMP,
            status TEXT NOT NULL,
            projects_added INTEGER DEFAULT 0,
            projects_updated INTEGER DEFAULT 0,
            files_added INTEGER DEFAULT 0,
            files_updated INTEGER DEFAULT 0,
            error TEXT
        )
        """)

        # Commit changes
        conn.commit()

        logger.info("LIDAR index database initialized successfully")

    except Exception as e:
        logger.error(f"Error initializing LIDAR index database: {str(e)}", exc_info=True)
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def add_project(project_data: Dict[str, Any], db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Add a project to the database.

    Args:
        project_data: Project data
        db_path: Path to the database file

    Returns:
        int: Project ID
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Extract project data
        name = project_data.get('name')
        prefix = project_data.get('prefix')
        year = project_data.get('year')
        description = project_data.get('description')
        source = project_data.get('source')
        metadata = json.dumps(project_data.get('metadata', {}))

        # Check if project already exists
        cursor.execute("SELECT id FROM projects WHERE name = ?", (name,))
        result = cursor.fetchone()

        if result:
            # Update existing project
            project_id = result[0]
            cursor.execute("""
            UPDATE projects
            SET prefix = ?, year = ?, description = ?, source = ?,
                date_updated = CURRENT_TIMESTAMP, metadata = ?
            WHERE id = ?
            """, (prefix, year, description, source, metadata, project_id))
            logger.info(f"Updated project {name} (ID: {project_id})")
        else:
            # Insert new project
            cursor.execute("""
            INSERT INTO projects (name, prefix, year, description, source, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (name, prefix, year, description, source, metadata))
            project_id = cursor.lastrowid
            logger.info(f"Added project {name} (ID: {project_id})")

        # Commit changes
        conn.commit()

        return project_id

    except Exception as e:
        logger.error(f"Error adding project {project_data.get('name')}: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def add_file(file_data: Dict[str, Any], project_id: int, db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Add a file to the database.

    Args:
        file_data: File data
        project_id: Project ID
        db_path: Path to the database file

    Returns:
        int: File ID
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Extract file data
        bucket = file_data.get('bucket')
        key = file_data.get('key')
        filename = key.split('/')[-1] if key else ''
        size = file_data.get('size')
        last_modified = file_data.get('last_modified')
        format = filename.split('.')[-1].lower() if filename else ''

        # Extract bounding box
        bbox = file_data.get('boundingBox', {})
        min_x = bbox.get('minX')
        min_y = bbox.get('minY')
        max_x = bbox.get('maxX')
        max_y = bbox.get('maxY')

        # Extract polygon
        polygon = json.dumps(file_data.get('polygon_points', []))

        # Extract metadata source
        metadata_source = file_data.get('metadata_source')

        # Extract metadata URLs
        ept_json_url = file_data.get('eptJsonUrl')
        ept_sources_url = file_data.get('eptSourcesUrl')
        ept_metadata_url = file_data.get('eptMetadataUrl')

        # Extract point cloud information
        point_count = file_data.get('pointCount')
        resolution = file_data.get('resolution')
        point_spacing = file_data.get('pointSpacing')
        coordinate_system = file_data.get('coordinateSystem')

        # Extract metadata
        metadata = json.dumps(file_data.get('metadata', {}))

        # Check if file already exists
        cursor.execute("SELECT id FROM files WHERE key = ?", (key,))
        result = cursor.fetchone()

        if result:
            # Update existing file
            file_id = result[0]
            cursor.execute("""
            UPDATE files
            SET project_id = ?, bucket = ?, filename = ?, size = ?, last_modified = ?,
                format = ?, min_x = ?, min_y = ?, max_x = ?, max_y = ?, polygon = ?,
                metadata_source = ?, date_updated = CURRENT_TIMESTAMP, metadata = ?,
                ept_json_url = ?, ept_sources_url = ?, ept_metadata_url = ?,
                point_count = ?, resolution = ?, point_spacing = ?, coordinate_system = ?
            WHERE id = ?
            """, (project_id, bucket, filename, size, last_modified, format,
                 min_x, min_y, max_x, max_y, polygon, metadata_source, metadata,
                 ept_json_url, ept_sources_url, ept_metadata_url,
                 point_count, resolution, point_spacing, coordinate_system, file_id))
            logger.debug(f"Updated file {key} (ID: {file_id})")
        else:
            # Insert new file
            cursor.execute("""
            INSERT INTO files (project_id, bucket, key, filename, size, last_modified,
                              format, min_x, min_y, max_x, max_y, polygon,
                              metadata_source, metadata, ept_json_url, ept_sources_url, ept_metadata_url,
                              point_count, resolution, point_spacing, coordinate_system)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, bucket, key, filename, size, last_modified, format,
                 min_x, min_y, max_x, max_y, polygon, metadata_source, metadata,
                 ept_json_url, ept_sources_url, ept_metadata_url,
                 point_count, resolution, point_spacing, coordinate_system))
            file_id = cursor.lastrowid
            logger.debug(f"Added file {key} (ID: {file_id})")

        # Commit changes
        conn.commit()

        return file_id

    except Exception as e:
        logger.error(f"Error adding file {file_data.get('key')}: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def start_crawl(db_path: str = DEFAULT_DB_PATH) -> int:
    """
    Start a new crawl and record it in the history.

    Args:
        db_path: Path to the database file

    Returns:
        int: Crawl ID
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Insert new crawl record
        cursor.execute("""
        INSERT INTO crawl_history (start_time, status)
        VALUES (CURRENT_TIMESTAMP, 'in_progress')
        """)

        crawl_id = cursor.lastrowid

        # Commit changes
        conn.commit()

        logger.info(f"Started new crawl (ID: {crawl_id})")

        return crawl_id

    except Exception as e:
        logger.error(f"Error starting crawl: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def update_crawl(crawl_id: int, status: str, stats: Dict[str, int] = None,
                error: str = None, db_path: str = DEFAULT_DB_PATH) -> None:
    """
    Update a crawl record.

    Args:
        crawl_id: Crawl ID
        status: Crawl status
        stats: Crawl statistics
        error: Error message
        db_path: Path to the database file
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Extract stats
        if stats is None:
            stats = {}

        projects_added = stats.get('projects_added', 0)
        projects_updated = stats.get('projects_updated', 0)
        files_added = stats.get('files_added', 0)
        files_updated = stats.get('files_updated', 0)

        # Update crawl record
        cursor.execute("""
        UPDATE crawl_history
        SET end_time = CURRENT_TIMESTAMP, status = ?,
            projects_added = ?, projects_updated = ?,
            files_added = ?, files_updated = ?,
            error = ?
        WHERE id = ?
        """, (status, projects_added, projects_updated, files_added,
              files_updated, error, crawl_id))

        # Commit changes
        conn.commit()

        logger.info(f"Updated crawl (ID: {crawl_id}) with status: {status}")

    except Exception as e:
        logger.error(f"Error updating crawl {crawl_id}: {str(e)}", exc_info=True)
        if conn:
            conn.rollback()
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def search_files_by_bbox(min_x: float, min_y: float, max_x: float, max_y: float,
                        format: str = None, db_path: str = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    """
    Search for files that intersect with a bounding box.

    Args:
        min_x: Minimum X coordinate
        min_y: Minimum Y coordinate
        max_x: Maximum X coordinate
        max_y: Maximum Y coordinate
        format: File format filter
        db_path: Path to the database file

    Returns:
        List[Dict[str, Any]]: List of matching files
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        # Log the search parameters
        logger.info(f"Searching for files in bbox: {min_x}, {min_y}, {max_x}, {max_y}")

        # Build query - use intersection logic
        # Two boxes intersect if one's min is <= the other's max and one's max is >= the other's min
        query = """
        SELECT f.*, p.name as project_name, p.year as project_year
        FROM files f
        JOIN projects p ON f.project_id = p.id
        WHERE
            f.min_x <= ? AND f.max_x >= ? AND
            f.min_y <= ? AND f.max_y >= ?
        """
        params = [max_x, min_x, max_y, min_y]

        # Log the query parameters
        logger.info(f"Query parameters: max_x={max_x}, min_x={min_x}, max_y={max_y}, min_y={min_y}")

        # Explain the intersection logic
        logger.info("Using intersection logic: file intersects with search area if:")
        logger.info(f"  file.min_x <= search.max_x ({max_x}) AND file.max_x >= search.min_x ({min_x}) AND")
        logger.info(f"  file.min_y <= search.max_y ({max_y}) AND file.max_y >= search.min_y ({min_y})")

        # Add format filter if specified
        if format and format.strip():
            # Make format filter case-insensitive
            query += " AND LOWER(f.format) = LOWER(?)"
            params.append(format)
            logger.info(f"Added case-insensitive format filter: {format}")

        # Execute query
        try:
            cursor.execute(query, params)

            # Log the SQL query
            logger.info(f"SQL query: {query}")
            logger.info(f"SQL params: {params}")

            # Fetch results
            results = []
            for row in cursor.fetchall():
                # Convert row to dictionary
                file_data = dict(row)

                # Parse JSON fields
                if file_data.get('polygon'):
                    file_data['polygon_points'] = json.loads(file_data['polygon'])

                if file_data.get('metadata'):
                    file_data['metadata'] = json.loads(file_data['metadata'])

                # Add bounding box
                file_data['boundingBox'] = {
                    'minX': file_data['min_x'],
                    'minY': file_data['min_y'],
                    'maxX': file_data['max_x'],
                    'maxY': file_data['max_y']
                }

                results.append(file_data)
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise

        logger.info(f"Found {len(results)} files intersecting with bbox: {min_x}, {min_y}, {max_x}, {max_y}")

        return results

    except Exception as e:
        logger.error(f"Error searching files by bbox: {str(e)}", exc_info=True)
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def get_database_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Get statistics about the database.

    Args:
        db_path: Path to the database file

    Returns:
        Dict[str, Any]: Database statistics
    """
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get project count
        cursor.execute("SELECT COUNT(*) FROM projects")
        project_count = cursor.fetchone()[0]

        # Get file count
        cursor.execute("SELECT COUNT(*) FROM files")
        file_count = cursor.fetchone()[0]

        # Get file count by format
        cursor.execute("""
        SELECT format, COUNT(*) as count
        FROM files
        GROUP BY format
        ORDER BY count DESC
        """)
        format_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get latest crawl
        cursor.execute("""
        SELECT id, start_time, end_time, status,
               projects_added, projects_updated,
               files_added, files_updated
        FROM crawl_history
        ORDER BY start_time DESC
        LIMIT 1
        """)
        latest_crawl = cursor.fetchone()

        if latest_crawl:
            latest_crawl = {
                'id': latest_crawl[0],
                'start_time': latest_crawl[1],
                'end_time': latest_crawl[2],
                'status': latest_crawl[3],
                'projects_added': latest_crawl[4],
                'projects_updated': latest_crawl[5],
                'files_added': latest_crawl[6],
                'files_updated': latest_crawl[7]
            }

        # Get database size
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        return {
            'project_count': project_count,
            'file_count': file_count,
            'format_counts': format_counts,
            'latest_crawl': latest_crawl,
            'db_size': db_size,
            'db_path': db_path
        }

    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}", exc_info=True)
        raise

    finally:
        # Close connection
        if conn:
            conn.close()

def database_exists(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Check if the database exists.

    Args:
        db_path: Path to the database file

    Returns:
        bool: True if the database exists, False otherwise
    """
    return os.path.exists(db_path)

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Initialize database
    init_database()

    # Print database stats
    stats = get_database_stats()
    print(f"Database path: {stats['db_path']}")
    print(f"Database size: {stats['db_size'] / (1024 * 1024):.2f} MB")
    print(f"Projects: {stats['project_count']}")
    print(f"Files: {stats['file_count']}")
    print("File formats:")
    for format, count in stats.get('format_counts', {}).items():
        print(f"  {format}: {count}")

    if stats.get('latest_crawl'):
        latest_crawl = stats['latest_crawl']
        print("Latest crawl:")
        print(f"  ID: {latest_crawl['id']}")
        print(f"  Status: {latest_crawl['status']}")
        print(f"  Start time: {latest_crawl['start_time']}")
        print(f"  End time: {latest_crawl['end_time']}")
        print(f"  Projects added: {latest_crawl['projects_added']}")
        print(f"  Projects updated: {latest_crawl['projects_updated']}")
        print(f"  Files added: {latest_crawl['files_added']}")
        print(f"  Files updated: {latest_crawl['files_updated']}")

def get_indexed_projects(db_path: str = DEFAULT_DB_PATH) -> Set[str]:
    """
    Get the names of all projects that have already been indexed.

    Args:
        db_path: Path to the database file

    Returns:
        Set[str]: Set of project names
    """
    try:
        logger.info(f"Getting indexed projects from {db_path}")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get all project names
        cursor.execute("SELECT name FROM projects")
        results = cursor.fetchall()

        # Close connection
        conn.close()

        # Return set of project names
        return {result[0] for result in results}

    except Exception as e:
        logger.error(f"Error getting indexed projects: {str(e)}", exc_info=True)
        return set()

def optimize_database(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Optimize the database for production use.

    Args:
        db_path: Path to the database file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Optimizing database at {db_path}")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Run VACUUM to rebuild the database file
        logger.info("Running VACUUM to rebuild the database file")
        cursor.execute("VACUUM")

        # Run ANALYZE to update statistics
        logger.info("Running ANALYZE to update statistics")
        cursor.execute("ANALYZE")

        # Create indexes for common queries
        logger.info("Creating indexes for common queries")

        # Index for spatial queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_spatial ON files
        (min_x, min_y, max_x, max_y)
        """)

        # Index for project queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_project_id ON files
        (project_id)
        """)

        # Index for format queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_format ON files
        (format)
        """)

        # Index for date queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_files_date ON files
        (date_added)
        """)

        # Index for project name queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_name ON projects
        (name)
        """)

        # Index for project year queries
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_projects_year ON projects
        (year)
        """)

        # Commit changes
        conn.commit()

        # Close connection
        conn.close()

        logger.info("Database optimization completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error optimizing database: {str(e)}", exc_info=True)
        return False
