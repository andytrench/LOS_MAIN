import tkinter as tk
from tkinter import filedialog, ttk
import xml.etree.ElementTree as ET
import ftplib
import json
from shapely.geometry import Polygon, box
import threading
import logging

class LidarSearchApp:
    def __init__(self, root):
        self.root = root
        self.root.title("NYS LiDAR Search Tool")
        
        # FTP Configuration
        self.FTP_HOST = "ftp.gis.ny.gov"
        self.FTP_BASE_PATH = "/elevation/LIDAR/"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
        
        # Search boundary
        self.search_polygon = None
        
        self.setup_ui()
    
    def setup_ui(self):
        # Create main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # KML Import button
        self.import_btn = ttk.Button(
            main_frame, 
            text="Import KML", 
            command=self.import_kml
        )
        self.import_btn.grid(row=0, column=0, pady=5)
        
        # Status label
        self.status_var = tk.StringVar(value="Ready")
        self.status_label = ttk.Label(
            main_frame, 
            textvariable=self.status_var
        )
        self.status_label.grid(row=1, column=0, pady=5)
        
        # Results tree
        self.results_tree = ttk.Treeview(
            main_frame, 
            columns=("Dataset", "File", "Bounds"),
            show="headings"
        )
        self.results_tree.heading("Dataset", text="Dataset")
        self.results_tree.heading("File", text="File")
        self.results_tree.heading("Bounds", text="Bounds")
        self.results_tree.grid(row=2, column=0, pady=5)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(
            main_frame,
            variable=self.progress_var,
            maximum=100
        )
        self.progress.grid(row=3, column=0, pady=5, sticky=(tk.W, tk.E))
    
    def import_kml(self):
        """Import and parse KML file"""
        filename = filedialog.askopenfilename(
            filetypes=[("KML files", "*.kml")]
        )
        if not filename:
            return
            
        try:
            tree = ET.parse(filename)
            root = tree.getroot()
            
            # Extract coordinates from KML
            coords_elem = root.find(".//{http://www.opengis.net/kml/2.2}coordinates")
            if coords_elem is None:
                raise ValueError("No coordinates found in KML")
                
            # Parse coordinates into list of (lon, lat) tuples
            coords_text = coords_elem.text.strip()
            coords = []
            for coord in coords_text.split():
                lon, lat, _ = map(float, coord.split(','))
                coords.append((lon, lat))
            
            # Create Shapely polygon
            self.search_polygon = Polygon(coords)
            
            self.status_var.set(f"Loaded polygon with {len(coords)} points")
            
            # Start search in background thread
            self.start_search()
            
        except Exception as e:
            self.status_var.set(f"Error loading KML: {str(e)}")
            self.logger.error(f"KML import error: {str(e)}")
    
    def start_search(self):
        """Start LiDAR search in background thread"""
        self.status_var.set("Searching...")
        self.progress_var.set(0)
        
        thread = threading.Thread(target=self.search_lidar_files)
        thread.daemon = True
        thread.start()
    
    def search_lidar_files(self):
        """Search FTP server for LiDAR files within polygon"""
        try:
            # Connect to FTP
            ftp = ftplib.FTP(self.FTP_HOST)
            ftp.login()  # Anonymous login
            
            # Navigate to LiDAR directory
            ftp.cwd(self.FTP_BASE_PATH)
            
            # Get list of datasets
            datasets = []
            ftp.dir(lambda line: datasets.append(line.split()[-1]))
            
            total_datasets = len(datasets)
            processed = 0
            
            for dataset in datasets:
                try:
                    # Update progress
                    processed += 1
                    progress = (processed / total_datasets) * 100
                    self.root.after(0, self.progress_var.set, progress)
                    
                    # Search dataset for LiDAR files
                    self.search_dataset(ftp, dataset)
                    
                except Exception as e:
                    self.logger.error(f"Error processing dataset {dataset}: {str(e)}")
                    continue
            
            self.status_var.set("Search complete")
            
        except Exception as e:
            self.status_var.set(f"Search error: {str(e)}")
            self.logger.error(f"Search error: {str(e)}")
        finally:
            try:
                ftp.quit()
            except:
                pass
    
    def search_dataset(self, ftp, dataset):
        """Search a single dataset for LiDAR files"""
        try:
            dataset_path = f"{self.FTP_BASE_PATH}{dataset}"
            ftp.cwd(dataset_path)
            
            # Find LAS/LAZ files
            files = []
            ftp.dir(lambda line: self.process_file_entry(line, files))
            
            # Check each file's bounds
            for file_info in files:
                if self.check_file_bounds(file_info):
                    # Add to results if within search polygon
                    self.root.after(0, self.add_result, dataset, file_info)
                    
        except Exception as e:
            self.logger.error(f"Error in dataset {dataset}: {str(e)}")
    
    def process_file_entry(self, line, files):
        """Process a single file entry from FTP listing"""
        parts = line.split()
        if len(parts) < 9:
            return
            
        filename = " ".join(parts[8:])
        if filename.lower().endswith(('.las', '.laz')):
            files.append({
                "filename": filename,
                "size": int(parts[4]),
                "date": " ".join(parts[5:8])
            })
    
    def check_file_bounds(self, file_info):
        """Check if file bounds intersect with search polygon"""
        # Extract bounds from filename or fetch header
        # This is a simplified version - you'll need to implement
        # the actual bounds extraction logic based on your needs
        return True  # Placeholder
    
    def add_result(self, dataset, file_info):
        """Add a result to the tree view"""
        self.results_tree.insert(
            "", 
            "end",
            values=(
                dataset,
                file_info["filename"],
                f"Size: {file_info['size']} bytes"
            )
        )

def main():
    root = tk.Tk()
    app = LidarSearchApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()