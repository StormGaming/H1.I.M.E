import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import win32com.client
import time
from rtlsdr import RtlSdr
import numpy as np
import sys
import os
import json
from datetime import datetime
import traceback

# Global variables for the GUI inputs
output_folder = ""
grid_width = 5
grid_height = 5
grid_spacing = 2
readings_per_measurement = 5
sdr_sample_rate = 250e3  # Hz (default)
sdr_center_freq = 1.42e9  # Hz (default hydrogen line frequency)
sdr_gain = 40  # (default)
settle_time = 2  # seconds (default)
telescope_progid = "EQMOD.Telescope"  # Default telescope driver

# List of common ASCOM telescope drivers
TELESCOPE_DRIVERS = [
    "EQMOD.Telescope",
    "EQMOD_SIM.Telescope",
    "ASCOM.Celestron.Telescope",
    "ASCOM.Meade.Telescope",
    "ASCOM.SkyWatcher.Telescope",
    "ASCOM.Simulator.Telescope"
]

class StdoutRedirector:
    def __init__(self, text_widget, root):
        self.text_widget = text_widget
        self.root = root

    def write(self, message):
        self.text_widget.insert(tk.END, message)
        self.root.after(0, lambda: self.text_widget.see(tk.END))  # Schedule auto-scroll

    def flush(self):
        pass

def log_error(error_message):
    try:
        log_path = os.path.join(os.path.expanduser("~"), "telescope_error_log.txt")
        with open(log_path, "a") as f:
            f.write(f"{datetime.now()}: {error_message}\n")
    except Exception as e:
        print(f"Failed to write to error log: {str(e)}")

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
        current_ra = telescope.RightAscension * 15
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
        telescope.TargetRightAscension = ra / 15
        telescope.TargetDeclination = dec
        telescope.SlewToTarget()
    except Exception as e:
        error_msg = f"Error slewing telescope: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        raise

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

def run_grid_scan():
    global output_folder, grid_width, grid_height, grid_spacing, sdr_sample_rate, sdr_center_freq, sdr_gain, settle_time, telescope_progid
    try:
        telescope = connect_to_telescope(telescope_progid)
        initial_ra, initial_dec = get_current_position(telescope)
        status_label.config(text=f"Initial Position - RA: {initial_ra:.2f} hours, Dec: {initial_dec:.2f} degrees")
        root.update()
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
                status_label.config(text="Grid scan completed. Returning to initial position.")
                root.update()
                print("Grid slew and measurement completed.")
                sdr.close()
                start_button.config(state="normal")
                status_label.config(text="Idle")
                return
            ra, dec = points[i]
            status_label.config(text=f"Slewing to Position {i + 1}/{grid_width*grid_height}: RA: {ra:.2f}, Dec: {dec:.2f}")
            print(f"Grid Position {i + 1} out of {grid_width*grid_height}: Slewing to RA: {ra}, Dec: {dec}")
            root.update()
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

            def wait_for_slew():
                try:
                    if telescope.Slewing:
                        root.after(100, wait_for_slew)
                    else:
                        status_label.config(text=f"Settling for {settle_time}s at Position {i + 1}/{grid_width*grid_height}")
                        root.update()
                        time.sleep(settle_time)
                        status_label.config(text=f"Measuring at Position {i + 1}/{grid_width*grid_height}: RA: {ra:.2f}, Dec: {dec:.2f}")
                        root.update()
                        hydrogen_line_power_db = measure_point(sdr)
                        readings.append({'RA': ra, "DEC": dec, "INTENSITY": hydrogen_line_power_db, 'TIME': datetime.now().strftime("%Y-%m-%d_%H-%M-%S")})
                        print(f'\nData recorded at position {i + 1} out of {grid_width*grid_height}: \nRA: {ra} hours, \nDec: {dec} degrees, \nHydrogen Line Strength: {hydrogen_line_power_db} dB\n\n')
                        root.after(100, process_point, i + 1)
                except Exception as e:
                    error_msg = f"Error during slew or measurement at position {i + 1}: {str(e)}"
                    print(error_msg)
                    log_error(error_msg)
                    status_label.config(text="Error: Operation failed. Check log.")
                    start_button.config(state="normal")
                    messagebox.showerror("Error", error_msg)
            root.after(100, wait_for_slew)
        process_point(0)
    except Exception as e:
        error_msg = f"Error in grid scan: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        log_error(error_msg)
        status_label.config(text="Error occurred. Check log.")
        start_button.config(state="normal")
        messagebox.showerror("Error", f"Scan failed: {str(e)}")

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

