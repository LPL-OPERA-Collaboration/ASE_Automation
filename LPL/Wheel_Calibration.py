"""
Wheel Calibration
-------------------------------------------------------------------------
Hardware:
  1. Thorlabs Elliptec (ELLO) Rotation Stage
  2. Quantum Composers Sapphire 9214 Pulse Generator
  3. Gentec MAESTRO Power Meter
"""

import time
import sys
import numpy as np
import pandas as pd
import serial
import elliptec
import qcsapphire
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Dict

# --- Windows Keyboard Handling ---
try:
    import msvcrt
    ON_WINDOWS = True
except ImportError:
    ON_WINDOWS = False
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
    """
    
    # --- Meta ---
    EXPERIMENT_NAME: str = "wheel_calibration"
    # IMPORTANT: Use 'r' before the string to handle Windows backslashes correctly
    SAVE_DIRECTORY: str = r"C:\Users\Equipe_OPAL\Desktop\Kaya\gentec data"

    # --- Connectivity ---
    PORT_MOTOR: str = 'COM6'    # Thorlabs Elliptec
    PORT_PULSER: str = 'COM5'   # Sapphire Generator
    PORT_METER: str = 'COM7'    # Gentec Maestro
    
    # --- Hardware Settings ---
    MOTOR_ADDR: str = '0'           # Standard address for single Elliptec motor
    MAESTRO_BAUD: int = 115200      # Fixed baud rate for Gentec Serial
    DETECTION_WAVELENGTH: int = 337 # nm (Used by Maestro)
    
    # --- Scan Logic ---
    START_ANGLE: float = 60.0
    END_ANGLE: float = 300.0
    STEP_ANGLE: float = 5.0
    MOVE_SETTLE_TIME: float = 0.5   # Seconds to wait after motor stops moving
    
    # --- Laser/Pulse Logic ---
    NUM_PULSES: int = 50            # How many shots to fire per measurement
    PULSE_RATE_HZ: float = 10.0
    PULSE_WIDTH_S: float = 5e-6
    PULSE_VOLTAGE_V: float = 5.0
    
    # --- Data Analysis ---
    SKIP_FIRST_N: int = 5           # Ignore first N pulses (often unstable)
    POWER_LIMIT_J: float = 60e-9    # Safety limit: Pause if Energy > 60 nJ
    MIN_PULSE_COUNT: int = 35       # If fewer pulses detected, assume laser misfire or bad detection
    STD_DEV_CUTOFF: float = 3.0     # Statistical outlier removal (3 Sigma)

    # --- Filter Logic (Strict Validation) ---
    # Dictionary mapping User Input Key -> OD Value
    # Logic: If user types '3', we treat it as OD 3.163
    # Used for calculating 'energy_corrected_J' at the end.
    VALID_FILTERS: Dict[str, float] = field(default_factory=lambda: {
        '0': 0.0,
        '1': 1.001,
        '3': 3.163
    })

    @property
    def MAX_PULSE_COUNT(self) -> int:
        # If the meter detects significantly more pulses than we fired,
        # it is likely picking up electrical noise or ambient light.
        return self.NUM_PULSES + 10 

    @property
    def pulse_period_s(self) -> float:
        return 1.0 / self.PULSE_RATE_HZ if self.PULSE_RATE_HZ > 0 else 0.1

    @property
    def burst_duration_s(self) -> float:
        return self.pulse_period_s * self.NUM_PULSES

    def get_filename(self) -> str:
        """Generates a unique filename based on time and scan settings."""
        timestamp_str = time.strftime("%Y%m%d_%H%M%S") 
        s = int(self.START_ANGLE) if self.START_ANGLE.is_integer() else self.START_ANGLE
        e = int(self.END_ANGLE) if self.END_ANGLE.is_integer() else self.END_ANGLE
        st = int(self.STEP_ANGLE) if self.STEP_ANGLE.is_integer() else self.STEP_ANGLE
        return f"{timestamp_str}_{self.EXPERIMENT_NAME}_{s}_to_{e}_by_{st}.csv"


# ============================================================================
# 2. UTILITIES & LOGGING
# ============================================================================

class ExperimentLogger:
    """
    A simple wrapper for 'print' that handles indentation levels.
    Makes the console output easier to read during a long scan.
    """
    def __init__(self):
        self.level = 0
        
    def indent(self): self.level += 1
    def unindent(self): 
        if self.level > 0: self.level -= 1
        
    def info(self, msg: str):
        print(f"{'    ' * self.level}{msg}")
        sys.stdout.flush()

    def warning(self, msg: str):
        print(f"\n{'    ' * self.level}*** WARNING: {msg} ***")
        sys.stdout.flush()

    def error(self, msg: str):
        print(f"\n{'    ' * self.level}!!! ERROR: {msg} !!!")
        sys.stdout.flush()

    def raw(self, msg: str):
        print(f"{'    ' * (self.level + 1)}{msg}")
        sys.stdout.flush()

    def input(self, prompt: str) -> str:
        if ON_WINDOWS:
            while msvcrt.kbhit(): msvcrt.getch()
        return input(f"{'    ' * self.level}>>> {prompt}")

log = ExperimentLogger()


# ============================================================================
# 3. HARDWARE WRAPPERS
# ============================================================================

class GentecMaestro:
    """
    Custom driver for the Gentec MAESTRO Power Meter.
    Uses basic Serial commands based on the Gentec ASCII protocol.
    """
    def __init__(self, port: str, baud: int, wavelength: int):
        log.info(f"Connecting to MAESTRO on {port}...")
        self.target_wavelength = wavelength
        self.ser = serial.Serial(port, baudrate=baud, timeout=2.0)
        self._verify_connection()
        self._setup_energy_mode()

    def _send(self, cmd: str) -> str:
        """Sends a command to the meter and waits for a response."""
        self.ser.flushInput()
        # log.raw(f"[TX]: {cmd}") # Commented out to reduce noise
        self.ser.write((cmd + '\r').encode())
        time.sleep(0.2)
        resp = self.ser.readline().decode('ascii').strip()
        # log.raw(f"[RX]: {resp}")
        return resp

    def _verify_connection(self):
        """Asks the device for its version (*VER) to ensure it's listening."""
        resp = self._send("*VER")
        if not resp: raise ConnectionError("MAESTRO not responding.")
        log.info(f"MAESTRO Connected: {resp}")

    def _setup_energy_mode(self):
        """Configures the meter for Energy measurement (Joules)."""
        self._send("*SSE1") 
        self._send(f"*PWC{int(self.target_wavelength):05d}")
        
    def start_stream(self):
        """Tells the meter to start sending data points to the USB buffer."""
        self._send("*CSU") 
        self._send("*CAU") 

    def stop_stream(self):
        """Stops the data stream."""
        self.ser.write(b'*CSU\r')
        time.sleep(0.1)

    def collect_stream_data(self) -> List[float]:
        """Reads all data currently sitting in the Serial buffer."""
        data = []
        self.ser.timeout = 0.1 
        while True:
            try:
                line = self.ser.readline().decode('ascii').strip()
                if not line: break
                data.append(float(line))
            except: continue
        self.ser.timeout = 2.0 
        return data

    def close(self):
        if self.ser and self.ser.is_open:
            self.stop_stream()
            self.ser.close()


