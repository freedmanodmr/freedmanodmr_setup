# -*- coding: utf-8 -*-
"""
odmr_driver.py
CW-ODMR experiment controller
 - Uses: SRS SG396 microwave source + Zurich Instruments MFLI lock-in amplifier
 - AWG modulation is currently handled manually (AWG code commented out)
 - Auto-connects to SG and MFLI via InstrumentGateway

Author: ODMR_user + GPT
"""

import time
import numpy as np
import struct
# import pandas as pd
# import matplotlib.pyplot as plt
# from typing import Iterable, Optional

from nspyre import InstrumentGateway


class _odmr_driver:
    """
    NSpyre-compatible ODMR driver that auto-connects to existing instruments
    running on the instrument server.
    """

    def __init__(self,
                 siggen_name: str = 'sg',
                 mfli_name: str = 'mfli',
                 awg_name: str = 'awg',
                 modulation_freq_hz: float = 0,
                 mw_amplitude_dbm: float = 7.4,
                 step_hz: float = 5e6,
                 start_hz: float = 0.0,
                 stop_hz: float = 6e9,
                 dwell: float = 0.05,
                 average: int = 1):
        """
        siggen_name: name of the SG396 driver in the instrument server
        mfli_name: name of the MFLI driver in the instrument server
        modulation_freq_hz: reference frequency for MFLI
        mw_amplitude_dbm: default MW amplitude in dBm
        step_hz: frequency step
        start_hz, stop_hz: sweep range
        dwell: delay between steps
        average: number of samples to average per frequency
        """
        gw = InstrumentGateway()

        # Auto-connect to instruments by name
        self.sg = getattr(gw, siggen_name)
        self.mfli = getattr(gw, mfli_name)
        self.awg = getattr(gw, awg_name)

        self.modulation_freq_hz = modulation_freq_hz
        self.mw_amplitude_dbm = mw_amplitude_dbm
        self.step_hz = step_hz
        self.start_hz = start_hz
        self.stop_hz = stop_hz
        self.dwell = dwell
        self.average = max(1, int(average))

    # -------------------------------------------------------------------------
    # Core functions
    # -------------------------------------------------------------------------


    def single_point_read(self):
        """Read and average MFLI demodulator samples."""
        x_vals, y_vals, r_vals, phase_vals = [], [], [], []

        for _ in range(self.average):
            signal = self.mfli.get_signal()
            x = signal["x"]
            y = signal["y"]
            r = signal["r"]
            phase = signal["phase"]
            
            x_vals.append(x)
            y_vals.append(y)
            r_vals.append(r)
            phase_vals.append(phase)

            if self.average > 1:
                time.sleep(0.002)

        x_vals = np.array(x_vals, dtype=float)
        y_vals = np.array(y_vals, dtype=float)
        r_vals = np.array(r_vals, dtype=float)
        phase_vals = np.array(phase_vals, dtype=float)
 #       print(x_vals, y_vals, r_vals, phase_vals)

        return {
            "x": np.nanmean(x_vals),
            "y": np.nanmean(y_vals),
            "r": np.nanmean(r_vals),
            "phase": np.nanmean(phase_vals),
            }
    
    def cnts(self, dwell: float = 0.050) -> float:
        """Return an equivalent 'photon count' based on the MFLI demodulated signal.
        dwell: integration time in seconds to average over (default 50 ms)
        Returns:
            float: averaged MFLI R magnitude (voltage)
            """
        t_end = time.time() + dwell
        vals = []
        while time.time() < t_end:
            sample = self.single_point_read()
            vals.append(sample["r"])   # Used to say "r"
            time.sleep(0.050)
            
        return float(np.nanmean(vals))

    def accum_cnts(self, dwell: float = 0.050) -> float:
        """Return an equivalent 'photon count' based on the MFLI demodulated signal.
        dwell: integration time in seconds to average over (default 50 ms)
        Returns:
            float: averaged MFLI R magnitude (voltage)
            """
        t_end = time.time() + dwell
        vals = []
        while time.time() < t_end:
            sample = self.single_point_read()
            vals.append(sample["r"])   # Used to say "r"
            time.sleep(0.050)
            
        return float(np.nansum(vals))
    
    
    def preempt_pulse(
            self,
            channel: int = 2,
            init_ns: int = 2000,
            mw_ns: int = 100,
            read_ns: int = 500,
            gap_ns: int = 50,
            sample_rate: float = 75e6,
            total_time_us: float = 10000,
            ):
        
        # --------------------------------
        # Pulse timing (seconds)
        # --------------------------------
        init_t = init_ns * 1e-9
        mw_t = mw_ns * 1e-9
        read_t = read_ns * 1e-9
        gap_t = gap_ns * 1e-9
        total_time_s = total_time_us * 1e-6
        
        # --------------------------------
        # Time base
        # --------------------------------
        num_pts = int(round(sample_rate * total_time_s))
        
        mw_start = init_t + gap_t
        read_start = mw_start + mw_t + gap_t
        
        # --------------------------------
        # Build waveform
        # --------------------------------
        w_laser = np.zeros(num_pts)
        
        self.apply_pulse(w_laser, 0.0, init_t, 8.0, sample_rate)
        self.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
        
        self.load_arbitrary_waveform_burst(
            channel=2,
            data=w_laser,
            name="preempt_laser",
            sample_rate=sample_rate,
            )
        
        time.sleep(0.01)

        
