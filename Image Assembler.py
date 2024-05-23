import os
import json
import numpy as np
import matplotlib.pyplot as plt
from tkinter import Tk, filedialog, Button, Label, Entry


def extract_data_from_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)

    # Access the measurements part of the JSON
    measurements = data.get('measurements', [])
    grid_spacing = data.get('grid_spacing', None)  # Extract grid_spacing from the file
    grid_width = data.get('grid_width', None)
    grid_height = data.get('grid_height', None)

    results = []
    # Extract RA, DEC, and Intensity from each measurement
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

    # You can handle the averaging or other aggregation of grid_spacing here
    average_spacing = sum(grid_spacings) / len(grid_spacings) if grid_spacings else None
    print(f"Average Grid Spacing: {average_spacing}")

    return data_points, average_spacing


def dB_to_linear(dB):
    """ Convert decibel (dB) to linear scale """
    return 10 ** (dB / 10)


def linear_to_dB(linear):
    """ Convert linear scale to decibel (dB) """
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

    # Determine the bounds and grid size based on the data range and grid spacing
    ra_range = max(ra_values) - min(ra_values)
    dec_range = max(dec_values) - min(dec_values)
    grid_width = int(np.ceil(ra_range / grid_spacing)) + 1
    grid_height = int(np.ceil(dec_range / grid_spacing)) + 1

    # Create grid coordinates for interpolation
    ra_lin = np.linspace(min(ra_values), max(ra_values), grid_width)
    dec_lin = np.linspace(min(dec_values), max(dec_values), grid_height)

    # Initialize grid with NaNs or zeros
    grid = np.full((grid_height, grid_width), np.nan)

    # Fill the grid
    for (ra, dec, power) in data_points:
        ra_idx = np.searchsorted(ra_lin, ra) - 1
        dec_idx = np.searchsorted(dec_lin, dec) - 1
        if np.isnan(grid[dec_idx, ra_idx]):
            grid[dec_idx, ra_idx] = power
        else:
            # Averaging if more than one value falls into the same grid cell
            grid[dec_idx, ra_idx] = (grid[dec_idx, ra_idx] + power) / 2

    # Plotting the results
    plt.figure(figsize=(10, 8))
    plt.imshow(grid, cmap='viridis', interpolation='nearest', origin='lower',
               extent=[min(ra_values), max(ra_values), min(dec_values), max(dec_values)])
    plt.colorbar(label='Hydrogen Line Power (dB)')
    plt.title('Hydrogen Line Signal Strength Grid')
    plt.xlabel('Right Ascension')
    plt.ylabel('Declination')
    plt.show()


def select_file():
    file_path = filedialog.askopenfilename(filetypes=[("JSON files", "*.json")])
    if file_path:
        try:
            data_points, grid_spacing = read_data_from_file(file_path)
            generate_image(data_points, grid_spacing)
        except ValueError:
            print("Grid size must be an integer.")


# GUI Setup
root = Tk()
root.title("Hydrogen Line Signal Strength Grid Assembler")

# File selection button
select_button = Button(root, text="Select JSON File", command=select_file)
select_button.grid(row=0, column=0, padx=10, pady=10)

# Start the GUI event loop
root.mainloop()
