# User Instruction Manual: ASE Automation System (LPL version)

## Introduction
This manual provides a comprehensive guide to using the ASE Automation System. The system consists of two main parts:
1.  **Acquisition Codes (v4_6)**: Controls the hardware (Spectrometer, Motor, Pulser) to acquire data.
2.  **Analysis Codes (v2)**: Processes the raw data to calculate energy, fluence, and ASE thresholds.

> [!NOTE]
> **Reference Documentation**: All technical documentation and manuals referenced for the development of these codes can be found in the **Shared** folder.

> [!TIP]
> **Source Code & Git**: The original codes are available at [https://github.com/LPL-OPERA-Collaboration/ASE_Automation](https://github.com/LPL-OPERA-Collaboration/ASE_Automation).
> You will need to **configure Git** to download and use these codes. Please refer to external resources (e.g., official documentation or AI assistants like Gemini) to learn how to clone and manage the repository.

## Environment Setup
> [!NOTE]
> **Virtual Environment Location**: When creating a Python virtual environment (venv), create it **outside** the Git repository folder (i.e., in a parent directory).
> *   **Reason**: To prevent thousands of environment files from being tracked by Git and contaminating the repository history.
> *   **Example**: If your repo is in `.../GitHub/LPL-OPERA-Collaboration/`, create your venv in `.../GitHub/` or a separate `envs/` folder.

### Required Libraries
You will need to install the following Python libraries in your virtual environment:
```bash
pip install numpy pandas matplotlib scipy pyserial pywin32 elliptec qcsapphire
```
## Directory Structure
The system uses a specific folder structure for data organization.

### Data & Results Organization
```
Kaya/
│
├── gentec data/                           <-- OUTPUT of Callibration (Step0)
│   └── 20251126_..._calibration.csv       (Source File)
│       [ACTION]: You must COPY this file manually to the daily folder below.
│
└── data/
    └── 20251126_Measurement_56/           <-- "BASE_DIR" in analysis_config.py
        │
        ├── 20251126_measurement.log       (Log file from Acquisition)
        ├── calibration_2025... .csv       (PASTED by You)
        ├── absorption_sample.txt          (PASTED by You)
        │
        ├── Raw_Data/                      <-- OUTPUT of Spectra Acquisition
        │   ├── ...angle_190.00... .txt    (Spectrum with Header info)
        │   └── ...angle_190.00... .tsf    (LabSpec Backup)
        │
        ├── Used_Acquisition_Codes_.../    <-- SNAPSHOT 1 (Auto-generated)
        │   ├── main_measurement.py
        │   └── experiment_config.py
        │
        ├── Results/                       <-- OUTPUT of Step 1 & Step 2
        │   ├── energies.csv               (Fluence values)
        │   ├── final_results_... .csv     (The Final Data Table)
        │   ├── ASE_Curve_... .png         (The Final Plot)
        │   └── COMBINED_smooth... .txt    (Matrix Data)
        │
        └── Used_Analysis_Codes_.../       <-- SNAPSHOT 2 (Auto-generated)
            ├── analysis_config.py
            ├── step1_energy_calc.py
            └── step2_spectrum_analysis.py
```

### Codebase Structure
```
LPL/
├── Aquisition_Codes_v4_6/          # [PART 1] Data Acquisition
│   ├── aquisition_config.py        # <--- MAIN CONFIGURATION FILE
│   ├── main_measurement.py         # <--- MAIN RUN SCRIPT
│   ├── horiba_spectrometer_controller.py
│   ├── sapphire_pulser_controller.py
│   └── elliptec_motor_controller.py
│
├── Analysis_Codes_v2/              # [PART 2] Data Analysis
│   ├── analysis_config.py          # <--- MAIN CONFIGURATION FILE
│   ├── step1_energy_calc.py        # Step 1: Energy & Fluence
│   ├── step2_signal_processing.py  # Step 2: Smoothing & Filtering
│   └── step3_spectrum_analysis.py  # Step 3: Physics & Thresholds
│
└── file_location_memo.py           # Helper file for path references
```

---

## Part 1: Data Acquisition (v4_6)

### Code Structure & Roles
The acquisition system is designed with a modular architecture:
-   **`main_measurement.py` (The Orchestrator)**: This is the main script you run. It manages the entire experiment flow (initialization, scanning, saving) and coordinates the hardware controllers. It does *not* contain low-level driver code.
-   **`aquisition_config.py` (The Configuration)**: Contains all settings (hardware constants, scan parameters, file paths). **This is the only file you should normally edit.**
-   **`*_controller.py` (The Drivers)**: These files (`horiba_...`, `elliptec_...`, `sapphire_...`) handle the specific communication protocols for each device. They are used by the Main script.

### 1. Hardware Setup
Ensure all devices are connected and powered on:
-   **Horiba Spectrometer**: Switch on the **Monochromator**, **Shutter**, and **Camera**.
-   **Pulse Generator**: USB connected.
-   **Elliptec Motor**: USB connected.
-   **Excitation Laser**: Turn on the laser source.

> [!NOTE]
> **Pre-run Check**: This code expects that the sample is already aligned.
> Ensure that the output signal **does not saturate** at the lowest filtering region of the filter wheel.
> Please perform these checks manually (the "classic way") before running this automated code.


### 2. Configuration
Before running an aquisition, open `Aquisition_Codes_v4_6/aquisition_config.py` and check and change the following:

-   **Save Directory**:
    ```python
    BASE_SAVE_DIRECTORY = r"C:\Path\To\Your\Data\Folder"
    # Example: BASE_SAVE_DIRECTORY = r"C:\Users\Equipe_OPAL\Desktop\Kaya\data"
    ```
    *The script will automatically create a new folder inside this directory for each run (e.g., `20251128_Measurement_1`), containing:*
    *   `Raw_Data/`: All spectrum files (`.txt`, `.tsf`).
    *   `Used_Acquisition_Codes_.../`: A snapshot of the code used.
    *   `...measurement.log`: The experiment log file.

-   **Scan Parameters**:
    ```python
    START_ANGLE = 85.0  # Wheel start position (degrees)
    END_ANGLE = 280.0   # Wheel end position (degrees)
    NUM_POINTS = 50     # How many steps to take between Start and End
    ACCUMULATIONS = 1
    ```

-   **Integration Times**:
    ```python
    # A list of integration times (in seconds) to try.
    # The codes shift to the next value when th signal hits the SATURATION_WARNING_THRESHOLD defined below.
    # This presets can contain multiple values.
    # Always list from LONGEST (most sensitive) to SHORTEST (least sensitive).
    INTEGRATION_TIME_PRESETS_S = [4.0, 0.1]
    ```

-   **Pulser Settings**:
    ```python
    PULSER_PULSE_WIDTH_S = 5e-6    # Pulse width of the generator (in seconds)
    # NOTE: This is NOT the laser pulse width (which is ~nanoseconds).
    ```

> [!NOTE]
> For other acquisition parameters, please check the configuration file itself (`aquisition_config.py`).

> [!WARNING]
> Changing parameters and constants other than **Section 2** in `aquisition_config.py` is **not recommended**. Edit them only when absolutely necessary.

> [!IMPORTANT]
> **Save Changes**: Press **Ctrl+S** to save `aquisition_config.py` (and any other modified files) before proceeding. The script reads the file on disk, not what is in your editor buffer.


### 3. Running the Measurement
1.  **Close Hardware Software**: Ensure the following control software is **CLOSED**:
    -   **LabSpec 6** (Spectrometer)
    -   **ELLO** (Elliptec Motor)
    -   **QC_9200.exe** (Pulse Generator)
    *The script cannot take control if these programs are holding the connection.*
2.  Open `Aquisition_Codes_v4_6/main_measurement.py` in **VS Code**.
    *Note: VS Code (or its derivatives) is recommended as the codes were written in this environment.*
3.  Run the script (F5 or Play Button).
    *Reminder: Ensure you have saved your changes (Ctrl+S) in `aquisition_config.py`.*
4.  The script will automatically perform the following sequence:
    -   **Initialization**:
        -   Creates a unique measurement folder (e.g., `..._Measurement_1`).
        -   Creates the `Raw_Data/` subfolder for spectra.
        -   Creates the `Used_Acquisition_Codes_.../` subfolder and copies the current code into it for reproducibility.
    -   **Connection**: Connects to the Spectrometer, Motor, and Pulse Generator.
    -   **Initialization Checks**:
        -   **CCD Temperature**: Checks if the detector is cooled (target: -70°C). If not, it waits for it to cool down.
        -   **Grating & Mirrors**: Reports the current grating details and moves the entrance mirror to the correct position (Front/Side).
        -   **Wavelength**: Moves the monochromator to the target wavelength defined in the config.
    -   **Real-Time Plot**: Opens a window showing Signal, Background, and Subtracted spectra.
    -   **Scan Loop (Repeats for each angle)**:
        1.  **Move Motor**: Rotates the filter wheel to the target angle.
        2.  **Auto-Exposure & Signal Acquisition**:
            -   Starts with the *longest* integration time (or the last successful one).
            -   Turns **Pulse Generator ON** (Laser ON).
            -   Acquires the **Signal Spectrum** via `horiba_spectrometer_controller.py`:
                -   Calls `acquire_frame()` which triggers the LabSpec ActiveX `Acq()` method.
                -   Waits for the acquisition to complete and returns a unique Spectrum ID.
            -   **Saturation Check**: If the signal is saturated (max counts > limit), it discards the data and retries with the next *shorter* integration time.
        3.  **Background Acquisition**:
            -   Checks if a background for the *current integration time* is cached.
            -   **If Not Cached**: Turns **Pulse Generator OFF**, acquires a **Background Spectrum**, and caches it.
            -   **If Cached**: Reuses the existing background.
            *Note: This means it only takes a new background when the integration time changes.*
        4.  **Data Processing**:
            -   Applies **Denoiser** to the Signal (if enabled).
            -   Calculates **Net Signal** = (Signal - Background).
        5.  **Save Data**:
            -   Saves **Raw Signal** (`.tsf` - LabSpec format).
            -   Saves **Processed Net Signal** (`.txt` - ASCII format).
        6.  **Plot Update**: Updates the real-time display.
    -   **Cleanup**: Homes the motor and closes connections when finished.

### 4. Output Folder Structure
The acquisition script creates a folder for each run:
```
20251128_Measurement_1/
├── Raw_Data/                       # Contains all .txt and .tsf spectrum files
├── Used_Acquisition_Codes_.../     # Snapshot of the code used for this run
└── 20251128_measurement.log        # Log file of the experiment
```

---

## Part 2: Data Analysis (v2)

### Code Structure & Roles
The analysis codes are designed to be run **sequentially**, as the output of one step becomes the input for the next:
-   **`analysis_config.py` (The Configuration)**: Central file for (almost)all analysis settings (paths, experiment constants, plotting parameters). **Edit this first.**
-   **`step1_energy_calc.py`**: Calculates per-pulse energy and fluence from raw spectra and calibration data.
-   **`step2_signal_processing.py`**: Performs noise reduction (smoothing) and prepares the data matrix. **This step is iterative.**
-   **`step3_spectrum_analysis.py`**: Performs the final physics calculations (FWHM, Threshold) and generates the results.

### 1. Prerequisites
**Required Files**
Before analyzing, place these files in the measurement directory:
-   **Calibration File**: A `.csv` file with the angle-dependent transmission curve (keyword: `calibration`).
-   **Absorption File**: A `.txt` file with the sample's absorption spectrum (keyword: `absorption`).

> [!NOTE]
> These files should be placed in the root of your measurement folder (e.g., inside `20251128_Measurement_1/`), not inside subfolders such as `Raw_Data/`.
> The program will search for these files by their keywords (e.g., `calibration.csv` and `absorption.txt`), so make sure they include the keywords in their names.

**One-time Manual Energy Measurements**
You must manually measure the reference energy (the "classic way") to populate the configuration variables (`ANGLE_REF`, `RAW_ENERGY_READ_NJ`, `TODAYS_OD`).
(Probably, the ANGLE_REF should be within the range of your acquisition (the range of your final plot))

### 2. Configuration
Open `Analysis_Codes_v2/analysis_config.py` and update:

-   **Base Directory**: Point to your measurement folder.(the folder generated by the acquisition script)
    ```python
    BASE_DIR = r"C:\Path\To\Your\Data\20251128_Measurement_1"
    ```
-   **Experiment Variables**:
    ```python
    ANGLE_REF = 245         
    # The angle where you measured the reference energy (usually the max transmission angle).
    # (probably, this should be within the range of your acquisition)
    RAW_ENERGY_READ_NJ = 24 
    # Raw energy value you read at ANGLE_REF in Gentec meter (in nJ).
    TODAYS_OD = OD3         
    # Which filter was on the Power Meter when you read the value above?
    # Choose from the constants defined in Section 1 (e.g., OD1, OD3, NO_OD).

    SPOT_SHAPE = "rectangle"    # Beam shape of excitation laser (normally "rectangle" for ASE measurements)
    # Shape options: "rectangle" (for slit/ASE), "circle", or "ellipse"
    SPOT_DIM_1_UM = 4000.0      
    SPOT_DIM_2_UM = 500.0
    # DEFINITIONS:
    # - Rectangle: DIM_1 = Length (Height),    DIM_2 = Width
    # - Circle:    DIM_1 = Diameter,           DIM_2 = (Ignored)
    # - Ellipse:   DIM_1 = Major Axis (Long),  DIM_2 = Minor Axis (Short)
    ```

### 3. Execution Steps
Run the scripts in order:

#### **Step 1: Energy Calculation**
-   **Script**: `step1_energy_calc.py`
-   **Inputs**:
    -   Raw Spectra (in `Raw_Data/`)
    -   Calibration File (`.csv`) & Absorption File (`.txt`)
    -   Configuration (`analysis_config.py`)
-   **Action**:
    -   Reads **Integration Time** and **Angle** from the header of each raw spectrum file.
    -   Reads **Laser Pulse Width** from `analysis_config.py`.
    -   [NOTE] This pulse width is the pulse width of the laser, not the pulse generator.
    -   Uses the **Calibration File** to determine the transmission for each angle.
    -   Calculates the **Pulse Energy** on the sample using the Reference Energy and Transmission.
    -   Calculates **Fluence** (Energy / Spot Area) and **Power Density**.
-   **Output**: `Results/energies.csv` (Manifest file).

#### **Step 2: Signal Processing**
-   **Script**: `step2_signal_processing.py`
-   **Inputs**:
    -   `Results/energies.csv` (from Step 1)
    -   Raw Spectra (for initial data loading)
-   **Configuration & Iterative Process**:
    -   Open the script and set `START_SMOOTHING_INDEX` and `SMOOTH_WINDOW` **before running**.
    -   You are expected to run this script **multiple times**, adjusting these parameters each time.
    -   This allows applying different smoothing levels (e.g., stronger smoothing for initial spectra, gradually lower for later ones).
-   **Action**:
    -   Loads the raw spectral data.
    -   Applies a **Savitzky-Golay filter** to smooth out noise.
    -   Combines all processed spectra into a single matrix for the next step.
-   **Interactive**: Opens a window to view raw vs. smoothed data.
-   **Output**: `Results/COMBINED_smoothed_spectra.csv`.

#### **Step 3: Physics Analysis**
-   **Script**: `step3_spectrum_analysis.py`
-   **Inputs**:
    -   `Results/COMBINED_smoothed_spectra.csv` (from Step 2)
    -   `Results/energies.csv` (from Step 1)
-   **Action**:
    -   Calculates **FWHM** (Full Width at Half Maximum) for each spectrum.
    -   Calculates **Integrated Intensity** (Area under the curve) within the specified ROI.
    -   Plots the **"S-Curve"** (Fluence vs. FWHM/Intensity).
    -   **ASE Threshold Determination**:
        -   Interpolates the FWHM vs. Fluence curve using a **cubic spline**.
        -   Calculates the **gradient (derivative)** of the interpolated curve.
        -   Identifies the threshold as the fluence value where the **gradient is minimum** (steepest drop in FWHM).
-   **Output**:
    -   `Results/FINAL_RESULTS.csv`
    -   `Results/Plot_SCurve.png` (The ASE Threshold Curve)
    -   `Results/Plot_Spectra_Normalized.png`
    -   `Results/Plot_Spectra_Unnormalized.png`

### 4. Output Directory Structure
After running all steps, your measurement folder will look like this:
```
20251128_Measurement_1/
├── ... (Acquisition Files)
├── Results/                       <-- Created by Analysis Codes
│   ├── energies.csv               (Step 1 Output)
│   ├── COMBINED_smoothed_spectra.csv (Step 2 Output)
│   ├── FINAL_RESULTS.csv          (Step 3 Output)
│   ├── Plot_SCurve.png            (Step 3 Plot)
│   ├── Plot_Spectra_Normalized.png (Step 3 Plot)
│   └── Plot_Spectra_Unnormalized.png (Step 3 Plot)
└── Used_Analysis_Codes_.../       (Snapshot of analysis codes, if generated)
```
