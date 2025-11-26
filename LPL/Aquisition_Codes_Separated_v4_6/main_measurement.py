"""
Master Python script to control:
1. Thorlabs Elliptec (ELLO) rotation stage (via 'elliptec_motor_controller' module)
2. Quantum Composers Sapphire 9214 Pulse Generator (via 'sapphire_pulser_controller' module)
3. Horiba LabSpec 6 Spectrometer (via 'horiba_spectrometer_controller' module)

This script performs a 50-point LINEAR angle scan. At each angle,
it uses a SMART STEP-DOWN ACQUISITION with BACKGROUND CACHING:
1. Starts acquisition at the last known non-saturating integration time.
2. If saturated, steps down the integration time until successful.
3. Acquires a "Signal" frame.
4. Checks if a "Background" for this integration time is in CACHE.
   - If YES: Reuses cached data (Fast).
   - If NO: Acquires new background and caches it (Slow).
5. Subtracts, saves data, and plots in real-time.

*** IMPORTANT ***
- You MUST run this script *with the visible LabSpec 6 application CLOSED*.
"""

# --- Python Imports ---
import time
import numpy as np
import sys
import os
import signal
import shutil
import logging
import matplotlib.pyplot as plt
import threading # Added for clean shutdown handling

# --- Import Controllers ---
from horiba_spectrometer_controller import HoribaSpectrometerController 
from sapphire_pulser_controller import SapphirePulserController 
from elliptec_motor_controller import ElliptecMotorController

# --- Import All Configuration Constants ---
from experiment_config import (
    # Experiment Parameters (Section 2)
    START_ANGLE, END_ANGLE, NUM_POINTS, ACCUMULATIONS,
    CHOSEN_SPIKE_FILTER_MODE, CHOSEN_DARK_SUB_MODE, DENOISER_FACTOR,
    BASE_SAVE_DIRECTORY, SATURATION_THRESHOLD, INTEGRATION_TIME_PRESETS_S,
    INTEGRATION_WARNING_THRESHOLD,
    # Hardware/Installation Settings (Section 3)
    PAUSE_AFTER_MOVE_S
)

# ===================================================================
# --- CONFIGURATION CONSTANTS (All moved to experiment_config.py) ---
# ===================================================================


