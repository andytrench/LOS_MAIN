#!/usr/bin/env python3
"""
Show Raw OCR Output

This script extracts text from a PDF using OCR and shows the raw output
before any cleaning or processing. It also shows the cleaned output for comparison.
"""

import os
import sys
import logging
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
from utilities.ocr_processor import extract_text_with_ocr, clean_ocr_text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def show_raw_ocr_output(pdf_path, save_to_file=True):
    """
    Extract text from PDF using OCR and show the raw output.
    
    Args:
        pdf_path: Path to the PDF file
        save_to_file: Whether to save the output to a file
        
    Returns:
        tuple: (raw_text, cleaned_text)
    """
    logger.info(f"Extracting text from PDF: {pdf_path}")
    
    # Extract raw text
    raw_text = extract_text_with_ocr(pdf_path, dpi=300, preprocess=True)
    logger.info(f"Raw text extracted: {len(raw_text)} characters")
    
    # Clean the text
    cleaned_text = clean_ocr_text(raw_text)
    logger.info(f"Cleaned text: {len(cleaned_text)} characters")
    
    # Save to files if requested
    if save_to_file:
        base_path = os.path.splitext(pdf_path)[0]
        
        # Save raw text
        raw_output_path = f"{base_path}_raw_ocr.txt"
        with open(raw_output_path, 'w', encoding='utf-8') as f:
            f.write("RAW OCR OUTPUT\n")
            f.write("=============\n\n")
            f.write(raw_text)
        logger.info(f"Raw text saved to: {raw_output_path}")
        
        # Save cleaned text
        cleaned_output_path = f"{base_path}_cleaned_ocr.txt"
        with open(cleaned_output_path, 'w', encoding='utf-8') as f:
            f.write("CLEANED OCR OUTPUT\n")
            f.write("=================\n\n")
            f.write(cleaned_text)
        logger.info(f"Cleaned text saved to: {cleaned_output_path}")
    
    return raw_text, cleaned_text

def extract_text_with_pymupdf(pdf_path, save_to_file=True):
    """
    Extract text from PDF using PyMuPDF for comparison.
    
    Args:
        pdf_path: Path to the PDF file
        save_to_file: Whether to save the output to a file
        
    Returns:
        str: Extracted text
    """
    logger.info(f"Extracting text with PyMuPDF from: {pdf_path}")
    
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        
        # Extract text from all pages
        pymupdf_text = ""
        for page_num in range(doc.page_count):
            page = doc[page_num]
            page_text = page.get_text()
            pymupdf_text += f"\n--- PAGE {page_num+1} ---\n\n"
            pymupdf_text += page_text + "\n\n"
            
        doc.close()
        logger.info(f"PyMuPDF text extracted: {len(pymupdf_text)} characters")
        
        # Save to file if requested
        if save_to_file:
            output_path = f"{os.path.splitext(pdf_path)[0]}_pymupdf.txt"
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write("PYMUPDF OUTPUT\n")
                f.write("=============\n\n")
                f.write(pymupdf_text)
            logger.info(f"PyMuPDF text saved to: {output_path}")
        
        return pymupdf_text
    except Exception as e:
        logger.error(f"Error extracting text with PyMuPDF: {str(e)}")
        return ""

def show_text_sample(text, title, max_chars=1000):
    """Show a sample of the text."""
    print("\n" + "="*50)
    print(f"{title} (first {min(max_chars, len(text))} chars of {len(text)} total):")
    print("="*50)
    print(text[:max_chars])
    if len(text) > max_chars:
        print("...")
    print("="*50 + "\n")

def main():
    """Main function."""
    if len(sys.argv) < 2:
        print("Usage: python show_raw_ocr.py <pdf_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF file not found: {pdf_path}")
        sys.exit(1)
    
    # Extract text using OCR
    raw_text, cleaned_text = show_raw_ocr_output(pdf_path)
    
    # Extract text using PyMuPDF for comparison
    pymupdf_text = extract_text_with_pymupdf(pdf_path)
    
    # Show samples of the extracted text
    show_text_sample(raw_text, "RAW OCR OUTPUT")
    show_text_sample(cleaned_text, "CLEANED OCR OUTPUT")
    show_text_sample(pymupdf_text, "PYMUPDF OUTPUT")
    
    # Print file paths
    base_path = os.path.splitext(pdf_path)[0]
    print(f"Full outputs saved to:")
    print(f"  - Raw OCR: {base_path}_raw_ocr.txt")
    print(f"  - Cleaned OCR: {base_path}_cleaned_ocr.txt")
    print(f"  - PyMuPDF: {base_path}_pymupdf.txt")
    
    # Try to open the files
    try:
        if sys.platform == 'darwin':  # macOS
            os.system(f"open '{base_path}_raw_ocr.txt'")
            os.system(f"open '{base_path}_cleaned_ocr.txt'")
            os.system(f"open '{base_path}_pymupdf.txt'")
    except:
        pass

if __name__ == "__main__":
    main()
