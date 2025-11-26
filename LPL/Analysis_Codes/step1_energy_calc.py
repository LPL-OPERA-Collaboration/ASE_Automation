import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import os
import re
import math
import config  # Imports your variables from config.py

# =============================================================================
# INSTRUCTIONS FOR OPERATOR
# =============================================================================
# This script calculates the "Fluence" (Energy Density) for every file.
# It does NOT look at the spectrum shape yet.
#
# REQUIREMENTS:
# 1. 'calibration_*.csv' must be in BASE_DIR. 
#    Columns required: 'angle', 'energy_J'
# 2. 'absorption_*.txt' must be in BASE_DIR.
# 3. 'spectrum_*.txt' files must be in BASE_DIR/Raw_Data.
# =============================================================================

def get_calibration_curve(csv_path):
    """
    Loads the calibration CSV.
    CRITICAL: The CSV headers must be exactly 'angle' and 'energy_J'.
    """
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration CSV not found: {csv_path}")

    # Check for correct column names to avoid confusing errors later
    if 'angle' not in df.columns or 'energy_J' not in df.columns:
        raise ValueError(f"CSV ERROR: File {os.path.basename(csv_path)} must contain 'angle' and 'energy_J' columns.")

    df = df.sort_values(by='angle')
    max_energy = df['energy_J'].max()
    
    # Normalize the curve so the max is 1.0 (100% transmission)
    normalized = df['energy_J'] / max_energy
    f = interp1d(df['angle'], normalized, kind='cubic', bounds_error=False, fill_value="extrapolate")
    return f

def extract_angle_from_filename(filename):
    """
    Parses 'spectrum_280.txt' -> 280.0
    Parses 'spectrum_280.5.txt' -> 280.5
    """
    match = re.search(r'[-+]?\d*\.\d+|\d+', filename)
    return float(match.group()) if match else None

def find_calibration_file(base_dir):
    """Auto-detects any file with 'calibration' in the name ending in .csv"""
    keyword = config.CALIBRATION_FILE_KEYWORD.lower()
    print(f"Searching for calibration file with keyword '{keyword}' in: {base_dir}")
    
    try:
        candidates = [f for f in os.listdir(base_dir) if keyword in f.lower() and f.endswith(".csv")]
    except FileNotFoundError:
        return None
    
    if not candidates:
        print(f"ERROR: No CSV file containing '{keyword}' found in BASE_DIR.")
        print("TIP: Did you copy the Master Calibration file to this folder?")
        return None
    
    chosen_file = candidates[0]
    full_path = os.path.join(base_dir, chosen_file)
    print(f" -> Found: {chosen_file}")
    return full_path

def find_absorption_file(base_dir):
    """Auto-detects any file with 'absorption' in the name."""
    keyword = config.ABSORPTION_FILE_KEYWORD.lower()
    print(f"Searching for absorption file with keyword '{keyword}' in: {base_dir}")
    
    try:
        candidates = [f for f in os.listdir(base_dir) 
                      if keyword in f.lower() 
                      and os.path.isfile(os.path.join(base_dir, f))]
    except FileNotFoundError:
        return None
    
    if not candidates:
        print(f"ERROR: No file containing '{keyword}' found in BASE_DIR.")
        return None
    
    chosen_file = candidates[0]
    full_path = os.path.join(base_dir, chosen_file)
    print(f" -> Found: {chosen_file}")
    return full_path

def calculate_spot_area_cm2():
    """
    Converts dimensions from microns (µm) to cm² because Energy Density is usually in µJ/cm².
    """
    shape = config.SPOT_SHAPE.lower()
    d1_um = config.SPOT_DIM_1_UM
    d2_um = config.SPOT_DIM_2_UM
    
    if shape == "rectangle":
        area_um2 = d1_um * d2_um
        print(f"Geometry: Rectangle ({d1_um} x {d2_um} µm)")
    elif shape == "circle":
        radius = d1_um / 2.0
        area_um2 = math.pi * (radius ** 2)
        print(f"Geometry: Circle (Diameter {d1_um} µm)")
    elif shape == "ellipse":
        semi_major = d1_um / 2.0
        semi_minor = d2_um / 2.0
        area_um2 = math.pi * semi_major * semi_minor
        print(f"Geometry: Ellipse ({d1_um} x {d2_um} µm)")
    else:
        raise ValueError(f"Unknown shape in config: {shape}")
    
    area_cm2 = area_um2 * 1e-8 # 1 um^2 = 1e-8 cm^2
    print(f" -> Calculated Area: {area_cm2:.4e} cm²")
    return area_cm2

def load_spectrum_robust(file_path):
    """Helper to load messy text files that might have headers."""
    data_rows = []
    with open(file_path, 'r', encoding='latin-1') as f:
        for line in f:
            line = line.strip()
            if not line: continue
            cleaned_line = line.replace(',', ' ').replace('\t', ' ')
            try:
                nums = [float(p) for p in cleaned_line.split()]
                if len(nums) >= 2: data_rows.append(nums[:2])
            except ValueError: continue
    if not data_rows: raise ValueError("Could not find any numeric data.")
    return np.array(data_rows)

