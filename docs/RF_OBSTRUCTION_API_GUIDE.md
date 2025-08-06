# RF Obstruction Database API - Complete Usage Guide

## 📡 Overview

The RF Obstruction Database API provides comprehensive access to **5.97 million RF-significant structures** derived from OpenStreetMap data. This production-ready API enables RF engineers, telecommunications planners, and wireless system designers to identify potential obstructions for radio frequency communications.

### 🌐 API Information
- **Base URL**: `http://34.212.90.38:8000`
- **Documentation**: `http://34.212.90.38:8000/docs`
- **Interactive Docs**: `http://34.212.90.38:8000/redoc`
- **Version**: 1.0.0
- **Database Size**: 5.97 million structures
- **Geographic Coverage**: Global (OpenStreetMap data)

## 🔐 Authentication

All API endpoints (except root and documentation) require authentication using Bearer tokens.

### Authentication Header
```http
Authorization: Bearer YOUR_API_TOKEN
```

### Demo Token (for testing)
```
demo_token_12345
```

**Note**: Replace with your actual API token in production.

## 📋 Available Endpoints

### 1. System Endpoints

#### `GET /` - API Information
Returns basic API information and status.

**Example Request:**
```bash
curl http://34.212.90.38:8000/
```

**Response:**
```json
{
  "service": "RF Obstruction Database API",
  "version": "1.0.0",
  "status": "operational",
  "endpoints": {
    "docs": "/docs",
    "health": "/health",
    "stats": "/stats",
    "query": "/query/*"
  }
}
```

#### `GET /health` - Health Check
Monitors system health and database status.

**Example Request:**
```bash
curl http://34.212.90.38:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-07-25T18:19:49.486353",
  "database_loaded": true,
  "indexes_available": {
    "main": true,
    "critical": true,
    "tall": true,
    "wind": true
  }
}
```

#### `GET /stats` - Database Statistics
Provides comprehensive database statistics.

**Example Request:**
```bash
curl -H "Authorization: Bearer demo_token_12345" \
     http://34.212.90.38:8000/stats
```

**Response:**
```json
{
  "total_structures": 5967144,
  "by_category": {
    "building": 4500000,
    "power": 800000,
    "communication": 150000,
    "industrial": 300000,
    "other": 217144
  },
  "loading_time_seconds": 45.2,
  "indexes_loaded": {
    "main": true,
    "critical": true,
    "tall": true,
    "wind": true
  }
}
```

### 2. Query Endpoints

#### `POST /query/radius` - Radius-Based Search
Search for structures within a specified radius of a center point.

**Request Body:**
```json
{
  "center_lat": 41.8781,
  "center_lon": -87.6298,
  "radius_km": 8.047
}
```

**Query Parameters:**
- `structure_type` (optional): Filter by type (`all`, `critical`, `tall`, `wind`)
- `min_height` (optional): Minimum height filter (meters)
- `rf_significance` (optional): RF significance (`critical`, `high`, `medium`, `low`)
- `limit` (optional): Maximum results (default: 1000, max: 5000)

**Example Request:**
```bash
curl -X POST http://34.212.90.38:8000/query/radius \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "center_lat": 41.8781,
    "center_lon": -87.6298,
    "radius_km": 8.047
  }'
```

**Response:**
```json
{
  "results": [
    {
      "osm_id": "12345678",
      "category": "power",
      "subtype": "tower",
      "coordinates": [-87.7020227, 41.8310438],
      "height": 30.0,
      "estimated_height": null,
      "elevation": 180.5,
      "rf_significance": "high",
      "material": "steel",
      "name": "ComEd Tower #47",
      "operator": "Commonwealth Edison"
    }
  ],
  "count": 153,
  "query_time_ms": 29601.4,
  "bbox": null
}
```

#### `POST /query/bbox` - Bounding Box Search
Search for structures within a rectangular geographic area.

**Request Body:**
```json
{
  "min_lat": 41.8681,
  "max_lat": 41.8881,
  "min_lon": -87.6398,
  "max_lon": -87.6198
}
```

**Query Parameters:**
- `structure_type` (optional): Filter by type
- `min_height` (optional): Minimum height filter (meters)
- `max_height` (optional): Maximum height filter (meters)
- `rf_significance` (optional): RF significance level
- `limit` (optional): Maximum results (default: 1000, max: 10000)

**Example Request:**
```bash
curl -X POST http://34.212.90.38:8000/query/bbox \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "min_lat": 41.8681,
    "max_lat": 41.8881,
    "min_lon": -87.6398,
    "max_lon": -87.6198
  }'
```

### 3. Analysis Endpoints

#### `POST /analysis/line-of-sight` - RF Link Analysis
Comprehensive line-of-sight analysis for microwave links and RF paths.

**Request Body:**
```json
{
  "start_lat": 41.8781,
  "start_lon": -87.6298,
  "end_lat": 41.9081,
  "end_lon": -87.5998,
  "frequency_ghz": 6.0
}
```

