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
    """Estimates threshold using gradient method."""
    idx = np.argsort(x)
    x_s, y_s = x[idx], y[idx]
    x_new = np.linspace(x_s.min(), x_s.max(), 1000)
    f = interp1d(x_s, y_s, kind='cubic')
    y_new = f(x_new)
    dy = np.gradient(y_new, x_new)
    
    # Only look for threshold in the upper 95% of the energy range
    mask = x_new > (x_new.min() + 0.05*(x_new.max()-x_new.min()))
    if np.sum(mask) == 0: return 0
    
    threshold = x_new[mask][np.argmin(dy[mask])]
    return threshold

# =============================================================================
# EXECUTION
# =============================================================================
def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"=== STEP 2: SPECTRUM ANALYSIS ({timestamp}) ===")

    # 1. Load The Manifest (CSV from Step 1)
    energy_file_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    
    if not os.path.exists(energy_file_path):
        print(f"CRITICAL ERROR: Manifest '{config.ENERGY_FILENAME}' not found.")
        print("Please run Step 1 first.")
        return
    
    print(f"Loading data manifest from: {energy_file_path}")
    try:
        df_manifest = pd.read_csv(energy_file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    # Check for the new 'fluence_uJ_cm2' column
    if 'fluence_uJ_cm2' not in df_manifest.columns:
        print("CRITICAL ERROR: 'fluence_uJ_cm2' column missing in CSV.")
        print("Your Step 1 output is outdated. Please re-run Step 1.")
        return

    # 2. Load Spectra based on the Manifest
    first_fname = df_manifest.iloc[0]['filename']
    first_path = os.path.join(config.DATA_DIR, first_fname)
    
    if not os.path.exists(first_path):
        print(f"ERROR: Could not find first spectrum file: {first_path}")
        return

    first_data = np.loadtxt(first_path)
    wavelengths = first_data[:, 0]
    n_pixels = len(wavelengths)
    n_files = len(df_manifest)
    
    raw_matrix = np.zeros((n_pixels, n_files))
    valid_indices = [] 

    print(f"Loading {n_files} spectra...")
    for i, row in df_manifest.iterrows():
        fname = row['filename']
        fpath = os.path.join(config.DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        try:
            data = np.loadtxt(fpath)
            if len(data[:, 0]) != n_pixels: continue
            raw_matrix[:, len(valid_indices)] = data[:, 1]
            valid_indices.append(i)
        except: continue

    if len(valid_indices) < n_files:
        raw_matrix = raw_matrix[:, :len(valid_indices)]
        df_manifest = df_manifest.iloc[valid_indices].reset_index(drop=True)

    # Save Data
    raw_filename = f'raw_spectra_{timestamp}.txt'
    header = "Wavelength " + " ".join(df_manifest['filename'].tolist())
    np.savetxt(os.path.join(config.RESULTS_DIR, raw_filename), np.column_stack((wavelengths, raw_matrix)), header=header)

    smooth_matrix = np.zeros_like(raw_matrix)
    for i in range(raw_matrix.shape[1]):
        smooth_matrix[:, i] = smooth(raw_matrix[:, i], config.SMOOTH_WINDOW)
    np.savetxt(os.path.join(config.RESULTS_DIR, f'smoothed_data_{timestamp}.txt'), smooth_matrix)

    # 3. Physics Analysis
    # We now skip the Excel loading because Step 1 handled the geometry.
    # The 'fluence_uJ_cm2' column contains the final X-axis values.
    energy_density = df_manifest['fluence_uJ_cm2'].values
    print(f"Loaded calculated Fluence (Energy Density) from manifest.")

    fwhm_list, intensity_list = [], []
    
    for i in range(smooth_matrix.shape[1]):
        spec = smooth_matrix[:, i]
        baseline = np.mean(spec[:10])
        spec_corrected = spec - baseline
        intensity_list.append(np.trapz(spec_corrected, wavelengths))
        fwhm_list.append(fwhm(wavelengths, spec_corrected))

    # Threshold
    try:
        threshold_val = ase_threshold(energy_density, np.array(fwhm_list))
        print(f"Calculated ASE Threshold: {threshold_val:.2f} µJ/cm²")
    except:
        threshold_val = 0

    # 4. Plotting
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    sort_idx = np.argsort(energy_density)
    ax1.semilogx(energy_density[sort_idx], np.array(fwhm_list)[sort_idx], 'bo--', label='FWHM')
    ax2.loglog(energy_density[sort_idx], np.array(intensity_list)[sort_idx], 'ro-', label='Intensity')
    
    ax1.set_xlabel('Absorbed Energy Density (µJ/cm²)')
    ax1.set_ylabel('FWHM (nm)', color='b')
    ax2.set_ylabel('Integrated Intensity (a.u.)', color='r')
    plt.title(f'ASE Characterization ({timestamp})\nThreshold ~ {threshold_val:.2f} µJ/cm²')
    plt.tight_layout()
    
    plot_name = f'ASE_Curve_{timestamp}.png'
    plt.savefig(os.path.join(config.RESULTS_DIR, plot_name))
    print(f"Plot saved to {plot_name}")
    plt.show()

if __name__ == "__main__":
    main()