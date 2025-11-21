import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import os
import re
import config  # Imports your variables from config.py

# =============================================================================
# TOOLS
# =============================================================================
def get_calibration_curve(csv_path):
    """Loads CSV and returns interpolation function (Angle -> Normalized Energy)."""
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration CSV not found: {csv_path}")

    if 'angle' not in df.columns or 'energy_J' not in df.columns:
        raise ValueError(f"CSV must contain 'angle' and 'energy_J' columns.")

    df = df.sort_values(by='angle')
    max_energy = df['energy_J'].max()
    if max_energy == 0: raise ValueError("Max energy in CSV is 0.")
        
    normalized = df['energy_J'] / max_energy
    f = interp1d(df['angle'], normalized, kind='cubic', bounds_error=False, fill_value="extrapolate")
    return f

def extract_angle_from_filename(filename):
    """Finds the number in 'spectrum_85.00.txt' -> 85.0"""
    match = re.search(r'[-+]?\d*\.\d+|\d+', filename)
    return float(match.group()) if match else None

def load_spectrum_robust(file_path):
    """
    Smart Parser: Reads a text file and extracts numeric data columns
    regardless of header length or delimiter (tab, comma, space).
    Returns: numpy array of shape (N, 2) [Wavelength, Absorbance]
    """
    data_rows = []
    
    with open(file_path, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line: continue # Skip empty lines
            
            # normalize delimiters: replace commas and tabs with space
            cleaned_line = line.replace(',', ' ').replace('\t', ' ')
            parts = cleaned_line.split()
            
            # Try to convert to floats
            try:
                # We expect at least 2 numbers (Wavelength, Value)
                nums = [float(p) for p in parts]
                if len(nums) >= 2:
                    data_rows.append(nums[:2]) # Keep only first 2 cols
            except ValueError:
                # Line contains text, treat as header and skip
                continue
                
    if not data_rows:
        raise ValueError("Could not find any numeric data in the file.")
        
    return np.array(data_rows)

def get_absorption_rate(file_path):
    """
    Reads absorption spectrum using smart parsing, finds value at 
    TARGET_WAVELENGTH, and returns absorption rate (1 - 10^-OD).
    """
    if not os.path.exists(file_path):
        print(f"WARNING: Absorption file not found: {file_path}")
        print(" -> Absorption will be set to 0 in the manifest.")
        return 0.0
        
    print(f"Reading absorption spectrum from: {os.path.basename(file_path)}")
    try:
        # Use the new robust loader
        data = load_spectrum_robust(file_path)
        
        wavelengths, absorbances = data[:, 0], data[:, 1]
        
        # Find closest wavelength
        idx = np.argmin(np.abs(wavelengths - config.TARGET_WAVELENGTH))
        closest_wl = wavelengths[idx]
        abs_val = absorbances[idx]
        
        # Calculate rate: 1 - 10^(-OD)
        abs_rate = 1 - 10**(-abs_val)
        
        print(f" > Target: {config.TARGET_WAVELENGTH} nm | Found: {closest_wl:.2f} nm")
        print(f" > Absorbance (OD): {abs_val:.4f} | Rate: {abs_rate:.4f} ({(abs_rate*100):.1f}%)")
        return abs_rate
        
    except Exception as e:
        print(f"Error parsing absorption file: {e}")
        return 0.0

# =============================================================================
# EXECUTION
# =============================================================================
def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    
    print(f"=== STEP 1: ENERGY & ABSORPTION CALCULATION ===")
    
    # 1. Calculate Reference Energy (The Anchor)
    daily_od_factor = 10 ** config.TODAYS_OD
    E_ref = config.RAW_ENERGY_READ * daily_od_factor * config.TRANSMISSION_LENS
    
    print(f"Reference Energy Calculation:")
    print(f" - Raw Reading: {config.RAW_ENERGY_READ} nJ")
    print(f" - OD Value:    {config.TODAYS_OD} (Factor: {daily_od_factor:.2f})")
    print(f" -> CALCULATED REF ENERGY: {E_ref:.2f} nJ")

    # 2. Get Curve Shape & Scale Factor
    print(f"\nLoading calibration curve from: {config.CSV_CALIB_PATH}")
    calib_func = get_calibration_curve(config.CSV_CALIB_PATH)
    
    trans_ref = calib_func(config.ANGLE_REF)
    scale_factor = E_ref / trans_ref
    print(f"Calibration Scale Factor: {scale_factor:.2f}")
    
    # 3. Determine Absorption Rate (Robust)
    print(f"\nCalculating Absorption Rate...")
    abs_file_path = os.path.join(config.DATA_DIR, config.ABSORPTION_FILENAME)
    absorption_rate = get_absorption_rate(abs_file_path)

    # 4. DETERMINE ANGLES FROM FILES
    print(f"\nScanning for spectra in: {config.DATA_DIR}")
    try:
        files = [f for f in os.listdir(config.DATA_DIR) if f.startswith('spectrum_') and f.endswith('.txt')]
    except FileNotFoundError:
        print(f"ERROR: Directory not found: {config.DATA_DIR}")
        return

    if not files:
        print(f"ERROR: No 'spectrum_*.txt' files found.")
        return

    # Extract angles and keep track of filenames
    data_list = []
    for f in files:
        angle = extract_angle_from_filename(f)
        if angle is not None:
            data_list.append({'filename': f, 'angle': angle})
    
    # Create DataFrame and sort
    df_results = pd.DataFrame(data_list)
    df_results = df_results.sort_values(by='angle').reset_index(drop=True)
    
    print(f" > Using {len(df_results)} angles extracted from files.")

    # 5. Calculate Energies (Incident AND Absorbed)
    transmissions = calib_func(df_results['angle'])
    
    # Incident Energy (nJ)
    df_results['energy_nJ'] = scale_factor * transmissions
    
    # Absorbed Energy (nJ)
    df_results['absorbed_energy_nJ'] = df_results['energy_nJ'] * absorption_rate
    
    # 6. Save Data as CSV (Manifest)
    save_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    df_results.to_csv(save_path, index=False)
    
    print(f"\nSUCCESS: Energies calculated for {len(df_results)} points.")
    print(f"Saved Manifest to: {save_path}")
    print("Preview:")
    print(df_results[['filename', 'angle', 'energy_nJ', 'absorbed_energy_nJ']].head())

    # 7. Check Plot
    plt.figure(figsize=(8, 5))
    plt.plot(df_results['angle'], df_results['energy_nJ'], 'o-', label='Incident Energy')
    plt.plot(df_results['angle'], df_results['absorbed_energy_nJ'], 's--', label='Absorbed Energy')
    plt.plot(config.ANGLE_REF, E_ref, 'r*', markersize=15, label='Ref Point')
    plt.xlabel('Angle (degrees)')
    plt.ylabel('Energy (nJ)')
    plt.title(f'Energy Calibration Check\nAbs Rate: {absorption_rate*100:.1f}%')
    plt.grid(True, alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()