**Example Request:**
```bash
curl -X POST http://34.212.90.38:8000/analysis/line-of-sight \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "start_lat": 41.8781,
    "start_lon": -87.6298,
    "end_lat": 41.9081,
    "end_lon": -87.5998,
    "frequency_ghz": 6.0
  }'
```

**Response:**
```json
{
  "link_parameters": {
    "distance_km": 4.16,
    "frequency_ghz": 6.0,
    "fresnel_radius_m": 14.4,
    "start_coordinates": [-87.6298, 41.8781],
    "end_coordinates": [-87.5998, 41.9081]
  },
  "obstructions": {
    "total": 11,
    "by_category": {
      "power": 11
    },
    "critical": [],
    "wind_turbines": [],
    "tall_structures": []
  },
  "recommendations": [
    "Consider antenna height adjustments",
    "Evaluate alternative frequencies"
  ],
  "query_time_ms": 15240.2
}
```

## 📊 Data Structure Reference

### RFObstruction Object
```json
{
  "osm_id": "string",              // OpenStreetMap ID
  "category": "string",            // Primary category (building, power, communication, etc.)
  "subtype": "string",             // Specific subtype (tower, mast, building, etc.)
  "coordinates": [lon, lat],       // Geographic coordinates [longitude, latitude]
  "height": 30.0,                 // Actual height in meters (if available)
  "estimated_height": 25.0,       // Estimated height in meters
  "elevation": 180.5,             // Ground elevation in meters
  "rf_significance": "high",      // RF impact level (critical, high, medium, low)
  "material": "steel",            // Construction material
  "name": "Tower Name",           // Structure name (if available)
  "operator": "Company Name"      // Operating company (if available)
}
```

### Structure Categories
- **`building`**: Residential, commercial, and industrial buildings
- **`power`**: Electrical infrastructure (towers, lines, substations)
- **`communication`**: Telecom towers, antennas, broadcasting facilities
- **`industrial`**: Factories, chimneys, industrial structures
- **`transportation`**: Bridges, airport infrastructure
- **`wind`**: Wind turbines and wind farms
- **`other`**: Miscellaneous RF-significant structures

### RF Significance Levels
- **`critical`**: Extremely high RF impact (>100m structures, major facilities)
- **`high`**: High RF impact (30-100m structures, power lines)
- **`medium`**: Moderate RF impact (10-30m structures)
- **`low`**: Low RF impact (<10m structures)

## 🚫 Error Handling

### Common Error Responses

#### Authentication Error (401)
```json
{
  "detail": "Invalid or missing authentication token"
}
```

#### Rate Limit Exceeded (429)
```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

#### Validation Error (422)
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "center_lat"],
      "msg": "Field required"
    }
  ]
}
```

#### Server Error (500)
```json
{
  "detail": "Internal server error"
}
```

## ⚡ Rate Limiting

The API implements rate limiting to ensure fair usage:

- **Health endpoint**: 100 requests/minute
- **Stats endpoint**: 10 requests/minute
- **Bbox queries**: 60 requests/minute
- **Radius queries**: 30 requests/minute
- **Line-of-sight analysis**: 10 requests/minute

## 🛠️ Code Examples

### Python Example
```python
import requests
import json

# API configuration
BASE_URL = "http://34.212.90.38:8000"
API_TOKEN = "demo_token_12345"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_TOKEN}"
}

def search_radius(lat, lon, radius_km):
    """Search for structures within radius"""
    url = f"{BASE_URL}/query/radius"
    data = {
        "center_lat": lat,
        "center_lon": lon,
        "radius_km": radius_km
    }
    
    response = requests.post(url, headers=HEADERS, json=data)
    return response.json()

def analyze_rf_path(start_lat, start_lon, end_lat, end_lon, freq_ghz):
    """Analyze RF path for obstructions"""
    url = f"{BASE_URL}/analysis/line-of-sight"
    data = {
        "start_lat": start_lat,
        "start_lon": start_lon,
        "end_lat": end_lat,
        "end_lon": end_lon,
        "frequency_ghz": freq_ghz
    }
    
    response = requests.post(url, headers=HEADERS, json=data)
    return response.json()

# Example usage
chicago_structures = search_radius(41.8781, -87.6298, 8.047)
print(f"Found {chicago_structures['count']} structures")

path_analysis = analyze_rf_path(41.8781, -87.6298, 41.9081, -87.5998, 6.0)
print(f"Path has {path_analysis['obstructions']['total']} potential obstructions")
```

### JavaScript Example
```javascript
const API_BASE = 'http://34.212.90.38:8000';
const API_TOKEN = 'demo_token_12345';

async function searchRadius(lat, lon, radiusKm) {
    const response = await fetch(`${API_BASE}/query/radius`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${API_TOKEN}`
        },
        body: JSON.stringify({
            center_lat: lat,
            center_lon: lon,
            radius_km: radiusKm
        })
    });
    
    return response.json();
}

