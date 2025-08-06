import tkinter as tk
from tkinterdnd2 import TkinterDnD, DND_FILES
import os
import requests
from tkinter import ttk, filedialog, messagebox
from threading import Thread, Lock, Event
import queue
import logging
import concurrent.futures
import time
import hashlib
import math
import asyncio
import aiohttp
from tqdm import tqdm
import threading
import subprocess
import shutil
from datetime import datetime
import json
import sys
from utilities.temp_dir_manager import get_temp_dir, get_temp_file, copy_to_output_dir

logger = logging.getLogger(__name__)

class UltraVerboseDownloaderer:
    def __init__(self, master):
        """Initialize the downloader with all required attributes"""
        self.master = master
        self.setup_logging()

        # Initialize ALL tracking variables first
        self.urls = []
        self.file_info = {}
        self.download_queue = queue.PriorityQueue()
        self.max_concurrent_downloads = 10
        self.current_downloads = 0
        self.lock = Lock()
        self.active_downloads = set()
        self.paused = Event()
        self.paused.set()
        self.destination_folder = os.getcwd()

        # Initialize selection tracking
        self.selected_files = set()  # For Treeview items
        self.item_url_map = {}      # Maps Treeview items to URLs

        # Add retry configuration
        self.max_retries = 3  # Maximum number of retry attempts
        self.retry_delay = 5  # Delay in seconds between retries

        logger.info("Initialized all tracking variables")

        # Set up UI with original layout
        self.setup_ui()

        self.log("Downloader initialized")

        # Start periodic UI refresh
        self.start_periodic_refresh()

    def setup_logging(self):
        self.logger = logging.getLogger("Downloaderer")
        self.logger.setLevel(logging.DEBUG)
        self.log_queue = queue.Queue()
        queue_handler = QueueHandler(self.log_queue)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        queue_handler.setFormatter(formatter)
        self.logger.addHandler(queue_handler)

    def check_log_queue(self):
        while True:
            try:
                record = self.log_queue.get_nowait()
                self.logs_text.configure(state=tk.NORMAL)
                self.logs_text.insert(tk.END, f"{record}\n")
                self.logs_text.see(tk.END)
                self.logs_text.configure(state=tk.DISABLED)
            except queue.Empty:
                break
        self.master.after(100, self.check_log_queue)

    def log(self, message, level=logging.INFO):
        self.logger.log(level, message)

    def format_size(self, size_in_bytes):
        """Format file size in human-readable format"""
        try:
            if not size_in_bytes:
                return "Unknown"

            for unit in ['B', 'KB', 'MB', 'GB']:
                if size_in_bytes < 1024:
                    return f"{size_in_bytes:.2f} {unit}"
                size_in_bytes /= 1024
            return f"{size_in_bytes:.2f} TB"

        except Exception as e:
            self.logger.error(f"Error formatting size: {str(e)}")
            return "Unknown"

    def check_completed_files(self):
        """Check for completed files in the destination folder and update their status"""
        try:
            for url, info in self.file_info.items():
                local_path = os.path.join(self.destination_folder, info['filename'])
                if os.path.exists(local_path):
                    # Verify file size matches expected size
                    actual_size = os.path.getsize(local_path)
                    expected_size = info['total_size']

                    if actual_size == expected_size:
                        # File is complete
                        info.update({
                            'status': 'Complete',
                            'progress': 100,
                            'size_on_disk': actual_size,
                            'end_time': datetime.fromtimestamp(os.path.getmtime(local_path))
                        })
                        logger.info(f"Found completed file: {info['filename']}")
                    else:
                        # File exists but is incomplete
                        info.update({
                            'status': 'Incomplete',
                            'progress': (actual_size / expected_size) * 100,
                            'size_on_disk': actual_size
                        })
                        logger.info(f"Found incomplete file: {info['filename']} ({self.format_size(actual_size)} / {self.format_size(expected_size)})")

                self.update_file_list(url)

        except Exception as e:
            logger.error(f"Error checking completed files: {e}", exc_info=True)

    async def fetch_file_size_async(self, url):
        """Fetch and set the definitive file size for a URL"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, allow_redirects=True) as response:
                    size = int(response.headers.get('Content-Length', 0))
                    with self.lock:
                        if url in self.file_info:
                            # Only set total_size if not already set
                            if self.file_info[url]['total_size'] == 0:
                                self.file_info[url]['total_size'] = size
                                logger.info(f"Set definitive file size for {self.file_info[url]['filename']}: {self.format_size(size)}")
                            self.update_file_list(url)
        except Exception as e:
            logger.error(f"Error fetching file size for {url}: {str(e)}", level=logging.ERROR)

    def add_url(self, url, filename, file_info=None):
        """Add a URL to the download queue with pre-fetched metadata"""
        try:
            if not url or not filename:
                raise ValueError("Both URL and filename must be provided")

            # Use provided file info or create minimal default
            info = file_info or {
                'filename': filename,
                'status': 'Queued',
                'progress': 0,
                'size_on_disk': 0,
                'total_size': 0,
                'metadata': {},
                'last_update_time': time.time(),
                'last_update_size': 0,
                'speed': 0,
                'eta': 0,
                'error': None,
                'last_progress': 0
            }

            # If URL exists, preserve existing state but update with new info
            if url in self.file_info:
                existing_info = self.file_info[url]
                info = {**existing_info, **info}
                # Ensure all progress tracking fields exist
                for field in ['last_update_time', 'last_update_size', 'speed', 'eta', 'last_progress']:
                    if field not in info:
                        info[field] = 0

            # Check file existence
            local_path = os.path.join(self.destination_folder, filename)
            if os.path.exists(local_path):
                actual_size = os.path.getsize(local_path)
                if actual_size == info['total_size'] and info['total_size'] > 0:
                    info.update({
                        'status': 'Complete',
                        'progress': 100,
                        'size_on_disk': actual_size,
                        'speed': 0,
                        'eta': 0
                    })
                    logger.info(f"File already complete: {filename}")
                else:
                    info.update({
                        'status': 'Incomplete',
                        'size_on_disk': actual_size,
                        'progress': 0
                    })
                    logger.info(f"Found incomplete file: {filename}")

            # Store file info
            with self.lock:
                self.file_info[url] = info

                # Always add to URLs list if not present
                if not any(u == url for u, _ in self.urls):
                    self.urls.append((url, filename))

                # Always add to download queue unless complete
                if info['status'] != 'Complete':
                    self.download_queue.put((url, filename))

            # Fetch file size asynchronously if not already known
            if info['total_size'] == 0:
                asyncio.run(self.fetch_file_size_async(url))

            logger.debug(f"Added to queue: {filename} | Size: {self.format_size(info['total_size'])} | Status: {info['status']}")
            return True

        except Exception as e:
            logger.error(f"Error adding URL to queue: {str(e)}", exc_info=True)
            return False

    def add_urls_bulk(self, file_info_list):
        """Add multiple URLs with pre-fetched metadata in bulk"""
        try:
            if not file_info_list:
                return 0, 0, 0

            logger.info(f"Adding batch of {len(file_info_list)} URLs to download queue")

            # Track unique filenames to avoid duplicates
            seen_filenames = set()

            # Add each URL to the queue
            added_count = 0
            skipped_count = 0
            error_count = 0
            already_in_queue = 0

            # Process all files first
            to_add = []
            for url, filename, info in file_info_list:
                try:
                    # Skip if filename already seen in this batch
                    if filename in seen_filenames:
                        logger.info(f"Duplicate filename in batch skipped: {filename}")
                        skipped_count += 1
                        continue

                    # Add to tracking set for this batch
                    seen_filenames.add(filename)

                    # Create a new info dict to avoid modifying the original
                    new_info = info.copy()

                    # Check if URL already exists
                    if url in self.file_info:
                        # Count as already in queue
                        already_in_queue += 1
                        logger.info(f"URL already in queue: {url} (filename: {filename})")

                        # Preserve existing state but update with new info
                        existing_info = self.file_info[url]
                        new_info = {**existing_info, **new_info}

                    # Single file existence check
                    local_path = os.path.join(self.destination_folder, filename)
                    if os.path.exists(local_path):
                        actual_size = os.path.getsize(local_path)
                        if actual_size == new_info['total_size'] and new_info['total_size'] > 0:
                            new_info.update({
                                'status': 'Complete',
                                'progress': 100,
                                'size_on_disk': actual_size
                            })
                        else:
                            new_info.update({
                                'status': 'Incomplete',
                                'size_on_disk': actual_size,
                                'progress': 0  # Will be updated after total_size is confirmed
                            })

                    to_add.append((url, filename, new_info))
                    added_count += 1

                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}", exc_info=True)
                    error_count += 1

            # Bulk update data structures
            for url, filename, info in to_add:
                with self.lock:
                    self.file_info[url] = info

                    # Add to URLs list if not already present
                    if not any(u == url for u, _ in self.urls):
                        self.urls.append((url, filename))

                    # Fetch file size asynchronously if not already known
                    if info['total_size'] == 0:
                        asyncio.run(self.fetch_file_size_async(url))

                    # Add to download queue if not complete
                    if info['status'] != 'Complete':
                        self.download_queue.put((url, filename))

            # Single UI update for all files
            self.refresh_file_list()

            logger.info(f"Bulk add complete - Added: {added_count}, Already in queue: {already_in_queue}, Skipped duplicates: {skipped_count}, Errors: {error_count}")
            return added_count, already_in_queue, error_count

        except Exception as e:
            logger.error(f"Error in bulk add: {e}", exc_info=True)
            return 0, 0, 1

    async def fetch_all_file_sizes_async(self):
        tasks = [self.fetch_file_size_async(url) for url, _ in self.urls]
        await asyncio.gather(*tasks)

    def fetch_all_file_sizes(self):
        asyncio.run(self.fetch_all_file_sizes_async())

    def update_file_list(self, url):
        """Thread-safe update of the file list display"""
        try:
            info = self.file_info[url]
            filename = info['filename']

            def do_update():
                for item in self.file_list.get_children():
                    if self.file_list.item(item)['values'][1] == filename:
                        # Get current values to ensure smooth updates
                        current_values = self.file_list.item(item)['values']

                        # Ensure progress never decreases
                        new_progress = info.get('progress', 0)
                        if current_values and len(current_values) > 4:
                            try:
                                current_progress = float(current_values[4].rstrip('%'))
                                new_progress = max(current_progress, new_progress)
                            except (ValueError, AttributeError):
                                pass

                        # Ensure speed is never negative
                        speed = max(0, info.get('speed', 0))
                        speed_text = self.format_speed(speed) if speed > 0 else ""

                        # Format ETA only if downloading
                        eta_text = self.format_eta(info.get('eta', 0)) if info.get('status', '').startswith('Downloading') else ""

                        # Keep status clean without speed/ETA info
                        status = info.get('status', 'Unknown')
                        if status.startswith('Downloading'):
                            status = 'Downloading'

                        self.file_list.item(item, values=(
                            current_values[0],  # Keep checkbox state
                            filename,
                            self.format_size(info.get('total_size', 0)),
                            self.format_size(info.get('size_on_disk', 0)),
                            f"{new_progress:.1f}%",
                            speed_text,
                            eta_text,
                            status
                        ))
                        break

            # Ensure update happens in main thread
            if threading.current_thread() is threading.main_thread():
                do_update()
            else:
                self.master.after(0, do_update)

        except Exception as e:
            logger.error(f"Error updating file list: {str(e)}")

    def on_item_click(self, event):
        """Handle clicks in the file list"""
        try:
            region = self.file_list.identify("region", event.x, event.y)
            column = self.file_list.identify_column(event.x)

            if region == "cell" and column == "#1":  # Checkbox column
                item = self.file_list.identify_row(event.y)
                if item:
                    # Toggle checkbox
                    current_values = list(self.file_list.item(item)['values'])
                    current_values[0] = "✓" if current_values[0] != "✓" else ""
                    self.file_list.item(item, values=current_values)

                    # Update selection tracking
                    filename = current_values[1]
                    for url, info in self.file_info.items():
                        if info['filename'] == filename:
                            if current_values[0] == "✓":
                                self.selected_files.add(url)
                            else:
                                self.selected_files.discard(url)
                            break

                    logger.info(f"Selected files count: {len(self.selected_files)}")

        except Exception as e:
            logger.error(f"Error handling item click: {str(e)}")

    def select_all(self):
        """Select all items in the file list"""
        try:
            # Clear current selection first
            self.selected_files.clear()
            self.item_url_map.clear()

            # Get all items in the file list
            items = self.file_list.get_children()
            logger.info(f"Selecting all {len(items)} files")

            # Update each item's checkbox and selection state
            for item in items:
                # Update checkbox display
                current_values = list(self.file_list.item(item)['values'])
                current_values[0] = "✓"  # Set checkbox to checked
                self.file_list.item(item, values=current_values)

                # Add to selected files set
                self.selected_files.add(item)

                # Map item to URL for easier lookup later
                filename = current_values[1]  # Get filename
                for url, info in self.file_info.items():
                    if info['filename'] == filename:
                        self.item_url_map[item] = url
                        break

            logger.info(f"Selected all files: {len(self.selected_files)} total")

            # Debug output of selected files
            if logger.isEnabledFor(logging.DEBUG):
                selected_filenames = []
                for selected_item in self.selected_files:
                    try:
                        item_values = self.file_list.item(selected_item)['values']
                        if item_values and len(item_values) > 1:
                            selected_filenames.append(item_values[1])
                    except:
                        pass
                logger.debug(f"Selected files: {selected_filenames}")

        except Exception as e:
            logger.error(f"Error in select_all: {str(e)}", exc_info=True)

    def deselect_all(self):
        """Deselect all items in the file list"""
        try:
            # Get all items in the file list
            items = self.file_list.get_children()
            logger.info(f"Deselecting all {len(items)} files")

            # Update each item's checkbox and selection state
            for item in items:
                # Update checkbox display
                current_values = list(self.file_list.item(item)['values'])
                current_values[0] = ""  # Clear checkbox
                self.file_list.item(item, values=current_values)

            # Clear selection tracking
            self.selected_files.clear()
            self.item_url_map.clear()
            logger.info("Deselected all files")

        except Exception as e:
            logger.error(f"Error in deselect_all: {str(e)}", exc_info=True)

    def start_downloads(self):
        """Start downloading selected files"""
        try:
            # Get files that are checked and not complete
            selected_files = []
            for item in self.file_list.get_children():
                values = self.file_list.item(item)['values']
                if values[0] == "✓":  # If checkbox is checked
                    filename = values[1]
                    url = next((url for url, info in self.file_info.items()
                              if info['filename'] == filename), None)
                    if url and self.file_info[url]['status'] not in ['Complete', 'Downloading']:
                        selected_files.append((url, filename))

            if not selected_files:
                logger.warning("No files selected for download or all selected files are already complete/downloading")
                messagebox.showwarning("No Selection", "Please select files to download (completed files are skipped).")
                return

            logger.info(f"Starting downloads for {len(selected_files)} files")

            # Allow downloads to proceed
            self.paused.set()

            # Update status of all selected files to Queued
            with self.lock:
                for url, _ in selected_files:
                    if url in self.file_info:
                        # Only update status if not already downloading or complete
                        current_status = self.file_info[url]['status']
                        if current_status not in ['Downloading', 'Complete']:
                            self.file_info[url]['status'] = 'Queued'
                            self.file_info[url]['retry_count'] = 0
                            self.update_file_list(url)

                        # Queue file for download if not already in active downloads
                        if url not in self.active_downloads:
                            self.download_queue.put((url, self.file_info[url]['filename']))
                            logger.info(f"Queued file for download: {self.file_info[url]['filename']}")

            # Ensure worker threads are running
            worker_count = self.ensure_workers_running()
            logger.info(f"Download workers running: {worker_count}")

            # Force an immediate UI refresh
            self.master.after(10, self.refresh_all_file_statuses)

        except Exception as e:
            logger.error(f"Error starting downloads: {str(e)}", exc_info=True)
            messagebox.showerror("Error", f"Failed to start downloads: {str(e)}")

    def ensure_workers_running(self):
        """Ensure we have enough worker threads running"""
        try:
            with self.lock:
                # Calculate how many new workers we need
                current = self.current_downloads
                needed = self.max_concurrent_downloads
                to_create = max(0, needed - current)

                if to_create > 0:
                    logger.info(f"Starting {to_create} new worker threads (current: {current}, target: {needed})")

                # Create workers as needed
                for _ in range(to_create):
                    thread = Thread(target=self.download_worker)
                    thread.daemon = True
                    thread.start()
                    self.current_downloads += 1

                return self.current_downloads

        except Exception as e:
            logger.error(f"Error ensuring workers: {e}", exc_info=True)
            return 0

    def download_worker(self):
        """Worker thread for downloading files"""
        worker_id = threading.get_ident()
        logger.info(f"Worker thread {worker_id} started")

        try:
            while True:
                # Check if we should exit (app is closing)
                if not hasattr(self, 'master') or not self.master.winfo_exists():
                    logger.info(f"Worker {worker_id} detected application closing, exiting")
                    break

                # Check if downloads are paused - sleep briefly and continue the loop
                if not self.paused.is_set():
                    time.sleep(0.1)
                    continue

                # Try to get a file from the queue with timeout
                try:
                    url, filename = self.download_queue.get(timeout=0.5)
                except queue.Empty:
                    # No files in queue, wait briefly and try again
                    time.sleep(0.1)
                    continue

                logger.debug(f"Worker {worker_id} got file from queue: {filename}")

                # Check if this file is already being downloaded
                skip_file = False
                with self.lock:
                    if url in self.active_downloads:
                        logger.debug(f"File {filename} is already being downloaded, skipping")
                        skip_file = True
                    else:
                        # Mark file as being downloaded
                        self.active_downloads.add(url)

                        # Update status in file_info
                        if url in self.file_info:
                            self.file_info[url]['status'] = 'Downloading'

                # Skip this file if already being downloaded
                if skip_file:
                    self.download_queue.task_done()
                    continue

                # Update UI outside of lock
                self.master.after(0, lambda u=url: self.update_file_list(u))

                # Download the file - this can take a while
                try:
                    self.download_file(url)
                except Exception as e:
                    logger.error(f"Error in worker {worker_id} downloading {filename}: {e}", exc_info=True)
                    # Mark file as having an error - updating UI will happen in the finally block
                    with self.lock:
                        if url in self.file_info:
                            self.file_info[url]['status'] = 'Error'
                            self.file_info[url]['error'] = str(e)

                finally:
                    # Always mark file as no longer being downloaded
                    with self.lock:
                        if url in self.active_downloads:
                            self.active_downloads.remove(url)
                        self.download_queue.task_done()

                    # Update UI with final status
                    self.master.after(0, lambda u=url: self.update_file_list(u))

        except Exception as e:
            logger.error(f"Worker {worker_id} thread exiting due to error: {str(e)}", exc_info=True)

        finally:
            # Decrement the worker count when the thread exits
            with self.lock:
                self.current_downloads -= 1
                logger.info(f"Worker {worker_id} exiting. Remaining workers: {self.current_downloads}")

    def pause_downloads(self):
        """Pause all active downloads"""
        try:
            logger.info("Pausing all downloads...")

            # Clear the paused flag to signal workers to pause
            # This needs to happen BEFORE acquiring the lock to prevent deadlock
            self.paused.clear()

            # Use a small delay to let worker threads notice the pause flag
            # This prevents a race condition where we change statuses before workers notice
            self.master.after(50, self._update_paused_statuses)

            logger.info("Paused all active downloads")

        except Exception as e:
            logger.error(f"Error pausing downloads: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to pause downloads: {str(e)}")

    def _update_paused_statuses(self):
        """Update status of downloading files to paused - called after a short delay"""
        try:
            paused_count = 0
            with self.lock:
                for url in self.file_info:
                    if self.file_info[url]['status'] == 'Downloading':
                        self.file_info[url]['status'] = 'Paused'
                        paused_count += 1

            # Update UI outside of lock
            self.refresh_all_file_statuses()

            if paused_count == 0:
                logger.info("No active downloads to pause")
            else:
                logger.info(f"Paused {paused_count} active downloads")

        except Exception as e:
            logger.error(f"Error updating paused statuses: {e}", exc_info=True)

    def resume_downloads(self):
        """Resume paused downloads"""
        try:
            logger.info("Resuming downloads...")

            # Set the paused flag to allow downloads to proceed
            # This needs to happen BEFORE acquiring the lock to prevent deadlock
            self.paused.set()

            # Use a small delay to let worker threads notice the resume flag
            self.master.after(50, self._update_resumed_statuses)

        except Exception as e:
            logger.error(f"Error resuming downloads: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to resume downloads: {str(e)}")

    def _update_resumed_statuses(self):
        """Update status of paused files to queued - called after a short delay"""
        try:
            files_resumed = 0
            queued_files = 0

            with self.lock:
                # First update status of paused files to queued
                for url in self.file_info:
                    if self.file_info[url]['status'] == 'Paused':
                        self.file_info[url]['status'] = 'Queued'

                        # Re-add to download queue if not already in active downloads
                        if url not in self.active_downloads:
                            self.download_queue.put((url, self.file_info[url]['filename']))
                            files_resumed += 1

                # Then check for any queued files that need to be started
                for url in self.file_info:
                    if self.file_info[url]['status'] == 'Queued' and url not in self.active_downloads:
                        self.download_queue.put((url, self.file_info[url]['filename']))
                        queued_files += 1

            # Start worker threads if needed - outside of lock
            worker_count = self.ensure_workers_running()

            # Update UI outside of lock
            self.refresh_all_file_statuses()

            if files_resumed > 0:
                logger.info(f"Resumed {files_resumed} paused downloads")
            if queued_files > 0:
                logger.info(f"Added {queued_files} queued files to download queue")
            logger.info(f"Download workers running: {worker_count}")

        except Exception as e:
            logger.error(f"Error updating resumed statuses: {e}", exc_info=True)

    def refresh_all_file_statuses(self):
        """Force refresh of all file statuses in the UI"""
        try:
            for url in self.file_info:
                self.update_file_list(url)
        except Exception as e:
            logger.error(f"Error refreshing file statuses: {e}", exc_info=True)

    def download_next_file(self):
        with self.lock:
            if self.current_downloads >= self.max_concurrent_downloads:
                return

            if self.download_queue.empty():
                return

            if not self.paused.is_set():
                return

            _, url = self.download_queue.get()
            self.current_downloads += 1
            self.active_downloads.add(url)

            thread = Thread(target=self.download_file, args=(url,))
            thread.start()

            self.master.after(100, self.download_next_file)

    def download_file(self, url):
        """Download a file from the given URL with improved progress tracking and error handling"""
        try:
            # Get file info with proper locking
            with self.lock:
                if url not in self.file_info:
                    logger.error(f"URL {url} not found in file_info")
                    return False

                info = self.file_info[url]
                filename = info['filename']
                local_filename = os.path.join(self.destination_folder, filename)

                # Initialize tracking data if not present
                if 'start_time' not in info:
                    info['start_time'] = time.time()
                if 'last_update_time' not in info:
                    info['last_update_time'] = time.time()
                if 'last_update_size' not in info:
                    info['last_update_size'] = 0
                if 'retry_count' not in info:
                    info['retry_count'] = 0

                # Update status to show we're starting
                info['status'] = 'Initializing'

            # Force UI update immediately
            self.update_file_list(url)

            # Check if file already exists and is complete
            total_size = info.get('total_size', 0)
            if os.path.exists(local_filename) and total_size > 0:
                file_size = os.path.getsize(local_filename)
                if file_size == total_size:
                    with self.lock:
                        info.update({
                            'status': 'Complete',
                            'progress': 100,
                            'size_on_disk': file_size,
                            'speed': 0,
                            'eta': 0
                        })
                    self.update_file_list(url)
                    logger.info(f"File {filename} already complete")
                    return True

            # Wait for total_size to be available if needed
            if total_size == 0:
                with self.lock:
                    info['status'] = 'Waiting for size info'
                self.update_file_list(url)

                # Try to fetch size if not yet available
                response = requests.head(url, allow_redirects=True)
                if 'content-length' in response.headers:
                    total_size = int(response.headers['content-length'])
                    with self.lock:
                        info['total_size'] = total_size

                # If we still don't have size, we'll log but continue
                if total_size == 0:
                    logger.warning(f"Could not determine size for {filename}")

            # Setup for download with proper retry handling
            retry_count = 0
            max_retries = self.max_retries

            while retry_count <= max_retries:
                try:
                    # Update status to show retry attempt if needed
                    if retry_count > 0:
                        with self.lock:
                            info['status'] = f"Retrying ({retry_count}/{max_retries})"
                            info['retry_count'] = retry_count
                        self.update_file_list(url)
                        logger.info(f"Retry #{retry_count} for {filename}")

                    # Check for partial download to resume
                    downloaded_size = 0
                    headers = {'User-Agent': 'UltraVerboseDownloaderer/1.0'}

                    mode = 'wb'
                    if os.path.exists(local_filename):
                        downloaded_size = os.path.getsize(local_filename)
                        if downloaded_size > 0:
                            headers['Range'] = f'bytes={downloaded_size}-'
                            mode = 'ab'
                            logger.info(f"Resuming download of {filename} from {self.format_size(downloaded_size)}")

                    # First verify the file is available
                    # Disable SSL verification for USGS servers
                    verify_ssl = not ('rockyweb.usgs.gov' in url or 'usgs.gov' in url)

                    with requests.head(url, headers=headers, timeout=30, allow_redirects=True, verify=verify_ssl) as head_response:
                        head_response.raise_for_status()

                        # Verify expected total size from server
                        server_size = int(head_response.headers.get('content-length', 0))
                        if 'content-range' in head_response.headers:
                            # Extract total size from content-range
                            content_range = head_response.headers['content-range']
                            if '/' in content_range:
                                server_total = int(content_range.split('/')[-1])
                                if total_size > 0 and server_total != total_size:
                                    logger.warning(f"Server reported size {server_total} differs from expected size {total_size}")
                                    total_size = server_total
                        elif total_size == 0 and server_size > 0:
                            total_size = server_size

                        with self.lock:
                            info['total_size'] = total_size

                    # Start the actual download
                    with self.lock:
                        info['status'] = 'Downloading'
                    self.update_file_list(url)

                    # Disable SSL verification for USGS servers
                    verify_ssl = not ('rockyweb.usgs.gov' in url or 'usgs.gov' in url)

                    # Get the response
                    response = requests.get(url, headers=headers, stream=True, timeout=30, verify=verify_ssl)
                    response.raise_for_status()

                    # Process the response
                    with response:

                        # Get content length for this response
                        content_length = int(response.headers.get('content-length', 0))
                        if content_length == 0 and response.status_code == 206:
                            # Handle case where server doesn't provide content-length for range requests
                            expected_remaining = total_size - downloaded_size
                            logger.info(f"Server didn't provide content-length. Expected remaining: {self.format_size(expected_remaining)}")

                        # If we're getting the whole file at once, make sure we have the correct total size
                        if response.status_code == 200 and content_length > 0:
                            total_size = content_length
                            with self.lock:
                                info['total_size'] = total_size

                        # Open file for writing
                        with open(local_filename, mode) as f:
                            chunk_size = 8192  # 8KB chunks
                            for chunk in response.iter_content(chunk_size=chunk_size):
                                if chunk:
                                    # Check if download should be paused
                                    if not self.paused.is_set():
                                        # Update status without holding the lock for too long
                                        with self.lock:
                                            info['status'] = 'Paused'

                                        # Update UI outside the lock
                                        self.master.after(0, lambda u=url: self.update_file_list(u))

                                        # Wait for pause to be cleared - sleep in small increments
                                        # to allow quick response when unpaused
                                        while not self.paused.is_set():
                                            # Check for cancel during pause
                                            if url not in self.active_downloads:
                                                logger.info(f"Download cancelled while paused: {filename}")
                                                return False
                                            time.sleep(0.1)

                                        # Once unpaused, update status back to Downloading
                                        with self.lock:
                                            info['status'] = 'Downloading'
                                        self.master.after(0, lambda u=url: self.update_file_list(u))

                                    # Check if download was cancelled
                                    if url not in self.active_downloads:
                                        logger.info(f"Download cancelled: {filename}")
                                        with self.lock:
                                            info['status'] = 'Cancelled'
                                        self.master.after(0, lambda u=url: self.update_file_list(u))
                                        return False

                                    # Write chunk and update progress
                                    f.write(chunk)
                                    downloaded_size += len(chunk)
                                    self.update_progress(url, downloaded_size, total_size)

                        # Verify final size
                        final_size = os.path.getsize(local_filename)
                        if total_size > 0 and final_size != total_size:
                            logger.warning(f"Download completed but size mismatch: {self.format_size(final_size)} vs expected {self.format_size(total_size)}")

                            # If we're very close (within 0.1%), consider it complete anyway
                            if abs(final_size - total_size) / total_size < 0.001:
                                logger.info(f"Size difference of {abs(final_size - total_size)} bytes is within tolerance, marking as complete")
                                final_status = 'Complete'
                            else:
                                # Not close enough - retry or fail
                                raise Exception(f"Size mismatch: {self.format_size(final_size)} vs expected {self.format_size(total_size)}")
                        else:
                            final_status = 'Complete'

                        # Mark as complete
                        with self.lock:
                            info.update({
                                'status': final_status,
                                'progress': 100,
                                'size_on_disk': final_size,
                                'speed': 0,
                                'eta': 0,
                                'end_time': time.time()
                            })
                        self.update_file_list(url)
                        logger.info(f"Download completed: {filename} - Size: {self.format_size(final_size)}")

                        return True

                except Exception as e:
                    retry_count += 1
                    logger.error(f"Download error: {str(e)}", exc_info=True)

                    # Check if we should retry
                    if retry_count <= max_retries:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        logger.warning(f"Will retry download in {wait_time}s: {filename}")

                        with self.lock:
                            info.update({
                                'status': f'Retrying ({retry_count}/{max_retries})',
                                'error': str(e)
                            })
                        self.update_file_list(url)
                        time.sleep(wait_time)
                    else:
                        with self.lock:
                            info.update({
                                'status': 'Failed',
                                'error': str(e),
                                'retry_count': retry_count,
                                'end_time': time.time()
                            })
                        self.update_file_list(url)
                        logger.error(f"Download failed after {max_retries} retries: {filename}")
                        return False

        except Exception as e:
            logger.error(f"Critical error in download_file: {str(e)}", exc_info=True)
            with self.lock:
                if url in self.file_info:
                    self.file_info[url].update({
                        'status': 'Error',
                        'error': str(e),
                        'end_time': time.time()
                    })
            self.update_file_list(url)
            return False

    def update_progress(self, url, downloaded_size, total_size):
        """Update download progress with speed and ETA calculations"""
        try:
            # Make a copy of needed info under the lock
            with self.lock:
                if url not in self.file_info:
                    return

                info = self.file_info[url]
                current_time = time.time()

                # Initialize progress tracking fields if missing
                if 'last_update_time' not in info:
                    info.update({
                        'last_update_time': current_time,
                        'last_update_size': downloaded_size,
                        'speed': 0,
                        'eta': 0,
                        'last_progress': 0
                    })

                # Calculate progress ensuring it never decreases
                if total_size > 0:
                    new_progress = min(100.0, (downloaded_size / total_size) * 100)
                    progress = max(new_progress, info.get('last_progress', 0))
                    info['progress'] = progress
                    info['last_progress'] = progress
                else:
                    progress = 0

                # Calculate speed and ETA with smoothing - only update every 100ms
                time_diff = current_time - info['last_update_time']
                if time_diff >= 0.1:  # Update speed every 100ms
                    size_diff = max(0, downloaded_size - info['last_update_size'])  # Ensure positive difference

                    # Calculate new speed with smoothing
                    current_speed = size_diff / time_diff if time_diff > 0 else 0
                    if 'speed' not in info or info['speed'] == 0:
                        speed = current_speed
                    else:
                        # Apply exponential smoothing
                        alpha = 0.3  # Smoothing factor
                        speed = alpha * current_speed + (1 - alpha) * info['speed']

                    # Ensure speed is never negative
                    speed = max(0, speed)

                    # Calculate ETA based on smoothed speed
                    remaining_bytes = total_size - downloaded_size
                    if speed > 0 and remaining_bytes > 0:
                        eta = remaining_bytes / speed
                    else:
                        eta = 0

                    # Update file info
                    info.update({
                        'size_on_disk': downloaded_size,
                        'total_size': total_size,
                        'speed': speed,
                        'eta': eta,
                        'last_update_time': current_time,
                        'last_update_size': downloaded_size
                    })

                    # We've updated fields, so schedule a UI update
                    should_update_ui = True
                else:
                    # Just update the basic fields but don't refresh UI yet
                    info.update({
                        'size_on_disk': downloaded_size,
                        'progress': progress
                    })
                    should_update_ui = False

            # Update UI outside of lock
            if should_update_ui:
                # Always use master.after to update UI
                self.master.after(0, lambda u=url: self.update_file_list(u))

        except Exception as e:
            logger.error(f"Error updating progress: {str(e)}", exc_info=True)

    def verify_and_update_metadata(self, url, local_filename):
        """Verify and update metadata for downloaded LIDAR file"""
        try:
            self.log(f"Verifying and updating metadata for {local_filename}", logging.INFO)

            # Extract project name from filename
            filename = os.path.basename(local_filename)
            from metadata import get_project_name
            project_name = get_project_name(filename)

            # Get item data from url
            item = None
            for u, i in self.urls:
                if u == url:
                    item = i
                    break

            if not item:
                self.log(f"Could not find item data for {url}", logging.WARNING)
                return

            # Check if we have a ProjectMetadata instance
            if not hasattr(self, 'project_metadata'):
                from metadata import ProjectMetadata
                self.project_metadata = ProjectMetadata()

            # Update metadata
            self.log(f"Updating metadata for project {project_name}", logging.INFO)
            self.project_metadata.add_project(project_name, item)

            # Validate metadata
            is_valid, missing_fields = self.project_metadata.validate_metadata(project_name)
            if not is_valid:
                self.log(f"Metadata for {project_name} is incomplete. Missing: {missing_fields}", logging.WARNING)
            else:
                self.log(f"Metadata for {project_name} is complete", logging.INFO)

            # Update tower_parameters.json
            self.project_metadata._update_tower_parameters(project_name)
            self.log(f"Updated tower_parameters.json with metadata for {project_name}", logging.INFO)

            # Update the local file path in tower_parameters.json
            self.update_local_file_path(project_name, local_filename)

        except Exception as e:
            self.log(f"Error verifying metadata: {str(e)}", logging.ERROR)

    def update_local_file_path(self, project_name, local_filename):
        """Update the local file path in tower_parameters.json"""
        try:
            # Get absolute path
            abs_path = os.path.abspath(local_filename)
            self.log(f"Updating local file path for {project_name} to {abs_path}", logging.INFO)

            # Read existing tower_parameters.json
            try:
                with open('tower_parameters.json', 'r') as f:
                    tower_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                self.log(f"Error reading tower_parameters.json: {e}", logging.ERROR)
                return

            # Update the local file path
            if 'lidar_data' in tower_data and project_name in tower_data['lidar_data']:
                tower_data['lidar_data'][project_name]['local_file_path'] = abs_path

                # Also update file format information if available
                if os.path.exists(abs_path):
                    file_size = os.path.getsize(abs_path)
                    file_ext = os.path.splitext(abs_path)[1].lower()

                    if 'format' not in tower_data['lidar_data'][project_name]:
                        tower_data['lidar_data'][project_name]['format'] = {}

                    tower_data['lidar_data'][project_name]['format']['size_bytes'] = file_size
                    tower_data['lidar_data'][project_name]['format']['extension'] = file_ext

                    # Add download timestamp
                    tower_data['lidar_data'][project_name]['download_timestamp'] = datetime.now().isoformat()

                # Write to a temporary file first, then move it to the final location
                temp_file = get_temp_file(suffix=".json", prefix="tower_params_")
                with open(temp_file, 'w') as f:
                    json.dump(tower_data, f, indent=2)

                # Verify the JSON is valid
                try:
                    with open(temp_file, 'r') as f:
                        json.load(f)  # This will raise an exception if JSON is invalid

                    # Replace the original file with the temporary file
                    shutil.copy2(temp_file, 'tower_parameters.json')
                    os.remove(temp_file)  # Clean up temp file

                    self.log(f"Successfully updated local file path for {project_name}", logging.INFO)
                except Exception as json_error:
                    self.log(f"Error validating JSON: {json_error}", logging.ERROR)
                    os.remove(temp_file)  # Clean up invalid temp file
                    return
            else:
                self.log(f"Project {project_name} not found in tower_parameters.json", logging.WARNING)

        except Exception as e:
            self.log(f"Error updating local file path: {str(e)}", logging.ERROR)

    def verify_file(self, url, local_filename):
        try:
            checksum = hashlib.sha256()
            with open(local_filename, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    checksum.update(chunk)

            if checksum.hexdigest() == self.file_info[url]['checksum']:
                self.file_info[url]['status'] = 'Downloaded and Verified'
                self.log(f"File {local_filename} verified successfully.")
            else:
                self.file_info[url]['status'] = 'Checksum Mismatch'
                self.log(f"File {local_filename} verification failed: Checksum mismatch.", level=logging.ERROR)
            self.update_file_list(url)
        except Exception as e:
            self.file_info[url]['status'] = f"Error: {e}"
            self.log(f"Error verifying file {local_filename}: {e}", level=logging.ERROR)
            self.update_file_list(url)

    def cancel_selected(self):
        for item in list(self.selected_for_download):
            values = self.file_list.item(item)['values']
            filename = values[1]
            url = next((url for url, fname in self.urls if fname == filename), None)
            if url:
                self.file_info[url]['status'] = 'Cancelled'
                self.update_file_list(url)
            self.selected_for_download.discard(item)
            self.file_list.item(item, tags=('unchecked',))
            self.file_list.set(item, 'Select', '')

    def choose_destination(self):
        """Open a dialog to select the download destination folder"""
        folder = filedialog.askdirectory()
        if folder:
            self.destination_folder = folder
            self.destination_path.delete(0, tk.END)
            self.destination_path.insert(0, self.destination_folder)
            logger.info(f"Destination folder set to: {self.destination_folder}")

            # Check for completed files in new destination
            self.check_completed_files()

    def on_closing(self):
        if self.active_downloads:
            if messagebox.askokcancel("Quit", "Active downloads are in progress. Are you sure you want to quit?"):
                self.master.quit()
        else:
            self.master.quit()

    def remove_selected(self):
        selected_items = [item for item in self.file_list.get_children() if 'checked' in self.file_list.item(item, "tags")]
        if not selected_items:
            messagebox.showwarning("No Selection", "Please select files to remove.")
            return

        for item in selected_items:
            values = self.file_list.item(item)['values']
            filename = values[1]  # Filename is the second column
            url = next((url for url, fname in self.urls if fname == filename), None)
            if url:
                self.urls = [(u, f) for u, f in self.urls if u != url]
                del self.file_info[url]
            self.file_list.delete(item)

        self.log(f"Removed {len(selected_items)} files from the download list.")

    def remove_all(self):
        if messagebox.askyesno("Remove All", "Are you sure you want to remove all files from the download list?"):
            self.file_list.delete(*self.file_list.get_children())
            self.urls.clear()
            self.file_info.clear()
            self.log("Removed all files from the download list.")

    def infinite_retry(self):
        """Continuously retry incomplete downloads until they complete"""
        try:
            # Find all items that are not complete
            incomplete_items = []
            for url, info in self.file_info.items():
                if info['status'] not in ['Complete', 'Downloaded']:
                    incomplete_items.append((url, info))

            if not incomplete_items:
                logger.info("No incomplete downloads to retry")
                messagebox.showinfo("Infinite Retry", "No incomplete downloads to retry.")
                return

            logger.info(f"Setting up infinite retry for {len(incomplete_items)} incomplete downloads")

            # Set max_retries to a very high number to enable "infinite" retries
            self.max_retries = 999999

            for url, info in incomplete_items:
                try:
                    # Reset download state
                    info.update({
                        'status': 'Queued',
                        'progress': 0,
                        'size_on_disk': 0,
                        'error': None,
                        'retry_count': 0,
                        'start_time': datetime.now(),
                        'end_time': None
                    })

                    # Add to download queue
                    self.download_queue.put((url, info['filename']))
                    logger.info(f"Queued {info['filename']} for infinite retry")
                    self.update_file_list(url)

                except Exception as e:
                    logger.error(f"Error setting up infinite retry for {info['filename']}: {e}", exc_info=True)

            # Ensure worker threads are running
            self.ensure_workers_running()

            # Set the paused flag to allow downloads to proceed
            self.paused.set()

            messagebox.showinfo("Infinite Retry", f"Started infinite retry for {len(incomplete_items)} downloads. The system will keep retrying until all downloads complete successfully.")

        except Exception as e:
            logger.error(f"Error setting up infinite retry: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to set up infinite retry: {str(e)}")

    def retry_failed(self):
        """Retry failed downloads with proper error handling and retry limits"""
        try:
            # Find all items with Error status
            failed_items = []
            for url, info in self.file_info.items():
                if info['status'].startswith('Error'):
                    failed_items.append((url, info))

            if not failed_items:
                logger.info("No failed downloads to retry")
                messagebox.showinfo("Retry Failed", "No failed downloads to retry.")
                return

            logger.info(f"Retrying {len(failed_items)} failed downloads")

            for url, info in failed_items:
                try:
                    # Check retry count
                    retry_count = info.get('retry_count', 0)
                    if retry_count >= self.max_retries:
                        logger.warning(f"Download {info['filename']} has exceeded maximum retry attempts ({self.max_retries})")
                        continue

                    # Update retry count
                    info['retry_count'] = retry_count + 1

                    # Reset download state
                    info.update({
                        'status': 'Queued',
                        'progress': 0,
                        'size_on_disk': 0,
                        'error': None,
                        'start_time': datetime.now(),
                        'end_time': None
                    })

                    # Schedule retry with delay
                    delay = self.retry_delay * (retry_count + 1)  # Exponential backoff
                    logger.info(f"Scheduling retry for {info['filename']} (Attempt {retry_count + 1}/{self.max_retries}) with delay {delay}s")

                    # Add to download queue after delay
                    self.master.after(
                        delay * 1000,  # Convert to milliseconds
                        lambda u=url, f=info['filename']: self.download_queue.put((u, f))
                    )

                    self.update_file_list(url)

                except Exception as e:
                    logger.error(f"Error scheduling retry for {info['filename']}: {e}", exc_info=True)

            # Ensure worker threads are running
            self.ensure_workers_running()

            messagebox.showinfo("Retry Failed", f"Scheduled {len(failed_items)} failed downloads for retry.")

        except Exception as e:
            logger.error(f"Error retrying failed downloads: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to retry downloads: {str(e)}")

    def retry_all(self):
        """Retry all downloads regardless of their current status"""
        try:
            # Cancel active downloads first
            active_urls = [url for url in self.active_downloads]
            for url in active_urls:
                self.cancel_download(url)

            # Reset and retry all downloads
            for url, info in self.file_info.items():
                # Reset download state
                info.update({
                    'status': 'Queued',
                    'progress': 0,
                    'size_on_disk': 0,
                    'error': None,
                    'retry_count': 0,
                    'start_time': datetime.now(),
                    'end_time': None
                })

                # Schedule download with staggered delay
                delay = len(self.file_info) * 500  # 500ms between each download
                self.master.after(
                    delay,
                    lambda u=url, f=info['filename']: self.download_queue.put((u, f))
                )

                logger.info(f"Scheduled restart for {info['filename']}")
                self.update_file_list(url)

            # Start worker threads if needed
            self.ensure_workers_running()
            logger.info(f"Restarting all {len(self.file_info)} downloads")

        except Exception as e:
            logger.error(f"Error retrying all downloads: {e}", exc_info=True)

    def cancel_download(self, url: str):
        """Cancel an active download"""
        try:
            if url in self.file_info:
                info = self.file_info[url]
                if info['status'] == 'Downloading':
                    self.active_downloads.discard(url)
                    info['status'] = 'Cancelled'
                    logger.info(f"Cancelled download of {info['filename']}")
                    self.update_file_list(url)

        except Exception as e:
            logger.error(f"Error cancelling download: {e}", exc_info=True)

    def on_checkbox_click(self, event):
        """Handle checkbox clicks in the file list"""
        try:
            logger.info("Checkbox click detected")
            region = self.file_list.identify("region", event.x, event.y)
            column = self.file_list.identify_column(event.x)

            logger.debug(f"Click region: {region}, column: {column}")

            if region == "cell" and column == "#1":  # First column (checkbox)
                item = self.file_list.identify_row(event.y)
                if item:
                    logger.info(f"Processing click on item: {item}")

                    # Get current values
                    current_values = list(self.file_list.item(item)['values'])
                    filename = current_values[1]  # Get filename

                    # Toggle checkbox
                    current_values[0] = "✓" if current_values[0] != "✓" else ""
                    self.file_list.item(item, values=current_values)

                    # Update selection tracking
                    if current_values[0] == "✓":
                        self.selected_files.add(item)
                        logger.info(f"Selected file: {filename}")

                        # Map item to URL for easier lookup later
                        for url, info in self.file_info.items():
                            if info['filename'] == filename:
                                self.item_url_map[item] = url
                                break
                    else:
                        self.selected_files.discard(item)
                        logger.info(f"Deselected file: {filename}")

                    logger.info(f"Total selected files: {len(self.selected_files)}")

                    # Debug output of selected files
                    if logger.isEnabledFor(logging.DEBUG):
                        selected_filenames = []
                        for selected_item in self.selected_files:
                            try:
                                item_values = self.file_list.item(selected_item)['values']
                                if item_values and len(item_values) > 1:
                                    selected_filenames.append(item_values[1])
                            except:
                                pass
                        logger.debug(f"Selected files: {selected_filenames}")

        except Exception as e:
            logger.error(f"Error in checkbox click: {str(e)}", exc_info=True)

    def format_speed(self, bytes_per_second):
        """Format download speed in human readable format"""
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} B/s"
        elif bytes_per_second < 1024 * 1024:
            return f"{bytes_per_second/1024:.1f} KB/s"
        elif bytes_per_second < 1024 * 1024 * 1024:
            return f"{bytes_per_second/(1024*1024):.1f} MB/s"
        else:
            return f"{bytes_per_second/(1024*1024*1024):.1f} GB/s"

    def format_eta(self, seconds):
        """Format estimated time remaining"""
        if seconds < 0:
            return "Unknown"
        elif seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds/60)}m {int(seconds%60)}s"
        else:
            hours = int(seconds/3600)
            minutes = int((seconds%3600)/60)
            return f"{hours}h {minutes}m"

    def setup_ui(self):
        """Set up the user interface"""
        # Main paned window
        self.main_paned = ttk.PanedWindow(self.master, orient=tk.VERTICAL)
        self.main_paned.pack(fill=tk.BOTH, expand=True)

        # Upper frame for downloads
        self.upper_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.upper_frame, weight=3)

        # Lower frame for logs
        self.lower_frame = ttk.Frame(self.main_paned)
        self.main_paned.add(self.lower_frame, weight=1)

        # Download Queue Frame
        self.file_list_frame = ttk.LabelFrame(self.upper_frame, text="Download Queue")
        self.file_list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Configure Treeview styles
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)  # Increase row height for better readability

        # Configure tags for different states
        self.file_list = ttk.Treeview(self.file_list_frame, columns=(
            'Select', 'Name', 'File Size', 'Size on Disk', 'Progress', 'Speed', 'ETA', 'Status'
        ), show='headings', style="Treeview")

        self.file_list.tag_configure('error', foreground='red')
        self.file_list.tag_configure('complete', foreground='green')
        self.file_list.tag_configure('downloading', foreground='blue')
        self.file_list.tag_configure('paused', foreground='orange')

        # Configure columns
        self.file_list.heading('Select', text='✓')
        self.file_list.heading('Name', text='Name')
        self.file_list.heading('File Size', text='File Size')
        self.file_list.heading('Size on Disk', text='Size on Disk')
        self.file_list.heading('Progress', text='Progress')
        self.file_list.heading('Speed', text='Speed')
        self.file_list.heading('ETA', text='Time Left')
        self.file_list.heading('Status', text='Status')

        # Set column widths
        self.file_list.column('Select', width=50, anchor='center')
        self.file_list.column('Name', width=300)
        self.file_list.column('File Size', width=100)
        self.file_list.column('Size on Disk', width=100)
        self.file_list.column('Progress', width=100)
        self.file_list.column('Speed', width=100)
        self.file_list.column('ETA', width=100)
        self.file_list.column('Status', width=150)  # Reduced width since we moved speed/ETA

        # Add scrollbar
        scrollbar = ttk.Scrollbar(self.file_list_frame, orient="vertical", command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=scrollbar.set)

        # Pack list and scrollbar
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Create a style for control buttons
        style = ttk.Style()
        style.configure('Control.TButton', padding=(2, 1))

        # Control Panel Frame - use grid layout for better control
        control_panel = ttk.Frame(self.upper_frame)
        control_panel.pack(fill=tk.X, padx=10, pady=5)

        # Configure control panel grid - 2 columns with equal width
        control_panel.columnconfigure(0, weight=1)
        control_panel.columnconfigure(1, weight=1)

        # Selection Frame
        selection_frame = ttk.LabelFrame(control_panel, text="Selection")
        selection_frame.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

        # Configure selection frame grid - 2 columns with equal width
        selection_frame.columnconfigure(0, weight=1)
        selection_frame.columnconfigure(1, weight=1)

        # Selection buttons
        ttk.Button(selection_frame, text="Select All", command=self.select_all,
                  style='Control.TButton').grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(selection_frame, text="Deselect All", command=self.deselect_all,
                  style='Control.TButton').grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # Download Control Frame
        download_frame = ttk.LabelFrame(control_panel, text="Download Control")
        download_frame.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Configure download frame grid - 3 columns with equal width
        download_frame.columnconfigure(0, weight=1)
        download_frame.columnconfigure(1, weight=1)
        download_frame.columnconfigure(2, weight=1)

        # Download control buttons
        ttk.Button(download_frame, text="Start", command=self.start_downloads,
                  style='Control.TButton').grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(download_frame, text="Pause", command=self.pause_downloads,
                  style='Control.TButton').grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(download_frame, text="Resume", command=self.resume_downloads,
                  style='Control.TButton').grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        # Management Frame
        manage_frame = ttk.LabelFrame(self.upper_frame, text="Download Management")
        manage_frame.pack(fill=tk.X, padx=10, pady=5)

        # Create 2x2 grid for management buttons
        # Configure grid columns to be equal width
        for i in range(4):
            manage_frame.columnconfigure(i, weight=1)

        # Management buttons
        ttk.Button(manage_frame, text="Remove Selected", command=self.remove_selected,
                  style='Control.TButton').grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        ttk.Button(manage_frame, text="Remove All", command=self.remove_all,
                  style='Control.TButton').grid(row=0, column=1, padx=2, pady=2, sticky="ew")
        ttk.Button(manage_frame, text="Infinite Retry", command=self.infinite_retry,
                  style='Control.TButton').grid(row=0, column=2, padx=2, pady=2, sticky="ew")
        ttk.Button(manage_frame, text="Retry Failed", command=self.retry_failed,
                  style='Control.TButton').grid(row=0, column=3, padx=2, pady=2, sticky="ew")

        # Destination folder selection - remove this since we added a button in the tools frame
        destination_frame = ttk.LabelFrame(self.upper_frame, text="Output Directory")
        destination_frame.pack(fill=tk.X, padx=10, pady=5)

        # Configure destination frame for grid layout
        destination_frame.columnconfigure(0, weight=10)  # Entry gets more space
        destination_frame.columnconfigure(1, weight=1)   # Button gets less space

        # Add entry for destination path
        self.destination_path = ttk.Entry(destination_frame)
        self.destination_path.grid(row=0, column=0, padx=2, pady=2, sticky="ew")
        self.destination_path.insert(0, self.destination_folder)

        # Add button to select destination
        ttk.Button(destination_frame, text="Browse...",
                  command=self.choose_destination,
                  style='Control.TButton').grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # Button frame for Merger and Synth buttons (above logs)
        tools_frame = ttk.LabelFrame(self.lower_frame, text="Tools")
        tools_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        # Configure tools frame for grid layout
        tools_frame.columnconfigure(0, weight=1)
        tools_frame.columnconfigure(1, weight=1)
        tools_frame.columnconfigure(2, weight=1)
        tools_frame.columnconfigure(3, weight=1)

        # Add Open in Merger button
        merger_button = ttk.Button(
            tools_frame,
            text="Open in Merger",
            command=self.open_in_merger,
            style='Control.TButton'
        )
        merger_button.grid(row=0, column=0, padx=2, pady=2, sticky="ew")

        # Add Open in Synth button
        synth_button = ttk.Button(
            tools_frame,
            text="Open in Synth",
            command=self.open_in_synth,
            style='Control.TButton'
        )
        synth_button.grid(row=0, column=1, padx=2, pady=2, sticky="ew")

        # Add Select Output Directory button
        output_button = ttk.Button(
            tools_frame,
            text="Select Output Directory",
            command=self.choose_destination,
            style='Control.TButton'
        )
        output_button.grid(row=0, column=2, padx=2, pady=2, sticky="ew")

        # Logs Frame
        logs_frame = ttk.LabelFrame(self.lower_frame, text="Logs")
        logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.logs_text = tk.Text(logs_frame, wrap=tk.WORD, height=10)
        self.logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        logs_scrollbar = ttk.Scrollbar(logs_frame, orient="vertical", command=self.logs_text.yview)
        logs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.logs_text.configure(yscrollcommand=logs_scrollbar.set)

        # Bind checkbox clicks
        self.file_list.bind('<Button-1>', self.on_checkbox_click)

        # Start log queue checker
        self.master.after(100, self.check_log_queue)

        # Start periodic UI refresh
        self.start_periodic_refresh()

    def find_python310(self):
        """Find Python 3.10 executable on the system

        Returns:
            str or None: Path to Python 3.10 executable, or None if not found
        """
        # Use Python 3.10 specifically
        python310_paths = [
            '/usr/local/bin/python3.10',
            '/usr/bin/python3.10',
            '/opt/homebrew/bin/python3.10',
            'python3.10'  # Try PATH lookup as fallback
        ]

        # Find the first available Python 3.10 executable
        for path in python310_paths:
            try:
                # Check if the Python executable exists and is version 3.10
                result = subprocess.run([path, '--version'],
                                       capture_output=True,
                                       text=True,
                                       check=False)
                if result.returncode == 0 and '3.10' in result.stdout:
                    logger.info(f"Found Python 3.10 at: {path}")
                    return path
            except Exception:
                continue

        logger.warning("Python 3.10 not found on the system")
        return None

    def run_with_python310(self, script_path, working_dir, app_name):
        """Run a Python script with Python 3.10 if available, otherwise use system Python

        Args:
            script_path (str): Path to the Python script to run
            working_dir (str): Working directory for the subprocess
            app_name (str): Name of the application for logging and messages

        Returns:
            bool: True if launched successfully, False otherwise
        """
        if not os.path.exists(script_path):
            logger.error(f"{app_name} application not found at expected path: {script_path}")
            messagebox.showerror("Error", f"Could not find {app_name} application. Check logs for details.")
            return False

        try:
            # Try to find Python 3.10
            python310_path = self.find_python310()

            if python310_path:
                # Use Python 3.10
                if sys.platform == 'darwin':  # macOS
                    # Use 'nice' to lower process priority on macOS
                    subprocess.Popen(['nice', '-n', '10', python310_path, script_path], cwd=working_dir)
                else:
                    subprocess.Popen([python310_path, script_path], cwd=working_dir)

                logger.info(f"{app_name} application launched successfully with Python 3.10 ({python310_path}).")
                messagebox.showinfo("Success", f"Parameters copied and {app_name} application launched successfully with Python 3.10.")
            else:
                # Fall back to system Python
                if sys.platform == 'darwin':  # macOS
                    subprocess.Popen(['nice', '-n', '10', sys.executable, script_path], cwd=working_dir)
                else:
                    subprocess.Popen([sys.executable, script_path], cwd=working_dir)

                logger.info(f"{app_name} application launched with system Python.")
                messagebox.showinfo("Success", f"Parameters copied and {app_name} application launched. Note: Python 3.10 was not found, using system Python instead.")

            return True
        except Exception as e:
            logger.error(f"Error launching {app_name} with Python 3.10: {e}", exc_info=True)

            try:
                # Fall back to system Python
                if sys.platform == 'darwin':  # macOS
                    subprocess.Popen(['nice', '-n', '10', sys.executable, script_path], cwd=working_dir)
                else:
                    subprocess.Popen([sys.executable, script_path], cwd=working_dir)

                logger.info(f"{app_name} application launched with system Python after failing to use Python 3.10.")
                messagebox.showinfo("Success", f"Parameters copied and {app_name} application launched with system Python (Python 3.10 launch failed).")
                return True
            except Exception as e2:
                logger.error(f"Failed to launch {app_name} with system Python: {e2}", exc_info=True)
                messagebox.showerror("Error", f"Failed to launch {app_name} application: {str(e2)}")
                return False

    def open_in_merger(self):
        """Launch PDAL Merger2 with downloaded LAS/LAZ files using the new utility"""
        try:
            # Import the new merger launcher utility
            from utilities.merger_launcher import launch_merger_from_downloader
            
            logger.info("Launching PDAL Merger2 with downloaded files")
            
            # Use the new utility to launch merger with downloaded files
            # Don't pass project_name - let merger2.py auto-detect projects from filenames
            success = launch_merger_from_downloader(
                downloader_instance=self,
                project_name=None,  # Let merger2.py handle project detection
                auto_analyze=True
            )
            
            if success:
                logger.info("PDAL Merger2 launched successfully via merger_launcher utility")
            else:
                logger.warning("Failed to launch PDAL Merger2 via merger_launcher utility")
                
        except ImportError as e:
            logger.error(f"Failed to import merger_launcher utility: {e}")
            messagebox.showerror("Error", "Merger launcher utility not found. Please check utilities/merger_launcher.py")
        except Exception as e:
            logger.error(f"Error launching PDAL Merger2: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to launch PDAL Merger2: {str(e)}")

    def open_in_synth(self):
        """Copy tower_parameters.json and run the Synth application using the current Python environment"""
        try:
            # Import the safe file operation utilities
            from utilities.file_operation_utils import safe_copy_file

            # Source file path
            source = "tower_parameters.json"
            if not os.path.exists(source):
                logger.error(f"Source file not found: {source}")
                messagebox.showerror("Error", "tower_parameters.json not found. Please create a tower parameters file first.")
                return

            # Define Synth paths using relative paths when possible
            synth_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Synth")
            destination = os.path.join(synth_dir, "tower_parameters.json")
            synth_path = os.path.join(synth_dir, "Synth2.py")

            # Check if Synth directory exists
            if not os.path.exists(synth_dir):
                # Fall back to hardcoded path if relative path doesn't work
                synth_dir = "/Users/master15/Desktop/Software/LOStool/Synth"
                destination = os.path.join(synth_dir, "tower_parameters.json")
                synth_path = os.path.join(synth_dir, "Synth2.py")

                if not os.path.exists(synth_dir):
                    logger.error(f"Synth directory not found: {synth_dir}")
                    messagebox.showerror("Error", "Synth application directory not found.")
                    return

            # Ensure the Synth directory exists
            if not os.path.exists(os.path.dirname(destination)):
                try:
                    os.makedirs(os.path.dirname(destination), exist_ok=True)
                    logger.info(f"Created Synth directory: {os.path.dirname(destination)}")
                except Exception as e:
                    logger.error(f"Failed to create Synth directory: {e}")
                    messagebox.showerror("Error", f"Failed to create Synth directory: {str(e)}")
                    return

            # Use direct file copy instead of safe_copy_file to ensure complete file transfer
            try:
                # First make a backup of the source file
                backup_path = f"{source}.bak"
                shutil.copy2(source, backup_path)
                logger.info(f"Created backup of tower_parameters.json at {backup_path}")

                # Then copy the file directly to the destination
                shutil.copy2(source, destination)
                logger.info(f"tower_parameters.json copied to Synth directory: {destination}")

                # Verify the file was copied correctly
                if os.path.exists(destination):
                    src_size = os.path.getsize(source)
                    dst_size = os.path.getsize(destination)
                    if src_size != dst_size:
                        logger.error(f"File size mismatch: source={src_size}, destination={dst_size}")
                        messagebox.showwarning("Warning", "The tower_parameters.json file may not have been copied completely. File sizes don't match.")
                    else:
                        logger.info(f"File copy verified: {src_size} bytes")
                else:
                    logger.error("Destination file does not exist after copy")
                    messagebox.showerror("Error", "Failed to copy tower_parameters.json to Synth directory.")
                    return
            except Exception as copy_error:
                logger.error(f"Error copying file: {copy_error}")
                messagebox.showerror("Error", f"Failed to copy tower_parameters.json to Synth directory: {str(copy_error)}")
                return

            # Use the current Python executable (same as running dropmap.py)
            current_python = sys.executable
            logger.info(f"Using current Python executable to run Synth: {current_python}")

            # Run Synth with the current Python executable
            try:
                if sys.platform == 'darwin':  # macOS
                    # Use 'nice' to lower process priority on macOS
                    subprocess.Popen(['nice', '-n', '10', current_python, synth_path], cwd=synth_dir)
                else:
                    subprocess.Popen([current_python, synth_path], cwd=synth_dir)

                logger.info(f"Synth application launched with current Python executable ({current_python}).")
                messagebox.showinfo("Success", "Parameters copied and Synth application launched successfully.")
                return True
            except Exception as launch_error:
                logger.error(f"Error launching Synth with current Python: {launch_error}", exc_info=True)
                messagebox.showerror("Error", f"Failed to launch Synth application: {str(launch_error)}")
                return False

        except Exception as e:
            logger.error(f"Failed to open Synth: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to launch Synth application: {str(e)}")
            return False

    def start_periodic_refresh(self):
        """Start periodic UI refresh to keep display up-to-date"""
        try:
            # Refresh all file statuses
            self.refresh_all_file_statuses()

            # Schedule next refresh
            self.master.after(2000, self.start_periodic_refresh)
        except Exception as e:
            logger.error(f"Error in periodic refresh: {e}", exc_info=True)

    def refresh_file_list(self):
        """Refresh the entire file list display"""
        try:
            # Clear existing items
            self.file_list.delete(*self.file_list.get_children())

            # Add all files in current state
            for url, info in self.file_info.items():
                try:
                    # Ensure all required fields exist
                    required_fields = {
                        'filename': info.get('filename', os.path.basename(url)),
                        'status': info.get('status', 'Unknown'),
                        'progress': info.get('progress', 0.0),
                        'total_size': info.get('total_size', 0),
                        'size_on_disk': info.get('size_on_disk', 0),
                        'speed': info.get('speed', 0),
                        'eta': info.get('eta', 0),
                        'last_progress': info.get('last_progress', 0)
                    }

                    # Update info with any missing fields
                    for field, value in required_fields.items():
                        if field not in info:
                            info[field] = value

                    # Ensure progress never decreases
                    current_progress = info['progress']
                    last_progress = info.get('last_progress', 0)
                    smoothed_progress = max(current_progress, last_progress)
                    info['progress'] = min(100.0, smoothed_progress)  # Cap at 100%
                    info['last_progress'] = info['progress']

                    # Format speed text - only show if downloading
                    speed_text = ""
                    if info['status'] == 'Downloading' and info['speed'] > 0:
                        speed_text = self.format_speed(info['speed'])

                    # Format ETA text - only show if downloading and there is remaining data
                    eta_text = ""
                    if info['status'] == 'Downloading' and info['eta'] > 0:
                        eta_text = self.format_eta(info['eta'])

                    # Add to file list
                    item_id = self.file_list.insert("", "end", values=(
                        "",  # Checkbox - always start unchecked in refresh
                        info['filename'],
                        self.format_size(info['total_size']),
                        self.format_size(info['size_on_disk']),
                        f"{info['progress']:.1f}%",
                        speed_text,
                        eta_text,
                        info['status']
                    ))

                    # Apply tags based on status
                    if info['status'] == 'Complete':
                        self.file_list.item(item_id, tags=('complete',))
                    elif info['status'] == 'Downloading':
                        self.file_list.item(item_id, tags=('downloading',))
                    elif info['status'] == 'Paused':
                        self.file_list.item(item_id, tags=('paused',))
                    elif info['status'] in ('Failed', 'Error'):
                        self.file_list.item(item_id, tags=('error',))

                except Exception as e:
                    logger.error(f"Error adding file {url} to list: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"Error refreshing file list: {e}", exc_info=True)

    def clear_queue(self):
        """Clear the download queue and reset state"""
        try:
            # Confirm with the user
            if messagebox.askyesno("Clear Queue", "Are you sure you want to completely clear the download queue and reset all tracking? This will not delete any downloaded files."):
                # Lock to prevent concurrent access
                with self.lock:
                    # Empty queues and trackers
                    self.urls = []
                    self.file_info = {}

                    # Clear the download queue
                    while not self.download_queue.empty():
                        try:
                            self.download_queue.get_nowait()
                            self.download_queue.task_done()
                        except queue.Empty:
                            break

                    # Reset other tracking variables
                    self.active_downloads.clear()
                    self.selected_files.clear()
                    self.item_url_map.clear()

                # Clear the file list in the UI
                self.file_list.delete(*self.file_list.get_children())

                logger.info("Download queue cleared and state reset")
                messagebox.showinfo("Queue Cleared", "Download queue has been cleared and all tracking has been reset.")

        except Exception as e:
            logger.error(f"Error clearing queue: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to clear download queue: {str(e)}")

class QueueHandler(logging.Handler):
    def __init__(self, queue):
        super().__init__()
        self.queue = queue

    def emit(self, record):
        self.queue.put(self.format(record))

