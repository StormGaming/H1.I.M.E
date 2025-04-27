import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import numpy as np
import matplotlib.pyplot as plt
import win32com.client
import time
from rtlsdr import RtlSdr
import sys
from datetime import datetime
import traceback
import asyncio

# Global variables for Data Collection
output_folder = ""
grid_width = 5
grid_height = 5
grid_spacing = 2
readings_per_measurement = 5
sdr_sample_rate = 250e3  # Hz
sdr_center_freq = 1.42e9  # Hz
sdr_gain = 40
settle_time = 2  # seconds
telescope_progid = "EQMOD.Telescope"

# List of common ASCOM telescope drivers
TELESCOPE_DRIVERS = [
    "EQMOD.Telescope",
    "EQMOD_SIM.Telescope",
    "ASCOM.Celestron.Telescope",
    "ASCOM.Meade.Telescope",
    "ASCOM.SkyWatcher.Telescope",
    "ASCOM.Simulator.Telescope"
]

# Modes for the combobox
MODES = ["Data Collection", "Image Assembly", "Slew Tool"]

# Utility class for redirecting stdout to GUI
class StdoutRedirector:
    def __init__(self, text_widget, root):
        self.text_widget = text_widget
        self.root = root

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.root.after(0, lambda: self.text_widget.see(tk.END))

    def flush(self):
        pass

# Logging function
def log_error(error_message):
    try:
        log_path = os.path.join(os.path.expanduser("~"), "telescope_error_log.txt")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: {error_message}\n")
    except Exception as e:
        print(f"Failed to write to error log: {str(e)}")

# Telescope control functions
def connect_to_telescope(progid):
    try:
        telescope = win32com.client.Dispatch(progid)
        if not telescope.Connected:
            telescope.Connected = True
        if telescope.Connected:
            print(f"Telescope connected successfully using {progid}.")
            return telescope
        else:
            raise Exception("Telescope connection failed")
    except Exception as e:
        error_msg = f"Error connecting to telescope with {progid}: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

def get_current_position(telescope):
    try:
        if not telescope.Connected:
            raise Exception("Telescope not connected")
        current_ra = telescope.RightAscension * 15  # Convert RA from hours to degrees
        current_dec = telescope.Declination
        return current_ra, current_dec
    except Exception as e:
        error_msg = f"Error getting telescope position: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

def slew_to(telescope, ra: float, dec: float):
    try:
        if not telescope.Connected:
            raise Exception("Telescope not connected")
        telescope.TargetRightAscension = ra / 15  # Convert RA from degrees to hours
        telescope.TargetDeclination = dec
        telescope.SlewToTarget()
    except Exception as e:
        error_msg = f"Error slewing telescope: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

# Data Collection functions
def iterative_spiral(center_ra: float, center_dec: float, width: int, height: int, spacing: float):
    x_min, x_max = 0, width - 1
    y_min, y_max = 0, height - 1
    points = []
    adj_center_ra = center_ra - (0.5 * spacing) if width % 2 == 0 else center_ra
    adj_center_dec = center_dec - (0.5 * spacing) if height % 2 == 0 else center_dec
    ra_offset = (0.5 * spacing) if width % 2 == 0 else 0
    dec_offset = (0.5 * spacing) if height % 2 == 0 else 0

    while x_min <= x_max and y_min <= y_max:
        for x in range(x_min, x_max + 1):
            ra = adj_center_ra + ra_offset + (x - (width - 1) / 2) * spacing
            dec = adj_center_dec + dec_offset + (y_min - (height - 1) / 2) * spacing
            points.append((ra, dec))
        for y in range(y_min + 1, y_max + 1):
            ra = adj_center_ra + ra_offset + (x_max - (width - 1) / 2) * spacing
            dec = adj_center_dec + dec_offset + (y - (height - 1) / 2) * spacing
            points.append((ra, dec))
        if y_min != y_max:
            for x in range(x_max - 1, x_min - 1, -1):
                ra = adj_center_ra + ra_offset + (x - (width - 1) / 2) * spacing
                dec = adj_center_dec + dec_offset + (y_max - (height - 1) / 2) * spacing
                points.append((ra, dec))
        if x_min != x_max:
            for y in range(y_max - 1, y_min, -1):
                ra = adj_center_ra + ra_offset + (x_min - (width - 1) / 2) * spacing
                dec = adj_center_dec + dec_offset + (y - (height - 1) / 2) * spacing
                points.append((ra, dec))
        x_min += 1
        x_max -= 1
        y_min += 1
        y_max -= 1
    return points

