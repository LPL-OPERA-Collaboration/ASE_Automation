import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import pandas as pd
from scipy.interpolate import interp1d
import os
import analysis_config as config

# =============================================================================
#  STEP 3: PHYSICS ANALYSIS (ROI INTEGRATION)
# =============================================================================

INPUT_FILENAME = "COMBINED_smoothed_spectra.csv"

# --- USER SETTINGS (NEW!) ----------------------------------------------------
# Define the range to calculate "Integrated Intensity".
# Set to None to use the full range.
# Example: If your peak is at 337nm, integrate 330 to 350 to exclude noise.
INTEGRATION_MIN = None   # e.g., 330.0
INTEGRATION_MAX = None   # e.g., 350.0
# -----------------------------------------------------------------------------

def fwhm(x, y):
    """Calculates FWHM."""
    if np.max(y) == 0: return 0.0
    y_norm = y / np.max(y)
    lev50 = 0.5
    if np.all(y_norm < lev50): return 0.0
    center = np.argmax(y_norm)
    
    i = center
    while i > 0 and y_norm[i] > lev50: i -= 1
    x1 = np.interp(lev50, [y_norm[i], y_norm[i+1]], [x[i], x[i+1]])
    
    i = center
    while i < len(y_norm)-1 and y_norm[i] > lev50: i += 1
    x2 = np.interp(lev50, [y_norm[i], y_norm[i-1]], [x[i], x[i-1]])
    
    return x2 - x1

def calculate_ase_threshold(energy, fwhm_values):
    try:
        idx = np.argsort(energy)
        x_s = energy[idx]
        y_s = np.array(fwhm_values)[idx]
        if len(x_s) < 4: return 0.0 
        
        x_new = np.linspace(x_s.min(), x_s.max(), 500)
        f = interp1d(x_s, y_s, kind='cubic', bounds_error=False, fill_value="extrapolate")
        y_new = f(x_new)
        dy = np.gradient(y_new, x_new)
        
        mask = x_new > (x_new.min() + 0.05 * (x_new.max() - x_new.min()))
        if np.sum(mask) == 0: return 0.0
        
        threshold_idx = np.argmin(dy[mask])
        return x_new[mask][threshold_idx]
    except: return 0.0

def get_integration_time(filepath):
    try:
        with open(filepath, 'r', encoding='latin-1') as f:
            for _ in range(20):
                line = f.readline()
                if "Integration Time (s):" in line:
                    return float(line.split(':')[1].strip())
    except: pass
    return 1.0

