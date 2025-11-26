"""
Configuration File for the Angle-Resolved Spectroscopy Experiment

This file is organized into three main sections:

SECTION 1: STATIC DRIVER CONSTANTS
  - "Magic numbers" defined by the manufacturer's drivers (e.g., COM objects, flags).
  - DO NOT EDIT these values unless you are certain the driver API has changed.

SECTION 2: EXPERIMENT PARAMETERS
  - Settings you change for *each new experiment* (e.g., angles, integration time).

SECTION 3: HARDWARE & INSTALLATION SETTINGS
  - Settings specific to your *physical setup* (e.g., COM ports, fixed temps, software IDs).
  - You set these once and rarely change them.
"""

# ===================================================================
# --- SECTION 1: STATIC DRIVER CONSTANTS ---
# ===================================================================
# (Manufacturer-defined "magic numbers". DO NOT EDIT.)

# --- LabSpec ActiveX Constants ---
ACQ_SPECTRUM = 0
ACQ_IMAGE = 1
ACQ_LABSPEC_PARAM = 2
ACQ_SPECTRAL_IMAGE = 3
ACQ_GET_TEMPERATURE = 4
ACQ_SPECTRUM_RTD = 5
ACQ_AUTO_SHOW = 10
MOTOR_VALUE = 0

# --- Spike Filter Constants ---
ACQ_LABSPEC_SPIKE_REMOVING = 0
ACQ_NO_SPIKE_REMOVING = 100
ACQ_SINGLE_SPIKE_REMOVING = 200
ACQ_DOUBLE_SPIKE_REMOVING = 300
ACQ_DOUBLE_AUTOADD_SPIKE_REMOVING = 400

# --- Dark Subtraction Constants ---
ACQ_NO_DARK = 1000000
ACQ_DARK = 2000000

# --- Post-Processing 'Treat' Constants ---
TREAT_FILTER_START = 0
TREAT_FILTER_DENOISER = 5

# --- JY Enumeration Constants ---
JY_UNIT_TYPE_WAVELENGTH = 1
JY_UNIT_NANOMETERS = 3
JY_UNIT_TYPE_TEMPERATURE = 5
JY_UNIT_CELSIUS = 25
JY_UNIT_KELVIN = 27
MIRROR_ENTRANCE = 0
MIRROR_EXIT = 1
MIRROR_FRONT = 2
MIRROR_SIDE = 3


# ===================================================================
# --- SECTION 2: EXPERIMENT PARAMETERS ---
# ===================================================================
# (Parameters you will change most often for a new experiment)

# --- Scan & Sequence Parameters ---
START_ANGLE = 85.0
END_ANGLE = 280.0
NUM_POINTS = 50
ACCUMULATIONS = 1

# --- Smart Acquisition Parameters ---
# A list of integration times (in seconds) to try, from longest to shortest.
INTEGRATION_TIME_PRESETS_S = [1.0, 0.8, 0.5, 0.2, 0.1]

# The "soft" threshold. If max counts are ABOVE this, we will
# proactively step down the integration time for the *next* angle.
INTEGRATION_WARNING_THRESHOLD = 50000 

# --- Acquisition Settings (Using constants from SECTION 1) ---
CHOSEN_SPIKE_FILTER_MODE = ACQ_SINGLE_SPIKE_REMOVING
CHOSEN_DARK_SUB_MODE = ACQ_NO_DARK 
DENOISER_FACTOR = 50.0 

# --- Spectrometer Setup ---
TARGET_GRATING_INDEX = 1 
TARGET_WAVELENGTH_NM = 550.0 

# --- Pulser Setup ---
PULSE_WIDTH_S = 5e-6 

# --- General Experiment Setup ---
BASE_SAVE_DIRECTORY = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data"
SATURATION_THRESHOLD = 65530 


# ===================================================================
# --- SECTION 3: HARDWARE & INSTALLATION SETTINGS ---
# ===================================================================
# (Parameters specific to your physical hardware setup)

# --- Rotator (Elliptec) ---
MOTOR_COM_PORT = 'COM6' 
MOTOR_ADDRESS = '0' 
MOTOR_TIMEOUT_S = 180 
PAUSE_AFTER_MOVE_S = 0.5 

# --- Pulser (Sapphire) ---
PULSER_COM_PORT = 'COM5'
PULSE_PERIOD_S = 0.3 
PULSE_VOLTAGE_V = 5.0

# --- Spectrometer (Horiba) ---
# COM Object Program IDs (fixed)
CTRL_PROG_ID = "NFACTIVEX.NFActiveXCtrl.1"
MONO_PROG_ID = "jymono.monochromator"
CCD_PROG_ID = "JYCCD.JYMCD"

# Unique IDs (configurable per LabSpec installation)
MONO_UNIQUE_ID = "Mono1" 
CCD_UNIQUE_ID = "CCD1" 

# Timeouts & Waits
INIT_WAIT_TIME_S = 5.0 
COOLING_WAIT_TIMEOUT_S = 600
COOLING_CHECK_INTERVAL_S = 5
COOLING_THRESHOLD_K = 223.15 
TARGET_DETECTOR_TEMP_K = 203.15