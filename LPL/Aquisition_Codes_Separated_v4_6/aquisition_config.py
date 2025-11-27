"""
Configuration File for the Angle-Resolved Spectroscopy Experiment

This file is organized into three main sections (SECTION 1,2,3)
"""

# ===================================================================
# --- SECTION 1: STATIC DRIVER CONSTANTS ---
# ===================================================================
# WARNING: DO NOT EDIT THIS SECTION.
# Manufacturer-defined "magic numbers".
# They map human-readable names (e.g., ACQ_SPECTRUM) to the integer codes the machine understands (e.g., 0).
# This section is on top because some parameters below uses these constants.

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
ACQ_NO_DARK = 1000000   # Do not subtract dark frame automatically
ACQ_DARK = 2000000      # LabSpec subtracts dark frame internally (Don't use this. I doesn't work.)

# --- Post-Processing 'Treat' Constants ---
# IDs for specific data treatments in the 'Treat' command
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
# Parameters you can change / have to check for each measuement

# --- Save Diectory ---
# NOTE: Use 'r' before the string to handle backslashes in Windows paths correctly.
BASE_SAVE_DIRECTORY = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data"

# --- Scan & Sequence Parameters ---
START_ANGLE = 85.0  # Wheel start position (degrees)
END_ANGLE = 280.0   # Wheel end position (degrees)
NUM_POINTS = 50     # How many steps to take between Start and End
ACCUMULATIONS = 1

# --- Smart Acquisition Parameters ---
# A list of integration times (in seconds) to try.
# The codes shift to the next value when th signal hits the SATURATION_WARNING_THRESHOLD defined below.
# This presets can contain multiple values.
# Always list from LONGEST (most sensitive) to SHORTEST (least sensitive).
INTEGRATION_TIME_PRESETS_S = [4.0, 0.1]

# The "soft" saturation threshold. If max counts are ABOVE this, we will
# proactively step down the integration time for the *next* angle.
# Logic: If the signal counts exceed this number (but don't hit the hard limit),
#        the script will proactively use the next shorter time for the NEXT angle.
#        This prevents saturating the next point if the signal is rising.
SATURATION_WARNING_THRESHOLD = 50000 


# --- Spectrometer Setup ---
TARGET_GRATING_INDEX = 1    # grating number. You can check which number corresponds to which grating by running the main code.
TARGET_WAVELENGTH_NM = 450.0    # center wavelength for aquisition


# --- Pulser Setup ---
PULSE_WIDTH_S = 5e-6    # Pulse width in seconds
PULSE_PERIOD_S = 0.1    # Period between pulses (10Hz = 0.1s)

# Acquisition Settings (Using constants from SECTION 1)
CHOSEN_SPIKE_FILTER_MODE = ACQ_SINGLE_SPIKE_REMOVING   # Recommended default
CHOSEN_DARK_SUB_MODE = ACQ_NO_DARK                     # We handle dark subtraction in Python, so set this to NO.
DENOISER_FACTOR = 50.0                                 # Strength of the 'Treat' denoiser (0 to 100)


# ===================================================================
# --- SECTION 3: HARDWARE & INSTALLATION SETTINGS ---
# ===================================================================
# (Parameters you don't normally change)

# --- Rotator (Elliptec) ---
MOTOR_COM_PORT = 'COM6'     # Windows Device Manager COM port
MOTOR_ADDRESS = '0'         # Hardware address (usually '0' for single motor)
MOTOR_TIMEOUT_S = 180       # Max time to wait for a move
PAUSE_AFTER_MOVE_S = 0.5    # Stabilization time after movement stops


# --- Pulser (Sapphire) ---
PULSER_COM_PORT = 'COM5'
PULSE_VOLTAGE_V = 5.0       # Output voltage Amplitude


# --- Spectrometer (Horiba) ---
# COM Object Program IDs (Registry Keys - Fixed by Manufacturer)
CTRL_PROG_ID = "NFACTIVEX.NFActiveXCtrl.1"
MONO_PROG_ID = "jymono.monochromator"
CCD_PROG_ID = "JYCCD.JYMCD"

# Unique IDs
MONO_UNIQUE_ID = "Mono1" 
CCD_UNIQUE_ID = "CCD1" 

# Saturation Threshold (hard limit)
# The CCD is probably a 16-bit ADC (Max value 65535).
SATURATION_THRESHOLD = 65530 

# Timeouts & Waits
INIT_WAIT_TIME_S = 5.0        # Hard wait for electronics to boot
COOLING_WAIT_TIMEOUT_S = 600  # Max time to wait for cooling (10 mins)
COOLING_CHECK_INTERVAL_S = 5  # How often to poll temperature during cooling

# Temperature Thresholds
COOLING_THRESHOLD_K = 223.15      # If warmer than this, force cooling sequence.
TARGET_DETECTOR_TEMP_K = 203.15   # Target setpoint (-70 C).