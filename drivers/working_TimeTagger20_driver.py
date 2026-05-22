# -*- coding: utf-8 -*-
"""
Created on Wed Dec 17 11:41:03 2025

@author: ODMR_user
"""

# High-level Python driver for Swabian Instruments TimeTagger20
# Based directly on the official C++ / SWIG API exposed in TimeTagger.py
# Maximum data rate is 9 MSa/s. Users should ensure they stay below this.



import sys
from pathlib import Path

SWABIAN_PATH = Path(
    r"C:\Program Files\Swabian Instruments\Time Tagger\driver\python\Swabian"
)

if SWABIAN_PATH.exists():
    sys.path.insert(0, str(SWABIAN_PATH))

import TimeTagger

import numpy as np
import time

SERIAL_NUMBER = "2434001CEJ"


class TimeTagger20:
    #_instance_created = False

    """
    High-level convenience driver wrapping the native TimeTagger API.
    This class intentionally mirrors C++ capabilities and only adds
    experiment-friendly helpers (histogram, start-stop, counters, etc.).
    """

    def __init__(self, serial="2434001CEJ"):
      #  if TimeTaggerDriver._instance_created:
      #      raise RuntimeError(
      #          "TimeTaggerDriver already instantiated. "
      #          "Create it once and reuse the object."
      #          )

        self.tagger = TimeTagger.createTimeTagger(serial)
        TimeTagger20._instance_created = True
        self.tagger.setTriggerLevel(1, 0.5)
        self.tagger.setTriggerLevel(2, 0.5)


    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------
    def set_event_divider(self, channel: int, divider: int = 1):
        """Apply an event divider to a physical channel."""
        if divider < 1 or divider > 65535:
            raise ValueError("Event divider must be in range [1, 65535]")
        self.tagger.setEventDivider(channel, divider)

    def clear_event_divider(self, channel: int):
        self.tagger.setEventDivider(channel, 1)

    def get_event_divider(self, channel: int) -> int:
        return self.tagger.getEventDivider(channel)

    def clear_overflows(self):
        self.tagger.clearOverflows()

    def get_overflows(self) -> int:
        return self.tagger.getOverflows()

    # ------------------------------------------------------------------
    # Reference / software clock
    # ------------------------------------------------------------------
    def set_reference_clock(
        self,
        clock_channel: int,
        clock_frequency: float = 10e6,
        time_constant: float = 1e-3,
        synchronization_channel: int | None = None,
        event_divider: int = 1,
    ):
        """
        Configure the software reference clock.
        Event divider is applied automatically before PLL lock.
        """
        self.set_event_divider(clock_channel, event_divider)

        kwargs = dict(
            clock_channel=clock_channel,
            clock_frequency=clock_frequency,
            time_constant=time_constant,
            wait_until_locked=True,
        )
        if synchronization_channel is not None:
            kwargs["synchronization_channel"] = synchronization_channel

        self.tagger.setReferenceClock(**kwargs)

    def disable_reference_clock(self):
        self.tagger.disableReferenceClock()

    # ------------------------------------------------------------------
    # Histogram experiment
    # ------------------------------------------------------------------
    def run_histogram(
        self,
        click_channel: int,
        start_channel: int | None = None,
        binwidth_ps: int = 1000,
        n_bins: int = 10000,
        capture_time_s: float | None = None,
        event_divider: dict[int, int] | None = None,
        start_delay: int = 0):
        
        self.tagger.setInputDelay(start_channel, start_delay)
       # self.tagger.setInputDelay(click_channel, 1000)

        """
        Run a standard histogram measurement.
        Note: native units of the TimeTagger is picoseconds

        Parameters
        ----------
        click_channel : int
            Detector channel
        start_channel : int | None
            Optional start channel (pulsed experiments)
        event_divider : dict
            Mapping {channel: divider}
        """
        if event_divider is not None:
            if isinstance(event_divider, dict):
                # Explicit per-channel dividers
                for ch, div in event_divider.items():
                    self.set_event_divider(ch, div)
            else:
                # Single divider applied to both relevant channels
                self.set_event_divider(click_channel, event_divider)
                self.set_event_divider(start_channel, event_divider)

        hist = TimeTagger.Histogram(
            tagger=self.tagger,
            click_channel=click_channel,
            start_channel=start_channel
            if start_channel is not None
            else TimeTagger.CHANNEL_UNUSED,
            binwidth=binwidth_ps,
            n_bins=n_bins)

        if capture_time_s is not None:
            hist.startFor(int(capture_time_s * 1e12))
            hist.waitUntilFinished()
        else:
            hist.start()
            time.sleep(0.1)
            hist.stop()

        data = np.array(hist.getData())
        t = np.array(hist.getIndex())

        return t, data

    # ------------------------------------------------------------------
    # Time differences (multi-histogram, pulsed ODMR friendly)
    # ------------------------------------------------------------------
    def run_time_differences(
        self,
        click_channel: int,
        start_channel: int,
        next_channel: int | None = None,
        sync_channel: int | None = None,
        binwidth_ps: int = 1000,
        n_bins: int = 10000,
        n_histograms: int = 1,
        max_counts: int = 0,
    ):

        td = TimeTagger.TimeDifferences(
            tagger=self.tagger,
            click_channel=click_channel,
            start_channel=start_channel,
            next_channel=next_channel
            if next_channel is not None
            else TimeTagger.CHANNEL_UNUSED,
            sync_channel=sync_channel
            if sync_channel is not None
            else TimeTagger.CHANNEL_UNUSED,
            binwidth=binwidth_ps,
            n_bins=n_bins,
            n_histograms=n_histograms,
        )

        td.setMaxCounts(max_counts)
        td.start()

        while not td.ready():
            time.sleep(0.01)

        td.stop()
        return np.array(td.getIndex()), np.array(td.getData())

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------
    def close(self):
        if self.tagger is not None:
            TimeTagger.freeTimeTagger(self.tagger)
            self.tagger = None
        TimeTagger20._instance_created = False

