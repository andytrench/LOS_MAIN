import tkinter as tk
from tkinter import ttk
import logging

# Configure logging
logger = logging.getLogger(__name__)

class ProjectSelectionDialog:
    """
    Dialog for selecting projects from a list.
    """
    def __init__(self, parent, projects):
        """
        Initialize the project selection dialog.
        
        Args:
            parent: The parent window
            projects: Dictionary or list of project data
        """
        self.parent = parent
        self.result = None
        self.selected_project = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Select Project")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog on the parent window
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (500 // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (400 // 2)
            self.dialog.geometry(f"+{x}+{y}")
        
        # Create frame for project list
        frame = ttk.Frame(self.dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Add label
        ttk.Label(frame, text="Select projects:").pack(anchor="w", pady=(0, 5))
        
        # Create scrollable frame for checkboxes
        self.canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Add checkboxes for each project
        self.project_vars = {}
        
        # Handle different project data formats
        if isinstance(projects, dict):
            # If projects is a dictionary
            for project_name, project_data in projects.items():
                self.add_project_checkbox(project_name, project_data)
        elif isinstance(projects, list):
            # If projects is a list of dictionaries
            for project_data in projects:
                project_name = project_data.get('name', 'Unknown')
                self.add_project_checkbox(project_name, project_data)
        
        # Add buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill="x", pady=10)
        
        ttk.Button(button_frame, text="Select All", command=self.select_all).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Deselect All", command=self.deselect_all).pack(side="left", padx=5)
        ttk.Button(button_frame, text="OK", command=self.on_ok).pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side="right", padx=5)
        
        # Wait for the dialog to be closed
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_cancel)
        self.dialog.wait_window()
    
    def add_project_checkbox(self, project_name, project_data):
        """Add a checkbox for a project"""
        var = tk.BooleanVar(value=False)
        self.project_vars[project_name] = (var, project_data)
        
        # Create frame for each project
        project_frame = ttk.Frame(self.scrollable_frame)
        project_frame.pack(fill="x", pady=2)
        
        # Add checkbox
        cb = ttk.Checkbutton(project_frame, text=project_name, variable=var)
        cb.pack(side="left", padx=5)
        
        # Add project info if available
        if isinstance(project_data, dict):
            # Add project details if available
            details = []
            
            # Add date range if available
            if 'dates' in project_data:
                date_range = project_data.get('dates', {})
                start = date_range.get('start_date', '')
                end = date_range.get('end_date', '')
                if start and end:
                    details.append(f"Dates: {start} to {end}")
            
            # Add file count if available
            file_count = project_data.get('file_count', 0)
            if file_count:
                details.append(f"Files: {file_count}")
            
            # Display details
            if details:
                detail_text = " | ".join(details)
                ttk.Label(project_frame, text=detail_text, foreground="gray").pack(side="left", padx=5)
    
    def select_all(self):
        """Select all projects"""
        for var, _ in self.project_vars.values():
            var.set(True)
    
    def deselect_all(self):
        """Deselect all projects"""
        for var, _ in self.project_vars.values():
            var.set(False)
    
    def on_ok(self):
        """Handle OK button click"""
        # Get selected projects
        selected = []
        for project_name, (var, project_data) in self.project_vars.items():
            if var.get():
                selected.append(project_name)
        
        self.result = selected
        
        # Also set selected_project for compatibility with existing code
        # This is for dialogs that expect a single selection
        if len(selected) == 1:
            project_name = selected[0]
            _, project_data = self.project_vars[project_name]
            self.selected_project = project_data
        
        self.dialog.destroy()
    
    def on_cancel(self):
        """Handle Cancel button click"""
        self.result = None
        self.selected_project = None
        self.dialog.destroy()

class ExportProgressDialog:
    """
    Dialog for showing export progress.
    """
    def __init__(self, parent, total_items):
        """
        Initialize the export progress dialog.
        
        Args:
            parent: The parent window
            total_items: Total number of items to process
        """
        self.parent = parent
        self.total_items = total_items
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Export Progress")
        self.dialog.geometry("400x150")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog on the parent window
        if parent:
            x = parent.winfo_x() + (parent.winfo_width() // 2) - (400 // 2)
            y = parent.winfo_y() + (parent.winfo_height() // 2) - (150 // 2)
            self.dialog.geometry(f"+{x}+{y}")
        
        # Create frame for progress
        frame = ttk.Frame(self.dialog, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Add label
        self.status_label = ttk.Label(frame, text="Exporting projects...")
        self.status_label.pack(anchor="w", pady=(0, 10))
        
        # Add progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            frame, 
            orient="horizontal", 
            length=380, 
            mode="determinate",
            variable=self.progress_var
        )
        self.progress_bar.pack(fill="x", pady=5)
        
        # Add current project label
        self.project_label = ttk.Label(frame, text="")
        self.project_label.pack(anchor="w", pady=5)
        
        # Add cancel button
        self.cancel_button = ttk.Button(frame, text="Cancel", command=self.on_cancel)
        self.cancel_button.pack(side="right", pady=10)
        
        # Initialize progress
        self.progress_var.set(0)
        self.cancelled = False
        
        # Make sure the dialog is updated
        self.dialog.update()
    
    def update_progress(self, project_name, percent):
        """Update the progress display"""
        self.progress_var.set(percent)
        self.project_label.config(text=f"Processing: {project_name}")
        self.dialog.update()
    
    def on_cancel(self):
        """Handle Cancel button click"""
        self.cancelled = True
        self.dialog.destroy()
    
    def destroy(self):
        """Close the dialog"""
        self.dialog.destroy()
