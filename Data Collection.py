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
sdr_sample_rate = 250e3  # Hz (default)
sdr_center_freq = 1.42e9  # Hz (default hydrogen line frequency)
sdr_gain = 40  # (default)

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
                telescope.Connected = True
            if telescope.Connected:
                print("Telescope connected successfully.")
                return telescope
        except Exception as e:
            print(f"Error connecting to telescope: {e}")
            time.sleep(1)

def get_current_position(telescope):
    current_ra = telescope.RightAscension * 15
    current_dec = telescope.Declination
    return current_ra, current_dec

def slew_to(telescope, ra: float, dec: float):
    telescope.TargetRightAscension = ra / 15
    telescope.TargetDeclination = dec
    telescope.SlewToTarget()

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
    sdr = RtlSdr()
    sdr.sample_rate = sample_rate
    sdr.center_freq = center_frequency
    sdr.freq_correction = 1  # PPM
    sdr.gain = gain
    return sdr

def measure_point(sdr, num_samples=1024 * 1024):
    samples = sdr.read_samples(num_samples)
    fft_result = np.fft.fftshift(np.fft.fft(samples))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(samples), 1 / sdr.sample_rate)) + sdr.center_freq
    power_spectrum = np.abs(fft_result) ** 2
    hydrogen_freq_index = np.argmin(np.abs(freqs - sdr.center_freq))
    hydrogen_line_power = power_spectrum[hydrogen_freq_index]
    hydrogen_line_power_db = 10 * np.log10(hydrogen_line_power + 1e-10)
    return hydrogen_line_power_db

def run_grid_scan():
    global output_folder, grid_width, grid_height, grid_spacing, sdr_sample_rate, sdr_center_freq, sdr_gain
    progid = "EQMOD.Telescope"
    telescope = connect_to_telescope(progid)
    initial_ra, initial_dec = get_current_position(telescope)
    print(f"Initial Position - RA: {initial_ra} hours, Dec: {initial_dec} degrees")
    points = iterative_spiral(initial_ra, initial_dec, grid_width, grid_height, grid_spacing)
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
    with open(file_path, 'w') as file:
        json.dump(data, file)

def select_output_folder():
    global output_folder
    output_folder = filedialog.askdirectory()
    folder_label.config(text=f"Output Folder: {output_folder}")

def start_scan():
    global grid_width, grid_height, grid_spacing, readings_per_measurement, sdr_center_freq, sdr_sample_rate, sdr_gain
    try:
        grid_width = int(width_entry.get())
        grid_height = int(height_entry.get())
        grid_spacing = float(spacing_entry.get())
        readings_per_measurement = float(avg_time_entry.get())
        sdr_center_freq = float(center_freq_entry.get())
        sdr_sample_rate = float(sample_rate_entry.get())
        sdr_gain = float(gain_entry.get())
    except ValueError:
        print("Error: Please enter valid numeric values for all inputs")
        return
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

tk.Label(root, text="Center Frequency (Hz):").grid(row=4, column=0)
center_freq_entry = tk.Entry(root)
center_freq_entry.insert(0, "1420000000")  # Default to hydrogen line frequency
center_freq_entry.grid(row=4, column=1)

tk.Label(root, text="Sample Rate (Hz):").grid(row=5, column=0)
sample_rate_entry = tk.Entry(root)
sample_rate_entry.insert(0, "250000")  # Default to 250e3 Hz
sample_rate_entry.grid(row=5, column=1)

tk.Label(root, text="Gain:").grid(row=6, column=0)
gain_entry = tk.Entry(root)
gain_entry.insert(0, "40")  # Default to 40
gain_entry.grid(row=6, column=1)

folder_button = tk.Button(root, text="Select Output Folder", command=select_output_folder)
folder_button.grid(row=7, column=0, columnspan=2)

folder_label = tk.Label(root, text="Output Folder: Not Selected")
folder_label.grid(row=8, column=0, columnspan=2)

start_button = tk.Button(root, text="Start Scan", command=start_scan)
start_button.grid(row=9, column=0, columnspan=2)

log_text = tk.Text(root, height=15, width=50)
log_text.grid(row=10, column=0, columnspan=2)

sys.stdout = StdoutRedirector(log_text)

root.mainloop()