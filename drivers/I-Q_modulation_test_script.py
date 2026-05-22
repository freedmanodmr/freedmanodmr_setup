# -*- coding: utf-8 -*-
"""
Created on Tue Mar 10 11:23:26 2026

@author: ODMR_user
"""

# -*- coding: utf-8 -*-
"""
Created on Wed Mar  4 14:10:46 2026

@author: ODMR_user

"""
# -*- coding: utf-8 -*-
"""
I/Q Modulation Test Script
"""

# To use this, make sure you connect to the InstrumentServer

import time
from pulsestreamer import PulseStreamer, Sequence, TriggerStart
from insmgr import MyInstrumentManager

IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
I_CH = 4
Q_CH = 5
TRIG_CH = 2

# Timing (ns)
init_ns = 1000
mw_gap_ns_1 = 1000
mw_ns = 0
mw_gap_ns_2 = 50000
readout_ns = 1000
recovery_ns = 600000

print("Connecting to PulseStreamer...")
ps = PulseStreamer(IP_ADDRESS)

# Stop anything currently running
ps.forceFinal()
time.sleep(0.2)

# --------------------------------------------------
# BUILD ONE SINGLE HARDWARE SEQUENCE
# --------------------------------------------------

with MyInstrumentManager() as mgr:

    ps82 = mgr.ps82
    sg = mgr.sg
    sg.set_frequency(10e6)
    sg.set_amplitude_rf(7.4)

    seq = Sequence()

    I_seq = [(init_ns,0),(mw_ns,0),(mw_gap_ns_1,0),
             (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
    
    Q_seq = [(init_ns,0),(mw_ns,0),(mw_gap_ns_1,0),
             (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
    
    mw_seq = [(init_ns,1),(mw_ns,0),(mw_gap_ns_1,1),
             (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
    
    trig_seq = [(init_ns,1),(mw_ns,0),(mw_gap_ns_1,0),
             (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]

    ps82.allocate_sequence(I_seq, 4)
    ps82.allocate_sequence(Q_seq, 5)
    ps82.allocate_sequence(mw_seq, 0)
    ps82.allocate_sequence(trig_seq, 2)

    ps82.begin_pulses(n_runs=-1)      