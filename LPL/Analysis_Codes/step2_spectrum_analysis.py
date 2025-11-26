import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
from scipy.signal import savgol_filter
import os
import re
import datetime
import shutil 
import ASE_Automation.LPL.Analysis_Codes.analysis_config as analysis_config  # Imports your variables from config.py

# =============================================================================
# INSTRUCTIONS FOR OPERATOR
# =============================================================================
# This script performs the "Physics" analysis.
# It reads the Energy Density calculated in Step 1, matches it with spectra,
# and generates the S-Curve (FWHM vs Energy).
#
# NEW FEATURE:
# It now reads the "Integration Time" from the file header to normalize intensity.
# Integrated_Intensity = (Area under curve) / (Integration Time)
#
# OUTPUTS:
# 1. COMBINED_*.txt: All your data stitched into one file.
# 2. final_results_*.csv: Table of FWHM, Raw/Corrected Intensity, and Fluence.
# 3. Used_Analysis_Codes_*: Backup of your code for traceability.
# =============================================================================

def smooth(x, S_value):
    """
    Savitzky-Golay smoothing.
    NOTE: S_value must be an ODD number. Defined in config.py as SMOOTH_WINDOW.
    """
    if S_value < 3 or S_value % 2 == 0:
        raise ValueError("Smooth window must be odd and >= 3")
    return savgol_filter(x, S_value, 3)

def fwhm(x, y):
    """Calculates Full Width at Half Maximum (Spectral narrowing)."""
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

def ase_threshold(x, y):
    """
    Estimates the ASE threshold using the derivative (gradient) method.
    It looks for the point where the FWHM drops the fastest.
    """
    idx = np.argsort(x)
    x_s, y_s = x[idx], y[idx]
    x_new = np.linspace(x_s.min(), x_s.max(), 1000)
    f = interp1d(x_s, y_s, kind='cubic')
    y_new = f(x_new)
    dy = np.gradient(y_new, x_new)
    
    # Only look for threshold in the upper 95% of the energy range
    # This prevents noise at low energy from confusing the algorithm
    mask = x_new > (x_new.min() + 0.05*(x_new.max()-x_new.min()))
    if np.sum(mask) == 0: return 0
    
    threshold = x_new[mask][np.argmin(dy[mask])]
    return threshold

