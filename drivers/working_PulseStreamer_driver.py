# -*- coding: utf-8 -*-
"""
Created on Tue Mar  3 16:12:26 2026

@author: ODMR_user + ChatGPT
"""

# -*- coding: utf-8 -*-
"""
PulseStreamer 8/2 Driver for ODMR experiments
Correct hardware-level architecture

Max Note: Encoding a pulse sequence using the PulseStreamer is very easy!




"""

import time
import logging
from pulsestreamer import PulseStreamer, Sequence, TriggerStart

log = logging.getLogger(__name__)


class PulseStreamer82:

    # --------------------------------------------------
    # INIT
    # --------------------------------------------------

    def __init__(self, ip_address: str):
        self.ip = ip_address
        self.ps = None
        self.connect()
        
        # Store user-defined sequences per channel
        self.channel_sequences = {}

        # Store original sequences (for resume)
        self._original_sequences = {}

        self._is_streaming = False

    # --------------------------------------------------
    # CONNECTION
    # --------------------------------------------------

    def connect(self):
        log.info(f"Connecting to PulseStreamer at {self.ip}")
        self.ps = PulseStreamer(self.ip)
        self.ps.forceFinal()
        time.sleep(0.2)

    # --------------------------------------------------
    # SEQUENCE MANAGEMENT
    # --------------------------------------------------

    def allocate_sequence(self, sequence, channel):
        """
        Store a pulse sequence for a given channel.
        sequence: list of (duration_ns, level)
        """
        self.channel_sequences[channel] = sequence.copy()
        self._original_sequences[channel] = sequence.copy()

    # --------------------------------------------------
    # INTERNAL: BUILD HARDWARE SEQUENCE
    # --------------------------------------------------

    def _compile_sequence(self):
        """
        Build ONE hardware Sequence object from all channels.
        Ensures all channels have identical total duration.
        """

        if not self.channel_sequences:
            raise RuntimeError("No channel sequences defined.")

        # Compute total duration of each channel
        totals = {
            ch: sum(duration for duration, _ in seq)
            for ch, seq in self.channel_sequences.items()
        }

        # Ensure all totals are identical
        durations = list(totals.values())
        if not all(d == durations[0] for d in durations):
            raise ValueError(f"Channel durations mismatch: {totals}")

        total_time = durations[0]
        log.info(f"Compiled sequence total duration: {total_time} ns")

        seq = Sequence()

        for ch, pulses in self.channel_sequences.items():
            seq.setDigital(ch, pulses)

        return seq


    def square_wave(self,
                period_ns: int,
                offset_ns: int = 0):
        """
        Generate a PulseStreamer-style square wave.

        Parameters
        ----------
        period_ns : int
            Total square-wave period.

        offset_ns : int
            Phase offset in ns.

        Returns
        -------
        list of (duration_ns, level)
        """

        period_ns = int(period_ns)
        offset_ns = int(offset_ns)

        if period_ns <= 0:
            raise ValueError("period_ns must be > 0")
        
        # 50% duty cycle
        high_ns = period_ns // 2
        low_ns = period_ns - high_ns

        # wrap offset into one cycle
        offset_ns = offset_ns % period_ns

        # ----------------------------------------
        # No offset
        # ----------------------------------------

        if offset_ns == 0:
            sequence = [(high_ns, 1),(low_ns, 0)]

        # ----------------------------------------
        # Offset inside HIGH
        # ----------------------------------------

        elif offset_ns < high_ns:
            sequence = [(high_ns - offset_ns, 1),(low_ns, 0),(offset_ns, 1)]

        # ----------------------------------------
        # Offset inside LOW
        # ----------------------------------------

        else:
            low_offset = offset_ns - high_ns
            sequence = [(low_ns - low_offset, 0),(high_ns, 1),(low_offset, 0)]

        return sequence

    # --------------------------------------------------
    # START STREAMING
    # --------------------------------------------------

    def begin_pulses(self, n_runs=-1, trigger=TriggerStart.IMMEDIATE):

        if self.ps is None:
            raise RuntimeError("Not connected to PulseStreamer.")

        self.ps.forceFinal()
        time.sleep(0.1)

        seq = self._compile_sequence()

        # Correct API for your installed version
        self.ps.setTrigger(trigger)
        self.ps.stream(seq, n_runs=n_runs)

        self._is_streaming = True
        log.info("Synchronized pulse sequence started")

    # --------------------------------------------------
    # STOP STREAMING
    # --------------------------------------------------

    def stop(self):
        if self.ps is not None:
            self.ps.forceFinal()
            self._is_streaming = False
            log.info("PulseStreamer forced to final state")

    # --------------------------------------------------
    # PAUSE / RESUME CHANNEL
    # --------------------------------------------------

    def pause_channel(self, channel):
        """
        Replace channel sequence with constant LOW
        while keeping identical duration.
        """

        if channel not in self.channel_sequences:
            raise ValueError(f"Channel {channel} not defined.")

        total_time = sum(
            duration for duration, _ in self.channel_sequences[channel]
        )

        self.channel_sequences[channel] = [(total_time, 0)]
        log.info(f"Channel {channel} paused")

    def resume_channel(self, channel):
        """
        Restore original channel sequence.
        """

        if channel not in self._original_sequences:
            raise ValueError(f"No stored sequence for channel {channel}")

        self.channel_sequences[channel] = \
            self._original_sequences[channel].copy()

        log.info(f"Channel {channel} resumed")

    # --------------------------------------------------
    # UPDATE LIVE (recompile + restart)
    # --------------------------------------------------

    def update_and_restart(self, n_runs=-1):
        """
        Stop, recompile, and restart.
        Useful after pause/resume.
        """

        if not self._is_streaming:
            raise RuntimeError("Cannot update: not currently streaming.")

        self.stop()
        time.sleep(0.1)
        self.begin_pulses(n_runs=n_runs)

    # --------------------------------------------------
    # STATUS
    # --------------------------------------------------

    def is_streaming(self):
        return self._is_streaming