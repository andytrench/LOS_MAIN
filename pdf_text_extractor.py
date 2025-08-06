#!/usr/bin/env python3
"""
PDF Text Extractor

A simple utility to extract raw text from PDF files and save it to a text file.
This helps analyze what PyMuPDF extracts before any AI processing.
"""

import os
import sys
import argparse
import fitz  # PyMuPDF
from datetime import datetime

def extract_text_from_pdf(pdf_path, output_dir=None, page_limit=None, verbose=False):
    """
    Extract text from a PDF file and save it to a text file.

    Args:
        pdf_path (str): Path to the PDF file
        output_dir (str): Directory to save the output text file (default: same as PDF)
        page_limit (int): Maximum number of pages to extract (default: all pages)
        verbose (bool): Whether to print detailed information

    Returns:
        str: Path to the output text file
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
            pages_to_extract = document.page_count
        else:
            pages_to_extract = page_limit

        if verbose:
            print(f"Extracting text from {pages_to_extract} pages...")

        # Extract text from each page
        all_text = ""
        page_texts = []

        for page_num in range(pages_to_extract):
            page = document[page_num]
            page_text = page.get_text()
            page_texts.append(page_text)
            all_text += page_text

            if verbose:
                print(f"Page {page_num+1}: Extracted {len(page_text)} characters")

        # Store document page count before closing
        doc_page_count = document.page_count
        document.close()

        # Determine output file path
        if output_dir is None:
            output_dir = os.path.dirname(pdf_path) or '.'

        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        pdf_filename = os.path.basename(pdf_path)
        pdf_name = os.path.splitext(pdf_filename)[0]
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_filename = f"{pdf_name}_extracted_{timestamp}.txt"
        output_path = os.path.join(output_dir, output_filename)

        # Save the extracted text
        with open(output_path, 'w', encoding='utf-8') as f:
            # Write a header with information about the extraction
            f.write(f"PDF TEXT EXTRACTION REPORT\n")
            f.write(f"=========================\n")
            f.write(f"Source PDF: {pdf_path}\n")
            f.write(f"Extraction date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total pages in PDF: {doc_page_count}\n")
            f.write(f"Pages extracted: {pages_to_extract}\n")
            f.write(f"Total characters extracted: {len(all_text)}\n")
            f.write(f"=========================\n\n")

            # Write the full text
            f.write("FULL EXTRACTED TEXT\n")
            f.write("===================\n\n")
            f.write(all_text)

            # Write each page separately
            f.write("\n\n=========================\n")
            f.write("TEXT BY PAGE\n")
            f.write("=========================\n\n")

            for page_num, page_text in enumerate(page_texts):
                f.write(f"PAGE {page_num+1}\n")
                f.write("-" * 40 + "\n")
                f.write(page_text)
                f.write("\n\n")

        if verbose:
            print(f"Extracted text saved to: {output_path}")
            print(f"Total characters extracted: {len(all_text)}")

        return output_path

    except Exception as e:
        print(f"Error extracting text from PDF: {str(e)}")
        return None

def main():
    """Main function to parse arguments and run the extraction."""
    parser = argparse.ArgumentParser(description="Extract raw text from PDF files")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("-o", "--output-dir", help="Directory to save the output text file")
    parser.add_argument("-p", "--page-limit", type=int, help="Maximum number of pages to extract")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed information")

    args = parser.parse_args()

    output_path = extract_text_from_pdf(
        args.pdf_path,
        args.output_dir,
        args.page_limit,
        args.verbose
    )

    if output_path:
        print(f"Extraction complete. Output saved to: {output_path}")

        # Optionally open the file
        if args.verbose:
            try:
                if sys.platform == 'darwin':  # macOS
                    os.system(f"open '{output_path}'")
                elif sys.platform == 'win32':  # Windows
                    os.system(f"start {output_path}")
                else:  # Linux
                    os.system(f"xdg-open '{output_path}'")
            except:
                pass
    else:
        print("Extraction failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
