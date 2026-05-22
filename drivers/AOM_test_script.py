# -*- coding: utf-8 -*-
"""
Created on Wed May 20 14:33:02 2026

@author: ODMR_user
"""

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
AOM_CH = 7

# Timing (ns)
modulation_freq = 1e8

num_on_pulses = 100
on_ns = 100

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

    seq = Sequence()
    
    ps82.channel_sequences = {}  # Clear previous
    period_ns = int(1e9 / modulation_freq)  
    aom_seq = ps82.square_wave(period_ns)
            
    ps82.allocate_sequence(aom_seq, 7)
    ps82.begin_pulses(n_runs=-1)              
            
    time.sleep(0.25)
  
# ----------------------------------------------------------------------------  
# Put me in a different file, or highlight the code you want to run and choose 
# "Run current line/selection". 
# ---------------------------------------------------------------------------- 

import time
from pulsestreamer import PulseStreamer, Sequence, TriggerStart
from insmgr import MyInstrumentManager
 
IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
AOM_CH = 7

num_on_pulses = 100     # an absolute number, no units
on_ns = 100             # in units of ns

print("Connecting to PulseStreamer...")
ps = PulseStreamer(IP_ADDRESS)

# Stop anything currently running
# %%
ps.forceFinal()
time.sleep(0.2)
# %%
   
with MyInstrumentManager() as mgr:

    num_on_pulses = int(num_on_pulses)
    on_train = [(on_ns,1),(on_ns,0)] * num_on_pulses
    on_total = sum(t for t,_ in on_train)

    aom_doublemod_seq = on_train + [(on_total, 0)]
    ps82.allocate_sequence(aom_doublemod_seq, 0)
    ps82.begin_pulses(n_runs=-1)  
