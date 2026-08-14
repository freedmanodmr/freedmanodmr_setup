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

MW_CH = 0
# Channels (0–7)
AOM_CH = 7

# Timing (ns)
#modulation_freq = 250

num_on_pulses = 100000
#on_ns = 100

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
    sg.set_frequency(200e6)
    sg.set_amplitude_rf(-2)

    seq = Sequence()
    
    ps82.channel_sequences = {}  # Clear previous
    pulse_length_us =3000
    off_time_us =3000

    aom_seq = [
    (pulse_length_us * 1000, 1),
    (off_time_us * 1000, 0)
    ]  
            
    ps82.allocate_sequence(aom_seq, 7)  # was channel 7 for AOM driver
    ps82.allocate_sequence(aom_seq, 2)
    ps82.begin_pulses(n_runs=-1)              
            
    time.sleep(0.25)
   
  
