"""
Utility for converting PDF pages to images for AI processing.
"""

import os
import io
import base64
import logging
import tempfile
from PIL import Image
from log_config import setup_logging

# Configure logging
logger = setup_logging(__name__)

def convert_pdf_to_images(pdf_path, max_pages=3, dpi=300):
    """
    Convert PDF pages to images.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to convert (default: 3)
        dpi: DPI for rendering (default: 300)
        
    Returns:
        list: List of paths to the generated image files
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Please install it with: pip install pymupdf")
        return []
        
    logger.info(f"Converting PDF to images: {pdf_path}")
    
    # Create a temporary directory for the images
    temp_dir = tempfile.mkdtemp(prefix="pdf_images_")
    logger.debug(f"Created temporary directory for PDF images: {temp_dir}")
    
    image_paths = []
    
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        
        # Get the number of pages to process
        num_pages = min(max_pages, len(doc))
        logger.info(f"Processing {num_pages} pages from PDF with {len(doc)} total pages")
        
        # Convert each page to an image
        for page_num in range(num_pages):
            page = doc.load_page(page_num)
            
            # Calculate matrix for desired DPI
            # 72 is the base DPI for PDF
            zoom = dpi / 72
            matrix = fitz.Matrix(zoom, zoom)
            
            # Render page to pixmap
            pix = page.get_pixmap(matrix=matrix)
            
            # Save the pixmap as an image
            image_path = os.path.join(temp_dir, f"page_{page_num+1}.png")
            pix.save(image_path)
            
            image_paths.append(image_path)
            logger.debug(f"Saved page {page_num+1} as image: {image_path}")
            
        logger.info(f"Successfully converted {len(image_paths)} pages to images")
        return image_paths
        
    except Exception as e:
        logger.error(f"Error converting PDF to images: {str(e)}", exc_info=True)
        return []

def get_image_base64(image_path, format="PNG"):
    """
    Convert an image file to base64 encoding.
    
    Args:
        image_path: Path to the image file
        format: Image format (default: PNG)
        
    Returns:
        str: Base64-encoded image data
    """
    try:
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
            return encoded_string
    except Exception as e:
        logger.error(f"Error encoding image to base64: {str(e)}", exc_info=True)
        return ""

def prepare_images_for_claude(pdf_path, max_pages=3, dpi=300):
    """
    Prepare images from a PDF for Claude API.
    
    Args:
        pdf_path: Path to the PDF file
        max_pages: Maximum number of pages to convert (default: 3)
        dpi: DPI for rendering (default: 300)
        
    Returns:
        list: List of dictionaries with image data in Claude API format
    """
    image_paths = convert_pdf_to_images(pdf_path, max_pages, dpi)
    
    claude_images = []
    
    for image_path in image_paths:
        base64_data = get_image_base64(image_path)
        
        if base64_data:
            claude_images.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64_data
                }
            })
    
    # Clean up the temporary image files
    for image_path in image_paths:
        try:
            os.remove(image_path)
        except Exception as e:
            logger.warning(f"Error removing temporary image file {image_path}: {str(e)}")
    
    # Remove the temporary directory
    if image_paths:
        try:
            os.rmdir(os.path.dirname(image_paths[0]))
        except Exception as e:
            logger.warning(f"Error removing temporary directory: {str(e)}")
    
    logger.info(f"Prepared {len(claude_images)} images for Claude API")
    return claude_images
