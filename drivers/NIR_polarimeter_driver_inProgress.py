# -*- coding: utf-8 -*-
"""
Created on Wed Aug  5 01:01:14 2026

@author: ODMR_user
"""

import pyvisa

RESOURCE = "USB0::0x1313::0x8031::M01298370::INSTR"

rm = pyvisa.ResourceManager()
pax = None

try:
    pax = rm.open_resource(RESOURCE)

    pax.timeout = 10_000
    pax.read_termination = "\n"
    pax.write_termination = "\n"

    print("ID:", pax.query("*IDN?").strip())

    wavelength_m = float(pax.query("SENS:CORR:WAV?"))
    print("Wavelength:", wavelength_m * 1e9, "nm")

    mode = pax.query("SENS:CALC:MODE?").strip()
    print("Measurement mode:", mode)

    rotation = pax.query("INP:ROT:STAT?").strip()
    print("Rotation state:", rotation)

    error = pax.query("SYST:ERR?").strip()
    print("Instrument error:", error)

finally:
    if pax is not None:
        pax.close()
    rm.close()