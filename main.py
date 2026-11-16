import threading
import queue
import os
import sys
import json
from pathlib import Path
from converter import convert_cr3
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED

# --------------------------------------------------
# Tcl / Tk configuration
# --------------------------------------------------

python_dir = Path(sys.base_prefix)

tcl_path = python_dir / "tcl" / "tcl8.6"
tk_path = python_dir / "tcl" / "tk8.6"

if tcl_path.exists():
    os.environ["TCL_LIBRARY"] = str(tcl_path)

if tk_path.exists():
    os.environ["TK_LIBRARY"] = str(tk_path)


# --------------------------------------------------
# Imports
# --------------------------------------------------

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog


# --------------------------------------------------
# Application settings
# --------------------------------------------------

SETTINGS_FILE = Path(__file__).parent / "settings.json"


def load_settings():
    """Load saved application settings."""

    default_settings = {
    "output_folder": "",
    "output_format": "JPG",
    "jpeg_quality": 95,
    "png_compression": 1,
    "max_workers": 5
    }

    if not SETTINGS_FILE.exists():
        return default_settings

    try:
        with open(SETTINGS_FILE, "r") as file:
            saved_settings = json.load(file)

        default_settings.update(saved_settings)

    except (json.JSONDecodeError, OSError):
        pass

    return default_settings


def save_settings(settings):
    """Save application settings to JSON."""

    with open(SETTINGS_FILE, "w") as file:
        json.dump(settings, file, indent=4)


# --------------------------------------------------
# Main application
# --------------------------------------------------

