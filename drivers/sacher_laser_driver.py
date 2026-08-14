# -*- coding: utf-8 -*-
"""
Created on Mon Jul 13 21:58:03 2026

@author: ODMR_user
"""

import os
import ctypes
from sachermotor import motor

DLL_PATH = r"C:\Users\ODMR_user\odmr_python_files\template\src\template\drivers\EposCMD64.dll"
USB_PORT_DEFAULT = "USB1"


# Add DLL directory once
os.add_dll_directory(os.path.dirname(DLL_PATH))


class SacherLaserDriver:
    def __init__(self, usb_port="USB1"):

        self.motor = motor()

        if not self.motor.connect(usb_port):
            raise ConnectionError(
                f"Failed to connect to Sacher Motor on {usb_port}"
            )

        self.usb_port = usb_port
        self.connected = True


    def get_wl(self):
        return self.motor.getWavelength()


    def move_to_wl(self, wl, high_precision=1, trigger=0):
        self.motor.moveToWavelength(wl, high_precision, trigger)


    def get_limits(self):
        return self.motor.getWavelengthMinMax()


    def close(self):
        if self.connected:
            self.motor.disconnect()
            self.connected = False


    def __del__(self):
        self.close()