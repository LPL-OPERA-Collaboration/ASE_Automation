import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button
import pandas as pd
from scipy.signal import savgol_filter
import os
import analysis_config as config

# =============================================================================
#  STEP 2: SIGNAL PROCESSING (METADATA IN HEADERS)
# =============================================================================

# --- USER SETTINGS -----------------------------------------------------------

# 1. THE CURSOR
# Files BEFORE this index will be LOCKED (kept from previous run).
# Files AFTER (and including) this index will be processed with NEW settings.
START_SMOOTHING_INDEX = 0

# 2. NEW SETTINGS (Applied only to files >= START_SMOOTHING_INDEX)
# This tag will be written into the CSV header.
SMOOTH_WINDOW = 51

# VIEW SETTINGS
COLS = 3             
ROWS_PER_VIEW = 4    
CROP_MIN = None   
CROP_MAX = None    
# -----------------------------------------------------------------------------

def smooth(x, window):
    if window < 3: return x
    if window % 2 == 0: window += 1 
    if len(x) < window: return x
    return savgol_filter(x, window, 3)

def main():
    print("=== STEP 2: SIGNAL PROCESSING (METADATA HEADERS) ===")
    
    # 1. Load Manifest to get Angles/Filenames
    manifest_path = os.path.join(config.RESULTS_DIR, config.ENERGY_FILENAME)
    if not os.path.exists(manifest_path):
        print("CRITICAL: Run Step 1 first."); return
    df = pd.read_csv(manifest_path)
    
    # Prepare base labels (Angles)
    if 'angle' in df.columns:
        base_labels = [str(a) for a in df['angle'].tolist()]
    else:
        base_labels = df['filename'].tolist()

    # 2. Setup Wavelengths
    first_path = os.path.join(config.DATA_DIR, df.iloc[0]['filename'])
    w_all = np.loadtxt(first_path, delimiter=',')[:, 0]
    mask = np.ones_like(w_all, dtype=bool)
    if CROP_MIN: mask &= (w_all >= CROP_MIN)
    if CROP_MAX: mask &= (w_all <= CROP_MAX)
    wavelengths = w_all[mask]
    n_files = len(df)
    
    # 3. Load PREVIOUS Results (Stateful Check)
    prev_results_path = os.path.join(config.RESULTS_DIR, "OPTIMIZED_SPECTRA.csv")
    prev_matrix = None
    prev_headers = None
    
    if os.path.exists(prev_results_path):
        print(f" -> Found previous results. Loading...")
        try:
            df_prev = pd.read_csv(prev_results_path)
            if 'Wavelength' in df_prev.columns:
                # Save the headers so we can preserve the old tags (e.g. "w=101")
                prev_headers = df_prev.columns.tolist() 
                # Drop Wavelength to get data matrix
                prev_matrix = df_prev.drop(columns=['Wavelength']).values
                print(f" -> Successfully loaded previous state.")
            else:
                print(f" -> WARNING: CSV missing 'Wavelength' header. Starting fresh.")
                
            if prev_matrix is not None and prev_matrix.shape[1] != n_files:
                print(f" -> WARNING: File count mismatch. Starting fresh.")
                prev_matrix = None
        except Exception as e:
            print(f" -> WARNING: Read error ({e}). Starting fresh.")
    else:
        print(" -> No previous results found. Starting fresh.")

    # 4. Process Loop
    print(f" -> Processing...")
    print(f"    [0 - {START_SMOOTHING_INDEX-1}] : LOCKED (Preserving old headers)")
    print(f"    [{START_SMOOTHING_INDEX} - End] : NEW PROCESSING (w={SMOOTH_WINDOW})")
    
    optimized_matrix = np.zeros((len(wavelengths), n_files))
    raw_debug_matrix = np.zeros((len(wavelengths), n_files))
    
    # We will build a new list of headers for the output CSV
    final_headers = []
    
    # We also track "Mode" just for the Plot title (display only)
    plot_titles = []

    for i, row in df.iterrows():
        try:
            # Load Raw
            fpath = os.path.join(config.DATA_DIR, row['filename'])
            raw_full = np.loadtxt(fpath, delimiter=',')[:, 1]
            intensity = raw_full[mask]
            raw_debug_matrix[:, i] = intensity
            
            base_name = base_labels[i]
            
            # --- DECISION LOGIC ---
            if i < START_SMOOTHING_INDEX:
                # ZONE A: HISTORY (LOCKED)
                if prev_matrix is not None:
                    optimized_matrix[:, i] = prev_matrix[:, i]
                    
                    # PRESERVE OLD HEADER TAG
                    # prev_headers[0] is Wavelength, so file i is at index i+1
                    old_h = prev_headers[i+1] 
                    final_headers.append(old_h)
                    
                    # For Plotting: Extract the tag from the string
                    # Example: "90.0 (w=101)" -> "LOCKED (w=101)"
                    if "(" in old_h:
                        tag = old_h.split('(')[-1].replace(')', '')
                        plot_titles.append(f"LOCKED ({tag})")
                    else:
                        plot_titles.append("LOCKED")
                else:
                    # Fallback
                    optimized_matrix[:, i] = intensity
                    final_headers.append(f"{base_name} (RAW)")
                    plot_titles.append("RAW (Fallback)")
            else:
                # ZONE B: NEW ACTION
                optimized_matrix[:, i] = smooth(intensity, SMOOTH_WINDOW)
                
                # CREATE NEW HEADER TAG
                tag = f"w={SMOOTH_WINDOW}"
                final_headers.append(f"{base_name} ({tag})")
                plot_titles.append(f"NEW ({tag})")
                
        except: 
            final_headers.append(f"ERROR_{i}")
            plot_titles.append("ERROR")

    # 5. Save Results AS CSV
    df_out = pd.DataFrame(optimized_matrix, columns=final_headers)
    df_out.insert(0, "Wavelength", wavelengths)
    
    try:
        df_out.to_csv(prev_results_path, index=False)
        print(f" -> Saved merged results to: {prev_results_path}")
    except PermissionError:
        print("\n" + "="*60)
        print("CRITICAL ERROR: Could not save file! Is it open in Excel?")
        print(f"Path: {prev_results_path}")
        print("="*60 + "\n")
        return

    # =========================================================================
    # 6. VISUALIZATION
    # =========================================================================
    print(" -> Opening Window...")
    
    plots_per_page = COLS * ROWS_PER_VIEW
    fig, axes = plt.subplots(ROWS_PER_VIEW, COLS, figsize=(14, 9))
    plt.subplots_adjust(right=0.85, hspace=0.6, wspace=0.3) # More hspace for multiline titles
    axes_flat = axes.flatten()
    
    lines_raw = []
    lines_opt = []
    titles = []
    backgrounds = [] 

    for ax in axes_flat:
        l_r, = ax.plot([], [], 'k-', alpha=0.3, lw=1)
        l_o, = ax.plot([], [], 'r-', lw=1.5)
        lines_raw.append(l_r)
        lines_opt.append(l_o)
        titles.append(ax.set_title(""))
        backgrounds.append(ax)
        ax.set_yticks([])

    state = {'start_index': 0}

    def update_view():
        start_idx = state['start_index']
        
        for k in range(plots_per_page):
            file_idx = start_idx + k
            
            if file_idx < n_files:
                # Data
                lines_raw[k].set_data(wavelengths, raw_debug_matrix[:, file_idx])
                lines_opt[k].set_data(wavelengths, optimized_matrix[:, file_idx])
                
                ax = backgrounds[k]
                ax.relim()
                ax.autoscale_view()
                ax.set_visible(True)
                
                # Titles
                angle_val = base_labels[file_idx]
                status_text = plot_titles[file_idx]
                
                titles[k].set_text(f"{angle_val}°\n{status_text}")
                
                # Colors
                if "LOCKED" in status_text:
                    color = 'blue'; lw = 1; alpha = 0.5
                elif "NEW" in status_text:
                    color = 'red'; lw = 2; alpha = 1.0
                else: 
                    color = 'black'; lw=1; alpha=0.5

                if file_idx == START_SMOOTHING_INDEX:
                    titles[k].set_text(f"{angle_val}°\n>>> START NEW <<<")
                    titles[k].set_fontweight('bold')
                    color = 'green'; lw = 3; alpha = 1.0

                titles[k].set_color(color)
                for spine in ax.spines.values(): 
                    spine.set_edgecolor(color); spine.set_linewidth(lw); spine.set_alpha(alpha)
            else:
                backgrounds[k].set_visible(False)
        
        fig.canvas.draw_idle()

    # Buttons
    ax_prev = plt.axes([0.87, 0.55, 0.1, 0.05])
    ax_next = plt.axes([0.87, 0.48, 0.1, 0.05])
    btn_prev = Button(ax_prev, '▲ UP')
    btn_next = Button(ax_next, '▼ DOWN')

    def scroll_down(event):
        if state['start_index'] + COLS < n_files: state['start_index'] += COLS; update_view()
    def scroll_up(event):
        if state['start_index'] - COLS >= 0: state['start_index'] -= COLS; update_view()

    btn_next.on_clicked(scroll_down)
    btn_prev.on_clicked(scroll_up)
    
    def on_scroll_wheel(event):
        if event.button == 'up': scroll_up(None)
        elif event.button == 'down': scroll_down(None)
    fig.canvas.mpl_connect('scroll_event', on_scroll_wheel)
    
    # Info Box
    fig.text(0.86, 0.85, "STATUS", fontsize=11, fontweight='bold')
    fig.text(0.86, 0.82, f"Cursor @ #{START_SMOOTHING_INDEX}", color='green')
    fig.text(0.86, 0.79, f"Previous: LOCKED", color='blue')
    fig.text(0.86, 0.76, f"Current:  w={SMOOTH_WINDOW}", color='red')

    update_view()
    plt.show()

if __name__ == "__main__":
    main()