# -*- coding: utf-8 -*-
"""
Created on Wed Nov  5 13:43:14 2025

@author: ODMR_user
"""

from nspyre import InstrumentGateway

gw = InstrumentGateway()

sg   = gw.sg            # SRS SG396
mfli = gw.mfli          # Zurich Instruments MFLI
odmr = gw.odmr_driver   # Your ODMR driver

sg.connect()

from zhinst.toolkit import Session
from zhinst.core.errors import DeviceInUseError

def connect(self):
    """Connect to the MFLI via Zurich Instruments Toolkit, with safe reconnect."""
    import zhinst.toolkit as tk
    from zhinst.core import errors

    # Create session if not already created
    if not hasattr(self, "_tk_session") or self._tk_session is None:
        self._tk_session = tk.Session(self.host)

    # If we already have a connected device, skip reconnect
    if hasattr(self, "_tk_dev") and self._tk_dev is not None:
        try:
            # Ping device
            _ = self._tk_dev.system
            print(f"{self.serial} already connected.")
            return
        except Exception:
            print("Previous connection invalid, reconnecting...")

    # Attempt to connect, with fallback if already in use
    try:
        self._tk_dev = self._tk_session.connect_device(self.serial, interface=self.interface)
        print(f"Connected to {self.serial}")
    except errors.DeviceInUseError:
        print(f"{self.serial} already in use, attempting force disconnect...")

        # Try to forcibly disconnect the device via the underlying daq_server
        try:
            self._tk_session._connection._core.daq_server.disconnectDevice(self.serial)
            print(f"Force released {self.serial}")
        except Exception as e:
            print(f"Warning: could not force release {self.serial}: {e}")

        # Try reconnecting again
        self._tk_dev = self._tk_session.connect_device(self.serial, interface=self.interface)
        print(f"Reconnected to {self.serial}")


# Then connect
mfli.connect()

# -------------------------------------------------------------------------
# 1️⃣ Configure the microwave source and lock-in reference
# -------------------------------------------------------------------------

# Make sure MFLI is ready to detect the AWG modulation
print("Configuring MFLI and SG396...")

# set microwave amplitude (in dBm)
odmr.set_mw_amplitude(-10.0)

# Set the sweep parameters
odmr.start_hz = 2.75e8
odmr.stop_hz  = 3.05e9
odmr.step_hz  = 5e6
odmr.dwell    = 0.05
odmr.average  = 10

print(f"Sweeping from {odmr.start_hz/1e9:.3f} to {odmr.stop_hz/1e9:.3f} GHz "
      f"in {odmr.step_hz/1e6:.1f} MHz steps...")

# -------------------------------------------------------------------------
# 2️⃣ Run the sweep
# -------------------------------------------------------------------------
print("Running ODMR sweep...")
df = odmr.run_and_plot()

# Optionally save the data
df.to_csv('odmr_sweep.csv', index=False)
print("Sweep complete. Data saved as 'odmr_sweep.csv'.")

# -------------------------------------------------------------------------
# 3️⃣ Cleanup
# -------------------------------------------------------------------------
print("Turning off SG396 output...")
sg.set_output(0)

print("Done ✅")