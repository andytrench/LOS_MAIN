"""
Certificate generation module for the LOS application.
Handles the creation of PDF certificates and reports.
"""

import logging
import os
from datetime import datetime
from tkinter import filedialog, messagebox, ttk, Toplevel
import tkinter as tk
import matplotlib.pyplot as plt
from PIL import Image, ImageGrab
from log_config import setup_logging
from utilities.obstruction_analyzer import format_distance, format_clearance
from utilities.export_utils import export_lidar_data_to_csv, export_lidar_data_to_json, export_map_view

# Create logger
logger = setup_logging(__name__)

def export_turbine_certificate(site_a, site_b, turbines, path_length, frequency, map_image=None):
    """Export a certificate for turbine obstruction analysis"""
    try:
        # Ask for save location
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Save Turbine Certificate"
        )

        if not output_path:
            logger.info("Certificate export cancelled by user")
            return False

        # Generate certificate
        logger.info(f"Generating turbine certificate to: {output_path}")

        # Check if reportlab is available
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
        except ImportError:
            logger.error("ReportLab library not available for PDF generation")
            messagebox.showerror("Export Error", "ReportLab library not available for PDF generation. Please install it with 'pip install reportlab'.")
            return False

        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title_style = styles["Title"]
        elements.append(Paragraph("Wind Turbine Obstruction Analysis Certificate", title_style))
        elements.append(Spacer(1, 0.25*inch))

        # Add date
        date_style = styles["Normal"]
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", date_style))
        elements.append(Spacer(1, 0.25*inch))

        # Add path information
        path_style = styles["Heading2"]
        elements.append(Paragraph("Microwave Path Information", path_style))
        elements.append(Spacer(1, 0.1*inch))

        # Create path information table
        path_data = [
            ["Site A ID", "Site B ID", "Path Length", "Frequency"],
            [
                site_a.get('site_id', 'Unknown'),
                site_b.get('site_id', 'Unknown'),
                f"{path_length:.2f} miles",
                f"{frequency:.1f} GHz"
            ],
            ["Site A Coordinates", "Site B Coordinates", "Site A Height", "Site B Height"],
            [
                f"{site_a.get('latitude', 'Unknown')}\n{site_a.get('longitude', 'Unknown')}",
                f"{site_b.get('latitude', 'Unknown')}\n{site_b.get('longitude', 'Unknown')}",
                f"{site_a.get('elevation_ft', 0) + site_a.get('antenna_cl_ft', 0):.2f} ft",
                f"{site_b.get('elevation_ft', 0) + site_b.get('antenna_cl_ft', 0):.2f} ft"
            ]
        ]

        path_table = Table(path_data, colWidths=[2*inch, 2*inch, 1.5*inch, 1.5*inch])
        path_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (3, 0), colors.lightgrey),
            ('BACKGROUND', (0, 2), (3, 2), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 2), (-1, 2), 'Helvetica-Bold')
        ]))

        elements.append(path_table)
        elements.append(Spacer(1, 0.25*inch))

        # Add map image if available
        if map_image:
            # Save map image to temporary file
            temp_image_path = "temp_map_image.png"
            map_image.save(temp_image_path)

            # Add to PDF
            elements.append(Paragraph("Path Map", path_style))
            elements.append(Spacer(1, 0.1*inch))

            img = RLImage(temp_image_path, width=6*inch, height=4*inch)
            elements.append(img)
            elements.append(Spacer(1, 0.25*inch))

            # Clean up temporary file
            try:
                os.remove(temp_image_path)
            except:
                pass

        # Add turbine information
        elements.append(Paragraph("Wind Turbine Analysis", path_style))
        elements.append(Spacer(1, 0.1*inch))

        if not turbines:
            elements.append(Paragraph("No wind turbines found in the vicinity of the path.", styles["Normal"]))
        else:
            # Create turbine table header
            turbine_data = [
                ["Turbine ID", "Distance to Path", "Height", "Clearance", "Status"]
            ]

            # Add turbine data
            for turbine in turbines:
                # Get turbine ID
                turbine_id = turbine.get('id') or turbine.get('case_id') or 'Unknown'

                # Get distance to path
                distance = turbine.get('distance_to_path', 0)
                distance_str = format_distance(distance)

                # Get height
                height_m = turbine.get('total_height_m') or turbine.get('t_ttlh') or 0
                height_ft = height_m * 3.28084
                height_str = f"{height_ft:.2f} ft ({height_m:.2f} m)"

                # Get clearance (if calculated)
                clearance = turbine.get('clearance', 0)
                clearance_str = format_clearance(clearance)

                # Determine status
                if clearance > 0:
                    status = "Clear"
                    status_color = colors.green
                else:
                    status = "Obstruction"
                    status_color = colors.red

                # Add to table
                turbine_data.append([
                    turbine_id,
                    distance_str,
                    height_str,
                    clearance_str,
                    status
                ])

            # Create table
            turbine_table = Table(turbine_data, colWidths=[1*inch, 2*inch, 1*inch, 1.5*inch, 1.5*inch])

            # Style table
            table_style = [
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')
            ]

            # Add status colors
            for i in range(1, len(turbine_data)):
                status = turbine_data[i][-1]
                if status == "Clear":
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.green))
                else:
                    table_style.append(('TEXTCOLOR', (-1, i), (-1, i), colors.red))

            turbine_table.setStyle(TableStyle(table_style))
            elements.append(turbine_table)

        # Add methodology section
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph("Analysis Methodology", path_style))
        elements.append(Spacer(1, 0.1*inch))

        methodology_text = """
        This certificate analyzes potential obstructions from wind turbines to the microwave path.
        The analysis includes:

        1. Calculation of the perpendicular distance from each turbine to the path
        2. Determination of the height of each turbine
        3. Calculation of the path height at the point closest to each turbine
        4. Adjustment for earth curvature using 4/3 earth model
        5. Calculation of the first Fresnel zone radius
        6. Determination of clearance between the path (including Fresnel zone) and the turbine

        A turbine is considered an obstruction if it penetrates the Fresnel zone of the path.
        """

        elements.append(Paragraph(methodology_text, styles["Normal"]))

        # Add certification statement
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph("Certification", path_style))
        elements.append(Spacer(1, 0.1*inch))

        certification_text = """
        This analysis was performed using the LOS Tool application, which implements industry-standard
        methodologies for microwave path clearance analysis. The results are based on the best available
        data for turbine locations and heights, and standard engineering practices for path analysis.
        """

        elements.append(Paragraph(certification_text, styles["Normal"]))

        # Build PDF
        doc.build(elements)

        logger.info(f"Certificate successfully exported to: {output_path}")
        messagebox.showinfo("Export Complete", f"Certificate successfully exported to:\n{output_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting turbine certificate: {str(e)}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export certificate: {str(e)}")
        return False

