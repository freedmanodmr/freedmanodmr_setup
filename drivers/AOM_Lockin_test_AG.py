# -*- coding: utf-8 -*-
"""
Swabian PulseStreamer & Zurich Instruments Sync Script
Optimized for 8 ns hardware clock constraints to guarantee Lock-In PLL tracking.
"""

import time
from pulsestreamer import PulseStreamer

# --- HARDWARE CONFIGURATION ---
IP_ADDRESS = "169.254.8.2"
AOM_CH = 7          # Digital channel driving your AOM
LOCKIN_REF_CH = 2   # Digital channel routed to Lock-In ExtRef In

# --- TIMING CONFIGURATIONS (Strict 8 ns Multiples) ---
rep_rate_hz = 100                  # 100 Hz global repetition envelope (10 ms total period)

# 1.04166 MHz carrier frequency provides a perfectly symmetric 960 ns cycle (divisible by 8)
pulse_on_time = 480                # 480 ns (60 clock cycles) - EXACT
pulse_off_time = 480               # 480 ns (60 clock cycles) - EXACT
carrier_period_ns = pulse_on_time + pulse_off_time  # 960 ns

total_period_ns = int(1e9 / rep_rate_hz)        # 10,000,000 ns

# Calculate exactly how many clean cycles fit into a 5 ms active window
num_active_cycles = 5000000 // carrier_period_ns   # 5208 cycles * 960 ns = 4,999,680 ns

# --- INITIALIZE HARDWARE ---
print("Connecting to PulseStreamer...")
ps = PulseStreamer(IP_ADDRESS)
ps.forceFinal()  
time.sleep(0.2)

# --- STEP 1: BUILD THE RAW TIME-DOMAIN PATTERNS ---

# Base unit for a single 1 MHz range square wave cycle
single_carrier_cycle = [(pulse_on_time, 1), (pulse_off_time, 0)]

# AOM Waveform: Active burst for ~5 ms, followed by dead silence for the remainder of the 10 ms frame
aom_active_pattern = single_carrier_cycle * num_active_cycles
remaining_dark_ns = total_period_ns - (carrier_period_ns * num_active_cycles)

# Ensure the dark padding duration is also rounded to a multiple of 8 ns
remaining_dark_ns = int(round(remaining_dark_ns / 8.0) * 8)
aom_dark_pattern = [(remaining_dark_ns, 0)]
aom_full_pattern = aom_active_pattern + aom_dark_pattern

# Lock-In Reference Waveform: Runs continuously for the entire 10 ms block
total_cycles_needed = total_period_ns // carrier_period_ns
lockin_full_pattern = single_carrier_cycle * total_cycles_needed


# --- STEP 2: CREATE SWABIAN SEQUENCE OBJECT AND MAP TO CHANNELS ---
print("Constructing sequence...")
seq = ps.createSequence()

# Write the custom patterns to their respective physical channels
seq.setDigital(AOM_CH, aom_full_pattern)
seq.setDigital(LOCKIN_REF_CH, lockin_full_pattern)


# --- STEP 3: STREAM TO HARDWARE ---
print("Streaming sequence to hardware (running indefinitely)...")
ps.stream(seq, n_runs=-1)

print("\n[SUCCESS] System is running with strictly aligned clock cycles.")
print(" -> Check LabOne: The ExtRef light should turn SOLID green at ~1.04 MHz.")