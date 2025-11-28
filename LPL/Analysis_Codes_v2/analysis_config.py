import os

# =============================================================================
#  ANALYSIS CONFIGURATION
# =============================================================================
# INSTRUCTIONS:
# 1. UPDATE 'Section 2' to point to your new data folder.
# 2. UPDATE 'Section 3' with the reference energy you measured today.
# 3. CHECK 'Section 4' if you changed the spot size.

# 1. --- EQUIPMENT & CONSTANTS ---
# These are physical properties of your lab equipment (Filters & Lenses).
# DO NOT CHANGE normally.
OD1 = 1.001   # "Real" ODs of the ND filters at 337 nm, measured by an absorption spectrometer
OD3 = 3.163   
NO_OD = 0     # No filter (OD = 0)
TRANSMISSION_LENS = 0.959  # Correction factor for the lens between the energymeter and sample (probably at 337 nm).

# 2. --- FILE SYSTEM --- (please referenciate "file_location_memo.py" for folder structure)
# Base Directory (Paste the path to your data folder here)
# (it shoud look like BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251127_Measurement_2")
BASE_DIR = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data\20251127_Measurement_2"

# Derived Directories
# (location of subfolders)
DATA_DIR = os.path.join(BASE_DIR, "Raw_Data")     # this contains raw spectra aquired by aquisition codes
RESULTS_DIR = os.path.join(BASE_DIR, "Results")   # this is where analysis code save results

# Keywords
# (the analysis codes look for the files with these keywords)
ENERGY_FILENAME = "energies.csv"
# (NOTE: the codes only look for calibration and absorption BASE_DIR, so make sure to put these files in the base directory)
CALIBRATION_KEYWORD = "calibration" # The angle-dependent transmission curve
ABSORPTION_KEYWORD = "absorption"


# 3. EXPERIMENT VARIABLES & CONSTANTS
ANGLE_REF = 245         # The angle where you measured the reference energy (usually the max transmission angle).
RAW_ENERGY_READ_NJ = 24 # Raw energy value you read at ANGLE_REF in Gentec meter (in nJ).
TODAYS_OD = OD3         # Which filter was on the Power Meter when you read the value above?
                        # Choose from the constants defined in Section 1 (e.g., OD1, OD3, NO_OD).
TARGET_WAVELENGTH = 337 # The wavelelength to read on the absorption spectrum. 337 nm for N2 laser.
LASER_PULSE_WIDTH_S = 3e-9 # Laser pulse width in seconds (e.g. 3 ns) 
# NOTE: this is the pulse width of the laser (constant), not the pulse of the pulse generator.

# 4. GEOMETRY
SPOT_SHAPE = "rectangle"    # Beam shape of excitation laser (normally "rectangle" for ASE measurements)
# Shape options: "rectangle" (for slit/ASE), "circle", or "ellipse"
SPOT_DIM_1_UM = 4000.0      
SPOT_DIM_2_UM = 500.0
# DEFINITIONS:
# - Rectangle: DIM_1 = Length (Height),    DIM_2 = Width
# - Circle:    DIM_1 = Diameter,           DIM_2 = (Ignored)
# - Ellipse:   DIM_1 = Major Axis (Long),  DIM_2 = Minor Axis (Short)