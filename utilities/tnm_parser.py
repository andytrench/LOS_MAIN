"""
TNM API Response Parser

This module provides robust parsing capabilities for TNM (The National Map) API responses
that can handle different JSON structures and formats that the API might return.
"""

import logging

def parse_tnm_response(response_data, logger=None):
    """
    Robust parser for TNM API responses that can handle different JSON structures.
    
    Args:
        response_data: The JSON data from TNM API
        logger: Logger instance for debugging (optional)
        
    Returns:
        dict: Standardized response with 'items', 'total', and other fields
    """
    if logger is None:
        logger = logging.getLogger(__name__)
        
    try:
        # Initialize standardized response structure
        standardized_response = {
            'items': [],
            'total': 0,
            'messages': [],
            'status': 'success',
            'source': 'TNM',
            'raw_response': response_data  # Keep original for debugging
        }
        
        logger.debug(f"Parsing TNM response. Response type: {type(response_data)}")
        logger.debug(f"Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Not a dict'}")
        
        # Case 1: Standard TNM format with 'items' array
        if isinstance(response_data, dict) and 'items' in response_data:
            logger.debug("TNM Response Format: Standard format with 'items' array")
            standardized_response['items'] = response_data.get('items', [])
            standardized_response['total'] = response_data.get('total', len(standardized_response['items']))
            standardized_response['messages'] = response_data.get('messages', [])
            
            # Log sample item structure for debugging
            if standardized_response['items']:
                sample_item = standardized_response['items'][0]
                logger.debug(f"Sample item keys: {list(sample_item.keys()) if isinstance(sample_item, dict) else 'Item not a dict'}")
                
        # Case 2: Direct array of items (some TNM endpoints return this)
        elif isinstance(response_data, list):
            logger.debug("TNM Response Format: Direct array of items")
            standardized_response['items'] = response_data
            standardized_response['total'] = len(response_data)
            
        # Case 3: Single item response (convert to array)
        elif isinstance(response_data, dict) and any(key in response_data for key in ['sourceId', 'downloadURL', 'title']):
            logger.debug("TNM Response Format: Single item response")
            standardized_response['items'] = [response_data]
            standardized_response['total'] = 1
            
        # Case 4: Nested structure (some API versions nest differently)
        elif isinstance(response_data, dict) and 'results' in response_data:
            logger.debug("TNM Response Format: Nested 'results' structure")
            results = response_data['results']
            if isinstance(results, dict) and 'items' in results:
                standardized_response['items'] = results.get('items', [])
                standardized_response['total'] = results.get('total', len(standardized_response['items']))
            elif isinstance(results, list):
                standardized_response['items'] = results
                standardized_response['total'] = len(results)
                
        # Case 5: Data field (alternative nesting)
        elif isinstance(response_data, dict) and 'data' in response_data:
            logger.debug("TNM Response Format: Nested 'data' structure")
            data = response_data['data']
            if isinstance(data, dict) and 'items' in data:
                standardized_response['items'] = data.get('items', [])
                standardized_response['total'] = data.get('total', len(standardized_response['items']))
            elif isinstance(data, list):
                standardized_response['items'] = data
                standardized_response['total'] = len(data)
                
        # Case 6: Products field (specific to some TNM endpoints)
        elif isinstance(response_data, dict) and 'products' in response_data:
            logger.debug("TNM Response Format: 'products' field structure")
            products = response_data['products']
            if isinstance(products, list):
                standardized_response['items'] = products
                standardized_response['total'] = len(products)
                
        # Case 7: Error response with error field OR errorMessage field (TNM Lambda errors)
        elif isinstance(response_data, dict) and ('error' in response_data or 'errorMessage' in response_data):
            error_msg = response_data.get('error') or response_data.get('errorMessage')
            logger.warning(f"TNM API returned error response: {error_msg}")
            
            # Check if this is the known TNM polygon bug
            if "'str' object has no attribute 'get'" in str(error_msg):
                logger.warning("Detected TNM polygon processing bug - likely caused by small polygon size")
                error_msg = f"TNM API bug with small polygons: {error_msg}\n\nSuggestion: Try increasing the search width to 1000ft or more."
            
            standardized_response['status'] = 'error'
            standardized_response['error'] = error_msg
            standardized_response['messages'] = [error_msg]
            
        # Case 8: Empty response or null
        elif not response_data or response_data == {}:
            logger.debug("TNM Response Format: Empty response")
            # Keep default empty response
            
        # Case 9: Unknown format - try to extract any list-like data
        else:
            logger.warning("TNM Response Format: Unknown structure, attempting to extract data")
            # Try to find any arrays in the response that might contain items
            if isinstance(response_data, dict):
                for key, value in response_data.items():
                    if isinstance(value, list) and value:
                        # Check if the list contains item-like objects
                        sample = value[0] if value else {}
                        if isinstance(sample, dict) and any(field in sample for field in ['sourceId', 'title', 'downloadURL', 'id']):
                            logger.debug(f"Found potential items array in field: {key}")
                            standardized_response['items'] = value
                            standardized_response['total'] = len(value)
                            break
        
        # Validate and enhance each item
        validated_items = []
        for i, item in enumerate(standardized_response['items']):
            if not isinstance(item, dict):
                logger.warning(f"Item {i} is not a dictionary, skipping: {type(item)}")
                continue
                
            # Ensure required fields exist with defaults
            validated_item = {
                'sourceId': item.get('sourceId') or item.get('id') or f"TNM_ITEM_{i}",
                'title': item.get('title') or item.get('name') or f"TNM Item {i+1}",
                'downloadURL': item.get('downloadURL') or item.get('url') or item.get('download_url') or '',
                'sizeInBytes': item.get('sizeInBytes') or item.get('size') or 0,
                'format': item.get('format') or 'Unknown',
                'publicationDate': item.get('publicationDate') or item.get('date') or '',
                'boundingBox': item.get('boundingBox') or item.get('bbox') or {},
                'metaUrl': item.get('metaUrl') or item.get('metadata_url') or '',
                'sourceName': item.get('sourceName') or 'TNM',
                'sourceOriginName': item.get('sourceOriginName') or 'USGS TNM'
            }
            
            # Copy any additional fields from the original item
            for key, value in item.items():
                if key not in validated_item:
                    validated_item[key] = value
                    
            # Note: Frequency values should be read from tower_parameters.json rather than TNM response
            # as per user preference for maintaining consistent frequency handling
                    
            validated_items.append(validated_item)
        
        standardized_response['items'] = validated_items
        standardized_response['total'] = len(validated_items)
        
        logger.info(f"TNM response parsed successfully: {len(validated_items)} items found")
        if standardized_response.get('messages'):
            logger.info(f"TNM messages: {standardized_response['messages']}")
            
        return standardized_response
        
    except Exception as e:
        logger.error(f"Error parsing TNM response: {str(e)}", exc_info=True)
        logger.error(f"Raw response data: {response_data}")
        return {
            'items': [],
            'total': 0,
            'status': 'error',
            'error': f"Failed to parse TNM response: {str(e)}",
            'messages': [f"Parser error: {str(e)}"],
            'raw_response': response_data
        }


