# -*- coding: utf-8 -*-
"""
Created on Thu May 21 11:20:07 2026

@author: ODMR_user + ChatGPT
"""

# -*- coding: utf-8 -*-
"""
Created on Thu May 21 2026

Python driver for Hittite / Analog Devices HMC-T2100 Signal Generator

@author: ODMR_user
"""

import pyvisa


class _HMCT2100:
    """
    Python VISA driver for the HMC-T2100 microwave signal generator.

    This driver is intentionally structured to mirror the SG396 driver API
    as closely as possible for easy drop-in replacement.
    """

    def __init__(self, visa_address: str):
        self.visa_address = visa_address

        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(visa_address)

        self.inst.timeout = 5000
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'

        # Check identity
        idn = self.get_idn()

        if "HMC" not in idn.upper() and "HITTITE" not in idn.upper():
            raise ValueError(f"Unexpected device ID: {idn}")

        print(f"Connected to: {idn}")

    # ------------------------------------------------------------------
    # Connection Methods
    # ------------------------------------------------------------------

    def connect(self):
        """Connect to instrument if not already connected."""

        if self.inst is not None:
            print(f"Already connected to {self.visa_address}")
            return

        self.rm = pyvisa.ResourceManager()

        self.inst = self.rm.open_resource(self.visa_address)

        self.inst.timeout = 5000
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'

        print(f"Connected to HMC-T2100 at {self.visa_address}")

    def disconnect(self):
        """Close VISA connection."""

        if self.inst:
            self.inst.close()
            self.inst = None
            print("HMC-T2100 disconnected.")

    def close(self):
        """Fully close VISA session."""

        if self.inst:
            self.inst.close()

        if self.rm:
            self.rm.close()

        print("Connection closed.")

    # ------------------------------------------------------------------
    # Basic SCPI Commands
    # ------------------------------------------------------------------

    def get_idn(self) -> str:
        """Read instrument identity."""
        return self.inst.query("*IDN?")

    def reset(self):
        """Reset instrument."""
        self.inst.write("*RST")

    def clear_status(self):
        """Clear status and error queue."""
        self.inst.write("*CLS")

    # ------------------------------------------------------------------
    # Frequency Control
    # ------------------------------------------------------------------

    def set_frequency(self, freq_hz: float):
        """
        Set CW frequency in Hz.
        """

        if freq_hz <= 0:
            raise ValueError("Frequency must be positive.")

        self.inst.write(f"FREQ:CW {freq_hz}")

    def get_frequency(self) -> float:
        """
        Get CW frequency in Hz.
        """

        return float(self.inst.query("FREQ:CW?"))

    # ------------------------------------------------------------------
    # Power / Amplitude Control
    # ------------------------------------------------------------------

    def set_amplitude(self, amplitude_dbm: float):
        """
        Set RF output power in dBm.
        """

        self.inst.write(f"POW:LEV {amplitude_dbm}")

    def get_amplitude(self) -> float:
        """
        Get RF output power in dBm.
        """

        return float(self.inst.query("POW:LEV?"))

    # Alias methods to mimic SG396 naming
    def set_amplitude_rf(self, amplitude_dbm: float):
        self.set_amplitude(amplitude_dbm)

    def get_amplitude_rf(self) -> float:
        return self.get_amplitude()

    # ------------------------------------------------------------------
    # RF Output Control
    # ------------------------------------------------------------------

    def set_output(self, state: bool):
        """
        Enable or disable RF output.
        """

        if state:
            self.inst.write("OUTP ON")
        else:
            self.inst.write("OUTP OFF")

    def get_output(self) -> bool:
        """
        Return True if RF output is ON.
        """

        return self.inst.query("OUTP?").strip() in ["1", "ON"]

    # ------------------------------------------------------------------
    # Error Handling
    # ------------------------------------------------------------------

    def check_errors(self):
        """
        Read error queue until empty.
        """

        errors = []

        while True:
            err = self.inst.query("SYST:ERR?")

            if err.startswith("0"):
                break

            errors.append(err)

        return errors

    # ------------------------------------------------------------------
    # Modulation Subclass
    # ------------------------------------------------------------------

    class Modulation:
        """
        Modulation control class.

        Usage:
            mod = sg.Modulation(sg)
        """

        def __init__(self, parent):
            self.parent = parent

        # --------------------------------------------------------------
        # Modulation Enable
        # --------------------------------------------------------------

        def enable(self, state: bool):
            """
            Enable or disable modulation.
            """

            if state:
                self.parent.inst.write("MOD:STAT ON")
            else:
                self.parent.inst.write("MOD:STAT OFF")

        def is_enabled(self) -> bool:
            """
            Return True if modulation is enabled.
            """

            return self.parent.inst.query("MOD:STAT?").strip() in ["1", "ON"]

        # --------------------------------------------------------------
        # Modulation Type
        # --------------------------------------------------------------

        def set_type(self, mod_type: str):
            """
            Set modulation type.

            Supported examples:
                'AM'
                'FM'
                'PM'
                'PULSE'
                'IQ'
            """

            valid_types = ['AM', 'FM', 'PM', 'PULSE', 'IQ']

            mod_type = mod_type.upper()

            if mod_type not in valid_types:
                raise ValueError(f"Invalid modulation type: {mod_type}")

            self.parent.inst.write(f"MOD:TYPE {mod_type}")

        def get_type(self) -> str:
            """
            Get current modulation type.
            """

            return self.parent.inst.query("MOD:TYPE?").strip()

        # --------------------------------------------------------------
        # Modulation Source
        # --------------------------------------------------------------

        def set_source(self, source: str):
            """
            Set modulation source.

            Examples:
                'INT'
                'EXT'
            """

            self.parent.inst.write(f"MOD:SOUR {source.upper()}")

        def get_source(self) -> str:
            """
            Get modulation source.
            """

            return self.parent.inst.query("MOD:SOUR?").strip()

        # --------------------------------------------------------------
        # AM Depth
        # --------------------------------------------------------------

        def set_depth(self, percent: float):
            """
            Set AM depth percentage.
            """

            self.parent.inst.write(f"AM:DEPTH {percent}")

        def get_depth(self) -> float:
            """
            Get AM depth percentage.
            """

            return float(self.parent.inst.query("AM:DEPTH?"))

        # --------------------------------------------------------------
        # FM Deviation
        # --------------------------------------------------------------

        def set_deviation(self, deviation_hz: float):
            """
            Set FM deviation in Hz.
            """

            self.parent.inst.write(f"FM:DEV {deviation_hz}")

        def get_deviation(self) -> float:
            """
            Get FM deviation in Hz.
            """

            return float(self.parent.inst.query("FM:DEV?"))

        # --------------------------------------------------------------
        # Internal Modulation Frequency
        # --------------------------------------------------------------

        def set_mod_frequency(self, freq_hz: float):
            """
            Set internal modulation frequency.
            """

            if freq_hz <= 0:
                raise ValueError("Modulation frequency must be positive.")

            self.parent.inst.write(f"MOD:FREQ {freq_hz}")

        def get_frequency(self) -> float:
            """
            Get internal modulation frequency.
            """

            return float(self.parent.inst.query("MOD:FREQ?"))


# ----------------------------------------------------------------------
# Example Usage
# ----------------------------------------------------------------------

if __name__ == "__main__":

    # Replace with actual VISA resource
    sg = _HMCT2100("TCPIP0::192.168.0.10::inst0::INSTR")

    try:

        # Basic CW operation
        sg.set_frequency(2.87e9)
        sg.set_amplitude(-10)
        sg.set_output(True)

        print(f"Frequency: {sg.get_frequency()} Hz")
        print(f"Amplitude: {sg.get_amplitude()} dBm")
        print(f"Output Enabled: {sg.get_output()}")

        # Modulation Example
        mod = sg.Modulation(sg)

        mod.enable(True)
        mod.set_type("FM")
        mod.set_deviation(1e6)
        mod.set_mod_frequency(1000)

        print(f"Modulation Type: {mod.get_type()}")
        print(f"FM Deviation: {mod.get_deviation()} Hz")

        # Check errors
        errors = sg.check_errors()

        if errors:
            print("Errors:")
            for err in errors:
                print(err)

    finally:

        sg.set_output(False)
        sg.close()