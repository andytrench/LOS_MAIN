"""
UI panels module for the LOS application.
Provides reusable UI panels for different parts of the application.
"""

import tkinter as tk
from tkinter import ttk
from tkcalendar import DateEntry
from datetime import date
import logging
from log_config import setup_logging
from utilities.ui_components import ButtonPanel, show_error_dialog

# Create logger
logger = setup_logging(__name__)

class LidarSearchPanel:
    """A reusable panel for LIDAR search functionality"""

    def __init__(self, parent, title="LIDAR Search"):
        """Initialize the LIDAR search panel

        Args:
            parent: Parent widget
            title: Panel title
        """
        self.panel = ButtonPanel(parent, title)

        # Initialize variables
        self.polygon_width_ft = tk.StringVar(value="2000")
        self.start_date_var = None
        self.end_date_var = None

        # Create UI elements
        self._setup_date_selectors()
        self._setup_width_control()
        self._setup_action_buttons()

        # Callbacks to be set by the parent
        self.on_search = None
        self.on_clear = None
        self.on_add_all = None
        self.on_export_kml = None
        self.on_export_shapefile = None
        self.on_search_towers = None

    def _setup_date_selectors(self):
        """Set up date selector controls"""
        # First row: Date selectors, width control, and search buttons
        self.panel.add_row(columns=6)

        # Start date
        self.panel.add_label("Start Date:", column=0)
        self.start_date = self.panel.add_date_entry(column=1)
        self.start_date.set_date(date(2000, 1, 1))

        # End date
        self.panel.add_label("End Date:", column=2)
        self.end_date = self.panel.add_date_entry(column=3)
        self.end_date.set_date(date.today())

        # Search width
        self.panel.add_label("Search Width (ft):", column=4)
        self.width_spinbox = self.panel.add_spinbox(
            from_=500,
            to=10000,
            increment=100,
            width=8,
            textvariable=self.polygon_width_ft,
            column=5
        )

        # Second row: Search and clear buttons
        self.panel.add_row(columns=6)

        # Search and clear buttons
        self.search_button = self.panel.add_button(
            "Search LIDAR",
            self._on_search_click,
            column=0,
            columnspan=3,
            sticky="ew"
        )
        self.clear_button = self.panel.add_button(
            "Clear Data",
            self._on_clear_click,
            column=3,
            columnspan=3,
            sticky="ew"
        )

    def _setup_width_control(self):
        """Set up add all and search towers buttons"""
        # Third row: Add all and search towers buttons
        self.panel.add_row(columns=6)

        # Add all button
        self.add_all_button = self.panel.add_button(
            "Add All Project Files to Download",
            self._on_add_all_click,
            column=0,
            columnspan=3,
            sticky="ew"
        )

        # Search towers button
        self.search_towers_button = self.panel.add_button(
            "Search Towers",
            self._on_search_towers_click,
            column=3,
            columnspan=3,
            sticky="ew"
        )

    def _setup_action_buttons(self):
        """Set up action buttons"""
        # Fourth row: Export buttons
        self.panel.add_row(columns=6)

        # Export buttons
        self.export_kml_button = self.panel.add_button(
            "Export KML",
            self._on_export_kml_click,
            column=0,
            columnspan=3,
            sticky="ew"
        )

        self.export_shapefile_button = self.panel.add_button(
            "Export Shapefile",
            self._on_export_shapefile_click,
            column=3,
            columnspan=3,
            sticky="ew"
        )

    def _on_search_click(self):
        """Handle search button click"""
        if self.on_search:
            try:
                self.on_search(
                    self.start_date.get_date(),
                    self.end_date.get_date(),
                    float(self.polygon_width_ft.get())
                )
            except Exception as e:
                logger.error(f"Error in search: {e}", exc_info=True)
                show_error_dialog("Search Error", f"Error performing search: {str(e)}")

    def _on_clear_click(self):
        """Handle clear button click"""
        if self.on_clear:
            try:
                self.on_clear()
            except Exception as e:
                logger.error(f"Error clearing data: {e}", exc_info=True)
                show_error_dialog("Clear Error", f"Error clearing data: {str(e)}")

    def _on_add_all_click(self):
        """Handle add all button click"""
        if self.on_add_all:
            try:
                self.on_add_all()
            except Exception as e:
                logger.error(f"Error adding all files: {e}", exc_info=True)
                show_error_dialog("Add Files Error", f"Error adding all files: {str(e)}")

    def _on_export_kml_click(self):
        """Handle export KML button click"""
        if self.on_export_kml:
            try:
                self.on_export_kml()
            except Exception as e:
                logger.error(f"Error exporting KML: {e}", exc_info=True)
                show_error_dialog("Export Error", f"Error exporting KML: {str(e)}")

    def _on_export_shapefile_click(self):
        """Handle export shapefile button click"""
        if self.on_export_shapefile:
            try:
                self.on_export_shapefile()
            except Exception as e:
                logger.error(f"Error exporting shapefile: {e}", exc_info=True)
                show_error_dialog("Export Error", f"Error exporting shapefile: {str(e)}")

    def pack(self, **kwargs):
        """Pack the panel"""
        self.panel.pack(**kwargs)

    def grid(self, **kwargs):
        """Grid the panel"""
        self.panel.grid(**kwargs)

    def _on_search_towers_click(self):
        """Handle search towers button click"""
        if self.on_search_towers:
            try:
                self.on_search_towers()
            except Exception as e:
                logger.error(f"Error searching towers: {e}", exc_info=True)
                show_error_dialog("Tower Search Error", f"Error searching for towers: {str(e)}")

    def set_callbacks(self, on_search=None, on_clear=None, on_add_all=None,
                     on_export_kml=None, on_export_shapefile=None, on_search_towers=None):
        """Set callbacks for the panel

        Args:
            on_search: Callback for search button
            on_clear: Callback for clear button
            on_add_all: Callback for add all button
            on_export_kml: Callback for export KML button
            on_export_shapefile: Callback for export shapefile button
            on_search_towers: Callback for search towers button
        """
        self.on_search = on_search
        self.on_clear = on_clear
        self.on_add_all = on_add_all
        self.on_export_kml = on_export_kml
        self.on_export_shapefile = on_export_shapefile
        self.on_search_towers = on_search_towers

