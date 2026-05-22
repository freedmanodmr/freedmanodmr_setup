# To use this, make sure you connect to the InstrumentServer

import time
from pulsestreamer import PulseStreamer, Sequence, TriggerStart
from insmgr import MyInstrumentManager

IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
AOM_CH = 7

# Timing (ns)
modulation_freq = 0.25e9

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