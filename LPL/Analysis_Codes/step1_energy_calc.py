import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from scipy.interpolate import interp1d
import os
import re  # Added to parse filenames
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

# =============================================================================
# EXECUTION
# =============================================================================
def main():
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    
    print(f"=== STEP 1: ENERGY CALCULATION ===")
    
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
    
    # 3. DETERMINE ANGLES FROM FILES
    print(f"\nScanning for spectra in: {config.DATA_DIR}")
    try:
        files = [f for f in os.listdir(config.DATA_DIR) if f.startswith('spectrum_') and f.endswith('.txt')]
    except FileNotFoundError:
        print(f"ERROR: Directory not found: {config.DATA_DIR}")
        return

    if not files:
        print(f"ERROR: No 'spectrum_*.txt' files found in {config.DATA_DIR}")
        print("Step 1 now requires spectrum files to determine the angles.")
        return

    # Extract angles from filenames
    print(f"Found {len(files)} spectrum files. Extracting angles...")
    
    extracted_angles = []
    for f in files:
        angle = extract_angle_from_filename(f)
        if angle is not None:
            extracted_angles.append(angle)
    
    # Sort numerically so energies line up with the spectrum loop in Step 2
    angles = np.array(sorted(extracted_angles))
    print(f" > Using {len(angles)} angles extracted from files.")
    print(f" > Range: {angles[0]:.2f}° to {angles[-1]:.2f}°")

    # 4. Calculate Energies
    transmissions = calib_func(angles)
    energies = scale_factor * transmissions
    
    # 5. Save Data
    save_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    np.savetxt(save_path, energies, header='Measured energies in nJ')
    
    print(f"\nSUCCESS: Energies calculated for {len(angles)} points.")
    print(f"Saved to: {save_path}")

    # 6. Check Plot
    plt.figure(figsize=(8, 5))
    plt.plot(angles, energies, 'o-', label='Calculated Energy Profile')
    plt.plot(config.ANGLE_REF, E_ref, 'r*', markersize=15, label='Daily Anchor Point')
    plt.xlabel('Angle (degrees)')
    plt.ylabel('Energy (nJ)')
    plt.title(f'Energy Calibration Check [Data Driven]\nRef: {E_ref:.2f} nJ @ {config.ANGLE_REF}°')
    plt.grid(True, which='both', alpha=0.6)
    plt.legend()
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()