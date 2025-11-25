import os

# ========================================================
# ASE ANALYSIS CONFIGURATION
# ========================================================

# --- Directory Structure ---
# Base directory for the specific measurement session (Update this daily)
BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251118_Measurement_56"

# Derived Directories
DATA_DIR = os.path.join(BASE_DIR, "Raw_Data")  # Where spectra & absorption files are
RESULTS_DIR = os.path.join(BASE_DIR, "Results") # Where analysis outputs go

# --- Dynamic File Locators ---
ENERGY_FILENAME = "energies.csv"

# Keywords to search for in BASE_DIR
CALIBRATION_FILE_KEYWORD = "calibration" 
ABSORPTION_FILE_KEYWORD = "absorption"

# --- Absorption Lookup Settings ---
TARGET_WAVELENGTH = 337     # Pump laser wavelength (nm)

# ========================================================
# EXCITATION SPOT GEOMETRY
# ========================================================
# Shape options: "rectangle", "circle", "ellipse"
SPOT_SHAPE = "rectangle"

# Dimensions in MICRONS (µm)
# - Rectangle: DIM_1 = Height (Length), DIM_2 = Width
# - Circle:    DIM_1 = Diameter,        DIM_2 = (Ignored)
# - Ellipse:   DIM_1 = Major Axis,      DIM_2 = Minor Axis
SPOT_DIM_1_UM = 4000.0  
SPOT_DIM_2_UM = 500.0   

# ========================================================
# CONSTANTS (Equipment Specs at 337 nm)
# ========================================================
OD1 = 1.001   
OD3 = 3.163   
NO_OD = 0     
TRANSMISSION_LENS = 0.959  

# ========================================================
# DAILY MEASUREMENT SETTINGS (The "Anchor")
# ========================================================
ANGLE_REF = 280
RAW_ENERGY_READ = 24
TODAYS_OD = OD3

# ========================================================
# ANALYSIS PARAMETERS
# ========================================================
SMOOTH_WINDOW = 51         
SMOOTH_START_INDEX = 31