def save_code_snapshot(base_dir, timestamp):
    """
    Creates a backup folder and copies the python scripts used.
    This guarantees you can always check how the result was calculated later.
    """
    folder_name = f"Used_Analysis_Codes_{timestamp}"
    target_dir = os.path.join(base_dir, folder_name)
    
    try:
        os.makedirs(target_dir, exist_ok=True)
        
        # Files to snapshot (Assumes they are in the same folder as this script)
        files_to_save = ['analysis_config.py', 'step1_energy_calc.py', 'step2_spectrum_analysis.py']
        current_script_dir = os.path.dirname(os.path.abspath(__file__))
        
        print(f" -> Snapshotting codes to: {folder_name}/")
        
        for filename in files_to_save:
            src = os.path.join(current_script_dir, filename)
            dst = os.path.join(target_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
            else:
                print(f"    [WARNING] Could not find {filename} to snapshot.")
                
    except Exception as e:
        print(f"    [WARNING] Failed to save code snapshot: {e}")

def get_integration_time(filepath):
    """
    Reads the file header to find the Integration Time.
    Looks for line: '# Integration Time (s): 1.0'
    Returns 1.0 if not found (to avoid division by zero).
    """
    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            for _ in range(20): # Only check first 20 lines
                line = f.readline()
                if "Integration Time (s):" in line:
                    # Extract the number after the colon
                    parts = line.split(':')
                    if len(parts) > 1:
                        val = float(parts[1].strip())
                        return val
    except Exception as e:
        pass # If error, return default
    
    print(f"    [WARNING] Could not find Integration Time in {os.path.basename(filepath)}. Assuming 1.0s")
    return 1.0

# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"=== STEP 2: SPECTRUM ANALYSIS ({timestamp}) ===")

    # SAFETY CHECK
    if not os.path.exists(analysis_config.RESULTS_DIR):
        print(f"CRITICAL ERROR: Results directory not found.")
        print("ACTION: Run Step 1 first.")
        return

    # 0. Save Code Snapshot (Traceability)
    save_code_snapshot(analysis_config.BASE_DIR, timestamp)

    # 1. Load The Manifest (CSV from Step 1)
    energy_file_path = os.path.join(analysis_config.RESULTS_DIR, analysis_config.ENERGY_FILENAME)
    
    if not os.path.exists(energy_file_path):
        print(f"CRITICAL ERROR: Manifest '{analysis_config.ENERGY_FILENAME}' not found.")
        return
    
    print(f"Loading data manifest from: {energy_file_path}")
    try:
        df_manifest = pd.read_csv(energy_file_path)
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if 'fluence_uJ_cm2' not in df_manifest.columns:
        print("CRITICAL ERROR: 'fluence_uJ_cm2' column missing in CSV.")
        return

    # 2. Load Spectra based on the Manifest
    first_fname = df_manifest.iloc[0]['filename']
    first_path = os.path.join(analysis_config.DATA_DIR, first_fname)
    
    if not os.path.exists(first_path):
        print(f"ERROR: Could not find first spectrum file: {first_path}")
        return

    first_data = np.loadtxt(first_path)
    wavelengths = first_data[:, 0]
    n_pixels = len(wavelengths)
    n_files = len(df_manifest)
    
    raw_matrix = np.zeros((n_pixels, n_files))
    valid_indices = [] 
    
    # [NEW] List to store integration times
    integration_times = []

    print(f"Loading {n_files} spectra & checking headers...")
    for i, row in df_manifest.iterrows():
        fname = row['filename']
        fpath = os.path.join(analysis_config.DATA_DIR, fname)
        if not os.path.exists(fpath):
            continue
        try:
            # Load Data
            data = np.loadtxt(fpath)
            if len(data[:, 0]) != n_pixels: continue
            
            # Load Integration Time
            int_time = get_integration_time(fpath)
            
            raw_matrix[:, len(valid_indices)] = data[:, 1]
            valid_indices.append(i)
            integration_times.append(int_time)
            
        except: continue

    if len(valid_indices) < n_files:
        raw_matrix = raw_matrix[:, :len(valid_indices)]
        df_manifest = df_manifest.iloc[valid_indices].reset_index(drop=True)
        # integration_times list matches valid_indices naturally

    # Save Combined Data
    raw_filename = f'COMBINED_raw_spectra_{timestamp}.txt'
    raw_path = os.path.join(analysis_config.RESULTS_DIR, raw_filename)
    header = "Wavelength " + " ".join(df_manifest['filename'].tolist())
    
    np.savetxt(raw_path, np.column_stack((wavelengths, raw_matrix)), header=header)
    print(f" -> Saved Raw Spectra to: {raw_filename}")

    smooth_matrix = np.zeros_like(raw_matrix)
    for i in range(raw_matrix.shape[1]):
        smooth_matrix[:, i] = smooth(raw_matrix[:, i], analysis_config.SMOOTH_WINDOW)
        
    smooth_filename = f'COMBINED_smoothed_spectra_{timestamp}.txt'
    smooth_path = os.path.join(analysis_config.RESULTS_DIR, smooth_filename)
    np.savetxt(smooth_path, smooth_matrix)
    print(f" -> Saved Smoothed Data to: {smooth_filename}")

    # 3. Physics Analysis
    energy_density = df_manifest['fluence_uJ_cm2'].values
    print(f"Loaded calculated Fluence (Energy Density) from manifest.")

    fwhm_list = []
    raw_intensity_list = [] # Area under curve
    corrected_intensity_list = [] # Area / Time
    
    for i in range(smooth_matrix.shape[1]):
        spec = smooth_matrix[:, i]
        t_int = integration_times[i]
        
        baseline = np.mean(spec[:10])
        spec_corrected = spec - baseline
        
        # Calculate Raw Area
        raw_area = np.trapz(spec_corrected, wavelengths)
        raw_intensity_list.append(raw_area)
        
        # Calculate Corrected Intensity (Area / Time)
        corrected_intensity_list.append(raw_area / t_int)
        
        fwhm_list.append(fwhm(wavelengths, spec_corrected))

    # Threshold Calculation (using FWHM)
    try:
        threshold_val = ase_threshold(energy_density, np.array(fwhm_list))
        print(f"Calculated ASE Threshold: {threshold_val:.2f} µJ/cm²")
    except:
        threshold_val = 0

    # Save Final Results Summary to CSV
    df_summary = df_manifest[['filename', 'fluence_uJ_cm2']].copy()
    df_summary['Integration_Time_s'] = integration_times
    df_summary['FWHM_nm'] = fwhm_list
    df_summary['Raw_Integrated_Intensity'] = raw_intensity_list
    df_summary['Integrated_Intensity'] = corrected_intensity_list
    
    summary_filename = f'final_results_{timestamp}.csv'
    summary_path = os.path.join(analysis_config.RESULTS_DIR, summary_filename)
    
    # We write the Threshold as a comment header, then the dataframe
    with open(summary_path, 'w', newline='') as f:
        f.write(f"# ASE Threshold: {threshold_val:.4f} uJ/cm2\n")
        df_summary.to_csv(f, index=False)
        
    print(f" -> Saved Final Results to: {summary_filename}")

    # 4. Plotting
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    sort_idx = np.argsort(energy_density)
    
    # Plotting FWHM vs Fluence
    ax1.semilogx(energy_density[sort_idx], np.array(fwhm_list)[sort_idx], 'bo--', label='FWHM')
    
    # Plotting CORRECTED Intensity vs Fluence
    ax2.loglog(energy_density[sort_idx], np.array(corrected_intensity_list)[sort_idx], 'ro-', label='Integrated Intensity')
    
    ax1.set_xlabel('Absorbed Energy Density (µJ/cm²)')
    ax1.set_ylabel('FWHM (nm)', color='b')
    ax2.set_ylabel('Integrated Intensity (Counts*nm/s)', color='r')
    plt.title(f'ASE Characterization ({timestamp})\nThreshold ~ {threshold_val:.2f} µJ/cm²')
    plt.tight_layout()
    
    plot_name = f'ASE_Curve_{timestamp}.png'
    plt.savefig(os.path.join(analysis_config.RESULTS_DIR, plot_name))
    print(f"Plot saved to {plot_name}")
    plt.show()

if __name__ == "__main__":
    main()