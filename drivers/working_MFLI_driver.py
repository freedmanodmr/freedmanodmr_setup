# -*- coding: utf-8 -*-
"""
Created on Mon Nov 10 13:00:30 2025

@author: ODMR_user
"""

"""
MFLI Driver — Zurich Instruments MFLI Lock-in Amplifier
=======================================================

Lightweight driver using zhinst.qcodes + zhinst.toolkit to connect,
configure, and read data from the MFLI. Designed for use by an
instrument server (e.g. NSpyre) to coordinate ODMR measurements.
"""

import numpy as np
import zhinst.qcodes as ziqc
from zhinst.toolkit import Session
import time

class _MFLI:
    """Minimal control interface for MFLI lock-in amplifier."""

    def __init__(self, serial: str = "DEV6813", host: str = "192.168.106.118", interface: str = "PCIe"):
        """
        Args:
            serial (str): MFLI device serial number, e.g. 'DEV6813'
            host (str): Host IP of the Zurich Instruments Data Server
            interface (str): '1GbE', 'USB', or 'PCIE'
        """
        self.serial = serial
        self.host = host
        self.interface = interface

        self.qc_inst = None          # zhinst.qcodes.MFLI object
        self.tk_session = None       # zhinst.toolkit.Session
        self.tk_object = None        # toolkit device handle
        self.connected = False

    # -------------------------------------------------------------------------
    # Connection Management
    # -------------------------------------------------------------------------
    def connect(self):
        """Connect to the MFLI using zhinst.qcodes + toolkit."""
        if self.connected:
            print(f"[INFO] Already connected to {self.serial}")
            return

        print(f"[INFO] Connecting to {self.serial} on {self.host} via {self.interface}...")

        try:
            # Create qcodes interface (user-level control)
            self.qc_inst = ziqc.MFLI(
                self.serial, host=self.host, interface=self.interface, new_session=True
            )
            print("[INFO] Connected via zhinst.qcodes.")
        except Exception as e:
            print(f"[WARN] qcodes connection failed: {e}")
            self.qc_inst = None

        try:
            # Create toolkit session (for fast node access)
            self.tk_session = Session(self.host)
            self.tk_object = self.tk_session.connect_device(self.serial, interface=self.interface)
            self.connected = True
            print("[INFO] Connected via zhinst.toolkit.")
        except Exception as e:
            print(f"[ERROR] toolkit connection failed: {e}")
            self.tk_session = None
            self.tk_object = None
            self.connected = False

    def disconnect(self):
        """Close connection to the MFLI."""
        if self.qc_inst:
            try:
                self.qc_inst.close()
                print(f"[INFO] Closed qcodes session for {self.serial}")
            except Exception as e:
                print(f"[WARN] Error closing qcodes session: {e}")

        if self.tk_session:
            try:
                self.tk_session.close()
                print(f"[INFO] Closed toolkit session for {self.serial}")
            except Exception as e:
                print(f"[WARN] Error closing toolkit session: {e}")

        self.qc_inst = None
        self.tk_session = None
        self.tk_object = None
        self.connected = False

    def ensure_connection(self):
        """Reconnect automatically if not already connected."""
        if not getattr(self, "connected", False):
            print("[INFO] MFLI not connected — reconnecting...")
            self.connect()

    # -------------------------------------------------------------------------
    # Configuration
    # -------------------------------------------------------------------------
    def set_demod_freq(self, freq_hz: float):
        """Set oscillator frequency."""
        if not self.connected:
            raise RuntimeError("MFLI not connected.")
        self.tk_object.oscs[0].freq(freq_hz)
        print(f"[INFO] Set frequency to {freq_hz / 1e6:.6f} kHz")


    def set_output(self, enable: bool = True):
        """Enable or disable signal output."""
        if not self.connected:
            raise RuntimeError("MFLI not connected.")
        self.tk_object.sigouts[0].on(enable)
        print(f"[INFO] Output {'enabled' if enable else 'disabled'}")


    def set_demod_time_constant(self, tau_s: float):
        """Set demodulator time constant (in seconds)."""
        if not self.connected:
            raise RuntimeError("MFLI not connected.")
        self.tk_object.demods[0].timeconstant(tau_s)
        print(f"[INFO] Time constant set to {tau_s:.3f} s")

    # -------------------------------------------------------------------------
    # Signal Acquisition
    # -------------------------------------------------------------------------
    
    def get_signal(self):
        """
        Read demodulated signal from the MFLI.

        Returns:
            dict: {"x": float, "y": float, "r": float, "phase": float}
        """
        self.ensure_connection()
        if not self.connected:
            raise RuntimeError("MFLI not connected.")
        try:
            sample = self.tk_object.demods[0].sample()
            x = float(sample["x"])
            y = float(sample["y"])
            r = np.sqrt(x**2 + y**2)
            phase = np.arctan2(y, x)
            print(f"[DATA] x={x:.3e}, y={y:.3e}, r={r:.3e}, φ={np.degrees(phase):.2f}°")
            print(x, y, r, phase)
            return dict(x=x, y=y, r=r, phase=phase)
        #    return (x, y, r, phase)
        except Exception as e:
            print(f"[ERROR] Could not read signal: {e}")
            return dict(x=None, y=None, r=None, phase=None)
  
        
    def get_demod_ref_freq(self):
        
        """Read the demodulator reference frequency.
        
        Returns: demodulation frequency"""
        
        self.ensure_connection()
        if not self.connected:
            raise RuntimeError("MFLI not connected.")
        try:
            freq = float(self.tk_object.oscs[0].freq())
            print(f"[INFO] Demod reference frequency: {freq/1:.3f} Hz")
            return freq
        except Exception as e:
            print(f"Unable to read demod reference frequency: {e}")
            return None
        

    # -------------------------------------------------------------------------
    # Scope Acquisition
    # -------------------------------------------------------------------------
    def get_scope_trace(self, channel: int = 0):
        """
        Acquires a single shot of scope data from the active MFLI scope module.

        Args:
            channel (int): Scope channel index to extract (0 for Channel 1)

        Returns:
            dict: {"time": ndarray (in ms), "signal": ndarray (in µV)}
        """
        self.ensure_connection()
        if not self.connected:
            raise RuntimeError("MFLI not connected.")

        try:
            # 1. Initialize the toolkit scope module
            scope_module = self.tk_session.modules.scope
            wave_node = self.tk_object.scopes[0].wave
            
            # Subscribe to the target scope wave node
            scope_module.subscribe(wave_node)
            
            # Ensure scope mode is set to time domain (1)
            scope_module.mode(1)
            
            # 2. Start execution and trigger a single capture block
            scope_module.execute()
            self.tk_object.scopes[0].enable(True)
            self.tk_session.sync()
            
            # Simple timeout loop to wait for data collection to finish
            timeout = 2.0  # seconds
            start_time = time.time()
            while scope_module.records() == 0:
                time.sleep(0.01)
                if time.time() - start_time > timeout:
                    raise TimeoutError("MFLI Scope module timed out waiting for data.")
            
            # 3. Read back and extract data
            data = scope_module.read()
            self.tk_object.scopes[0].enable(False) # Turn scope off
            
            if wave_node in data:
                scope_records = data[wave_node]
                latest_record = scope_records[-1] # Grabs the latest trigger block
                
                # Extract targeted wave channel
                wave = latest_record["wave"][channel]
                
                # 4. Process math to match LabOne visual output
                totalsamples = latest_record["totalsamples"]
                dt = latest_record["dt"]
                
                # Shift time axis so 0 is centered exactly like LabOne scope
                time_axis = (np.arange(totalsamples) - totalsamples // 2) * dt * 1e3  # convert to ms
                
                # Convert raw voltage to microvolts (µV)
                signal_uV = wave * 1e6
                
                return {"time": time_axis, "signal": signal_uV}
            else:
                print("[WARN] Scope wave node missing from read data block.")
                return None

        except Exception as e:
            print(f"[ERROR] Failed to fetch scope trace: {e}")
            return None
        
        
    def get_background_PL(self, integration_time=0.1, channel=0):
        """
        Measure background PL from raw MFLI current input.
        
        The scope acquires repeated traces for the specified integration_time.
        The returned value is the average current over all acquired samples.
        
        Parameters
        ----------
        integration_time : float
            Total averaging time (seconds).
            
        channel : int
            Scope channel index.

        Returns
        -------
        float
            Averaged current input signal (Amps).
            """

        self.ensure_connection()

        if not self.connected:
            raise RuntimeError("MFLI not connected.")

        scope = self.tk_session.modules.scope
        wave_node = "/dev6813/scopes/0/wave"
        
        waves = []

        try:
            scope.finish()
            scope.unsubscribe("*")
            scope.subscribe(wave_node)
            scope.mode(1)
            
            self.tk_object.scopes[0].enable(True)
        
            start = time.time()

            while time.time() - start < integration_time:
                scope.execute()
                
                # Wait for one trace
                t0 = time.time()
                
                while scope.records() < 1:
                    if time.time() - t0 > 1.0:
                        raise TimeoutError("Scope acquisition timeout")
                    time.sleep(0.001)

            data = scope.read()
            record = data[wave_node][0][-1]

            wave = np.asarray(
                record["wave"][channel],
                dtype=float)

            waves.append(wave)

            self.tk_object.scopes[0].enable(False)
            scope.finish()

        except Exception as e:
            print(f"[ERROR] Background PL acquisition failed: {e}")
            self.tk_object.scopes[0].enable(False)
            scope.finish()
            return np.nan
        
        if len(waves) == 0:
            return np.nan

        # Average all traces and all samples
        background_PL = np.mean(waves)

        return float(background_PL)
                        

    def single_point_read(self):
        """Read and average MFLI demodulator samples."""

        x_vals, y_vals, r_vals, phase_vals = [], [], [], []

        for _ in range(self.average):

            signal = self.mfli.get_signal()

            x_vals.append(signal["x"])
            y_vals.append(signal["y"])
            r_vals.append(signal["r"])
            phase_vals.append(signal["phase"])

        if self.average > 1:
            time.sleep(0.001)

        return {
            "x": np.nanmean(x_vals),
            "y": np.nanmean(y_vals),
            "r": np.nanmean(r_vals),
            "phase": np.nanmean(phase_vals)}