def setup_sdr(sample_rate, center_frequency, gain):
    try:
        sdr = RtlSdr()
        sdr.sample_rate = sample_rate
        sdr.center_freq = center_frequency
        sdr.freq_correction = 1  # PPM
        sdr.gain = gain
        return sdr
    except Exception as e:
        error_msg = f"Error setting up SDR: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

def measure_point(sdr, num_samples=1024 * 1024):
    try:
        samples = sdr.read_samples(num_samples)
        fft_result = np.fft.fftshift(np.fft.fft(samples))
        freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1 / sdr.sample_rate)) + sdr.center_freq
        power_spectrum = np.abs(fft_result) ** 2
        hydrogen_freq_index = np.argmin(np.abs(freqs - sdr.center_freq))
        hydrogen_line_power = power_spectrum[hydrogen_freq_index]
        hydrogen_line_power_db = 10 * np.log10(hydrogen_line_power + 1e-10)
        return hydrogen_line_power_db
    except Exception as e:
        error_msg = f"Error measuring point: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

def save_measurement(data: dict, folder: str):
    try:
        if not os.path.exists(folder):
            os.makedirs(folder)
        file_path = os.path.join(folder, datetime.now().strftime("%Y-%m-%d_%H-%M-%S.json"))
        with open(file_path, 'w') as file:
            json.dump(data, file)
    except Exception as e:
        error_msg = f"Error saving measurement: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

def run_grid_scan(root, status_label, start_button):
    global output_folder, grid_width, grid_height, grid_spacing, sdr_sample_rate, sdr_center_freq, sdr_gain, settle_time, telescope_progid
    try:
        # Connect to telescope and get current position
        telescope = connect_to_telescope(telescope_progid)
        initial_ra, initial_dec = get_current_position(telescope)
        print(f"Retrieved initial position - RA: {initial_ra:.2f} degrees, Dec: {initial_dec:.2f} degrees")
        status_label.config(text=f"Initial Position - RA: {initial_ra:.2f} deg, Dec: {initial_dec:.2f} deg")
        root.update_idletasks()

        # Generate grid points centered on current position
        points = iterative_spiral(initial_ra, initial_dec, grid_width, grid_height, grid_spacing)
        sdr = setup_sdr(sdr_sample_rate, sdr_center_freq, sdr_gain)
        measurements = {
            'sample_rate': sdr_sample_rate,
            'center_frequency': sdr_center_freq,
            'gain': sdr_gain,
            'grid_width': grid_width,
            'grid_height': grid_height,
            'grid_spacing': grid_spacing,
            'initial_ra': initial_ra,
            'initial_dec': initial_dec
        }
        readings = []

        def process_point(i):
            if i >= len(points):
                measurements['measurements'] = readings
                save_measurement(measurements, output_folder)
                slew_to(telescope, initial_ra, initial_dec)
                status_label.config(text="Grid scan completed. Returning to initial position.")
                root.update_idletasks()
                print("Grid slew and measurement completed.")
                sdr.close()
                start_button.config(state="normal")
                status_label.config(text="Idle")
                return
            ra, dec = points[i]
            status_label.config(text=f"Slewing to Position {i + 1}/{grid_width*grid_height}: RA: {ra:.2f}, Dec: {dec:.2f}")
            print(f"Grid Position {i + 1} out of {grid_width*grid_height}: Slewing to RA: {ra:.2f} deg, Dec: {dec:.2f} deg")
            root.update_idletasks()
            try:
                slew_to(telescope, ra, dec)
            except Exception as e:
                error_msg = f"Failed to slew to position {i + 1}: {str(e)}"
                print(error_msg)
                log_error(error_msg)
                status_label.config(text="Error: Slew failed. Check log.")
                start_button.config(state="normal")
                messagebox.showerror("Error", error_msg)
                return

            def wait_for_slew(elapsed=0):
                try:
                    if telescope.Slewing and elapsed < 30000:  # Timeout after 30s
                        root.after(100, wait_for_slew, elapsed + 100)
                    elif elapsed >= 30000:
                        error_msg = f"Timeout waiting for slew at position {i + 1}"
                        print(error_msg)
                        log_error(error_msg)
                        status_label.config(text="Error: Slew timeout. Check log.")
                        start_button.config(state="normal")
                        messagebox.showerror("Error", error_msg)
                    else:
                        status_label.config(text=f"Settling for {settle_time}s at Position {i + 1}/{grid_width*grid_height}")
                        root.update_idletasks()
                        # Schedule settle time non-blocking
                        root.after(int(settle_time * 1000), lambda: measure_and_proceed(i))
                except Exception as e:
                    error_msg = f"Error during slew at position {i + 1}: {str(e)}"
                    print(error_msg)
                    log_error(error_msg)
                    status_label.config(text="Error: Operation failed. Check log.")
                    start_button.config(state="normal")
                    messagebox.showerror("Error", error_msg)

            def measure_and_proceed(i):
                try:
                    status_label.config(text=f"Measuring at Position {i + 1}/{grid_width*grid_height}: RA: {ra:.2f}, Dec: {dec:.2f}")
                    root.update_idletasks()
                    hydrogen_line_power_db = measure_point(sdr)
                    readings.append({
                        'RA': ra,
                        'DEC': dec,
                        'INTENSITY': hydrogen_line_power_db,
                        'TIME': datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    })
                    print(f'\nData recorded at position {i + 1} out of {grid_width*grid_height}: \nRA: {ra:.2f} deg, \nDec: {dec:.2f} deg, \nHydrogen Line Strength: {hydrogen_line_power_db:.2f} dB\n\n')
                    root.after(100, process_point, i + 1)
                except Exception as e:
                    error_msg = f"Error during measurement at position {i + 1}: {str(e)}"
                    print(error_msg)
                    log_error(error_msg)
                    status_label.config(text="Error: Operation failed. Check log.")
                    start_button.config(state="normal")
                    messagebox.showerror("Error", error_msg)

            root.after(100, wait_for_slew, 0)

        process_point(0)
    except Exception as e:
        error_msg = f"Error in grid scan: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        log_error(error_msg)
        status_label.config(text="Error occurred. Check log.")
        start_button.config(state="normal")
        messagebox.showerror("Error", f"Scan failed: {str(e)}")

