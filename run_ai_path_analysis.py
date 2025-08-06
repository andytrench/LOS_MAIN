#!/usr/bin/env python3
"""
Standalone script to run the AI path analysis without running dropmap.py.
This script reads site coordinates from towers_parameter.json and launches
the AI path analysis directly.
"""

import sys
import json
import tkinter as tk
import threading
from utilities.ai_path_analyze import run_multi_source_analysis, AnalysisWindow

def load_tower_parameters():
    """Load tower parameters from the JSON file."""
    try:
        with open('tower_parameters.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: tower_parameters.json file not found.")
        return None
    except json.JSONDecodeError:
        print("Error: tower_parameters.json is not a valid JSON file.")
        return None

def main():
    """Main function to run the AI path analysis."""
    # Load tower parameters
    tower_params = load_tower_parameters()
    if not tower_params:
        print("Could not load tower parameters. Exiting.")
        return 1

    # Extract site coordinates
    try:
        site_a = tower_params.get('site_A', {})
        site_b = tower_params.get('site_B', {})

        start_lat = site_a.get('adjusted_latitude')
        start_lon = site_a.get('adjusted_longitude')
        end_lat = site_b.get('adjusted_latitude')
        end_lon = site_b.get('adjusted_longitude')

        if not all([start_lat, start_lon, end_lat, end_lon]):
            print("Error: Missing coordinate data in tower_parameters.json")
            return 1

        start_coords = (start_lat, start_lon)
        end_coords = (end_lat, end_lon)

        print(f"Site A: {site_a.get('site_id')} at {start_coords}")
        print(f"Site B: {site_b.get('site_id')} at {end_coords}")
        print(f"Path length: {tower_params.get('general_parameters', {}).get('path_length_mi', 'N/A')} miles")

    except Exception as e:
        print(f"Error extracting coordinates: {e}")
        return 1

    # Create Tkinter root window
    root = tk.Tk()
    root.title("AI Path Analysis")
    root.geometry("400x200")

    # Create a frame with information
    frame = tk.Frame(root, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)

    # Add labels with site information
    tk.Label(frame, text="AI Path Analysis", font=("Arial", 16, "bold")).pack(pady=10)
    tk.Label(frame, text=f"Site A: {site_a.get('site_id')}").pack(anchor=tk.W)
    tk.Label(frame, text=f"Site B: {site_b.get('site_id')}").pack(anchor=tk.W)
    tk.Label(frame, text=f"Path length: {tower_params.get('general_parameters', {}).get('path_length_mi', 'N/A')} miles").pack(anchor=tk.W)

    # Function to start the analysis
    def start_analysis():
        # Create the analysis window
        analysis_window = AnalysisWindow(root, start_coords, end_coords)

        # Start the analysis in a separate thread
        # Pass root as None to prevent creating another window
        analysis_thread = threading.Thread(
            target=run_multi_source_analysis,
            args=(None, start_coords, end_coords, analysis_window),
            daemon=True
        )
        analysis_thread.start()

    # Add a button to start the analysis
    tk.Button(frame, text="Start AI Path Analysis", command=start_analysis,
              bg="#4CAF50", fg="white", font=("Arial", 12),
              padx=10, pady=5).pack(pady=20)

    # Run the Tkinter main loop
    root.mainloop()
    return 0

if __name__ == "__main__":
    sys.exit(main())