# ---------------------------------
# ODMR operating modes from AWG
# ---------------------------------
# PROBABLY DON'T WORK AT THE MOMENT
    def setCWMode(self, freq=2000, amp=5, DutyCycle=50, offset=0, channel=1):
        """
        Continuous wave ODMR: use SQUARE waveform.
        
        Defaults are set to 50% duty cycle with a 5 Vpp 
        (required for TTL) and a waveperiod of 0.005 seconds (2 kHz).
        
        Default Channel is 1, but for the laser you must specific "channel=2")
        
        """
        self.awg.setWaveType(self.WAVEFORM_SQUARE, channel)
        self.awg.setWaveFrequency(freq, channel)
        self.awg.setWaveAmplitude(amp, channel)
        self.awg.setDutyCycle(DutyCycle)
        self.awg.setWaveOffset(offset, channel)

    def setPulsedMode(self, rep_rate=100, width=16, amp=5, offset=0, channel=1):
        """Pulsed ODMR: use PULSE waveform."""
        """
        Defaults are set to 16 ns pulse with a 5 Vpp 
        (required for TTL) and a waveperiod of 0.01 seconds (rep_rate=100 Hz) to 
        allow for 100 measurements per second. 
        
        Default Channel is 1, but for the laser you must specific "channel=2")
        
        """
        self.awg.selectPulseWaveform(channel)
        self.awg.setWaveFrequency(rep_rate, channel)   # repetition rate
        self.awg.setPulseWidth(width, channel)
        self.awg.setWaveAmplitude(amp, channel)
        self.awg.setWaveOffset(offset, channel)
    
    # -----------------------------
    # High-level pulse sequence programming
    # -----------------------------

    def load_arbitrary_waveform(
        self,
        channel: int,
        data: np.ndarray,
        name: str = None,
        sample_rate: float = None,
        amplitude: float = 1.0,
        offset: float = 0.0,
        normalize: bool = True,
        verbose: bool = True,
        trigger_delay: float = None,
        trigger_width: float = None,
        trigger_amp: float = 3):
        """
        Upload an arbitrary waveform to the SDG2000X TrueArb engine AND optionally
        configure a TTL trigger pulse via Aux Out.
        """    
        TRUEARB_MAX_SRATE = self.awg._sample_rate
        
        # ------------------------------
        # Validate channel
        # ------------------------------
        if channel not in self.awg.channel:
            raise ValueError(f"Invalid channel {channel}. Must be 1 or 2.")

        # ------------------------------
        # Prepare name
        # ------------------------------
        if name is None:
            name = f"userarb_ch{channel}_{int(time.time())}"
            
        # ------------------------------
        # Enforce sample rate
        # ------------------------------
        if sample_rate is None:
            sr = self.awg._sample_rate
        else:
            sr = min(float(sample_rate), TRUEARB_MAX_SRATE)
            self.awg.set_sample_rate(sr)

        # ------------------------------
        # Convert waveform to int16
        # ------------------------------
        arr = np.asarray(data, dtype=float)

        if normalize:
            max_abs = np.max(np.abs(arr))
            scale = 0.0 if max_abs < 1e-12 else 32767.0 / max_abs
            arr_i16 = np.int16(arr * scale)
        else:
            arr_i16 = np.int16(arr * 32767.0)

        binary_block = b"".join(struct.pack("<h", x) for x in arr_i16)
        num_samples = len(arr_i16)

        # ------------------------------
        # Upload WVDT block
        # ------------------------------
        header = f"C{channel}:WVDT WVNM,{name},WAVEDATA,".encode("ascii")
        self.awg._write_raw(header + binary_block)
        
        # ------------------------------
        # Enable TrueArb mode
        # ------------------------------
        self.awg._write(f"C{channel}:ARWV NAME,{name}")
        self.awg._write(f"C{channel}:ARWV MODE,TRUE")
        self.awg._write(f"C{channel}:ARWV SRATE,{sr}")
        
        # ------------------------------
        # Apply amplitude & offset
        # ------------------------------
        self.awg.set_amplitude(channel, amplitude)
        self.awg.set_offset(channel, offset)
        
        # ------------------------------
        # Enable channel output
        # ------------------------------
        self.awg._write(f"C{channel}:ARWV STATE,ON")
        self.awg.output(channel, True)

        # ------------------------------
        # Print summary
        # ------------------------------
        if verbose:
            print("\n=== Uploaded Arbitrary Waveform ===")
            print(f"  Channel:       {channel}")
            print(f"  Name:          {name}")
            print(f"  Samples:       {num_samples}")
            print(f"  Sample rate:   {sr/1e6:.3f} MSa/s")
            print(f"  Amplitude:     {amplitude} Vpp")
            print(f"  Offset:        {offset} V")
            print("===================================\n")

        return name
    
