# -*- coding: utf-8 -*-
"""
Created on Wed Dec 10 15:42:22 2025

@author: George Fratian
"""

import numpy as np
import struct
# from piec.drivers.awg import awg
# from piec.drivers import scpi
import pyvisa
# import time

TRUEARB_MAX_SRATE = 75_000_000.0  # 75 MSa/s hardware ceiling (TrueArb)

class SDG2042XVisaException(Exception):
    pass

class SDG2042XParameterException(Exception):
    pass

class SDG2000X():
    """
    Driver for the Siglent SDG2000X Series Arbitrary Waveform Generator.
    Based on the Programming Guide PG02-E03B.
    """

    # --- AUTODETECT IDENTIFIER ---
    # Derived from *IDN? response examples in the manual.
    # The manual explicitly lists responses for these models in the examples[cite: 198, 1407, 1467].
    AUTODETECT_ID = ["SDG2042X", "SDG2122X", "SDG2102X"]

    # --- INSTRUMENT PARAMETERS ---
    
    # Channel: The manual specifies C1 and C2[cite: 318].
    channel = [1, 2]

    # Waveform: Mapped from manual types SINE, SQUARE, RAMP, PULSE, NOISE, ARB, DC, PRBS[cite: 328].
    waveform = ['SIN', 'SQU', 'RAMP', 'PULS', 'NOIS', 'DC', 'USER', 'PRBS']

    # Frequency: Manual refers to the data sheet for valid ranges[cite: 328].
    frequency = {
        'func': {
            'SIN': (None, None), 
            'SQU': (None, None), 
            'RAMP': (None, None), 
            'PULS': (None, None), 
            'NOIS': (None, None), 
            'DC': (None, None), 
            'USER': (None, None),
            'PRBS': (None, None)
        }
    }

    # Amplitude: Manual refers to the data sheet for valid ranges[cite: 328].
    amplitude = (None, None)
    
    # Offset: Manual refers to the data sheet for valid ranges[cite: 328].
    offset = (None, None)

    # Load Impedance: Manual lists 50 to 100000 Hz for SDG2000X[cite: 321].
    load_impedance = (50, 100000)

    # Source Impedance: Not specified as a settable parameter in the OUTPUT command[cite: 318].
    source_impedance = None

    # Polarity: Manual lists NOR (Normal) and INVT (Invert)[cite: 318].
    polarity = ['NORM', 'INV']

    # Duty Cycle: Manual lists 0 to 100%[cite: 328].
    duty_cycle = (0.0, 100.0)

    # Symmetry: Manual lists 0 to 100%[cite: 328].
    symmetry = (0.0, 100.0)

    # Pulse Width: Manual refers to the data sheet[cite: 328].
    pulse_width = (None, None)
    
    # Pulse Delay: Manual refers to the data sheet[cite: 337].
    pulse_delay = (None, None)

    # Rise/Fall Time: Manual refers to the data sheet[cite: 328, 337].
    rise_time = (None, None)
    fall_time = (None, None)

    # Trigger Source: Manual lists EXT, INT, MAN[cite: 463].
    trigger_source = ['INT', 'EXT', 'MAN']

    # Trigger Slope: Manual lists RISE, FALL[cite: 463].
    trigger_slope = ['POS', 'NEG']

    # Trigger Mode: Manual lists GATE and NCYC[cite: 463].
    # Mapped to 'LEV' (Level/Gated) and 'EDGE' (Cycle/Edge).
    trigger_mode = ["EDGE", "LEV"] 

    # Arb Data Range: Manual specifies 16B - 16MB for SDG2000X[cite: 715].
    arb_data_range = (16, 16777216)

    def __init__(self, visa_address: str = "USB0::0xF4EC::0x1102::SDG2XFBC900189::INSTR"):
        self.visa_address = visa_address
        rm = pyvisa.ResourceManager()
        try:
            self.instrument = rm.open_resource(visa_address)
            self.instrument.timeout = 20000
            self.instrument.write_termination = '\n'
            self.instrument.read_termination = '\n'
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to open VISA instrumentice {visa_address}: {e}")

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
                if hasattr(self.instrument, "write_raw"):
                    self.instrument.write_raw(cmd)
                else:
                    # fallback: write then newline
                    self.instrument.write(cmd + b'\n')
            else:
                self.instrument.write(str(cmd))
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to write command '{cmd}': {e}")

    def _query(self, cmd: str):
        try:
            return self.instrument.query(cmd).strip()
        except Exception as e:
            raise SDG2042XVisaException(f"Failed to query command '{cmd}': {e}")

    def _write_raw(self, data: bytes):
        """Low-level raw write for binary blocks (pyvisa write_raw preferred)."""
        try:
            if hasattr(self.instrument, "write_raw"):
                self.instrument.write_raw(data)
            else:
                self.instrument.write(data + b'\n')
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
    # instrumentice identification & sample-rate mapping
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

    def set_sample_rate(self, sample_rate: float = 75e6):
        """Allow user to override the sample rate (enforced to <= TRUEARB_MAX_SRATE)."""
        s = float(sample_rate)
        if s > TRUEARB_MAX_SRATE:
            s = TRUEARB_MAX_SRATE
        self._sample_rate = s

    # -----------------------------
    # Pulse Settings 
    # -----------------------------

    def set_arb_mode(self, channel: int, state: str = "ON", sample_rate: int = 75e6):
        """
          This function should be called at the beginning of any measurement 
          that uses a user-defined pulse sequence
        """
        self.instrument.write(f"C{channel}:BSWV STATE,{state}")   # turn on channel
        self.instrument.write(f"C{channel}:BSWV WVTP,ARB")   # turn on Arb mode 
        self.instrument.write(f"C{channel}:SRATE MODE,TARB")   # force TrueArb mode
        self.instrument.write(f"C{channel}:SRATE VALUE,{sample_rate}")  # set the maximum sample rate


    def set_burst_mode(self, channel: int, enable: bool = True):
        """
        Enable or disable Burst mode on a given channel.
        Args:
            channel: 1 or 2
            enable: True = Burst ON, False = Burst OFF
        """

        if channel not in self.channel:
            raise ValueError(f"Invalid channel {channel}. Must be 1 or 2.")

        state = "ON" if enable else "OFF"
        self.instrument.write(f"C{channel}:BTWV STATE,{state}")
        self.instrument.write(f"C{channel}:BTWV TRSR,INT")
        self.instrument.write(f"C{channel}:BTWV NCYC,1")
        if channel == 2:    
            self.instrument.write(f"C{channel}:BTWV TRMD,RISE")
        else:
            self.instrument.write(f"C{channel}:BTWV TRMD,OFF")


    # Doesn't work at the moment unfortunately :-(
    def set_burst_trigger(
                self,
                channel: int,
                enable: bool = True,
                state: str = "ON",
                source: str = "INT",
                shape: str = "RISE",
                delay: float = 0.0,
                ):
            """
            Configure the trigger used during BURST mode and the Trig Out (AUX) behavior.            
            Args:
                channel: 1 or 2
                enable: Enable or disable burst triggering for this channel
                source: Trigger source: "INT", "EXT", or "MAN"
                shape: Trigger output shape: "POS" (Up), "NEG" (Down), or "OFF"
                delay: Trigger output delay in seconds
            """

            # --- Channel validation ---
            if channel not in self.channel:
                raise ValueError(f"Invalid channel {channel}. Must be 1 or 2.")
            if source not in {"INT", "EXT", "MAN"}:
                raise ValueError("source must be 'INT', 'EXT', or 'MAN'")
            if shape not in {"RISE", "FALL", "OFF"}:
                raise ValueError("shape must be 'RISE', 'FALL', or 'OFF'")
            if delay < 0:
                raise ValueError("delay must be >= 0")

            # --- 1) Enable / disable burst trigger for THIS CHANNEL ---
            state = "ON" if enable else "OFF"
            self.instrument.write(f"C{channel}:BTWV TRIG,{state}")
            
            # --- 2) Configure trigger source for THIS CHANNEL ---
            # (what starts the burst)
            self.instrument.write(f"C{channel}:BTWV TRSR,{source}")
            
            # --- 3) Configure Trig Out (AUX) ---
            # (what is emitted during burst events)
            self.instrument.write(f"C{channel}:BTWV CARR {shape}")
            self.instrument.write(f"C{channel}:BTWV DLAY {delay}")


    def output(self, channel, on=True):
        """
        Turns the output of a specified channel on or off[cite: 318].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")
        
        state = "ON" if on else "OFF"
        self.instrument.write(f"C{channel}:OUTP {state}")


    def set_waveform(self, channel, waveform):
        """
        Sets the built_in waveform type[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        mapping = {
            'SIN': 'SINE', 'SQU': 'SQUARE', 'RAMP': 'RAMP',
            'PULS': 'PULSE', 'NOIS': 'NOISE', 'DC': 'DC',
            'USER': 'ARB', 'PRBS': 'PRBS'
        }
        
        if waveform not in mapping:
             raise ValueError(f"Invalid waveform. Must be one of {list(mapping.keys())}")

        # Defensive programming
        self.instrument.write(f"C{channel}:OUTP OFF")
        self.instrument.write(f"C{channel}:BSWV STATE,ON")
        self.instrument.write(f"C{channel}:BSWV WVTP,{mapping[waveform]}")
        self.instrument.write(f"C{channel}:OUTP ON")

    def set_frequency(self, channel, frequency):
        """
        Sets the frequency of the waveform[cite: 328] in units of Hz.
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")
        
        self.instrument.write(f"C{channel}:BSWV FRQ,{frequency}")

    def set_amplitude(self, channel, amplitude):
        """
        Sets the amplitude (Vpp)[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV AMP,{amplitude}")

    def set_offset(self, channel, offset):
        """
        Sets the offset voltage[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV OFST,{offset}")

    def set_load_impedance(self, channel, load_impedance):
        """
        Sets the output load impedance[cite: 318, 321].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:OUTP LOAD,{load_impedance}")

    def set_polarity(self, channel, polarity):
        """
        Sets the output polarity[cite: 318].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        mapping = {'NORM': 'NOR', 'INV': 'INVT'}
        if polarity not in mapping:
            raise ValueError(f"Invalid polarity. Must be one of {list(mapping.keys())}")

        self.instrument.write(f"C{channel}:OUTP PLRT,{mapping[polarity]}")

    def set_square_duty_cycle(self, channel, duty_cycle):
        """
        Sets the duty cycle for Square waves[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV DUTY,{duty_cycle}")

    def set_ramp_symmetry(self, channel, symmetry):
        """
        Sets the symmetry for Ramp waves[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV SYM,{symmetry}")

    def set_pulse_width(self, channel, pulse_width):
        """
        Sets the positive pulse width[cite: 328] in units of seconds.
        e.g., 100 ns == 1e-7
        User must ensure the pulse width does not exceed 1/frequency
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")
        self.instrument.write(f"C{channel}:BSWV WIDTH,{pulse_width}")

    def set_pulse_rise_time(self, channel, rise_time):
        """
        Sets the rise time for Pulse waves[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV RISE,{rise_time}")

    def set_pulse_fall_time(self, channel, fall_time):
        """
        Sets the fall time for Pulse waves[cite: 337].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV FALL,{fall_time}")

    def set_pulse_duty_cycle(self, channel, duty_cycle):
        """
        Sets the duty cycle for Pulse waves[cite: 328].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV DUTY,{duty_cycle}")

    def set_pulse_delay(self, channel, pulse_delay):
        """
        Sets the pulse delay[cite: 337].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        self.instrument.write(f"C{channel}:BSWV DLY,{pulse_delay}")

#######################################################################

######## PULSE SHAPING AND GENERATION
######## NOTE: NOT USED FOR ODMR. INSTEAD USE FUNCTION IN ODMR_DRIVER

########################################################################

    def create_arb_waveform(self, channel, name, data):
        """
        Creates/Downloads an arbitrary waveform to the instrument[cite: 697, 715, 1549].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")
        
        # Convert data to binary (Little endian, 16-bit 2's complement) as per Python Example 4.1.5
        # Example 4.1.5 converts values to hex strings then bytes, but direct packing is more efficient.
        if isinstance(data, (list, tuple, np.ndarray)):
            # Ensure data consists of integers
            data = [int(x) for x in data]
            binary_data = b''.join([struct.pack('<h', x) for x in data])
        else:
            binary_data = data 

        # Construct header command. 
        # Example 4.1.5 uses: C1:WVDT WVNM,wave1, ... WAVEDATA,<data>
        cmd_header = f"C{channel}:WVDT WVNM,{name},WAVEDATA,"
        
        # Send raw command with binary data appended
        self.instrument.write_raw(cmd_header.encode('ascii') + binary_data)

    def set_arb_waveform(self, channel, name):
        """
        Selects an arbitrary waveform by name[cite: 501].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")
        self.instrument.write(f"C{channel}:ARWV NAME,{name}")

    def set_trigger_source(self, channel, trigger_source):
        """
        Sets the trigger source for Burst/Sweep modes[cite: 463].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        mapping = {'INT': 'INT', 'EXT': 'EXT', 'MAN': 'MAN'}
        if trigger_source not in mapping:
             raise ValueError(f"Invalid trigger source. Must be one of {list(mapping.keys())}")
        
        self.instrument.write(f"C{channel}:BTWV TRSR,{mapping[trigger_source]}")

    def set_trigger_slope(self, channel, trigger_slope):
        """
        Sets the trigger edge (slope)[cite: 463].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        mapping = {'POS': 'RISE', 'NEG': 'FALL'}
        if trigger_slope not in mapping:
            raise ValueError(f"Invalid trigger slope. Must be one of {list(mapping.keys())}")

        self.instrument.write(f"C{channel}:BTWV EDGE,{mapping[trigger_slope]}")

    def set_trigger_mode(self, channel, trigger_mode):
        """
        Sets the burst mode (Gated or Cycle) which corresponds to Level or Edge triggering[cite: 463].
        """
        if channel not in self.channel:
            raise ValueError(f"Invalid channel. Must be one of {self.channel}")

        mapping = {'EDGE': 'NCYC', 'LEV': 'GATE'}
        if trigger_mode not in mapping:
             raise ValueError(f"Invalid trigger mode. Must be one of {list(mapping.keys())}")

        self.instrument.write(f"C{channel}:BTWV GATE_NCYC,{mapping[trigger_mode]}")

    def output_trigger(self):
        """
        Sends a manual trigger signal[cite: 446].
        Defaulting to Channel 1 as this is a instrumentice-action.
        """
        self.instrument.write(f"C1:BTWV MTRIG")