def main():
    print("=== STEP 3: PHYSICS ANALYSIS ===")
    
    # 1. Load Data
    step2_output_path = os.path.join(config.RESULTS_DIR, INPUT_FILENAME)
    manifest_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    
    if not os.path.exists(step2_output_path): print(f"CRITICAL: Run Step 2 first."); return
    if not os.path.exists(manifest_path): print("CRITICAL: Run Step 1 first."); return

    print(f" -> Loading Spectra from: {INPUT_FILENAME}")
    df_spectra = pd.read_csv(step2_output_path)
    wavelengths = df_spectra['Wavelength'].values
    spectra_matrix = df_spectra.drop(columns=['Wavelength']).values
    
    print(f" -> Loading Energy Manifest...")
    df_manifest = pd.read_csv(manifest_path)
    
    if spectra_matrix.shape[1] != len(df_manifest):
        print(f"ERROR: Dimension Mismatch! Re-run Step 1 and 2."); return
    
    # --- ROI LOGIC ---
    # Create a mask for calculations (but keep full wavelength for plotting)
    calc_mask = np.ones_like(wavelengths, dtype=bool)
    if INTEGRATION_MIN: calc_mask &= (wavelengths >= INTEGRATION_MIN)
    if INTEGRATION_MAX: calc_mask &= (wavelengths <= INTEGRATION_MAX)
    
    wl_calc = wavelengths[calc_mask]
    print(f" -> Integration Range: {wl_calc.min():.1f}nm to {wl_calc.max():.1f}nm")
    
    # 3. Calculate Physics Metrics
    fwhm_list = []
    intensity_list = []
    
    for i, row in df_manifest.iterrows():
        spec = spectra_matrix[:, i]
        orig_path = os.path.join(config.DATA_DIR, row['filename'])
        t_int = get_integration_time(orig_path)
        
        # Baseline Correction
        baseline = np.mean(spec[:10])
        spec_corr = np.maximum(spec - baseline, 0)
        
        # METRIC 1: Intensity (Uses ROI)
        # We only integrate the part of the spectrum inside the mask
        spec_for_calc = spec_corr[calc_mask]
        area = np.trapz(spec_for_calc, wl_calc)
        intensity_list.append(area / t_int) 
        
        # METRIC 2: FWHM (Uses Full Spectrum)
        # FWHM needs the full shape to find the edges accurately
        fwhm_list.append(fwhm(wavelengths, spec_corr))

    # 4. Threshold & Save
    energies = df_manifest['fluence_uJ_cm2'].values
    threshold = calculate_ase_threshold(energies, fwhm_list)
    print(f"\n   [RESULT] Calculated ASE Threshold: {threshold:.2f} µJ/cm²\n")

    df_manifest['FWHM_nm'] = fwhm_list
    df_manifest['Integrated_Intensity'] = intensity_list
    df_manifest['Calculated_Threshold'] = threshold
    
    final_csv_path = os.path.join(config.RESULTS_DIR, "FINAL_RESULTS.csv")
    df_manifest.to_csv(final_csv_path, index=False)
    print(f" -> Saved Final Table: {final_csv_path}")

    # =========================================================================
    # 5. PLOTTING
    # =========================================================================
    
    sort_idx = np.argsort(energies)
    e_sorted = energies[sort_idx]
    f_sorted = np.array(fwhm_list)[sort_idx]
    i_sorted = np.array(intensity_list)[sort_idx]
    colors = cm.jet(np.linspace(0, 1, len(df_manifest)))

    # PLOT A: S-Curve
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    ax1.semilogx(e_sorted, f_sorted, 'bo--', label='FWHM')
    ax1.set_xlabel('Fluence (µJ/cm²)')
    ax1.set_ylabel('FWHM (nm)', color='b', fontweight='bold')
    ax2.loglog(e_sorted, i_sorted, 'ro-', label='Intensity')
    ax2.set_ylabel('Integrated Intensity', color='r', fontweight='bold')
    if threshold > 0:
        plt.axvline(x=threshold, color='k', linestyle='--', label=f'Thresh: {threshold:.1f}')
    plt.title(f'ASE Curve (Th ~ {threshold:.2f} µJ/cm²)')
    plt.tight_layout()
    plt.savefig(os.path.join(config.RESULTS_DIR, "Plot_SCurve.png"))

    # PLOT B: NORMALIZED (Full Spectrum)
    plt.figure(figsize=(10, 6))
    for i in sort_idx:
        y = spectra_matrix[:, i]
        if np.max(y) > np.min(y):
            y_norm = (y - np.min(y)) / (np.max(y) - np.min(y))
        else: y_norm = y
        plt.plot(wavelengths, y_norm, color=colors[i], alpha=0.6, linewidth=1)
        
    # Draw vertical lines to show Integration Range
    if INTEGRATION_MIN: plt.axvline(x=INTEGRATION_MIN, color='k', linestyle=':', alpha=0.5)
    if INTEGRATION_MAX: plt.axvline(x=INTEGRATION_MAX, color='k', linestyle=':', alpha=0.5)
        
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Normalized Intensity')
    plt.title('Normalized Spectral Evolution (Dotted lines = Calc Region)')
    plt.tight_layout()
    plt.savefig(os.path.join(config.RESULTS_DIR, "Plot_Spectra_Normalized.png"))

    # PLOT C: UNNORMALIZED (Full Spectrum)
    plt.figure(figsize=(10, 6))
    for i in sort_idx:
        y = spectra_matrix[:, i]
        plt.plot(wavelengths, y, color=colors[i], alpha=0.6, linewidth=1)
    
    if INTEGRATION_MIN: plt.axvline(x=INTEGRATION_MIN, color='k', linestyle=':', alpha=0.5)
    if INTEGRATION_MAX: plt.axvline(x=INTEGRATION_MAX, color='k', linestyle=':', alpha=0.5)

    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Unnormalized Intensity (Counts)')
    plt.title('Unnormalized Intensity Growth')
    plt.tight_layout()
    plt.savefig(os.path.join(config.RESULTS_DIR, "Plot_Spectra_Unnormalized.png"))
    
    print(" -> Plots saved.")
    plt.show()

if __name__ == "__main__":
    main()