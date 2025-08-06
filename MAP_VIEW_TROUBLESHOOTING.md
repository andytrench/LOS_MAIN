# Map View Troubleshooting Guide

## Quick Diagnostics

Run the diagnostic script to check all components:
```bash
python diagnose_map_issues.py
```

## Common Issues & Solutions

### 1. "No module named 'osmium'" Error
**Solution:**
```bash
pip install osmium
```

### 2. Map Won't Load / Browser Shows Errors
**Check in this order:**

1. **Check Browser Console (F12)**
   - Look for JavaScript errors
   - Check Network tab for failed requests

2. **Verify Server is Running**
   - Map server should be at: `http://127.0.0.1:9000/map`
   - Check terminal for server startup messages

3. **Check tower_parameters.json**
   - Must have valid JSON format
   - Required sections: `site_A`, `site_B`, `general_parameters`
   - Coordinates must be in `adjusted_latitude`/`adjusted_longitude` fields

### 3. Coordinates Not Loading
**Check these fields in tower_parameters.json:**
```json
{
  "site_A": {
    "adjusted_latitude": 43.416583333333335,
    "adjusted_longitude": -84.471
  },
  "site_B": {
    "adjusted_latitude": 43.4125,
    "adjusted_longitude": -84.3411111111111
  }
}
```

### 4. Frequency Values Issues
- System reads frequency from `tower_parameters.json` ✅
- Check: `general_parameters.frequency_ghz`
- Current value should be: `11.0` (as per user preference)

### 5. OSM Structures Not Showing
- ✅ **FIXED**: `osmium` package now installed
- Falls back to spatial index if PostgreSQL not ready (this is normal)
- Shows as "mock data" in logs (this is OK)

### 6. Google Maps vs Leaflet Issues
**Google Maps Requirements:**
- API key in `.env` file: `GOOGLE_MAPS_API_KEY`
- Current status: ✅ API key found

**Leaflet (Fallback):**
- Works without API keys
- Uses OpenStreetMap by default
- Can use Mapbox with token

## Map Provider Switching

The map supports multiple providers:
- **Google Maps**: Default, requires API key
- **Leaflet**: Fallback, no API key needed
- **Auto-fallback**: If Google fails, switches to Leaflet

## Data Flow

1. `dropmap.py` → "View on Map" button
2. `LOS_map_view.py` → Loads `tower_parameters.json`
3. `map_server.py` → Serves HTML page
4. `templates/map.html` → Loads JavaScript
5. JavaScript → Fetches coordinates and displays map

## Browser Console Commands

Open browser console (F12) and run:

```javascript
// Check if coordinates loaded
console.log('Current coordinates:', currentCoordinates);

// Check map provider
console.log('Map provider:', currentMapProvider);

// Check if map initialized
console.log('Map object:', map);
```

## File Locations

**Core Files:**
- `tower_parameters.json` - Site data and frequency
- `templates/map.html` - Main HTML template
- `static/js/map_client.js` - Main map JavaScript
- `static/js/map_providers.js` - Google Maps/Leaflet abstraction

**Logs:**
- Check `logs/` directory for detailed error messages

## Port Issues

Default port: `9000`
- If in use, server automatically finds alternative port
- Check terminal output for actual port number

## API Keys

**Google Maps API Key:**
- Location: `.env` file
- Variable: `GOOGLE_MAPS_API_KEY`
- Status: ✅ Found (length: 39)

**Mapbox Token:**
- Location: `.env` file  
- Variable: `MAPBOX_ACCESS_TOKEN`
- Status: ✅ Found (length: 93)

## Quick Test

1. Run: `python dropmap.py`
2. Click "View on Map" button
3. Browser should open to: `http://127.0.0.1:9000/map`
4. Should see donor and recipient sites marked on map

## All Systems Status: ✅ GREEN

- ✅ Dependencies installed
- ✅ Required files present
- ✅ tower_parameters.json valid
- ✅ Coordinates loaded
- ✅ Frequency set correctly (11.0 GHz)
- ✅ API keys configured
- ✅ Port available

**Your map view should now work correctly!** 