# Image Assembly functions
def extract_data_from_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    measurements = data.get('measurements', [])
    grid_spacing = data.get('grid_spacing', None)
    grid_width = data.get('grid_width', None)
    grid_height = data.get('grid_height', None)

    results = []
    for measurement in measurements:
        ra = measurement.get('RA')
        dec = measurement.get('DEC')
        power = measurement.get('INTENSITY')
        if ra is not None and dec is not None and power is not None:
            results.append((ra, dec, power))
        else:
            raise ValueError("Data format in file is incorrect or missing some values")
    return results, grid_spacing, grid_width, grid_height

def read_data_from_file(file_path):
    data_points = []
    grid_spacings = []
    try:
        measurements, grid_spacing, _, _ = extract_data_from_file(file_path)
        data_points.extend(measurements)
        if grid_spacing is not None:
            grid_spacings.append(grid_spacing)
    except ValueError as e:
        print(f"Skipping file {file_path}: {e}")
    average_spacing = sum(grid_spacings) / len(grid_spacings) if grid_spacings else None
    print(f"Average Grid Spacing: {average_spacing}")
    return data_points, average_spacing

def dB_to_linear(dB):
    return 10 ** (dB / 10)

def linear_to_dB(linear):
    return 10 * np.log10(linear)

def plot_intensity_distribution(power_values):
    plt.figure(figsize=(10, 6))
    plt.hist(power_values, bins=50, color='blue', edgecolor='black')
    plt.title('Distribution of Hydrogen Line Power Intensity')
    plt.xlabel('Intensity (dB)')
    plt.ylabel('Frequency')
    plt.grid(True)
    plt.show()

def generate_image(data_points, grid_spacing):
    ra_values = [ra for ra, dec, power in data_points]
    dec_values = [dec for ra, dec, power in data_points]

    ra_range = max(ra_values) - min(ra_values)
    dec_range = max(dec_values) - min(dec_values)
    grid_width = int(np.ceil(ra_range / grid_spacing)) + 1
    grid_height = int(np.ceil(dec_range / grid_spacing)) + 1

    ra_lin = np.linspace(min(ra_values), max(ra_values), grid_width)
    dec_lin = np.linspace(min(dec_values), max(dec_values), grid_height)

    grid = np.full((grid_height, grid_width), np.nan)

    for (ra, dec, power) in data_points:
        ra_idx = np.searchsorted(ra_lin, ra) - 1
        dec_idx = np.searchsorted(dec_lin, dec) - 1
        if np.isnan(grid[dec_idx, ra_idx]):
            grid[dec_idx, ra_idx] = power
        else:
            grid[dec_idx, ra_idx] = (grid[dec_idx, ra_idx] + power) / 2

    plt.figure(figsize=(10, 8))
    plt.imshow(grid, cmap='viridis', interpolation='nearest', origin='lower',
               extent=[min(ra_values), max(ra_values), min(dec_values), max(dec_values)])
    plt.colorbar(label='Hydrogen Line Power (dB)')
    plt.title('Hydrogen Line Signal Strength Grid')
    plt.xlabel('Right Ascension')
    plt.ylabel('Declination')
    plt.show()

