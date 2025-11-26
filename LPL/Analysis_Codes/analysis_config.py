import os

# =============================================================================
#  ASE ANALYSIS CONFIGURATION (THE CONTROL PANEL)
# =============================================================================
#  INSTRUCTIONS FOR THE OPERATOR:
#  This file is organized by TOPIC.
#  1. CONSTANTS & EQUIPMENT: Fixed physics values (Define these first).
#  2. FILE SYSTEM: Where your data is stored.
#  3. EXPERIMENTAL READINGS: The specific numbers from your lab notebook.
#  4. GEOMETRY: The shape and size of the laser spot.
#  5. ANALYSIS: Settings for the calculation algorithms.
#
#  NOTE: Use r"path" for Windows paths to avoid errors with backslashes.
# =============================================================================

# =============================================================================
# 1. CONSTANTS & EQUIPMENT SPECS (STATIC)
# =============================================================================
# Optical Density (OD) filter values
OD1 = 1.001   
OD3 = 3.163   
NO_OD = 0     

# Equipment characteristics at 337 nm
TRANSMISSION_LENS = 0.959  
TARGET_WAVELENGTH = 337     

# =============================================================================
# 2. FILE SYSTEM & PATHS
# =============================================================================
# [USER ACTION] The absolute path to today's measurement folder.
# This folder MUST contain the Calibration (.csv) and Absorption (.txt) files.
BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251126_Measurement_3"

# Derived Directories (Automatically set based on BASE_DIR)
# The code expects spectra to be in a subfolder named "Raw_Data"
DATA_DIR = os.path.join(BASE_DIR, "Raw_Data") 
RESULTS_DIR = os.path.join(BASE_DIR, "Results")

# Keywords for auto-detecting files
ENERGY_FILENAME = "energies.csv"
CALIBRATION_FILE_KEYWORD = "calibration" 
ABSORPTION_FILE_KEYWORD = "absorption"

# =============================================================================
# 3. EXPERIMENTAL READINGS (CHANGE DAILY)
# =============================================================================
# [USER ACTION] The Angle where you measured the Reference Energy.
# Example: If you put the detector at 280 degrees to measure the pump energy.
ANGLE_REF = 280

# [USER ACTION] The Raw Energy reading from the power meter (in nJ).
# NOTE: Enter the value read from the screen (before math).
RAW_ENERGY_READ = 24 

# [USER ACTION] Which Optical Density (OD) filter was used for the reading above?
# Choose from the constants defined in Section 1 (e.g., OD1, OD3, NO_OD).
TODAYS_OD = OD3

# =============================================================================
# 4. SAMPLE GEOMETRY (SETUP DEPENDENT)
# =============================================================================
# [USER ACTION] The shape of the excitation laser spot on the sample.
# Options: "rectangle" (stripe), "circle", "ellipse"
SPOT_SHAPE = "rectangle"

# [USER ACTION] Dimensions in MICRONS (µm).
# DEFINITIONS:
# - Rectangle: DIM_1 = Length (Height),    DIM_2 = Width
# - Circle:    DIM_1 = Diameter,           DIM_2 = (Ignored)
# - Ellipse:   DIM_1 = Major Axis (Long),  DIM_2 = Minor Axis (Short)
SPOT_DIM_1_UM = 4000.0  
SPOT_DIM_2_UM = 500.0   

# =============================================================================
# 5. ANALYSIS ALGORITHMS
# =============================================================================
# Smoothing Settings
# Window size must be an ODD number (e.g., 51, 101).
# Higher = smoother curves but broader peaks. Lower = noisier but sharper.
SMOOTH_WINDOW = 51         
SMOOTH_START_INDEX = 31