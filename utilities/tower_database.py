"""
Tower Database Module

This module provides functions to create, maintain, and query a database of FCC registered towers.
"""

import os
import sqlite3
import logging
import json
from typing import List, Dict, Any, Optional, Tuple
import math
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Database file path
DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                              'data', 'tower_index.db')

# Path to tower data files
TOWER_DATA_DIR = os.path.join('/Users/master15/Desktop/Software/LOStool/Towers/data')

def init_database(db_path: str = DEFAULT_DB_PATH, force: bool = False) -> bool:
    """
    Initialize the tower database.

    Args:
        db_path: Path to the database file
        force: Force reinitialization if database already exists

    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        # Check if database already exists
        if os.path.exists(db_path) and not force:
            logger.info(f"Tower database already exists at {db_path}")
            return True

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        logger.info(f"Initializing tower database at {db_path}")

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create registration table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS registration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_number TEXT,
            registration_number TEXT,
            unique_system_id INTEGER UNIQUE,
            application_purpose TEXT,
            status_code TEXT,
            date_entered TEXT,
            date_received TEXT,
            date_issued TEXT,
            date_constructed TEXT,
            date_dismantled TEXT,
            date_action TEXT,
            structure_street TEXT,
            structure_city TEXT,
            structure_state TEXT,
            county_code TEXT,
            zip_code TEXT,
            height_structure REAL,
            ground_elevation REAL,
            overall_height_ground REAL,
            overall_height_amsl REAL,
            structure_type TEXT,
            date_faa_determination TEXT,
            faa_study_number TEXT,
            faa_circular_number TEXT,
            specification_option INTEGER,
            painting_and_lighting TEXT
        )
        """)

        # Create coordinates table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS coordinates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_system_id INTEGER UNIQUE,
            coordinate_type TEXT,
            latitude_degrees INTEGER,
            latitude_minutes INTEGER,
            latitude_seconds REAL,
            latitude_direction TEXT,
            latitude_total_seconds REAL,
            longitude_degrees INTEGER,
            longitude_minutes INTEGER,
            longitude_seconds REAL,
            longitude_direction TEXT,
            longitude_total_seconds REAL,
            decimal_latitude REAL,
            decimal_longitude REAL,
            FOREIGN KEY (unique_system_id) REFERENCES registration(unique_system_id) ON DELETE CASCADE
        )
        """)

        # Create entity table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS entity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_system_id INTEGER,
            contact_type TEXT,
            entity_type TEXT,
            entity_name TEXT,
            first_name TEXT,
            middle_initial TEXT,
            last_name TEXT,
            phone TEXT,
            street_address TEXT,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            FOREIGN KEY (unique_system_id) REFERENCES registration(unique_system_id) ON DELETE CASCADE
        )
        """)

        # Create spatial index on coordinates
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_coordinates_location ON coordinates (decimal_latitude, decimal_longitude)
        """)

        # Create index on unique_system_id
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_registration_unique_system_id ON registration (unique_system_id)
        """)

        # Create index on structure_type
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_registration_structure_type ON registration (structure_type)
        """)

        # Create index on height
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_registration_height ON registration (overall_height_ground)
        """)

        # Commit changes
        conn.commit()

        logger.info("Tower database initialized successfully")
        return True

    except Exception as e:
        logger.error(f"Error initializing tower database: {str(e)}", exc_info=True)
        return False

    finally:
        # Close connection
        if conn:
            conn.close()