class LabAutomation:
    """
    Encapsulates all hardware control, setup, acquisition, and
    cleanup logic for the angle-resolved spectroscopy experiment.
    """
    def __init__(self):
        # --- Hardware Controller Objects ---
        self.spectrometer_controller = None 
        self.pulser_controller = None 
        self.motor_controller = None 
        
        # --- Plotting Attributes ---
        self.plot_fig = None
        self.plot_ax = None
        self.line_signal = None
        self.line_background = None
        self.line_subtracted = None
        
        # --- State Flags & Memory ---
        self.shutdown_requested = False
        self.shutdown_event = threading.Event() 
        self.last_successful_integ_time_s = None 
        
        # --- NEW: Background Cache ---
        # Format: { integration_time_float: numpy_array_of_data }
        self.background_cache = {}
        
        # --- Path/Date ---
        self.script_run_date = ""
        self.save_directory = ""
        
        # --- Logging ---
        self.logger = None 
        self.log_file_handler = None
        self.log_stream_handler = None

    def _handle_shutdown(self, sig, frame):
        """Signal handler for Ctrl+C (SIGINT)."""
        if self.shutdown_requested:
            self.logger.critical("\n--- FORCE EXIT (SECOND CTRL+C). MAY LEAVE HARDWARE IN BAD STATE. ---")
            sys.exit(1)
            
        self.logger.warning("\n\n--- SHUTDOWN REQUESTED (CTRL+C) ---")
        self.logger.warning("--- Finishing current step, then cleaning up. ---")
        self.logger.warning("--- Press Ctrl+C again to force immediate exit. ---")
        self.shutdown_requested = True
        self.shutdown_event.set() 

    def _setup_logging(self):
        """Sets up the logger to print to console and a log file."""
        try:
            self.logger = logging.getLogger('LabAutomation')
            self.logger.setLevel(logging.INFO)
            
            if self.logger.hasHandlers():
                self.logger.handlers.clear()

            log_filename = f"{self.script_run_date}_measurement.log"
            log_filepath = os.path.join(self.save_directory, log_filename)
            
            self.log_file_handler = logging.FileHandler(log_filepath)
            file_format = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            self.log_file_handler.setFormatter(file_format)
            self.log_file_handler.setLevel(logging.INFO)
            self.logger.addHandler(self.log_file_handler)
            
            self.log_stream_handler = logging.StreamHandler(sys.stdout)
            stream_format = logging.Formatter('%(message)s') 
            self.log_stream_handler.setFormatter(stream_format)
            self.log_stream_handler.setLevel(logging.INFO)
            self.logger.addHandler(self.log_stream_handler)
            
            self.logger.info(f"Logging initialized. Log file: {log_filepath}")

        except Exception as e:
            print(f"CRITICAL: Failed to initialize logging: {e}")
            print("--- SCRIPT WILL CONTINUE WITH PRINT STATEMENTS ---")
            self.logger = None

    def _log_or_print(self, message, level='info'):
        """Helper to safely log or print if logging failed."""
        if self.logger:
            if level == 'info':
                self.logger.info(message)
            elif level == 'warning':
                self.logger.warning(message)
            elif level == 'error':
                self.logger.error(message)
            elif level == 'critical':
                self.logger.critical(message)
            elif level == 'exception':
                self.logger.exception(message)
        else:
            print(message) 


    def _save_code_snapshot(self):
        """Creates a timestamped folder and copies source code into it."""
        files_to_snapshot = [
            "main_measurement.py", 
            "experiment_config.py",
            "horiba_spectrometer_controller.py",
            "sapphire_pulser_controller.py",
            "elliptec_motor_controller.py"
        ]
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snapshot_folder = f"Used_Acquisition_Codes_{timestamp}"
        snapshot_path = os.path.join(self.save_directory, snapshot_folder)
        
        try:
            os.makedirs(snapshot_path, exist_ok=True)
            self.logger.info(f"Created code snapshot folder: {snapshot_folder}")
            
            for filename in files_to_snapshot:
                if os.path.exists(filename):
                    shutil.copy2(filename, os.path.join(snapshot_path, filename))
                else:
                    self.logger.warning(f"Snapshot skipped (file not found): {filename}")
        except Exception as e:
            self.logger.warning(f"Failed to save code snapshot: {e}")


    def _create_measurement_dir(self):
        """Finds and creates a unique measurement directory for this run."""
        print(f"Ensuring base save directory exists: {BASE_SAVE_DIRECTORY}")
        os.makedirs(BASE_SAVE_DIRECTORY, exist_ok=True)
        
        self.script_run_date = time.strftime("%Y%m%d")
        
        measurement_num = 1
        while True:
            folder_name = f"{self.script_run_date}_Measurement_{measurement_num}"
            new_save_dir = os.path.join(BASE_SAVE_DIRECTORY, folder_name)
            
            if not os.path.exists(new_save_dir):
                print(f"Creating new measurement directory: {new_save_dir}")
                os.makedirs(new_save_dir)
                self.save_directory = new_save_dir 
                break
            measurement_num += 1
            
        # =================================================================
        # [NEW] 1. Create the 'Raw_Data' subfolder for Spectra
        # =================================================================
        raw_data_path = os.path.join(self.save_directory, "Raw_Data")
        os.makedirs(raw_data_path, exist_ok=True)
        print(f"Created subfolder: {raw_data_path}")

        # =================================================================
        # [NEW] 2. Call the dedicated snapshot method
        # (This REPLACES the old 'try... shutil.copyfile...' block)
        # =================================================================
        self._save_code_snapshot()
            
        

    def _connect_hardware(self):
        """Connects to all hardware components in sequence."""
        try:
            self.motor_controller = ElliptecMotorController(self.logger)
            self.motor_controller.connect()
            
            self.pulser_controller = SapphirePulserController(self.logger)
            self.pulser_controller.connect()
            
            self.spectrometer_controller = HoribaSpectrometerController(self.logger)
            self.spectrometer_controller.connect_all()
            
        except Exception as e:
            self.logger.critical(f"\n--- FATAL HARDWARE CONNECTION ERROR ---")
            self.logger.exception(f"   Error: {e}")
            self.logger.critical("   Script will not proceed to scan. Cleanup will be attempted.")
            raise 

    def _setup_spectrometer_state(self):
        """Sets the initial state of the monochromator (now delegated to controller)."""
        if not self.spectrometer_controller:
            raise Exception("Spectrometer controller not initialized.")
            
        self.spectrometer_controller.setup_spectrometer_state()
        self.logger.info("Spectrometer state setup delegated to controller.")

    def _ask_retry_or_stop(self, error_message):
        """Helper to ask the user to retry or stop the ENTIRE ANGLE."""
        while True:
            self.logger.warning(f"--- {error_message.upper()} ---")
            self.logger.info("\nPlease choose an action:")
            choice = input("    [R]etry this angle, or [S]top the entire scan? ").strip().upper()
            
            if choice == 'S':
                self.logger.warning("User selected [S]top. Halting experiment.")
                return False
            
            elif choice == 'R':
                self.logger.info("User selected [R]etry.")
                input("    >>> Please modify hardware (filters, alignment) NOW. Press ENTER when ready to re-acquire... <<<")
                self.logger.info("... Retrying acquisition for this angle ...")
                return True
            
            else:
                self.logger.warning(f"Invalid choice '{choice}'. Please enter 'R' or 'S'.")

    def _ask_retry_or_stop_time(self, error_message, integ_time_s):
        """NEW Helper to ask the user to retry or stop the CURRENT TIME STEP (Acquisition only)."""
        while True:
            self.logger.warning(f"--- {error_message.upper()} ---")
            self.logger.info(f"\nPlease choose an action for time {integ_time_s}s:")
            choice = input("    [R]etry this TIME, or [S]top the entire scan? ").strip().upper()
            
            if choice == 'S':
                self.logger.warning("User selected [S]top. Halting experiment.")
                self.shutdown_event.set() 
                return False
            
            elif choice == 'R':
                self.logger.info("User selected [R]etry.")
                input("    >>> Please check connections/hardware. Press ENTER when ready to re-acquire... <<<")
                self.logger.info(f"... Retrying acquisition for {integ_time_s}s ...")
                return True
            
            else:
                self.logger.warning(f"Invalid choice '{choice}'. Please enter 'R' or 'S'.")


    def _run_single_point(self, angle, i, total_points):
        """
        Moves, acquires, and saves data for a single angle using the 
        Smart Step-Down Acquisition logic AND Background Caching.
        """
        
        target_angle = round(angle, 2)
        self.logger.info(f"\n--- Step {i+1}/{total_points}: Angle = {target_angle} deg ---")

        # --- 7.1: Move Elliptec Motor ---
        self.motor_controller.set_angle(target_angle)
        time.sleep(PAUSE_AFTER_MOVE_S)

        # --- 7.2: Prepare Integration Time List ---
        try:
            if self.last_successful_integ_time_s is None:
                 start_index = 0
            else:
                 start_index = INTEGRATION_TIME_PRESETS_S.index(self.last_successful_integ_time_s)
        except ValueError:
             self.logger.warning(f"Time {self.last_successful_integ_time_s} not in presets. Starting from longest.")
             start_index = 0
             
        times_to_try = INTEGRATION_TIME_PRESETS_S[start_index:]
        self.logger.info(f"   Starting acquisition test from: {times_to_try[0]}s. (Presets to try: {times_to_try})")


        # --- 7.3: Acquisition Loop (Iterate through times_to_try) ---
        acquisition_successful = False
        signal_spectrum_id = -1
        dark_spectrum_id = -1 # This will hold the ID if we acquire a new one, or -1 if cached
        bg_id_for_header = "Unknown" # String to write to file header
        
        for current_integ_time in times_to_try:
            if self.shutdown_event.is_set(): return 

            while True: 
                signal_spectrum_id = -1
                dark_spectrum_id = -1
                bg_id_for_header = "Unknown"
                
                try:
                    self.logger.info(f"   Trying acquisition at time: {current_integ_time}s")
                    
                    # 7.3.A: Acquire SIGNAL (Pulser ON)
                    self.pulser_controller.set_state(1) 
                    time.sleep(0.5) 
                    
                    signal_spectrum_id = self.spectrometer_controller.acquire_frame(
                        integration_time_s=current_integ_time, 
                        accumulations=ACCUMULATIONS, 
                        is_signal_frame=True, 
                        auto_show=True,
                        spike_filter_mode=CHOSEN_SPIKE_FILTER_MODE, 
                        dark_sub_mode=CHOSEN_DARK_SUB_MODE 
                    )

                    # 7.3.B: Check Saturation on RAW data
                    y_signal_values_raw = self.spectrometer_controller.get_raw_data(signal_spectrum_id)
                    max_intensity = np.max(y_signal_values_raw)
                    del y_signal_values_raw 

                    # --- HARD SATURATION CHECK ---
                    if max_intensity >= SATURATION_THRESHOLD: 
                        self.logger.critical(f"   *** HARD SATURATED at {current_integ_time}s (Max: {max_intensity}). Trying shorter time.")
                        
                        self.spectrometer_controller.remove_spectrum(signal_spectrum_id)
                        signal_spectrum_id = -1 
                        raise StopIteration("Hard saturation detected.") 
                    
                    
                    # 7.3.C: Acquire or Retrieve BACKGROUND (Pulser OFF)
                    y_dark_denoised = None

                    # --- CACHE CHECK (Always attempt background subtraction) ---
                    if current_integ_time in self.background_cache:
                        # HIT: Use cached array
                        self.logger.info(f"      Using CACHED background for {current_integ_time}s.")
                        y_dark_denoised = self.background_cache[current_integ_time]
                        dark_spectrum_id = -1 # No ID to clean up
                        bg_id_for_header = "Cached"
                    else:
                        # MISS: Acquire new background
                        self.logger.info(f"      Acquiring NEW background for {current_integ_time}s...")
                        self.pulser_controller.set_state(0) 
                        time.sleep(0.5) 

                        dark_spectrum_id = self.spectrometer_controller.acquire_frame(
                            integration_time_s=current_integ_time, 
                            accumulations=ACCUMULATIONS, 
                            is_signal_frame=False, 
                            auto_show=False, 
                            spike_filter_mode=CHOSEN_SPIKE_FILTER_MODE,
                            dark_sub_mode=CHOSEN_DARK_SUB_MODE
                        )
                        bg_id_for_header = str(dark_spectrum_id)
                        
                        # We must process (denoise) this NEW background immediately to cache the final array
                        self.spectrometer_controller.apply_denoiser(dark_spectrum_id, DENOISER_FACTOR)
                        
                        # Retrieve the processed data array
                        # NOTE: get_filtered_spectrum expects TWO IDs. 
                        # We can fetch just raw data via get_raw_data, but we need the filtered version.
                        # We can reuse get_raw_data because we applied the filter IN PLACE on the LabSpec object.
                        y_dark_denoised = self.spectrometer_controller.get_raw_data(dark_spectrum_id)
                        
                        # Store in cache
                        self.background_cache[current_integ_time] = y_dark_denoised
                        self.logger.info(f"      New background cached.")
                    
                    # Acquisition Succeeded!
                    acquisition_successful = True 
                    break 
                    
                except StopIteration:
                    break 
                    
                except Exception as e_acq:
                    self.logger.exception(f"   ERROR during time test acquisition: {e_acq}")
                    try:
                        self.pulser_controller.set_state(0)
                        self.spectrometer_controller.remove_spectrum(signal_spectrum_id)
                        self.spectrometer_controller.remove_spectrum(dark_spectrum_id)
                    except: pass 

                    if not self._ask_retry_or_stop_time(f"Acquisition failed for {current_integ_time}s.", current_integ_time):
                        raise Exception("User chose to stop.") 
                    
            if acquisition_successful:
                break 

        # --- 7.4: Handle All Time Presets Failed ---
        if not acquisition_successful:
            self.logger.critical(f"   *** ALL {len(INTEGRATION_TIME_PRESETS_S)} TIME PRESETS FAILED (SATURATED/ERROR) for angle {target_angle} ***")
            
            if not self._ask_retry_or_stop("All preset integration times failed"):
                raise Exception("User chose to stop.") 
            else:
                self.last_successful_integ_time_s = INTEGRATION_TIME_PRESETS_S[0]
                return 


        # --- 7.5: Data Processing, State Update, and Save (Success Path) ---
        try:
            self.logger.info(f"   Acquisition succeeded at {current_integ_time}s. Max intensity: {max_intensity:.0f}.")
            
            # 1. Update State Memory
            current_index = INTEGRATION_TIME_PRESETS_S.index(current_integ_time)
            
            if max_intensity >= INTEGRATION_WARNING_THRESHOLD:
                self.logger.info("   Signal is HIGH. Proactively stepping down guess time for next angle.")
                next_index = min(current_index + 1, len(INTEGRATION_TIME_PRESETS_S) - 1)
            else:
                self.logger.info("   Signal is GOOD. Retaining current time as guess for next angle.")
                next_index = current_index
                
            self.last_successful_integ_time_s = INTEGRATION_TIME_PRESETS_S[next_index]
            self.logger.info(f"   Next angle's starting time will be: {self.last_successful_integ_time_s}s")
            
            # 2. Apply Denoiser to SIGNAL (Background is already denoised in cache)
            self.spectrometer_controller.apply_denoiser(signal_spectrum_id, DENOISER_FACTOR) 
            
            # Get Signal Data (We can use get_raw_data since we treated it in-place)
            y_signal_denoised = self.spectrometer_controller.get_raw_data(signal_spectrum_id)
            
            # Get X-Axis (Wavelength) - Use the NEW get_axis method
            x_values = self.spectrometer_controller.get_axis(signal_spectrum_id)
            
            # 3. Perform Subtraction
            if y_dark_denoised is not None:
                y_final_values = y_signal_denoised - y_dark_denoised
            else:
                # This branch should theoretically not be hit if subtraction is mandatory,
                # but kept for robustness if background acquisition somehow failed
                y_final_values = y_signal_denoised


            self.logger.info("   Filtered subtraction complete. Proceeding to save.")

            # 4. Save Files
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            base_filename = f"{self.script_run_date}_spectrum_angle_{target_angle:.2f}deg_t_{current_integ_time}s_id_{signal_spectrum_id}_{timestamp}"

            # [NEW] Define the subfolder path specifically for data
            raw_data_dir = os.path.join(self.save_directory, "Raw_Data")

            # Save TSF
            tsf_filename = f"{base_filename}.tsf"
            full_tsf_path = os.path.join(raw_data_dir, tsf_filename) # <--- UPDATED
            self.spectrometer_controller.save_tsf_file(signal_spectrum_id, full_tsf_path)
            self.logger.info(f"   Denoised Raw Signal TSF saved to: {full_tsf_path}")

            # Save TXT
            txt_filename = f"{base_filename}_Subtracted_Denoised.txt"
            full_txt_path = os.path.join(raw_data_dir, txt_filename)
            
            header_lines = [
                f"Date: {timestamp}",
                f"Angle (deg): {target_angle:.2f}",
                f"Integration Time (s): {current_integ_time}", 
                f"Accumulations: {ACCUMULATIONS}", 
                f"Denoised Signal ID: {signal_spectrum_id}",
                f"Denoised Background ID: {bg_id_for_header}",
                f"Denoiser Factor: {DENOISER_FACTOR}", 
                "---",
                "Wavelength (nm), Intensity (Counts, Denoised Signal-Background)"
            ]
            header = "\n".join(header_lines)
            data_to_save = np.vstack((x_values, y_final_values)).T
            np.savetxt(full_txt_path, data_to_save, delimiter=',', header=header, fmt='%.4f, %.2f')
            self.logger.info(f"   Denoised Subtracted TXT Save successful to: {full_txt_path}")

            # 5. Update plot
            # We handle the case where background might be None for plotting
            plot_bg = y_dark_denoised if y_dark_denoised is not None else np.zeros_like(y_signal_denoised)
            self._update_plot(target_angle, x_values, y_final_values, y_signal_denoised, plot_bg)

        except Exception as e_process:
            self.logger.exception(f"   ERROR during post-acquisition process: {e_process}")
            if not self._ask_retry_or_stop("Data processing/saving failed"):
                raise Exception("User chose to stop.") 
            else:
                pass 

        finally:
            # --- Cleanup Data Objects ---
            self.spectrometer_controller.remove_spectrum(signal_spectrum_id)
            # Only remove dark_spectrum_id if it was a NEW acquisition (positive ID)
            self.spectrometer_controller.remove_spectrum(dark_spectrum_id)
            self.logger.info("   Data objects cleaned from memory.")


    def _update_plot(self, target_angle, x_values, y_final_values, y_signal_denoised_values, y_dark_denoised_values):
        """Helper to update the Matplotlib plot."""
        try:
            self.logger.info("   Updating real-time plot with all data lines...")
            
            self.line_signal.set_data(x_values, y_signal_denoised_values)
            self.line_background.set_data(x_values, y_dark_denoised_values)
            self.line_subtracted.set_data(x_values, y_final_values)
            
            max_subtracted_intensity = np.max(y_final_values)
            self.plot_ax.set_title(f"Angle: {target_angle:.2f} deg (Subtracted Max: {max_subtracted_intensity:.0f}, T_int: {self.last_successful_integ_time_s}s)")
            
            self.plot_ax.relim()
            self.plot_ax.autoscale_view()
            
            self.plot_fig.canvas.draw()
            self.plot_fig.canvas.flush_events()
            plt.pause(0.01) 
        except Exception as e_plot:
            self.logger.warning(f"   WARNING: Failed to update plot: {e_plot}")

    def _run_angle_scan(self):
        """Generates the position list and runs the main acquisition loop."""
        if not all([self.spectrometer_controller, self.pulser_controller, self.motor_controller]):
            raise Exception("Cannot start main loop, required controllers failed to initialize.")
            
        if not INTEGRATION_TIME_PRESETS_S:
            self.logger.critical("FATAL: INTEGRATION_TIME_PRESETS_S list in config is empty!")
            raise ValueError("INTEGRATION_TIME_PRESETS_S must not be empty.")

        # --- Set Initial Guess ---
        # The first run starts checking from the longest time in the presets list.
        self.last_successful_integ_time_s = INTEGRATION_TIME_PRESETS_S[0]
        self.logger.info(f"Setting initial integration time guess to: {self.last_successful_integ_time_s}s")
        
        self.logger.info("Generating 50-point LINEAR position list...")
        # CHANGED: From geomspace (log) to linspace (linear)
        position_list = np.linspace(START_ANGLE, END_ANGLE, NUM_POINTS)
        self.logger.info(f"List generated: {len(position_list)} points from {START_ANGLE} to {END_ANGLE}.")

        self.motor_controller.home()
        self.logger.info("Elliptec motor homing complete.")

        self.logger.info("\n\n*** STARTING MAIN ACQUISITION SEQUENCE ***")
        for i, angle in enumerate(position_list):
            if self.shutdown_requested or self.shutdown_event.is_set():
                self.logger.warning("--- Shutdown requested. Breaking main loop. ---")
                break
            
            try:
                self._run_single_point(angle, i, len(position_list))
            except Exception as e_point:
                self.logger.exception(f"--- ERROR during point {i+1} (angle {angle:.2f}) ---")
                self.logger.error(f"--- Details: {e_point} ---")
                if "user chose to stop" in str(e_point) or self.shutdown_requested or self.shutdown_event.is_set():
                    self.logger.error("--- Halting main loop as requested. ---")
                    break 
                else:
                    self.logger.error("--- Attempting to continue to next point... ---")

        self.logger.info("\n*** SEQUENCE COMPLETE ***")

    def _cleanup_hardware(self):
        """Homes motor and closes all hardware connections."""
        self.logger.info("\n--- Cleaning up all hardware connections ---")
        
        if self.motor_controller:
            try:
                self._log_or_print("   Homing Elliptec motor (returning to zero-stop)...", level='info')
                self.motor_controller.home()
            except Exception as e:
                self._log_or_print(f"   Error during Elliptec homing in cleanup: {e}", level='warning')
            
            self.motor_controller.close()

        if self.pulser_controller:
            self.pulser_controller.close()

        if self.spectrometer_controller:
            self.spectrometer_controller.close_communications()
        
        if self.logger:
            self._log_or_print("\nPython script finished.", level='info')
            if self.log_file_handler:
                self.log_file_handler.close()
                self.logger.removeHandler(self.log_file_handler)
            if self.log_stream_handler:
                self.log_stream_handler.close()
                self.logger.removeHandler(self.log_stream_handler)
        else:
            print("\nPython script finished.")

    def run(self):
        """Main entry point for the automation script."""
        
        try:
            self._create_measurement_dir()
            self._setup_logging()
            signal.signal(signal.SIGINT, self._handle_shutdown)
            self._connect_hardware()
            self._setup_spectrometer_state()
            
            self.logger.info("\n--- Initializing Real-Time Plot (Signal, Background, Subtracted) ---")
            plt.ion() 
            self.plot_fig, self.plot_ax = plt.subplots()
            
            self.line_signal, = self.plot_ax.plot([], [], 'r-', label='Signal (Laser ON)', alpha=0.5, linewidth=1)
            self.line_background, = self.plot_ax.plot([], [], 'k-', label='Background (Laser OFF)', alpha=0.5, linewidth=1)
            self.line_subtracted, = self.plot_ax.plot([], [], 'b-', label='Subtracted', linewidth=2)
            
            self.plot_ax.set_xlabel("Wavelength (nm)")
            self.plot_ax.set_ylabel("Intensity (Counts)")
            self.plot_ax.legend(loc='upper right') 
            self.plot_ax.grid(True)
            self.plot_fig.canvas.draw()
            self.plot_fig.canvas.flush_events()
            self.logger.info("Plot window opened.")
            
            self.logger.info("\n*** PRESS CTRL+C AT ANY TIME TO INITIITE A GRACEFUL SHUTDOWN ***\n")
            self._run_angle_scan()

        except KeyboardInterrupt:
            self._log_or_print("\n\n--- GRACEFUL SHUTDOWN INITIATED ---", level='warning')
            self._log_or_print("--- Proceeding to cleanup... ---", level='warning')
        
        except Exception as e:
            self._log_or_print(f"\n\n--- A FATAL ERROR OCCURRED ---", level='critical')
            self._log_or_print(f"Error: {e}", level='exception')
            self._log_or_print("--- Attempting to clean up hardware... ---", level='warning')

        finally:
            if self.plot_fig:
                self._log_or_print("\nScan complete. Close the plot window to exit.", level='info')
                plt.ioff() 
                self.plot_fig.canvas.manager.set_window_title("Scan Complete - Close this window to exit")
                plt.show(block=True) 
            
            self.logger.info("Running final hardware cleanup...")
            self._cleanup_hardware()

# ===================================================================
# --- SCRIPT EXECUTION ---
# ===================================================================
if __name__ == "__main__":
    app = LabAutomation()
    app.run()