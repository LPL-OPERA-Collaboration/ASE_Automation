"""
MASTER EXPERIMENT CONTROLLER (GLASS BOX VERSION)
-------------------------------------------------------------------------
Hardware:
  1. Thorlabs Elliptec (ELLO) Rotation Stage
  2. Quantum Composers Sapphire 9214 Pulse Generator
  3. Gentec MAESTRO Power Meter

Refactored for: Visibility. 
All serial communication is printed to the terminal so you can see the "heartbeat" of the experiment.
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
    """Global experiment configuration."""
    
    # --- Meta ---
    EXPERIMENT_NAME: str = "wheel_calibration"
    SAVE_DIRECTORY: str = r"C:\Users\Equipe_OPAL\Desktop\Kaya\gentec data"

    # --- Connectivity ---
    PORT_MOTOR: str = 'COM6'
    PORT_PULSER: str = 'COM5'
    PORT_METER: str = 'COM7'
    
    # --- Hardware Settings ---
    MOTOR_ADDR: str = '0'
    MAESTRO_BAUD: int = 115200
    DETECTION_WAVELENGTH: int = 337 # <--- Detection Wavelength (nm)
    
    # --- Scan Logic ---
    START_ANGLE: float = 40.0
    END_ANGLE: float = 50.0
    STEP_ANGLE: float = 5.0
    MOVE_SETTLE_TIME: float = 0.5
    
    # --- Laser/Pulse Logic ---
    NUM_PULSES: int = 50
    PULSE_RATE_HZ: float = 10.0
    PULSE_WIDTH_S: float = 5e-6
    PULSE_VOLTAGE_V: float = 5.0
    
    # --- Data Analysis ---
    SKIP_FIRST_N: int = 5        # Warmup pulses to ignore
    POWER_LIMIT_J: float = 60e-9 # 60 nJ Safety Threshold
    MIN_PULSE_COUNT: int = 35    # Minimum valid pulses to accept a reading
    STD_DEV_CUTOFF: float = 3.0  # Sigma for outlier rejection

    @property
    def pulse_period_s(self) -> float:
        return 1.0 / self.PULSE_RATE_HZ if self.PULSE_RATE_HZ > 0 else 0.1

    @property
    def burst_duration_s(self) -> float:
        return self.pulse_period_s * self.NUM_PULSES

    def get_filename(self) -> str:
        """Generates a descriptive filename."""
        date_str = time.strftime("%Y%m%d")
        # Format numbers to be integers if they have no decimal part (e.g., 40.0 -> 40)
        s = int(self.START_ANGLE) if self.START_ANGLE.is_integer() else self.START_ANGLE
        e = int(self.END_ANGLE) if self.END_ANGLE.is_integer() else self.END_ANGLE
        st = int(self.STEP_ANGLE) if self.STEP_ANGLE.is_integer() else self.STEP_ANGLE
        
        return f"{date_str}_{self.EXPERIMENT_NAME}_{s}_to_{e}_by_{st}.csv"


# ============================================================================
# 2. UTILITIES & LOGGING
# ============================================================================

class ExperimentLogger:
    """Handles printing to console with indentation management."""
    def __init__(self):
        self.level = 0
        
    def indent(self):
        self.level += 1
        
    def unindent(self):
        if self.level > 0: self.level -= 1
        
    def info(self, msg: str):
        prefix = "    " * self.level
        print(f"{prefix}{msg}")
        sys.stdout.flush()

    def warning(self, msg: str):
        prefix = "    " * self.level
        print(f"\n{prefix}*** WARNING: {msg} ***")
        sys.stdout.flush()

    def error(self, msg: str):
        prefix = "    " * self.level
        print(f"\n{prefix}!!! ERROR: {msg} !!!")
        sys.stdout.flush()

    def raw(self, msg: str):
        """Prints raw hardware comms with deeper indentation."""
        prefix = "    " * (self.level + 1)
        print(f"{prefix}{msg}")
        sys.stdout.flush()

    def input(self, prompt: str) -> str:
        """Clear buffer before asking for input."""
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
    'Glass Box' design: Prints all serial traffic to console.
    """
    def __init__(self, port: str, baud: int, wavelength: int):
        log.info(f"Connecting to MAESTRO on {port}...")
        self.target_wavelength = wavelength
        self.ser = serial.Serial(port, baudrate=baud, timeout=2.0)
        self._verify_connection()
        self._setup_energy_mode()

    def _send(self, cmd: str) -> str:
        """Sends a command and prints the TX/RX interaction."""
        self.ser.flushInput()
        
        # GLASS BOX: Show what we are sending
        log.raw(f"[TX]: {cmd}")
        
        self.ser.write((cmd + '\r').encode())
        time.sleep(0.2)
        
        resp = self.ser.readline().decode('ascii').strip()
        
        # GLASS BOX: Show what we received
        log.raw(f"[RX]: {resp}")
        
        return resp

    def _verify_connection(self):
        resp = self._send("*VER")
        if not resp:
            raise ConnectionError("MAESTRO not responding.")
        log.info(f"MAESTRO Connected: {resp}")

    def _setup_energy_mode(self):
        log.info("Configuring MAESTRO settings...")
        self._send("*SSE1") # Energy mode
        
        # Set Wavelength
        log.info(f"Setting Wavelength to {self.target_wavelength} nm...")
        self._send(f"*PWC{int(self.target_wavelength):05d}") # Format *PWC01064
        
        # Verify Wavelength
        wl = self._send("*GWL") # Get Wavelength
        log.info(f"MAESTRO Wavelength confirmed: {wl}")

    def start_stream(self):
        log.info("Starting Data Stream...")
        self._send("*CSU") # Clear stream
        self._send("*CAU") # Start stream

    def stop_stream(self):
        log.info("Stopping Stream...")
        # We don't use _send here because we don't want to wait for a response line yet
        log.raw("[TX]: *CSU") 
        self.ser.write(b'*CSU\r')
        time.sleep(0.1)

    def collect_stream_data(self) -> List[float]:
        """Reads the buffer until empty and prints every line."""
        log.info("Collecting Buffer Data...")
        data = []
        self.ser.timeout = 0.1 # Fast reads
        
        while True:
            try:
                line = self.ser.readline().decode('ascii').strip()
                if not line: 
                    break # Buffer empty
                
                # GLASS BOX: Print the raw data line
                log.raw(f"[DATA]: {line}")
                
                data.append(float(line))
            except ValueError:
                log.raw(f"[JUNK]: {line}") # Show if we get garbage
                continue
            except Exception:
                break
        
        self.ser.timeout = 2.0 # Restore normal timeout
        return data

    def close(self):
        if self.ser and self.ser.is_open:
            self.stop_stream()
            self.ser.close()


