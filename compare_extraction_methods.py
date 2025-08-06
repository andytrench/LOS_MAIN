#!/usr/bin/env python3
"""
Compare PDF Text Extraction Methods

This script compares different methods of extracting text from PDFs:
1. PyMuPDF (fitz) direct extraction
2. OCR-based extraction using Tesseract
3. Hybrid approach

It helps determine which method works best for your specific PDFs.
"""

import os
import sys
import argparse
import fitz  # PyMuPDF
import logging
from datetime import datetime
from utilities.ocr_processor import extract_and_clean_pdf_text, hybrid_text_extraction

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def extract_with_pymupdf(pdf_path):
    """Extract text using PyMuPDF."""
    try:
        doc = fitz.open(pdf_path)
        pymupdf_text = ""
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_text = page.get_text()
            pymupdf_text += f"\n--- PAGE {page_num+1} ---\n\n"
            pymupdf_text += page_text + "\n\n"
            
        doc.close()
        return pymupdf_text
    except Exception as e:
        logger.error(f"PyMuPDF extraction failed: {str(e)}")
        return ""

def compare_extraction_methods(pdf_path, output_dir=None):
    """
    Compare different text extraction methods on the same PDF.
    
    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save the output files
        
    Returns:
        dict: Comparison results
    """
    logger.info(f"Comparing extraction methods for: {pdf_path}")
    
    # Create output directory if needed
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path) or '.'
        
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Get filename without extension
    pdf_filename = os.path.basename(pdf_path)
    pdf_name = os.path.splitext(pdf_filename)[0]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Extract text using different methods
    methods = {
        "pymupdf": {
            "name": "PyMuPDF",
            "description": "Direct text extraction using PyMuPDF",
            "function": extract_with_pymupdf
        },
        "ocr": {
            "name": "OCR (Tesseract)",
            "description": "OCR-based extraction using Tesseract",
            "function": lambda p: extract_and_clean_pdf_text(p, dpi=300, preprocess=True)
        },
        "hybrid": {
            "name": "Hybrid (OCR First)",
            "description": "Hybrid approach trying OCR first, then PyMuPDF if needed",
            "function": lambda p: hybrid_text_extraction(p, ocr_first=True)
        }
    }
    
    results = {}
    
    # Run each extraction method
    for method_id, method_info in methods.items():
        logger.info(f"Extracting with {method_info['name']}...")
        start_time = datetime.now()
        
        # Extract text
        extracted_text = method_info["function"](pdf_path)
        
        # Calculate time taken
        end_time = datetime.now()
        time_taken = (end_time - start_time).total_seconds()
        
        # Save to file
        output_filename = f"{pdf_name}_{method_id}_{timestamp}.txt"
        output_path = os.path.join(output_dir, output_filename)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"EXTRACTION METHOD: {method_info['name']}\n")
            f.write(f"DESCRIPTION: {method_info['description']}\n")
            f.write(f"TIME TAKEN: {time_taken:.2f} seconds\n")
            f.write(f"CHARACTERS EXTRACTED: {len(extracted_text)}\n")
            f.write("="*50 + "\n\n")
            f.write(extracted_text)
        
        # Store results
        results[method_id] = {
            "name": method_info["name"],
            "time_taken": time_taken,
            "char_count": len(extracted_text),
            "output_path": output_path
        }
        
        logger.info(f"{method_info['name']}: {len(extracted_text)} chars in {time_taken:.2f}s")
    
    # Create comparison report
    report_filename = f"{pdf_name}_comparison_{timestamp}.txt"
    report_path = os.path.join(output_dir, report_filename)
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("PDF TEXT EXTRACTION COMPARISON REPORT\n")
        f.write("="*40 + "\n\n")
        f.write(f"PDF: {pdf_path}\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        f.write("SUMMARY\n")
        f.write("-"*40 + "\n")
        for method_id, result in results.items():
            f.write(f"{result['name']}:\n")
            f.write(f"  - Characters: {result['char_count']}\n")
            f.write(f"  - Time: {result['time_taken']:.2f}s\n")
            f.write(f"  - Output: {os.path.basename(result['output_path'])}\n\n")
        
        # Determine best method based on character count
        best_method = max(results.items(), key=lambda x: x[1]['char_count'])
        f.write(f"RECOMMENDATION: {best_method[1]['name']} extracted the most text.\n\n")
        
        # Add sample comparison
        f.write("TEXT SAMPLES\n")
        f.write("-"*40 + "\n")
        for method_id, result in results.items():
            with open(result['output_path'], 'r', encoding='utf-8') as method_file:
                # Skip header lines
                for _ in range(5):
                    method_file.readline()
                
                # Get first 500 chars of actual content
                sample = method_file.read(500)
                
                f.write(f"{result['name']} SAMPLE:\n")
                f.write(f"{sample}...\n\n")
    
    logger.info(f"Comparison report saved to: {report_path}")
    return {
        "results": results,
        "report_path": report_path
    }

def main():
    """Main function to parse arguments and run the comparison."""
    parser = argparse.ArgumentParser(description="Compare PDF text extraction methods")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("-o", "--output-dir", help="Directory to save the output files")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)
    
    result = compare_extraction_methods(args.pdf_path, args.output_dir)
    
    print("\nCOMPARISON SUMMARY:")
    print("-"*40)
    for method_id, method_result in result["results"].items():
        print(f"{method_result['name']}: {method_result['char_count']} chars in {method_result['time_taken']:.2f}s")
    
    print(f"\nDetailed report saved to: {result['report_path']}")
    
    # Try to open the report
    try:
        if sys.platform == 'darwin':  # macOS
            os.system(f"open '{result['report_path']}'")
    except:
        pass

if __name__ == "__main__":
    main()
