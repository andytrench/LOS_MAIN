import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import ftplib
import tempfile
import shapely.geometry
import geopandas as gpd
from shapely.geometry import Polygon, box
import json
import threading
import pyproj
from pyproj import Transformer
from shapely.ops import transform
import tkintermapview
import requests  # Add requests for custom geocoding
import xml.etree.ElementTree as ET  # For parsing XML
import io  # For handling XML data as streams
import re  # For regular expressions
import time
import queue
import logging
from datetime import datetime
from threading import Lock, Event
import random

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set User-Agent for Geocoder library (used by tkintermapview)
# Replace with a real contact/project URL if distributing
# Using a more Nominatim-friendly format
os.environ['GEOCODER_UA'] = 'LiDARDownloaderApp/1.0 (Contact: your_email@example.com)'

FTP_HOST = "ftp.gis.ny.gov"
FTP_BASE_PATH = "/elevation/LIDAR/"
CATALOG_FILE = "complete_lidar_catalog.json"  # Path to our comprehensive catalog file

# Custom geocoding function
def geocode_address(address):
    """
    Custom geocoding function using Nominatim with a proper User-Agent header.
    Returns (lat, lon) on success, None on failure.
    """
    try:
        # Nominatim API endpoint
        url = "https://nominatim.openstreetmap.org/search"
        
        # Parameters
        params = {
            "q": address,
            "format": "json",
            "limit": 1
        }
        
        # Headers with a proper User-Agent (please customize if distributing)
        headers = {
            "User-Agent": "LiDARDownloaderApp/1.0 (Contact: your_email@example.com)"
        }
        
        # Make the request
        response = requests.get(url, params=params, headers=headers)
        
        # Check for successful response
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                # Extract coordinates
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                return (lat, lon)
        return None
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
        return None

