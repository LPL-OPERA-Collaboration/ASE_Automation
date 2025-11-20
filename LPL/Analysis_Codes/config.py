# ========================================================
# ASE ANALYSIS CONFIGURATION
# ========================================================

# --- File Paths ---
# Use 'r' before strings to handle Windows backslashes correctly
CSV_CALIB_PATH = r"C:\Users\Equipe_OPAL\Desktop\Kaya\gentec data\20251119_185705_wheel_calibration_190_to_210_by_5.csv"

# Directory containing the spectrum files AND the absorption file
DATA_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya"  

RESULTS_DIR = "ASE Results"
MANUAL_EXCEL_PATH = "Manual_ASE_data.xlsx"

# Shared Filename for communication between Step 1 and Step 2
ENERGY_FILENAME = "energies.csv"

# --- Absorption Lookup Settings ---
# The name of your absorption file located inside DATA_DIR
ABSORPTION_FILENAME = "absorption_spectrum.txt"  # <--- CHANGE THIS to your actual file name
TARGET_WAVELENGTH = 337     # The pump laser wavelength (nm)
ABS_SKIP_HEADER = 55        # Number of header lines to skip in the absorption file

# ========================================================
# CONSTANTS (Equipment Specs at 337 nm)
# ========================================================
OD1 = 1.001   # Transmission = 10^(-1.001) ~ 9.9%
OD3 = 3.163   # Transmission = 10^(-3.163) ~ 0.068%
NO_OD = 0     # Transmission = 10^0 = 1 (100%)

TRANSMISSION_LENS = 0.959  # Static transmission of the focusing lens

# ========================================================
# DAILY MEASUREMENT SETTINGS (The "Anchor")
# ========================================================
# Update these three values every day before running analysis:
# 1. Angle where you measured (deg)
# 2. Raw Energy reading on the screen (nJ)
# 3. The OD Filter you used for this reading (OD1, OD3, or NO_OD)

ANGLE_REF = 280
RAW_ENERGY_READ = 24
TODAYS_OD = OD3

# ========================================================
# ANALYSIS PARAMETERS
# ========================================================
SMOOTH_WINDOW = 51         # Filter window size (must be odd, >= 3)
SMOOTH_START_INDEX = 31    # Index to start visual checks for smoothing