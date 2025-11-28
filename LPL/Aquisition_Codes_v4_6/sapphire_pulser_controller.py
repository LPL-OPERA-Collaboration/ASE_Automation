import qcsapphire
import time
import logging
from aquisition_config import (
    PULSER_COM_PORT, PULSE_PERIOD_S, PULSER_PULSE_WIDTH_S, PULSE_VOLTAGE_V
)

class SapphirePulserController:
    """
    Controller class to control the Quantum Composers Sapphire 9214 Pulse Generator 
    via the 'qcsapphire' library.
    
    - Channel A: Connected to the Laser Trigger input.
    - Channels B/C/D: Unused (and explicitly disabled).
    
    LOGIC:
    The controller sets up a continuous pulse train (Period/Width), but keeps
    the "System Output" disabled until the main script calls set_state(1).

    Encapsulates initialization, configuration, and state control.
    """
    def __init__(self, logger):
        self.logger = logger
        self.pulser = None
        self.connected = False
        
    def connect(self):
        """
        Connects to the pulser, performs hardware reset, and sets initial 
        pulse configuration parameters (period, width, voltage).
        """
        self.logger.info(f"\n--- Connecting to Sapphire Pulser on {PULSER_COM_PORT} ---")
        try:
            # The 'qcsapphire' object is created here
            self.pulser = qcsapphire.Pulser(PULSER_COM_PORT)
            self.logger.info(f"Connected to: {self.pulser.query('*IDN?')}")
            
            self.logger.info("Resetting and configuring pulser...")
            self.pulser.query('*RST')
            time.sleep(1) 
            self.pulser.system.mode('normal')
            self.pulser.system.period(PULSE_PERIOD_S)
            
            ch_A = self.pulser.channel('A')
            ch_A.mode('normal')
            ch_A.width(PULSER_PULSE_WIDTH_S)
            ch_A.delay(0)
            self.pulser.query(f':PULSE1:OUTPut:AMPLitude {PULSE_VOLTAGE_V}')
            
            # Ensure unused channels are off and system is initially disabled
            self.pulser.channel('B').state(0)
            self.pulser.channel('C').state(0)
            self.pulser.channel('D').state(0)
            self.pulser.system.state(0)
            ch_A.state(0)
            
            self.logger.info("Pulser initialized and ready.")
            self.connected = True
            return True
            
        except Exception as e:
            self.logger.exception(f"FATAL ERROR connecting/initializing Sapphire Pulser: {e}")
            self.connected = False
            raise

    def set_state(self, state: int):
        """
        Sets the global system state and Channel A state.
        
        state: 1 for ON, 0 for OFF.
        """
        if not self.connected:
            self.logger.warning("Attempted to set pulser state, but controller is not connected.")
            return

        state_str = "ON" if state == 1 else "OFF"
        self.logger.debug(f"Setting pulser system and channel A state to {state_str}")
        
        try:
            # We set Channel A state first, then the master system state
            self.pulser.channel('A').state(state)
            self.pulser.system.state(state)
        except Exception as e:
            self.logger.error(f"Error setting pulser state to {state_str}: {e}")
            raise # Re-raise error to be handled by main script logic
            
    def close(self):
        """Stops the pulser and closes the serial connection."""
        if self.pulser and self.connected:
            self.logger.info("   Stopping pulser system...")
            try:
                self.pulser.system.state(0)
                self.pulser.channel('A').state(0)
                self.pulser.close()
                self.logger.info("   Pulser connection closed.")
            except Exception as e:
                self.logger.warning(f"   Error closing pulser connection: {e}")
            self.connected = False
        else:
            self.logger.info("   Pulser controller was not connected or already closed.")