import ctypes
import os

# --- Configuration ---
PMA_DLL_PATH = r"C:\Program Files (x86)\U6039-01 Ver4.0.3 for PMA\DVPMA32.dll"
SPECTRO_DLL_PATH = r"C:\Program Files (x86)\U6039-01 Ver4.0.3 for PMA\Acton32US.dll"

PMA_DEVICE_ID = 5
SPECTRO_DEVICE_ID = 0

# Define the "invalid" handle value we discovered
INVALID_HANDLE_VALUE = 65535

# --- Global Handles ---
pma_handle = 0
spectro_handle = 0

try:
    # --- 1. Load Both Driver DLLs ---
    print(f"Loading {PMA_DLL_PATH}...")
    pma_dll = ctypes.WinDLL(PMA_DLL_PATH)
    
    print(f"Loading {SPECTRO_DLL_PATH}...")
    spectro_dll = ctypes.WinDLL(SPECTRO_DLL_PATH)
    
    print("--- DLLs loaded successfully ---\n")

    # --- 2. Initialize Spectrograph (Acton32US.dll) ---
    print(f"Attempting to open Spectrograph (Device {SPECTRO_DEVICE_ID})...")
    
    spectro_handle = spectro_dll.DEV_OpenEx(SPECTRO_DEVICE_ID, None, None)
    
    # NEW, CORRECTED LOGIC
    if spectro_handle != 0 and spectro_handle != INVALID_HANDLE_VALUE:
        print(f"  [SUCCESS] Spectrograph connected. Real Handle: {spectro_handle}")
    else:
        print(f"  [FAILURE] Failed to connect to spectrograph. Code: {spectro_handle}")
        spectro_handle = 0 # Set to 0 so 'finally' block doesn't try to close it

    # --- 3. Initialize Detector (DVPMA32.dll) ---
    print(f"\nAttempting to open PMA Detector (Device {PMA_DEVICE_ID})...")
    
    pma_handle = pma_dll.DEV_OpenEx(PMA_DEVICE_ID, None, None)
    
    # NEW, CORRECTED LOGIC
    if pma_handle != 0 and pma_handle != INVALID_HANDLE_VALUE:
        print(f"  [SUCCESS] PMA Detector connected. Real Handle: {pma_handle}")
    else:
        print(f"  [FAILURE] Failed to connect to PMA Detector. Code: {pma_handle}")
        pma_handle = 0 # Set to 0 for 'finally' block

    if pma_handle == 0 or spectro_handle == 0:
        raise Exception("Could not connect to one or more devices.")

    print("\n--- All devices connected successfully! ---")

except Exception as e:
    print(f"\n[ERROR] An error occurred: {e}")

finally:
    # --- 4. Clean Up and Close (CRITICAL) ---
    print("\n--- Cleaning up... ---")
    if spectro_handle != 0: # This check now works
        print(f"Closing Spectrograph (Handle {spectro_handle})...")
        spectro_dll.DEV_CloseEx(spectro_handle)
    
    if pma_handle != 0: # This check now works
        print(f"Closing PMA Detector (Handle {pma_handle})...")
        pma_dll.DEV_CloseEx(pma_handle)
        
    print("--- Cleanup complete. ---")