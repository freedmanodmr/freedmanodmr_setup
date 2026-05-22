# -*- coding: utf-8 -*-
"""
Created on Thu Oct 16 15:51:26 2025

@author: ODMR_user
"""

"""
working_mfli_driver.py
A small wrapper to control Zurich Instruments MFLI via zhinst.qcodes (preferred)
or zhinst.toolkit.Session. Designed to be tolerant and to expose a simple API.

Assumptions:
- zhinst.qcodes is installed and usable in your environment (you used it earlier).
- The MFLI has at least one demodulator and you want the 'R' magnitude as signal.
- If API differences appear, adapt the small get_demod_sample() implementation.
"""

import time
import logging

import zhinst.core
import zhinst.qcodes as ziqc
from zhinst.toolkit import Session

log = logging.getLogger(__name__)


class _MFLI:
    def __init__(self, serial: "DEV6813", host: str = "192.168.106.118", interface: str = "PCIe",
                 port: int = 8004, shared: bool = False, new_session: bool = True):
        """
        serial: e.g. "DEV6813"
        host: usually 192.168.106.118 when using local ziServer
        interface: "PCIE" === USB
        shared: if True, connect in shared mode (allow LabOne GUI concurrently)
        new_session: pass to qcodes/Toolkit session
        """
        self.serial = serial
        self.host = host
        self.interface = interface
        self.port = port
        self.shared = shared
        self.new_session = new_session

        self._inst = None    # qcodes instrument object if available
        self._tk_session = None
        self._connected = False
        
    def connect(self):
        """Connect to the MFLI using zhinst.qcodes if available, otherwise toolkit."""
        if ziqc is not None:
            # Use qcodes wrapper
            log.info("Connecting to MFLI via zhinst.qcodes")
            # qcodes MFLI constructor signature: MFLI(serial, host, interface=..., new_session=..., name=...)
            # Some versions accept interface case-insensitive; supply uppercase for safety.
            try:
                self._inst = ziqc.MFLI(self.serial, self.host, interface=self.interface.upper(),
                                       new_session=self.new_session)
                self._connected = True
                log.info("Connected to MFLI (qcodes wrapper).")
                return
            except Exception as e:
                log.warning("zhinst.qcodes connect failed: %s", e)

        # Fallback: use toolkit Session
        if Session is not None:
            log.info("Attempting connection using zhinst.toolkit.Session")
            self._tk_session = Session(self.host)   # , port=self.port
            # toolkit connect_device returns a toolkit device object
            tk_dev = self._tk_session.connect_device(self.serial, interface=self.interface)
            # expose tk_dev for low-level ops
            self._tk_device = tk_dev
            self._connected = True
            log.info("Connected to MFLI (toolkit).")
            return

        raise RuntimeError("No suitable zhinst connection method available (install zhinst.qcodes or zhinst.toolkit).")

    def disconnect(self):
        """Gracefully close all connections to the MFLI."""
        try:
            # If using the zhinst.qcodes driver
            if getattr(self, "_inst", None) is not None:
                try:
                    self._inst.disconnect()
                    print("Disconnected qcodes MFLI instrument.")
                except Exception as e:
                    print(f"Warning: error during qcodes disconnect: {e}")
                    self._inst = None

            # If using the zhinst.toolkit session
            if getattr(self, "_tk_session", None) is not None:
                try:
                    # Disconnect device first
                    if hasattr(self, "_tk_device") and self._tk_device is not None:
                        try:
                            self._tk_device.disconnect()
                            print("Toolkit device disconnected.")
                        except Exception as e:
                            print(f"Warning: could not disconnect toolkit device: {e}")
                            self._tk_device = None

                    # Then close the session
                    self._tk_session.disconnect()
                    print("Toolkit session closed.")
                except Exception as e:
                    print(f"Warning: error during toolkit session close: {e}")
                    self._tk_session = None

            # Reset connection flag
            self._connected = False
            print("✅ MFLI fully disconnected and cleaned up.")

        except Exception as e:
            print(f"Error while disconnecting MFLI: {e}")
            
        
    def configure_demod(self, demod_index: int = 0, bandwidth: float = 1.0, rate: float = 16384):
        """
        Configure demodulator parameters. The exact parameter names depend on the
        API; this function uses common names. Adjust if you use a different zhinst API.
        - demod_index: which demodulator to use
        - bandwidth: demodulator bandwidth in Hz
        - rate: sample rate (where applicable)
        """

        # Try qcodes API
        if self._inst is not None:
            try:
                # qcodes MFLI instruments expose demodulators as self.demods[n]
                demod = self._inst.demods[demod_index]
                demod.bandwidth.set(bandwidth)
                # sample rate / time constant: set integration / rate if available
                # Many qcodes wrappers expose 'time_constant' or 'rate' parameters; adjust if necessary.
                try:
                    demod.rate.set(rate)
                except Exception:
                    pass
                log.info("Configured demod via qcodes wrapper.")
                return
            except Exception as e:
                log.warning("Could not configure demod via qcodes: %s", e)

        # Fallback: toolkit low-level
        if getattr(self, "_tk_session", None) is not None:
            # Typical toolkit settings path example:
            # self._tk_session.set(' /{serial}/demods/{i}/enable', 1)
            base = f"/{self.serial}/demods/{demod_index}"
            self._tk_session.set(f"{base}/enable", 1)
            self._tk_session.set(f"{base}/rate", rate)
            self._tk_session.set(f"{base}/bandwidth", bandwidth)
            self._tk_session.sync()
            log.info("Configured demod via toolkit.")

    def set_demod_ref(self, ref_freq_hz: float, source: str = "external"):
        """
        Set reference for lock-in detection. If using AWG TTL to generate modulation,
        the MFLI should use the external/REF input (or 'auxin' depending on hardware).
        source: 'external' or 'internal' — here we set to external by default.
        """
        self.connect()
        if not self._connected:
            raise RuntimeError("Driver not connected. Call connect() first.")

        if self._inst is not None:
            try:
                # Set reference generator to external or internal at requested freq
                # Many qcodes wrappers allow: self.reference.signal.set(...) or similar.
                # Here we try a few common patterns (best-effort).
                try:
                    # try direct reference frequency set (if internal)
                    self._inst.references[0].freq.set(ref_freq_hz)
                except Exception:
                    pass
                # enable external reference if requested
                if source.lower().startswith("ext"):
                    # for some wrappers: self._inst.refsource.set('External')
                    try:
                        self._inst.refsource.set('External')
                    except Exception:
                        pass
                log.info("Reference configured (qcodes).")
                return
            except Exception as e:
                log.warning("Could not set reference via qcodes wrapper: %s", e)

        # toolkit fallback
        if getattr(self, "_tk_session", None) is not None:
            if source.lower().startswith("ext"):
                self._tk_session.set(f"/{self.serial}/refsource", 1)  # 1 => external (toolkit mapping)
            else:
                self._tk_session.set(f"/{self.serial}/refsource", 0)  # internal
                self._tk_session.set(f"/{self.serial}/refclock/freq", ref_freq_hz)
            self._tk_session.sync()
            log.info("Reference configured (toolkit).")

    def get_demod_ref_freq(self, demod_index: int = 0):
        """
        Return the demodulator's reference frequency (Hz).    
        Works for both zhinst.qcodes and zhinst.toolkit backends.
        Returns float or None if unavailable.
        """
      #  if not getattr(self, "_connected", False):
      #      raise RuntimeError("MFLI not connected. Call connect() first.")
            
      # --- Try zhinst.qcodes backend ---
        self.connect()
        if getattr(self, "_inst", None) is not None:
             try:
                 demod = self._inst.demods[demod_index]
                 freq = demod.freq() if callable(demod.freq) else demod.freq()
                 print(f"Demod {demod_index} reference frequency: {freq} Hz (qcodes)")
                 return float(freq)
             except Exception as e:
                  print(f"Failed via qcodes: {e}")
                    
                  # --- Try zhinst.toolkit backend ---
        if getattr(self, "_tk_session", None) is not None:
            try:
                node_path = f"/{self.serial}/demods/{demod_index}/freq"
                val = self._tk_session.get(node_path)
                # toolkit returns dict or Node object
                if isinstance(val, dict) and "value" in val:
                    val = val["value"]
                if isinstance(val, (list, tuple)):
                    val = val[0]
                freq = float(val)
                print(f"Demod {demod_index} reference frequency: {freq} Hz (toolkit)")
                return freq
            except Exception as e:
                print(f"Failed via toolkit: {e}")
                                    
        print("Unable to read demod reference frequency.")
        return None

    def get_demod_sample(self, demod_index: int = 0):
        """Return (x, y, r, phase) as floats, or (None, None, None, None) if unavailable."""
        self.connect()
        if self._inst is not None:
            try:
                demod = self._inst.demods[demod_index]
                x = getattr(demod.x, "get", lambda: demod.x())()
                y = getattr(demod.y, "get", lambda: demod.y())()
                r = getattr(demod.r, "get", lambda: demod.r())()
                phase = getattr(demod.phase, "get", lambda: demod.phase())()
                return (float(x), float(y), float(r), float(phase))
            except Exception as e:
                log.warning("qcodes demod sample read failed: %s", e)

        # toolkit fallback
        if getattr(self, "_tk_session", None) is not None:
            base = f"/{self.serial}/demods/{demod_index}/sample"
            try:
                def _extract_value(node):
                    val = self._tk_device.get(node)
                    # handle dict-style return from toolkit
                    if isinstance(val, dict):
                        val = val.get("value", None)
                        if isinstance(val, (list, tuple)) and len(val):
                            val = val[0]
                    return float(val) if val is not None else None

                x = _extract_value(f"{base}/x")
                y = _extract_value(f"{base}/y")
                r = _extract_value(f"{base}/r")
                phase = _extract_value(f"{base}/phase")
                return (x, y, r, phase)
            except Exception as e:
                log.warning("Toolkit demod sample read failed: %s", e)

        return (None, None, None, None)

    def close(self):
        """Close sessions cleanly (recommended at end of scripts)."""
        if self._inst is not None:
            try:
                # If qcodes, instrument usually has a close method
                self._inst.close()
            except Exception:
                pass
            self._inst = None
        if getattr(self, "_tk_session", None) is not None:
            try:
                self._tk_session.close()
            except Exception:
                pass
            self._tk_session = None
        self._connected = False
        log.info("MFLI driver closed.")