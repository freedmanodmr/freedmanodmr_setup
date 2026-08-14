# -*- coding: utf-8 -*-
"""
Created on Mon Jul 13 21:58:03 2026

@author: ODMR_user
"""

import os
import ctypes
from sachermotor import motor

class SacherLaserDriver:
    def __init__(self, dll_path: str, usb_port: str = "USB1"): #USB0 for 920 nm laser and USB1 for 1040 nm 
        # 1. Handle Windows DLL paths securely
        if not os.path.exists(dll_path):
            raise FileNotFoundError(f"DLL not found at: {dll_path}")
        
        os.add_dll_directory(os.path.dirname(dll_path))
        ctypes.WinDLL(dll_path)
        
        # 2. Connect to the motor
        self.mc = motor()
        if not self.mc.connect(usb_port):
            raise ConnectionError(f"Failed to connect to Sacher Motor on {usb_port}")
            
    def get_wl(self):
        return self.mc.getWavelength()

    def move_to_wl(self, wl, high_precision=1, trigger=0):
        # Using the signature from your example 3: moveToWavelength(wl, precision, trigger)
        self.mc.moveToWavelength(wl, high_precision, trigger)

    def get_limits(self):
        # Returns (min_wl, max_wl)
        return self.mc.getWavelengthMinMax()

    def close(self):
        self.mc.disconnect()