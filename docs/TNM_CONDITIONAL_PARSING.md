# TNM Conditional Parsing

## Overview

The TNM (The National Map) API can return different JSON structures depending on various factors like server load, API version changes, or different query types. To handle this variability, we've implemented a robust conditional parser that can handle multiple response formats.

## Features

### Conditional JSON Parsing
The new `utilities/tnm_parser.py` module provides:

- **Multiple Format Support**: Handles 9+ different TNM response formats
- **Intelligent Detection**: Automatically detects the response format  
- **Graceful Fallback**: Attempts to extract data even from unknown formats
- **Error Handling**: Properly handles error responses from TNM
- **Field Normalization**: Standardizes field names across different formats

### Supported Response Formats

1. **Standard TNM Format**: `{"items": [...], "total": N}`
2. **Direct Array**: `[{item1}, {item2}, ...]`
3. **Single Item**: `{sourceId: "...", title: "...", ...}`
4. **Nested Results**: `{"results": {"items": [...]}}`
5. **Nested Data**: `{"data": [...]}`
6. **Products Field**: `{"products": [...]}`
7. **Error Response**: `{"error": "message"}`
8. **Empty Response**: `{}`
9. **Unknown Formats**: Attempts to find any array with item-like objects

### Enhanced Error Messages

Instead of cryptic JSON parsing errors, you now get helpful messages like:

```
Invalid response from TNM API. The response was not valid JSON.

This usually indicates:
• TNM service is temporarily unavailable
• Invalid search parameters  
• Service maintenance

Please try again later or use one of the other search methods (Index Search, Point Search).
```

## Usage

### In Your Code

```python
from utilities.tnm_parser import parse_tnm_response

# Parse any TNM response
response_data = requests.get(tnm_url).json()
parsed = parse_tnm_response(response_data, logger)

# Check for errors
if parsed['status'] == 'error':
    print(f"Error: {parsed['error']}")
else:
    print(f"Found {len(parsed['items'])} items")
```

### Testing the Parser

Run the test script to see how different formats are handled:

```bash
python test_scripts/test_tnm_conditional_parser.py
```

This will demonstrate parsing of 7 different response formats.

## Integration

The conditional parser is now automatically used in:

- **Main LIDAR Search** (`dropmap.py` - "Search LIDAR" button)
- **Point Search** (`utilities/point_search.py` - "Point Search" button)

## Debugging TNM Issues

### Enable Debug Logging

Set your logging level to DEBUG to see detailed parsing information:

```python
logging.basicConfig(level=logging.DEBUG)
```

### Check Response Format

Use the format detection function:

```python
from utilities.tnm_parser import detect_tnm_response_format

format_type = detect_tnm_response_format(response_data)
print(f"TNM returned format: {format_type}")
```

### Raw Response Access

The parser preserves the original response for debugging:

```python
parsed = parse_tnm_response(response_data, logger)
original = parsed['raw_response']  # Original TNM response
```

## Alternative Search Methods

If TNM continues to have issues, use these alternatives:

1. **Index Search**: Uses local LIDAR database
2. **Point Search**: Searches specific points along your path
3. **NOAA Search**: Uses NOAA's bathymetric/topographic database

## Benefits

- **Reliability**: No more crashes from unexpected JSON formats
- **Flexibility**: Adapts to TNM API changes automatically  
- **Debugging**: Better error messages and logging
- **Backwards Compatibility**: Works with existing code
- **Future-Proof**: Easily extensible for new formats

## Technical Details

### Field Mapping

The parser automatically maps common field variations:

| Standard Field | Alternative Names |
|----------------|-------------------|
| `sourceId` | `id` |
| `title` | `name` |
| `downloadURL` | `url`, `download_url` |
| `sizeInBytes` | `size` |
| `boundingBox` | `bbox` |
| `publicationDate` | `date` |

### Error Recovery

When encountering unknown formats, the parser:

1. Searches for arrays containing item-like objects
2. Validates each item has required fields
3. Applies default values for missing fields  
4. Preserves original data for debugging

This ensures maximum compatibility with TNM API variations while maintaining data integrity.

### Frequency Handling

The parser respects user preferences for frequency values. Frequency values are always read from the `tower_parameters.json` file rather than using arbitrary or hardcoded values from TNM responses, ensuring consistency across all search methods.

## Known TNM API Issues

### Small Polygon Bug

**Issue**: TNM API has a bug where small search polygons (typically < 1000ft width) trigger an internal server error:
```
{errorMessage=[BadRequest] ''str' object has no attribute 'get''}
```

**Symptoms**: 
- Wider polygons (1000ft+) work fine
- Narrower polygons (500ft, 300ft) fail with JSON parsing errors
- Error occurs in TNM's `get_products.py` Lambda function

**Automatic Solution**: 
The conditional parser now:
1. **Detects** this specific TNM bug automatically
2. **Suggests** increasing polygon width to 1000ft+
3. **Offers** automatic retry with larger polygon
4. **Logs** the issue for debugging

**Manual Workaround**:
Simply increase your search width to 1000ft or more when searching with TNM.

**Root Cause**: 
This appears to be a bug in USGS TNM's server-side polygon processing code, not in our application. 