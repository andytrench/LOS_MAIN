#!/usr/bin/env python3
"""
OCR Processor for PDF files

This module provides functions to extract text from PDFs using OCR (Optical Character Recognition).
It uses Tesseract OCR via the pytesseract library to extract text from PDF pages rendered as images.
"""

import os
import logging
import fitz  # PyMuPDF
from PIL import Image
import pytesseract
import tempfile
import re

# Set up logging
logger = logging.getLogger(__name__)

# Configure pytesseract path if needed (uncomment and modify if Tesseract is not in PATH)
# pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'

def preprocess_image(image, enhance_contrast=True, scale_factor=1.5):
    """
    Preprocess image before OCR to improve text recognition.

    Args:
        image: PIL Image object
        enhance_contrast: Whether to enhance contrast
        scale_factor: Factor to scale the image by (larger can improve OCR for small text)

    Returns:
        PIL Image: Preprocessed image
    """
    from PIL import ImageEnhance, ImageFilter

    # Scale image if needed
    if scale_factor != 1:
        new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
        image = image.resize(new_size, Image.LANCZOS)

    # Convert to grayscale
    if image.mode != 'L':
        image = image.convert('L')

    # Enhance contrast
    if enhance_contrast:
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)  # Increase contrast

    # Apply slight blur to reduce noise
    image = image.filter(ImageFilter.SHARPEN)

    return image

def extract_text_with_ocr(pdf_path, dpi=300, preprocess=True, page_range=None):
    """
    Extract text from PDF using OCR.

    Args:
        pdf_path: Path to the PDF file
        dpi: DPI for rendering PDF pages (higher values give better quality but slower processing)
        preprocess: Whether to preprocess images before OCR
        page_range: Range of pages to process (e.g., (0, 3) for first 3 pages)

    Returns:
        str: Extracted text
    """
    logger.info(f"Extracting text from PDF using OCR: {pdf_path}")

    try:
        # Open the PDF
        doc = fitz.open(pdf_path)

        # Determine page range
        if page_range is None:
            start_page = 0
            end_page = doc.page_count
        else:
            start_page = max(0, page_range[0])
            end_page = min(doc.page_count, page_range[1])

        logger.info(f"Processing pages {start_page+1} to {end_page} with OCR")

        # Extract text from each page
        all_text = ""

        for page_num in range(start_page, end_page):
            logger.debug(f"OCR processing page {page_num+1}/{doc.page_count}")

            # Render page to image
            page = doc[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))

            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Preprocess image if requested
            if preprocess:
                img = preprocess_image(img)

            # Perform OCR
            page_text = pytesseract.image_to_string(img)

            # Add page number and text to result
            all_text += f"\n--- PAGE {page_num+1} ---\n\n"
            all_text += page_text + "\n\n"

            logger.debug(f"Extracted {len(page_text)} characters from page {page_num+1}")

        doc.close()
        logger.info(f"OCR extraction complete. Total characters: {len(all_text)}")

        return all_text

    except Exception as e:
        logger.error(f"Error extracting text with OCR: {str(e)}", exc_info=True)
        return ""

def clean_ocr_text(text):
    """
    Clean up common OCR errors in extracted text.

    Args:
        text: Raw OCR text

    Returns:
        str: Cleaned text
    """
    # Remove page markers added during extraction
    text = re.sub(r'\n--- PAGE \d+ ---\n\n', '\n', text)

    # Fix common OCR errors in microwave link PDFs
    replacements = [
        # Fix latitude/longitude format issues
        (r'Lat[li]tude:?\s*(\d+)[°˚]\s*-?\s*(\d+)[\'′]\s*-?\s*(\d+\.?\d*)[\"″]?\s*([NSns])', r'Latitude: \1-\2-\3 \4'),
        (r'Long[li]tude:?\s*(\d+)[°˚]\s*-?\s*(\d+)[\'′]\s*-?\s*(\d+\.?\d*)[\"″]?\s*([EWew])', r'Longitude: \1-\2-\3 \4'),

        # Fix common OCR errors with numbers
        (r'([Ee]levation:?\s*)l', r'\g<1>1'),  # Replace lowercase l with 1
        (r'([Aa]zimuth:?\s*)l', r'\g<1>1'),    # Replace lowercase l with 1
        (r'([Aa]ntenna\s*CL:?\s*)l', r'\g<1>'),  # Remove lowercase l after "Antenna CL:"

        # Fix common prefixes before values
        (r'Latitude:[\s]*[lIW]+', 'Latitude: '),
        (r'Longitude:[\s]*[lI]+', 'Longitude: '),
        (r'Azimuth:[\s]*[lIX]+', 'Azimuth: '),
        (r'Elevation:[\s]*[lI]+', 'Elevation: '),
        (r'[!]?Antenna\s*CL:[\s]*[lIYZ]+', 'Antenna CL: '),

        # Fix frequency and path length
        (r'Frequency\s*\(GHz\)\s*[=:]\s*(\d+\.?\d*)', r'Frequency (GHz) = \1'),
        (r'Path\s*length\s*\((\d+\.?\d*)\s*mi\)', r'Path length (\1 mi)'),

        # Fix site IDs (common format CH12345A)
        (r'([A-Z]{2}\d{5}[A-Z])', r'\1'),
    ]

    # Apply all replacements
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)

    return text

