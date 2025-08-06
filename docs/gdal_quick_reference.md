# GDAL Quick Reference Guide

## Command Line Tools

### Information Commands

```bash
# Get GDAL version
gdal-config --version

# List all GDAL raster formats
gdalinfo --formats

# List all OGR vector formats
ogrinfo --formats

# Get detailed info about a raster file
gdalinfo file.tif

# Get detailed info about a vector file
ogrinfo -al file.shp
```

### Conversion Commands

```bash
# Convert between raster formats
gdal_translate input.tif output.png

# Convert between vector formats
ogr2ogr -f "GeoJSON" output.geojson input.shp

# Reproject raster data
gdalwarp -t_srs EPSG:4326 input.tif output.tif

# Reproject vector data
ogr2ogr -t_srs EPSG:4326 output.shp input.shp
```

### LiDAR Commands

```bash
# Get LAS/LAZ file info
lasinfo file.laz

# Convert LAS to LAZ
las2las -i file.las -o file.laz

# Convert LAS to other formats
las2ogr -i file.las -o points.shp
```

## Python GDAL Examples

### Basic Import and Version Check

```python
from osgeo import gdal, ogr, osr

# Print GDAL version
print(f"GDAL version: {gdal.VersionInfo()}")
```

### Reading Raster Data

```python
# Open a raster file
dataset = gdal.Open("example.tif")

# Get raster dimensions
width = dataset.RasterXSize
height = dataset.RasterYSize
bands = dataset.RasterCount

# Get geotransform and projection
geotransform = dataset.GetGeoTransform()
projection = dataset.GetProjection()

# Read raster data
band = dataset.GetRasterBand(1)
data = band.ReadAsArray()
```

### Reading Vector Data

```python
# Open a vector file
driver = ogr.GetDriverByName("ESRI Shapefile")
dataset = driver.Open("example.shp", 0)  # 0 means read-only
layer = dataset.GetLayer()

# Get feature count
feature_count = layer.GetFeatureCount()

# Iterate through features
for feature in layer:
    geometry = feature.GetGeometryRef()
    properties = {}
    for i in range(feature.GetFieldCount()):
        field_name = feature.GetFieldDefnRef(i).GetName()
        properties[field_name] = feature.GetField(i)
```

### Coordinate Transformation

```python
# Create source and target spatial reference systems
source = osr.SpatialReference()
source.ImportFromEPSG(4326)  # WGS84

target = osr.SpatialReference()
target.ImportFromEPSG(3857)  # Web Mercator

# Create transformation
transform = osr.CoordinateTransformation(source, target)

# Transform a point
lon, lat = -74.0060, 40.7128  # New York City
x, y, z = transform.TransformPoint(lon, lat)
```

### Creating Vector Data

```python
# Create a new shapefile
driver = ogr.GetDriverByName("ESRI Shapefile")
dataset = driver.CreateDataSource("output.shp")

# Create a spatial reference
srs = osr.SpatialReference()
srs.ImportFromEPSG(4326)

# Create a layer
layer = dataset.CreateLayer("points", srs, ogr.wkbPoint)

# Add fields
field = ogr.FieldDefn("Name", ogr.OFTString)
layer.CreateField(field)

# Create a feature
feature = ogr.Feature(layer.GetLayerDefn())
feature.SetField("Name", "Test Point")

# Create a point geometry
point = ogr.Geometry(ogr.wkbPoint)
point.AddPoint(-74.0060, 40.7128)  # New York City
feature.SetGeometry(point)

# Add the feature to the layer
layer.CreateFeature(feature)

# Clean up
feature = None
dataset = None
```

### Creating Raster Data

```python
# Create a new GeoTIFF
driver = gdal.GetDriverByName("GTiff")
dataset = driver.Create("output.tif", 100, 100, 1, gdal.GDT_Float32)

# Set geotransform and projection
geotransform = (-74.0, 0.01, 0, 40.7, 0, -0.01)  # Example for NYC area
dataset.SetGeoTransform(geotransform)

srs = osr.SpatialReference()
srs.ImportFromEPSG(4326)
dataset.SetProjection(srs.ExportToWkt())

# Write data to the raster band
band = dataset.GetRasterBand(1)
import numpy as np
data = np.zeros((100, 100))
band.WriteArray(data)

# Clean up
dataset = None
```

## Common Issues and Solutions

### Library Not Found

**Issue**: `ImportError: dlopen(...): Library not loaded: /opt/homebrew/opt/gdal/lib/libgdal.XX.dylib`

**Solution**:
```bash
# Run the fix script
./fix_gdal.sh

# Or create symbolic links manually
sudo ln -sf /opt/homebrew/Cellar/gdal/3.10.3/lib/libgdal.36.dylib /opt/homebrew/opt/gdal/lib/libgdal.36.dylib
```

### Version Mismatch

**Issue**: Python GDAL package version doesn't match Homebrew GDAL version

**Solution**:
```bash
# Reinstall Python GDAL package
pip uninstall gdal
pip install gdal==$(gdal-config --version)
```

### Missing Drivers

**Issue**: GDAL is missing drivers or formats you need

**Solution**:
```bash
# Reinstall GDAL with additional options
brew uninstall gdal
brew install gdal --with-complete

# Check available drivers
python -c "from osgeo import gdal; for i in range(gdal.GetDriverCount()): print(gdal.GetDriver(i).GetDescription())"
```

## Testing GDAL Installation

```python
# Save as test_gdal.py
from osgeo import gdal, ogr, osr

# Test GDAL version
print(f"GDAL version: {gdal.VersionInfo()}")

# Test raster drivers
print(f"GDAL raster driver count: {gdal.GetDriverCount()}")

# Test vector drivers
print(f"OGR vector driver count: {ogr.GetDriverCount()}")

# Test coordinate transformation
source = osr.SpatialReference()
source.ImportFromEPSG(4326)
target = osr.SpatialReference()
target.ImportFromEPSG(3857)
transform = osr.CoordinateTransformation(source, target)
x, y, z = transform.TransformPoint(-74.0060, 40.7128)
print(f"Coordinate transformation test: {x:.2f}, {y:.2f}")

print("GDAL is working correctly!")
```

Run with:
```bash
python test_gdal.py
```