class LiDARDownloader:
    def __init__(self, root):
        self.root = root
        self.root.title("NY LiDAR Downloader")
        self.root.geometry("1000x850")
        
        # Variable to store selected files
        self.selected_files = []
        self.current_directory = ""
        self.drawn_polygon_widget = None

        # Initialize polygon drawing variables
        self.drawing_polygon = False
        self.polygon_points = []
        self.polygon_markers = []
        self.polygon_path = None

        # For XML metadata caching
        self.xml_cache = {}  # Store XML metadata by dataset name
        self.dataset_bounds = {}  # Store dataset boundary polygons
        
        # Download tracking variables
        self.download_queue = queue.Queue()
        self.active_downloads = set()
        self.current_downloads = 0
        self.max_concurrent_downloads = 5
        self.lock = Lock()
        self.paused = Event()
        self.paused.set()  # Set initially to allow downloads
        
        # Project organization
        self.projects = {}  # Dictionary to store files by project
        self.current_project = tk.StringVar()
        self.selected_checkboxes = set()  # Track selected items by ID
        self.file_status = {}  # Track download status of each file
        
        # Polygon display variables
        self.lidar_polygons = []  # Store all polygon objects
        self.project_polygons = {}  # Store polygons by project
        self.project_visibility = {}  # Track project visibility state
        self.project_colors = {}  # Store colors for each project
        self._original_polygon_data = {}  # Store original polygon data for toggling
        
        # Define a color series for project polygons
        self.color_series = [
            "#FF5733", "#33FF57", "#3357FF", "#F3FF33", "#FF33F3",
            "#33FFF3", "#F333FF", "#FF3333", "#33FF33", "#3333FF"
        ]
        
        # Create main frame
        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Top Frame for Controls and Map ---
        self.top_frame = ttk.Frame(self.main_frame)
        self.top_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create a frame for the top controls
        self.control_frame = ttk.Frame(self.top_frame)
        self.control_frame.pack(fill=tk.X, pady=5)
        
        # Search box
        ttk.Label(self.control_frame, text="Search Address:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(self.control_frame, textvariable=self.search_var, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Search Map", command=self.search_location).pack(side=tk.LEFT, padx=5)

        # New Map interaction buttons for tkintermapview
        self.draw_button = ttk.Button(self.control_frame, text="Start Drawing", command=self.start_drawing_mode)
        self.draw_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Clear Drawing", command=self.clear_drawing).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.control_frame, text="Find LiDAR Files", command=self.find_lidar_files).pack(side=tk.LEFT, padx=5)

        # Map Widget Frame
        self.map_widget_frame = ttk.LabelFrame(self.top_frame, text="Map View")
        self.map_widget_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create map widget - Fix: Enable mouse wheel zooming and map dragging
        self.map_widget = tkintermapview.TkinterMapView(
            self.map_widget_frame, 
            width=780, 
            height=400, 
            corner_radius=0
            # Remove invalid parameter: use_mouse_wheel_for_zooming=True
        )
        self.map_widget.pack(fill=tk.BOTH, expand=True)
        
        # Configure map for dragging and zooming
        self.map_widget.canvas.configure(cursor="fleur")  # Hand cursor for dragging
        
        # Set initial position to New York
        self.map_widget.set_position(42.9538, -75.5268)
        self.map_widget.set_zoom(7)
        # Add satellite view option
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22) # Google satellite

        # --- Bottom Frame for FTP and Files ---
        self.bottom_frame = ttk.Frame(self.main_frame)
        self.bottom_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        # Create a project selection frame
        self.project_frame = ttk.Frame(self.bottom_frame)
        self.project_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(self.project_frame, text="Project:").pack(side=tk.LEFT, padx=5)
        self.project_combo = ttk.Combobox(self.project_frame, textvariable=self.current_project, state="readonly", width=40)
        self.project_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.project_combo.bind("<<ComboboxSelected>>", self.on_project_selected)
        
        ttk.Button(self.project_frame, text="Select All Project Files", command=self.select_all_project_files).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.project_frame, text="Deselect All", command=self.deselect_all_files).pack(side=tk.LEFT, padx=5)

        # Create a paned window for FTP/Files
        self.paned = ttk.PanedWindow(self.bottom_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)
        
        # Frame for FTP browser
        self.ftp_frame = ttk.LabelFrame(self.paned, text="FTP Browser")
        self.paned.add(self.ftp_frame, weight=1)
        
        # Frame for file operations
        self.file_frame = ttk.LabelFrame(self.paned, text="Selected Files")
        self.paned.add(self.file_frame, weight=1)
        
        # FTP navigation
        self.nav_frame = ttk.Frame(self.ftp_frame)
        self.nav_frame.pack(fill=tk.X, pady=5)
        
        self.current_path_var = tk.StringVar(value=FTP_BASE_PATH)
        ttk.Entry(self.nav_frame, textvariable=self.current_path_var, state="readonly", width=40).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.nav_frame, text="Up", command=self.navigate_up).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.nav_frame, text="Refresh", command=self.refresh_ftp).pack(side=tk.LEFT, padx=5)
        
        # FTP file list
        self.ftp_files_frame = ttk.Frame(self.ftp_frame)
        self.ftp_files_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.ftp_tree = ttk.Treeview(self.ftp_files_frame, columns=("size", "date"), show="headings")
        self.ftp_tree.heading("size", text="Size")
        self.ftp_tree.heading("date", text="Date")
        self.ftp_tree.column("size", width=100)
        self.ftp_tree.column("date", width=150)
        self.ftp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.ftp_scrollbar = ttk.Scrollbar(self.ftp_files_frame, orient=tk.VERTICAL, command=self.ftp_tree.yview)
        self.ftp_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.ftp_tree.configure(yscrollcommand=self.ftp_scrollbar.set)
        
        self.ftp_tree.bind("<Double-1>", self.on_ftp_item_double_click)
        self.ftp_tree.bind("<Return>", self.on_ftp_item_double_click)
        self.ftp_tree.bind("<Button-3>", self.on_ftp_right_click)
        
        # Selected files list - upgrade to show download progress and status
        self.selected_files_frame = ttk.Frame(self.file_frame)
        self.selected_files_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Configure styles for treeview
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)  # Taller rows for better readability
        
        # Create enhanced file list with checkboxes and progress info
        self.selected_tree = ttk.Treeview(
            self.selected_files_frame, 
            columns=("select", "path", "size", "progress", "speed", "eta", "status"),
            show="headings"
        )
        
        # Configure columns
        self.selected_tree.heading("select", text="✓")
        self.selected_tree.heading("path", text="Path")
        self.selected_tree.heading("size", text="Size")
        self.selected_tree.heading("progress", text="Progress")
        self.selected_tree.heading("speed", text="Speed")
        self.selected_tree.heading("eta", text="Time Left")
        self.selected_tree.heading("status", text="Status")
        
        # Set column widths
        self.selected_tree.column("select", width=30, anchor="center")
        self.selected_tree.column("path", width=300)
        self.selected_tree.column("size", width=80)
        self.selected_tree.column("progress", width=80)
        self.selected_tree.column("speed", width=80)
        self.selected_tree.column("eta", width=80)
        self.selected_tree.column("status", width=100)
        
        # Configure tags for different states
        self.selected_tree.tag_configure('error', foreground='red')
        self.selected_tree.tag_configure('complete', foreground='green')
        self.selected_tree.tag_configure('downloading', foreground='blue')
        self.selected_tree.tag_configure('paused', foreground='orange')
        
        self.selected_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.selected_scrollbar = ttk.Scrollbar(self.selected_files_frame, orient=tk.VERTICAL, command=self.selected_tree.yview)
        self.selected_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.selected_tree.configure(yscrollcommand=self.selected_scrollbar.set)
        
        # Bind checkbox clicks in the selected files tree
        self.selected_tree.bind("<Button-1>", self.on_checkbox_click)
        
        # Download controls
        self.download_controls_frame = ttk.Frame(self.file_frame)
        self.download_controls_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(self.download_controls_frame, text="Start Download", command=self.start_downloads).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.download_controls_frame, text="Pause", command=self.pause_downloads).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.download_controls_frame, text="Resume", command=self.resume_downloads).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.download_controls_frame, text="Clear Completed", command=self.clear_completed).pack(side=tk.LEFT, padx=5)
        
        # Download button
        self.download_frame = ttk.Frame(self.file_frame)
        self.download_frame.pack(fill=tk.X, pady=5)
        
        self.output_path_var = tk.StringVar()
        ttk.Label(self.download_frame, text="Download to:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(self.download_frame, textvariable=self.output_path_var, width=25).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.download_frame, text="Browse...", command=self.browse_output).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5,0))
        
        # Connect to FTP
        self.connect_ftp()
        
        # Start download worker threads
        self.start_download_workers()

    def connect_ftp(self):
        """Connect to the FTP server and list initial directory"""
        try:
            self.ftp = ftplib.FTP(FTP_HOST)
            self.ftp.login()  # Anonymous login
            self.set_status(f"Connected to {FTP_HOST}")
            self.refresh_ftp()
        except Exception as e:
            messagebox.showerror("FTP Error", f"Error connecting to FTP server: {str(e)}")
            self.set_status(f"Error: {str(e)}")
    
    def refresh_ftp(self):
        """Refresh the current FTP directory listing"""
        current_path = self.current_path_var.get()
        try:
            # Clear existing items
            for item in self.ftp_tree.get_children():
                self.ftp_tree.delete(item)
            
            # Navigate to the directory
            self.ftp.cwd(current_path)
            self.current_directory = current_path
            
            # List directory contents
            files = []
            directories = []
            
            def process_line(line):
                parts = line.split()
                if len(parts) >= 9:
                    # This is a typical Unix-style directory listing
                    file_type = parts[0][0]
                    file_name = " ".join(parts[8:])
                    file_size = parts[4]
                    file_date = " ".join(parts[5:8])
                    
                    if file_type == 'd':
                        directories.append((file_name, file_size, file_date))
                    else:
                        files.append((file_name, file_size, file_date))
            
            self.ftp.retrlines('LIST', process_line)
            
            # Add directories first
            for dir_name, dir_size, dir_date in sorted(directories):
                self.ftp_tree.insert("", tk.END, text=dir_name, values=("DIR", dir_date), tags=("directory",))
                
            # Then add files
            for file_name, file_size, file_date in sorted(files):
                self.ftp_tree.insert("", tk.END, text=file_name, values=(file_size, file_date), tags=("file",))
            
            self.set_status(f"Listing directory: {current_path}")
        except Exception as e:
            messagebox.showerror("FTP Error", f"Error listing directory: {str(e)}")
            self.set_status(f"Error: {str(e)}")
            # Try to go back to the base path
            self.current_path_var.set(FTP_BASE_PATH)
            self.refresh_ftp()
    
    def navigate_up(self):
        """Navigate to the parent directory"""
        current_path = self.current_path_var.get()
        if current_path == FTP_BASE_PATH:
            return
        
        # Get parent directory
        parent_path = os.path.dirname(current_path)
        if not parent_path.endswith('/'):
            parent_path += '/'
            
        self.current_path_var.set(parent_path)
        self.refresh_ftp()
    
    def on_ftp_item_double_click(self, event):
        """Handle double-click on FTP item"""
        selected_item = self.ftp_tree.focus()
        if not selected_item:
            return
            
        item_tags = self.ftp_tree.item(selected_item, "tags")
        item_text = self.ftp_tree.item(selected_item, "text")
        
        if "directory" in item_tags:
            # Navigate to directory
            new_path = os.path.join(self.current_directory, item_text)
            if not new_path.endswith('/'):
                new_path += '/'
            self.current_path_var.set(new_path)
            self.refresh_ftp()
        else:
            # Add file to selected files
            file_path = os.path.join(self.current_directory, item_text)
            self.add_to_selected(file_path)
    
    def on_ftp_right_click(self, event):
        """Handle right-click on FTP item to show context menu"""
        item = self.ftp_tree.identify_row(event.y)
        if not item:
            return
            
        # Select the item
        self.ftp_tree.selection_set(item)
        
        # Create context menu
        menu = tk.Menu(self.root, tearoff=0)
        
        item_tags = self.ftp_tree.item(item, "tags")
        if "file" in item_tags:
            menu.add_command(label="Add to Selected", command=lambda: self.add_selected_to_list())
            menu.add_command(label="Download", command=lambda: self.download_single_file())
        
        menu.tk_popup(event.x_root, event.y_root)
    
    def add_selected_to_list(self):
        """Add selected FTP item to download list"""
        selected_items = self.ftp_tree.selection()
        for item in selected_items:
            item_tags = self.ftp_tree.item(item, "tags")
            item_text = self.ftp_tree.item(item, "text")
            
            if "file" in item_tags:
                file_path = os.path.join(self.current_directory, item_text)
                self.add_to_selected(file_path)
    
    def add_to_selected(self, file_path):
        """Add a file to the selected files list"""
        # Check if already in list
        for item in self.selected_tree.get_children():
            if self.selected_tree.item(item, "values")[0] == file_path:
                return
                
        # Add to list
        self.selected_tree.insert("", tk.END, values=(file_path,))
        self.selected_files.append(file_path)
        self.set_status(f"Added {file_path} to selected files")
    
    def browse_output(self):
        """Browse for output directory"""
        output_dir = filedialog.askdirectory(title="Select Download Directory")
        if output_dir:
            self.output_path_var.set(output_dir)
    
    def start_downloads(self):
        """Start downloading selected files"""
        output_dir = self.output_path_var.get()
        if not output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
            
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Cannot create output directory: {str(e)}")
                return
                
        # Get all files with checkboxes selected
        files_to_download = []
        for item in self.selected_tree.get_children():
            values = self.selected_tree.item(item, "values")
            if values[0] == "✓":  # Checkbox is checked
                file_path = values[1]  # Path is in the second column
                files_to_download.append(file_path)
        
        if not files_to_download:
            messagebox.showinfo("No Selection", "Please select files to download")
            return
            
        logger.info(f"Starting downloads for {len(files_to_download)} files")
        
        # Allow downloads to proceed
        self.paused.set()
        
        # Enqueue files for download
        with self.lock:
            for file_path in files_to_download:
                # Initialize file status if not exists
                if file_path not in self.file_status:
                    self.file_status[file_path] = {
                        'size': 'Unknown',
                        'progress': '0%',
                        'speed': '',
                        'eta': '',
                        'status': 'Queued',
                        'start_time': None,
                        'downloaded': 0,
                        'total_size': 0,
                        'last_update_time': time.time(),
                        'last_update_size': 0
                    }
                else:
                    # Reset if it's not currently downloading
                    current_status = self.file_status[file_path]['status']
                    if current_status not in ['Downloading', 'Complete']:
                        self.file_status[file_path]['status'] = 'Queued'
                
                # Only add to queue if not already being downloaded
                if file_path not in self.active_downloads:
                    self.download_queue.put(file_path)
                
                # Update UI
                self.update_file_status(file_path)
        
        self.set_status(f"Started downloading {len(files_to_download)} files")

    def pause_downloads(self):
        """Pause all active downloads"""
        logger.info("Pausing all downloads")
        self.paused.clear()  # Clear the flag to signal workers to pause
        
        # Update status of downloading files to paused - use a small delay to let
        # worker threads notice the pause flag
        self.root.after(50, self._update_paused_statuses)
    
    def _update_paused_statuses(self):
        """Update status of downloading files to paused"""
        with self.lock:
            for file_path, status in self.file_status.items():
                if status['status'] == 'Downloading':
                    status['status'] = 'Paused'
                    self.update_file_status(file_path)
        
        self.set_status("Downloads paused")
    
    def resume_downloads(self):
        """Resume paused downloads"""
        logger.info("Resuming downloads")
        self.paused.set()  # Set the flag to allow downloads to proceed
        
        # Update status of paused files to queued - use a small delay to let
        # worker threads notice the resume flag
        self.root.after(50, self._update_resumed_statuses)
    
    def _update_resumed_statuses(self):
        """Update status of paused files to queued"""
        with self.lock:
            for file_path, status in self.file_status.items():
                if status['status'] == 'Paused':
                    status['status'] = 'Queued'
                    
                    # Re-add to download queue if not already in active downloads
                    if file_path not in self.active_downloads:
                        self.download_queue.put(file_path)
                    
                    self.update_file_status(file_path)
        
        self.set_status("Downloads resumed")
    
    def download_worker(self):
        """Worker thread for downloading files"""
        logger.info(f"Download worker started - Thread {threading.get_ident()}")
        
        while True:
            try:
                # Check if the application is closing
                if not hasattr(self, 'root') or not self.root.winfo_exists():
                    logger.info("Application closing, worker exiting")
                    break
                
                # Check if downloads are paused
                if not self.paused.is_set():
                    time.sleep(0.5)
                    continue
                
                # Get a file from the queue
                try:
                    file_path = self.download_queue.get(timeout=1.0)
                except queue.Empty:
                    # No files in queue, wait and try again
                    time.sleep(0.5)
                    continue
                
                # Mark as being downloaded
                with self.lock:
                    if file_path in self.active_downloads:
                        # Already being downloaded by another worker
                        self.download_queue.task_done()
                        continue
                    
                    # Update status
                    self.active_downloads.add(file_path)
                    if file_path in self.file_status:
                        self.file_status[file_path]['status'] = 'Initializing'
                        self.file_status[file_path]['start_time'] = time.time()
                    else:
                        self.file_status[file_path] = {
                            'size': 'Unknown',
                            'progress': '0%',
                            'speed': '',
                            'eta': '',
                            'status': 'Initializing',
                            'start_time': time.time(),
                            'downloaded': 0,
                            'total_size': 0,
                            'last_update_time': time.time(),
                            'last_update_size': 0
                        }
                
                # Update UI
                self.update_file_status(file_path)
                
                # Download the file
                try:
                    success = self.download_file(file_path)
                    if success:
                        logger.info(f"Download completed: {file_path}")
                    else:
                        logger.error(f"Download failed: {file_path}")
                except Exception as e:
                    logger.error(f"Error downloading {file_path}: {str(e)}")
                    with self.lock:
                        if file_path in self.file_status:
                            self.file_status[file_path]['status'] = f'Error: {str(e)}'
                    
                    self.update_file_status(file_path)
                
                # Mark as no longer being downloaded
                with self.lock:
                    self.active_downloads.discard(file_path)
                    self.download_queue.task_done()
            
            except Exception as e:
                logger.error(f"Error in download worker: {str(e)}")
                time.sleep(1)  # Avoid tight error loop
    
    def download_file(self, file_path):
        """Download a single file with progress tracking"""
        try:
            output_dir = self.output_path_var.get()
            if not output_dir:
                logger.error("No output directory set")
                return False
            
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get file name from path
            file_name = os.path.basename(file_path)
            local_path = os.path.join(output_dir, file_name)
            
            # Check if file already exists and is complete
            if os.path.exists(local_path):
                existing_size = os.path.getsize(local_path)
                file_info = self.file_status.get(file_path, {})
                total_size = file_info.get('total_size', 0)
                
                if total_size > 0 and existing_size == total_size:
                    # File is already complete
                    with self.lock:
                        self.file_status[file_path] = {
                            'size': self.format_size(total_size),
                            'progress': '100%',
                            'speed': '',
                            'eta': '',
                            'status': 'Complete',
                            'total_size': total_size,
                            'downloaded': total_size
                        }
                    self.update_file_status(file_path)
                    return True
            
            # Connect to FTP
            ftp = ftplib.FTP(FTP_HOST)
            ftp.login()
            
            # Update status to downloading
            with self.lock:
                if file_path in self.file_status:
                    self.file_status[file_path]['status'] = 'Downloading'
                    self.update_file_status(file_path)
            
            # Get file size if not known
            try:
                ftp.voidcmd('TYPE I')  # Binary mode
                total_size = ftp.size(file_path)
                
                with self.lock:
                    if file_path in self.file_status:
                        self.file_status[file_path]['total_size'] = total_size
                        self.file_status[file_path]['size'] = self.format_size(total_size)
                        self.update_file_status(file_path)
            except:
                logger.warning(f"Could not determine size for {file_path}")
                total_size = 0
            
            # Prepare for download with progress tracking
            downloaded = 0
            start_time = time.time()
            last_update_time = start_time
            
            # Open local file for writing
            with open(local_path, 'wb') as local_file:
                # Define callback to track progress
                def callback(data):
                    nonlocal downloaded, last_update_time
                    
                    # Write data
                    local_file.write(data)
                    
                    # Update progress
                    downloaded += len(data)
                    
                    # Calculate speed and ETA
                    current_time = time.time()
                    time_diff = current_time - last_update_time
                    
                    # Only update UI every 0.5 seconds to avoid overhead
                    if time_diff >= 0.5:
                        with self.lock:
                            if file_path in self.file_status:
                                # Calculate speed (bytes per second)
                                size_diff = downloaded - self.file_status[file_path].get('last_update_size', 0)
                                speed = size_diff / time_diff if time_diff > 0 else 0
                                
                                # Calculate progress percentage
                                if total_size > 0:
                                    progress = min(100, (downloaded / total_size) * 100)
                                    progress_str = f"{progress:.1f}%"
                                else:
                                    progress_str = "Unknown"
                                
                                # Calculate ETA
                                if speed > 0 and total_size > 0:
                                    remaining_bytes = total_size - downloaded
                                    eta_seconds = remaining_bytes / speed
                                    eta = self.format_time(eta_seconds)
                                else:
                                    eta = "Unknown"
                                
                                # Update status
                                self.file_status[file_path].update({
                                    'downloaded': downloaded,
                                    'progress': progress_str,
                                    'speed': self.format_speed(speed),
                                    'eta': eta,
                                    'last_update_time': current_time,
                                    'last_update_size': downloaded
                                })
                                
                                # Check if download should be paused
                                if not self.paused.is_set():
                                    self.file_status[file_path]['status'] = 'Paused'
                                    raise Exception("Download paused")
                        
                        # Update UI
                        self.update_file_status(file_path)
                        last_update_time = current_time
                
                # Start download with progress tracking
                try:
                    ftp.retrbinary(f'RETR {file_path}', callback)
                    
                    # Verify download size
                    if total_size > 0 and downloaded != total_size:
                        logger.warning(f"Download size mismatch: {downloaded} vs expected {total_size}")
                    
                    # Mark as complete
                    with self.lock:
                        if file_path in self.file_status:
                            self.file_status[file_path].update({
                                'status': 'Complete',
                                'progress': '100%',
                                'speed': '',
                                'eta': '',
                                'downloaded': downloaded,
                                'total_size': downloaded if total_size == 0 else total_size
                            })
                    
                    self.update_file_status(file_path)
                    
                    # Extract project info for organization
                    self.extract_project_info(file_path, local_path)
                    
                    return True
                
                except Exception as e:
                    # If paused, return but don't mark as error
                    if str(e) == "Download paused":
                        logger.info(f"Download paused: {file_path}")
                        return False
                    
                    logger.error(f"Download error: {str(e)}")
                    
                    with self.lock:
                        if file_path in self.file_status:
                            self.file_status[file_path]['status'] = f'Error: {str(e)}'
                    
                    self.update_file_status(file_path)
                    return False
            
        except Exception as e:
            logger.error(f"Error downloading {file_path}: {str(e)}")
            
            with self.lock:
                if file_path in self.file_status:
                    self.file_status[file_path]['status'] = f'Error: {str(e)}'
            
            self.update_file_status(file_path)
            return False
        finally:
            # Close FTP connection
            try:
                ftp.quit()
            except:
                pass
    
    def update_file_status(self, file_path):
        """Update the UI for a file's status"""
        # This needs to be thread-safe by using after method
        def do_update():
            try:
                # Find the item in the tree view
                item_found = False
                for item in self.selected_tree.get_children():
                    values = self.selected_tree.item(item, "values")
                    if values[1] == file_path:  # Path is the second column
                        # Get status
                        status = self.file_status.get(file_path, {})
                        
                        # Update values
                        current_values = list(values)
                        current_values[2] = status.get('size', 'Unknown')
                        current_values[3] = status.get('progress', '0%')
                        current_values[4] = status.get('speed', '')
                        current_values[5] = status.get('eta', '')
                        current_values[6] = status.get('status', 'Ready')
                        
                        # Apply special formatting based on status
                        file_status = status.get('status', '')
                        tag = None
                        
                        if file_status == 'Complete':
                            tag = 'complete'
                        elif file_status == 'Downloading':
                            tag = 'downloading'
                        elif file_status == 'Paused':
                            tag = 'paused'
                        elif file_status.startswith('Error'):
                            tag = 'error'
                        
                        # Update the item
                        self.selected_tree.item(item, values=current_values, tags=(tag,) if tag else ())
                        item_found = True
                        break
                
                # If the item wasn't found, it might be because we're filtering by project
                # We'll still update the status dictionary for when the item becomes visible
                if not item_found:
                    if file_path not in self.file_status:
                        return
            except Exception as e:
                logger.error(f"Error updating file status: {str(e)}")
        
        # Schedule the update on the main thread
        if threading.current_thread() is threading.main_thread():
            do_update()
        else:
            self.root.after(0, do_update)
    
    def extract_project_info(self, file_path, local_path):
        """Extract project information from downloaded file and organize by project"""
        try:
            # Simple project extraction based on path components
            # Customize this based on your actual naming conventions
            path_parts = file_path.split('/')
            
            # Use different strategies to identify projects:
            
            # Strategy 1: Use the dataset name as the project
            if len(path_parts) >= 4:  # /elevation/LIDAR/dataset_name/file.las
                project = path_parts[3]  # Dataset name
            else:
                # Fallback: Use filename pattern
                filename = os.path.basename(file_path)
                name_parts = filename.split('_')
                
                if len(name_parts) > 1:
                    # Try to extract a meaningful project name
                    # For example, file names like "County_Monroe_2017_1234.las"
                    if "County" in filename:
                        # Find the county name
                        county_idx = name_parts.index("County") if "County" in name_parts else -1
                        if county_idx >= 0 and county_idx + 1 < len(name_parts):
                            project = f"County_{name_parts[county_idx+1]}"
                        else:
                            project = "Unknown_County"
                    elif any(x in filename for x in ["FEMA", "NYSDEC", "NYSGPO"]):
                        # Extract agency name
                        for prefix in ["FEMA", "NYSDEC", "NYSGPO"]:
                            if prefix in filename:
                                parts = filename.split(prefix)
                                if len(parts) > 1:
                                    project = f"{prefix}{parts[1].split('_')[0]}"
                                    break
                        else:
                            project = "Unknown_Agency"
                    else:
                        # Last resort: first part of filename
                        project = name_parts[0]
                else:
                    project = "Unknown"
            
            # Store in projects dictionary
            if project not in self.projects:
                self.projects[project] = []
            
            if file_path not in self.projects[project]:
                self.projects[project].append(file_path)
            
            # Update the project dropdown if needed
            if project not in self.project_combo["values"]:
                projects = list(self.project_combo["values"])
                projects.append(project)
                self.project_combo["values"] = projects
            
            logger.info(f"Added file to project '{project}': {file_path}")
            
        except Exception as e:
            logger.error(f"Error extracting project info: {str(e)}")
    
    def format_size(self, size_in_bytes):
        """Format file size in human-readable format"""
        if not size_in_bytes:
            return "Unknown"
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024
        return f"{size_in_bytes:.2f} TB"
    
    def format_speed(self, bytes_per_second):
        """Format download speed in human-readable format"""
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} B/s"
        elif bytes_per_second < 1024 * 1024:
            return f"{bytes_per_second/1024:.1f} KB/s"
        else:
            return f"{bytes_per_second/(1024*1024):.1f} MB/s"
    
    def format_time(self, seconds):
        """Format time in human-readable format"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds%3600)/60)
            return f"{hours}h {minutes}m"

    def on_project_selected(self, event):
        """Handle project selection"""
        project = self.current_project.get()
        if project:
            self.filter_files_by_project(project)
            
    def filter_files_by_project(self, project):
        """Show only files from the selected project that intersect with the polygon"""
        # Clear current view
        for item in self.selected_tree.get_children():
            self.selected_tree.delete(item)
            
        # If project is valid, show its files
        if project in self.projects:
            # Count files for status reporting
            total_files = len(self.projects[project])
            intersecting_files = 0
            
            for file_path, file_box in self.projects[project]:
                # Check if file intersects with polygon
                if self.file_status.get(file_path, {}).get('intersects_polygon', False):
                    intersecting_files += 1
                    
                    # Get file status if it exists
                    status_info = self.file_status.get(file_path, {
                        'size': 'Unknown',
                        'progress': '0%',
                        'speed': '',
                        'eta': '',
                        'status': 'Ready'
                    })
                    
                    # Add to tree view
                    self.selected_tree.insert("", "end", values=(
                        "",  # Checkbox
                        file_path,
                        status_info['size'],
                        status_info['progress'],
                        status_info['speed'],
                        status_info['eta'],
                        status_info['status']
                    ))
                    
            # Update status
            self.set_status(f"Showing {intersecting_files} files (of {total_files} total) for project: {project}")
            
            # Make sure this project's polygons are visible
            if project in self.project_visibility:
                if not self.project_visibility[project].get():
                    # Turn on visibility
                    self.project_visibility[project].set(True)
                    self.toggle_project_visibility(project)

    def select_all_project_files(self):
        """Select all files in the current project that intersect with polygon"""
        project = self.current_project.get()
        if not project:
            messagebox.showinfo("No Project", "Please select a project first")
            return
            
        # Count variables for status reporting
        selected_count = 0
        
        # Set all checkboxes for the current view (which already only shows intersecting files)
        for item in self.selected_tree.get_children():
            current_values = list(self.selected_tree.item(item, "values"))
            current_values[0] = "✓"  # Check the box
            self.selected_tree.item(item, values=current_values)
            self.selected_checkboxes.add(item)
            selected_count += 1
            
        self.set_status(f"Selected {selected_count} files from project: {project}")

    def deselect_all_files(self):
        """Deselect all files"""
        # Uncheck all boxes
        for item in self.selected_tree.get_children():
            current_values = list(self.selected_tree.item(item, "values"))
            current_values[0] = ""  # Uncheck the box
            self.selected_tree.item(item, values=current_values)
            
        # Clear selection tracking
        self.selected_checkboxes.clear()
        self.set_status("Deselected all files")

    def on_checkbox_click(self, event):
        """Handle click in the checkbox column"""
        region = self.selected_tree.identify("region", event.x, event.y)
        column = self.selected_tree.identify_column(event.x)
        
        if region == "cell" and column == "#1":  # Checkbox column
            item = self.selected_tree.identify_row(event.y)
            if item:
                # Toggle checkbox
                current_values = list(self.selected_tree.item(item, "values"))
                current_values[0] = "✓" if current_values[0] != "✓" else ""
                self.selected_tree.item(item, values=current_values)
                
                # Update selection set
                if current_values[0] == "✓":
                    self.selected_checkboxes.add(item)
                else:
                    self.selected_checkboxes.discard(item)
                
                logger.debug(f"Selected items: {len(self.selected_checkboxes)}")
                
    def clear_completed(self):
        """Remove completed downloads from the list"""
        completed_items = []
        for item in self.selected_tree.get_children():
            values = self.selected_tree.item(item, "values")
            if values and values[6] == "Complete":
                completed_items.append(item)
                
        for item in completed_items:
            self.selected_tree.delete(item)
            
        self.set_status(f"Removed {len(completed_items)} completed downloads")

    def start_drawing_mode(self):
        """Enable/Disable polygon drawing mode using canvas click events."""
        if self.draw_button.cget('text') == "Start Drawing":
            # Clear previous drawing before starting a new one
            self.clear_drawing()
            # Start drawing mode
            self.drawing_polygon = True
            self.polygon_points = []
            self.polygon_markers = []
            self.draw_button.config(text="Finish Drawing")
            
            # Bind canvas clicks for adding points
            self.map_widget.canvas.bind("<Button-1>", self.add_polygon_point)
            self.map_widget.canvas.bind("<Button-3>", self.finish_polygon)  # Right-click to finish
            
            self.set_status("Drawing mode enabled. Left-click to add points, right-click to finish.")
        else: # Finish Drawing
            self.finish_polygon(None)  # None is passed as the event

    def add_polygon_point(self, event):
        """Add a point to the polygon at the clicked location."""
        if not self.drawing_polygon:
            return
            
        # Convert canvas x,y to latitude, longitude
        lat, lon = self.map_widget.convert_canvas_coords_to_decimal_coords(event.x, event.y)
        
        # Add to points list
        self.polygon_points.append((lat, lon))
        
        # Add a marker at the point
        marker = self.map_widget.set_marker(lat, lon, text=f"{len(self.polygon_points)}")
        self.polygon_markers.append(marker)
        
        # Draw or update the path between points
        self.update_polygon_path()
        
        self.set_status(f"Added point {len(self.polygon_points)} at {lat:.6f}, {lon:.6f}")

    def update_polygon_path(self):
        """Update the path connecting the polygon points."""
        # Need at least 2 points for a path
        if len(self.polygon_points) < 2:
            return
            
        # Delete existing path if any
        if self.polygon_path:
            self.polygon_path.delete()
            
        # Create a new path between all points (including closing the loop if more than 2 points)
        if len(self.polygon_points) > 2:
            # Make a closed polygon by including the first point at the end
            path_points = self.polygon_points + [self.polygon_points[0]]
        else:
            # Just a line for 2 points
            path_points = self.polygon_points
            
        self.polygon_path = self.map_widget.set_path(path_points)

    def finish_polygon(self, event):
        """Finish the polygon drawing and create the Shapely polygon."""
        if not self.drawing_polygon or len(self.polygon_points) < 3:
            if self.drawing_polygon:
                messagebox.showwarning("Drawing", "Need at least 3 points to create a polygon.")
                self.set_status("Drawing cancelled - at least 3 points required.")
            
            # Reset drawing mode but keep any points for further editing
            self.drawing_polygon = False
            self.draw_button.config(text="Start Drawing")
            self.map_widget.canvas.unbind("<Button-1>")
            self.map_widget.canvas.unbind("<Button-3>")
            return
            
        # We have at least 3 points
        self.drawing_polygon = False
        
        # Create a Shapely polygon - Converting (lat, lon) to (lon, lat) for Shapely
        coords_lon_lat = [(lon, lat) for lat, lon in self.polygon_points]
        try:
            self.drawn_polygon_widget = Polygon(coords_lon_lat)
            self.set_status(f"Polygon created with {len(self.polygon_points)} vertices. Ready for Find LiDAR Files.")
        except Exception as e:
            self.drawn_polygon_widget = None
            messagebox.showerror("Drawing Error", f"Could not create polygon: {e}")
            self.set_status(f"Error creating polygon: {e}")
            
        # Reset UI
        self.draw_button.config(text="Start Drawing")
        self.map_widget.canvas.unbind("<Button-1>")
        self.map_widget.canvas.unbind("<Button-3>")

    def clear_drawing(self):
        """Clear any drawings from the map widget."""
        # Remove all markers for polygon points
        for marker in self.polygon_markers:
            marker.delete()
        self.polygon_markers = []
        
        # Remove the path
        if self.polygon_path:
            self.polygon_path.delete()
            self.polygon_path = None
            
        # Reset variables
        self.polygon_points = []
        self.drawn_polygon_widget = None
        self.drawing_polygon = False
        
        # Ensure Start/Finish button is reset
        self.draw_button.config(text="Start Drawing")
        
        # Unbind events if needed
        try:
            self.map_widget.canvas.unbind("<Button-1>")
            self.map_widget.canvas.unbind("<Button-3>")
        except:
            pass
            
        self.set_status("Map drawing cleared.")
    
    def search_location(self):
        """Search for a location using custom geocoding and center the map."""
        search_term = self.search_var.get()
        if not search_term:
            self.set_status("Please enter a search term (address, place, or lat,lon).")
            return

        # First, check if the search term looks like coordinates
        # Format: "latitude, longitude" or "latitude longitude"
        coords = None
        search_term = search_term.strip()
        
        # Try to parse as coordinates first (either comma or space separated)
        for separator in [',', ' ']:
            if separator in search_term:
                try:
                    parts = search_term.split(separator)
                    if len(parts) >= 2:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        if -90 <= lat <= 90 and -180 <= lon <= 180:
                            coords = (lat, lon)
                            break
                except ValueError:
                    # Not coordinates, continue to geocoding
                    pass
        
        # If not coordinates, use geocoding
        if coords is None:
            self.set_status(f"Searching for '{search_term}'...")
            coords = geocode_address(search_term)
            
        # Use the coordinates if found
        if coords:
            lat, lon = coords
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(12)  # Reasonable zoom level for found locations
            
            # Add a marker at the location
            # Remove any previous markers first
            for marker in self.map_widget.canvas_marker_list:
                marker.delete()
            
            marker = self.map_widget.set_marker(lat, lon, text=search_term)
            
            self.set_status(f"Map centered on '{search_term}' at {lat:.4f}, {lon:.4f}")
        else:
            self.set_status(f"Could not find location: '{search_term}'.")
            messagebox.showwarning("Search Failed", f"Could not find location: '{search_term}'")

    def find_lidar_files(self):
        """Find LiDAR files that intersect with the drawn polygon by searching XML metadata."""
        if not self.drawn_polygon_widget:
            messagebox.showerror("Error", "Please draw and finish a polygon first using Start/Finish Drawing.")
            return
        
        # Clean up any existing polygons before starting new search
        self.clear_lidar_polygons()
        
        # Clear previous project data
        self.projects = {}
        self.project_visibility = {}
        
        self.set_status("Searching for LiDAR files that intersect with drawn area...")
        
        # Start a thread to search for intersecting LiDAR datasets
        threading.Thread(target=self.search_lidar_files_thread).start()

    def search_lidar_files_thread(self):
        """Search for individual LiDAR files that intersect with the drawn polygon in a separate thread."""
        try:
            # Show status update
            self.root.after(0, lambda: self.set_status("Loading LiDAR catalog..."))
            
            # Load our comprehensive catalog instead of scanning the FTP server
            try:
                catalog = self.load_lidar_catalog()
                if not catalog:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Could not load LiDAR catalog file. Please run extract_all_lidar_files.py first."))
                    self.root.after(0, lambda: self.set_status("Error: No LiDAR catalog found. Run extract_all_lidar_files.py first."))
                    return
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Could not load LiDAR catalog: {str(e)}"))
                self.root.after(0, lambda: self.set_status(f"Error loading LiDAR catalog: {str(e)}"))
                return
            
            # PASS 1: Find datasets that intersect with our polygon
            self.root.after(0, lambda: self.set_status(f"PASS 1: Checking datasets for intersection..."))
            
            total_datasets = len(catalog["datasets"])
            matching_datasets = []
            
            # Track progress for large catalogs
            progress_interval = max(1, min(20, total_datasets // 20))  # Update every 5% or so
            
            for i, (dataset_name, dataset_info) in enumerate(catalog["datasets"].items()):
                # Periodically update status for large catalogs
                if i % progress_interval == 0:
                    self.root.after(0, lambda i=i, t=total_datasets: 
                                  self.set_status(f"PASS 1: Checking dataset {i}/{t}..."))
                
                # Try to find dataset boundary information
                dataset_box = self.get_dataset_boundary_from_catalog(dataset_info)
                
                if dataset_box and dataset_box.intersects(self.drawn_polygon_widget):
                    matching_datasets.append((dataset_name, dataset_info, dataset_box))
            
            # Update status with number of matching datasets
            self.root.after(0, lambda: self.set_status(f"PASS 1 complete: Found {len(matching_datasets)} datasets intersecting with polygon"))
            
            if not matching_datasets:
                self.root.after(0, lambda: messagebox.showinfo("Search Results", "No LiDAR datasets found in the specified area."))
                return
            
            # PASS 2: Find individual files within matching datasets that intersect with the polygon
            self.root.after(0, lambda: self.set_status(f"PASS 2: Finding LiDAR files in {len(matching_datasets)} datasets..."))
            
            # Prepare to collect matching files
            matching_files = []  # Store files that intersect with polygon
            total_files_checked = 0
            
            # Display progress updates periodically
            last_update_time = time.time()
            
            for idx, (dataset_name, dataset_info, dataset_box) in enumerate(matching_datasets):
                try:
                    # Update status periodically to avoid UI freezing
                    current_time = time.time()
                    if current_time - last_update_time > 0.5:  # Update at most twice per second
                        self.root.after(0, lambda d=dataset_name, i=idx+1, t=len(matching_datasets): 
                                      self.set_status(f"PASS 2: Checking files in dataset [{i}/{t}]: {d}..."))
                        last_update_time = current_time
                    
                    # Get all files in this dataset from our catalog
                    if "files" not in dataset_info:
                        logger.warning(f"No files found in dataset {dataset_name}")
                        continue
                        
                    files_to_check = dataset_info["files"]
                    total_files_checked += len(files_to_check)
                    
                    # For each file, check if it intersects with our polygon
                    for file_info in files_to_check:
                        try:
                            # Get file path
                            file_path = file_info["path"]
                            
                            # Try to get precise file boundary from catalog
                            file_box = self.get_file_boundary_from_catalog(file_info)
                            
                            # If we couldn't determine file boundary, use dataset boundary as approximation
                            if not file_box:
                                # Create a slightly smaller box to avoid including all files
                                # This helps in cases where we can't get precise boundaries
                                minx, miny, maxx, maxy = dataset_box.bounds
                                file_box = box(
                                    minx + (maxx-minx)*0.1*random.random(),  # Add some randomness for visual separation
                                    miny + (maxy-miny)*0.1*random.random(),
                                    maxx - (maxx-minx)*0.1*random.random(),
                                    maxy - (maxy-miny)*0.1*random.random()
                                )
                                logger.debug(f"Using approximated file boundary for {file_path}")
                            
                            # Check intersection with polygon
                            if file_box.intersects(self.drawn_polygon_widget):
                                # Store file with its boundary for display
                                matching_files.append((file_path, dataset_name, file_box))
                                
                                # Update UI periodically with progress
                                if len(matching_files) % 10 == 0 and (current_time - last_update_time > 0.5):
                                    self.root.after(0, lambda n=len(matching_files): 
                                                  self.set_status(f"Found {n} matching LiDAR files..."))
                                    last_update_time = current_time
                        except Exception as e:
                            logger.error(f"Error checking file {file_info.get('path', 'unknown')}: {e}")
                            continue
                        
                except Exception as e:
                    logger.error(f"Error scanning dataset {dataset_name}: {e}")
                    continue
            
            # Process results on the main thread
            self.root.after(0, lambda files=matching_files: self.process_matching_files(files))
            
        except Exception as e:
            logger.error(f"Search thread error: {e}")
            self.root.after(0, lambda: self.set_status(f"Error in search: {e}"))
            self.root.after(0, lambda: messagebox.showerror("Error", f"Error searching LiDAR files: {e}"))

    def load_lidar_catalog(self):
        """Load the comprehensive LiDAR catalog file"""
        try:
            # Check if catalog file exists
            if not os.path.exists(CATALOG_FILE):
                logger.error(f"Catalog file {CATALOG_FILE} not found")
                return None
                
            # Load the catalog
            with open(CATALOG_FILE, 'r') as f:
                catalog = json.load(f)
                
            # Basic validation
            if not isinstance(catalog, dict) or "datasets" not in catalog:
                logger.error(f"Invalid catalog format in {CATALOG_FILE}")
                return None
                
            logger.info(f"Loaded LiDAR catalog with {len(catalog['datasets'])} datasets")
            return catalog
        except Exception as e:
            logger.error(f"Error loading LiDAR catalog: {e}")
            return None

    def get_dataset_boundary_from_catalog(self, dataset_info):
        """Extract dataset boundary from catalog information"""
        try:
            # First check if there's an explicit boundary
            if "boundary" in dataset_info:
                bounds = dataset_info["boundary"]
                
                # Handle different formats of boundary data
                if "min_x" in bounds and "min_y" in bounds and "max_x" in bounds and "max_y" in bounds:
                    # Simple bounding box with min/max values
                    return box(
                        float(bounds["min_x"]), 
                        float(bounds["min_y"]),
                        float(bounds["max_x"]), 
                        float(bounds["max_y"])
                    )
                elif "west" in bounds and "south" in bounds and "east" in bounds and "north" in bounds:
                    # WGS84 format
                    return box(
                        float(bounds["west"]), 
                        float(bounds["south"]),
                        float(bounds["east"]), 
                        float(bounds["north"])
                    )
                    
            # If no explicit boundary, try to compute from files
            if "files" in dataset_info and dataset_info["files"]:
                # Get boundaries from all files that have them
                file_boxes = []
                for file_info in dataset_info["files"]:
                    file_box = self.get_file_boundary_from_catalog(file_info)
                    if file_box:
                        file_boxes.append(file_box)
                        
                if file_boxes:
                    # Compute union of all file boxes
                    union_box = file_boxes[0]
                    for box in file_boxes[1:]:
                        union_box = union_box.union(box)
                    return union_box
            
            # Fallback: create a generic box in NY state if we can't determine boundary
            logger.warning(f"Could not determine boundary for dataset {dataset_info.get('name', 'unknown')}")
            # This is a very rough approximation of NY state
            return box(-79.8, 40.5, -71.8, 45.0)
            
        except Exception as e:
            logger.error(f"Error getting dataset boundary: {e}")
            return None

    def get_file_boundary_from_catalog(self, file_info):
        """Extract file boundary from catalog information"""
        try:
            # Check if file has header info with bounds
            if "header_info" in file_info and file_info["header_info"].get("found", False):
                header_info = file_info["header_info"]
                
                # Check for different formats of boundary data
                if "bounds" in header_info and header_info["bounds"]:
                    bounds = header_info["bounds"]
                    if len(bounds) >= 4:
                        return box(bounds[0], bounds[1], bounds[2], bounds[3])
                        
                elif "min_x" in header_info and "min_y" in header_info and "max_x" in header_info and "max_y" in header_info:
                    return box(
                        float(header_info["min_x"]), 
                        float(header_info["min_y"]),
                        float(header_info["max_x"]), 
                        float(header_info["max_y"])
                    )
            
            # If header info doesn't have bounds, try to extract from filename
            file_path = file_info.get("path", "")
            if file_path:
                filename = os.path.basename(file_path)
                boundary = self.get_file_boundary(file_path, None)  # Use existing filename parsing logic
                if boundary:
                    return boundary
            
            # No boundary information available
            return None
            
        except Exception as e:
            logger.error(f"Error getting file boundary from catalog: {e}")
            return None

    def get_file_boundary(self, file_path, dataset_name):
        """Determine the boundary of a LAS file based on filename or metadata."""
        try:
            # Option 1: Extract coordinates from filename if it follows a pattern
            # Common patterns: XXXXXX_YYYYYY.las or UTM_X_Y.las or 18XXX_YYY.las
            filename = os.path.basename(file_path)
            basename = os.path.splitext(filename)[0]
            
            # Try to determine file boundaries from the filename
            # This depends on naming conventions which vary by dataset
            
            # Pattern 1: EPSG:32618 UTM coordinates like 18TWM580935.las
            # Where 580935 might be easting_northing
            utm_pattern = r'(\d{2})T?([A-Z]{2,3})(\d{3,6})(\d{3,6})'
            match = re.search(utm_pattern, basename)
            if match:
                # Approximated box (this would need refinement for production)
                zone, square, easting, northing = match.groups()
                e = int(easting) * 1000
                n = int(northing) * 1000
                # Estimate a 1000m tile size
                tile_size = 1000
                logger.debug(f"UTM pattern match for {filename}: zone={zone}, square={square}, easting={easting}, northing={northing}")
                return box(e, n, e + tile_size, n + tile_size)
            
            # Pattern 2: Simple coordinates like 462000_4654500.las
            # Where 462000 is easting and 4654500 is northing
            coord_pattern = r'(\d{5,7})_(\d{5,7})'
            match = re.search(coord_pattern, basename)
            if match:
                easting, northing = match.groups()
                e = int(easting)
                n = int(northing)
                # Estimate a 1500m tile size
                tile_size = 1500
                logger.debug(f"Coordinate pattern match for {filename}: easting={easting}, northing={northing}")
                return box(e, n, e + tile_size, n + tile_size)
            
            # Pattern 3: Files with "tile" in name often have a grid index
            tile_pattern = r'tile(\d+)'
            match = re.search(tile_pattern, basename.lower())
            if match:
                # We don't have exact coordinates, but we can use dataset bounds
                # and approximate by dividing into a grid based on tile number
                if dataset_name:
                    dataset_box = self.get_dataset_boundary_from_catalog({"name": dataset_name})
                    if dataset_box:
                        # Assume tiles are numbered in a grid pattern
                        # This would need customization for specific datasets
                        tile_num = int(match.group(1))
                        
                        # Assume 10x10 grid for simplicity - this would need to be adapted
                        grid_size = 10
                        row = tile_num // grid_size
                        col = tile_num % grid_size
                        
                        # Get dataset bounds
                        minx, miny, maxx, maxy = dataset_box.bounds
                        
                        # Calculate cell size
                        cell_width = (maxx - minx) / grid_size
                        cell_height = (maxy - miny) / grid_size
                        
                        # Calculate tile bounds
                        tile_minx = minx + col * cell_width
                        tile_miny = miny + row * cell_height
                        tile_maxx = tile_minx + cell_width
                        tile_maxy = tile_miny + cell_height
                        
                        logger.debug(f"Tile pattern match for {filename}: tile={tile_num}, bounds=({tile_minx}, {tile_miny}, {tile_maxx}, {tile_maxy})")
                        return box(tile_minx, tile_miny, tile_maxx, tile_maxy)
            
            # Pattern 4: Files with numbers that look like coordinates
            # For example: file_418000_4668000.las
            coords_pattern = r'[_\-](\d{6})[\-_](\d{7})[_\-\.]'
            match = re.search(coords_pattern, filename)
            if match:
                easting, northing = match.groups()
                e = int(easting)
                n = int(northing)
                # Assume a standard tile size (adjust as needed)
                tile_size = 1000
                return box(e, n, e + tile_size, n + tile_size)
            
            # Pattern 5: Look for lat/lon values in decimal format
            # For example: tile_42.55_-76.23.las
            latlon_pattern = r'[-_](\d{1,2}\.\d+)[-_]([-]?\d{1,3}\.\d+)[-_\.]'
            match = re.search(latlon_pattern, filename)
            if match:
                lat, lon = match.groups()
                lat, lon = float(lat), float(lon)
                # Create a small box around this point (roughly 1km x 1km)
                delta = 0.01  # Approximately 1km at mid-latitudes
                return box(lon - delta/2, lat - delta/2, lon + delta/2, lat + delta/2)
            
            # If none of the patterns match, return None
            return None
            
        except Exception as e:
            logger.error(f"Error determining file boundary for {file_path}: {str(e)}")
            return None

    def process_matching_files(self, matching_files):
        """Process the list of matching files and display in UI."""
        if not matching_files:
            self.set_status("No LiDAR files found that intersect with your area of interest.")
            messagebox.showinfo("Search Results", "No intersecting LiDAR files found.")
            return
        
        # Clear previous selections and display
        for item in self.selected_tree.get_children():
            self.selected_tree.delete(item)
        
        # Reset selected files list
        self.selected_files = []
        
        # Clear existing polygons
        self.clear_lidar_polygons()
        
        # Organize files by project
        projects = {}
        for file_path, dataset_name, file_box in matching_files:
            # Add to projects dict
            if dataset_name not in projects:
                projects[dataset_name] = []
                
                # Assign a color for this project
                if dataset_name not in self.project_colors:
                    color_index = len(self.project_colors) % len(self.color_series)
                    self.project_colors[dataset_name] = self.color_series[color_index]
                    
                # Create visibility toggle for this project
                self.add_project_toggle(dataset_name, self.project_colors[dataset_name])
            
            projects[dataset_name].append((file_path, file_box))
            
            # Add to master list
            self.selected_files.append(file_path)
            
            # Store geometry info in file_status (for spatial filtering)
            if file_path not in self.file_status:
                self.file_status[file_path] = {
                    'size': 'Unknown',
                    'progress': '0%',
                    'speed': '',
                    'eta': '',
                    'status': 'Ready',
                    'intersects_polygon': True,  # These files already match the polygon
                    'bounding_box': file_box     # Store the bounding box for later reference
                }
            else:
                self.file_status[file_path]['intersects_polygon'] = True
                self.file_status[file_path]['bounding_box'] = file_box
                
            # Draw bounding box for this file
            try:
                # Convert shapely box to polygon points for drawing
                minx, miny, maxx, maxy = file_box.bounds
                polygon_points = [
                    (miny, minx),  # Bottom-left (note: we swap lat-lon order)
                    (miny, maxx),  # Bottom-right
                    (maxy, maxx),  # Top-right
                    (maxy, minx),  # Top-left
                    (miny, minx)   # Close the polygon
                ]
                
                # Draw polygon on map
                polygon = self.map_widget.set_polygon(
                    polygon_points,
                    fill_color="",
                    outline_color=self.project_colors[dataset_name],
                    border_width=2
                )
                
                # Store attributes on polygon object
                polygon.position_list = polygon_points
                polygon.outline_color = self.project_colors[dataset_name]
                polygon.project_name = dataset_name
                polygon.file_path = file_path
                
                # Store original polygon data for visibility toggling
                self.create_original_polygon_data(dataset_name, polygon_points, self.project_colors[dataset_name])
                
                # Add to tracking structures
                if dataset_name not in self.project_polygons:
                    self.project_polygons[dataset_name] = []
                
                self.lidar_polygons.append(polygon)
                self.project_polygons[dataset_name].append(polygon)
                
            except Exception as e:
                logger.error(f"Error drawing polygon for {file_path}: {e}")
        
        # Store projects in instance variable
        self.projects = projects
        
        # Update project dropdown
        self.project_combo['values'] = sorted(list(projects.keys()))
        if projects:
            self.current_project.set(list(projects.keys())[0])
            
        # Display files from first project
        if self.current_project.get():
            self.filter_files_by_project(self.current_project.get())
        else:
            # If no project selected, show all files
            for file_path, file_box in [item for items in projects.values() for item in items]:
                # Add to tree view
                self.selected_tree.insert("", "end", values=(
                    "",  # Checkbox
                    file_path,
                    self.file_status[file_path]['size'],
                    self.file_status[file_path]['progress'],
                    self.file_status[file_path]['speed'],
                    self.file_status[file_path]['eta'],
                    self.file_status[file_path]['status']
                ))
        
        # Update status
        total_files = len(matching_files)
        total_projects = len(projects)
        self.set_status(f"Found {total_files} LiDAR files in {total_projects} projects that intersect with your drawn area.")
        
        # Optional: Navigate to the directory of the first file in the FTP browser
        if matching_files:
            first_dir = os.path.dirname(matching_files[0][0])
            try:
                self.current_path_var.set(first_dir + "/")
                self.refresh_ftp()
            except:
                pass
    
    def set_status(self, message):
        """Set the status bar message"""
        self.status_var.set(message)
        self.root.update_idletasks()

    def start_download_workers(self):
        """Start download worker threads"""
        for _ in range(self.max_concurrent_downloads):
            thread = threading.Thread(target=self.download_worker, daemon=True)
            thread.start()
            logger.info(f"Started download worker thread")

    def toggle_project_visibility(self, project_name):
        """Toggle visibility of all polygon boundaries for a specific project"""
        try:
            # Get the current visibility state
            is_visible = self.project_visibility[project_name].get()
            logger.info(f"Toggling visibility for project {project_name} to {is_visible}")
            
            # Get current polygons for this project
            current_polygons = self.project_polygons.get(project_name, [])
            
            # Step 1: Delete all existing polygons for this project
            for polygon in current_polygons[:]:  # Create a copy to safely iterate
                try:
                    polygon.delete()  # Delete from map widget
                except Exception as e:
                    logger.error(f"Error deleting polygon: {e}")
            
            # Step 2: Clear tracking structures
            self.lidar_polygons = [p for p in self.lidar_polygons if p not in current_polygons]
            self.project_polygons[project_name] = []
            
            # Step 3: If visibility is ON, recreate the polygons
            if is_visible:
                # Get the original polygon data
                if project_name in self._original_polygon_data:
                    original_data = self._original_polygon_data[project_name]
                    logger.info(f"Recreating {len(original_data)} polygons for project {project_name}")
                    
                    # Create new polygons
                    new_polygons = []
                    for i, data in enumerate(original_data):
                        try:
                            # Extract polygon data
                            polygon_points = data['position_list']
                            color = data['outline_color']
                            
                            # Create polygon
                            if polygon_points and len(polygon_points) >= 3:
                                new_polygon = self.map_widget.set_polygon(
                                    polygon_points,
                                    fill_color="",
                                    outline_color=color,
                                    border_width=2
                                )
                                
                                # Store attributes
                                new_polygon.position_list = polygon_points
                                new_polygon.outline_color = color
                                new_polygon.project_name = project_name
                                
                                # Add to tracking
                                new_polygons.append(new_polygon)
                                self.lidar_polygons.append(new_polygon)
                        except Exception as e:
                            logger.error(f"Error recreating polygon: {e}")
                    
                    # Update tracking
                    self.project_polygons[project_name] = new_polygons
                    logger.info(f"Added {len(new_polygons)} polygons for project {project_name}")
            
            # Update status
            self.set_status(f"Project {project_name} visibility set to {is_visible}")
            
        except Exception as e:
            logger.error(f"Error toggling project visibility: {e}")

    def create_original_polygon_data(self, project_name, polygon_points, color):
        """Store original polygon data for later recreation when toggling visibility"""
        try:
            # Initialize project entry if needed
            if project_name not in self._original_polygon_data:
                self._original_polygon_data[project_name] = []
            
            # Create data structure with essential polygon info
            polygon_data = {
                'position_list': polygon_points,
                'outline_color': color
            }
            
            # Add to project's data list
            self._original_polygon_data[project_name].append(polygon_data)
            
            return True
        except Exception as e:
            logger.error(f"Error storing original polygon data: {e}")
            return False

    def clear_lidar_polygons(self):
        """Clear all LIDAR polygons from the map"""
        try:
            # Remove all polygons from the map
            if hasattr(self, 'lidar_polygons'):
                for polygon in self.lidar_polygons:
                    try:
                        polygon.delete()
                    except:
                        pass
                self.lidar_polygons = []
            
            # Clear project polygons
            if hasattr(self, 'project_polygons'):
                for project_name, polygons in self.project_polygons.items():
                    for polygon in polygons:
                        try:
                            polygon.delete()
                        except:
                            pass
                self.project_polygons = {}
            
            # Clear original polygon data
            self._original_polygon_data = {}
            
            # Clear project visibility toggles from UI
            if hasattr(self, 'legend_frame'):
                for widget in self.legend_frame.winfo_children():
                    widget.destroy()
            
            logger.info("LIDAR polygons cleared successfully")
        except Exception as e:
            logger.error(f"Error clearing LIDAR polygons: {e}")

    def add_project_toggle(self, project_name, color):
        """Add a toggle button for a project's visibility"""
        # Make sure we have a legend frame
        if not hasattr(self, 'legend_frame'):
            self.create_legend_frame()
        
        # Create frame for this project
        project_frame = ttk.Frame(self.legend_frame)
        project_frame.pack(fill='x', padx=5, pady=2)
        
        # Create visibility variable
        self.project_visibility[project_name] = tk.BooleanVar(value=True)
        
        # Add project label
        label = ttk.Label(
            project_frame,
            text=project_name,
            foreground=color
        )
        label.pack(side='left', padx=(0, 5))
        
        # Add visibility toggle button
        toggle_btn = ttk.Checkbutton(
            project_frame,
            text="Show Tiles",
            variable=self.project_visibility[project_name],
            command=lambda p=project_name: self.toggle_project_visibility(p)
        )
        toggle_btn.pack(side='right', padx=5)
        
        # Add files count label
        files_count = len(self.projects.get(project_name, []))
        count_label = ttk.Label(
            project_frame,
            text=f"Files: {files_count}"
        )
        count_label.pack(side='right', padx=5)
        
        return project_frame

    def create_legend_frame(self):
        """Create a frame for the legend showing project toggles"""
        # Create main legend frame if it doesn't exist
        if not hasattr(self, 'legend_frame'):
            self.legend_frame = ttk.LabelFrame(self.main_frame, text="Project Visibility")
            self.legend_frame.pack(fill='x', padx=10, pady=5, before=self.bottom_frame)
            
            # Add select/deselect all buttons
            button_frame = ttk.Frame(self.legend_frame)
            button_frame.pack(fill='x', padx=5, pady=2)
            
            ttk.Button(
                button_frame,
                text="Show All",
                command=self.show_all_projects
            ).pack(side='left', padx=5)
            
            ttk.Button(
                button_frame,
                text="Hide All",
                command=self.hide_all_projects
            ).pack(side='left', padx=5)

    def show_all_projects(self):
        """Show all projects by setting all visibility toggles to True"""
        for project_name, var in self.project_visibility.items():
            if not var.get():
                var.set(True)
                self.toggle_project_visibility(project_name)
        
        self.set_status("All projects visible")

    def hide_all_projects(self):
        """Hide all projects by setting all visibility toggles to False"""
        for project_name, var in self.project_visibility.items():
            if var.get():
                var.set(False)
                self.toggle_project_visibility(project_name)
        
        self.set_status("All projects hidden")

def main():
    root = tk.Tk()
    app = LiDARDownloader(root)
    root.mainloop()

if __name__ == "__main__":
    main()
