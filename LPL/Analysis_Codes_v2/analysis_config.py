import os

# =============================================================================
#  ASE ANALYSIS CONFIGURATION (STATIC SETTINGS)
# =============================================================================

# 1. EQUIPMENT & CONSTANTS
OD1 = 1.001   
OD3 = 3.163   
NO_OD = 0     
TRANSMISSION_LENS = 0.959  
TARGET_WAVELENGTH = 337     

# 2. FILE SYSTEM
# [USER ACTION] Change this path daily
BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251126_Measurement_6"

# Derived Directories
DATA_DIR = os.path.join(BASE_DIR, "Raw_Data") 
RESULTS_DIR = os.path.join(BASE_DIR, "Results")

# Keywords
ENERGY_FILENAME = "energies.csv"
CALIBRATION_KEYWORD = "calibration" 
ABSORPTION_KEYWORD = "absorption"

# 3. EXPERIMENT VARIABLES
ANGLE_REF = 280
RAW_ENERGY_READ = 24 
TODAYS_OD = OD3

# 4. GEOMETRY
SPOT_SHAPE = "rectangle"
SPOT_DIM_1_UM = 4000.0  
SPOT_DIM_2_UM = 500.0