class ProjectControlPanel:
    """A reusable panel for project control functionality"""

    def __init__(self, parent, title="Project Control"):
        """Initialize the project control panel

        Args:
            parent: Parent widget
            title: Panel title
        """
        self.panel = ButtonPanel(parent, title)

        # Create UI elements
        self._setup_project_selector()
        self._setup_action_buttons()

        # Callbacks to be set by the parent
        self.on_project_change = None
        self.on_view_map = None
        self.on_add_files = None

    def _setup_project_selector(self):
        """Set up project selector"""
        # First row: Project selector
        self.panel.add_row(columns=6)

        # Project selector
        self.panel.add_label("Select Project:", column=0)
        self.project_var = tk.StringVar()
        self.project_dropdown = self.panel.add_combobox(
            values=["Overview"],
            textvariable=self.project_var,
            column=1,
            columnspan=3
        )
        self.project_var.set("Overview")
        self.project_dropdown.bind("<<ComboboxSelected>>", self._on_project_change)

        # Action buttons
        self.view_map_button = self.panel.add_button(
            "View on Map",
            self._on_view_map_click,
            column=4
        )

        self.add_files_button = self.panel.add_button(
            "Add Project Files to Download",
            self._on_add_files_click,
            column=5
        )

    def _setup_action_buttons(self):
        """Set up action buttons"""
        # No additional buttons for now
        pass

    def _on_project_change(self, event):
        """Handle project change"""
        if self.on_project_change:
            try:
                self.on_project_change(self.project_var.get())
            except Exception as e:
                logger.error(f"Error changing project: {e}", exc_info=True)
                show_error_dialog("Project Error", f"Error changing project: {str(e)}")

    def _on_view_map_click(self):
        """Handle view map button click"""
        if self.on_view_map:
            try:
                self.on_view_map()
            except Exception as e:
                logger.error(f"Error viewing map: {e}", exc_info=True)
                show_error_dialog("Map Error", f"Error viewing map: {str(e)}")

    def _on_add_files_click(self):
        """Handle add files button click"""
        if self.on_add_files:
            try:
                self.on_add_files()
            except Exception as e:
                logger.error(f"Error adding files: {e}", exc_info=True)
                show_error_dialog("Add Files Error", f"Error adding files: {str(e)}")

    def set_projects(self, projects):
        """Set the list of available projects

        Args:
            projects: List of project names
        """
        self.project_dropdown.configure(values=projects)
        if projects and self.project_var.get() not in projects:
            self.project_var.set(projects[0])

    def get_selected_project(self):
        """Get the currently selected project

        Returns:
            The selected project name
        """
        return self.project_var.get()

    def pack(self, **kwargs):
        """Pack the panel"""
        self.panel.pack(**kwargs)

    def grid(self, **kwargs):
        """Grid the panel"""
        self.panel.grid(**kwargs)

    def set_callbacks(self, on_project_change=None, on_view_map=None, on_add_files=None):
        """Set callbacks for the panel

        Args:
            on_project_change: Callback for project change
            on_view_map: Callback for view map button
            on_add_files: Callback for add files button
        """
        self.on_project_change = on_project_change
        self.on_view_map = on_view_map
        self.on_add_files = on_add_files

