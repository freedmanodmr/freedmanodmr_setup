# To use this, make sure you connect to the InstrumentServer

import time
from pulsestreamer import PulseStreamer, Sequence, TriggerStart
from insmgr import MyInstrumentManager

IP_ADDRESS = "169.254.8.2"

# Channels (0–7)
AOM_CH = 7

# Timing converted to nanoseconds (1 ms = 1,000,000 ns)
PULSE_ON_NS = 1000000
PULSE_OFF_NS = 1000000

print("Connecting to PulseStreamer...")
ps = PulseStreamer(IP_ADDRESS)

# Stop anything currently running
ps.forceFinal()
time.sleep(0.2)

# This code is written by Google Gemini to operate the AOM driver. Using this sequence, we can create on off pulses for any experiment. 
#—————————————————————————
# BUILD ONE SINGLE HARDWARE SEQUENCE (1ms ON / 1ms OFF)
# --------------------------------------------------

with MyInstrumentManager() as mgr:

    ps82 = mgr.ps82
    sg = mgr.sg

    seq = Sequence()
    
    ps82.channel_sequences = {}  # Clear previous
    
    # Define a step-by-step sequence for Channel 7 (AOM_CH)
    # Format: .setDigital(channel, duration_in_ns)
    # 1 means High (TTL On), 0 means Low (TTL Off)
    seq.setDigital(AOM_CH, PULSE_ON_NS)   # 1 ms ON
    seq.setDigital(0, PULSE_OFF_NS)      # 1 ms OFF (using ch 0 as a dummy/padding time step)
    
    # Alternatively, if your wrapper supports direct assignment:
    # aom_seq = [(PULSE_ON_NS, 1), (PULSE_OFF_NS, 0)]
    
    # Allocate and run infinitely (-1)
    ps82.allocate_sequence(seq, AOM_CH)
    ps82.begin_pulses(n_runs=-1)              
               
    time.sleep(0.25)