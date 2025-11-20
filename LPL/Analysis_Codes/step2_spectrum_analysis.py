import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
import os
import re
import datetime
import config  # Imports your variables from config.py

# =============================================================================
# TOOLS: SIGNAL PROCESSING
# =============================================================================
def smooth(x, S_value):
    """Savitzky-Golay smoothing."""
    if S_value < 3 or S_value % 2 == 0:
        raise ValueError("Smooth window must be odd and >= 3")
    return savgol_filter(x, S_value, 3)

def fwhm(x, y):
    """Calculates Full Width at Half Maximum."""
    y_norm = y / np.max(y)
    lev50 = 0.5
    if np.all(y_norm < lev50): return np.nan
    center = np.argmax(y_norm)
    # Leading edge
    i = center
    while i > 0 and y_norm[i] > lev50: i -= 1
    x1 = np.interp(lev50, [y_norm[i], y_norm[i+1]], [x[i], x[i+1]])
    # Trailing edge
    i = center
    while i < len(y_norm)-1 and y_norm[i] > lev50: i += 1
    x2 = np.interp(lev50, [y_norm[i], y_norm[i-1]], [x[i], x[i-1]])
    return x2 - x1

def find_decimal_number(s):
    """Extracts the first float number found in a string."""
    match = re.search(r'[-+]?\d*\.\d+|\d+', str(s))
    return float(match.group()) if match else 0.0

def ase_threshold(x, y):
    idx = np.argsort(x)
    x_s, y_s = x[idx], y[idx]
    x_new = np.linspace(x_s.min(), x_s.max(), 1000)
    f = interp1d(x_s, y_s, kind='cubic')
    y_new = f(x_new)
    dy = np.gradient(y_new, x_new)
    mask = x_new > (x_new.min() + 0.05*(x_new.max()-x_new.min()))
    threshold = x_new[mask][np.argmin(dy[mask])]
    return threshold

# =============================================================================
# EXECUTION
# =============================================================================
def main():
    # Generate Timestamp for this analysis run
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"=== STEP 2: SPECTRUM ANALYSIS ({timestamp}) ===")

    # 1. Load Energies (From Step 1)
    energy_file = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    
    if not os.path.exists(energy_file):
        print(f"ERROR: '{config.ENERGY_FILENAME}' not found in results dir!")
        print("Please run 'step1_energy_calc.py' first.")
        return
    
    energies = np.loadtxt(energy_file)
    print(f"Loaded {len(energies)} energy points from {config.ENERGY_FILENAME}")

    # 2. Load Spectra (Parsed and Sorted by Angle)
    print(f"Scanning folder: {config.DATA_DIR}")
    files = [f for f in os.listdir(config.DATA_DIR) if f.startswith('spectrum_') and f.endswith('.txt')]
    
    if not files:
        print(f"No spectrum files found in {config.DATA_DIR}")
        return

    # CRITICAL FIX: Sort files NUMERICALLY based on the angle in the filename.
    # Alphabetical sort puts '100' before '85'. Numerical sort fixes this.
    files.sort(key=lambda f: find_decimal_number(f))
    
    print(f"Found {len(files)} spectrum files. Range: {files[0]} -> {files[-1]}")
    
    # Mismatch Check
    if len(files) != len(energies):
        print(f"CRITICAL WARNING: File count ({len(files)}) does not match Energy count ({len(energies)})!")
        print("Check that your Config 'NUMBER_POINTS' matches the number of files.")

    # Initialize Matrix
    first_data = np.loadtxt(os.path.join(config.DATA_DIR, files[0]))
    wavelengths = first_data[:, 0]
    raw_matrix = np.zeros((len(wavelengths), len(files)))

    print(f"Processing spectra...")
    for i, fname in enumerate(files):
        data = np.loadtxt(os.path.join(config.DATA_DIR, fname))
        raw_matrix[:, i] = data[:, 1]

    # Save Fresh Raw Data (Timestamped)
    raw_filename = f'raw_spectra_{timestamp}.txt'
    raw_path = os.path.join(config.RESULTS_DIR, raw_filename)
    header = "Wavelength " + " ".join([f"Spectrum_{i+1}" for i in range(len(files))])
    np.savetxt(raw_path, np.column_stack((wavelengths, raw_matrix)), header=header)
    print(f"Saved fresh raw data to {raw_filename}")

    # Smoothing
    smooth_matrix = np.zeros_like(raw_matrix)
    for i in range(raw_matrix.shape[1]):
        smooth_matrix[:, i] = smooth(raw_matrix[:, i], config.SMOOTH_WINDOW)
    
    # Save Smoothed Data (Timestamped)
    smooth_filename = f'smoothed_data_{timestamp}.txt'
    np.savetxt(os.path.join(config.RESULTS_DIR, smooth_filename), smooth_matrix)
    print(f"Saved smoothed data to {smooth_filename}")

    # 3. Physics Analysis
    try:
        df_manual = pd.read_excel(config.MANUAL_EXCEL_PATH, header=None)
        pulse_duration = find_decimal_number(df_manual.iloc[2, 0]) * 1e-9
        absorption = find_decimal_number(df_manual.iloc[3, 0])
        L_stripe = find_decimal_number(df_manual.iloc[4, 0]) * 1e-4
        e_stripe = find_decimal_number(df_manual.iloc[5, 0]) * 1e-4
    except Exception as e:
        print(f"Error reading Excel: {e}")
        return

    # Calculations
    energies_uJ = energies * 1e-3
    absorbed_J = energies_uJ * 1e-6 * absorption
    energy_density = (absorbed_J / (L_stripe * e_stripe)) * 1e6 

    fwhm_list, intensity_list = [], []
    
    for i in range(smooth_matrix.shape[1]):
        spec = smooth_matrix[:, i]
        spec = spec - spec[0] # Baseline
        intensity_list.append(np.trapz(spec, wavelengths))
        fwhm_list.append(fwhm(wavelengths, spec))

    # Threshold
    try:
        threshold_val = ase_threshold(energy_density, np.array(fwhm_list))
        print(f"Calculated ASE Threshold: {threshold_val:.2f} µJ/cm²")
    except:
        threshold_val = 0

    # 4. Plotting
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    
    ax1.semilogx(energy_density, fwhm_list, 'bo--', label='FWHM')
    ax2.loglog(energy_density, intensity_list, 'ro-', label='Intensity')
    
    ax1.set_xlabel('Absorbed Energy Density (µJ/cm²)')
    ax1.set_ylabel('FWHM (nm)', color='b')
    ax2.set_ylabel('Integrated Intensity (a.u.)', color='r')
    plt.title(f'ASE Characterization ({timestamp})\nThreshold ~ {threshold_val:.2f} µJ/cm²')
    plt.tight_layout()
    
    # Save Plot (Timestamped)
    plot_name = f'ASE_Curve_{timestamp}.png'
    plt.savefig(os.path.join(config.RESULTS_DIR, plot_name))
    print(f"Plot saved to {plot_name}")
    plt.show()

if __name__ == "__main__":
    main()