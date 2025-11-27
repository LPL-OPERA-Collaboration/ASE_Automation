import os

# =============================================================================
#  ANALYSIS CONFIGURATION
# =============================================================================

# 1. --- EQUIPMENT & CONSTANTS ---
OD1 = 1.001   # "Real" ODs of the ND filters at 337 nm, measured by an absorption spectrometer
OD3 = 3.163   
NO_OD = 0     
TRANSMISSION_LENS = 0.959  # Correction factor for the lens between the energymeter and sample (probably at 337 nm).
TARGET_WAVELENGTH = 337   # The wavelelength to read on the absorption spectrum. 337 nm for N2 laser.


# 2. --- FILE SYSTEM --- (please referenciate "file_location_memo.py" for folder structure)
# Base Directory (please set it to your data folder, which is created by aquisition code)
# (it shoud look like BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251127_Measurement_2")
BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251127_Measurement_2"

# Derived Directories
# (location of subfolders)
DATA_DIR = os.path.join(BASE_DIR, "Raw_Data")   # this contains raw spectra aquired by aquisition codes
RESULTS_DIR = os.path.join(BASE_DIR, "Results")   # this is where analysis code save results

# Keywords
# (the analysis codes look for the files with these keywords)
ENERGY_FILENAME = "energies.csv"
# (NOTE: the codes only look for calibration and absorption at the base directory (BASE_DIR), so make sure to put these files in the base directory)
CALIBRATION_KEYWORD = "calibration" 
ABSORPTION_KEYWORD = "absorption"


# 3. EXPERIMENT VARIABLES
ANGLE_REF = 280     # The "Anchor" angle for each measuement.
RAW_ENERGY_READ_NJ = 24      # Raw energy value you read at ANGLE_REF in Gentec meter (in nJ).
TODAYS_OD = OD3     # OD of the ND filter you put in front of Gentec meter when you measured RAW_ENERGY_READ_NJ.
                    # Choose from the constants defined in Section 1 (e.g., OD1, OD3, NO_OD).


# 4. GEOMETRY
SPOT_SHAPE = "rectangle"    # Beam shape of excitation laser (normally "rectangle" for ASE measurements)
SPOT_DIM_1_UM = 4000.0      
SPOT_DIM_2_UM = 500.0
# DEFINITIONS:
# - Rectangle: DIM_1 = Length (Height),    DIM_2 = Width
# - Circle:    DIM_1 = Diameter,           DIM_2 = (Ignored)
# - Ellipse:   DIM_1 = Major Axis (Long),  DIM_2 = Minor Axis (Short)