def main():

    root = tk.Tk()

    root.title("CR3Converter")

    # Allow the window to resize
    root.resizable(True, True)

    # Minimum window dimensions
    root.minsize(800, 600)

    # Start maximised
    #root.state("zoomed")
    
    # Application data
    settings = load_settings()
    selected_files = set()
    file_status = {}
    
    # Background conversion controls
    conversion_queue = queue.Queue()
    cancel_event = threading.Event()
    conversion_running = False
    admin_unlocked = False

    output_folder = tk.StringVar(
        value=settings["output_folder"]
    )

    output_format = tk.StringVar(
        value=settings["output_format"]
    )

    jpeg_quality = tk.IntVar(
        value=settings["jpeg_quality"]
    )
    
    png_compression = tk.IntVar(
        value=settings["png_compression"]
    )

    max_workers = tk.IntVar(
        value=settings["max_workers"]
    )
    
    filename_prefix = tk.StringVar()
    
    # --------------------------------------------------
    # Main layout
    # --------------------------------------------------

    title = ttk.Label(
        root,
        text="CR3Converter",
        font=("Segoe UI", 22, "bold")
    )
    title.pack(pady=(20, 5))

    subtitle = ttk.Label(
        root,
        text="Convert Canon RAW photos to JPG or PNG"
    )
    subtitle.pack(pady=(0, 20))

    # Create tabs
    notebook = ttk.Notebook(root)
    notebook.pack(
        fill=tk.BOTH,
        expand=True,
        padx=20,
        pady=(0, 20)
    )

    converter_tab = ttk.Frame(notebook, padding=15)
    settings_tab = ttk.Frame(notebook, padding=15)
    admin_tab = ttk.Frame(notebook, padding=15)

    notebook.add(converter_tab, text="Converter")
    notebook.add(settings_tab, text="Settings")
    
    
    def unlock_admin():

        nonlocal admin_unlocked

        passcode = simpledialog.askstring(
            "Admin Access",
            "Enter admin passcode:",
            show="*"
        )

        if passcode is None:
            return

        if passcode == "0807":

            admin_unlocked = True

            if not admin_tab.winfo_ismapped():
                notebook.add(admin_tab, text="Admin")

            notebook.select(admin_tab)

            admin_access_button.config(
                text="Hide Admin Settings",
                command=hide_admin
            )

            messagebox.showinfo(
                "Access granted",
                "Admin settings unlocked."
            )

        else:
            messagebox.showerror(
                "Access denied",
                "Incorrect passcode."
            )


    def hide_admin():

        nonlocal admin_unlocked

        notebook.forget(admin_tab)

        admin_unlocked = False

        admin_access_button.config(
            text="Unlock Admin Settings",
            command=unlock_admin
        )

    # --------------------------------------------------
    # Converter tab functions
    # --------------------------------------------------

    
    def refresh_file_list():

        # Remember the current scroll position.
        scroll_position = file_list.yview()[0]

        # Use the current list order to remember selected files.
        old_sorted_files = sorted(
            selected_files,
            key=lambda path: (path.name.lower(), str(path).lower())
        )

        selected_indices = file_list.curselection()

        previously_selected = {
            old_sorted_files[index]
            for index in selected_indices
            if index < len(old_sorted_files)
        }

        # Clear the existing list.
        file_list.delete(0, tk.END)

        # Sort files consistently.
        sorted_files = sorted(
            selected_files,
            key=lambda path: (path.name.lower(), str(path).lower())
        )

        # Rebuild the list with updated statuses.
        for file_path in sorted_files:

            status = file_status.get(file_path, "Waiting")

            if status == "Converted":
                display_text = f"✓  {file_path.name}"

            elif status == "Failed":
                display_text = f"✕  {file_path.name}"

            elif status == "Converting":
                display_text = f"⏳  {file_path.name}"

            else:
                display_text = f"○  {file_path.name}"

            file_list.insert(tk.END, display_text)

            index = file_list.size() - 1

            if status == "Converted":
                file_list.itemconfig(index, fg="green")

            elif status == "Failed":
                file_list.itemconfig(index, fg="red")

        # Restore the previously selected files.
        for index, file_path in enumerate(sorted_files):

            if file_path in previously_selected:
                file_list.selection_set(index)

        # Restore the scroll position.
        file_list.yview_moveto(scroll_position)

        file_count_label.config(
            text=f"{len(selected_files)} photos selected"
        )
        
        update_conversion_summary()

    def update_conversion_summary():

        completed = sum(
            1 for status in file_status.values()
            if status == "Converted"
        )

        failed = sum(
            1 for status in file_status.values()
            if status == "Failed"
        )

        remaining = len(selected_files) - completed - failed

        conversion_summary_label.config(
            text=(
                f"Completed: {completed}  |  "
                f"Failed: {failed}  |  "
                f"Remaining: {remaining}"
            )
        )
        
    def add_files():

        files = filedialog.askopenfilenames(
            title="Select CR3 photos",
            filetypes=[
                ("Canon RAW files", "*.CR3 *.cr3"),
                ("All files", "*.*")
            ]
        )

        for file in files:

            file_path = Path(file)

            if file_path.suffix.lower() == ".cr3":
                selected_files.add(file_path)

                # Give newly added files their default status.
                file_status[file_path] = "Waiting"

        refresh_file_list()
        
    def add_folder():

        folder = filedialog.askdirectory(
            title="Select folder containing CR3 photos"
        )

        if not folder:
            return

        folder_path = Path(folder)

        cr3_files = [
            file for file in folder_path.rglob("*")
            if file.is_file()
            and file.suffix.lower() == ".cr3"
        ]

        if not cr3_files:
            messagebox.showinfo(
                "No photos found",
                "This folder does not contain any CR3 photos."
            )
            return

        selected_files.update(cr3_files)
        refresh_file_list()

    def clear_files():

        selected_files.clear()
        refresh_file_list()

    
    
    def start_conversion():
        nonlocal conversion_running
        
        files_to_convert = [
            file_path
            for file_path in selected_files
            if file_status.get(file_path) != "Converted"
        ]

        if not selected_files:
            messagebox.showwarning(
                "No files selected",
                "Please add some CR3 files first."
            )
            return

        if not files_to_convert:
            messagebox.showinfo(
                "Nothing to convert",
                "All selected photos have already been converted."
            )
            return
        
        if conversion_running:
            return

        folder = output_folder.get().strip()

        if not folder or not Path(folder).is_dir():
            messagebox.showerror(
                "Invalid destination",
                "Please choose a valid output folder in Settings."
            )
            return

        output_format_value = output_format.get()
        prefix_value = filename_prefix.get().strip()

        # Prevent characters that Windows does not allow in filenames.
        invalid_characters = '<>:"/\\|?*'

        if any(char in invalid_characters or ord(char) < 32 for char in prefix_value):
            messagebox.showerror(
                "Invalid filename prefix",
                'The prefix cannot contain these characters: <>:"/\\|?*'
            )
            return

        try:
            quality_value = jpeg_quality.get()
        except (tk.TclError, ValueError):
            messagebox.showerror(
                "Invalid quality",
                "Please enter a valid JPEG quality."
            )
            return

        if output_format_value == "JPG":
            if not 50 <= quality_value <= 100:
                messagebox.showerror(
                    "Invalid quality",
                    "JPEG quality must be between 50 and 100."
                )
                return

        files_to_convert = sorted(
            files_to_convert,
            key=lambda path: path.name.lower()
        )
        # Reset all selected files to Waiting.
        for file_path in files_to_convert:
            file_status[file_path] = "Waiting"

        refresh_file_list()

        cancel_event.clear()
        conversion_running = True

        convert_button.config(state=tk.DISABLED)
        cancel_button.config(state=tk.NORMAL)

        progress_bar["maximum"] = len(files_to_convert)
        progress_bar["value"] = 0

        status_label.config(
            text=f"Starting conversion of {len(files_to_convert)} photos..."
        )

        worker = threading.Thread(
            target=conversion_worker,
            args=(
                files_to_convert,
                folder,
                output_format_value,
                quality_value,
                png_compression.get(),
                prefix_value,
                settings["max_workers"]
            ),
            daemon=True
        )

        worker.start()
        root.after(100, check_conversion_queue)


    
    
    def conversion_worker(
        files,
        folder,
        output_format_value,
        quality_value,
        png_compression_value,
        prefix_value,
        max_workers_value
    ):
        successful = 0
        failures = []
        completed = 0
        completed_files = set()

        file_iterator = iter(files)

        with ThreadPoolExecutor(max_workers=max_workers_value) as executor:

            pending = {}

            # Submit a new conversion, if cancellation hasn't been requested.
            def submit_next():

                if cancel_event.is_set():
                    return False

                try:
                    file_path = next(file_iterator)
                except StopIteration:
                    return False

                future = executor.submit(
                    convert_cr3,
                    input_path=file_path,
                    output_folder=folder,
                    output_format=output_format_value,
                    jpeg_quality=quality_value,
                    png_compression=png_compression_value,
                    filename_prefix=prefix_value
                )

                pending[future] = file_path

                conversion_queue.put(("converting", file_path))

                return True

            # Initially submit only two photos.
            for _ in range(max_workers_value):
                if not submit_next():
                    break

            # Process completed conversions and refill available worker slots.
            while pending:

                done, _ = wait(
                    pending,
                    return_when=FIRST_COMPLETED
                )

                for future in done:

                    file_path = pending.pop(future)

                    try:
                        future.result()
                        successful += 1
                        success = True

                    except Exception as error:
                        failures.append((file_path.name, str(error)))
                        success = False

                    completed += 1
                    completed_files.add(file_path)

                    conversion_queue.put((
                        "progress",
                        completed,
                        file_path,
                        success
                    ))

                # If cancelled, stop submitting and cancel jobs
                # that haven't started yet.
                if cancel_event.is_set():

                    for future, file_path in list(pending.items()):

                        if future.cancel():
                            pending.pop(future)

                else:

                    # Keep a maximum of two conversions in progress.
                    while len(pending) < max_workers_value:

                        if not submit_next():
                            break

        # Return unfinished photos to the Waiting status.
        for file_path in files:

            if file_path not in completed_files:
                conversion_queue.put(("waiting", file_path))

        conversion_queue.put((
            "finished",
            successful,
            failures,
            cancel_event.is_set()
        ))



    def check_conversion_queue():
        nonlocal conversion_running

        try:
            while True:
                message = conversion_queue.get_nowait()
                
                if message[0] == "converting":

                    _, file_path = message

                    file_status[file_path] = "Converting"
                    refresh_file_list()

                elif message[0] == "waiting":

                    _, file_path = message

                    file_status[file_path] = "Waiting"
                    refresh_file_list()

                elif message[0] == "progress":
                    
                    _, index, file_path, success = message

                    # Find the file associated with this result.
                    file_status[file_path] = (
                        "Converted" if success else "Failed"
                    )

                    refresh_file_list()

                    progress_bar["value"] = index

                    status = "Converted" if success else "Failed"

                    status_label.config(
                        text=f"{status}: {file_path.name} ({index}/{int(progress_bar['maximum'])})"
                    )

                elif message[0] == "finished":
                    _, successful, failures, cancelled = message

                    conversion_running = False

                    convert_button.config(state=tk.NORMAL)
                    cancel_button.config(state=tk.DISABLED)

                    if cancelled:
                        status_label.config(text="Conversion cancelled.")
                    else:
                        status_label.config(text="Conversion completed.")

                    summary = (
                        f"Successful: {successful}\n"
                        f"Failed: {len(failures)}"
                    )

                    if cancelled:
                        summary += "\n\nThe batch was cancelled."

                    if failures:
                        summary += "\n\nFailed files:\n"

                        for filename, error in failures[:10]:
                            summary += f"\n• {filename}: {error}"

                        if len(failures) > 10:
                            summary += (
                                f"\n\nAnd {len(failures) - 10} more failures."
                            )

                    messagebox.showinfo(
                        "Conversion report",
                        summary
                    )

                    return

        except queue.Empty:
            pass

        if conversion_running:
            root.after(100, check_conversion_queue)


    def cancel_conversion():
        if conversion_running:
            cancel_event.set()
            cancel_button.config(state=tk.DISABLED)

            status_label.config(
                text="Cancelling after the current photo..."
            )


    # --------------------------------------------------
    # Converter tab interface
    # --------------------------------------------------

    button_frame = ttk.Frame(converter_tab)
    button_frame.pack(pady=10)

    ttk.Button(
        button_frame,
        text="Add Files",
        command=add_files
    ).pack(side=tk.LEFT, padx=5)

    ttk.Button(
        button_frame,
        text="Add Folder",
        command=add_folder
    ).pack(side=tk.LEFT, padx=5)

    ttk.Button(
        button_frame,
        text="Clear Selection",
        command=clear_files
    ).pack(side=tk.LEFT, padx=5)

    # Selected photos section
    files_frame = ttk.LabelFrame(
        converter_tab,
        text="Selected Photos",
        padding=10
    )
    files_frame.pack(
        fill=tk.BOTH,
        expand=True,
        padx=5,
        pady=15
    )

    file_list = tk.Listbox(
        files_frame,
        font=("Segoe UI", 10),
        selectmode=tk.EXTENDED
    )
    file_list.pack(
        side=tk.LEFT,
        fill=tk.BOTH,
        expand=True
    )

    scrollbar = ttk.Scrollbar(
        files_frame,
        orient=tk.VERTICAL,
        command=file_list.yview
    )
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    file_list.config(
        yscrollcommand=scrollbar.set
    )

    file_count_label = ttk.Label(
        converter_tab,
        text="0 photos selected"
    )
    file_count_label.pack(pady=5)
    
    conversion_summary_label = ttk.Label(
        converter_tab,
        text="Completed: 0  |  Failed: 0  |  Remaining: 0",
        font=("Segoe UI", 10)
    )
    conversion_summary_label.pack(pady=5)
    
    # Conversion progress

    progress_bar = ttk.Progressbar(
        converter_tab,
        orient=tk.HORIZONTAL,
        mode="determinate",
        length=400
    )
    progress_bar.pack(fill=tk.X, padx=5, pady=(15, 5))

    status_label = ttk.Label(
        converter_tab,
        text="Ready to convert."
    )
    status_label.pack(pady=5)

    # Filename prefix

    prefix_frame = ttk.Frame(converter_tab)
    prefix_frame.pack(fill=tk.X, padx=5, pady=(10, 0))

    prefix_label = ttk.Label(
        prefix_frame,
        text="Filename prefix (optional):"
    )
    prefix_label.pack(side=tk.LEFT, padx=(0, 10))

    prefix_entry = ttk.Entry(
        prefix_frame,
        textvariable=filename_prefix,
        width=20
    )
    prefix_entry.pack(side=tk.LEFT)


    # Conversion buttons

    conversion_button_frame = ttk.Frame(converter_tab)
    conversion_button_frame.pack(anchor=tk.E, pady=15)

    convert_button = ttk.Button(
        conversion_button_frame,
        text="Convert Images",
        command=start_conversion
    )
    convert_button.pack(side=tk.LEFT, padx=5)

    cancel_button = ttk.Button(
        conversion_button_frame,
        text="Cancel",
        command=cancel_conversion,
        state=tk.DISABLED
    )
    cancel_button.pack(side=tk.LEFT, padx=5)

    # --------------------------------------------------
    # Settings tab functions
    # --------------------------------------------------
    
    def save_admin_settings():

        try:
            workers_value = max_workers.get()
        except (tk.TclError, ValueError):
            messagebox.showerror(
                "Invalid setting",
                "Please enter a valid number of workers."
            )
            return

        if not 1 <= workers_value <= 10:
            messagebox.showerror(
                "Invalid setting",
                "The number of workers must be between 1 and 10."
            )
            return

        settings["max_workers"] = workers_value

        try:
            save_settings(settings)

            messagebox.showinfo(
                "Settings saved",
                f"Maximum simultaneous conversions set to {workers_value}."
            )

        except OSError as error:
            messagebox.showerror(
                "Save failed",
                f"Could not save admin settings:\n{error}"
            )

    def browse_output_folder():

        folder = filedialog.askdirectory(
            title="Choose output destination",
            initialdir=output_folder.get() or str(Path.home())
        )

        if folder:
            output_folder.set(folder)

    def save_output_settings():

        folder = output_folder.get().strip()
        
        settings["output_format"] = output_format.get()
        settings["jpeg_quality"] = jpeg_quality.get()
        settings["png_compression"] = png_compression.get()

        if not folder:
            messagebox.showwarning(
                "Missing folder",
                "Please choose an output folder first."
            )
            return

        if not Path(folder).is_dir():
            messagebox.showerror(
                "Invalid folder",
                "The selected output folder does not exist."
            )
            return

        settings["output_folder"] = folder

        try:
            save_settings(settings)

            messagebox.showinfo(
                "Settings saved",
                "Your output destination has been saved."
            )

        except OSError as error:
            messagebox.showerror(
                "Save failed",
                f"Could not save settings:\n{error}"
            )

   
    # --------------------------------------------------
    # Settings tab interface
    # --------------------------------------------------

    settings_title = ttk.Label(
        settings_tab,
        text="Conversion Settings",
        font=("Segoe UI", 14, "bold")
    )
    settings_title.pack(anchor=tk.W, pady=(10, 20))

    # Output destination

    output_label = ttk.Label(
        settings_tab,
        text="Output destination:"
    )
    output_label.pack(anchor=tk.W, pady=(0, 8))

    output_frame = ttk.Frame(settings_tab)
    output_frame.pack(fill=tk.X, pady=5)

    output_entry = ttk.Entry(
        output_frame,
        textvariable=output_folder
    )
    output_entry.pack(
        side=tk.LEFT,
        fill=tk.X,
        expand=True,
        padx=(0, 10)
    )

    browse_button = ttk.Button(
        output_frame,
        text="Browse",
        command=browse_output_folder
    )
    browse_button.pack(side=tk.RIGHT)

    # Output format

    format_label = ttk.Label(
        settings_tab,
        text="Output format:"
    )
    format_label.pack(anchor=tk.W, pady=(20, 5))

    format_dropdown = ttk.Combobox(
        settings_tab,
        textvariable=output_format,
        values=["JPG", "PNG"],
        state="readonly",
        width=15
    )
    format_dropdown.pack(anchor=tk.W)

    # JPEG quality

    quality_label = ttk.Label(
        settings_tab,
        text="JPEG quality (50-100):"
    )
    quality_label.pack(anchor=tk.W, pady=(20, 5))

    quality_frame = ttk.Frame(settings_tab)
    quality_frame.pack(anchor=tk.W)

    quality_spinbox = ttk.Spinbox(
        quality_frame,
        from_=50,
        to=100,
        textvariable=jpeg_quality,
        width=8
    )
    quality_spinbox.pack(side=tk.LEFT)

    quality_description = ttk.Label(
        quality_frame,
        text="Higher quality = larger files",
    )
    quality_description.pack(
        side=tk.LEFT,
        padx=10
    )

    # PNG compression

    png_compression_label = ttk.Label(
        settings_tab,
        text="PNG compression:"
    )
    png_compression_label.pack(anchor=tk.W, pady=(20, 5))

    png_compression_dropdown = ttk.Combobox(
        settings_tab,
        textvariable=png_compression,
        values=[1, 3, 6, 9],
        state="readonly",
        width=15
    )
    png_compression_dropdown.pack(anchor=tk.W)

    png_compression_description = ttk.Label(
        settings_tab,
        text="Lower = faster conversion | Higher = smaller files"
    )
    png_compression_description.pack(anchor=tk.W, pady=(5, 0))
    
    # Save settings

    save_button = ttk.Button(
        settings_tab,
        text="Save Settings",
        command=save_output_settings
    )
    save_button.pack(anchor=tk.W, pady=25)

    admin_access_button = ttk.Button(
        settings_tab,
        text="Unlock Admin Settings",
        command=unlock_admin
    )
    admin_access_button.pack(anchor=tk.W, pady=5)
    
    # --------------------------------------------------
    # Admin tab interface
    # --------------------------------------------------

    admin_title = ttk.Label(
        admin_tab,
        text="Admin Settings",
        font=("Segoe UI", 14, "bold")
    )
    admin_title.pack(anchor=tk.W, pady=(10, 20))

    workers_label = ttk.Label(
        admin_tab,
        text="Maximum simultaneous conversions:"
    )
    workers_label.pack(anchor=tk.W, pady=(10, 5))

    workers_spinbox = ttk.Spinbox(
        admin_tab,
        from_=1,
        to=10,
        textvariable=max_workers,
        width=8
    )
    workers_spinbox.pack(anchor=tk.W)

    workers_description = ttk.Label(
        admin_tab,
        text="Choose between 1 and 10 concurrent conversions."
    )
    workers_description.pack(anchor=tk.W, pady=5)
    
    admin_save_button = ttk.Button(
        admin_tab,
        text="Save Admin Settings",
        command=save_admin_settings
    )
    admin_save_button.pack(anchor=tk.W, pady=20)

        # --------------------------------------------------
        # Start application
        # --------------------------------------------------

    root.mainloop()


# --------------------------------------------------
# Application entry point
# --------------------------------------------------

if __name__ == "__main__":
    main()