def validate_tnm_item(item, index=0):
    """
    Validate and normalize a single TNM item.
    
    Args:
        item: The item dictionary to validate
        index: The index of the item (for generating default IDs)
        
    Returns:
        dict: Validated and normalized item
    """
    if not isinstance(item, dict):
        return None
        
    # Ensure required fields exist with defaults
    validated_item = {
        'sourceId': item.get('sourceId') or item.get('id') or f"TNM_ITEM_{index}",
        'title': item.get('title') or item.get('name') or f"TNM Item {index+1}",
        'downloadURL': item.get('downloadURL') or item.get('url') or item.get('download_url') or '',
        'sizeInBytes': item.get('sizeInBytes') or item.get('size') or 0,
        'format': item.get('format') or 'Unknown',
        'publicationDate': item.get('publicationDate') or item.get('date') or '',
        'boundingBox': item.get('boundingBox') or item.get('bbox') or {},
        'metaUrl': item.get('metaUrl') or item.get('metadata_url') or '',
        'sourceName': item.get('sourceName') or 'TNM',
        'sourceOriginName': item.get('sourceOriginName') or 'USGS TNM'
    }
    
    # Copy any additional fields from the original item
    for key, value in item.items():
        if key not in validated_item:
            validated_item[key] = value
            
    return validated_item


def detect_tnm_response_format(response_data):
    """
    Detect the format of a TNM API response.
    
    Args:
        response_data: The JSON data from TNM API
        
    Returns:
        str: Description of the detected format
    """
    if not response_data:
        return "Empty or null response"
    
    if isinstance(response_data, list):
        return "Direct array of items"
    
    if not isinstance(response_data, dict):
        return f"Unexpected type: {type(response_data)}"
    
    if 'items' in response_data:
        return "Standard TNM format with 'items' array"
    
    if 'results' in response_data:
        return "Nested 'results' structure"
    
    if 'data' in response_data:
        return "Nested 'data' structure"
    
    if 'products' in response_data:
        return "'products' field structure"
    
    if 'error' in response_data:
        return "Error response"
    
    if any(key in response_data for key in ['sourceId', 'downloadURL', 'title']):
        return "Single item response"
    
    return "Unknown or custom format" 