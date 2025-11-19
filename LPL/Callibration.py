"""
MASTER EXPERIMENT CONTROLLER (GLASS BOX VERSION)
-------------------------------------------------------------------------
Hardware:
  1. Thorlabs Elliptec (ELLO) Rotation Stage
  2. Quantum Composers Sapphire 9214 Pulse Generator
  3. Gentec MAESTRO Power Meter

Documentation References:
  - Gentec MAESTRO User Manual V6 (Sections 3.4.3 for Serial Commands)
  - Quantum Composers 9200 Operators Manual (Section 8: Programming & SCPI Commands)

Author: [Your Name/Lab]
Refactored for: High Visibility ("Glass Box") and Educational Value.
"""

import time
import sys
import numpy as np
import pandas as pd
import serial
import elliptec
import qcsapphire
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

# --- Windows Keyboard Handling ---
# WHY IS THIS HERE?
# The 'msvcrt' library allows us to check if a key is pressed without pausing the code.
# This is specific to Windows. We use it to "flush" (clear) the keyboard buffer
# so that accidental key presses during the experiment don't auto-answer 
# the "Do you want to retry?" prompts later on.
try:
    import msvcrt
    ON_WINDOWS = True
except ImportError:
    ON_WINDOWS = False
    # If we are on Mac/Linux, we create a fake class so the code doesn't crash.
    class msvcrt:
        @staticmethod
        def kbhit(): return False
        @staticmethod
        def getch(): return b''


# ============================================================================
# 1. CONFIGURATION
# ============================================================================

@dataclass
class Config:
    """
    Global experiment configuration.
    Change these values to adjust the experiment without touching the logic code.
    """
    
    # --- Meta ---
    # Used for naming the output file. Change this if you change the sample.
    EXPERIMENT_NAME: str = "wheel_calibration"
    SAVE_DIRECTORY: str = r"C:\Users\Equipe_OPAL\Desktop\Kaya\gentec data"

    # --- Connectivity ---
    # These must match the ports in Windows Device Manager.
    PORT_MOTOR: str = 'COM6'
    PORT_PULSER: str = 'COM5'
    PORT_METER: str = 'COM7'
    
    # --- Hardware Settings ---
    MOTOR_ADDR: str = '0'
    MAESTRO_BAUD: int = 115200 # Standard Baud rate for Gentec Maestro (Manual Sec 3.1.2.2)
    DETECTION_WAVELENGTH: int = 337 # nm - Required for internal calibration tables
    
    # --- Scan Logic ---
    START_ANGLE: float = 190.0
    END_ANGLE: float = 210.0
    STEP_ANGLE: float = 5.0
    # Time to wait after the motor moves before shooting. 
    # Important to let mechanical vibrations die down so they don't affect alignment.
    MOVE_SETTLE_TIME: float = 0.5
    
    # --- Laser/Pulse Logic ---
    NUM_PULSES: int = 50
    PULSE_RATE_HZ: float = 10.0
    PULSE_WIDTH_S: float = 5e-6
    PULSE_VOLTAGE_V: float = 5.0
    
    # --- Data Analysis ---
    SKIP_FIRST_N: int = 5        # Lasers often have unstable energy for the first few shots.
    POWER_LIMIT_J: float = 60e-9 # 60 nJ. If we hit this, we pause to add filters.
    MIN_PULSE_COUNT: int = 35    # If we receive fewer than this, something is broken.
    
    # New Safety Check: Too many pulses means noise triggering
    @property
    def MAX_PULSE_COUNT(self) -> int:
        """If we get more than this, we are likely reading noise."""
        return self.NUM_PULSES + 10 

    STD_DEV_CUTOFF: float = 3.0  # Statistical filter to remove extreme outliers.

    @property
    def pulse_period_s(self) -> float:
        """Calculates period (T = 1/f) because the hardware expects seconds, not Hz."""
        return 1.0 / self.PULSE_RATE_HZ if self.PULSE_RATE_HZ > 0 else 0.1

    @property
    def burst_duration_s(self) -> float:
        """Calculates how long the laser needs to stay ON to fire N pulses."""
        return self.pulse_period_s * self.NUM_PULSES

    def get_filename(self) -> str:
        """
        Generates a descriptive filename automatically.
        Format: YYYYMMDD_HHMMSS_ExpName_Start_to_End_by_Step.csv
        Added time (Hour-Minute-Second) to distinguish multiple runs on the same day.
        """
        timestamp_str = time.strftime("%Y%m%d_%H%M%S") # e.g., 20231027_143005
        s = int(self.START_ANGLE) if self.START_ANGLE.is_integer() else self.START_ANGLE
        e = int(self.END_ANGLE) if self.END_ANGLE.is_integer() else self.END_ANGLE
        st = int(self.STEP_ANGLE) if self.STEP_ANGLE.is_integer() else self.STEP_ANGLE
        
        return f"{timestamp_str}_{self.EXPERIMENT_NAME}_{s}_to_{e}_by_{st}.csv"


