# ========================================================
# ASE ANALYSIS CONFIGURATION
# ========================================================

# --- File Paths ---
CSV_CALIB_PATH = r"C:\Users\Equipe_OPAL\Desktop\Kaya\gentec data\20251119_185705_wheel_calibration_190_to_210_by_5.csv"
DATA_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya"  
RESULTS_DIR = "ASE Results"
ENERGY_FILENAME = "energies.csv"

# --- Absorption Lookup Settings ---
ABSORPTION_FILENAME = "absorption_spectrum.txt"
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