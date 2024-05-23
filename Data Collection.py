import tkinter as tk
from tkinter import filedialog
import win32com.client
import time
from rtlsdr import RtlSdr
import numpy as np
import sys
import os
import json

from datetime import datetime

# Global variables for the GUI inputs
output_folder = ""
grid_width = 5
grid_height = 5
grid_spacing = 2

readings_per_measurement = 5

sdr_sample_rate = 250e3  # Hz
sdr_center_freq = 1.42e9  # Hz
sdr_gain = 40


class StdoutRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.text_widget.see(tk.END)  # Auto-scroll to the end

    def flush(self):
        pass  # This is needed for compatibility with Python's logging system


def connect_to_telescope(progid):
    while True:
        try:
            telescope = win32com.client.Dispatch(progid)
            if not telescope.Connected:
                telescope.Connected = True  # Connect to the telescope if not already connected
            if telescope.Connected:
                print("Telescope connected successfully.")
                return telescope
        except Exception as e:
            print(f"Error connecting to telescope: {e}")
            time.sleep(1)  # Wait for 1 second before retrying


def get_current_position(telescope):
    current_ra = telescope.RightAscension * 15
    current_dec = telescope.Declination
    return current_ra, current_dec


def slew_to(telescope, ra: float, dec: float):
    # Convert RA from hours to degrees
    telescope.TargetRightAscension = ra / 15
    telescope.TargetDeclination = dec
    telescope.SlewToTarget()


def iterative_spiral(center_ra: float, center_dec: float, width: int, height: int, spacing: float):
    x_min, x_max = 0, width - 1
    y_min, y_max = 0, height - 1
    points = []

    # Adjust center point for even dimensions
    adj_center_ra = center_ra - (0.5 * spacing) if width % 2 == 0 else center_ra
    adj_center_dec = center_dec - (0.5 * spacing) if height % 2 == 0 else center_dec

    # Adjust center offset for even dimensions
    ra_offset = (0.5 * spacing) if width % 2 == 0 else 0
    dec_offset = (0.5 * spacing) if height % 2 == 0 else 0

    while x_min <= x_max and y_min <= y_max:
        # Top row
        for x in range(x_min, x_max + 1):
            ra = adj_center_ra + ra_offset + (x - (width - 1) / 2) * spacing
            dec = adj_center_dec + dec_offset + (y_min - (height - 1) / 2) * spacing
            points.append((ra, dec))

        # Right column
        for y in range(y_min + 1, y_max + 1):
            ra = adj_center_ra + ra_offset + (x_max - (width - 1) / 2) * spacing
            dec = adj_center_dec + dec_offset + (y - (height - 1) / 2) * spacing
            points.append((ra, dec))

        # Bottom row
        if y_min != y_max:
            for x in range(x_max - 1, x_min - 1, -1):
                ra = adj_center_ra + ra_offset + (x - (width - 1) / 2) * spacing
                dec = adj_center_dec + dec_offset + (y_max - (height - 1) / 2) * spacing
                points.append((ra, dec))

        # Left column
        if x_min != x_max:
            for y in range(y_max - 1, y_min, -1):
                ra = adj_center_ra + ra_offset + (x_min - (width - 1) / 2) * spacing
                dec = adj_center_dec + dec_offset + (y - (height - 1) / 2) * spacing
                points.append((ra, dec))

        # Contract the bounds for the next layer
        x_min += 1
        x_max -= 1
        y_min += 1
        y_max -= 1

    return points


def setup_sdr(sample_rate, center_frequency, gain):
    sdr = RtlSdr()

    # Configure for Hydrogen Line mostly my guess, you might know better
    sdr.sample_rate = 250e3  # Hz
    sdr.center_freq = 1.42e9  # Hz
    sdr.freq_correction = 1  # PPM
    sdr.gain = 40  # Fixed gain that you might want to mess with, to keep the measurements consistent

    return sdr


def measure_point(sdr, num_samples=1024 * 1024):
    # Read samples from the SDR
    samples = sdr.read_samples(num_samples)

    # Perform Fast Fourier Transform (FFT)
    fft_result = np.fft.fftshift(np.fft.fft(samples))
    # Adjust the frequency array to be centered at the SDR's center frequency
    freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1 / sdr.sample_rate)) + sdr.center_freq

    # Calculate power spectrum (magnitude squared of FFT)
    power_spectrum = np.abs(fft_result) ** 2

    # Find the index of the hydrogen line frequency
    hydrogen_freq_index = np.argmin(np.abs(freqs - 1.42e9))  # 1.42 GHz for hydrogen line

    # Power at the hydrogen line
    hydrogen_line_power = power_spectrum[hydrogen_freq_index]

    # Convert power to decibels (dB)
    hydrogen_line_power_db = 10 * np.log10(hydrogen_line_power + 1e-10)  # Adding a small constant to avoid log(0)

    return hydrogen_line_power_db