async function analyzeRFPath(startLat, startLon, endLat, endLon, freqGhz) {
    const response = await fetch(`${API_BASE}/analysis/line-of-sight`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${API_TOKEN}`
        },
        body: JSON.stringify({
            start_lat: startLat,
            start_lon: startLon,
            end_lat: endLat,
            end_lon: endLon,
            frequency_ghz: freqGhz
        })
    });
    
    return response.json();
}

// Example usage
searchRadius(41.8781, -87.6298, 8.047)
    .then(data => console.log(`Found ${data.count} structures`));
```

### cURL Examples

#### Basic Health Check
```bash
curl http://34.212.90.38:8000/health
```

#### Search 10km radius around New York City
```bash
curl -X POST http://34.212.90.38:8000/query/radius \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "center_lat": 40.7589,
    "center_lon": -73.9851,
    "radius_km": 10.0
  }'
```

#### Search for tall structures only
```bash
curl -X POST "http://34.212.90.38:8000/query/radius?structure_type=tall&min_height=50" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "center_lat": 40.7589,
    "center_lon": -73.9851,
    "radius_km": 5.0
  }'
```

#### Analyze microwave link path
```bash
curl -X POST http://34.212.90.38:8000/analysis/line-of-sight \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{
    "start_lat": 40.7589,
    "start_lon": -73.9851,
    "end_lat": 40.8176,
    "end_lon": -73.9782,
    "frequency_ghz": 6.0
  }'
```

## 🎯 Use Cases & Applications

### 1. **RF Site Planning**
```python
# Find suitable locations with minimal obstructions
def find_clear_sites(center_lat, center_lon, search_radius_km):
    results = search_radius(center_lat, center_lon, search_radius_km)
    
    # Filter for areas with fewer obstructions
    low_obstruction_areas = []
    for result in results['results']:
        if result['rf_significance'] in ['low', 'medium']:
            low_obstruction_areas.append(result)
    
    return low_obstruction_areas
```

### 2. **Microwave Path Engineering**
```python
# Analyze multiple frequency options
def optimize_microwave_link(start_lat, start_lon, end_lat, end_lon):
    frequencies = [6.0, 11.0, 18.0, 23.0, 38.0]  # GHz
    best_freq = None
    min_obstructions = float('inf')
    
    for freq in frequencies:
        analysis = analyze_rf_path(start_lat, start_lon, end_lat, end_lon, freq)
        obstruction_count = analysis['obstructions']['total']
        
        if obstruction_count < min_obstructions:
            min_obstructions = obstruction_count
            best_freq = freq
    
    return best_freq, min_obstructions
```

### 3. **Interference Analysis**
```python
# Identify critical RF interference sources
def find_interference_sources(lat, lon, radius_km):
    results = search_radius(lat, lon, radius_km)
    
    critical_sources = [
        result for result in results['results']
        if result['rf_significance'] == 'critical'
    ]
    
    return sorted(critical_sources, key=lambda x: x.get('height', 0), reverse=True)
```

### 4. **Regulatory Compliance**
```python
# Check for protected structures in area
def check_protected_structures(lat, lon, radius_km):
    results = search_radius(lat, lon, radius_km)
    
    protected = []
    for result in results['results']:
        if result['category'] in ['communication', 'airport'] or \
           result.get('height', 0) > 60:  # FAA notification threshold
            protected.append(result)
    
    return protected
```

## 🚀 Best Practices

### Performance Optimization
1. **Use appropriate search radius** - Larger radii significantly increase query time
2. **Apply filters** - Use `structure_type`, `min_height`, and `rf_significance` to reduce results
3. **Implement caching** - Cache frequently queried areas
4. **Batch requests** - Group nearby queries when possible

### Data Interpretation
1. **Consider elevation** - Ground elevation affects actual obstruction height
2. **Fresnel zone analysis** - Use line-of-sight analysis for accurate path planning
3. **Material considerations** - Metal structures have higher RF impact
4. **Seasonal variations** - Consider vegetation growth in foliage seasons

### Error Handling
1. **Implement retry logic** - Handle rate limits gracefully
2. **Validate coordinates** - Ensure lat/lon are within valid ranges
3. **Check response status** - Always verify successful responses
4. **Monitor API health** - Regular health checks for system monitoring

## 📞 Support & Resources

### Documentation
- **Interactive API Docs**: `http://34.212.90.38:8000/docs`
- **ReDoc Documentation**: `http://34.212.90.38:8000/redoc`
- **OpenAPI Specification**: `http://34.212.90.38:8000/openapi.json`

### Technical Specifications
- **Coordinate System**: WGS84 (EPSG:4326)
- **Distance Units**: Kilometers and meters
- **Height Reference**: Meters above ground level
- **Data Source**: OpenStreetMap (enhanced and processed)
- **Update Frequency**: Quarterly (OSM data refresh)

### Contact Information
- **API Status**: Monitor via `/health` endpoint
- **Rate Limits**: Documented per endpoint
- **Data Issues**: Report via GitHub issues
- **Feature Requests**: Submit enhancement requests

---

**© 2025 RF Obstruction Database API - Version 1.0.0**

*This API provides RF obstruction data for engineering and planning purposes. Always verify critical measurements with on-site surveys.* 