def get_absorption_rate(file_path):
    """Finds the absorbance at the TARGET_WAVELENGTH (e.g., 337nm)."""
    if not os.path.exists(file_path):
        print(f"WARNING: Absorption file not found: {file_path}")
        return 0.0
        
    print(f"Reading absorption spectrum from: {os.path.basename(file_path)}")
    try:
        data = load_spectrum_robust(file_path)
        wavelengths, absorbances = data[:, 0], data[:, 1]
        
        # Find index of wavelength closest to 337nm
        idx = np.argmin(np.abs(wavelengths - config.TARGET_WAVELENGTH))
        closest_wl = wavelengths[idx]
        abs_val = absorbances[idx]
        
        # Absorbance (OD) to Absorption Rate (0-1)
        # Rate = 1 - 10^(-OD)
        abs_rate = 1 - 10**(-abs_val)
        
        print(f" > Target: {config.TARGET_WAVELENGTH} nm")
        print(f" > Found:  {closest_wl:.2f} nm")
        print(f" > Absorbance (OD): {abs_val:.4f} | Rate: {abs_rate:.4f} ({(abs_rate*100):.1f}%)")
        return abs_rate
        
    except Exception as e:
        print(f"Error parsing absorption file: {e}")
        return 0.0

# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    print(f"=== STEP 1: PHYSICS CALCULATIONS ===")
    
    # SAFETY CHECK: Verify directories exist
    if not os.path.exists(config.BASE_DIR):
        print(f"\nCRITICAL ERROR: BASE_DIR not found.")
        print(f"Path searched: {config.BASE_DIR}")
        print("ACTION: Open config.py and update 'BASE_DIR'.")
        return
    
    if not os.path.exists(config.DATA_DIR):
        print(f"\nCRITICAL ERROR: Raw_Data folder not found.")
        print(f"Path searched: {config.DATA_DIR}")
        print("ACTION: Create a folder named 'Raw_Data' inside your measurement folder and put spectra there.")
        return

    os.makedirs(config.RESULTS_DIR, exist_ok=True)

    # 1. Calculate Spot Area
    try:
        stripe_area_cm2 = calculate_spot_area_cm2()
    except Exception as e:
        print(f"CRITICAL GEOMETRY ERROR: {e}")
        return

    # 2. Calculate Reference Energy
    # E_ref = Reading * 10^OD * Lens_Transmission
    daily_od_factor = 10 ** config.TODAYS_OD
    E_ref = config.RAW_ENERGY_READ * daily_od_factor * config.TRANSMISSION_LENS
    print(f"Ref Energy: {E_ref:.2f} nJ (Calculated from {config.RAW_ENERGY_READ} nJ reading)")

    # 3. Find and Load Calibration Curve
    calib_path = find_calibration_file(config.BASE_DIR)
    if not calib_path:
        print("CRITICAL ERROR: Calibration file missing. Cannot proceed.")
        return

    print(f"Loading calibration curve from: {os.path.basename(calib_path)}")
    calib_func = get_calibration_curve(calib_path)
    
    # Calculate Scaling Factor: How much energy corresponds to 1.0 transmission?
    trans_ref = calib_func(config.ANGLE_REF)
    scale_factor = E_ref / trans_ref
    
    # 4. Find and Load Absorption Rate
    abs_path = find_absorption_file(config.BASE_DIR)
    if abs_path:
        absorption_rate = get_absorption_rate(abs_path)
    else:
        print("WARNING: No absorption file found. Assuming Rate = 0 (0% Absorption).")
        absorption_rate = 0.0

    # 5. Scan Files
    try:
        files = [f for f in os.listdir(config.DATA_DIR) if f.startswith('spectrum_') and f.endswith('.txt')]
    except FileNotFoundError:
        print(f"Directory not found: {config.DATA_DIR}"); return

    if not files: print(f"No spectrum files found."); return

    data_list = []
    for f in files:
        angle = extract_angle_from_filename(f)
        if angle is not None:
            data_list.append({'filename': f, 'angle': angle})
    
    df_results = pd.DataFrame(data_list)
    df_results = df_results.sort_values(by='angle').reset_index(drop=True)
    
    # 6. CALCULATE ALL PHYSICS VALUES
    transmissions = calib_func(df_results['angle'])
    
    # A. Incident Energy (nJ)
    df_results['energy_nJ'] = scale_factor * transmissions
    
    # B. Absorbed Energy (nJ)
    df_results['absorbed_energy_nJ'] = df_results['energy_nJ'] * absorption_rate
    
    # C. Fluence / Energy Density (µJ/cm²)
    df_results['fluence_uJ_cm2'] = (df_results['absorbed_energy_nJ'] * 1e-3) / stripe_area_cm2
    
    # 7. Save Manifest
    save_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    df_results.to_csv(save_path, index=False)
    print(f" -> Saved Manifest to: {save_path}")
    
    print(f"\nSUCCESS. Calculated Fluence using Area {stripe_area_cm2:.2e} cm²")
    print("Manifest Preview (First 5 rows):")
    print(df_results[['filename', 'angle', 'absorbed_energy_nJ', 'fluence_uJ_cm2']].head())

    # 8. Plot
    plt.figure(figsize=(8, 5))
    plt.plot(df_results['angle'], df_results['fluence_uJ_cm2'], 'g^--', label='Fluence (µJ/cm²)')
    plt.xlabel('Angle (degrees)')
    plt.ylabel('Fluence (µJ/cm²)')
    plt.title(f'Final Energy Density Profile\nAbs Rate: {absorption_rate*100:.1f}%')
    plt.grid(True, alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()