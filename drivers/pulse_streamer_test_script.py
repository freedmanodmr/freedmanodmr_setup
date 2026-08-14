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
from pulsestreamer import PulseStreamer, Sequence
from insmgr import MyInstrumentManager

IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
MW_CH = 0
LASER_CH = 1
TRIGGER_CH = 2

# Timing (ns)
init_ns = 1000000
red_read_ns = 10000
microwave_ns = 30000
readout_ns = 40000

recovery_ns = 10000000

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
    sg.set_frequency(500e6)
    sg.set_amplitude_rf(5)
  
    ps82.channel_sequences = {}  # Clear previous
    seq = Sequence()
        
    # --------------------------------
    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
    # --------------------------------
 #   laser_seq = [(100, 1),(init_ns,1),(microwave_ns,1),(40000, 1),(readout_ns,1),(recovery_ns,1)]
 #   red_seq = [(100, 0),(init_ns,0),(microwave_ns,1),(100000, 1),(readout_ns,0),(recovery_ns,0)]
 #   trig_seq = [(100, 1),(init_ns,0),(microwave_ns,0),(40000, 0),(readout_ns,0),(recovery_ns,0)]
    microwave_seq = [(100, 0),(init_ns,1),(red_read_ns,0),(microwave_ns,0),(0, 0),(100000, 0),(readout_ns,0),(recovery_ns,0)]

#    ps82.allocate_sequence(laser_seq, 1)
#    ps82.allocate_sequence(red_seq, 4)
#    ps82.allocate_sequence(trig_seq, 2)
#    ps82.allocate_sequence(microwave_seq, 0)
    ps82.allocate_sequence(microwave_seq, "AO1")
    
    ps82.begin_pulses(n_runs=-1)    