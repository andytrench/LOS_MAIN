"""
UI components module for the LOS application.
Provides custom UI widgets and frames.
"""

import tkinter as tk
from tkinter import ttk
import logging
from log_config import setup_logging

# Create logger
logger = setup_logging(__name__)

def create_scrollable_frame(parent, label_text=None):
    """Create a scrollable frame with optional label"""
    # Create a frame with optional label
    if label_text:
        frame = ttk.LabelFrame(parent, text=label_text)
    else:
        frame = ttk.Frame(parent)

    # Create a canvas inside the frame
    canvas = tk.Canvas(frame)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    scrollable_frame = ttk.Frame(canvas)

    # Configure the canvas
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Pack the widgets
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Add mousewheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    return frame, scrollable_frame, canvas

def create_info_display(parent, label_text, initial_text=""):
    """Create an information display with label and text widget"""
    # Create frame
    frame = ttk.LabelFrame(parent, text=label_text)

    # Create text widget
    text_widget = tk.Text(frame, wrap="word", height=5, width=40)
    text_widget.insert("1.0", initial_text)
    text_widget.config(state="disabled")

    # Add scrollbar
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=text_widget.yview)
    text_widget.configure(yscrollcommand=scrollbar.set)

    # Pack widgets
    text_widget.pack(side="left", fill="both", expand=True, padx=5, pady=5)
    scrollbar.pack(side="right", fill="y", pady=5)

    return frame, text_widget

def create_button_grid(parent, buttons_config, columns=2):
    """Create a grid of buttons

    Args:
        parent: Parent widget
        buttons_config: List of dictionaries with keys 'text' and 'command'
        columns: Number of columns in the grid
    """
    # Create frame
    frame = ttk.Frame(parent)

    # Configure columns for even distribution
    for i in range(columns):
        frame.columnconfigure(i, weight=1)

    # Add buttons
    for i, config in enumerate(buttons_config):
        row = i // columns
        col = i % columns

        button = ttk.Button(
            frame,
            text=config['text'],
            command=config['command']
        )
        button.grid(row=row, column=col, padx=5, pady=3, sticky="ew")

    return frame

def create_date_selector(parent, label_text, default_date=None):
    """Create a date selector with label"""
    from tkcalendar import DateEntry
    from datetime import date

    # Create frame
    frame = ttk.Frame(parent)

    # Add label
    label = ttk.Label(frame, text=label_text)
    label.pack(side="left", padx=5)

    # Create date entry
    if default_date is None:
        default_date = date.today()

    date_entry = DateEntry(frame, width=12, background='darkblue',
                          foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd',
                          year=default_date.year, month=default_date.month, day=default_date.day)
    date_entry.pack(side="left", padx=5)

    return frame, date_entry

def create_numeric_entry(parent, label_text, default_value=0, min_value=None, max_value=None, width=10):
    """Create a numeric entry with label and validation"""
    # Create frame
    frame = ttk.Frame(parent)

    # Add label
    label = ttk.Label(frame, text=label_text)
    label.pack(side="left", padx=5)

    # Create StringVar for the entry
    var = tk.StringVar(value=str(default_value))

    # Validation function
    def validate_numeric(action, value_if_allowed):
        if action == '1':  # Insert
            if value_if_allowed == "":
                return True
            try:
                value = int(value_if_allowed)
                if min_value is not None and value < min_value:
                    return False
                if max_value is not None and value > max_value:
                    return False
                return True
            except ValueError:
                return False
        return True

    # Register validation
    vcmd = (parent.register(validate_numeric), '%d', '%P')

    # Create entry
    entry = ttk.Entry(frame, textvariable=var, width=width, validate="key", validatecommand=vcmd)
    entry.pack(side="left", padx=5)

    return frame, var

def create_dropdown(parent, label_text, options, default_option=None, width=15):
    """Create a dropdown with label"""
    # Create frame
    frame = ttk.Frame(parent)

    # Add label
    label = ttk.Label(frame, text=label_text)
    label.pack(side="left", padx=5)

    # Create StringVar for the dropdown
    var = tk.StringVar()
    if default_option:
        var.set(default_option)
    elif options:
        var.set(options[0])

    # Create dropdown
    dropdown = ttk.Combobox(frame, textvariable=var, values=options, width=width)
    dropdown.pack(side="left", padx=5)

    return frame, var, dropdown