def extract_and_clean_pdf_text(pdf_path, dpi=300, preprocess=True, page_range=None):
    """
    Extract text from PDF using OCR and clean up the results.

    Args:
        pdf_path: Path to the PDF file
        dpi: DPI for rendering PDF pages
        preprocess: Whether to preprocess images before OCR
        page_range: Range of pages to process

    Returns:
        str: Cleaned OCR text
    """
    # Extract text with OCR
    raw_text = extract_text_with_ocr(pdf_path, dpi, preprocess, page_range)

    # Clean up the text
    cleaned_text = clean_ocr_text(raw_text)

    # Log the difference in length
    logger.info(f"Text cleaning: {len(raw_text)} chars → {len(cleaned_text)} chars")

    return cleaned_text

def hybrid_text_extraction(pdf_path, ocr_first=True, min_chars_per_page=50):
    """
    Extract text using both PyMuPDF and OCR, prioritizing the better result.

    Args:
        pdf_path: Path to the PDF file
        ocr_first: Whether to try OCR first (True) or PyMuPDF first (False)
        min_chars_per_page: Minimum characters per page to consider extraction successful

    Returns:
        str: Extracted text from the better method
    """
    logger.info(f"Performing hybrid text extraction on {pdf_path}")

    # Function to extract with PyMuPDF
    def extract_with_pymupdf():
        try:
            doc = fitz.open(pdf_path)
            pymupdf_text = ""
            total_chars = 0

            for page_num in range(doc.page_count):
                page = doc[page_num]
                page_text = page.get_text()
                pymupdf_text += f"\n--- PAGE {page_num+1} ---\n\n"
                pymupdf_text += page_text + "\n\n"
                total_chars += len(page_text)

            doc.close()
            logger.info(f"PyMuPDF extraction: {total_chars} total characters")
            return pymupdf_text, total_chars
        except Exception as e:
            logger.error(f"PyMuPDF extraction failed: {str(e)}")
            return "", 0

    # Extract text using both methods
    if ocr_first:
        # Try OCR first
        ocr_text = extract_and_clean_pdf_text(pdf_path)
        ocr_chars = len(ocr_text)

        # If OCR produced good results, use it
        if ocr_chars > min_chars_per_page * 3:  # Assuming at least 3 pages worth of content
            logger.info(f"Using OCR text ({ocr_chars} chars)")
            return ocr_text

        # Otherwise try PyMuPDF
        logger.info(f"OCR text insufficient ({ocr_chars} chars), trying PyMuPDF")
        pymupdf_text, pymupdf_chars = extract_with_pymupdf()

        # Return the better result
        if pymupdf_chars > ocr_chars:
            logger.info(f"Using PyMuPDF text ({pymupdf_chars} chars)")
            return pymupdf_text
        else:
            logger.info(f"Using OCR text ({ocr_chars} chars)")
            return ocr_text
    else:
        # Try PyMuPDF first
        pymupdf_text, pymupdf_chars = extract_with_pymupdf()

        # If PyMuPDF produced good results, use it
        if pymupdf_chars > min_chars_per_page * 3:  # Assuming at least 3 pages worth of content
            logger.info(f"Using PyMuPDF text ({pymupdf_chars} chars)")
            return pymupdf_text

        # Otherwise try OCR
        logger.info(f"PyMuPDF text insufficient ({pymupdf_chars} chars), trying OCR")
        ocr_text = extract_and_clean_pdf_text(pdf_path)
        ocr_chars = len(ocr_text)

        # Return the better result
        if ocr_chars > pymupdf_chars:
            logger.info(f"Using OCR text ({ocr_chars} chars)")
            return ocr_text
        else:
            logger.info(f"Using PyMuPDF text ({pymupdf_chars} chars)")
            return pymupdf_text

if __name__ == "__main__":
    # Simple command-line interface for testing
    import argparse
    import sys

    # Configure logging to console
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    parser = argparse.ArgumentParser(description="Extract text from PDF using OCR")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for rendering (default: 300)")
    parser.add_argument("--no-preprocess", action="store_true", help="Disable image preprocessing")
    parser.add_argument("--pages", type=str, help="Page range to process (e.g., '0-3' for first 3 pages)")
    parser.add_argument("--hybrid", action="store_true", help="Use hybrid extraction (OCR + PyMuPDF)")
    parser.add_argument("--pymupdf-first", action="store_true", help="Try PyMuPDF before OCR in hybrid mode")

    args = parser.parse_args()

    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        sys.exit(1)

    # Parse page range
    page_range = None
    if args.pages:
        try:
            start, end = map(int, args.pages.split('-'))
            page_range = (start, end)
        except:
            print(f"Error: Invalid page range format. Use 'start-end' (e.g., '0-3')")
            sys.exit(1)

    # Extract text
    if args.hybrid:
        text = hybrid_text_extraction(args.pdf_path, not args.pymupdf_first)
    else:
        text = extract_and_clean_pdf_text(
            args.pdf_path,
            dpi=args.dpi,
            preprocess=not args.no_preprocess,
            page_range=page_range
        )

    # Print the extracted text
    print("\n" + "="*50)
    print("EXTRACTED TEXT:")
    print("="*50 + "\n")
    print(text)

    # Save to file
    output_path = os.path.splitext(args.pdf_path)[0] + "_ocr.txt"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f"\nText saved to: {output_path}")
