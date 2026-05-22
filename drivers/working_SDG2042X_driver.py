# -*- coding: utf-8 -*-
"""
working_SDG2042X_driver.py
Low-level SDG2042X driver with:
 - RPyC-safe conversions
 - binary ARB upload (definite-length IEEE/IEC binary block)
 - convenience compatibility methods: stop/start, set_sample_rate, load_waveform, set_waveform_output
 - TrueArb default sample rate limit: 75 MSa/s
"""

import time
import pyvisa
#import struct
import numpy as np

TRUEARB_MAX_SRATE = 75_000_000.0  # 75 MSa/s hardware ceiling (TrueArb)

class SDG2042XVisaException(Exception):
    pass

class SDG2042XParameterException(Exception):
    pass

class SDG2042X:
    def __init__(self, visa_address: str = "USB0::0xF4EC::0x1102::SDG2XFBC900189::INSTR"):
        self.visa_address = visa_address
        rm = pyvisa.ResourceManager()
        try:
            self.dev = rm.open_resource(visa_address)
            self.dev.timeout = 5000
            self.dev.write_termination = '\n'
            self.dev.read_termination = '\n'
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to open VISA device {visa_address}: {e}")

        # internal state
        self._sample_rate = None  # Sa/s
        self._user_arbs = {}      # channel -> name
        self._detect_model_sample_rate()

    # -----------------------------
    # Internal helpers (RPyC-safe)
    # -----------------------------
    def _write(self, cmd):
        """Write a SCPI command (string) or raw bytes. Uses pyvisa write when possible."""
        try:
            if isinstance(cmd, (bytes, bytearray)):
                # raw binary write
                if hasattr(self.dev, "write_raw"):
                    self.dev.write_raw(cmd)
                else:
                    # fallback: write then newline
                    self.dev.write(cmd + b'\n')
            else:
                self.dev.write(str(cmd))
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to write command '{cmd}': {e}")

    def _query(self, cmd: str):
        try:
            return self.dev.query(cmd).strip()
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to query command '{cmd}': {e}")

    def _write_raw(self, data: bytes):
        """Low-level raw write for binary blocks (pyvisa write_raw preferred)."""
        try:
            if hasattr(self.dev, "write_raw"):
                self.dev.write_raw(data)
            else:
                self.dev.write(data + b'\n')
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to write raw data: {e}")

    def _to_float(self, v):
        """Convert possible remote proxies / numpy scalars to Python float."""
        try:
            return float(v)
        except Exception:
            try:
                import numpy as _np
                if isinstance(v, _np.generic):
                    return float(v.item())
            except Exception:
                pass
        raise SDG2042XParameterException(f"Cannot convert value to float: {v!r}")

    def _to_float_list(self, arr):
        """Convert array-like (possibly RPyC-proxied or numpy) to a plain Python list of floats."""
        try:
            import numpy as _np
            if isinstance(arr, _np.ndarray):
                # avoid object dtype proxies
                if arr.dtype == object:
                    return [self._to_float(x) for x in arr.tolist()]
                return [float(x) for x in arr.astype(float).tolist()]
        except Exception:
            pass

        try:
            return [self._to_float(x) for x in list(arr)]
        except Exception:
            # scalar -> single-item list
            return [self._to_float(arr)]

    # -----------------------------
    # Device identification & sample-rate mapping
    # -----------------------------
    def identify(self):
        return self._query("*IDN?")

    def _detect_model_sample_rate(self):
        """Set a conservative default sample rate. Prefer 75 MSa/s for TrueArb."""
        try:
            idn = self.identify()
        except Exception:
            idn = ""

        # Default mapping (conservative). Override via set_sample_rate()
        # We'll always default to TRUEARB_MAX_SRATE unless we have reason not to.
        self._sample_rate = TRUEARB_MAX_SRATE

    def set_sample_rate(self, sample_rate_hz: float):
        """Allow user to override the sample rate (enforced to <= TRUEARB_MAX_SRATE)."""
        s = float(sample_rate_hz)
        if s > TRUEARB_MAX_SRATE:
            s = TRUEARB_MAX_SRATE
        self._sample_rate = s

    # -----------------------------
    # Basic SCPI helpers
    # -----------------------------
    def factoryDefaults(self):
        self._write("*RST")

    def outputEnable(self, channel=1, polarity=1, load="HZ"):
        cmd = f"C{channel}:OUTP ON,LOAD,{load},PLTR,{'NOR' if polarity==1 else 'INVT'}"
        self._write(cmd)

    def outputDisable(self, channel=1):
        self._write(f"C{channel}:OUTP OFF")

    def setWaveType(self, waveform, channel=1):
        self._write(f"C{channel}:BSWV WVTP,{waveform}")

    def setWaveFrequency(self, frequency, channel=1):
        self._write(f"C{channel}:BSWV FRQ,{float(frequency)}")

    def setWaveAmplitude(self, vpp, channel=1):
        self._write(f"C{channel}:BSWV AMP,{float(vpp)}")

    def setWaveOffset(self, offsetV, channel=1):
        self._write(f"C{channel}:BSWV OFST,{float(offsetV)}")

    # -----------------------------
    # Simple pulse mode helpers (PLWV)
    # -----------------------------
    def selectPulseWaveform(self, channel=1):
        self._write(f"C{channel}:BSWV WVTP,PULSE")

    def setPulseWidth(self, width_s, channel=1):
        self._write(f"C{channel}:PLWV WIDTH,{float(width_s)}")

    def setPulseRiseTime(self, rise_s, channel=1):
        self._write(f"C{channel}:PLWV RISE,{float(rise_s)}")

    def setPulseFallTime(self, fall_s, channel=1):
        self._write(f"C{channel}:PLWV FALL,{float(fall_s)}")

    def setPulseLeadingDelay(self, delay_s, channel=1):
        self._write(f"C{channel}:PLWV DLY,{float(delay_s)}")

    # -----------------------------
    # Compatibility methods for high-level code
    # -----------------------------
    def stop(self):
        """Turn outputs off (both channels)."""
        try:
            self.outputDisable(1)
            self.outputDisable(2)
        except Exception:
            pass

    def start(self):
        """Turn outputs on (both channels)."""
        try:
            self.outputEnable(1, polarity=1, load="HZ")
            self.outputEnable(2, polarity=1, load="HZ")
        except Exception:
            pass

    def set_waveform_output(self, channel:int, state:bool):
        if state:
            self.outputEnable(channel, polarity=1, load="HZ")
        else:
            self.outputDisable(channel)

    # -----------------------------
    # ARB upload: ASCII fallback
    # -----------------------------
    def upload_arb_ascii(self, channel:int, name:str, waveform, normalize:bool=True):
        """
        Upload waveform as ASCII CSV to the AWG.
        waveform: array-like floats (will be normalized if normalize=True)
        """
        floats = self._to_float_list(waveform)
        try:
            import numpy as _np
            arr = _np.array(floats, dtype=float)
        except Exception:
            arr = [float(x) for x in floats]

        # convert to list of floats
        if hasattr(arr, "tolist"):
            vals = arr.tolist()
        else:
            vals = [float(x) for x in arr]

        npts = len(vals)
        if npts < 2:
            raise SDG2042XParameterException("Waveform too short for ASCII upload.")
        MAX_POINTS = 16000
        if npts > MAX_POINTS:
            raise SDG2042XVisaException(f"ASCII upload too long ({npts} pts). Use binary upload.")

        # normalize if requested
        if normalize:
            maxabs = max(abs(x) for x in vals) if npts else 1.0
            if maxabs != 0:
                vals = [x / maxabs for x in vals]

        csv_values = ','.join([f"{float(v):.9f}" for v in vals])
        # name slot
        self._write(f"C{channel}:WVDT 1,NAME,{name}")
        header = f"C{channel}:WVDT 1,DATA," + csv_values
        # Send in chunks if necessary
        if len(header) < 4000:
            self._write(header)
        else:
            start = 0; L = len(csv_values); chunk_size = 2000
            while start < L:
                end = min(start + chunk_size, L)
                if end < L:
                    comma = csv_values.rfind(',', start, end)
                    if comma > start:
                        end = comma
                chunk = csv_values[start:end]
                self._write(f"C{channel}:WVDT 1,DATA," + chunk)
                start = end + 1
        # try to load (firmware dependent)
        try:
            self._write(f"C{channel}:WVDT 1,LOAD")
        except Exception:
            pass

    # -----------------------------
    # ARB upload: Binary (preferred)
    # -----------------------------
    def upload_arb_binary(self, channel:int, name:str, waveform):
        """
        Upload a waveform as a binary block. waveform should be array-like floats in [-1..1].
        Converts to signed 16-bit ints and sends a definite-length binary block.
        """
        floats = self._to_float_list(waveform)
        try:
            import numpy as _np
            arr = _np.array(floats, dtype=float)
        except Exception:
            arr = [float(x) for x in floats]

        npts = len(arr)
        if npts < 2:
            raise SDG2042XParameterException("Waveform too short for binary upload.")
        MAX_POINTS = 16384
        if npts > MAX_POINTS:
            raise SDG2042XParameterException(f"Binary upload length {npts} exceeds {MAX_POINTS} samples.")

        # clip to [-1,1]
        try:
            import numpy as _np
            arr = _np.clip(arr, -1.0, 1.0)
            int_data = _np.int16((_np.round(arr * 32767.0)).astype(_np.int16))
            payload = int_data.tobytes()
        except Exception:
            # fallback: manual conversion
            int_vals = []
            for v in arr:
                f = float(v)
                if f < -1.0: f = -1.0
                if f > 1.0: f = 1.0
                int_vals.append(int(round(f * 32767.0)))
            payload = b''.join(int(v & 0xffff).to_bytes(2, 'little', signed=True) for v in int_vals)

        length = len(payload)
        len_digits = str(length)
        block_header = b'#' + str(len(len_digits)).encode('ascii') + len_digits.encode('ascii')

        # sample rate: use driver's _sample_rate if set
        sample_rate = float(self._sample_rate or TRUEARB_MAX_SRATE)

        # Build command prefix (mirrors working example style)
        prefix = (f"C{channel}:WVDT WVNM,{name},FREQ,{sample_rate:.1f},AMPL,1.0,OFST,0.0,PHASE,0.0,WAVEDATA,").encode('ascii')

        # Send prefix + binary block raw
        try:
            self._write_raw(prefix + block_header + payload + b'\n')
        except Exception as e:
            raise SDG2042XVisaException(f"Binary upload failed: {e}")

        # Register ARB name if required
        try:
            self._write(f"C{channel}:ARWV NAME,{name}")
        except Exception:
            pass

    # -----------------------------
    # Select ARB and convenience wrapper
    # -----------------------------
    def set_arb_mode(self, channel:int, name:str):
        """Select the previously uploaded ARB by name for channel playback."""
        try:
            # Select by ARWV NAME then ensure waveform type ARB is selected
            self._write(f"C{channel}:ARWV NAME,{name}")
            self._write(f"C{channel}:BSWV WVTP,ARB")
            # firmware variants may support WVNM
            try:
                self._write(f"C{channel}:BSWV WVNM,{name}")
            except Exception:
                pass
        except Exception:
            pass

    def load_waveform(self, channel:int, waveform, name_prefix="USR_ARB"):
        """
        Top-level wrapper used by higher-level code.
        waveform: list/array of floats (voltages, 0..Vpp desired) — we normalize to [-1..1].
        Chooses binary upload for >2000 points otherwise ASCII.
        Returns generated waveform name.
        """
        floats = self._to_float_list(waveform)
        try:
            import numpy as _np
            arr = _np.array(floats, dtype=float)
        except Exception:
            arr = [float(x) for x in floats]

        npts = len(arr)
        if npts < 2:
            raise SDG2042XParameterException("Waveform too short to load.")

        # Normalize: the high-level code uses volt amplitudes (0..5). We normalize to -1..1 by dividing by maxabs
        maxabs = max(abs(x) for x in arr) if npts else 1.0
        if maxabs == 0:
            norm = [0.0] * npts
        else:
            norm = [float(x) / float(maxabs) for x in arr]

        name = f"{name_prefix}_CH{channel}_{int(time.time()*1000)}"

        # pick upload method
        if npts > 2000:
            self.upload_arb_binary(channel, name, norm)
        else:
            self.upload_arb_ascii(channel, name, norm, normalize=False)

        # select and store
        self.set_arb_mode(channel, name)
        self._user_arbs[channel] = name
        return name

    def configure_arb_output(self, channel:int, amplitude_vpp:float=1.0, offset_v:float=0.0, period_s:float=None):
        """Set amplitude and offset for the channel; optionally set repetition period."""
        self.setWaveAmplitude(amplitude_vpp, channel)
        self.setWaveOffset(offset_v, channel)
        if period_s is not None:
            # set burst period for repetition
            self._write(f"C{channel}:BTWV PRD,{float(period_s)}")

    # -----------------------------
    # Cleanup
    # -----------------------------
    def close(self):
        try:
            self.dev.close()
        except Exception:
            pass