class ExperimentHardware:
    """Context Manager to ensure hardware connects and disconnects safely."""
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.rotator = None
        self.pulser = None
        self.meter = None
        self.controller = None # Elliptec controller

    def __enter__(self):
        """Initialize all hardware."""
        try:
            # 1. Motor
            log.info(f"Initializing Motor on {self.cfg.PORT_MOTOR}...")
            self.controller = elliptec.Controller(self.cfg.PORT_MOTOR)
            self.rotator = elliptec.Rotator(self.controller, address=self.cfg.MOTOR_ADDR)
            self.rotator.home()
            log.info("Motor Homed.")

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
            
            # Ensure everything is off
            self.pulser.system.state(0)
            ch.state(0)
            log.info("Pulser Ready.")

            # 3. Meter
            self.meter = GentecMaestro(
                self.cfg.PORT_METER, 
                self.cfg.MAESTRO_BAUD,
                self.cfg.DETECTION_WAVELENGTH
            )
            
            return self

        except Exception as e:
            log.error(f"Hardware Init Failed: {e}")
            self.__exit__(None, None, None) # Force cleanup
            raise e

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up all connections."""
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
        """Fires laser, reads meter, processes data. Returns (mean, total_pulses, good_pulses)."""
        
        # 1. Start Stream (Commands will be printed)
        hw.meter.start_stream()
        
        # 2. Fire Laser
        log.info(f"Firing {self.cfg.NUM_PULSES} pulses ({self.cfg.burst_duration_s:.2f}s)...")
        hw.pulser.channel('A').state(1)
        hw.pulser.system.state(1)
        
        time.sleep(self.cfg.burst_duration_s + 0.25)
        
        hw.pulser.system.state(0)
        hw.pulser.channel('A').state(0)
        
        # 3. Stop Stream & Collect (Data lines will be printed)
        hw.meter.stop_stream()
        raw_data = hw.meter.collect_stream_data()
        
        # 4. Analyze
        return self._analyze(raw_data)

    def _analyze(self, data: List[float]) -> Tuple[float, int, int]:
        count = len(data)
        if count <= self.cfg.SKIP_FIRST_N:
            return 0.0, count, 0
            
        # Filter warmup pulses
        valid_data = data[self.cfg.SKIP_FIRST_N:]
        
        # Filter outliers
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
        
        # --- Hardware Context Manager ---
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
                    mean_e, n_total, n_used = self.acquire_data_point(hw)
                    
                    log.info(f"Received {n_total} pulses. Used {n_used}.")
                    log.info(f"Energy: {mean_e:.4e} J")

                    # Check Data Quality
                    if n_total < self.cfg.MIN_PULSE_COUNT:
                        log.warning(f"Low pulse count ({n_total}). Threshold is {self.cfg.MIN_PULSE_COUNT}.")
                        log.input("Check hardware. Press ENTER to retry this angle...")
                        continue # Retry loop

                    # Check Power Threshold
                    if mean_e >= self.cfg.POWER_LIMIT_J:
                        log.warning(f"Power Limit Reached! ({mean_e:.2e} >= {self.cfg.POWER_LIMIT_J:.2e})")
                        self._handle_filter_change(hw, angle)
                        
                        # Ask if we should redo this angle with the new filter
                        choice = log.input("Press 1 to CONTINUE to next angle, 2 to REDO this angle: ")
                        if choice == '2':
                            log.info("Redoing measurement...")
                            continue # Retry loop with new filter
                    
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
                i += 1 # Next angle

        self._save_data()

    def _handle_filter_change(self, hw, angle):
        """Pauses logic to allow user to change filter."""
        log.info(f"Please change filter. Last angle was {angle}.")
        new_name = ""
        while not new_name:
            new_name = log.input("Enter NEW filter name: ")
        self.current_filter = new_name

    def _save_data(self):
        """Saves results to CSV."""
        if not self.results:
            log.warning("No data to save.")
            return

        df = pd.DataFrame(self.results)
        
        # Create directory
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
    print("   AUTOMATED ANGLE SCAN for CALLIBRATION - GENTEC/QC")
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