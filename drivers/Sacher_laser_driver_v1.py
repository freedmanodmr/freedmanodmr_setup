import os
import ctypes

DLL_PATH = r"C:\Users\ODMR_user\odmr_python_files\template\src\template\drivers\EposCMD64.dll"

# Add DLL directory
os.add_dll_directory(os.path.dirname(DLL_PATH))

# Load DLL
ctypes.WinDLL(DLL_PATH)

from sachermotor import motor

# Create controller object
mc = motor()

# Connect
if not mc.connect("USB1"):
    raise RuntimeError("Failed to connect to laser")

print("Connected")

maxWl = mc.getWavelengthMinMax()[1]
minWl = mc.getWavelengthMinMax()[0]
centerWl = (maxWl - minWl)/2 + minWl
#getting the center wavelength
#mc.moveToWavelength(centerWl)
#moves to the center wavelength

mc.disconnect()
#disconnects the motor

# Read current wavelength
#wl = mc.getWavelength()
#print(f"Current wavelength: {wl:.4f} nm")

# Move laser
target_wl = 1025.0
print(f"Moving to {target_wl} nm...")
mc.moveToWavelength(target_wl)

# Read back wavelength
print(f"Current wavelength: {mc.getWavelength():.4f} nm")

# Disconnect
mc.disconnect()
print("Disconnected")