def select_output_folder():
    global output_folder
    try:
        output_folder = filedialog.askdirectory()
        folder_label.config(text=f"Output Folder: {output_folder if output_folder else 'Not Selected'}")
    except Exception as e:
        error_msg = f"Error selecting folder: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        messagebox.showerror("Error", f"Failed to select folder: {str(e)}")

def start_scan():
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
    except ValueError as e:
        error_msg = f"Invalid input values: {str(e)}"
        print(error_msg)
        log_error(error_msg)
        status_label.config(text="Error: Invalid input values")
        messagebox.showerror("Error", error_msg)
        return
    start_button.config(state="disabled")
    status_label.config(text="Starting scan...")
    root.update()
    run_grid_scan()

# Setup GUI
try:
    root = tk.Tk()
    root.title("Telescope Grid Scan Controller")
    root.geometry("600x600")
    root.resizable(False, False)

    # Configure root to allow log frame to expand
    root.rowconfigure(0, weight=1)
    root.columnconfigure(0, weight=1)

    # Main frame with padding
    main_frame = ttk.Frame(root, padding="10")
    main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    main_frame.rowconfigure(5, weight=1)  # Allow log frame to expand
    main_frame.columnconfigure(0, weight=1)

    # Telescope Settings Frame
    telescope_frame = ttk.LabelFrame(main_frame, text="Telescope Settings", padding="5")
    telescope_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)

    ttk.Label(telescope_frame, text="Telescope Driver:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
    driver_combobox = ttk.Combobox(telescope_frame, values=TELESCOPE_DRIVERS, width=30)
    driver_combobox.set("EQMOD.Telescope")
    driver_combobox.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

    # Grid Settings Frame
    grid_frame = ttk.LabelFrame(main_frame, text="Grid Settings", padding="5")
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

    # SDR Settings Frame
    sdr_frame = ttk.LabelFrame(main_frame, text="SDR Settings", padding="5")
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

    # Output Settings Frame
    output_frame = ttk.LabelFrame(main_frame, text="Output Settings", padding="5")
    output_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=5)

    folder_button = ttk.Button(output_frame, text="Select Output Folder", command=select_output_folder)
    folder_button.grid(row=0, column=0, columnspan=2, pady=5)
    folder_label = ttk.Label(output_frame, text="Output Folder: Not Selected")
    folder_label.grid(row=1, column=0, columnspan=2, pady=5)

    # Control and Status
    control_frame = ttk.Frame(main_frame)
    control_frame.grid(row=4, column=0, sticky=(tk.W, tk.E), pady=10)

    start_button = ttk.Button(control_frame, text="Start Scan", command=start_scan)
    start_button.grid(row=0, column=0, padx=5)

    status_label = ttk.Label(control_frame, text="Idle")
    status_label.grid(row=0, column=1, padx=5)

    # Log Output
    log_frame = ttk.LabelFrame(main_frame, text="Log Output", padding="5")
    log_frame.grid(row=5, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
    log_frame.rowconfigure(0, weight=1)
    log_frame.columnconfigure(0, weight=1)

    log_text = tk.Text(log_frame, height=10, width=60, wrap=tk.WORD)
    log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
    scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=log_text.yview)
    scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
    log_text['yscrollcommand'] = scrollbar.set

    sys.stdout = StdoutRedirector(log_text, root)

    root.mainloop()

except Exception as e:
    error_msg = f"Failed to initialize GUI: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    log_error(error_msg)
    try:
        tk.Tk().withdraw()
        messagebox.showerror("Initialization Error", f"Failed to start GUI: {str(e)}")
    except:
        pass