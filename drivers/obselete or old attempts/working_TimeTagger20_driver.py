# -*- coding: utf-8 -*-
"""
Created on Fri Oct 10 16:06:12 2025

@author: ODMR_user
"""

import pyvisa

class _SG396:
    def __init__(self, resource_name: str):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(resource_name)
        self.inst.timeout = 5000  # 5 seconds timeout
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'

        # Check identity
        idn = self.get_idn()
        if "SG396" not in idn:
            raise ValueError(f"Unexpected device ID: {idn}")
        print(f"Connected to: {idn}")
        
    visa_address = "ASRL8::INSTR"
    
    def connect(self):
        import pyvisa
        if self.inst is not None:
            print(f"Already connected to {self.visa_address}")
            return

        rm = pyvisa.ResourceManager()
        visa_address = "ASRL8::INSTR"
        self.inst = rm.open_resource(self.visa_address)
        self.inst.timeout = 5000
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'
        print(f"Connected to SG396 at {self.visa_address}")

    def disconnect(self):
        """Close VISA connection."""
        if self.inst:
            self.inst.close()
            self.inst = None
            print("SG396 disconnected.")

    def get_idn(self) -> str:
        return self.inst.query("*IDN?")

    def reset(self):
        self.inst.write("*RST")

    def clear_status(self):
        self.inst.write("*CLS")

    def set_frequency(self, freq_hz: float):
        """Set frequency in Hz."""
        self.inst.write(f"FREQ {freq_hz:.6f}")

    def get_frequency(self) -> float:
        """Get current frequency in Hz."""
        return float(self.inst.query("FREQ?"))

    def set_amplitude_rf(self, amplitude_dbm: float):
        """Set output amplitude in dBm from N-type > 62.5 MHz."""
        self.inst.write(f"AMPR {amplitude_dbm:.2f}")

    def set_amplitude_lf(self, amplitude_dbm: float):
        """Set output amplitude in dBm from BNC < 62.5 MHz."""
        self.inst.write(f"AMPL {amplitude_dbm:.2f}")

    def get_amplitude_rf(self) -> float:
        """Get current amplitude in dBm."""
        return float(self.inst.query("AMPR?"))

    def get_amplitude_lf(self) -> float:
        """Get current amplitude in dBm."""
        return float(self.inst.query("AMPL?"))

    def set_output(self, state):
        """Enable (True) or disable (False) the RF output."""
        "for some reason this doesn't do anything at the moment"
        self.inst.write(f"ENBR {state: .2f}")

    def get_output(self) -> bool:
        """Check if RF output is ON (True) or OFF (False)."""
        return self.inst.query("ENBR?").strip() == "1"

    def close(self):
        """Close the VISA session."""
        self.inst.close()
        self.rm.close()
        print("Connection closed.")

    def check_errors(self):
        """Query error queue."""
        errors = []
        while True:
            err = self.inst.query("INSE?")
            if '0,"No error"' in err:
                break
            errors.append(err)
        return errors

# ------------------------
    # Inner class: Modulation
# ------------------------
class Modulation(_SG396):
    
    def __init__(self, parent):
        self.parent = parent  # reference to SG396

    def enable(self, state: bool):
        """Enable or disable modulation."""
        self.parent.inst.write(f"MOD:STAT {'ON' if state else 'OFF'}")

    def is_enabled(self, state: bool):
       """Return True if modulation is enabled."""
       return self.parent.inst.query("MOD:STAT?").strip() == "1"

    def set_type(self, mod_type: str):
       """
       Set modulation type.

       mod_type: 'AM', 'FM', 'PM', 'PULM', 'FSK', 'ASK'
       """
       valid_types = ['AM', 'FM', 'PM', 'PULM', 'FSK', 'ASK']
       mod_type = mod_type.upper()
       if mod_type not in valid_types:
           raise ValueError(f"Invalid modulation type: {mod_type}")
           self.parent.inst.write(f"MOD:TYPE {mod_type}")

    def get_type(self) -> str:
        return self.parent.inst.query("MOD:TYPE?").strip()

    def set_source(self, source: str):
        """
        Set modulation source.

        source: 'INT', 'EXT', 'EXT2', 'INT2', etc.
        """
        self.parent.inst.write(f"MOD:SOUR {source.upper()}")

    def get_source(self) -> str:
        return self.parent.inst.query("MOD:SOUR?").strip()

    def set_depth(self, percent: float):
        """Set AM depth (only applicable when AM is selected)."""
        self.parent.inst.write(f"AM:DEPTH {percent:.1f}")

    def get_depth(self) -> float:
        return float(self.parent.inst.query("AM:DEPTH?"))

    def set_deviation(self, deviation: float):
        """Set FM deviation in Hz (only when FM is selected)."""
        self.parent.inst.write(f"FM:DEV {deviation}")

    def get_deviation(self) -> float:
        return float(self.parent.inst.query("FM:DEV?"))


# Example usage
if __name__ == "__main__":
    # Replace with your actual VISA resource address, e.g., 'USB0::0x0A8D::0x0050::123456::INSTR'
    sg = _SG396("ASRL8::INSTR")
    try:
        sg.set_frequency(100e6)  # 1 MHz
        sg.set_amplitude_rf(-10)  # -10 dBm
        sg.set_output(0)

        print(f"Frequency: {sg.get_frequency()} Hz")
        print(f"Amplitude: {sg.get_amplitude_rf()} dBm")
        print(f"Output Enabled: {sg.get_output()}")
#        print(f"Errors: {sg.check_errors()}")

    finally:
        sg.set_output(False)
#       sg.close()