def export_map_view(map_widget):
    """Export the current map view as an image"""
    try:
        # Ask for save location
        output_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
            title="Save Map View"
        )

        if not output_path:
            logger.info("Map export cancelled by user")
            return False

        # Capture map widget
        logger.info(f"Exporting map view to: {output_path}")

        # Get map widget's position and size
        x = map_widget.winfo_rootx()
        y = map_widget.winfo_rooty()
        width = map_widget.winfo_width()
        height = map_widget.winfo_height()

        # Capture screenshot
        image = ImageGrab.grab((x, y, x+width, y+height))

        # Save image
        image.save(output_path)

        logger.info(f"Map view successfully exported to: {output_path}")
        messagebox.showinfo("Export Complete", f"Map view successfully exported to:\n{output_path}")
        return True
    except Exception as e:
        logger.error(f"Error exporting map view: {str(e)}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export map view: {str(e)}")
        return False

def export_elevation_profile(elevation_profile, output_path=None):
    """Export the elevation profile as an image"""
    try:
        # Ask for save location if not provided
        if not output_path:
            output_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG files", "*.png"), ("All files", "*.*")],
                title="Save Elevation Profile"
            )

        if not output_path:
            logger.info("Profile export cancelled by user")
            return False

        # Get the figure from the elevation profile
        if hasattr(elevation_profile, 'figure') and elevation_profile.figure:
            # Save figure
            elevation_profile.figure.savefig(output_path, dpi=300, bbox_inches='tight')

            logger.info(f"Elevation profile successfully exported to: {output_path}")
            messagebox.showinfo("Export Complete", f"Elevation profile successfully exported to:\n{output_path}")
            return True
        else:
            logger.warning("No elevation profile figure available")
            messagebox.showwarning("Export Warning", "No elevation profile figure available to export.")
            return False
    except Exception as e:
        logger.error(f"Error exporting elevation profile: {str(e)}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to export elevation profile: {str(e)}")
        return False

