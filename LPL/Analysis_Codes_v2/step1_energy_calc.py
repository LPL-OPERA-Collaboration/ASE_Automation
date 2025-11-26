import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import os
import math
import analysis_config as analysis_config

# =============================================================================
#  STEP 1: ENERGY & POWER CALCULATION (ROBUST READER)
# =============================================================================

def get_calibration_curve(csv_path):
    """Loads calibration CSV (angle vs energy)."""
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration CSV not found: {csv_path}")

    if 'angle' not in df.columns or 'energy_corrected_J' not in df.columns:
        raise ValueError(f"CSV ERROR: {os.path.basename(csv_path)} needs 'angle' and 'energy_corrected_J'.")

    df = df.sort_values(by='angle')
    max_energy = df['energy_corrected_J'].max()
    
    if max_energy == 0: raise ValueError("Max energy is 0.")

    # Normalize max to 1.0
    normalized = df['energy_corrected_J'] / max_energy
    f = interp1d(df['angle'], normalized, kind='cubic', bounds_error=False, fill_value="extrapolate")
    return f

def get_header_value(filepath, search_str):
    """Scans the first 20 lines for a specific string (e.g. '# Angle (deg):')."""
    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            for _ in range(20):
                line = f.readline()
                if search_str in line:
                    parts = line.split(':')
                    if len(parts) > 1:
                        return float(parts[1].strip())
    except: pass 
    return None

def find_file_universal(base_dir, keyword):
    """
    Scans directory for a file containing the keyword.
    Prioritizes .csv, then .txt, then anything else.
    """
    try:
        all_files = os.listdir(base_dir)
        # filter for keyword
        candidates = [f for f in all_files if keyword.lower() in f.lower()]
        
        if not candidates: return None
        
        # Sort priority: CSV first, then TXT
        # We achieve this by sorting based on extension
        candidates.sort(key=lambda f: 0 if f.endswith('.csv') else (1 if f.endswith('.txt') else 2))
        
        chosen = candidates[0]
        return os.path.join(base_dir, chosen)
    except: return None

def calculate_spot_area_cm2():
    """Calculates spot area in cm2."""
    shape = analysis_config.SPOT_SHAPE.lower()
    d1 = analysis_config.SPOT_DIM_1_UM
    d2 = analysis_config.SPOT_DIM_2_UM
    
    if shape == "rectangle": area_um2 = d1 * d2
    elif shape == "circle": area_um2 = math.pi * ((d1/2)**2)
    elif shape == "ellipse": area_um2 = math.pi * (d1/2) * (d2/2)
    else: raise ValueError(f"Unknown shape: {shape}")
    
    return area_um2 * 1e-8 # Convert to cm2

def get_absorption_rate(file_path):
    """
    ROBUST LOADER: Reads .txt, .csv, space, tab, or comma separated.
    Calculates Absorption Rate (0-1) from OD spectrum.
    """
    if not file_path or not os.path.exists(file_path):
        print("WARNING: No absorption file found. Assuming 0% absorption.")
        return 0.0
        
    print(f"Reading absorption from: {os.path.basename(file_path)}")
    try:
        # 1. Universal Read (Sniffs delimiter automatically)
        # header=None ensures we read everything, then we clean it up
        # comment='#' ignores standard comments
        df = pd.read_csv(file_path, sep=None, engine='python', comment='#', header=None)
        
        # 2. Force Numeric (Handles text headers that weren't commented)
        # Any cell that isn't a number becomes NaN
        df = df.apply(pd.to_numeric, errors='coerce')
        
        # 3. Drop rows that contain NaN (e.g. text headers)
        df = df.dropna()
        
        # 4. Extract Columns (Expects Col 0 = Wavelength, Col 1 = Absorbance)
        data = df.values
        if data.shape[1] < 2:
            print("ERROR: Absorption file must have at least 2 columns (Wavelength, Value).")
            return 0.0
            
        wavelengths, absorbances = data[:, 0], data[:, 1]
        
        # 5. Find Target
        idx = np.argmin(np.abs(wavelengths - analysis_config.TARGET_WAVELENGTH))
        closest_wl = wavelengths[idx]
        abs_val = absorbances[idx]
        
        # Rate = 1 - 10^(-OD)
        rate = 1 - 10**(-abs_val)
        
        print(f"   -> Value at {closest_wl:.1f} nm: OD = {abs_val:.3f}")
        print(f"   -> Absorption Rate: {rate*100:.1f}%")
        return rate

    except Exception as e:
        print(f"Error reading absorption file: {e}")
        return 0.0

