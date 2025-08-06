import os
import logging
from datetime import datetime
from utilities.coordinates import convert_dms_to_decimal
from utilities.geometry_utils import get_search_ring_points
from utilities.lidar_map import export_polygon

# Configure logging
logger = logging.getLogger(__name__)

class SearchRingGenerator:
    """
    Class for generating and exporting search rings around sites.
    """
    def __init__(self, project_metadata=None):
        """
        Initialize the search ring generator.

        Args:
            project_metadata: Optional ProjectMetadata object to store project data
        """
        self.project_metadata = project_metadata

    def export_search_rings(self, site_data, output_dir, is_donor=True, donor_radius_ft=1000, recipient_radius_ft=2000):
        """
        Export search rings for a site.

        Args:
            site_data: Dictionary containing site data
            output_dir: Directory to save the output files
            is_donor: Whether this is a donor site (True) or recipient site (False)
            donor_radius_ft: Radius for donor sites in feet
            recipient_radius_ft: Radius for recipient sites in feet

        Returns:
            Dictionary with information about the exported files
        """
        try:
            # Extract site information
            site_id = site_data.get('site_id', 'unknown')
            site_name = site_data.get('site_name', f"Site {site_id}")

            # Get coordinates
            lat_dms = site_data.get('latitude')
            lon_dms = site_data.get('longitude')

            if not lat_dms or not lon_dms:
                logger.error(f"Missing coordinates for site {site_id}")
                return {"error": f"Missing coordinates for site {site_id}"}

            # Convert coordinates to decimal
            lat, lon = convert_dms_to_decimal(lat_dms, lon_dms)
            logger.info(f"Site {site_id} coordinates: {lat}, {lon}")

            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)

            # Generate filename
            site_type = "Donor" if is_donor else "Recipient"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{site_type}_Site_{site_id}_{timestamp}.kml"
            output_path = os.path.join(output_dir, filename)

            # Export search ring
            radius_ft = donor_radius_ft if is_donor else recipient_radius_ft

            logger.info(f"Exporting {site_type} search ring for site {site_id} with radius {radius_ft}ft")

            # Generate search ring points
            ring_points = get_search_ring_points((lat, lon), radius_ft)

            # Export as KML
            export_polygon(
                ring_points,
                output_path,
                f"{site_type} Site Search Ring - {radius_ft}ft",
                description=f"{site_type} site search ring with {radius_ft}ft radius"
            )

            logger.info(f"Search ring exported to {output_path}")

            # Return information about the exported file
            return {
                "site_id": site_id,
                "site_name": site_name,
                "site_type": site_type,
                "radius_ft": radius_ft,
                "output_path": output_path,
                "coordinates": (lat, lon)
            }

        except Exception as e:
            logger.error(f"Error exporting search rings: {str(e)}", exc_info=True)
            return {"error": str(e)}

    def generate_search_ring_points(self, site_data, is_donor=True, donor_radius_ft=1000, recipient_radius_ft=2000):
        """
        Generate points for a search ring without exporting.

        Args:
            site_data: Dictionary containing site data
            is_donor: Whether this is a donor site (True) or recipient site (False)
            donor_radius_ft: Radius for donor sites in feet
            recipient_radius_ft: Radius for recipient sites in feet

        Returns:
            List of (lat, lon) tuples representing the search ring
        """
        try:
            # Extract site information
            site_id = site_data.get('site_id', 'unknown')

            # Get coordinates
            lat_dms = site_data.get('latitude')
            lon_dms = site_data.get('longitude')

            if not lat_dms or not lon_dms:
                logger.error(f"Missing coordinates for site {site_id}")
                return None

            # Convert coordinates to decimal
            lat, lon = convert_dms_to_decimal(lat_dms, lon_dms)
            logger.info(f"Site {site_id} coordinates: {lat}, {lon}")

            # Generate search ring points
            radius_ft = donor_radius_ft if is_donor else recipient_radius_ft

            logger.info(f"Generating {radius_ft}ft search ring points for site {site_id}")
            ring_points = get_search_ring_points((lat, lon), radius_ft)

            return ring_points

        except Exception as e:
            logger.error(f"Error generating search ring points: {str(e)}", exc_info=True)
            return None