class FileListPanel:
    """A reusable panel for file list functionality"""

    def __init__(self, parent, title=None):
        """Initialize the file list panel

        Args:
            parent: Parent widget
            title: Panel title
        """
        if title:
            self.frame = ttk.LabelFrame(parent, text=title)
        else:
            self.frame = ttk.Frame(parent)

        # Create treeview for file list
        self._setup_treeview()

        # Create button panel
        self.button_panel = ButtonPanel(self.frame)
        self._setup_buttons()
        self.button_panel.pack(fill="x", padx=5, pady=5)

        # Callbacks to be set by the parent
        self.on_select_all = None
        self.on_deselect_all = None
        self.on_add_to_downloads = None
        self.on_write_metadata = None

    def _setup_treeview(self):
        """Set up the treeview for file list"""
        # Create frame for treeview
        self.tree_frame = ttk.Frame(self.frame)
        self.tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Create treeview with scrollbars
        self.tree = ttk.Treeview(
            self.tree_frame,
            columns=("ID", "Name", "Size", "Project", "Tile ID"),
            show="headings",
            selectmode="extended"
        )

        # Add scrollbars
        vsb = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(self.tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Pack scrollbars
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True)

        # Configure columns
        self.tree.heading("ID", text="ID")
        self.tree.heading("Name", text="Name")
        self.tree.heading("Size", text="Size")
        self.tree.heading("Project", text="Project")
        self.tree.heading("Tile ID", text="Tile ID")

        self.tree.column("ID", width=50, anchor="center")
        self.tree.column("Name", width=200)
        self.tree.column("Size", width=80, anchor="center")
        self.tree.column("Project", width=100)
        self.tree.column("Tile ID", width=80, anchor="center")

    def _setup_buttons(self):
        """Set up buttons for file list actions"""
        # First row of buttons
        self.button_panel.add_row(columns=3)

        self.select_all_button = self.button_panel.add_button(
            "Select All",
            self._on_select_all_click,
            column=0
        )

        self.deselect_all_button = self.button_panel.add_button(
            "Deselect All",
            self._on_deselect_all_click,
            column=1
        )

        self.add_to_downloads_button = self.button_panel.add_button(
            "Add to Downloads",
            self._on_add_to_downloads_click,
            column=2
        )

        # Second row of buttons
        self.button_panel.add_row(columns=1)

        self.write_metadata_button = self.button_panel.add_button(
            "Write Project Metadata",
            self._on_write_metadata_click,
            column=0
        )

    def _on_select_all_click(self):
        """Handle select all button click"""
        if self.on_select_all:
            try:
                self.on_select_all()
            except Exception as e:
                logger.error(f"Error selecting all: {e}", exc_info=True)
                show_error_dialog("Selection Error", f"Error selecting all items: {str(e)}")

    def _on_deselect_all_click(self):
        """Handle deselect all button click"""
        if self.on_deselect_all:
            try:
                self.on_deselect_all()
            except Exception as e:
                logger.error(f"Error deselecting all: {e}", exc_info=True)
                show_error_dialog("Selection Error", f"Error deselecting all items: {str(e)}")

    def _on_add_to_downloads_click(self):
        """Handle add to downloads button click"""
        if self.on_add_to_downloads:
            try:
                selected_items = self.tree.selection()
                self.on_add_to_downloads(selected_items)
            except Exception as e:
                logger.error(f"Error adding to downloads: {e}", exc_info=True)
                show_error_dialog("Download Error", f"Error adding items to downloads: {str(e)}")

    def _on_write_metadata_click(self):
        """Handle write metadata button click"""
        if self.on_write_metadata:
            try:
                self.on_write_metadata()
            except Exception as e:
                logger.error(f"Error writing metadata: {e}", exc_info=True)
                show_error_dialog("Metadata Error", f"Error writing metadata: {str(e)}")

    def clear(self):
        """Clear all items from the treeview"""
        for item in self.tree.get_children():
            self.tree.delete(item)

    def add_item(self, item_id, name, size, project, tile_id):
        """Add an item to the treeview

        Args:
            item_id: Item ID
            name: Item name
            size: Item size
            project: Project name
            tile_id: Tile ID
        """
        self.tree.insert("", "end", values=(item_id, name, size, project, tile_id))

    def pack(self, **kwargs):
        """Pack the panel"""
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        """Grid the panel"""
        self.frame.grid(**kwargs)

    def set_callbacks(self, on_select_all=None, on_deselect_all=None,
                     on_add_to_downloads=None, on_write_metadata=None):
        """Set callbacks for the panel

        Args:
            on_select_all: Callback for select all button
            on_deselect_all: Callback for deselect all button
            on_add_to_downloads: Callback for add to downloads button
            on_write_metadata: Callback for write metadata button
        """
        self.on_select_all = on_select_all
        self.on_deselect_all = on_deselect_all
        self.on_add_to_downloads = on_add_to_downloads
        self.on_write_metadata = on_write_metadata