def create_checkbox(parent, text, default_value=False):
    """Create a checkbox"""
    # Create variable
    var = tk.BooleanVar(value=default_value)

    # Create checkbox
    checkbox = ttk.Checkbutton(parent, text=text, variable=var)

    return checkbox, var

def create_progress_bar(parent, label_text=None):
    """Create a progress bar with optional label"""
    # Create frame
    frame = ttk.Frame(parent)

    # Add label if provided
    if label_text:
        label = ttk.Label(frame, text=label_text)
        label.pack(side="top", anchor="w", padx=5, pady=(5, 0))

    # Create progress bar
    progress_bar = ttk.Progressbar(frame, orient="horizontal", length=200, mode="determinate")
    progress_bar.pack(side="top", fill="x", padx=5, pady=5)

    return frame, progress_bar

def create_status_bar(parent):
    """Create a status bar at the bottom of the parent"""
    # Create frame
    frame = ttk.Frame(parent, relief="sunken", borderwidth=1)
    frame.pack(side="bottom", fill="x")

    # Create label
    status_var = tk.StringVar(value="Ready")
    status_label = ttk.Label(frame, textvariable=status_var, anchor="w", padding=(5, 2))
    status_label.pack(side="left", fill="x")

    return frame, status_var

def show_info_dialog(title, message):
    """Show an information dialog"""
    from tkinter import messagebox
    messagebox.showinfo(title, message)

def show_error_dialog(title, message):
    """Show an error dialog"""
    from tkinter import messagebox
    messagebox.showerror(title, message)

def show_warning_dialog(title, message):
    """Show a warning dialog"""
    from tkinter import messagebox
    messagebox.showwarning(title, message)

def show_yes_no_dialog(title, message):
    """Show a yes/no dialog"""
    from tkinter import messagebox
    return messagebox.askyesno(title, message)