# =============================================================================
# MAIN EXECUTION
# =============================================================================
def main():
    print(f"=== STEP 1: PHYSICS CALCULATIONS ===")
    
    if not os.path.exists(analysis_config.BASE_DIR):
        print(f"CRITICAL: BASE_DIR not found: {analysis_config.BASE_DIR}"); return
    if not os.path.exists(analysis_config.DATA_DIR):
        print(f"CRITICAL: Raw_Data folder not found."); return

    os.makedirs(analysis_config.RESULTS_DIR, exist_ok=True)

    # 1. Geometry & Ref Energy
    area_cm2 = calculate_spot_area_cm2()
    E_ref = analysis_config.RAW_ENERGY_READ * (10 ** analysis_config.TODAYS_OD) * analysis_config.TRANSMISSION_LENS
    print(f"Ref Energy: {E_ref:.2f} nJ | Spot Area: {area_cm2:.2e} cm²")

    # 2. Calibration Curve
    calib_path = find_file_universal(analysis_config.BASE_DIR, analysis_config.CALIBRATION_KEYWORD)
    if not calib_path: print("CRITICAL: Calibration file missing."); return
    
    calib_func = get_calibration_curve(calib_path)
    trans_ref = calib_func(analysis_config.ANGLE_REF)
    scale_factor = E_ref / trans_ref 

    # 3. Absorption (Robust Search)
    abs_path = find_file_universal(analysis_config.BASE_DIR, analysis_config.ABSORPTION_KEYWORD)
    absorption_rate = get_absorption_rate(abs_path)

    # 4. Scan Files
    # Note: We stick to .txt for spectra files as that is standard from spectrometers
    files = [f for f in os.listdir(analysis_config.DATA_DIR) 
             if 'spectrum' in f.lower() and f.endswith('.txt')]
    
    if not files: print("No spectrum files found."); return

    data_list = []
    print(f"Scanning {len(files)} files...")
    
    for f in files:
        full_path = os.path.join(analysis_config.DATA_DIR, f)
        
        # A. Get Angle
        angle = get_header_value(full_path, "Angle (deg):")
        
        # B. Get Pulse Width
        pulse_width = get_header_value(full_path, "Pulse Width (s):")
        
        if angle is not None:
            entry = {'filename': f, 'angle': angle}
            
            # Default to NaN if missing
            if pulse_width is None or pulse_width == 0:
                entry['pulse_width_s'] = np.nan
            else:
                entry['pulse_width_s'] = pulse_width
                
            data_list.append(entry)
            
    if not data_list: print("Error: Could not extract angles."); return
    
    df = pd.DataFrame(data_list)
    df = df.sort_values(by='angle').reset_index(drop=True)
    
    # 5. CALCULATE PHYSICS
    transmissions = calib_func(df['angle'])
    
    # Energy
    df['incident_energy_nJ'] = scale_factor * transmissions
    df['absorbed_energy_nJ'] = df['incident_energy_nJ'] * absorption_rate
    
    # Fluence (µJ/cm²)
    df['fluence_uJ_cm2'] = (df['absorbed_energy_nJ'] * 1e-3) / area_cm2
    
    # Power Density (W/cm²)
    # Formula: (Fluence_uJ * 1e-6) / PulseWidth_s
    df['Power_Density_W_cm2'] = (df['fluence_uJ_cm2'] * 1e-6) / df['pulse_width_s']
    df['Power_Density_W_cm2'] = df['Power_Density_W_cm2'].fillna(0)

    # 6. Save
    save_path = os.path.join(analysis_config.RESULTS_DIR, analysis_config.ENERGY_FILENAME)
    df.to_csv(save_path, index=False)
    
    print(f" -> Saved Manifest: {save_path}")
    print("\nPreview:")
    print(df[['filename', 'angle', 'fluence_uJ_cm2', 'Power_Density_W_cm2']].head())

    # 7. Plot
    plt.figure(figsize=(8, 5))
    plt.plot(df['angle'], df['fluence_uJ_cm2'], 'g^--', label='Fluence')
    plt.xlabel('Angle (deg)')
    plt.ylabel('Fluence (µJ/cm²)')
    plt.title('Energy Density Profile')
    plt.grid(True, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()