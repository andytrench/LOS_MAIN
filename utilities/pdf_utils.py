"""
PDF utility functions for the LOS application.
Provides functions for creating PDF documents and certificates.
"""

import os
import json
import logging
import math
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def create_certificate(info, output_dir="test_output"):
    """
    Create a PDF certificate for a LIDAR project.
    
    Args:
        info: Dictionary containing project metadata
        output_dir: Directory to save the certificate
        
    Returns:
        Path to the created PDF file or None if an error occurred
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Generate filename based on project title
        project_name = info.get('title', 'Unknown_Project').replace(' ', '_')
        filename = os.path.join(output_dir, f"LIDAR_Certificate_{project_name}.pdf")
        
        logger.info(f"Creating certificate for {project_name}")
        logger.info(f"Using metadata: {json.dumps(info, indent=2)}")
        
        # Create PDF
        doc = SimpleDocTemplate(filename, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f497d'),
            spaceAfter=30
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#1f497d'),
            spaceBefore=20,
            spaceAfter=10
        )
        
        field_style = ParagraphStyle(
            'CustomField',
            parent=styles['Normal'],
            fontSize=10,
            spaceBefore=5
        )
        
        # Title
        elements.append(Paragraph("LIDAR Data Certificate", title_style))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Italic']))
        elements.append(Spacer(1, 20))
        
        # Project Information
        elements.append(Paragraph("Project Information", heading_style))
        elements.extend([
            Paragraph(f"<b>Project Title:</b> {info.get('title', 'N/A')}", field_style),
            Paragraph(f"<b>Project Summary:</b> {info.get('summary', 'N/A')}", field_style)
        ])
        
        # Temporal Information
        dates = info.get('dates', {})
        if dates:
            elements.append(Paragraph("Temporal Information", heading_style))
            elements.extend([
                Paragraph(f"<b>Collection Start:</b> {dates.get('Start', 'N/A')}", field_style),
                Paragraph(f"<b>Collection End:</b> {dates.get('End', 'N/A')}", field_style),
                Paragraph(f"<b>Publication Date:</b> {dates.get('Publication', 'N/A')}", field_style)
            ])
        
        # Spatial Reference
        spatial_ref = info.get('spatial_ref', {})
        if spatial_ref:
            elements.append(Paragraph("Spatial Reference System", heading_style))
            coord_system = spatial_ref.get('coordinate_system', {})
            elements.extend([
                Paragraph(f"<b>Coordinate System:</b> {coord_system.get('name', 'N/A')}", field_style),
                Paragraph(f"<b>EPSG Code:</b> {coord_system.get('epsg_code', 'N/A')}", field_style),
                Paragraph(f"<b>Units:</b> {coord_system.get('units', 'N/A')}", field_style)
            ])
            
            # Add datum information
            datum = spatial_ref.get('datum', {})
            if datum:
                elements.extend([
                    Paragraph(f"<b>Horizontal Datum:</b> {datum.get('horizontal_datum', 'N/A')}", field_style),
                    Paragraph(f"<b>Vertical Datum:</b> {datum.get('vertical_datum', 'N/A')}", field_style)
                ])
        
        # Coverage Information
        bounds = info.get('bounds', {})
        if bounds:
            elements.append(Paragraph("Coverage Information", heading_style))
            elements.extend([
                Paragraph(f"<b>West Bound:</b> {bounds.get('minX', 'N/A')}°", field_style),
                Paragraph(f"<b>East Bound:</b> {bounds.get('maxX', 'N/A')}°", field_style),
                Paragraph(f"<b>South Bound:</b> {bounds.get('minY', 'N/A')}°", field_style),
                Paragraph(f"<b>North Bound:</b> {bounds.get('maxY', 'N/A')}°", field_style)
            ])
            
            # Calculate and add area coverage if bounds are available
            if all(isinstance(bounds.get(k), (int, float)) for k in ['minX', 'maxX', 'minY', 'maxY']):
                width = abs(bounds['maxX'] - bounds['minX'])
                height = abs(bounds['maxY'] - bounds['minY'])
                area_sqkm = width * height * 111.32 * 111.32  # Approximate conversion to km²
                elements.append(Paragraph(f"<b>Approximate Area Coverage:</b> {area_sqkm:.2f} km²", field_style))
        
        # Quality Information
        quality = info.get('quality', {})
        if quality:
            elements.append(Paragraph("Quality Information", heading_style))
            elements.extend([
                Paragraph(f"<b>Vertical Accuracy:</b> {quality.get('vertical_accuracy', 'N/A')}", field_style),
                Paragraph(f"<b>Horizontal Accuracy:</b> {quality.get('horizontal_accuracy', 'N/A')}", field_style),
                Paragraph(f"<b>Point Spacing:</b> {quality.get('point_spacing', 'N/A')}", field_style),
                Paragraph(f"<b>Point Density:</b> {quality.get('point_density', 'N/A')}", field_style)
            ])
        
        # Collection Parameters
        collection = info.get('collection', {})
        if collection:
            elements.append(Paragraph("Collection Parameters", heading_style))
            elements.extend([
                Paragraph(f"<b>Collection Type:</b> {collection.get('type', 'N/A')}", field_style),
                Paragraph(f"<b>Sensor:</b> {collection.get('sensor', 'N/A')}", field_style),
                Paragraph(f"<b>Platform:</b> {collection.get('platform', 'N/A')}", field_style),
                Paragraph(f"<b>Flying Height:</b> {collection.get('flying_height', 'N/A')}", field_style),
                Paragraph(f"<b>Scan Angle:</b> {collection.get('scan_angle', 'N/A')}", field_style),
                Paragraph(f"<b>Pulse Rate:</b> {collection.get('pulse_rate', 'N/A')}", field_style)
            ])
        
        # Add coverage map if available
        coverage_map = info.get('coverage_map')
        if coverage_map:
            elements.append(Paragraph("Coverage Map", heading_style))
            img = Image(coverage_map)
            img.drawHeight = 300
            img.drawWidth = 400
            elements.append(img)
        
        # Build PDF
        doc.build(elements)
        logger.info(f"Certificate created successfully: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error creating certificate: {e}", exc_info=True)
        return None

def create_json_certificate(info, output_dir="test_output"):
    """
    Create a JSON certificate for a LIDAR project.
    
    Args:
        info: Dictionary containing project metadata
        output_dir: Directory to save the certificate
        
    Returns:
        Path to the created JSON file or None if an error occurred
    """
    try:
        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Generate filename based on project title
        project_name = info.get('title', 'Unknown_Project').replace(' ', '_')
        filename = os.path.join(output_dir, f"LIDAR_Certificate_{project_name}.json")
        
        # Add generation timestamp
        certificate_data = info.copy()
        certificate_data['certificate_generated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Write to file
        with open(filename, 'w') as f:
            json.dump(certificate_data, f, indent=2)
            
        logger.info(f"JSON certificate created successfully: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Error creating JSON certificate: {e}", exc_info=True)
        return None

def add_section_header(page, title, y, left_margin):
    """
    Add a section header to the PDF.
    
    Args:
        page: PDF page object
        title: Header title
        y: Y-coordinate
        left_margin: Left margin
        
    Returns:
        New Y-coordinate after adding the header
    """
    page.insert_text((left_margin, y), title, fontsize=14, color=(0, 0, 0.7))
    return y + 20

def add_field(page, label, value, y, left_margin):
    """
    Add a field with label and value to the PDF.
    
    Args:
        page: PDF page object
        label: Field label
        value: Field value
        y: Y-coordinate
        left_margin: Left margin
        
    Returns:
        New Y-coordinate after adding the field
    """
    page.insert_text((left_margin + 20, y), f"{label}:", fontsize=10, color=(0.3, 0.3, 0.3))
    page.insert_text((left_margin + 150, y), str(value), fontsize=10)
    return y + 16