###########################################################

## ESSENTIAL FUNCTION FOR CONSTRUCTING THE WAVEFORM INTO THE NATIVE AWG TIMING    
    
###########################################################

    def apply_pulse(
            self,
            waveform: np.ndarray,
            start_s: float,
            width_s: float,
            amplitude: float,
            sample_rate: float,
            ):
        """
        Apply a rectangular pulse to a waveform array.
        
        Args:
            waveform: numpy array to modify in-place
            start_s: pulse start time (seconds)
            width_s: pulse width (seconds)
            amplitude: pulse amplitude (same units as waveform)
            sample_rate: waveform sample rate (Sa/s)
        Notes:
            - Times are interpreted in seconds
            - Indices are clipped safely to waveform bounds
            - Pulse end is exclusive (Python slicing convention)
            """
        if width_s <= 0:
            raise ValueError("Pulse width must be > 0")

        if start_s < 0:
            raise ValueError("Pulse start time must be >= 0")

        n = len(waveform)
        
        # Convert time → sample index
        start_idx = int(round(start_s * sample_rate))
        width_pts = int(round(width_s * sample_rate))
        end_idx = start_idx + width_pts
        
        # Clip to array bounds
        start_idx = max(0, min(start_idx, n))
        end_idx   = max(start_idx, min(end_idx, n))

        # Apply pulse
        waveform[start_idx:end_idx] = amplitude

  
    def load_arbitrary_waveform_burst(
        self,
        channel: int,
        data: np.ndarray,
        name: str = None,
        sample_rate: float = None,
 #      amplitude: float = 8.0,
 #      offset: float = 0.0,
        normalize: bool = True,
        verbose: bool = True,
        # --- Optional channel burst ---
 #       trigger_channel_burst: bool = False,
 #       burst_ncycles: int = 1,
 #       burst_delay: float = 0.0,
       ):
        """
        Upload an arbitrary waveform to TrueArb channel and optionally
        activate burst mode for this channel using an internal trigger
        and falling edge trigger by default.
        """
        TRUEARB_MAX_SRATE = self.awg._sample_rate
        
        # ------------------------------
        # Validate channel
        # ------------------------------
        if channel not in self.awg.channel:
            raise ValueError(f"Invalid channel {channel}. Must be 1 or 2.")

        # ------------------------------
        # Prepare waveform name
        # ------------------------------
        if name is None:
            name = f"userarb_ch{channel}_{int(time.time())}"
            
        # ------------------------------
        # Enforce sample rate
        # ------------------------------
        sr = self.awg._sample_rate if sample_rate is None else min(float(sample_rate), TRUEARB_MAX_SRATE)
        self.awg.set_sample_rate(sr)
    
        # ------------------------------
        # Convert waveform to int16
        # ------------------------------
        arr = np.asarray(data, dtype=float)
        if normalize:
            max_abs = np.max(np.abs(arr))
            scale = 0.0 if max_abs < 1e-12 else 32767.0 / max_abs
            arr_i16 = np.int16(arr * scale)
        else:
            arr_i16 = np.int16(arr * 32767.0)

        binary_block = b"".join(struct.pack("<h", x) for x in arr_i16)
        num_samples = len(arr_i16)

        # ------------------------------
        # Upload WVDT block
        # ------------------------------
        header = f"C{channel}:WVDT WVNM,{name},WAVEDATA,".encode("ascii")
        self.awg._write_raw(header + binary_block)
        
        # ------------------------------
        # Ensure TrueArb mode is enabled
        # ------------------------------
        self.awg._write(f"C{channel}:ARWV NAME,{name}")   # assign waveform
 #       self.awg._write(f"C{channel}:ARWV MODE,TRUE")    # force TrueArb mode, I think this is breaking the mode
 #       self.awg._write(f"C{channel}:ARWV SRATE,{sr}")   # set sample rate
 #       self.awg.output(channel, True)                    # enable output
        
        # ------------------------------
        # Apply amplitude & offset
        # ------------------------------
 #      self.awg.set_amplitude(channel, amplitude)
 #      self.awg.set_offset(channel, offset)
    
        # ------------------------------
        # Enable channel output explicitly
        # ------------------------------
