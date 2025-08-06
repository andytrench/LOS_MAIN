"""
AWS S3 Download Handler

This module provides a UI for downloading files from AWS S3 using the requester pays option.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import logging
import threading
import boto3
import time
from typing import List, Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

class AWSDownloadDialog:
    """Dialog for downloading files from AWS S3"""
    
    def __init__(self, parent, items, aws_credentials=None):
        """
        Initialize the AWS download dialog.
        
        Args:
            parent: Parent window
            items: List of items to download
            aws_credentials: Optional dictionary with AWS credentials
        """
        self.parent = parent
        self.items = items
        self.aws_credentials = aws_credentials or {}
        self.selected_items = []
        self.download_path = os.path.expanduser("~/Downloads/LIDAR")
        self.download_in_progress = False
        self.cancel_download = False
        
        # Create the dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("AWS S3 Download")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Create the UI
        self.create_ui()
    
    def create_ui(self):
        """Create the UI elements"""
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Info label
        info_text = (
            "These files will be downloaded directly from AWS S3 using the requester pays option.\n"
            "Standard AWS charges may apply. You will be billed for the data transfer costs."
        )
        info_label = ttk.Label(main_frame, text=info_text, wraplength=780, justify=tk.LEFT)
        info_label.pack(fill=tk.X, pady=(0, 10))
        
        # AWS credentials frame
        creds_frame = ttk.LabelFrame(main_frame, text="AWS Credentials", padding=10)
        creds_frame.pack(fill=tk.X, pady=(0, 10))
        
        # AWS Access Key ID
        ttk.Label(creds_frame, text="AWS Access Key ID:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.access_key_var = tk.StringVar(value=self.aws_credentials.get('AWS_ACCESS_KEY_ID', ''))
        ttk.Entry(creds_frame, textvariable=self.access_key_var, width=40).grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)
        
        # AWS Secret Access Key
        ttk.Label(creds_frame, text="AWS Secret Access Key:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.secret_key_var = tk.StringVar(value=self.aws_credentials.get('AWS_SECRET_ACCESS_KEY', ''))
        ttk.Entry(creds_frame, textvariable=self.secret_key_var, width=40, show="*").grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        
        # AWS Region
        ttk.Label(creds_frame, text="AWS Region:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.region_var = tk.StringVar(value=self.aws_credentials.get('AWS_REGION', 'us-west-2'))
        ttk.Entry(creds_frame, textvariable=self.region_var, width=40).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)
        
        # Configure grid columns
        creds_frame.columnconfigure(0, weight=0)
        creds_frame.columnconfigure(1, weight=1)
        
        # Download path frame
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(path_frame, text="Download Path:").pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar(value=self.download_path)
        path_entry = ttk.Entry(path_frame, textvariable=self.path_var, width=50)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        
        browse_button = ttk.Button(path_frame, text="Browse...", command=self.browse_path)
        browse_button.pack(side=tk.LEFT)
        
        # File list frame
        list_frame = ttk.LabelFrame(main_frame, text="Files to Download", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create file list with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.pack(fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_container)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Treeview for file list
        columns = ("select", "filename", "project", "size")
        self.file_list = ttk.Treeview(list_container, columns=columns, show="headings", selectmode="browse")
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Configure scrollbar
        scrollbar.config(command=self.file_list.yview)
        self.file_list.config(yscrollcommand=scrollbar.set)
        
        # Configure columns
        self.file_list.heading("select", text="Select")
        self.file_list.heading("filename", text="Filename")
        self.file_list.heading("project", text="Project")
        self.file_list.heading("size", text="Size")
        
        self.file_list.column("select", width=50, anchor=tk.CENTER)
        self.file_list.column("filename", width=300, anchor=tk.W)
        self.file_list.column("project", width=200, anchor=tk.W)
        self.file_list.column("size", width=100, anchor=tk.E)
        
        # Populate file list
        self.populate_file_list()
        
        # Bind click event to toggle selection
        self.file_list.bind("<ButtonRelease-1>", self.toggle_selection)
        
        # Selection buttons
        select_frame = ttk.Frame(main_frame)
        select_frame.pack(fill=tk.X, pady=(0, 10))
        
        select_all_button = ttk.Button(select_frame, text="Select All", command=self.select_all)
        select_all_button.pack(side=tk.LEFT, padx=(0, 5))
        
        deselect_all_button = ttk.Button(select_frame, text="Deselect All", command=self.deselect_all)
        deselect_all_button.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=(0, 5))
        
        # Status label
        self.status_var = tk.StringVar(value="Ready to download")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack(fill=tk.X, pady=(0, 10))
        
        # Buttons frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Download button
        self.download_button = ttk.Button(button_frame, text="Download Selected", command=self.start_download)
        self.download_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Cancel button
        self.cancel_button = ttk.Button(button_frame, text="Cancel Download", command=self.cancel_download_action, state=tk.DISABLED)
        self.cancel_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # Close button
        close_button = ttk.Button(button_frame, text="Close", command=self.close)
        close_button.pack(side=tk.RIGHT)
    
    def populate_file_list(self):
        """Populate the file list with items"""
        for i, item in enumerate(self.items):
            filename = item.get('title', 'Unknown')
            project = item.get('projectName', 'Unknown')
            size = item.get('sizeInBytes', 0)
            size_str = self.format_size(size)
            
            # Add to treeview
            item_id = self.file_list.insert("", tk.END, values=("☐", filename, project, size_str))
            
            # Store the item data with the item ID
            self.file_list.item(item_id, tags=(str(i),))
    
    def toggle_selection(self, event):
        """Toggle selection of a file"""
        # Get the item ID that was clicked
        item_id = self.file_list.identify_row(event.y)
        if not item_id:
            return
        
        # Get the column that was clicked
        col = self.file_list.identify_column(event.x)
        if col != "#1":  # Only toggle if the checkbox column was clicked
            return
        
        # Get current values
        values = list(self.file_list.item(item_id, "values"))
        
        # Toggle checkbox
        if values[0] == "☐":
            values[0] = "☑"
            self.selected_items.append(item_id)
        else:
            values[0] = "☐"
            if item_id in self.selected_items:
                self.selected_items.remove(item_id)
        
        # Update the item
        self.file_list.item(item_id, values=values)
        
        # Update status
        self.status_var.set(f"Selected {len(self.selected_items)} files")
    
    def select_all(self):
        """Select all files"""
        self.selected_items = []
        for item_id in self.file_list.get_children():
            values = list(self.file_list.item(item_id, "values"))
            values[0] = "☑"
            self.file_list.item(item_id, values=values)
            self.selected_items.append(item_id)
        
        # Update status
        self.status_var.set(f"Selected {len(self.selected_items)} files")
    
    def deselect_all(self):
        """Deselect all files"""
        for item_id in self.file_list.get_children():
            values = list(self.file_list.item(item_id, "values"))
            values[0] = "☐"
            self.file_list.item(item_id, values=values)
        
        self.selected_items = []
        
        # Update status
        self.status_var.set("No files selected")
    
    def browse_path(self):
        """Browse for download path"""
        path = filedialog.askdirectory(
            title="Select Download Directory",
            initialdir=self.download_path
        )
        if path:
            self.download_path = path
            self.path_var.set(path)
    
    def start_download(self):
        """Start downloading selected files"""
        if not self.selected_items:
            messagebox.showwarning("No Selection", "Please select files to download.")
            return
        
        # Get AWS credentials
        access_key = self.access_key_var.get().strip()
        secret_key = self.secret_key_var.get().strip()
        region = self.region_var.get().strip()
        
        if not access_key or not secret_key:
            messagebox.showwarning("Missing Credentials", "Please enter your AWS credentials.")
            return
        
        # Get download path
        download_path = self.path_var.get().strip()
        if not download_path:
            messagebox.showwarning("Missing Path", "Please enter a download path.")
            return
        
        # Create download path if it doesn't exist
        if not os.path.exists(download_path):
            try:
                os.makedirs(download_path)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create download directory: {str(e)}")
                return
        
        # Disable UI elements during download
        self.download_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.download_in_progress = True
        self.cancel_download = False
        
        # Start download thread
        threading.Thread(target=self.download_files, args=(access_key, secret_key, region, download_path), daemon=True).start()
    
    def download_files(self, access_key, secret_key, region, download_path):
        """Download selected files in a separate thread"""
        try:
            # Initialize S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region
            )
            
            # Get selected items
            selected_items = []
            for item_id in self.selected_items:
                item_idx = int(self.file_list.item(item_id, "tags")[0])
                if 0 <= item_idx < len(self.items):
                    selected_items.append(self.items[item_idx])
            
            total_files = len(selected_items)
            completed_files = 0
            failed_files = 0
            
            # Update status
            self.update_status(f"Downloading {total_files} files...", 0)
            
            # Download each file
            for i, item in enumerate(selected_items):
                if self.cancel_download:
                    self.update_status("Download cancelled", 0)
                    break
                
                try:
                    # Get file info
                    key = item.get('awsKey') or item.get('downloadURL', '').replace('s3://usgs-lidar/', '')
                    filename = item.get('title', 'Unknown')
                    project = item.get('projectName', 'Unknown')
                    
                    # Create project directory
                    project_dir = os.path.join(download_path, project)
                    if not os.path.exists(project_dir):
                        os.makedirs(project_dir)
                    
                    # Output path
                    output_path = os.path.join(project_dir, filename)
                    
                    # Update status
                    self.update_status(f"Downloading {i+1}/{total_files}: {filename}", (i / total_files) * 100)
                    
                    # Download file with requester pays
                    s3_client.download_file(
                        Bucket='usgs-lidar',
                        Key=key,
                        Filename=output_path,
                        ExtraArgs={'RequestPayer': 'requester'}
                    )
                    
                    completed_files += 1
                    
                    # Update item status in the list
                    self.dialog.after(0, lambda id=self.selected_items[i], status="✓": self.update_item_status(id, status))
                
                except Exception as e:
                    logger.error(f"Error downloading file {filename}: {str(e)}", exc_info=True)
                    failed_files += 1
                    
                    # Update item status in the list
                    self.dialog.after(0, lambda id=self.selected_items[i], status="✗": self.update_item_status(id, status))
            
            # Update final status
            if self.cancel_download:
                final_status = f"Download cancelled. Completed: {completed_files}, Failed: {failed_files}"
            else:
                final_status = f"Download complete. Completed: {completed_files}, Failed: {failed_files}"
            
            self.update_status(final_status, 100 if not self.cancel_download else 0)
            
            # Show completion message
            if not self.cancel_download:
                self.dialog.after(0, lambda: messagebox.showinfo("Download Complete", final_status))
        
        except Exception as e:
            logger.error(f"Error in download thread: {str(e)}", exc_info=True)
            self.update_status(f"Error: {str(e)}", 0)
            self.dialog.after(0, lambda: messagebox.showerror("Error", f"Download failed: {str(e)}"))
        
        finally:
            # Re-enable UI elements
            self.dialog.after(0, self.reset_ui)
    
    def update_item_status(self, item_id, status):
        """Update the status of an item in the file list"""
        values = list(self.file_list.item(item_id, "values"))
        values[0] = status
        self.file_list.item(item_id, values=values)
    
    def update_status(self, status, progress):
        """Update status and progress bar"""
        self.dialog.after(0, lambda: self.status_var.set(status))
        self.dialog.after(0, lambda: self.progress_var.set(progress))
    
    def reset_ui(self):
        """Reset UI elements after download"""
        self.download_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.download_in_progress = False
    
    def cancel_download_action(self):
        """Cancel the download"""
        if self.download_in_progress:
            self.cancel_download = True
            self.status_var.set("Cancelling download...")
    
    def close(self):
        """Close the dialog"""
        if self.download_in_progress:
            if messagebox.askyesno("Cancel Download", "A download is in progress. Cancel and close?"):
                self.cancel_download = True
                self.dialog.destroy()
        else:
            self.dialog.destroy()
    
    @staticmethod
    def format_size(size_bytes):
        """Format size in bytes to human-readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ("B", "KB", "MB", "GB", "TB")
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024
            i += 1
        
        return f"{size_bytes:.2f} {size_names[i]}"


def show_aws_download_dialog(parent, items, aws_credentials=None):
    """
    Show the AWS download dialog.
    
    Args:
        parent: Parent window
        items: List of items to download
        aws_credentials: Optional dictionary with AWS credentials
    """
    dialog = AWSDownloadDialog(parent, items, aws_credentials)
    return dialog
