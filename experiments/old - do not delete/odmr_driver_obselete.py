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
import pandas as pd
import matplotlib.pyplot as plt
from typing import Iterable, Optional

from nspyre import InstrumentGateway


class _odmr_driver:
    """
    NSpyre-compatible ODMR driver that auto-connects to existing instruments
    running on the instrument server.
    """

    def __init__(self,
                 siggen_name: str = 'sg',
                 mfli_name: str = 'mfli',
                 modulation_freq_hz: float = 150.0,
                 mw_amplitude_dbm: float = -10.0,
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

        self.modulation_freq_hz = modulation_freq_hz
        self.mw_amplitude_dbm = mw_amplitude_dbm
        self.step_hz = step_hz
        self.start_hz = start_hz
        self.stop_hz = stop_hz
        self.dwell = dwell
        self.average = max(1, int(average))

    # -------------------------------------------------------------------------
    # (Future AWG code commented out)
    # -------------------------------------------------------------------------
    # def prepare_modulation(self, amplitude_volt: float = 1.0, duty: float = 0.5):
    #     self.awg.set_square(self.modulation_freq_hz, amplitude_volt, offset=0.0, duty=duty)
    #     self.awg.start()
    #     self.mfli.set_reference(self.modulation_freq_hz, source="external")
    #     time.sleep(0.1)

    # def stop_modulation(self):
    #     self.awg.stop()

    # -------------------------------------------------------------------------
    # Core functions
    # -------------------------------------------------------------------------
    def set_mw_amplitude(self, amplitude_dbm: float):
        """Set microwave amplitude on SG396."""
        self.sg.set_amplitude_rf(amplitude_dbm)
        self.mw_amplitude_dbm = amplitude_dbm

    def set_output(self, state):
        """Set microwave amplitude on SG396."""
        self.sg.set_output(state)


    def single_point_read(self):
        """Read and average MFLI demodulator samples."""
        x_vals, y_vals, r_vals, phase_vals = [], [], [], []
        for _ in range(self.average):
            x, y, r, phase = self.mfli.get_demod_sample(0)
            x_vals.append(x)
            y_vals.append(y)
            r_vals.append(r)
            phase_vals.append(phase)
            if self.average > 1:
                time.sleep(0.002)

        return {
            "x": np.nanmean(x_vals),
            "y": np.nanmean(y_vals),
            "r": np.nanmean(r_vals),
            "phase": np.nanmean(phase_vals),
        }

    def sweep(self,
              frequencies: Optional[Iterable[float]] = None,
              settle: Optional[float] = None,
              progress_callback=None):
        """Sweep microwave frequency and read MFLI output."""
        if frequencies is None:
            freqs = np.arange(self.start_hz,
                              self.stop_hz + self.step_hz,
                              self.step_hz,
                              dtype=np.float64)
        else:
            freqs = np.array(list(frequencies), dtype=np.float64)

        settle_time = self.dwell if settle is None else settle
        rows = []
        total = len(freqs)

        for i, f in enumerate(freqs):
            self.sg.set_frequency(f)
            self.sg.set_amplitude_rf(self.mw_amplitude_dbm)
            self.sg.set_output(1)

            if progress_callback:
                progress_callback(i + 1, total, f)

            time.sleep(settle_time)

            samp = self.single_point_read()
            rows.append({"frequency_hz": f, **samp})

        return pd.DataFrame(rows)

    def run_and_plot(self,
                     frequencies: Optional[Iterable[float]] = None,
                     settle: Optional[float] = None,
                     show_plot: bool = True,
                     save_path: Optional[str] = None,
                     progress_callback=None):
        """Convenience: run sweep and plot result."""
        df = self.sweep(frequencies, settle, progress_callback)

        if show_plot:
            plt.figure(figsize=(8, 4))
            if 'r' in df.columns:
                plt.plot(df['frequency_hz'] / 1e9, df['r'], marker='o', linestyle='-')
                plt.xlabel('Frequency (GHz)')
                plt.ylabel('Lock-in R (V)')
                plt.title('CW-ODMR Frequency Sweep')
                plt.grid(True)
            else:
                plt.plot(df['frequency_hz'] / 1e9, df['x'], marker='o')
                plt.xlabel('Frequency (GHz)')
                plt.ylabel('Lock-in X (V)')
                plt.grid(True)
            if save_path:
                plt.savefig(save_path, dpi=200)
            plt.show()

        return df