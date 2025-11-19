import win32com.client
import pythoncom
import time
import numpy as np
import logging
import sys
from experiment_config import (
    # Hardware/Installation Settings (Section 3)
    CTRL_PROG_ID, MONO_PROG_ID, CCD_PROG_ID, MONO_UNIQUE_ID, CCD_UNIQUE_ID,
    COOLING_THRESHOLD_K, TARGET_DETECTOR_TEMP_K, COOLING_WAIT_TIMEOUT_S,
    COOLING_CHECK_INTERVAL_S, TARGET_GRATING_INDEX, TARGET_WAVELENGTH_NM, 
    INIT_WAIT_TIME_S,
    # Static Driver Constants (Section 1)
    ACQ_SPECTRUM, ACQ_AUTO_SHOW, MOTOR_VALUE, JY_UNIT_TYPE_WAVELENGTH,
    JY_UNIT_NANOMETERS, MIRROR_ENTRANCE, MIRROR_FRONT, TREAT_FILTER_DENOISER,
    TREAT_FILTER_START, ACQ_NO_DARK, ACQ_SINGLE_SPIKE_REMOVING
)

class HoribaSpectrometerController:
    """
    Controller class to control the Horiba LabSpec 6 Spectrometer via its 
    ActiveX, JYMono, and JYCCD COM objects.
    
    All spectrometer-specific logic and COM object management are 
    encapsulated here.
    """
    def __init__(self, logger):
        # --- Hardware Objects ---
        self.labspec_activex = None
        self.mono_controller = None
        self.ccd_controller = None
        
        # --- State Flags ---
        self.activex_connected = False
        self.mono_init_ok = False
        self.ccd_init_ok = False
        
        # --- Logger ---
        self.logger = logger
        
    # ===================================================================
    # --- CONNECTION METHODS ---
    # ===================================================================

    def _wait_for_mono_ready(self, timeout=180):
        """Waits for the monochromator to be not busy AND ready."""
        self.logger.info(f"      Waiting for Monochromator (timeout {timeout}s)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            is_busy_ret = self.mono_controller.IsBusy()
            is_ready_ret = self.mono_controller.IsReady()

            # Robust handling of COM object return values (tuple/list or scalar)
            is_busy = bool(is_busy_ret[-1]) if isinstance(is_busy_ret, (tuple, list)) else bool(is_busy_ret)
            is_ready = bool(is_ready_ret[-1]) if isinstance(is_ready_ret, (tuple, list)) else bool(is_ready_ret)

            if not is_busy and is_ready:
                self.logger.info("      ...Monochromator is Ready.")
                return True
            elif is_busy:
                self.logger.debug("      ...mono busy...")
            elif not is_ready:
                self.logger.debug("      ...mono not ready...")

            time.sleep(0.2)
        raise Exception(f"Monochromator wait timed out after {timeout}s.")

    def _connect_labspec(self):
        self.logger.info(f"\n--- Connecting to LabSpec ActiveX ({CTRL_PROG_ID}) ---")
        self.logger.info("(Remember: LabSpec GUI must be CLOSED)")
        self.labspec_activex = win32com.client.Dispatch(CTRL_PROG_ID)
        _ = self.labspec_activex.GetMotorPosition("Spectro", MOTOR_VALUE) # Dummy call
        self.activex_connected = True
        self.logger.info("LabSpec ActiveX initialized.")

    def _connect_ccd(self):
        self.logger.info(f"\n--- Connecting & Initializing CCD Controller ({CCD_PROG_ID}) ---")
        try:
            self.ccd_controller = win32com.client.Dispatch(CCD_PROG_ID)
            self.logger.info(f"   Setting UniqueId = '{CCD_UNIQUE_ID}'...")
            self.ccd_controller.UniqueId = CCD_UNIQUE_ID
            self.logger.info("   Calling Load()...")
            self.ccd_controller.Load()
            self.logger.info("   Calling OpenCommunications()...")
            self.ccd_controller.OpenCommunications()
            self.logger.info("   Calling Initialize()...")
            self.ccd_controller.Initialize(False, False)

            self.logger.info(f"   Waiting a fixed {INIT_WAIT_TIME_S} seconds for initialization to complete...")
            time.sleep(INIT_WAIT_TIME_S)
            self.logger.info("   Fixed wait finished. Now confirming by reading temperature...")

            self._manage_detector_cooling()

            self.ccd_init_ok = True
            self.logger.info("      CCD Controller initialization confirmed.")

        except pythoncom.com_error as e:
            self.logger.exception(f"\n   FATAL COM Error during CCD Controller setup: {e}")
            self.ccd_controller = None
            self.ccd_init_ok = False
            raise 
        except Exception as e:
            self.logger.exception(f"\n   Error connecting/initializing the CCD Controller object: {e}")
            self.ccd_controller = None
            self.ccd_init_ok = False
            raise

    def _manage_detector_cooling(self):
        """Internal helper to check and set detector temperature."""
        self.logger.info("\n   --- Checking/Setting Detector Temperature (via JYCCD) ---")
        try:
            current_temp_k = self.ccd_controller.CurrentTemperature
            current_temp_c = current_temp_k - 273.15
            self.logger.info(f"      Current Temperature (read): {current_temp_k:.2f} K ({current_temp_c:.2f} C)")

            if current_temp_k > COOLING_THRESHOLD_K:
                self.logger.info(f"      Temperature ({current_temp_c:.2f} C) is above threshold (-50 C).")
                self.logger.info(f"      Setting Temperature Setpoint to {TARGET_DETECTOR_TEMP_K:.2f} K (approx -70 C)...")
                self.ccd_controller.TemperatureSetPoint = TARGET_DETECTOR_TEMP_K
                self.logger.info("      Waiting for detector to cool...")

                cool_start_time = time.time()
                while current_temp_k > COOLING_THRESHOLD_K:
                    if time.time() - cool_start_time > COOLING_WAIT_TIMEOUT_S:
                        self.logger.warning(f"      *** WARNING: Cooling timeout after {COOLING_WAIT_TIMEOUT_S}s. ***")
                        self.logger.warning("      *** Proceeding with scan anyway. ***")
                        break
                    
                    self.logger.info(f"      ...current temp is {current_temp_k:.2f} K ({current_temp_c:.2f} C)...")
                    time.sleep(COOLING_CHECK_INTERVAL_S)
                    current_temp_k = self.ccd_controller.CurrentTemperature
                    current_temp_c = current_temp_k - 273.15
                
                if current_temp_k <= COOLING_THRESHOLD_K:
                    self.logger.info(f"      Detector is now cooled to {current_temp_c:.2f} C. Proceeding.")
            else:
                self.logger.info(f"      Temperature ({current_temp_c:.2f} C) is already below -50 C.")
                self.logger.info(f"      Setting setpoint to {TARGET_DETECTOR_TEMP_K:.2f} K to maintain cooling.")
                self.ccd_controller.TemperatureSetPoint = TARGET_DETECTOR_TEMP_K
                self.logger.info("      Proceeding with scan.")

        except pythoncom.com_error as e_temp_com:
            self.logger.exception(f"      *** COM ERROR during temperature control: {e_temp_com} ***")
            raise Exception("Failed to confirm CCD initialization via temperature read.")
        except Exception as e_temp:
            self.logger.warning(f"      WARNING: Error during temperature control: {e_temp}")
            raise Exception("Failed to confirm CCD initialization via temperature read.")


    def _connect_mono(self):
        self.logger.info(f"\n--- Connecting & Initializing Monochromator ({MONO_PROG_ID}) ---")
        try:
            self.mono_controller = win32com.client.Dispatch(MONO_PROG_ID)
            self.logger.info(f"   Setting UniqueId = '{MONO_UNIQUE_ID}'...")
            self.mono_controller.UniqueId = MONO_UNIQUE_ID
            self.logger.info("   Calling Load()...")
            self.mono_controller.Load()
            self.logger.info("   Calling OpenCommunications()...")
            self.mono_controller.OpenCommunications()
            self.logger.info("   Calling Initialize()...")
            self.mono_controller.Initialize(False, False)

            self.logger.info(f"   Waiting for Monochromator to initialize...")
            self._wait_for_mono_ready() 
            self.logger.info("   Monochromator initialization confirmed.")
            self.mono_init_ok = True

        except pythoncom.com_error as e:
            self.logger.exception(f"\n   FATAL COM Error during Monochromator setup: {e}")
            raise Exception("Monochromator initialization failed.")
        except Exception as e:
            self.logger.exception(f"\n   Error connecting/initializing the Monochromator object: {e}")
            raise Exception("Monochromator initialization failed.")

    def connect_all(self):
        """Public method to connect all COM components."""
        self._connect_labspec()
        self._connect_ccd()
        self._connect_mono()
        
        # Check all flags before declaring success
        if not (self.activex_connected and self.ccd_init_ok and self.mono_init_ok):
            raise Exception("One or more LabSpec components failed to connect/initialize.")
        self.logger.info("\n*** All Spectrometer components connected successfully. ***")

    # ===================================================================
    # --- SETUP STATE METHODS ---
    # ===================================================================

    def setup_spectrometer_state(self):
        """Sets the initial state of the monochromator (grating, mirror, etc.)."""
        if not self.mono_init_ok:
            raise Exception("Cannot set spectrometer state, Monochromator not initialized.")

        self.logger.info(f"\n--- Setting Spectrometer State ---")

        # --- 5.1: Set Wavelength Units to Nanometers ---
        self.logger.info(f"   Setting wavelength units to Nanometers...")
        self.mono_controller.SetDefaultUnits(JY_UNIT_TYPE_WAVELENGTH, JY_UNIT_NANOMETERS)
        self.logger.info(f"   Wavelength units set.")

        # --- 5.2: Get and Print Grating Report (Report only, no function change) ---
        self._report_grating_details()

        # --- 5.3: Check and Set Grating ---
        self._move_grating(TARGET_GRATING_INDEX)

        # --- 5.4: Check and Set Entrance Mirror ---
        self._move_entrance_mirror(MIRROR_FRONT)

        # --- 5.5: Set Wavelength ---
        self.logger.info(f"   Moving wavelength to {TARGET_WAVELENGTH_NM} nm...")
        self.mono_controller.MovetoWavelength(TARGET_WAVELENGTH_NM)
        self._wait_for_mono_ready()
        current_wl_ret = self.mono_controller.GetCurrentWavelength()
        current_wl = float(current_wl_ret[-1]) if isinstance(current_wl_ret, (tuple, list)) else float(current_wl_ret)
        self.logger.info(f"   Current wavelength confirmed: {current_wl:.2f} nm")

        self.logger.info("Spectrometer state is set.")
    
    def _report_grating_details(self):
        """Internal helper for 5.2 Grating Report."""
        try:
            self.logger.info("\n   --- Monochromator Grating Report ---")
            grating_details = self.mono_controller.GetCurrentGratingWithDetails()
            
            if len(grating_details) >= 4 and len(grating_details[1]) > 0:
                current_density = float(grating_details[0])
                densities = grating_details[1]
                blazes = grating_details[2]
                descriptions = grating_details[3]
                
                self.logger.info(f"      Currently selected density: {current_density} gr/mm")
                
                for i in range(len(densities)):
                    self.logger.info(f"      Index {i}: {densities[i]} gr/mm (Blaze: {blazes[i]}, Desc: {descriptions[i]})")
                self.logger.info("   --------------------------------------\n")
            else:
                self.logger.warning("      WARNING: Could not retrieve grating details. Report incomplete.")
        except Exception as e_grating_report:
            self.logger.warning(f"      *** WARNING: Could not generate grating report: {e_grating_report} ***")

    def _move_grating(self, target_index):
        """Internal helper for 5.3 Grating move."""
        self.logger.info(f"   Checking current grating position...")
        try:
            current_grating_ret = self.mono_controller.GetCurrentTurret()
            current_grating_index = int(current_grating_ret[-1]) if isinstance(current_grating_ret, (tuple, list)) else int(current_grating_ret)
            self.logger.info(f"      Current grating is at index {current_grating_index}.")
            
            if current_grating_index != target_index:
                self.logger.info(f"      Moving grating from {current_grating_index} to index {target_index}...")
                self.mono_controller.MovetoTurret(target_index)
                self._wait_for_mono_ready()
                self.logger.info(f"      Grating move complete.")
            else:
                self.logger.info(f"      Grating is already at target index {target_index}.")
        except Exception as e_grating:
            self.logger.warning(f"      *** WARNING: Could not check/move grating: {e_grating} ***")

    def _move_entrance_mirror(self, target_position):
        """Internal helper for 5.4 Mirror move."""
        self.logger.info(f"   Checking current entrance mirror position...")
        try:
            current_mirror_ret = self.mono_controller.GetCurrentMirrorPosition(MIRROR_ENTRANCE)
            current_mirror_pos = int(current_mirror_ret[-1]) if isinstance(current_mirror_ret, (tuple, list)) else int(current_mirror_ret)
            pos_str = "Front" if current_mirror_pos == MIRROR_FRONT else "Side"
            self.logger.info(f"      Current entrance mirror is at position {current_mirror_pos} ({pos_str}).")

            if current_mirror_pos != target_position:
                target_pos_str = "Front" if target_position == MIRROR_FRONT else "Side"
                self.logger.info(f"      Moving entrance mirror to position {target_position} ({target_pos_str})...")
                self.mono_controller.MovetoMirrorPosition(MIRROR_ENTRANCE, target_position)
                self._wait_for_mono_ready()
                self.logger.info(f"      Entrance mirror move complete.")
            else:
                self.logger.info(f"      Entrance mirror is already at target position (Front).")
        except Exception as e_mirror:
            self.logger.warning(f"      *** WARNING: Could not check/move entrance mirror: {e_mirror} ***")

    # ===================================================================
    # --- ACQUISITION & PROCESSING METHODS ---
    # ===================================================================

    def _wait_for_acq_id(self, current_integ_time, current_accum, acq_mode, timeout_buffer=30):
        """Waits for LabSpec to return a valid (positive) Acquisition ID."""
        num_acquisitions = 1 
        
        expected_acq_time = (current_integ_time * current_accum) * num_acquisitions
        actual_timeout = expected_acq_time + timeout_buffer
        self.logger.info(f"      Waiting for Acq ID (timeout {actual_timeout:.1f}s)...")
        start_time = time.time()
        spectrum_id = -1

        while spectrum_id <= 0:
            get_id_ret = self.labspec_activex.GetAcqID()
            try:
                if isinstance(get_id_ret, (tuple, list)):
                    spectrum_id = int(get_id_ret[-1])
                elif isinstance(get_id_ret, (int, float)):
                    spectrum_id = int(get_id_ret)
                else:
                    spectrum_id = -1
            except (ValueError, IndexError):
                spectrum_id = -1

            if spectrum_id > 0:
                return spectrum_id
            if spectrum_id == 0:
                self.logger.debug("      ...acq in progress (ID=0)...")
            elif spectrum_id == -2:
                self.logger.warning("      ...Acq cancelled by user (ID=-2).")
                return -2
            elif spectrum_id == -1:
                self.logger.debug("      ...waiting for acq ID (ID=-1)...")

            if time.time() - start_time > actual_timeout:
                raise Exception(f"Acquisition ID timeout after {actual_timeout:.1f}s.")
            time.sleep(0.1)
        return spectrum_id

    def acquire_frame(self, integration_time_s, accumulations, is_signal_frame=True, auto_show=False, spike_filter_mode=ACQ_SINGLE_SPIKE_REMOVING, dark_sub_mode=ACQ_NO_DARK):
        """
        Starts an acquisition in LabSpec and waits for the Spectrum ID.
        """
        
        self.logger.info(f"   Starting {'SIGNAL' if is_signal_frame else 'BACKGROUND'} Frame ({integration_time_s}s x {accumulations} accum)...")
        
        if is_signal_frame:
            self.labspec_activex.PutValue(0, "DisplayUnit", "nm") # Only set DisplayUnit for the visible frame

        acq_mode = ACQ_SPECTRUM + spike_filter_mode + dark_sub_mode
        if auto_show:
            acq_mode += ACQ_AUTO_SHOW

        self.logger.info(f"      Calling Acq() (Mode: {acq_mode})...")
        self.labspec_activex.Acq(acq_mode, integration_time_s, accumulations, 0, 0)
        
        spectrum_id = self._wait_for_acq_id(integration_time_s, accumulations, acq_mode)
        
        if spectrum_id <= 0:
            raise Exception(f"Acquisition failed, returned ID: {spectrum_id}")
            
        return spectrum_id

    def get_raw_data(self, spectrum_id):
        """Retrieves raw data array from a Spectrum ID for saturation check."""
        y_com = self.labspec_activex.GetValue(spectrum_id, "Data")
        y_raw = y_com[-1] if isinstance(y_com, tuple) else y_com
        
        if not hasattr(y_raw, '__len__'):
            raise TypeError("GetValue(Data) did not return sequence-like object.")
            
        return np.array(y_raw)

    def get_axis(self, spectrum_id):
        """
        Retrieves the X-axis (Wavelength) data array for a given Spectrum ID.
        NEW: Added to robustly get X-axis when background ID is invalid/cached.
        """
        x_com = self.labspec_activex.GetValue(spectrum_id, "Axis")
        x_raw = x_com[-1] if isinstance(x_com, tuple) else x_com
        
        if not hasattr(x_raw, '__len__'):
            raise TypeError("GetValue(Axis) did not return sequence-like object.")
            
        return np.array(x_raw)

    def apply_denoiser(self, spectrum_id, denoiser_factor):
        """Applies the Denoiser treatment to a spectrum ID."""
        if denoiser_factor > 0:
            self.logger.info(f"   Applying Denoiser (Factor: {denoiser_factor}) to ID {spectrum_id}...")
            try:
                # Use imported constants for treatment parameters
                self.labspec_activex.Treat(spectrum_id, "Filter", TREAT_FILTER_START,
                                           TREAT_FILTER_DENOISER, 0, 0, 0, denoiser_factor, 0)
                self.logger.info("   Denoiser applied.")
            except Exception as e_treat:
                self.logger.exception(f"   *** WARNING: Failed to apply Denoiser to ID {spectrum_id}: {e_treat} ***")
        else:
            self.logger.debug(f"   Denoiser disabled for ID {spectrum_id}.")

    def get_filtered_spectrum(self, signal_spectrum_id, dark_spectrum_id):
        """
        Retrieves the X-axis and filtered Y-axis data for both signal and dark.
        
        Returns: x_values, y_signal_denoised_values, y_dark_denoised_values
        """
        self.logger.info("   Getting filtered data arrays for subtraction...")
        
        x_data_com = self.labspec_activex.GetValue(signal_spectrum_id, "Axis")
        y_signal_denoised_com = self.labspec_activex.GetValue(signal_spectrum_id, "Data")
        y_dark_denoised_com = self.labspec_activex.GetValue(dark_spectrum_id, "Data")

        x_raw = x_data_com[-1] if isinstance(x_data_com, tuple) else x_data_com
        y_signal_denoised_raw = y_signal_denoised_com[-1] if isinstance(y_signal_denoised_com, tuple) else y_signal_denoised_com
        y_dark_denoised_raw = y_dark_denoised_com[-1] if isinstance(y_dark_denoised_com, tuple) else y_dark_denoised_com

        if not (hasattr(x_raw, '__len__') and hasattr(y_signal_denoised_raw, '__len__') and hasattr(y_dark_denoised_raw, '__len__')):
             raise TypeError("GetValue did not return sequence-like objects for all filtered data.")
        
        x_values = np.array(x_raw)
        y_signal_denoised_values = np.array(y_signal_denoised_raw)
        y_dark_denoised_values = np.array(y_dark_denoised_raw)
        
        if x_values.ndim != 1 or y_signal_denoised_values.ndim != 1 or y_dark_denoised_values.ndim != 1 or \
           len(x_values) != len(y_signal_denoised_values) or len(x_values) != len(y_dark_denoised_values):
            raise ValueError(f"Data dimension/length mismatch: X={x_values.shape}, Signal Y={y_signal_denoised_values.shape}, Dark Y={y_dark_denoised_values.shape}")
        
        return x_values, y_signal_denoised_values, y_dark_denoised_values


    def save_tsf_file(self, spectrum_id, full_tsf_path):
        """Saves a TSF file for a given Spectrum ID."""
        self.logger.info(f"   Saving TSF for ID {spectrum_id} to: {full_tsf_path}")
        save_result_ret = self.labspec_activex.Save(spectrum_id, full_tsf_path, "")
        save_result = int(save_result_ret[-1]) if isinstance(save_result_ret, (tuple, list)) else int(save_result_ret)
        if save_result != 0:
            self.logger.error(f"   *** TSF SAVE FAILED (Error code: {save_result}) ***")
            return False
        return True
        
    def remove_spectrum(self, spectrum_id):
        """Removes a spectrum from LabSpec memory."""
        if spectrum_id > 0:
            self.logger.debug(f"   Cleaning up spectrum ID {spectrum_id} from memory.")
            self.labspec_activex.Exec(spectrum_id, 2, 0) # 2 = REMOVE_DATA
        
    # ===================================================================
    # --- CLEANUP METHOD ---
    # ===================================================================

    def close_communications(self):
        """Closes all COM object communications and releases objects."""
        self.logger.info("\n--- Cleaning up Spectrometer COM connections ---")

        # --- Close Monochromator ---
        if self.mono_controller:
            try:
                self.logger.info("   Closing Monochromator communication...")
                self.mono_controller.CloseCommunications()
                self.logger.info("   Monochromator communication closed.")
            except Exception as e:
                self.logger.warning(f"   Error closing Monochromator: {e}")

        # --- Close CCD Controller ---
        if self.ccd_controller:
            try:
                self.logger.info("   Closing CCD Controller communication...")
                self.ccd_controller.CloseCommunications()
                self.logger.info("   CCD Controller communication closed.")
            except Exception as e:
                self.logger.warning(f"   Error closing CCD Controller: {e}")

        # --- Release ActiveX/COM Objects ---
        self.labspec_activex = None
        self.mono_controller = None
        self.ccd_controller = None
        self.logger.info("   COM objects released from Python memory.")