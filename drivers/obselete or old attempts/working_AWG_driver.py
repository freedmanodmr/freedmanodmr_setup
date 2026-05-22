# -*- coding: utf-8 -*-
"""
Created on Mon Nov 17 09:27:20 2025

@author: ODMR_user + ChatGPT
"""

import time
import pyvisa


class SiglentAWG:
    """
    Siglent AWG driver for producing TTL pulses to control
    Cobolt laser digital modulation input.
    Compatible with SDG1000X, SDG2000X, SDG6000X series.
    """

    def __init__(self, resource_name):
        rm = pyvisa.ResourceManager()
        self.inst = rm.open_resource(resource_name)
        self.inst.timeout = 5000

        # Basic setup
        self.inst.write("C1:OUTP ON")          # enable channel 1 output
        self.inst.write("C1:LOAD 50")          # set 50 ohm output

    #---------------------------------------------------------
    # Basic waveform configuration
    #---------------------------------------------------------
    def set_constant_high(self, volts=5.0):
        """Set AWG output to constant 5 V (CW laser ON)."""
        self.inst.write(f"C1:BSWV WV,DC,OFST,{volts/2},AMP,{volts}")

    def set_constant_low(self):
        """Force laser off."""
        self.inst.write("C1:BSWV WV,DC,OFST,0,AMP,0")

    def set_square_mod(self, freq_hz, duty_percent=50, high_v=5.0, low_v=0.0):
        """Square wave TTL output."""
        self.inst.write(
            f"C1:BSWV WV,SQ,FRQ,{freq_hz},"
            f"DUTY,{duty_percent},HLEV,{high_v},LLEV,{low_v}"
        )

    #---------------------------------------------------------
    # Pulse mode (better than square for ODMR)
    #---------------------------------------------------------
    def set_single_pulse(self, width_us, period_us, high_v=5.0, low_v=0.0):
        """Generate repeating pulses with given timing."""
        self.inst.write(
            "C1:BSWV WV,PULSE," +
            f"WIDTH,{width_us}US,PERI,{period_us}US,HLEV,{high_v},LLEV,{low_v}"
        )

    #---------------------------------------------------------
    # Arbitrary pulse sequences for pulsed ODMR
    #---------------------------------------------------------
    def send_pulse_train(self, on_times_us, off_times_us, high_v=5.0, low_v=0.0):
        """
        Program a pulse train using burst mode.
        Ideal for pulsed ODMR where pulse spacing varies.
        """
        assert len(on_times_us) == len(off_times_us)

        # Clear burst settings
        self.inst.write("C1:BTWV STATE,OFF")

        # Build arbitrary sequence (simple concatenation)
        points = []
        current_time = 0

        for on, off in zip(on_times_us, off_times_us):
            # high section
            points.append((current_time, high_v))
            current_time += on
            points.append((current_time, high_v))

            # low section
            points.append((current_time, low_v))
            current_time += off
            points.append((current_time, low_v))

        # Convert times to seconds
        t = [p[0] * 1e-6 for p in points]
        v = [p[1] for p in points]

        # Upload AWG arbitrary waveform
        self._upload_arb_waveform(t, v)

    def _upload_arb_waveform(self, t, v):
        """Upload an arbitrary waveform to the AWG."""
        # Resample to uniform points
        import numpy as np
        N = 16000  # supported by most Siglent AWGs
        t_uniform = np.linspace(t[0], t[-1], N)
        v_uniform = np.interp(t_uniform, t, v)

        # Format for SCPI upload
        csv = ",".join(f"{x:.3f}" for x in v_uniform)

        # Send waveform
        self.inst.write("C1:ARWV WAVEFORM," + csv)
        self.inst.write("C1:BSWV WV,ARBITRARY")

    #---------------------------------------------------------
    # Utility
    #---------------------------------------------------------
    def output_on(self):
        self.inst.write("C1:OUTP ON")

    def output_off(self):
        self.inst.write("C1:OUTP OFF")

    def close(self):
        self.inst.close()
