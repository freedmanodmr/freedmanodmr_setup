# -*- coding: utf-8 -*-
"""
Created on Wed Jan 14 11:34:26 2026

@author: ODMR_user
"""

import numpy as np
import time
from odmr_driver import _odmr_driver
from working_SG396_driver import _SG396
from insmgr import MyInstrumentManager

# ================================================================
# AWG / Sequence parameters
# ================================================================
SRATE = 75e6          # 75 MSa/s
SEQ_T = 100e-6         # 50 µs total waveform length

# Pulse durations (seconds)
INIT_T = 30.0e-6       # 2 µs laser init
MW_T   = 0.1e-6      # 0.25 µs Rabi pulse
READ_T = 4.0e-7       # 400 ns laser readout
MW_GAP = 5e-9        # 50 ns gap before & after MW
MW_GAP_2 = 1E-6
MW_CHANNEL_DELAY = -3.879e-6   # -3.879e-6   # Measured Delay

# Pulse timing
MW_START   = MW_CHANNEL_DELAY + INIT_T + MW_GAP
READ_START = INIT_T + MW_T + MW_GAP_2

# Output levels
AMP = 8.0   # Vpp on both channels


with MyInstrumentManager() as mgr:

    awg = mgr.awg
    sg = mgr.sg
    drv = mgr.odmr_driver

    # ================================================================
    # Build waveform arrays
    # ================================================================
    num_pts = int(round(SRATE * SEQ_T))
    t = np.arange(num_pts) / SRATE
    
    # CH1 → microwave
    w_mw = np.zeros(num_pts)
    # CH2 → laser
    w_laser = np.zeros(num_pts)
    
    # ================================================================
    # Apply pulses USING DRIVE
    # ================================================================
    drv = _odmr_driver()
    
    # Laser pulses (CH2)
    drv.apply_pulse(w_laser, 0.0,        INIT_T, AMP, SRATE)
    drv.apply_pulse(w_laser, READ_START, READ_T, AMP, SRATE)
    
    # Microwave pulse (CH1)
    drv.apply_pulse(w_mw, MW_START, MW_T, AMP, SRATE)    # READ_START instead of 0.0 usually
    
    print(f"Waveform length: {SEQ_T*1e6:.1f} µs ({num_pts} samples)")
    
    sg.set_frequency(50e6)

    # --------------------------------
    # AWG burst configuration (ONCE)
    # --------------------------------
    awg.instrument.write("C1:BSWV PHSE,-0.8")
    awg.instrument.write("C1:BTWV PRD,0.0002")
    awg.output(1, True)
    awg.set_arb_mode(1)
    awg.set_burst_mode(1, True)
    awg.set_amplitude(1,8)
    
    awg.output(2, True)
    awg.set_arb_mode(2)
    awg.set_burst_mode(2, True)
    awg.set_amplitude(2,8)
    awg.instrument.write("C2:BSWV PHSE,-0.01")
    awg.instrument.write("C2:BTWV PRD,0.0002")
    time.sleep(0.02)
    
    # MW → Channel 1
    drv.load_arbitrary_waveform(
        channel=1,
        data=w_mw,
        name="rabi_mw",
        sample_rate=SRATE,
        amplitude=AMP,
        offset=0.0,
        )
    
    # Laser → Channel 2
    drv.load_arbitrary_waveform(
        channel=2,
        data=w_laser,
        name="rabi_laser",
        sample_rate=SRATE,
        amplitude=AMP,
        offset=0.0,
        )
    
    
    
    print("✅ Rabi sequence armed")
    print("👉 Microwave on CH1 (20 ms rep, -0.8° phase); Laser on CH2 (10 ms rep, −0.1° phase)")
    print("👉 Trigger source: INTERNAL")
            