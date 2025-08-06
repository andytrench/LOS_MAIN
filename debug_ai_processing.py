#!/usr/bin/env python3
"""
Debug AI Processing

This script shows the exact prompt sent to Claude and the raw response received.
It helps debug issues with AI processing of PDF documents.
"""

import os
import sys
import json
import logging
from anthropic import Anthropic
from dotenv import load_dotenv
from utilities.ocr_processor import extract_and_clean_pdf_text

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize Anthropic client
anthropic_client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def debug_ai_processing(pdf_path, use_ocr=True, save_to_file=True):
    """
    Debug AI processing of a PDF document.
    
    Args:
        pdf_path: Path to the PDF file
        use_ocr: Whether to use OCR for text extraction
        save_to_file: Whether to save the output to files
        
    Returns:
        tuple: (prompt, response)
    """
    logger.info(f"Debugging AI processing of: {pdf_path}")
    
    # Extract text from the PDF
    if use_ocr:
        logger.info("Using OCR for text extraction")
        document_text = extract_and_clean_pdf_text(pdf_path, dpi=300, preprocess=True)
    else:
        logger.info("Using PyMuPDF for text extraction")
        import fitz
        document = fitz.open(pdf_path)
        document_text = ""
        for page_num in range(min(3, document.page_count)):
            page = document[page_num]
            document_text += page.get_text()
        document.close()
    
    logger.info(f"Extracted text length: {len(document_text)}")
    
    # Create the prompt for Claude
    prompt = f"""
Analyze the following text extracted from a microwave link PDF document. Extract the required information in the exact JSON format provided below. The "donor" tower (site A) is on the left side, and the "recipient" tower (site B) is on the right side of the report.

Required JSON format:
{{
  "site_A": {{
    "site_id": "",
    "latitude": "",
    "longitude": "",
    "elevation_ft": 0,
    "antenna_cl_ft": 0,
    "azimuth_deg": 0
  }},
  "site_B": {{
    "site_id": "",
    "latitude": "",
    "longitude": "",
    "elevation_ft": 0,
    "antenna_cl_ft": 0,
    "azimuth_deg": 0
  }},
  "general_parameters": {{
    "frequency_ghz": 0,
    "path_length_mi": 0
  }}
}}

Fill in the JSON structure with the correct values from the text. Ensure all numeric values are numbers, not strings. For latitude and longitude, use the format "DD-MM-SS.S D" where D is the direction (N, S, E, or W).

Important notes:
1. The text was extracted using OCR, so there might be some formatting issues or errors.
2. Look for patterns like "Latitude: XX-XX-XX.X N" and "Longitude: XX-XX-XX.X W" for coordinates.
3. Look for "Elevation: XXX.XX ft" for elevation values.
4. Look for "Antenna CL: XX.XX ft AGL" for antenna heights.
5. Look for "Azimuth: XX.XX Deg" for azimuth values.
6. Look for "Frequency (GHz) = XX.XX" for frequency.
7. Look for "Path length (XX.XX mi)" for path length.

Extracted text:
{document_text[:50000]}

Respond ONLY with the JSON object, no additional text.
"""
    
    logger.info("Sending prompt to Claude")
    
    # Send the prompt to Claude
    response = anthropic_client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=1000,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
    
    logger.info("Received response from Claude")
    
    # Save to files if requested
    if save_to_file:
        base_path = os.path.splitext(pdf_path)[0]
        
        # Save prompt
        prompt_path = f"{base_path}_ai_prompt.txt"
        with open(prompt_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        logger.info(f"Prompt saved to: {prompt_path}")
        
        # Save raw response
        response_path = f"{base_path}_ai_response.txt"
        with open(response_path, 'w', encoding='utf-8') as f:
            f.write(response.content[0].text)
        logger.info(f"Raw response saved to: {response_path}")
        
        # Try to parse and save JSON
        try:
            json_data = json.loads(response.content[0].text)
            json_path = f"{base_path}_ai_parsed.json"
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2)
            logger.info(f"Parsed JSON saved to: {json_path}")
        except json.JSONDecodeError:
            logger.error("Failed to parse response as JSON")
    
    return prompt, response.content[0].text

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python debug_ai_processing.py <pdf_path> [--no-ocr]")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    use_ocr = "--no-ocr" not in sys.argv
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Debug AI processing
    prompt, response = debug_ai_processing(pdf_path, use_ocr)
    
    # Print summary
    print("\n" + "="*50)
    print("AI PROCESSING SUMMARY")
    print("="*50)
    print(f"PDF: {pdf_path}")
    print(f"Text extraction method: {'OCR' if use_ocr else 'PyMuPDF'}")
    print(f"Prompt length: {len(prompt)} characters")
    print(f"Response length: {len(response)} characters")
    print("="*50 + "\n")
    
    # Print response
    print("RAW RESPONSE FROM CLAUDE:")
    print("="*50)
    print(response)
    print("="*50 + "\n")
    
    # Try to parse JSON
    try:
        json_data = json.loads(response)
        print("PARSED JSON:")
        print("="*50)
        print(json.dumps(json_data, indent=2))
        print("="*50 + "\n")
    except json.JSONDecodeError:
        print("ERROR: Failed to parse response as JSON")
    
    # Print file paths
    base_path = os.path.splitext(pdf_path)[0]
    print(f"Full outputs saved to:")
    print(f"  - Prompt: {base_path}_ai_prompt.txt")
    print(f"  - Response: {base_path}_ai_response.txt")
    
    # Try to open the files
    try:
        if sys.platform == 'darwin':  # macOS
            os.system(f"open '{base_path}_ai_response.txt'")
    except:
        pass

if __name__ == "__main__":
    main()
