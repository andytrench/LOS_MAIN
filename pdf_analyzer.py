#!/usr/bin/env python3
"""
PDF Analyzer

A more advanced utility to analyze PDFs and extract text with detailed information
about the structure, formatting, and content.
"""

import os
import sys
import argparse
import json
import fitz  # PyMuPDF
from datetime import datetime
import re

def analyze_pdf(pdf_path, output_dir=None, page_limit=None, verbose=False, extract_tables=True):
    """
    Analyze a PDF file and extract text with detailed information.

    Args:
        pdf_path (str): Path to the PDF file
        output_dir (str): Directory to save the output files (default: same as PDF)
        page_limit (int): Maximum number of pages to analyze (default: all pages)
        verbose (bool): Whether to print detailed information
        extract_tables (bool): Whether to attempt table extraction

    Returns:
        dict: Analysis results
    """
    try:
        # Verify the PDF file exists
        if not os.path.exists(pdf_path):
            print(f"Error: PDF file not found: {pdf_path}")
            return None

        # Open the PDF
        document = fitz.open(pdf_path)

        if verbose:
            print(f"PDF opened successfully. Page count: {document.page_count}")

        # Determine how many pages to extract
        if page_limit is None or page_limit > document.page_count:
            pages_to_analyze = document.page_count
        else:
            pages_to_analyze = page_limit

        if verbose:
            print(f"Analyzing {pages_to_analyze} pages...")

        # Prepare results structure
        results = {
            "pdf_info": {
                "filename": os.path.basename(pdf_path),
                "path": pdf_path,
                "total_pages": document.page_count,
                "pages_analyzed": pages_to_analyze,
                "metadata": document.metadata
            },
            "pages": [],
            "full_text": "",
            "potential_data_fields": [],
            "potential_tables": []
        }

        # Extract text and analyze each page
        for page_num in range(pages_to_analyze):
            page = document[page_num]

            # Basic text extraction
            page_text = page.get_text()
            results["full_text"] += page_text

            # Get page dimensions
            page_rect = page.rect

            # Extract text blocks with position information
            blocks = page.get_text("blocks")

            # Extract text with formatting information (HTML)
            html_text = page.get_text("html")

            # Extract text as JSON with detailed formatting
            dict_text = page.get_text("dict")

            # Extract images if available
            images = []
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                base_image = document.extract_image(xref)
                if base_image:
                    images.append({
                        "index": img_index,
                        "width": base_image["width"],
                        "height": base_image["height"],
                        "colorspace": base_image["colorspace"]
                    })

            # Store page information
            page_info = {
                "page_number": page_num + 1,
                "width": page_rect.width,
                "height": page_rect.height,
                "text_length": len(page_text),
                "block_count": len(blocks),
                "image_count": len(images),
                "text": page_text,
                "blocks": [
                    {
                        "bbox": [b[0], b[1], b[2], b[3]],
                        "text": b[4]
                    } for b in blocks
                ],
                "images": images
            }

            results["pages"].append(page_info)

            if verbose:
                print(f"Page {page_num+1}: Extracted {len(page_text)} characters, {len(blocks)} blocks, {len(images)} images")

        # Look for potential data fields (key-value pairs)
        # This uses regex to find patterns like "Field: Value" or "Field = Value"
        field_patterns = [
            r'([A-Za-z0-9_\s]+):\s*([^:\n]+)',  # Field: Value
            r'([A-Za-z0-9_\s]+)\s*=\s*([^=\n]+)'  # Field = Value
        ]

        for pattern in field_patterns:
            matches = re.findall(pattern, results["full_text"])
            for match in matches:
                key = match[0].strip()
                value = match[1].strip()
                if key and value:
                    results["potential_data_fields"].append({
                        "key": key,
                        "value": value
                    })

        # Look for potential coordinates (latitude/longitude)
        coord_patterns = [
            r'(\d{1,3})-(\d{1,2})-(\d{1,2}(?:\.\d+)?)\s*([NSEW])',  # DD-MM-SS.S N/S/E/W
            r'Lat(?:itude)?[:\s]+([+-]?\d+\.\d+)',  # Latitude: DD.DDDD
            r'Lon(?:gitude)?[:\s]+([+-]?\d+\.\d+)'  # Longitude: DD.DDDD
        ]

        coord_matches = []
        for pattern in coord_patterns:
            matches = re.findall(pattern, results["full_text"])
            if matches:
                coord_matches.extend(matches)

        if coord_matches:
            results["potential_coordinates"] = coord_matches

        # Store document page count before closing
        doc_page_count = document.page_count

        # Close the document
        document.close()

        # Determine output file paths
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path) or '.'

        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        pdf_filename = os.path.basename(pdf_path)
        pdf_name = os.path.splitext(pdf_filename)[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Save the raw text
        text_output_path = os.path.join(output_dir, f"{pdf_name}_text_{timestamp}.txt")
        with open(text_output_path, 'w', encoding='utf-8') as f:
            f.write(results["full_text"])

        # Save the analysis results as JSON
        json_output_path = os.path.join(output_dir, f"{pdf_name}_analysis_{timestamp}.json")

        # Create a simplified version of results for JSON output (exclude full page text to reduce size)
        json_results = results.copy()
        for page in json_results["pages"]:
            # Keep only the first 200 characters of each page's text for the JSON output
            if len(page["text"]) > 200:
                page["text"] = page["text"][:200] + "... [truncated]"

            # Simplify blocks to reduce JSON size
            page["blocks"] = f"{len(page['blocks'])} blocks (details omitted for brevity)"

        with open(json_output_path, 'w', encoding='utf-8') as f:
            json.dump(json_results, f, indent=2)

        # Create a human-readable report
        report_output_path = os.path.join(output_dir, f"{pdf_name}_report_{timestamp}.txt")
        with open(report_output_path, 'w', encoding='utf-8') as f:
            f.write(f"PDF ANALYSIS REPORT\n")
            f.write(f"===================\n")
            f.write(f"Source PDF: {pdf_path}\n")
            f.write(f"Analysis date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total pages in PDF: {doc_page_count}\n")
            f.write(f"Pages analyzed: {pages_to_analyze}\n")
            f.write(f"Total characters extracted: {len(results['full_text'])}\n\n")

            # Add metadata
            f.write(f"PDF METADATA\n")
            f.write(f"===========\n")
            for key, value in results["pdf_info"]["metadata"].items():
                f.write(f"{key}: {value}\n")
            f.write("\n")

            # Add page summary
            f.write(f"PAGE SUMMARY\n")
            f.write(f"===========\n")
            for page in results["pages"]:
                f.write(f"Page {page['page_number']}: {page['text_length']} chars, {len(page['blocks'])} blocks, {page['image_count']} images\n")
            f.write("\n")

            # Add potential data fields
            f.write(f"POTENTIAL DATA FIELDS\n")
            f.write(f"====================\n")
            for field in results["potential_data_fields"]:
                f.write(f"{field['key']}: {field['value']}\n")
            f.write("\n")

            # Add potential coordinates
            if "potential_coordinates" in results:
                f.write(f"POTENTIAL COORDINATES\n")
                f.write(f"====================\n")
                for coord in results["potential_coordinates"]:
                    f.write(f"{coord}\n")
                f.write("\n")

            # Add full text
            f.write(f"FULL EXTRACTED TEXT\n")
            f.write(f"===================\n\n")
            f.write(results["full_text"])

        if verbose:
            print(f"Analysis complete.")
            print(f"Raw text saved to: {text_output_path}")
            print(f"Analysis results saved to: {json_output_path}")
            print(f"Human-readable report saved to: {report_output_path}")

        return {
            "results": results,
            "text_output_path": text_output_path,
            "json_output_path": json_output_path,
            "report_output_path": report_output_path
        }

    except Exception as e:
        print(f"Error analyzing PDF: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to parse arguments and run the analysis."""
    parser = argparse.ArgumentParser(description="Analyze PDF files and extract text with detailed information")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("-o", "--output-dir", help="Directory to save the output files")
    parser.add_argument("-p", "--page-limit", type=int, help="Maximum number of pages to analyze")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed information")
    parser.add_argument("--no-tables", action="store_true", help="Skip table extraction")

    args = parser.parse_args()

    result = analyze_pdf(
        args.pdf_path,
        args.output_dir,
        args.page_limit,
        args.verbose,
        not args.no_tables
    )

    if result:
        print(f"Analysis complete.")
        print(f"Raw text saved to: {result['text_output_path']}")
        print(f"Analysis results saved to: {result['json_output_path']}")
        print(f"Human-readable report saved to: {result['report_output_path']}")

        # Optionally open the report
        if args.verbose:
            try:
                if sys.platform == 'darwin':  # macOS
                    os.system(f"open '{result['report_output_path']}'")
                elif sys.platform == 'win32':  # Windows
                    os.system(f"start {result['report_output_path']}")
                else:  # Linux
                    os.system(f"xdg-open '{result['report_output_path']}'")
            except:
                pass
    else:
        print("Analysis failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
