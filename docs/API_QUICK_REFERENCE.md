# RF Obstruction Database API - Quick Reference

## 🚀 Essential Information
- **API URL**: `http://34.212.90.38:8000`
- **Auth Token**: `demo_token_12345`
- **Docs**: `http://34.212.90.38:8000/docs`

## 📍 Core Endpoints

### Search Within Radius
```bash
curl -X POST http://34.212.90.38:8000/query/radius \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{"center_lat": 41.8781, "center_lon": -87.6298, "radius_km": 8.047}'
```

### Search Bounding Box
```bash
curl -X POST http://34.212.90.38:8000/query/bbox \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{"min_lat": 41.86, "max_lat": 41.89, "min_lon": -87.64, "max_lon": -87.62}'
```

### RF Path Analysis
```bash
curl -X POST http://34.212.90.38:8000/analysis/line-of-sight \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_12345" \
  -d '{"start_lat": 41.8781, "start_lon": -87.6298, "end_lat": 41.9081, "end_lon": -87.5998, "frequency_ghz": 6.0}'
```

### Health Check
```bash
curl http://34.212.90.38:8000/health
```

### Database Stats
```bash
curl -H "Authorization: Bearer demo_token_12345" http://34.212.90.38:8000/stats
```

## 🔍 Common Filters
- `?structure_type=tall` - Tall structures only
- `?min_height=50` - Minimum height 50m
- `?rf_significance=critical` - Critical RF impact only
- `?limit=500` - Max 500 results

## 📊 Rate Limits
- Health: 100/min
- Stats: 10/min  
- Bbox: 60/min
- Radius: 30/min
- Analysis: 10/min

## 🏗️ Structure Categories
- `building` - Buildings
- `power` - Power infrastructure  
- `communication` - Telecom towers
- `industrial` - Industrial structures
- `wind` - Wind turbines
- `transportation` - Bridges, airports

## 📡 RF Significance
- `critical` - >100m, major facilities
- `high` - 30-100m, power lines
- `medium` - 10-30m structures  
- `low` - <10m structures 