# ============================================================================
# 2. UTILITIES & LOGGING
# ============================================================================

class ExperimentLogger:
    """
    Handles printing to console.
    It adds indentation to make the output look like a structured tree,
    making it easier to read the flow of the experiment.
    """
    def __init__(self):
        self.level = 0
        
    def indent(self):
        self.level += 1
        
    def unindent(self):
        if self.level > 0: self.level -= 1
        
    def info(self, msg: str):
        prefix = "    " * self.level
        print(f"{prefix}{msg}")
        sys.stdout.flush() # Forces the text to appear immediately, even if Python is busy

    def warning(self, msg: str):
        prefix = "    " * self.level
        print(f"\n{prefix}*** WARNING: {msg} ***")
        sys.stdout.flush()

    def error(self, msg: str):
        prefix = "    " * self.level
        print(f"\n{prefix}!!! ERROR: {msg} !!!")
        sys.stdout.flush()

    def raw(self, msg: str):
        """Prints raw hardware comms with deeper indentation to separate it from logic."""
        prefix = "    " * (self.level + 1)
        print(f"{prefix}{msg}")
        sys.stdout.flush()

    def input(self, prompt: str) -> str:
        """
        Clears the keyboard buffer before asking for input.
        WHY? If you accidentally typed '2' five minutes ago while the script was running,
        we don't want that '2' to automatically answer a safety prompt now.
        """
        if ON_WINDOWS:
            while msvcrt.kbhit():
                msvcrt.getch()
        prefix = "    " * self.level
        return input(f"{prefix}>>> {prompt}")

log = ExperimentLogger()


# ============================================================================
# 3. HARDWARE WRAPPERS
# ============================================================================

class GentecMaestro:
    """
    Wrapper for the Gentec MAESTRO Power Meter.
    This class handles the ASCII commands described in the Maestro User Manual (Sec 3.4.3).
    """
    def __init__(self, port: str, baud: int, wavelength: int):
        log.info(f"Connecting to MAESTRO on {port}...")
        self.target_wavelength = wavelength
        # Timeout of 2.0s ensures we don't hang forever if the device is unplugged
        self.ser = serial.Serial(port, baudrate=baud, timeout=2.0)
        
        self._verify_connection()
        self._setup_energy_mode()

    def _send(self, cmd: str) -> str:
        """
        Sends a command to the serial port and returns the response.
        See Maestro Manual Sec 3.4.1.2 (Text Mode Rules).
        """
        # Flush Input: clear any old data sitting in the buffer (garbage collection)
        self.ser.flushInput()
        
        # GLASS BOX: Show exactly what we are sending
        log.raw(f"[TX]: {cmd}")
        
        # Write command + Carriage Return (\r) as required by Manual Sec 3.4.1.2
        self.ser.write((cmd + '\r').encode())
        
        # WHY SLEEP? Serial communication is slow. The device needs time to 
        # process the command and write the response to the buffer.
        time.sleep(0.2)
        
        # Read the response
        resp = self.ser.readline().decode('ascii').strip()
        
        # GLASS BOX: Show exactly what we received
        log.raw(f"[RX]: {resp}")
        
        return resp

    def _verify_connection(self):
        # *VER: Query Version (Manual Sec 3.4.3 - Info Commands)
        resp = self._send("*VER")
        if not resp:
            raise ConnectionError("MAESTRO not responding.")
        log.info(f"MAESTRO Connected: {resp}")

    def _setup_energy_mode(self):
        log.info("Configuring MAESTRO settings...")
        
        # *SSE1: Set Single Shot Energy Mode (Manual Sec 3.4.3 - Measurement Control)
        # 1 = Energy Mode (Joules), 0 = Power Mode (Watts)
        self._send("*SSE1") 
        
        # Set Wavelength
        log.info(f"Setting Wavelength to {self.target_wavelength} nm...")
        
        # *PWC: Set Personal Wavelength Correction (Manual Sec 3.4.3 - Measurement Setup)
        # IMPORTANT: Manual says "The input parameter must have 5 digits."
        # So 1064 must be sent as "*PWC01064". The :05d code does this padding.
        self._send(f"*PWC{int(self.target_wavelength):05d}")
        
        # *GWL: Get Wavelength (Verify it was set correctly)
        wl = self._send("*GWL") 
        log.info(f"MAESTRO Wavelength confirmed: {wl}")

    def start_stream(self):
        log.info("Starting Data Stream...")
        # *CSU: Clear Stream / Stop previous stream (Manual Sec 3.4.3)
        self._send("*CSU") 
        # *CAU: Continuous Acquisition (Manual Sec 3.4.3)
        # This tells the Maestro to start spitting out numbers as fast as it can.
        self._send("*CAU") 

    def stop_stream(self):
        log.info("Stopping Stream...")
        # We send *CSU again to stop the *CAU stream.
        log.raw("[TX]: *CSU") 
        self.ser.write(b'*CSU\r')
        time.sleep(0.1)

    def collect_stream_data(self) -> List[float]:
        """
        Reads all data currently sitting in the buffer.
        This is called AFTER the laser has finished firing.
        """
        log.info("Collecting Buffer Data...")
        data = []
        
        # WHY CHANGE TIMEOUT?
        # We want to read fast. If there is no data left, we want to stop immediately,
        # not wait 2.0 seconds per line.
        self.ser.timeout = 0.1 
        
        while True:
            try:
                line = self.ser.readline().decode('ascii').strip()
                if not line: 
                    break # Buffer is empty, we are done.
                
                # GLASS BOX: Print the raw energy value received
                log.raw(f"[DATA]: {line}")
                
                data.append(float(line))
            except ValueError:
                # Sometimes serial data gets corrupted (e.g., "1.234\x00"). Ignore it.
                log.raw(f"[JUNK]: {line}") 
                continue
            except Exception:
                break
        
        self.ser.timeout = 2.0 # Restore normal safety timeout
        return data

    def close(self):
        """Safely closes the connection."""
        if self.ser and self.ser.is_open:
            self.stop_stream() # Ensure we don't leave it spewing data
            self.ser.close()