def import_tower_data(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Import tower data from .dat files into the database.

    Args:
        db_path: Path to the database file

    Returns:
        bool: True if successful, False otherwise
    """
    conn = None
    try:
        # Check if database exists
        if not os.path.exists(db_path):
            logger.error(f"Tower database does not exist at {db_path}")
            return False

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Import registration data
        ra_file = os.path.join(TOWER_DATA_DIR, 'RA.dat')
        if os.path.exists(ra_file):
            logger.info(f"Importing registration data from {ra_file}")

            # Count lines in file
            with open(ra_file, 'r', encoding='latin-1') as f:
                total_lines = sum(1 for _ in f)

            # Read and process file
            with open(ra_file, 'r', encoding='latin-1') as f:
                count = 0
                batch = []
                batch_size = 1000

                for line in f:
                    count += 1
                    if count % 10000 == 0:
                        logger.info(f"Processing registration record {count}/{total_lines}")

                    # Parse line
                    fields = line.strip().split('|')
                    if len(fields) < 30:
                        logger.warning(f"Skipping invalid registration record: {line[:100]}")
                        continue

                    # Extract fields
                    try:
                        record_type = fields[0]
                        if record_type != 'RA':
                            logger.warning(f"Skipping non-RA record: {line[:100]}")
                            continue

                        file_number = fields[2]
                        registration_number = fields[3]
                        unique_system_id = int(fields[4]) if fields[4] else None
                        application_purpose = fields[5]
                        status_code = fields[8]
                        date_entered = fields[9]
                        date_received = fields[10]
                        date_issued = fields[11]
                        date_constructed = fields[12]
                        date_dismantled = fields[13]
                        date_action = fields[14]
                        structure_street = fields[23]
                        structure_city = fields[24]
                        structure_state = fields[25]
                        county_code = fields[26]
                        zip_code = fields[27]
                        height_structure = float(fields[28]) if fields[28] else None
                        ground_elevation = float(fields[29]) if fields[29] else None
                        overall_height_ground = float(fields[30]) if fields[30] else None
                        overall_height_amsl = float(fields[31]) if fields[31] else None
                        structure_type = fields[32]
                        date_faa_determination = fields[33]
                        faa_study_number = fields[34]
                        faa_circular_number = fields[35]
                        specification_option = int(fields[36]) if fields[36] else None
                        painting_and_lighting = fields[37]

                        # Add to batch
                        batch.append((
                            file_number, registration_number, unique_system_id, application_purpose,
                            status_code, date_entered, date_received, date_issued, date_constructed,
                            date_dismantled, date_action, structure_street, structure_city,
                            structure_state, county_code, zip_code, height_structure, ground_elevation,
                            overall_height_ground, overall_height_amsl, structure_type,
                            date_faa_determination, faa_study_number, faa_circular_number,
                            specification_option, painting_and_lighting
                        ))

                        # Insert batch if batch size reached
                        if len(batch) >= batch_size:
                            cursor.executemany("""
                            INSERT OR REPLACE INTO registration (
                                file_number, registration_number, unique_system_id, application_purpose,
                                status_code, date_entered, date_received, date_issued, date_constructed,
                                date_dismantled, date_action, structure_street, structure_city,
                                structure_state, county_code, zip_code, height_structure, ground_elevation,
                                overall_height_ground, overall_height_amsl, structure_type,
                                date_faa_determination, faa_study_number, faa_circular_number,
                                specification_option, painting_and_lighting
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, batch)
                            conn.commit()
                            batch = []

                    except Exception as e:
                        logger.warning(f"Error processing registration record: {e}")
                        continue

                # Insert remaining batch
                if batch:
                    cursor.executemany("""
                    INSERT OR REPLACE INTO registration (
                        file_number, registration_number, unique_system_id, application_purpose,
                        status_code, date_entered, date_received, date_issued, date_constructed,
                        date_dismantled, date_action, structure_street, structure_city,
                        structure_state, county_code, zip_code, height_structure, ground_elevation,
                        overall_height_ground, overall_height_amsl, structure_type,
                        date_faa_determination, faa_study_number, faa_circular_number,
                        specification_option, painting_and_lighting
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    conn.commit()

            logger.info(f"Imported {count} registration records")
        else:
            logger.warning(f"Registration data file not found: {ra_file}")

        # Import coordinates data
        co_file = os.path.join(TOWER_DATA_DIR, 'CO.dat')
        if os.path.exists(co_file):
            logger.info(f"Importing coordinates data from {co_file}")

            # Count lines in file
            with open(co_file, 'r', encoding='latin-1') as f:
                total_lines = sum(1 for _ in f)

            # Read and process file
            with open(co_file, 'r', encoding='latin-1') as f:
                count = 0
                batch = []
                batch_size = 1000

                for line in f:
                    count += 1
                    if count % 10000 == 0:
                        logger.info(f"Processing coordinates record {count}/{total_lines}")

                    # Parse line
                    fields = line.strip().split('|')
                    if len(fields) < 17:
                        logger.warning(f"Skipping invalid coordinates record: {line[:100]}")
                        continue

                    # Extract fields
                    try:
                        record_type = fields[0]
                        if record_type != 'CO':
                            logger.warning(f"Skipping non-CO record: {line[:100]}")
                            continue

                        unique_system_id = int(fields[4]) if fields[4] else None
                        coordinate_type = fields[5]
                        latitude_degrees = int(fields[6]) if fields[6] else None
                        latitude_minutes = int(fields[7]) if fields[7] else None
                        latitude_seconds = float(fields[8]) if fields[8] else None
                        latitude_direction = fields[9]
                        latitude_total_seconds = float(fields[10]) if fields[10] else None
                        longitude_degrees = int(fields[11]) if fields[11] else None
                        longitude_minutes = int(fields[12]) if fields[12] else None
                        longitude_seconds = float(fields[13]) if fields[13] else None
                        longitude_direction = fields[14]
                        longitude_total_seconds = float(fields[15]) if fields[15] else None

                        # Calculate decimal coordinates
                        decimal_latitude = None
                        decimal_longitude = None

                        if latitude_degrees is not None and latitude_minutes is not None and latitude_seconds is not None:
                            decimal_latitude = latitude_degrees + (latitude_minutes / 60.0) + (latitude_seconds / 3600.0)
                            if latitude_direction == 'S':
                                decimal_latitude = -decimal_latitude

                        if longitude_degrees is not None and longitude_minutes is not None and longitude_seconds is not None:
                            decimal_longitude = longitude_degrees + (longitude_minutes / 60.0) + (longitude_seconds / 3600.0)
                            if longitude_direction == 'W':
                                decimal_longitude = -decimal_longitude

                        # Add to batch
                        batch.append((
                            unique_system_id, coordinate_type, latitude_degrees, latitude_minutes,
                            latitude_seconds, latitude_direction, latitude_total_seconds,
                            longitude_degrees, longitude_minutes, longitude_seconds, longitude_direction,
                            longitude_total_seconds, decimal_latitude, decimal_longitude
                        ))

                        # Insert batch if batch size reached
                        if len(batch) >= batch_size:
                            cursor.executemany("""
                            INSERT OR REPLACE INTO coordinates (
                                unique_system_id, coordinate_type, latitude_degrees, latitude_minutes,
                                latitude_seconds, latitude_direction, latitude_total_seconds,
                                longitude_degrees, longitude_minutes, longitude_seconds, longitude_direction,
                                longitude_total_seconds, decimal_latitude, decimal_longitude
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, batch)
                            conn.commit()
                            batch = []

                    except Exception as e:
                        logger.warning(f"Error processing coordinates record: {e}")
                        continue

                # Insert remaining batch
                if batch:
                    cursor.executemany("""
                    INSERT OR REPLACE INTO coordinates (
                        unique_system_id, coordinate_type, latitude_degrees, latitude_minutes,
                        latitude_seconds, latitude_direction, latitude_total_seconds,
                        longitude_degrees, longitude_minutes, longitude_seconds, longitude_direction,
                        longitude_total_seconds, decimal_latitude, decimal_longitude
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    conn.commit()

            logger.info(f"Imported {count} coordinates records")
        else:
            logger.warning(f"Coordinates data file not found: {co_file}")

        # Import entity data
        en_file = os.path.join(TOWER_DATA_DIR, 'EN.dat')
        if os.path.exists(en_file):
            logger.info(f"Importing entity data from {en_file}")

            # Count lines in file
            with open(en_file, 'r', encoding='latin-1') as f:
                total_lines = sum(1 for _ in f)

            # Read and process file
            with open(en_file, 'r', encoding='latin-1') as f:
                count = 0
                batch = []
                batch_size = 1000

                for line in f:
                    count += 1
                    if count % 10000 == 0:
                        logger.info(f"Processing entity record {count}/{total_lines}")

                    # Parse line
                    fields = line.strip().split('|')
                    if len(fields) < 20:
                        logger.warning(f"Skipping invalid entity record: {line[:100]}")
                        continue

                    # Extract fields
                    try:
                        record_type = fields[0]
                        if record_type != 'EN':
                            logger.warning(f"Skipping non-EN record: {line[:100]}")
                            continue

                        unique_system_id = int(fields[4]) if fields[4] else None
                        contact_type = fields[5]
                        entity_type = fields[6]
                        entity_name = fields[9]
                        first_name = fields[10]
                        middle_initial = fields[11]
                        last_name = fields[12]
                        phone = fields[14]
                        street_address = fields[17]
                        city = fields[20]
                        state = fields[21]
                        zip_code = fields[22]

                        # Add to batch
                        batch.append((
                            unique_system_id, contact_type, entity_type, entity_name,
                            first_name, middle_initial, last_name, phone,
                            street_address, city, state, zip_code
                        ))

                        # Insert batch if batch size reached
                        if len(batch) >= batch_size:
                            cursor.executemany("""
                            INSERT OR REPLACE INTO entity (
                                unique_system_id, contact_type, entity_type, entity_name,
                                first_name, middle_initial, last_name, phone,
                                street_address, city, state, zip_code
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, batch)
                            conn.commit()
                            batch = []

                    except Exception as e:
                        logger.warning(f"Error processing entity record: {e}")
                        continue

                # Insert remaining batch
                if batch:
                    cursor.executemany("""
                    INSERT OR REPLACE INTO entity (
                        unique_system_id, contact_type, entity_type, entity_name,
                        first_name, middle_initial, last_name, phone,
                        street_address, city, state, zip_code
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, batch)
                    conn.commit()

            logger.info(f"Imported {count} entity records")
        else:
            logger.warning(f"Entity data file not found: {en_file}")

        # Optimize database
        logger.info("Optimizing database")
        cursor.execute("VACUUM")
        cursor.execute("ANALYZE")

        logger.info("Tower data import completed successfully")
        return True

    except Exception as e:
        logger.error(f"Error importing tower data: {str(e)}", exc_info=True)
        return False

    finally:
        # Close connection
        if conn:
            conn.close()

def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    Check if a point is inside a polygon using the ray casting algorithm.

    Args:
        point: (longitude, latitude) tuple
        polygon: List of (longitude, latitude) tuples forming the polygon

    Returns:
        bool: True if the point is inside the polygon, False otherwise
    """
    x, y = point
    n = len(polygon)
    inside = False

    p1x, p1y = polygon[0]
    for i in range(1, n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y

    return inside

def get_bounding_box(polygon: List[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """
    Get the bounding box of a polygon.

    Args:
        polygon: List of (longitude, latitude) tuples forming the polygon

    Returns:
        Tuple[float, float, float, float]: (min_lon, min_lat, max_lon, max_lat)
    """
    lons = [p[0] for p in polygon]
    lats = [p[1] for p in polygon]
    return min(lons), min(lats), max(lons), max(lats)

def search_towers_in_polygon(polygon: List[Tuple[float, float]], db_path: str = DEFAULT_DB_PATH,
                           min_height: float = None, max_height: float = None,
                           structure_types: List[str] = None) -> List[Dict[str, Any]]:
    """
    Search for towers within a polygon.

    Args:
        polygon: List of (longitude, latitude) tuples forming the polygon
        db_path: Path to the database file
        min_height: Minimum tower height in feet
        max_height: Maximum tower height in feet
        structure_types: List of structure types to include

    Returns:
        List[Dict[str, Any]]: List of tower dictionaries
    """
    try:
        # Check if database exists
        if not os.path.exists(db_path):
            logger.error(f"Tower database does not exist at {db_path}")
            return []

        # Get bounding box of polygon
        min_lon, min_lat, max_lon, max_lat = get_bounding_box(polygon)

        # Add a small buffer to the bounding box
        buffer = 0.01  # About 1 km
        min_lon -= buffer
        min_lat -= buffer
        max_lon += buffer
        max_lat += buffer

        # Connect to the database
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        cursor = conn.cursor()

        # Build query
        query = """
        SELECT r.*, c.*, e.entity_name, e.first_name, e.middle_initial, e.last_name
        FROM registration r
        JOIN coordinates c ON r.unique_system_id = c.unique_system_id
        LEFT JOIN entity e ON r.unique_system_id = e.unique_system_id AND e.contact_type = 'O'
        WHERE c.decimal_latitude >= ? AND c.decimal_latitude <= ?
        AND c.decimal_longitude >= ? AND c.decimal_longitude <= ?
        """
        params = [min_lat, max_lat, min_lon, max_lon]

        # Add height filter if specified
        if min_height is not None:
            query += " AND r.overall_height_ground >= ?"
            params.append(min_height)
        if max_height is not None:
            query += " AND r.overall_height_ground <= ?"
            params.append(max_height)

        # Add structure type filter if specified
        if structure_types:
            placeholders = ', '.join(['?'] * len(structure_types))
            query += f" AND r.structure_type IN ({placeholders})"
            params.extend(structure_types)

        # Execute query
        cursor.execute(query, params)

        # Fetch results
        results = []
        for row in cursor.fetchall():
            # Convert row to dictionary
            tower_data = dict(row)

            # Check if tower is inside polygon
            point = (tower_data['decimal_longitude'], tower_data['decimal_latitude'])
            if point_in_polygon(point, polygon):
                results.append(tower_data)

        logger.info(f"Found {len(results)} towers within polygon")
        return results

    except Exception as e:
        logger.error(f"Error searching for towers: {str(e)}", exc_info=True)
        return []

    finally:
        # Close connection
        if conn:
            conn.close()

def get_database_stats(db_path: str = DEFAULT_DB_PATH) -> Dict[str, Any]:
    """
    Get statistics about the tower database.

    Args:
        db_path: Path to the database file

    Returns:
        Dict[str, Any]: Database statistics
    """
    conn = None
    try:
        # Check if database exists
        if not os.path.exists(db_path):
            logger.error(f"Tower database does not exist at {db_path}")
            return {}

        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get registration count
        cursor.execute("SELECT COUNT(*) FROM registration")
        registration_count = cursor.fetchone()[0]

        # Get coordinates count
        cursor.execute("SELECT COUNT(*) FROM coordinates")
        coordinates_count = cursor.fetchone()[0]

        # Get entity count
        cursor.execute("SELECT COUNT(*) FROM entity")
        entity_count = cursor.fetchone()[0]

        # Get structure type counts
        cursor.execute("""
        SELECT structure_type, COUNT(*) as count
        FROM registration
        GROUP BY structure_type
        ORDER BY count DESC
        """)
        structure_type_counts = {row[0]: row[1] for row in cursor.fetchall()}

        # Get height statistics
        cursor.execute("""
        SELECT MIN(overall_height_ground), MAX(overall_height_ground), AVG(overall_height_ground)
        FROM registration
        WHERE overall_height_ground IS NOT NULL
        """)
        height_stats = cursor.fetchone()
        min_height, max_height, avg_height = height_stats if height_stats else (None, None, None)

        # Get database size
        db_size = os.path.getsize(db_path) if os.path.exists(db_path) else 0

        return {
            'registration_count': registration_count,
            'coordinates_count': coordinates_count,
            'entity_count': entity_count,
            'structure_type_counts': structure_type_counts,
            'min_height': min_height,
            'max_height': max_height,
            'avg_height': avg_height,
            'db_size': db_size,
            'db_path': db_path
        }

    except Exception as e:
        logger.error(f"Error getting database stats: {str(e)}", exc_info=True)
        return {}

    finally:
        # Close connection
        if conn:
            conn.close()

def ensure_tower_database_exists(db_path: str = DEFAULT_DB_PATH) -> bool:
    """
    Ensure that the tower database exists and is populated.

    Args:
        db_path: Path to the database file

    Returns:
        bool: True if database exists and is populated, False otherwise
    """
    conn = None
    try:
        # Check if database exists
        if not os.path.exists(db_path):
            logger.info(f"Tower database does not exist at {db_path}, initializing")
            if not init_database(db_path):
                logger.error("Failed to initialize tower database")
                return False

            logger.info("Importing tower data")
            if not import_tower_data(db_path):
                logger.error("Failed to import tower data")
                return False

            return True

        # Check if database is populated
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM registration")
        registration_count = cursor.fetchone()[0]

        conn.close()
        conn = None

        if registration_count == 0:
            logger.info("Tower database exists but is empty, importing data")
            if not import_tower_data(db_path):
                logger.error("Failed to import tower data")
                return False

        return True

    except Exception as e:
        logger.error(f"Error ensuring tower database exists: {str(e)}", exc_info=True)
        return False

    finally:
        # Close connection
        if conn:
            conn.close()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO,
                       format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Initialize database
    init_database()

    # Import tower data
    import_tower_data()

    # Get database stats
    stats = get_database_stats()
    print(f"Tower database statistics:")
    print(f"  Registration records: {stats.get('registration_count', 0)}")
    print(f"  Coordinates records: {stats.get('coordinates_count', 0)}")
    print(f"  Entity records: {stats.get('entity_count', 0)}")
    print(f"  Database size: {stats.get('db_size', 0) / (1024 * 1024):.2f} MB")
