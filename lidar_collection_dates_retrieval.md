# Technical Guide: Retrieving LiDAR Collection Dates

This document outlines the technical process for fetching, parsing, and storing collection dates for LiDAR (Light Detection and Ranging) data projects. The workflow is based on interacting with public metadata APIs, primarily The National Map (TNM) and ScienceBase, and includes fallback logic for cases where data is incomplete.

## High-Level Workflow

The process can be broken down into the following key steps:

1.  **Search**: Perform an initial search against a public API (e.g., The National Map) using geographic boundaries (a polygon) to get a list of relevant LiDAR data products.
2.  **Group**: Process the API response to group individual data files (tiles) into logical projects based on their naming conventions.
3.  **Fetch Details**: For each project, use the metadata URL (`metaUrl`) provided in the initial response to fetch a more detailed metadata record from a source like ScienceBase.
4.  **Parse Dates**: Parse the detailed metadata (which can be in JSON or XML format) to find the official collection start and end dates.
5.  **Fallback**: If explicit dates are not found, use fallback logic to infer a date range from the project's name or title (e.g., extracting the year).
6.  **Store**: Store the retrieved date information in a structured format for application use.

### Workflow Diagram

```mermaid
graph TD
    A[Start: Search for LiDAR Data] --> B{API Response Received?};
    B -- Yes --> C[Group Items into Projects by Name];
    B -- No --> Z[End/Error];

    C --> D{For Each Project};
    D --> E[Get a sample item's `metaUrl`];
    E --> F[Fetch Detailed Metadata (JSON/XML)];
    F --> G{Parse for Collection Dates};

    G -- XML Found --> H[Find `<rngdates>` -> `<begdate>` & `<enddate>`];
    G -- JSON Found --> I[Find `startDate` & `endDate` keys];
    G -- No Explicit Dates --> J[Fallback: Extract Year from Project Name];

    H --> K[Format Dates to YYYY-MM-DD];
    I --> K;
    J --> L[Create Full Year Date Range];

    K --> M[Store Collection Period];
    L --> M;

    M --> N{All Projects Processed?};
    N -- No --> D;
    N -- Yes --> Y[End: Dates Retrieved];
```

---

## Detailed Implementation Steps

### Step 1: Search for LiDAR Data via API

The primary entry point is searching for LiDAR products within a specified geographical area.

*   **API Endpoint**: `https://tnmaccess.nationalmap.gov/api/v1/products`
*   **Method**: `GET`
*   **Key Parameters**:
    *   `polygon`: A string of comma-separated longitude/latitude pairs defining the search area (e.g., `-88.5 39.5,-88.5 39.6,-88.4 39.6,-88.4 39.5,-88.5 39.5`).
    *   `datasets`: The type of data to search for. For LiDAR, this is typically `"Lidar Point Cloud (LPC)"`.
    *   `prodFormats`: The desired file format, such as `"LAZ"`.
    *   `start` / `end`: Optional date filters in `YYYY-MM-DD` format.
    *   `outputFormat`: `"JSON"`.

**Example Request (Python)**:
```python
import requests

BASE_URL = "https://tnmaccess.nationalmap.gov/api/v1/products"
polygon_coords = "-88.48,39.77,-88.48,39.78,-88.47,39.78,-88.47,39.77,-88.48,39.77"

params = {
    "polygon": polygon_coords,
    "datasets": "Lidar Point Cloud (LPC)",
    "prodFormats": "LAZ",
    "outputFormat": "JSON"
}

response = requests.get(BASE_URL, params=params)
if response.status_code == 200:
    results = response.json()
    # The response contains a list under the 'items' key
    lidar_items = results.get('items', [])
```

### Step 2: Group Results into Projects

The API returns a flat list of individual file items. These need to be grouped into projects. Project names are typically derived from the filenames.

A utility function should be created to extract a consistent project name from a filename (e.g., from the `downloadURL` field). This logic often involves splitting the filename by underscores `_` and removing tile-specific coordinates or identifiers.

