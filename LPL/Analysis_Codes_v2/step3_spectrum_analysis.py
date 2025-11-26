import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import pandas as pd
import os
import analysis_config as config

# =============================================================================
#  STEP 3: SPECTRA ANALYSIS (PHYSICS RESULTS)
# =============================================================================
#  1. Reads 'OPTIMIZED_SPECTRA.txt' (Output of Step 2).
#  2. Calculates FWHM and Integration Intensity.
#  3. Generates the S-Curve and Waterfall plots.
# =============================================================================

def fwhm(x, y):
    """Calculates FWHM."""
    if np.max(y) == 0: return 0.0
    y_norm = y / np.max(y)
    lev50 = 0.5
    if np.all(y_norm < lev50): return 0.0
    
    center = np.argmax(y_norm)
    
    # Simple Interp for edges
    i = center
    while i > 0 and y_norm[i] > lev50: i -= 1
    x1 = np.interp(lev50, [y_norm[i], y_norm[i+1]], [x[i], x[i+1]])
    
    i = center
    while i < len(y_norm)-1 and y_norm[i] > lev50: i += 1
    x2 = np.interp(lev50, [y_norm[i], y_norm[i-1]], [x[i], x[i-1]])
    
    return x2 - x1

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
    print("=== STEP 3: PHYSICS ANALYSIS & PLOTTING ===")
    
    # 1. Load Data
    spec_path = os.path.join(config.RESULTS_DIR, "OPTIMIZED_SPECTRA.txt")
    manifest_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    
    if not os.path.exists(spec_path):
        print("CRITICAL ERROR: Run Step 2 first to generate OPTIMIZED_SPECTRA.txt"); return

    data = np.loadtxt(spec_path)
    wavelengths = data[:, 0]
    spectra = data[:, 1:] # Columns 1 to N are files
    
    df = pd.read_csv(manifest_path)
    
    # 2. Calculate Metrics
    fwhm_list = []
    intensity_list = []
    
    for i, row in df.iterrows():
        spec = spectra[:, i]
        
        # Get Time from original file for normalization
        orig_path = os.path.join(config.DATA_DIR, row['filename'])
        t_int = get_integration_time(orig_path)
        
        # Baseline Correction
        baseline = np.mean(spec[:10])
        spec_corr = np.maximum(spec - baseline, 0)
        
        # Metrics
        area = np.trapz(spec_corr, wavelengths)
        intensity_list.append(area / t_int) # Area per second
        fwhm_list.append(fwhm(wavelengths, spec_corr))

    # 3. Save Final CSV
    df['FWHM_nm'] = fwhm_list
    df['Integrated_Intensity'] = intensity_list
    
    csv_path = os.path.join(config.RESULTS_DIR, "FINAL_RESULTS.csv")
    df.to_csv(csv_path, index=False)
    print(f" -> Saved Final Table: {csv_path}")

    # 4. PLOT 1: The S-Curve (Physics)
    energies = df['fluence_uJ_cm2'].values
    sort_idx = np.argsort(energies)
    
    fig, ax1 = plt.subplots(figsize=(8, 6))
    ax2 = ax1.twinx()
    
    ax1.semilogx(energies[sort_idx], np.array(fwhm_list)[sort_idx], 'bo--', label='FWHM')
    ax2.loglog(energies[sort_idx], np.array(intensity_list)[sort_idx], 'ro-', label='Intensity')
    
    ax1.set_xlabel('Fluence (µJ/cm²)')
    ax1.set_ylabel('FWHM (nm)', color='b')
    ax2.set_ylabel('Integrated Intensity', color='r')
    plt.title('ASE Characterization Curve')
    plt.tight_layout()
    plt.savefig(os.path.join(config.RESULTS_DIR, "Plot_SCurve.png"))

    # 5. PLOT 2: Spectral Evolution (Visualization)
    plt.figure(figsize=(10, 6))
    colors = cm.jet(np.linspace(0, 1, len(df)))
    
    for i in sort_idx:
        y = spectra[:, i]
        # Normalize 0-1 for visualization
        if np.max(y) > np.min(y):
            y_norm = (y - np.min(y)) / (np.max(y) - np.min(y))
        else:
            y_norm = y
            
        plt.plot(wavelengths, y_norm, color=colors[i], alpha=0.6)
        
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Normalized Intensity')
    plt.title('Spectral Evolution (Blue=Low E, Red=High E)')
    plt.savefig(os.path.join(config.RESULTS_DIR, "Plot_Spectra_Evolution.png"))
    
    print(" -> Plots saved.")
    plt.show()

if __name__ == "__main__":
    main()