class ExperimentHardware:
    """
    Context Manager to ensure hardware connects and disconnects safely.
    Usage: 'with ExperimentHardware(cfg) as hw:'
    
    WHY? If the program crashes in the middle of the 'with' block,
    the '__exit__' function runs AUTOMATICIALLY, ensuring we close ports.
    """
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rotator = None
        self.pulser = None
        self.meter = None
        self.controller = None # Elliptec controller

    def _disable_unused_channels(self, pulser):
        """
        Queries the hardware for all available channels and turns off
        everything except Channel A.
        """
        try:
            # Fallback safety: Blindly turn off 2, 3, 4
            log.info("Disabling unused channels (B, C, D)...")
            pulser.query(':PULSe2:STATe 0') # CHB
            pulser.query(':PULSe3:STATe 0') # CHC
            pulser.query(':PULSe4:STATe 0') # CHD
        except Exception as e:
            log.warning(f"Could not disable some channels (normal for 2-CH units): {e}")

    def __enter__(self):
        """Initialize all hardware connections."""
        try:
            # 1. Motor (Thorlabs Elliptec)
            log.info(f"Initializing Motor on {self.cfg.PORT_MOTOR}...")
            self.controller = elliptec.Controller(self.cfg.PORT_MOTOR)
            self.rotator = elliptec.Rotator(self.controller, address=self.cfg.MOTOR_ADDR)
            self.rotator.home() # Always home the motor to ensure 0 deg is real 0.
            log.info("Motor Homed.")

            # 2. Pulser (Quantum Composers 9200 Series)
            log.info(f"Initializing Pulser on {self.cfg.PORT_PULSER}...")
            self.pulser = qcsapphire.Pulser(self.cfg.PORT_PULSER)
            
            # *RST: Reset to Factory Defaults (QC Manual Page 33 & 41)
            # Why? Ensures no hidden settings from a previous user (like 'Burst Mode') affect us.
            self.pulser.query('*RST') 
            time.sleep(0.5)
            
            # --- SAFETY: Disable unused channels (B, C, D) ---
            self._disable_unused_channels(self.pulser)
            
            # :PULSe0:MODe: Set System Mode (QC Manual Page 37)
            # 'normal' in library = 'NORMal' or 'CONTinuous' in SCPI.
            # This means the T0 timer runs continuously at the set period.
            self.pulser.system.mode('normal')
            
            # :PULSe0:PERiod: Set Period (QC Manual Page 37)
            # Sets the time between T0 pulses (inverse of frequency).
            self.pulser.system.period(self.cfg.pulse_period_s)
            
            # Configure Channel A
            ch = self.pulser.channel('A')
            
            # :PULSe[n]:CMODe: Set Channel Mode (QC Manual Page 39)
            # 'normal' means it fires one pulse for every T0 system pulse.
            ch.mode('normal')
            
            # :PULSe[n]:WIDTh: Set Pulse Width (QC Manual Page 38)
            ch.width(self.cfg.PULSE_WIDTH_S)
            
            # :PULSe[n]:OUTPut:AMPLitude (QC Manual Page 39)
            # We use the raw query here because the library wrapper might vary.
            self.pulser.query(f':PULSE1:OUTPut:AMPLitude {self.cfg.PULSE_VOLTAGE_V}')
            
            # Ensure everything is off initially (Safety First!)
            # :PULSe0:STATe 0 (QC Manual Page 37) -> Disables System
            self.pulser.system.state(0)
            # :PULSe1:STATe 0 (QC Manual Page 38) -> Disables Channel A
            ch.state(0)
            
            log.info("Pulser Ready.")

            # 3. Meter (Gentec Maestro)
            self.meter = GentecMaestro(
                self.cfg.PORT_METER, 
                self.cfg.MAESTRO_BAUD,
                self.cfg.DETECTION_WAVELENGTH
            )
            
            return self

        except Exception as e:
            log.error(f"Hardware Init Failed: {e}")
            self.__exit__(None, None, None) # Force cleanup if init fails
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up all connections, run automatically on exit or crash."""
        log.info("--- Closing Hardware Connections ---")
        
        if self.rotator:
            try:
                log.info("Returning Motor to 0...")
                self.rotator.set_angle(0)
            except Exception as e: log.error(f"Motor cleanup error: {e}")
        
        if self.controller:
            try: self.controller.close_connection()
            except Exception: pass
            
        if self.pulser:
            try:
                # Turn off laser trigger
                # :PULSe0:STATe OFF (QC Manual Page 37)
                self.pulser.system.state(0)
                self.pulser.channel('A').state(0)
                self.pulser.close()
            except Exception as e: log.error(f"Pulser cleanup error: {e}")
            
        if self.meter:
            try: self.meter.close()
            except Exception as e: log.error(f"Meter cleanup error: {e}")


# ============================================================================
# 4. CORE LOGIC (CONTROLLER)
# ============================================================================

class ExperimentController:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.results = []
        self.current_filter = "default"

    def acquire_data_point(self, hw: ExperimentHardware) -> Tuple[float, int, int]:
        """
        The specific dance to take one measurement point.
        Returns (mean_energy, total_pulses_received, valid_pulses_used).
        """
        
        # 1. Start Stream (Commands will be printed to terminal)
        # We start listening BEFORE we fire, so we don't miss the first pulse.
        hw.meter.start_stream()
        
        # 2. Fire Laser
        log.info(f"Firing {self.cfg.NUM_PULSES} pulses ({self.cfg.burst_duration_s:.2f}s)...")
        
        # :PULSe[n]:STATe ON (QC Manual Page 38) -> Enable Channel A Output
        hw.pulser.channel('A').state(1)
        
        # :PULSe0:STATe ON (QC Manual Page 37) -> Start System Timer (T0)
        # This effectively starts the pulse train.
        hw.pulser.system.state(1)
        
        # Wait for the burst to finish + 0.25s padding to be safe
        time.sleep(self.cfg.burst_duration_s + 0.25)
        
        # Turn off laser
        # :PULSe0:STATe OFF -> Stop System Timer
        hw.pulser.system.state(0)
        hw.pulser.channel('A').state(0)
        
        # 3. Stop Stream & Collect (Data lines will be printed to terminal)
        hw.meter.stop_stream()
        raw_data = hw.meter.collect_stream_data()
        
        # 4. Analyze the raw numbers
        return self._analyze(raw_data)

    def _analyze(self, data: List[float]) -> Tuple[float, int, int]:
        """
        Filters the raw data.
        1. Drops the first N pulses (often unstable).
        2. Drops statistical outliers (e.g. cosmic rays or misfires).
        """
        count = len(data)
        if count <= self.cfg.SKIP_FIRST_N:
            return 0.0, count, 0
            
        # Filter warmup pulses
        valid_data = data[self.cfg.SKIP_FIRST_N:]
        
        # Filter outliers (Standard Deviation Method)
        median = np.median(valid_data)
        sigma = np.std(valid_data)
        cutoff = self.cfg.STD_DEV_CUTOFF * sigma
        
        clean_data = [x for x in valid_data if (median - cutoff) <= x <= (median + cutoff)]
        
        if not clean_data:
            return 0.0, count, 0
            
        return np.mean(clean_data), count, len(clean_data)

    def run(self):
        """Main execution flow."""
        
        # Ask for initial filter
        self.current_filter = log.input("Enter STARTING filter name (e.g., 'ND1'): ")
        if not self.current_filter: self.current_filter = "default"

        angles = np.arange(self.cfg.START_ANGLE, 
                           self.cfg.END_ANGLE + self.cfg.STEP_ANGLE, 
                           self.cfg.STEP_ANGLE)
        
        log.info(f"Starting scan: {len(angles)} points.")
        
        try:
            # --- Hardware Context Manager (Connects here, disconnects at end of block) ---
            with ExperimentHardware(self.cfg) as hw:
                
                i = 0
                while i < len(angles):
                    angle = float(angles[i])
                    log.info(f"--- Step {i+1}/{len(angles)}: Angle {angle:.2f} ---")
                    log.indent()

                    # Move Motor
                    hw.rotator.set_angle(angle)
                    time.sleep(self.cfg.MOVE_SETTLE_TIME)
                    
                    # Measurement Loop (allows retry)
                    success = False
                    while not success:
                        # Run the acquire/analyze sequence
                        mean_e, n_total, n_used = self.acquire_data_point(hw)
                        
                        log.info(f"Received {n_total} pulses. Used {n_used}.")
                        log.info(f"Energy: {mean_e:.4e} J")

                        # CHECK 1: Did we get enough data?
                        if n_total < self.cfg.MIN_PULSE_COUNT:
                            log.warning(f"Low pulse count ({n_total}). Threshold is {self.cfg.MIN_PULSE_COUNT}.")
                            log.input("Check hardware (is laser blocked?). Press ENTER to retry this angle...")
                            continue # Restart 'while not success' loop

                        # CHECK 2: Did we get TOO MANY pulses? (Noise check)
                        if n_total > self.cfg.MAX_PULSE_COUNT:
                            log.warning(f"Too many pulses ({n_total} > {self.cfg.MAX_PULSE_COUNT}).")
                            log.warning("Likely reading noise. Check connections/triggering.")
                            log.input("Press ENTER to retry this angle...")
                            continue # Restart 'while not success' loop

                        # CHECK 3: Is the energy too high? (Safety/Saturation check)
                        if mean_e >= self.cfg.POWER_LIMIT_J:
                            log.warning(f"Power Limit Reached! ({mean_e:.2e} >= {self.cfg.POWER_LIMIT_J:.2e})")
                            self._handle_filter_change(hw, angle)
                            
                            # Ask if we should redo this angle with the new filter
                            choice = log.input("Press 1 to CONTINUE to next angle, 2 to REDO this angle: ")
                            if choice == '2':
                                log.info("Redoing measurement...")
                                continue # Restart 'while not success' loop with new filter
                        
                        # If we get here, result is accepted
                        self.results.append({
                            'angle': angle,
                            'filter': self.current_filter,
                            'energy_J': mean_e,
                            'pulses_total': n_total,
                            'pulses_valid': n_used
                        })
                        success = True
                    
                    log.unindent()
                    i += 1 # Move to next angle

        finally:
            # This block runs whether the loop finishes normally, crashes, or is interrupted by the user.
            # It ensures we ALWAYS save whatever data we managed to collect.
            log.info("Experiment sequence ended. Attempting to save data...")
            self._save_data()

    def _handle_filter_change(self, hw, angle):
        """Pauses logic to allow user to change filter."""
        log.info(f"Please change filter. Last angle was {angle}.")
        new_name = ""
        while not new_name:
            new_name = log.input("Enter NEW filter name: ")
        self.current_filter = new_name

    def _save_data(self):
        """Saves results to CSV using pandas."""
        if not self.results:
            log.warning("No data to save.")
            return

        df = pd.DataFrame(self.results)
        
        # Create directory if it doesn't exist
        save_dir = Path(self.cfg.SAVE_DIRECTORY)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Create path
        filepath = save_dir / self.cfg.get_filename()
        
        try:
            df.to_csv(filepath, index=False)
            log.info(f"Successfully saved to:\n    {filepath}")
            print("\n" + df.to_string())
        except Exception as e:
            log.error(f"Failed to save file: {e}")
            print(df.to_string())


# ============================================================================
# 5. MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n========================================")
    print("   AUTOMATED ANGLE SCAN - GENTEC/QC")
    print("========================================")
    
    try:
        config = Config()
        experiment = ExperimentController(config)
        experiment.run()
        
    except KeyboardInterrupt:
        print("\n\nExecution interrupted by User.")
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress ENTER to exit...")