# GUI functions
def select_output_folder(folder_label):
    global output_folder
    try:
        output_folder = filedialog.askdirectory()
        folder_label.config(text=f"Output Folder: {output_folder if output_folder else 'Not Selected'}")
    except Exception as e:
        error_msg = f"Error selecting folder: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        messagebox.showerror("Error", f"Failed to select folder: {str(e)}")

def select_json_file():
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    return file_path

def validate_coordinates(ra_str, dec_str):
    try:
        ra = float(ra_str)
        dec = float(dec_str)
        if not (0 <= ra <= 360):
            raise ValueError("RA must be between 0 and 360 degrees")
        if not (-90 <= dec <= 90):
            raise ValueError("Dec must be between -90 and 90 degrees")
        return ra, dec
    except ValueError as e:
        raise ValueError(f"Invalid coordinates: {str(e)}")

def create_data_collection_frame(parent, root, log_text):
    frame = ttk.LabelFrame(parent, text="Data Collection", padding="5")
    
    # Telescope Settings
    telescope_frame = ttk.LabelFrame(frame, text="Telescope Settings", padding="5")
    telescope_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
    ttk.Label(telescope_frame, text="Telescope Driver:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
    driver_combobox = ttk.Combobox(telescope_frame, values=TELESCOPE_DRIVERS, width=30)
    driver_combobox.set("EQMOD.Telescope")
    driver_combobox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

    # Grid Settings
    grid_frame = ttk.LabelFrame(frame, text="Grid Settings", padding="5")
    grid_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
    ttk.Label(grid_frame, text="Grid Width:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
    width_entry = ttk.Entry(grid_frame, width=15)
    width_entry.insert(0, "5")
    width_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(grid_frame, text="Grid Height:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
    height_entry = ttk.Entry(grid_frame, width=15)
    height_entry.insert(0, "5")
    height_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(grid_frame, text="Grid Spacing (degrees):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
    spacing_entry = ttk.Entry(grid_frame, width=15)
    spacing_entry.insert(0, "2")
    spacing_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(grid_frame, text="Averaging Time (s):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
    avg_time_entry = ttk.Entry(grid_frame, width=15)
    avg_time_entry.insert(0, "2")
    avg_time_entry.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(grid_frame, text="(Max 2s to avoid errors)").grid(row=3, column=2, sticky=tk.W, padx=5, pady=2)
    ttk.Label(grid_frame, text="Settle Time (s):").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
    settle_time_entry = ttk.Entry(grid_frame, width=15)
    settle_time_entry.insert(0, "2")
    settle_time_entry.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

    # SDR Settings
    sdr_frame = ttk.LabelFrame(frame, text="SDR Settings", padding="5")
    sdr_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=5)
    ttk.Label(sdr_frame, text="Center Frequency (Hz):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
    center_freq_entry = ttk.Entry(sdr_frame, width=15)
    center_freq_entry.insert(0, "1420000000")
    center_freq_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(sdr_frame, text="Sample Rate (Hz):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
    sample_rate_entry = ttk.Entry(sdr_frame, width=15)
    sample_rate_entry.insert(0, "250000")
    sample_rate_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(sdr_frame, text="Gain:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
    gain_entry = ttk.Entry(sdr_frame, width=15)
    gain_entry.insert(0, "40")
    gain_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

    # Output Settings
    output_frame = ttk.LabelFrame(frame, text="Output Settings", padding="5")
    output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)
    folder_button = ttk.Button(output_frame, text="Select Output Folder", command=lambda: select_output_folder(folder_label))
    folder_button.grid(row=0, column=0, columnspan=2, pady=5)
    folder_label = ttk.Label(output_frame, text="Output Folder: Not Selected")
    folder_label.grid(row=1, column=0, columnspan=2, pady=5)

    # Control and Status
    control_frame = ttk.Frame(frame)
    control_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)
    start_button = ttk.Button(control_frame, text="Start Scan", command=lambda: start_scan(root, status_label, start_button, width_entry, height_entry, spacing_entry, avg_time_entry, center_freq_entry, sample_rate_entry, gain_entry, settle_time_entry, driver_combobox))
    start_button.grid(row=0, column=0, padx=5)
    status_label = ttk.Label(control_frame, text="Idle")
    status_label.grid(row=0, column=1, padx=5)

    def start_scan(root, status_label, start_button, width_entry, height_entry, spacing_entry, avg_time_entry, center_freq_entry, sample_rate_entry, gain_entry, settle_time_entry, driver_combobox):
        global grid_width, grid_height, grid_spacing, readings_per_measurement, sdr_center_freq, sdr_sample_rate, sdr_gain, settle_time, telescope_progid
        try:
            grid_width = int(width_entry.get())
            grid_height = int(height_entry.get())
            grid_spacing = float(spacing_entry.get())
            readings_per_measurement = float(avg_time_entry.get())
            sdr_center_freq = float(center_freq_entry.get())
            sdr_sample_rate = float(sample_rate_entry.get())
            sdr_gain = float(gain_entry.get())
            settle_time = float(settle_time_entry.get())
            telescope_progid = driver_combobox.get()
            if not telescope_progid:
                raise ValueError("No telescope driver selected")
            if not output_folder:
                raise ValueError("Output folder not selected")
        except ValueError as e:
            error_msg = f"Invalid input values: {str(e)}"
            print(error_msg)
            log_error(error_msg)
            status_label.config(text="Error: Invalid input values")
            messagebox.showerror("Error", error_msg)
            return
        start_button.config(state="disabled")
        status_label.config(text="Starting scan...")
        root.update_idletasks()
        run_grid_scan(root, status_label, start_button)

    return frame

def create_image_assembly_frame(parent, root, log_text):
    frame = ttk.LabelFrame(parent, text="Image Assembly", padding="5")
    select_button = ttk.Button(frame, text="Select JSON File", command=lambda: select_file(root, log_text))
    select_button.grid(row=0, column=0, padx=10, pady=10)
    status_label = ttk.Label(frame, text="Idle")
    status_label.grid(row=1, column=0, padx=10, pady=5)

    def select_file(root, log_text):
        file_path = select_json_file()
        if file_path:
            try:
                status_label.config(text="Processing file...")
                root.update_idletasks()
                data_points, grid_spacing = read_data_from_file(file_path)
                generate_image(data_points, grid_spacing)
                status_label.config(text="Image generated successfully")
            except ValueError as e:
                error_msg = f"Error processing file: {str(e)}"
                print(error_msg)
                log_error(error_msg)
                status_label.config(text="Error: Check log")
                messagebox.showerror("Error", error_msg)
        else:
            status_label.config(text="No file selected")

    return frame

def create_slew_tool_frame(parent, root, log_text):
    frame = ttk.LabelFrame(parent, text="Slew Tool", padding="5")
    
    # Telescope Driver
    ttk.Label(frame, text="Telescope Driver:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
    driver_combobox = ttk.Combobox(frame, values=TELESCOPE_DRIVERS, width=30)
    driver_combobox.set("EQMOD.Telescope")
    driver_combobox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

    # Coordinates
    ttk.Label(frame, text="Right Ascension (degrees):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
    ra_entry = ttk.Entry(frame, width=15)
    ra_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
    ttk.Label(frame, text="Declination (degrees):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
    dec_entry = ttk.Entry(frame, width=15)
    dec_entry.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

    # Control and Status
    control_frame = ttk.Frame(frame)
    control_frame.grid(row=3, column=0, columnspan=2, pady=10)
    slew_button = ttk.Button(control_frame, text="Slew to Coordinates", command=lambda: slew_to_coordinates(root, status_label, slew_button, ra_entry, dec_entry, driver_combobox))
    slew_button.grid(row=0, column=0, padx=5)
    status_label = ttk.Label(control_frame, text="Idle")
    status_label.grid(row=0, column=1, padx=5)

    def slew_to_coordinates(root, status_label, slew_button, ra_entry, dec_entry, driver_combobox):
        try:
            ra_str = ra_entry.get().strip()
            dec_str = dec_entry.get().strip()
            ra, dec = validate_coordinates(ra_str, dec_str)
            telescope_progid = driver_combobox.get()
            if not telescope_progid:
                raise ValueError("No telescope driver selected")
            status_label.config(text="Connecting to telescope...")
            root.update_idletasks()
            telescope = connect_to_telescope(telescope_progid)
            status_label.config(text=f"Slewing to RA: {ra:.2f}, Dec: {dec:.2f}")
            root.update_idletasks()
            slew_to(telescope, ra, dec)

            def wait_for_slew(elapsed=0):
                try:
                    if telescope.Slewing and elapsed < 30000:
                        root.after(100, wait_for_slew, elapsed + 100)
                    elif elapsed >= 30000:
                        error_msg = "Timeout waiting for slew"
                        print(error_msg)
                        log_error(error_msg)
                        status_label.config(text="Error: Slew timeout. Check log.")
                        slew_button.config(state="normal")
                        messagebox.showerror("Error", error_msg)
                    else:
                        status_label.config(text="Slew completed")
                        slew_button.config(state="normal")
                        root.update_idletasks()
                except Exception as e:
                    error_msg = f"Error during slew: {str(e)}"
                    print(error_msg)
                    log_error(error_msg)
                    status_label.config(text="Error: Check log")
                    slew_button.config(state="normal")
                    messagebox.showerror("Error", error_msg)
            slew_button.config(state="disabled")
            root.after(100, wait_for_slew, 0)
        except Exception as e:
            error_msg = f"Error in slew operation: {str(e)}"
            print(error_msg)
            log_error(error_msg)
            status_label.config(text="Error: Check log")
            slew_button.config(state="normal")
            messagebox.showerror("Error", error_msg)

    return frame

def switch_mode(mode, frames, main_frame, canvas):
    for frame in frames.values():
        frame.grid_forget()
    frames[mode].grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    main_frame.update_idletasks()
    canvas.update_idletasks()
    canvas.configure(scrollregion=canvas.bbox("all"))

# Main GUI setup
try:
    print("Initializing GUI...")
    root = tk.Tk()
    root.title("Radio Astronomy Master Controller")
    root.geometry("600x600")
    root.resizable(False, False)
    print("Root window created.")

    # Create a canvas and scrollbar
    canvas = tk.Canvas(root)
    scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)
    print("Canvas and scrollbar configured.")

    # Create a frame inside the canvas
    main_frame = ttk.Frame(canvas, padding="10")
    canvas_frame = canvas.create_window((0, 0), window=main_frame, anchor="nw")
    main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    main_frame.rowconfigure(2, weight=1)
    main_frame.columnconfigure(0, weight=1)
    print("Main frame created.")

    # Mode Selection
    mode_frame = ttk.LabelFrame(main_frame, text="Select Mode", padding="5")
    mode_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
    mode_combobox = ttk.Combobox(mode_frame, values=MODES, width=30, state="readonly")
    mode_combobox.set("Data Collection")
    mode_combobox.grid(row=0, column=0, padx=5, pady=5)
    print("Mode selection configured.")

    # Log Output (placed at the bottom)
    log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
    log_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    log_frame.rowconfigure(0, weight=1)
    log_frame.columnconfigure(0, weight=1)
    log_text = tk.Text(log_frame, height=10, width=60, wrap=tk.WORD)
    log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
    log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    log_text['yscrollcommand'] = log_scrollbar.set
    sys.stdout = StdoutRedirector(log_text, root)
    print("Log output configured.")

    # Mode Frames
    frames = {
        "Data Collection": create_data_collection_frame(main_frame, root, log_text),
        "Image Assembly": create_image_assembly_frame(main_frame, root, log_text),
        "Slew Tool": create_slew_tool_frame(main_frame, root, log_text)
    }
    frames["Data Collection"].grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
    print("Mode frames created.")

    # Bind mode switch
    mode_combobox.bind("<<ComboboxSelected>>", lambda event: switch_mode(mode_combobox.get(), frames, main_frame, canvas))
    print("Mode switch bound.")

    # Update canvas scroll region after initial layout
    root.after(100, lambda: canvas.configure(scrollregion=canvas.bbox("all")))
    print("Canvas scroll region scheduled.")

    root.mainloop()
    print("GUI event loop started.")

except Exception as e:
    error_msg = f"Failed to initialize GUI: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    log_error(error_msg)
    try:
        tk.Tk().withdraw()
        messagebox.showerror("Initialization Error", f"Failed to start GUI: {str(e)}")
    except:
        print("Failed to show error messagebox.")
    sys.exit(1)