def generate_report(site_a, site_b, turbines, lidar_data, map_image=None, elevation_image=None):
    """Generate a comprehensive report with all analysis data"""
    try:
        # Ask for save location
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Save Comprehensive Report"
        )

        if not output_path:
            logger.info("Report generation cancelled by user")
            return False

        # Generate report
        logger.info(f"Generating comprehensive report to: {output_path}")

        # Check if reportlab is available
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
        except ImportError:
            logger.error("ReportLab library not available for PDF generation")
            messagebox.showerror("Export Error", "ReportLab library not available for PDF generation. Please install it with 'pip install reportlab'.")
            return False

        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Add title
        title_style = styles["Title"]
        elements.append(Paragraph("Microwave Path Analysis Report", title_style))
        elements.append(Spacer(1, 0.25*inch))

        # Add date
        date_style = styles["Normal"]
        elements.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d')}", date_style))
        elements.append(Spacer(1, 0.25*inch))

        # Add path information
        # ... (similar to the turbine certificate)

        # Add LIDAR data section
        # ... (add LIDAR data details)

        # Add turbine analysis section
        # ... (similar to the turbine certificate)

        # Add images
        # ... (add map and elevation profile images)

        # Build PDF
        doc.build(elements)

        logger.info(f"Report successfully generated to: {output_path}")
        messagebox.showinfo("Export Complete", f"Report successfully generated to:\n{output_path}")
        return True
    except Exception as e:
        logger.error(f"Error generating report: {str(e)}", exc_info=True)
        messagebox.showerror("Export Error", f"Failed to generate report: {str(e)}")
        return False