def run_grid_scan():
    global output_folder, grid_width, grid_height, grid_spacing, sdr_sample_rate, sdr_center_freq, sdr_gain

    progid = "EQMOD.Telescope"  # Replace with the appropriate progid for your telescope driver
    telescope = connect_to_telescope(progid)

    # Get the current position of the telescope
    initial_ra, initial_dec = get_current_position(telescope)
    print(f"Initial Position - RA: {initial_ra} hours, Dec: {initial_dec} degrees")

    # Generate the spiral grid around the current position
    points = iterative_spiral(initial_ra, initial_dec, grid_width, grid_height, grid_spacing)

    # Setup SDR
    sdr = setup_sdr(sdr_sample_rate, sdr_center_freq, sdr_gain)

    measurements = {'sample_rate': sdr_sample_rate, 'center_frequency': sdr_center_freq, 'gain': sdr_gain,
                    'grid_width': grid_width, 'grid_height': grid_height, 'grid_spacing': grid_spacing}
    readings = []

    def process_point(i):
        if i >= len(points):
            measurements['measurements'] = readings
            save_measurement(measurements, output_folder)
            slew_to(telescope, initial_ra, initial_dec)
            sdr.close()
            print("Grid slew and measurement completed.")
            return

        ra, dec = points[i]
        print(f"Grid Position {i + 1} out of {grid_width*grid_height}: Slewed to RA: {ra}, Dec: {dec}")
        slew_to(telescope, ra, dec)

        def wait_for_slew():
            if telescope.Slewing:
                root.after(1000, wait_for_slew)
            else:
                hydrogen_line_power_db = measure_point(sdr)
                readings.append({'RA': ra, "DEC": dec, "INTENSITY": hydrogen_line_power_db, 'TIME': datetime.now().strftime("%Y-%m-%d_%H-%M-%S")})
                print(f'\nData recorded at position {i + 1} out of {grid_width*grid_height}: \nRA: {ra} hours, \nDec: {dec} degrees, \nHydrogen Line Strength: {hydrogen_line_power_db} dB\n\n')
                root.after(100, process_point, i + 1)

        wait_for_slew()

    process_point(0)


def save_measurement(data: dict, folder: str):
    if not os.path.exists(folder):
        os.makedirs(folder)

    file_path = os.path.join(folder, datetime.now().strftime("%Y-%m-%d_%H-%M-%S.json"))

    # Write the data to the file
    with open(file_path, 'w') as file:
        json.dump(data, file)


def select_output_folder():
    global output_folder
    output_folder = filedialog.askdirectory()
    folder_label.config(text=f"Output Folder: {output_folder}")


def start_scan():
    global grid_width, grid_height, grid_spacing, readings_per_measurement
    grid_width = int(width_entry.get())
    grid_height = int(height_entry.get())
    grid_spacing = float(spacing_entry.get())
    readings_per_measurement = float(avg_time_entry.get())
    run_grid_scan()


# Setup GUI
root = tk.Tk()
root.title("Telescope Grid Scan Controller")

tk.Label(root, text="Grid Width:").grid(row=0, column=0)
width_entry = tk.Entry(root)
width_entry.insert(0, "5")
width_entry.grid(row=0, column=1)

tk.Label(root, text="Grid Height:").grid(row=1, column=0)
height_entry = tk.Entry(root)
height_entry.insert(0, "5")
height_entry.grid(row=1, column=1)

tk.Label(root, text="Grid Spacing (degrees):").grid(row=2, column=0)
spacing_entry = tk.Entry(root)
spacing_entry.insert(0, "2")
spacing_entry.grid(row=2, column=1)

tk.Label(root, text="Averaging Time (seconds): (GOING OVER 2 MAY CAUSE ERRORS)").grid(row=3, column=0)
avg_time_entry = tk.Entry(root)
avg_time_entry.insert(0, "2")
avg_time_entry.grid(row=3, column=1)

folder_button = tk.Button(root, text="Select Output Folder", command=select_output_folder)
folder_button.grid(row=4, column=0, columnspan=2)

folder_label = tk.Label(root, text="Output Folder: Not Selected")
folder_label.grid(row=5, column=0, columnspan=2)

start_button = tk.Button(root, text="Start Scan", command=start_scan)
start_button.grid(row=6, column=0, columnspan=2)

# Text widget to display log messages
log_text = tk.Text(root, height=15, width=50)
log_text.grid(row=7, column=0, columnspan=2)

# Redirect stdout to the text widget
sys.stdout = StdoutRedirector(log_text)

root.mainloop()