#        self.awg._write(f"C{channel}:ARWV STATE,ON")

        # ------------------------------
        # Configure optional channel burst
        # ------------------------------
#        if trigger_channel_burst:
#            self.awg._write(f"C{channel}:BTWV STATE,ON")               # enable burst
#            self.awg._write(f"C{channel}:BTWV TRSR,INT")               # internal trigger
#            self.awg._write(f"C{channel}:BTWV TRMD,RISE")              # falling edge trigger
#            self.awg._write(f"C{channel}:BTWV TIME,{burst_ncycles}")   # number of cycles
#            self.awg._write(f"C{channel}:BTWV DLAY,{burst_delay}")     # optional delay

        # ------------------------------
        # Summary
        # ------------------------------
        if verbose:
            print("\n=== Uploaded Arbitrary Waveform ===")
            print(f"  Channel:       {channel}")
            print(f"  Name:          {name}")
            print(f"  Samples:       {num_samples}")
            print(f"  Sample rate:   {sr/1e6:.3f} MSa/s")
 #          print(f"  Amplitude:     {amplitude} Vpp")
 #          print(f"  Offset:        {offset} V")
 #           if trigger_channel_burst:
 #               print(f"  Channel burst: Enabled, {burst_ncycles} cycle(s), delay={burst_delay}s, internal trigger, falling edge")
            print("===================================\n")

        return name