class ExperimentHardware:
    """
    Context Manager for Hardware.
    
    NOTE:
    Using the 'with ExperimentHardware() as hw:' pattern ensures that
    __exit__ is ALWAYS called, even if the script crashes.
    This guarantees the Laser is turned OFF and ports are released safely.
    """
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rotator = None
        self.pulser = None
        self.meter = None
        self.controller = None

    def __enter__(self):
        try:
            # 1. Motor
            log.info(f"Initializing Motor on {self.cfg.PORT_MOTOR}...")
            self.controller = elliptec.Controller(self.cfg.PORT_MOTOR)
            self.rotator = elliptec.Rotator(self.controller, address=self.cfg.MOTOR_ADDR)
            self.rotator.home()
            
            # 2. Pulser
            log.info(f"Initializing Pulser on {self.cfg.PORT_PULSER}...")
            self.pulser = qcsapphire.Pulser(self.cfg.PORT_PULSER)
            self.pulser.query('*RST') 
            time.sleep(0.5)
            self.pulser.system.mode('normal')
            self.pulser.system.period(self.cfg.pulse_period_s)
            ch = self.pulser.channel('A')
            ch.mode('normal')
            ch.width(self.cfg.PULSE_WIDTH_S)
            self.pulser.query(f':PULSE1:OUTPut:AMPLitude {self.cfg.PULSE_VOLTAGE_V}')
            self.pulser.system.state(0)
            ch.state(0)
            
            # 3. Meter
            self.meter = GentecMaestro(self.cfg.PORT_METER, self.cfg.MAESTRO_BAUD, self.cfg.DETECTION_WAVELENGTH)
            
            return self
        except Exception as e:
            log.error(f"Hardware Init Failed: {e}")
            self.__exit__(None, None, None)
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup routine called automatically at end of 'with' block."""
        log.info("--- Closing Hardware Connections ---")
        if self.rotator: self.rotator.set_angle(0)
        if self.controller: self.controller.close_connection()
        if self.pulser:
            self.pulser.system.state(0)
            self.pulser.close()
        if self.meter: self.meter.close()


# ============================================================================
# 4. CORE LOGIC (CONTROLLER)
# ============================================================================

class ExperimentController:
    """
    Orchestrates the experiment:
    1. Moves Motor
    2. Controls Laser firing
    3. Reads Meter
    4. Analyzes Data
    5. Saves to CSV
    """
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.results = []
        self.current_filter_key = "0" # Stores '0', '1', or '3'

    def _get_valid_filter_input(self) -> str:
        """
        Forces the user to enter a key present in the Config.
        Loops indefinitely until a valid key ('0', '1', '3') is entered.
        """
        valid_keys = list(self.cfg.VALID_FILTERS.keys())
        prompt = f"Enter Filter ID {valid_keys} (0=None, 1=OD1, 3=OD3): "
        
        while True:
            choice = log.input(prompt).strip()
            if choice in valid_keys:
                return choice
            log.warning(f"Invalid input '{choice}'. You MUST enter one of: {valid_keys}")

    def acquire_data_point(self, hw: ExperimentHardware) -> Tuple[float, int, int]:
        
        """
        Synchronizes the measurement sequence.
        Returns: (Average Energy, Total Pulses Detected, Valid Pulses Used)
        """
        # 1. Start listening to the power meter
        hw.meter.start_stream()

        # 2. Fire the laser burst
        log.info(f"Firing {self.cfg.NUM_PULSES} pulses...")
        hw.pulser.channel('A').state(1)
        hw.pulser.system.state(1)
        # Wait for the exact duration of the pulse train + buffer
        time.sleep(self.cfg.burst_duration_s + 0.25)

        hw.pulser.system.state(0)
        hw.pulser.channel('A').state(0)

        # 3. Stop listening and download data
        hw.meter.stop_stream()
        raw_data = hw.meter.collect_stream_data()

        # 4. Calculate statistics
        return self._analyze(raw_data)

    def _analyze(self, data: List[float]) -> Tuple[float, int, int]:
        """
        Statistical Processing:
        1. Skips first N pulses (instability).
        2. Calculates Median and Standard Deviation.
        3. Removes outliers outside of median +/- (3 * Sigma).
        """
        count = len(data)
        if count <= self.cfg.SKIP_FIRST_N: return 0.0, count, 0
            
        valid_data = data[self.cfg.SKIP_FIRST_N:]
        median = np.median(valid_data)
        sigma = np.std(valid_data)
        cutoff = self.cfg.STD_DEV_CUTOFF * sigma
        clean_data = [x for x in valid_data if (median - cutoff) <= x <= (median + cutoff)]
        
        if not clean_data: return 0.0, count, 0
        return np.mean(clean_data), count, len(clean_data)

    def run(self):
        """Main Experiment Loop."""
        log.info("Select STARTING filter.")
        self.current_filter_key = self._get_valid_filter_input()
        
        current_od = self.cfg.VALID_FILTERS[self.current_filter_key]
        log.info(f"Starting with Filter '{self.current_filter_key}' (OD={current_od})")

        angles = np.arange(self.cfg.START_ANGLE, 
                           self.cfg.END_ANGLE + self.cfg.STEP_ANGLE, 
                           self.cfg.STEP_ANGLE)
        
        log.info(f"Starting scan: {len(angles)} points.")
        
        try:
            with ExperimentHardware(self.cfg) as hw:
                i = 0
                while i < len(angles):
                    angle = float(angles[i])
                    log.info(f"--- Step {i+1}/{len(angles)}: Angle {angle:.2f} ---")
                    log.indent()

                    hw.rotator.set_angle(angle)
                    time.sleep(self.cfg.MOVE_SETTLE_TIME)
                    
                    success = False
                    while not success:
                        mean_e, n_total, n_used = self.acquire_data_point(hw)
                        log.info(f"Energy (Raw): {mean_e:.4e} J | Pulses: {n_used}/{n_total}")

                        # Quality Checks
                        if n_total < self.cfg.MIN_PULSE_COUNT:
                            log.warning(f"Low pulse count ({n_total}). Check laser.")
                            log.input("Press ENTER to retry...")
                            continue 
                        
                        if n_total > self.cfg.MAX_PULSE_COUNT:
                            log.warning(f"Too many pulses ({n_total}). Noise detected.")
                            log.input("Press ENTER to retry...")
                            continue 

                        # Power Limit Check
                        if mean_e >= self.cfg.POWER_LIMIT_J:
                            log.warning(f"Power Limit ({self.cfg.POWER_LIMIT_J:.2e} J) Exceeded!")
                            self._handle_filter_change(angle)
                            
                            choice = log.input("Retry this angle with new filter? (y/n): ").lower()
                            if choice == 'y':
                                log.info("Redoing measurement...")
                                continue
                        
                        self.results.append({
                            'angle': angle,
                            'filter_id': self.current_filter_key,
                            'energy_J': mean_e,
                            'pulses_valid': n_used
                        })
                        success = True
                    
                    log.unindent()
                    i += 1 

        finally:
            log.info("Scan finished/interrupted. Saving data...")
            self._save_data()

    def _handle_filter_change(self, angle):
        """Pauses execution and demands a valid filter input from user."""
        log.info(f"PAUSED at Angle {angle:.2f}. Change filter now.")
        self.current_filter_key = self._get_valid_filter_input()

    def _save_data(self):
        """Compiles results, applies mathematical corrections, and saves CSV."""
        if not self.results:
            log.warning("No data to save.")
            return

        df = pd.DataFrame(self.results)
        
        # --- AUTO CORRECTION LOGIC ---
        log.info("Applying OD Corrections...")
        
        # 1. Lookup OD Value based on the user's input key
        # df['filter_id'] contains '0', '1', '3'
        # We map these to actual OD values using the config dictionary
        df['od_value'] = df['filter_id'].map(self.cfg.VALID_FILTERS)
        
        # 2. Calculate Correction Factor: 10^(OD)
        # Example: OD 1 = 10x attenuation, so we multiply read energy by 10.
        df['correction_factor'] = 10 ** df['od_value']
        
        # 3. Calculate Corrected Energy
        df['energy_corrected_J'] = df['energy_J'] * df['correction_factor']
        
        # -----------------------------
        
        save_dir = Path(self.cfg.SAVE_DIRECTORY)
        save_dir.mkdir(parents=True, exist_ok=True)
        filepath = save_dir / self.cfg.get_filename()
        
        try:
            df.to_csv(filepath, index=False)
            log.info(f"Successfully saved to:\n    {filepath}")
            print("\n" + df[['angle', 'filter_id', 'energy_J', 'energy_corrected_J']].to_string())
        except Exception as e:
            log.error(f"Failed to save file: {e}")


# ============================================================================
# 5. MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print("\n========================================")
    print("   AUTOMATED ANGLE SCAN   ")
    print("========================================")
    
    try:
        config_obj = Config()
        experiment = ExperimentController(config_obj)
        experiment.run()
        
    except KeyboardInterrupt:
        print("\n\nExecution interrupted by User.")
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    input("\nPress ENTER to exit...")