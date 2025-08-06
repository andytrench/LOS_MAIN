# PostgreSQL Setup and Configuration

This document provides detailed instructions for setting up and configuring the PostgreSQL database with PostGIS extension for the LOS Tool application.

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Database Setup](#database-setup)
4. [OSM Data Import](#osm-data-import)
5. [Database Schema](#database-schema)
6. [Performance Tuning](#performance-tuning)
7. [Backup and Restore](#backup-and-restore)
8. [Troubleshooting](#troubleshooting)

## Overview

The LOS Tool application uses PostgreSQL with the PostGIS extension to store and query OpenStreetMap (OSM) data. This provides efficient spatial queries for structures within a polygon, which is essential for analyzing potential obstructions in line-of-sight paths.

Key components:
- PostgreSQL database server
- PostGIS spatial extension
- Custom schema for OSM structures
- Spatial indexes for efficient queries

## Installation

### PostgreSQL Installation

#### macOS

Using Homebrew:
```bash
brew install postgresql
brew services start postgresql
```

#### Windows

1. Download the installer from [PostgreSQL Downloads](https://www.postgresql.org/download/windows/)
2. Run the installer and follow the prompts
3. Select the PostGIS extension during installation
4. Start the PostgreSQL service

#### Linux (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### PostGIS Installation

#### macOS

```bash
brew install postgis
```

#### Windows

PostGIS should be installed during PostgreSQL installation if selected.

#### Linux (Ubuntu/Debian)

```bash
sudo apt install postgis postgresql-<version>-postgis-<version>
```

### psycopg2 Installation

The Python `psycopg2` library is required for connecting to PostgreSQL from the application:

```bash
pip install psycopg2-binary
```

## Database Setup

### Creating the Database

1. Connect to PostgreSQL:
   ```bash
   psql -U postgres
   ```

2. Create the database:
   ```sql
   CREATE DATABASE osm_db;
   ```

3. Connect to the new database:
   ```sql
   \c osm_db
   ```

4. Enable the PostGIS extension:
   ```sql
   CREATE EXTENSION postgis;
   ```

### Creating the Structure Tables

Create the tables for storing structure data:

```sql
-- Power structures table
CREATE TABLE power_structures (
    osm_id BIGINT PRIMARY KEY,
    type TEXT,
    power TEXT,
    height REAL,
    material TEXT,
    operator TEXT,
    name TEXT,
    ref TEXT,
    tags JSONB,
    geom GEOMETRY(Point, 4326)
);

-- Communication structures table
CREATE TABLE communication_structures (
    osm_id BIGINT PRIMARY KEY,
    type TEXT,
    man_made TEXT,
    height REAL,
    material TEXT,
    operator TEXT,
    name TEXT,
    ref TEXT,
    tags JSONB,
    geom GEOMETRY(Point, 4326)
);

-- Other structures table
CREATE TABLE other_structures (
    osm_id BIGINT PRIMARY KEY,
    type TEXT,
    man_made TEXT,
    height REAL,
    material TEXT,
    operator TEXT,
    name TEXT,
    ref TEXT,
    tags JSONB,
    geom GEOMETRY(Point, 4326)
);
```

### Creating Spatial Indexes

Create spatial indexes for efficient queries:

```sql
-- Spatial indexes
CREATE INDEX idx_power_structures_geom ON power_structures USING GIST(geom);
CREATE INDEX idx_communication_structures_geom ON communication_structures USING GIST(geom);
CREATE INDEX idx_other_structures_geom ON other_structures USING GIST(geom);

-- Type indexes
CREATE INDEX power_structures_type_idx ON power_structures(type);
CREATE INDEX communication_structures_type_idx ON communication_structures(type);
CREATE INDEX other_structures_type_idx ON other_structures(type);
```

### Creating the All Structures View

Create a view that combines all structure tables:

```sql
CREATE OR REPLACE VIEW all_structures AS
SELECT osm_id, type, 'power' AS category, power AS subtype, height, material, operator, name, ref, tags, geom
FROM power_structures
UNION ALL
SELECT osm_id, type, 'communication' AS category, man_made AS subtype, height, material, operator, name, ref, tags, geom
FROM communication_structures
UNION ALL
SELECT osm_id, type, 'other' AS category, man_made AS subtype, height, material, operator, name, ref, tags, geom
FROM other_structures;
```

## OSM Data Import

### Downloading OSM Data

1. Download OSM data for your region from [Geofabrik](https://download.geofabrik.de/) or [Planet OSM](https://planet.openstreetmap.org/)
2. The data should be in PBF format (e.g., `north-america-latest.osm.pbf`)

### Filtering and Importing OSM Data

Use the `osm2pgsql` tool to import OSM data into PostgreSQL:

```bash
# Install osm2pgsql
# macOS: brew install osm2pgsql
# Ubuntu/Debian: sudo apt install osm2pgsql
# Windows: Download from https://osm2pgsql.org/

# Create a custom style file for filtering
cat > osm_structures.style << EOF
node,way   power       text         polygon
node,way   man_made    text         polygon
node,way   height      text         linear
node,way   material    text         linear
node,way   operator    text         linear
node,way   name        text         linear
node,way   ref         text         linear
EOF

# Import OSM data
osm2pgsql --create --database osm_db --style osm_structures.style --hstore --output=pgsql north-america-latest.osm.pbf
```

### Processing OSM Data

After importing the raw OSM data, process it to populate the structure tables:

```sql
-- Insert power structures
INSERT INTO power_structures (osm_id, type, power, height, material, operator, name, ref, tags, geom)
SELECT 
    osm_id,
    CASE
        WHEN power = 'tower' THEN 'power_tower'
        WHEN power = 'pole' THEN 'power_pole'
        WHEN power = 'portal' THEN 'power_portal'
        WHEN power = 'terminal' THEN 'power_terminal'
        ELSE 'power_' || power
    END AS type,
    power,
    CASE
        WHEN height ~ '^[0-9]+(\.[0-9]+)?$' THEN height::REAL
        ELSE NULL
    END AS height,
    material,
    operator,
    name,
    ref,
    tags,
    way AS geom
FROM planet_osm_point
WHERE power IN ('tower', 'pole', 'portal', 'terminal', 'substation', 'generator');

-- Insert communication structures
INSERT INTO communication_structures (osm_id, type, man_made, height, material, operator, name, ref, tags, geom)
SELECT 
    osm_id,
    CASE
        WHEN man_made = 'mast' THEN 'mast'
        WHEN man_made = 'tower' AND tags->'tower:type' = 'communication' THEN 'communications_tower'
        WHEN man_made = 'tower' THEN 'tower'
        WHEN man_made = 'antenna' THEN 'antenna'
        ELSE man_made
    END AS type,
    man_made,
    CASE
        WHEN height ~ '^[0-9]+(\.[0-9]+)?$' THEN height::REAL
        ELSE NULL
    END AS height,
    material,
    operator,
    name,
    ref,
    tags,
    way AS geom
FROM planet_osm_point
WHERE man_made IN ('mast', 'tower', 'antenna') 
AND (tags->'tower:type' = 'communication' OR tags->'tower:type' IS NULL);

-- Insert other structures
INSERT INTO other_structures (osm_id, type, man_made, height, material, operator, name, ref, tags, geom)
SELECT 
    osm_id,
    man_made AS type,
    man_made,
    CASE
        WHEN height ~ '^[0-9]+(\.[0-9]+)?$' THEN height::REAL
        ELSE NULL
    END AS height,
    material,
    operator,
    name,
    ref,
    tags,
    way AS geom
FROM planet_osm_point
WHERE man_made IN ('water_tower', 'chimney', 'flagpole', 'crane', 'silo', 'storage_tank')
AND osm_id NOT IN (SELECT osm_id FROM communication_structures);
```

## Database Schema

### Structure Tables

Each structure table has the following schema:

- **osm_id**: Unique identifier from OSM
- **type**: Structure type (e.g., power_tower, mast)
- **power/man_made**: Original OSM tag value
- **height**: Structure height in meters
- **material**: Structure material
- **operator**: Company or organization operating the structure
- **name**: Structure name
- **ref**: Reference code or identifier
- **tags**: JSONB field containing all other OSM tags
- **geom**: PostGIS geometry (Point)

### All Structures View

The `all_structures` view combines all three structure tables with a consistent schema:

- **osm_id**: Unique identifier from OSM
- **type**: Structure type
- **category**: Category (power, communication, other)
- **subtype**: Original OSM tag value
- **height**: Structure height in meters
- **material**: Structure material
- **operator**: Company or organization operating the structure
- **name**: Structure name
- **ref**: Reference code or identifier
- **tags**: JSONB field containing all other OSM tags
- **geom**: PostGIS geometry (Point)

## Performance Tuning

### PostgreSQL Configuration

Edit the `postgresql.conf` file to optimize performance:

```
# Memory settings
shared_buffers = 2GB                  # 25% of RAM for dedicated servers
work_mem = 64MB                       # Increase for complex queries
maintenance_work_mem = 256MB          # Increase for maintenance operations

# Query planner settings
random_page_cost = 1.1                # Lower for SSDs
effective_cache_size = 6GB            # 75% of RAM for dedicated servers

# Write settings
wal_buffers = 16MB                    # Increase for write-heavy workloads
checkpoint_completion_target = 0.9    # Spread checkpoints over time

# Autovacuum settings
autovacuum = on
autovacuum_vacuum_scale_factor = 0.1  # Vacuum when 10% of tuples are dead
```

### PostGIS Tuning

Optimize PostGIS for spatial queries:

```sql
-- Set statistics target for geometry columns
ALTER TABLE power_structures ALTER COLUMN geom SET STATISTICS 1000;
ALTER TABLE communication_structures ALTER COLUMN geom SET STATISTICS 1000;
ALTER TABLE other_structures ALTER COLUMN geom SET STATISTICS 1000;

-- Cluster tables by spatial index
CLUSTER power_structures USING idx_power_structures_geom;
CLUSTER communication_structures USING idx_communication_structures_geom;
CLUSTER other_structures USING idx_other_structures_geom;

-- Analyze tables
ANALYZE power_structures;
ANALYZE communication_structures;
ANALYZE other_structures;
```

### Query Optimization

Optimize the polygon query function:

```sql
-- Use ST_DWithin for faster filtering
SELECT
    osm_id,
    type,
    category,
    subtype,
    height,
    material,
    operator,
    name,
    ref,
    tags,
    ST_AsGeoJSON(geom) as geom
FROM
    all_structures
WHERE
    ST_DWithin(geom, ST_GeomFromText('POLYGON((...))'), 0)
AND type IN ('power_tower', 'mast');
```

## Backup and Restore

### Database Backup

Create a backup of the database:

```bash
# Full database backup
pg_dump -U postgres -F c -b -v -f osm_db_backup.dump osm_db

# Structure tables only
pg_dump -U postgres -F c -b -v -t power_structures -t communication_structures -t other_structures -f structures_backup.dump osm_db
```

### Database Restore

Restore the database from a backup:

```bash
# Create a new database
createdb -U postgres osm_db_new

# Enable PostGIS
psql -U postgres -d osm_db_new -c "CREATE EXTENSION postgis;"

# Restore from backup
pg_restore -U postgres -d osm_db_new -v osm_db_backup.dump
```

## Troubleshooting

### Common Issues

1. **Connection Errors**:
   - Check if PostgreSQL is running: `pg_isready`
   - Verify connection parameters in the application
   - Check PostgreSQL logs: `tail -f /var/log/postgresql/postgresql-<version>-main.log`

2. **Slow Queries**:
   - Use `EXPLAIN ANALYZE` to diagnose query performance
   - Check if indexes are being used
   - Increase `work_mem` for complex spatial queries

3. **Import Errors**:
   - Check disk space
   - Increase `maintenance_work_mem` for imports
   - Use smaller OSM extracts for testing

4. **Memory Issues**:
   - Adjust `shared_buffers` and `effective_cache_size`
   - Monitor memory usage during operations
   - Consider using a server with more RAM for large datasets

### Diagnostic Queries

1. **Check Database Size**:
   ```sql
   SELECT pg_size_pretty(pg_database_size('osm_db'));
   ```

2. **Check Table Sizes**:
   ```sql
   SELECT
       relname AS table_name,
       pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
       pg_size_pretty(pg_relation_size(relid)) AS table_size,
       pg_size_pretty(pg_indexes_size(relid)) AS index_size
   FROM pg_catalog.pg_statio_user_tables
   ORDER BY pg_total_relation_size(relid) DESC;
   ```

3. **Check Index Usage**:
   ```sql
   SELECT
       relname AS table_name,
       indexrelname AS index_name,
       idx_scan AS index_scans,
       idx_tup_read AS tuples_read,
       idx_tup_fetch AS tuples_fetched
   FROM pg_stat_user_indexes
   JOIN pg_statio_user_indexes USING (indexrelid)
   ORDER BY idx_scan DESC;
   ```

4. **Test Spatial Query Performance**:
   ```sql
   EXPLAIN ANALYZE
   SELECT COUNT(*)
   FROM all_structures
   WHERE ST_Within(geom, ST_GeomFromText('POLYGON((-75.3 42.5, -75.1 42.5, -75.1 42.8, -75.3 42.8, -75.3 42.5))', 4326));
   ```