**Example Logic**:
*   `USGS_LPC_IL_SouthCentral_2021_D21_9430_1133.laz` -> `USGS_LPC_IL_SouthCentral_2021`
*   `IA_FullState_2019_9085_1253.laz` -> `IA_FullState_2019`

### Step 3: Fetch Detailed Metadata

For each logical project, take the first item belonging to it and extract its `metaUrl`. This URL is the key to getting comprehensive metadata.

1.  **Get the `metaUrl`**: From a sample item in the project group, get the value of the `metaUrl` key.
2.  **Fetch JSON Metadata**: The `metaUrl` often points to a human-readable page. Append `?format=json` to this URL to get a machine-readable JSON response from the ScienceBase API.

**Example (Python)**:
```python
# Assuming 'item' is a dictionary from the initial API response
meta_url = item.get('metaUrl')

if meta_url:
    json_metadata_url = f"{meta_url}?format=json"
    response = requests.get(json_metadata_url)
    if response.status_code == 200:
        detailed_metadata = response.json()
```

### Step 4: Parse Metadata for Collection Dates

The detailed metadata from ScienceBase contains links to the definitive source of truth, which is often an XML file.

#### A. Parsing XML Metadata (Primary Method)

1.  **Find the XML URL**: In the JSON response from Step 3, look inside the `webLinks` array. Find the object where `type` is `'originalMetadata'` and `title` is `'Product Metadata'`. The `uri` of this object is the URL to the full XML metadata file.

2.  **Fetch and Parse XML**: Download the content from the XML URL. Use an XML parsing library (like Python's `xml.etree.ElementTree`) to parse it.

3.  **Extract Dates**: The collection dates are typically located at the following XML path:
    *   Path: `.//timeperd/timeinfo/rngdates`
    *   Start Date Tag: `<begdate>`
    *   End Date Tag: `<enddate>`

**Example (Python)**:
```python
import xml.etree.ElementTree as ET

# Assume 'xml_content' is the text from the XML URL
root = ET.fromstring(xml_content)

# Namespace handling might be required depending on the XML
ns = {'fgdc': 'http://www.fgdc.gov/metadata/fgdc-std-001-1998.dtd'} # Example

# Find the date range
range_dates_element = root.find('.//timeperd/timeinfo/rngdates')

if range_dates_element is not None:
    start_date_str = range_dates_element.findtext('begdate') # e.g., '20210101'
    end_date_str = range_dates_element.findtext('enddate')   # e.g., '20211231'

    # Dates may need reformatting from YYYYMMDD to YYYY-MM-DD
    if start_date_str and len(start_date_str) == 8:
        start_date = f"{start_date_str[:4]}-{start_date_str[4:6]}-{start_date_str[6:]}"
    if end_date_str and len(end_date_str) == 8:
        end_date = f"{end_date_str[:4]}-{end_date_str[4:6]}-{end_date_str[6:]}"
```

#### B. Parsing JSON Metadata (Alternative/S3)

For some data sources, particularly those hosted on AWS S3, the metadata might be in a `metadata.json` file. The logic is similar: fetch the JSON and look for keys like `startDate` and `endDate`.

### Step 5: Fallback Logic for Missing Dates

If the detailed metadata does not contain an explicit date range, a fallback mechanism should be used.

1.  **Extract Year**: Parse the project name or title for a four-digit number that represents a year (e.g., `2021`).
2.  **Create Date Range**: If a year is found, create a date range spanning the entire year.
    *   Start Date: `YYYY-01-01`
    *   End Date: `YYYY-12-31`

### Step 6: Store the Data

The final extracted dates should be stored in a consistent, structured format associated with the project.

**Example Final Data Structure**:
```json
{
  "USGS_LPC_IL_SouthCentral_2021": {
    "name": "USGS_LPC_IL_SouthCentral_2021",
    "title": "USGS Lidar Point Cloud IL SouthCentral 2021",
    "dates": {
      "Start": "2021-01-01",
      "End": "2021-12-31",
      "Publication": "2022-11-21"
    },
    "spatial_ref": {
        ...
    },
    ...
  }
}
```
