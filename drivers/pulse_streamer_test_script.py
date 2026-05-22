# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 14:10:46 2026

@author: ODMR_user

"""
# -*- coding: utf-8 -*-
"""
Minimal hardware-level PulseStreamer sync test
Runs indefinitely for oscilloscope inspection
"""

# To use this, make sure you connect to the InstrumentServer

import time
from pulsestreamer import PulseStreamer, Sequence, TriggerStart
from insmgr import MyInstrumentManager

IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
MW_CH = 0
LASER_CH = 1
TRIGGER_CH = 2

# Timing (ns)
init_ns = 100000

recovery_ns = 50000

print("Connecting to PulseStreamer...")
ps = PulseStreamer(IP_ADDRESS)

# Stop anything currently running
# %%
ps.forceFinal()
time.sleep(0.2)
# %%

# --------------------------------------------------
# BUILD ONE SINGLE HARDWARE SEQUENCE
# --------------------------------------------------

with MyInstrumentManager() as mgr:

    ps82 = mgr.ps82
    sg = mgr.sg
    sg.set_frequency(100e6)
    sg.set_amplitude_rf(7.4)

    seq = Sequence()
        
    # --------------------------------
    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
    # --------------------------------
    laser_seq = [(100, 0),(init_ns,1),(recovery_ns,0)]
    trig_seq = [(100, 1),(init_ns,0),(recovery_ns,0)]

    ps82.allocate_sequence(laser_seq, 1)
    ps82.allocate_sequence(trig_seq, 2)

    ps82.begin_pulses(n_runs=-1)    