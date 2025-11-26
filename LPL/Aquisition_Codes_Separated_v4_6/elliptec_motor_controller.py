import elliptec
import logging
import time
from aquisition_config import (
    MOTOR_COM_PORT, MOTOR_ADDRESS, MOTOR_TIMEOUT_S
)

class ElliptecMotorController:
    """
    Controller class for the Thorlabs Elliptec (ELLO) rotation stage.
    
    Encapsulates connection, homing, movement, and cleanup using the 
    'elliptec' library.
    """
    def __init__(self, logger):
        self.logger = logger
        self.elliptec_controller = None
        self.rotator = None
        self.connected = False
        
    def connect(self):
        """Connects to the Elliptec motor via serial port."""
        self.logger.info(f"\n--- Connecting to Elliptec Motor on {MOTOR_COM_PORT} ---")
        try:
            # Use imported constants for connection
            self.elliptec_controller = elliptec.Controller(MOTOR_COM_PORT)
            self.elliptec_controller.s.timeout = MOTOR_TIMEOUT_S
            self.rotator = elliptec.Rotator(self.elliptec_controller, address=MOTOR_ADDRESS)
            self.logger.info("Elliptec motor connected.")
            self.connected = True
            return True
        except Exception as e:
            self.logger.exception(f"FATAL ERROR connecting/initializing Elliptec Motor: {e}")
            self.connected = False
            raise
            
    def home(self):
        """Homes the Elliptec motor to its zero-stop position."""
        if not self.connected:
            self.logger.warning("Attempted to home motor, but controller is not connected.")
            return

        self.logger.info(f"\n--- Homing Elliptec Motor (returning to zero-stop) ---")
        try:
            # Use imported constant for timeout via controller setup
            self.rotator.home() 
            self.logger.info("Elliptec motor homing complete.")
        except Exception as e:
            self.logger.error(f"Error during Elliptec homing: {e}")
            raise
            
    def set_angle(self, target_angle):
        """Moves the rotation stage to the target angle."""
        if not self.connected:
            self.logger.warning("Attempted to move motor, but controller is not connected.")
            return

        try:
            self.logger.info(f"   Moving rotator to {target_angle} deg...")
            self.rotator.set_angle(target_angle)
            current_pos = self.rotator.get_angle()
            self.logger.info(f"   Arrived at: {current_pos} deg")
            return current_pos
        except Exception as e:
            self.logger.error(f"Error moving Elliptec motor to {target_angle}: {e}")
            raise

    def close(self):
        """Closes the serial connection to the Elliptec motor."""
        if self.elliptec_controller and self.connected:
            try:
                self.logger.info("   Closing Elliptec connection...")
                self.elliptec_controller.close_connection()
                self.logger.info("   Elliptec connection closed.")
            except Exception as e:
                self.logger.warning(f"   Error closing Elliptec: {e}")
            self.connected = False
        else:
            self.logger.info("   Elliptec controller was not connected or already closed.")