class ButtonPanel:
    """A reusable panel for organizing buttons in rows"""

    def __init__(self, parent, title=None):
        """Initialize the button panel

        Args:
            parent: Parent widget
            title: Optional title for the panel
        """
        if title:
            self.frame = ttk.LabelFrame(parent, text=title)
        else:
            self.frame = ttk.Frame(parent)

        self.rows = []
        self.current_row = None
        self.current_row_index = -1

    def add_row(self, columns=0):
        """Add a new row to the panel

        Args:
            columns: Number of columns to configure with equal weight
        """
        self.current_row_index += 1
        self.current_row = ttk.Frame(self.frame)
        self.current_row.pack(fill="x", padx=5, pady=2)
        self.rows.append(self.current_row)

        # Configure columns for even distribution if specified
        if columns > 0:
            for i in range(columns):
                self.current_row.columnconfigure(i, weight=1)

            # Make sure the row itself expands to fill available width
            self.current_row.pack(fill="x", expand=True, padx=5, pady=2)

        return self.current_row

    def add_button(self, text, command, column=None, columnspan=1, width=None, sticky="ew", **kwargs):
        """Add a button to the current row

        Args:
            text: Button text
            command: Button command
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            width: Button width
            sticky: Grid sticky parameter
            **kwargs: Additional button parameters
        """
        if self.current_row is None:
            self.add_row()

        button = ttk.Button(self.current_row, text=text, command=command, width=width, **kwargs)

        if column is not None:
            # Use grid with weight to ensure buttons expand properly
            self.current_row.columnconfigure(column, weight=1)
            button.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky=sticky)
        else:
            button.pack(side="left", fill="x", expand=True, padx=5, pady=2)

        return button

    def add_label(self, text, column=None, columnspan=1, sticky="w", **kwargs):
        """Add a label to the current row

        Args:
            text: Label text
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            sticky: Grid sticky parameter
            **kwargs: Additional label parameters
        """
        if self.current_row is None:
            self.add_row()

        label = ttk.Label(self.current_row, text=text, **kwargs)

        if column is not None:
            label.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky=sticky)
        else:
            label.pack(side="left", padx=5, pady=2)

        return label

    def add_entry(self, column=None, columnspan=1, width=None, textvariable=None, **kwargs):
        """Add an entry field to the current row

        Args:
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            width: Entry width
            textvariable: Tkinter variable to bind to the entry
            **kwargs: Additional entry parameters
        """
        if self.current_row is None:
            self.add_row()

        entry = ttk.Entry(self.current_row, width=width, textvariable=textvariable, **kwargs)

        if column is not None:
            entry.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky="ew")
        else:
            entry.pack(side="left", fill="x", expand=True, padx=5, pady=2)

        return entry

    def add_spinbox(self, from_, to, increment=1, column=None, columnspan=1, width=None, textvariable=None, **kwargs):
        """Add a spinbox to the current row

        Args:
            from_: Minimum value
            to: Maximum value
            increment: Increment value
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            width: Spinbox width
            textvariable: Tkinter variable to bind to the spinbox
            **kwargs: Additional spinbox parameters
        """
        if self.current_row is None:
            self.add_row()

        spinbox = ttk.Spinbox(
            self.current_row,
            from_=from_,
            to=to,
            increment=increment,
            width=width,
            textvariable=textvariable,
            **kwargs
        )

        if column is not None:
            spinbox.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky="ew")
        else:
            spinbox.pack(side="left", padx=5, pady=2)

        return spinbox

    def add_date_entry(self, column=None, columnspan=1, width=12, **kwargs):
        """Add a date entry to the current row

        Args:
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            width: Date entry width
            **kwargs: Additional date entry parameters
        """
        from tkcalendar import DateEntry

        if self.current_row is None:
            self.add_row()

        date_entry = DateEntry(
            self.current_row,
            width=width,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            **kwargs
        )

        if column is not None:
            date_entry.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky="ew")
        else:
            date_entry.pack(side="left", padx=5, pady=2)

        return date_entry

    def add_combobox(self, values, column=None, columnspan=1, width=None, textvariable=None, **kwargs):
        """Add a combobox to the current row

        Args:
            values: List of values for the combobox
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            width: Combobox width
            textvariable: Tkinter variable to bind to the combobox
            **kwargs: Additional combobox parameters
        """
        if self.current_row is None:
            self.add_row()

        combobox = ttk.Combobox(
            self.current_row,
            values=values,
            width=width,
            textvariable=textvariable,
            **kwargs
        )

        if column is not None:
            combobox.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky="ew")
        else:
            combobox.pack(side="left", fill="x", expand=True, padx=5, pady=2)

        return combobox

    def add_checkbox(self, text, column=None, columnspan=1, variable=None, **kwargs):
        """Add a checkbox to the current row

        Args:
            text: Checkbox text
            column: Column position (if None, will be placed using pack)
            columnspan: Number of columns to span
            variable: Tkinter variable to bind to the checkbox
            **kwargs: Additional checkbox parameters
        """
        if self.current_row is None:
            self.add_row()

        checkbox = ttk.Checkbutton(
            self.current_row,
            text=text,
            variable=variable,
            **kwargs
        )

        if column is not None:
            checkbox.grid(row=0, column=column, columnspan=columnspan, padx=5, pady=2, sticky="w")
        else:
            checkbox.pack(side="left", padx=5, pady=2)

        return checkbox

    def pack(self, **kwargs):
        """Pack the frame with the given parameters"""
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        """Grid the frame with the given parameters"""
        self.frame.grid(**kwargs)

def create_section_header(parent, text, pady=10):
    """Create a section header with a horizontal separator"""
    frame = ttk.Frame(parent)
    frame.pack(fill="x", pady=pady)

    label = ttk.Label(frame, text=text, font=("TkDefaultFont", 10, "bold"))
    label.pack(side="top", anchor="w", padx=5)

    separator = ttk.Separator(frame, orient="horizontal")
    separator.pack(fill="x", pady=2)

    return frame, label

def show_warning_dialog(title, message):
    """Show a warning dialog"""
    from tkinter import messagebox
    messagebox.showwarning(title, message)

def show_confirmation_dialog(title, message):
    """Show a confirmation dialog"""
    from tkinter import messagebox
    return messagebox.askyesno(title, message)
