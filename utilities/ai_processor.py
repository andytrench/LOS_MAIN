import os
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
import time

from log_config import setup_logging

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging(__name__)

# Configure the Gemini API key
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
    logger.info("Google GenAI SDK configured successfully.")
except Exception as e:
    logger.error(f"Failed to configure Google GenAI SDK: {e}", exc_info=True)
    # You might want to handle this more gracefully depending on application requirements
    # For now, it will fail loudly when genai.GenerativeModel is called.

def process_document_with_ai(file_path):
    """
    Processes a PDF document using Google's Gemini 1.5 Pro model to extract
    microwave link parameters.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        dict: A dictionary containing the extracted site and path data,
              formatted for the tower_parameters.json structure.
              Returns None if processing fails.
    """
    logger.info(f"Starting AI processing for document: {file_path}")

    if not os.path.exists(file_path):
        logger.error(f"File not found at path: {file_path}")
        return None

    try:
        # 1. Upload the file to Google
        logger.info("Uploading file to Google for processing...")
        uploaded_file = genai.upload_file(path=file_path, display_name=os.path.basename(file_path))
        logger.info(f"Successfully uploaded file: {uploaded_file.display_name} (URI: {uploaded_file.uri})")

        # 2. Create the generative model instance
        model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

        # 3. Define the detailed extraction prompt
        prompt = """
You are an expert AI assistant specialized in analyzing microwave path engineering documents. Your task is to extract specific data points from the provided PDF file and return them in a structured JSON format.

The PDF contains details for a microwave communication link with a "donor" site (Site A) and a "recipient" site (Site B).

Please extract the following information and structure it exactly as specified in the JSON format below. Ensure all numerical values are returned as numbers (float or int), not strings.

**JSON Output Format:**
```json
{
            "site_A": {
    "site_id": "Site A Name or ID",
    "latitude": "DD-MM-SS.S N/S",
    "longitude": "DDD-MM-SS.S E/W",
    "elevation_ft": 0.0,
    "antenna_cl_ft": 0.0,
    "azimuth_deg": 0.0
            },
            "site_B": {
    "site_id": "Site B Name or ID",
    "latitude": "DD-MM-SS.S N/S",
    "longitude": "DDD-MM-SS.S E/W",
    "elevation_ft": 0.0,
    "antenna_cl_ft": 0.0,
    "azimuth_deg": 0.0
            },
            "general_parameters": {
    "link_id": "Link Identifier",
    "link_name": "Site A to Site B Name",
    "frequency_ghz": null,
    "path_length_mi": 0.0
            },
            "fresnel_parameters": {
      "fresnel_found": true,
                "zones": [
                    {
                        "zone": 1,
              "enabled": true,
              "zone_percent": 60.0,
              "k_factor": 1.33,
              "color": "#0000FF",
                        "color_name": "blue"
                    },
                    {
                        "zone": 2,
              "enabled": true,
              "zone_percent": 30.0,
              "k_factor": 0.67,
              "color": "#FFFF00",
                        "color_name": "yellow"
                    },
                    {
                        "zone": 3,
              "enabled": true,
              "zone_percent": 100.0,
              "k_factor": 1.33,
              "color": "#FF0000",
                        "color_name": "red"
          }
      ]
  }
}
```

**Detailed Instructions for Extraction:**
1.  **`site_id`**: Find the name or identifier for each site.
2.  **`latitude` / `longitude`**: Extract the geographic coordinates for each site. They must be in Degrees-Minutes-Seconds format (e.g., "34-16-04.3 N").
3.  **`elevation_ft`**: Extract the ground elevation for each site, specified in feet (ft).
4.  **`antenna_cl_ft`**: Extract the antenna centerline height above ground level (AGL) in feet.
5.  **`azimuth_deg`**: Extract the antenna azimuth in degrees. This is a critical value. Pay close attention to which value belongs to Site A and which belongs to Site B.
6.  **`link_id`**: Find the unique identifier for the microwave link.
7.  **`link_name`**: The name of the path, usually a combination of the two site names.
8.  **`frequency_ghz`**: Extract the frequency of the link, in GHz. Look for values like "11 GHz", "6 GHz", "18 GHz", etc. If you cannot find a frequency value in the document, set this to null (not 0.0).
9.  **`path_length_mi`**: Extract the total length of the path, in miles.
10. **`fresnel_parameters`**: Look for values for F1, F2, F3 and K1, K2, K3.
    - `zone_percent`: Use the percentage value associated with F1, F2, and F3.
    - `k_factor`: Use the value associated with K1, K2, and K3.
    - If these specific values are not found, use the default values provided in the JSON schema above and set `fresnel_found` to `false`.

CRITICAL: 
- Extract the EXACT frequency value from the document (e.g., if it says "18.00 GHz", extract 18.0)
- If you cannot find the frequency in the document, set frequency_ghz to null
- Do NOT use 0.0, 11.0, or any default/assumed values
- Common frequencies include: 6, 11, 18, 23, 38 GHz - extract whatever is actually stated

Respond ONLY with the single, complete JSON object. Do not include any explanatory text, markdown formatting, or any other content outside of the JSON structure.
"""

        # 4. Generate content
        logger.info("Sending request to Gemini model...")
        response = model.generate_content([prompt, uploaded_file],
                                          generation_config=genai.types.GenerationConfig(
                                              response_mime_type="application/json"))

        logger.info("Received response from Gemini model.")

        # 5. Clean up the uploaded file
        logger.info(f"Deleting uploaded file: {uploaded_file.name}")
        genai.delete_file(uploaded_file.name)
        logger.info("File deleted successfully.")

        # 6. Parse and return the data
        try:
            # The response.text should be a clean JSON string because of the MIME type setting
            extracted_data = json.loads(response.text)
            logger.info("Successfully parsed JSON response from Gemini.")
            logger.debug(f"Extracted data: {json.dumps(extracted_data, indent=2)}")
            return extracted_data
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from Gemini response: {e}", exc_info=True)
            logger.error(f"Raw Gemini response text: {response.text}")
            return None
        except Exception as e:
            logger.error(f"An unexpected error occurred while parsing the response: {e}", exc_info=True)
            return None

    except Exception as e:
        logger.error(f"An error occurred during the AI processing pipeline: {e}", exc_info=True)
        # Attempt to delete the file if it was uploaded before the error
        if 'uploaded_file' in locals() and uploaded_file:
            try:
                logger.info(f"Attempting to clean up uploaded file after error: {uploaded_file.name}")
                genai.delete_file(uploaded_file.name)
                logger.info("File deleted successfully during error cleanup.")
            except Exception as cleanup_error:
                logger.error(f"Failed to delete file during error cleanup: {cleanup_error}", exc_info=True)
        return None 