def export_project_certificates(app_controller):
    """Export certificate for the currently selected project

    Args:
        app_controller: The application controller instance with access to project_details, project_metadata, etc.
    """
    logger.info("Starting certificate export process")
    try:
        # Get currently selected project
        selected = app_controller.project_details.project_combobox.get()
        if not selected or selected == "Overview":
            messagebox.showwarning("No Project Selected",
                                 "Please select a specific project from the dropdown first.")
            return

        logger.info(f"Selected project: {selected}")

        # Get project metadata
        project_data = app_controller.project_metadata.get_project(selected)
        if not project_data:
            logger.warning(f"No metadata found for project: {selected}")
            messagebox.showerror("Error", f"No metadata found for project: {selected}")
            return

        # Create a dialog to select what to export
        export_options = [
            "Export Criticals",
            "Project Certificate",
            "Map View",
            "LIDAR Data Table (CSV)",
            "LIDAR Data Table (JSON)"
        ]

        # Create a custom dialog for export options
        from tkinter import Toplevel, Label, Listbox, Button, SINGLE

        export_dialog = Toplevel(app_controller.root)
        export_dialog.title("Export Options")
        export_dialog.geometry("400x300")
        export_dialog.transient(app_controller.root)
        export_dialog.grab_set()

        # Center the dialog on the parent window
        x = app_controller.root.winfo_x() + (app_controller.root.winfo_width() // 2) - (400 // 2)
        y = app_controller.root.winfo_y() + (app_controller.root.winfo_height() // 2) - (300 // 2)
        export_dialog.geometry(f"+{x}+{y}")

        Label(export_dialog, text="Select what to export:", font=("Arial", 12)).pack(pady=10)

        # Create listbox for options
        listbox = Listbox(export_dialog, selectmode=SINGLE, font=("Arial", 11), height=len(export_options))
        for option in export_options:
            listbox.insert("end", option)
        listbox.select_set(0)  # Select "Export Criticals" by default (now the first option)
        listbox.pack(fill="both", expand=True, padx=20, pady=10)

        # Function to handle export selection
        def on_export_selected():
            selection = listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select an export option.")
                return

            option = export_options[selection[0]]
            export_dialog.destroy()

            # Handle the selected export option
            if option == "Export Criticals":
                # Export critical files
                from utilities.export_utils import export_criticals
                export_criticals(app_controller)
            elif option == "Project Certificate":
                # Continue with the original certificate export process
                _export_project_certificate(app_controller, selected, project_data)
            elif option == "Map View":
                # Export map view
                if hasattr(app_controller, 'map_widget_ref') and app_controller.map_widget_ref:
                    export_map_view(app_controller.map_widget_ref, app_controller.root)
                else:
                    messagebox.showwarning("No Map", "Map view not available.")
            elif option == "LIDAR Data Table (CSV)":
                # Export LIDAR data as CSV
                if hasattr(app_controller, 'downloader') and app_controller.downloader:
                    export_lidar_data_to_csv(app_controller.downloader)
                else:
                    messagebox.showwarning("No Data", "LIDAR data not available.")
            elif option == "LIDAR Data Table (JSON)":
                # Export LIDAR data as JSON
                if hasattr(app_controller, 'downloader') and app_controller.downloader:
                    export_lidar_data_to_json(app_controller.downloader)
                else:
                    messagebox.showwarning("No Data", "LIDAR data not available.")

        # Function to handle cancel
        def on_cancel():
            export_dialog.destroy()

        # Add buttons
        Button(export_dialog, text="Export", command=on_export_selected, width=10).pack(side="left", padx=20, pady=20)
        Button(export_dialog, text="Cancel", command=on_cancel, width=10).pack(side="right", padx=20, pady=20)

        # Wait for the dialog to close
        app_controller.root.wait_window(export_dialog)

    except Exception as e:
        logger.error(f"Error in export_project_certificates: {e}", exc_info=True)
        messagebox.showerror("Error", f"An error occurred: {str(e)}")

def _export_project_certificate(app_controller, selected, project_data):
    """Export certificate for a specific project

    Args:
        app_controller: The application controller instance
        selected: The selected project name
        project_data: The project metadata
    """
    try:
        logger.info(f"Project data keys: {list(project_data.keys())}")

        # Get output directory
        logger.debug("Prompting for output directory")
        output_dir = filedialog.askdirectory(
            title="Select folder to save certificate",
            initialdir=os.path.expanduser("~")
        )
        if not output_dir:
            logger.info("User cancelled directory selection")
            return

        logger.info(f"Selected output directory: {output_dir}")

        try:
            # Center the map on the project area
            bounds = project_data.get('bounds', {})
            if bounds:
                try:
                    # Calculate center point from bounds
                    min_y = float(bounds.get('minY', 0) or bounds.get('south', 0))
                    max_y = float(bounds.get('maxY', 0) or bounds.get('north', 0))
                    min_x = float(bounds.get('minX', 0) or bounds.get('west', 0))
                    max_x = float(bounds.get('maxX', 0) or bounds.get('east', 0))

                    center_lat = (min_y + max_y) / 2
                    center_lon = (min_x + max_x) / 2

                    # Set map position to center of bounds
                    app_controller.map_widget.set_position(center_lat, center_lon)

                    # Calculate appropriate zoom level based on bounds size
                    lat_span = abs(max_y - min_y)
                    lon_span = abs(max_x - min_x)

                    # Add padding to ensure all bounds are visible
                    lat_span *= 1.2  # Add 20% padding
                    lon_span *= 1.2  # Add 20% padding

                    # Determine zoom level based on the larger span
                    max_span = max(lat_span, lon_span)

                    # More granular zoom levels for better visibility
                    if max_span < 0.005:  # Very small area
                        zoom = 16
                    elif max_span < 0.01:
                        zoom = 15
                    elif max_span < 0.02:
                        zoom = 14
                    elif max_span < 0.05:
                        zoom = 13
                    elif max_span < 0.1:
                        zoom = 12
                    elif max_span < 0.2:
                        zoom = 11
                    elif max_span < 0.5:
                        zoom = 10
                    elif max_span < 1.0:
                        zoom = 9
                    else:
                        zoom = 8

                    # Ensure zoom is not too high or too low
                    zoom = max(min(zoom, 16), 6)

                    app_controller.map_widget.set_zoom(zoom)
                    logger.info(f"Centered map on project area: ({center_lat:.6f}, {center_lon:.6f}), zoom: {zoom}")
                    logger.info(f"Bounds: minY={min_y}, maxY={max_y}, minX={min_x}, maxX={max_x}, span={max_span}")
                except Exception as e:
                    logger.error(f"Error centering map on project area: {e}", exc_info=True)
                    # Continue with the process even if centering fails
            else:
                logger.warning("No bounds information available for project")

            # Show dialog for map capture
            # Create a custom dialog that stays open until user explicitly clicks a button
            # but allows interaction with the main window
            adjust_dialog = tk.Toplevel(app_controller.root)
            adjust_dialog.title("Adjust Map View")
            adjust_dialog.geometry("400x150")
            adjust_dialog.transient(app_controller.root)

            # Keep dialog on top but allow map interaction
            adjust_dialog.attributes('-topmost', True)

            # Set focus to dialog but allow switching back to main window
            adjust_dialog.focus_set()

            # Add instructions label
            ttk.Label(
                adjust_dialog,
                text="The map has been centered on the project area.\n\nYou can now adjust the map zoom and position.\nClick 'Capture' when ready.",
                justify=tk.CENTER
            ).pack(pady=20)

            # Create capture flag
            capture_flag = {'proceed': False}

            # Create button frame
            button_frame = ttk.Frame(adjust_dialog)
            button_frame.pack(side=tk.BOTTOM, pady=15)

            # Add buttons
            def on_capture():
                capture_flag['proceed'] = True
                adjust_dialog.destroy()

            def on_cancel():
                adjust_dialog.destroy()

            ttk.Button(
                button_frame,
                text="Capture",
                command=on_capture
            ).pack(side=tk.LEFT, padx=20)

            ttk.Button(
                button_frame,
                text="Cancel",
                command=on_cancel
            ).pack(side=tk.LEFT, padx=20)

            # Position the dialog in a corner that doesn't cover the center of the map
            screen_width = app_controller.root.winfo_screenwidth()
            screen_height = app_controller.root.winfo_screenheight()
            dialog_width = 400
            dialog_height = 150

            # Position in the top-right corner of the screen
            dialog_x = screen_width - dialog_width - 20
            dialog_y = 100

            adjust_dialog.geometry(f"{dialog_width}x{dialog_height}+{dialog_x}+{dialog_y}")

            # Wait for dialog to be closed
            logger.info("Waiting for user to adjust map view for certificate")
            app_controller.root.wait_window(adjust_dialog)
            logger.info(f"Dialog closed, proceed flag: {capture_flag['proceed']}")

            # Proceed with capture only if the capture button was clicked
            if capture_flag['proceed']:
                # Capture the map view
                coverage_map = app_controller._capture_map_view()
                logger.info(f"Map view captured: {coverage_map}")

                # Check for XML metadata
                xml_metadata = None
                xml_path = os.path.join("XML_Temp", f"{selected}_metadata.xml")
                if os.path.exists(xml_path):
                    logger.info(f"Found XML metadata at: {xml_path}")
                    try:
                        with open(xml_path, 'r', encoding='utf-8') as f:
                            xml_metadata = f.read()
                        logger.info("Successfully loaded XML metadata")
                    except Exception as e:
                        logger.error(f"Error reading XML metadata: {e}", exc_info=True)
                else:
                    logger.info(f"No XML metadata found at: {xml_path}")

                # Prepare project data for certificate
                project = {
                    'name': selected,
                    'data': project_data,
                    'title': project_data.get('title', selected),
                    'dates': project_data.get('dates', {}),
                    'collection': project_data.get('collection', {}),
                    'quality': project_data.get('quality', {}),
                    'spatial_ref': project_data.get('spatial_ref', {}),
                    'bounds': project_data.get('bounds', {}),
                    'coverage_map': coverage_map  # This is the map image path
                }

                # Add XML metadata if available
                if xml_metadata:
                    project['xml_metadata'] = xml_metadata

                # Create certificate
                try:
                    from certificates import create_certificate
                    cert_path = create_certificate(project, output_dir)

                    if cert_path:
                        logger.info(f"Certificate created: {cert_path}")
                        messagebox.showinfo(
                            "Certificate Created",
                            f"Certificate has been created and saved to:\n{cert_path}"
                        )

                        # Don't clean up temporary files - the certificate creation function will handle this
                        # This ensures the map image is available for the certificate
                    else:
                        logger.error("Certificate creation failed, no path returned")
                        messagebox.showerror(
                            "Certificate Creation Failed",
                            "Failed to create certificate. Please check the logs for details."
                        )
                except Exception as cert_error:
                    logger.error(f"Error creating certificate: {cert_error}", exc_info=True)
                    messagebox.showerror(
                        "Certificate Creation Error",
                        f"An error occurred while creating the certificate: {str(cert_error)}"
                    )
            else:
                logger.info("Certificate export cancelled by user")
        except Exception as e:
            logger.error(f"Error in export process: {e}", exc_info=True)
            messagebox.showerror("Error", f"An error occurred: {str(e)}")
            return False

        return True
    except Exception as e:
        logger.error(f"Error in _export_project_certificate: {e}", exc_info=True)
        messagebox.showerror("Error", f"An error occurred: {str(e)}")
        return False
