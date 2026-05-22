# working_PulseStreamer8_driver.py

# Author: ChatGPT + odmr_user

from pulsestreamer import PulseStreamer, Sequence, TriggerStart, TriggerRearm, OutputState
import logging
import numpy as np

class PulseStreamer82:
    """
    Driver for Swabian Instruments PulseStreamer 8/2 (via their Python client).
    Supports sequence creation, streaming, and trigger control, for CW  and pulsed ODMR.
    
    NOTE: Native units for the PulseStreamer is nanoseconds
    
    PulseStreamer IP address = '169.254.8.2'
    """

    def __init__(self, ip_address: str):
        """
        Initialize the PulseStreamer.

        Parameters
        ----------
        ip_address : str
            IP address or hostname of the PulseStreamer device.
        """
        self.log = logging.getLogger(__name__)
        self.ip = ip_address
        self.ps = PulseStreamer(self.ip)
        self.channel_sequences = {}
        self.seq = None

    def connect(self):
        """Connect / verify the device is reachable. Resets device to default."""
        self.log.info(f"Connecting to PulseStreamer at {self.ip}")
        self.ps.reset()
        return self.ps.hasSequence(), self.ps.isStreaming()

    def start(self, n_runs: int = -1, final_state=None):
        """
        Start streaming the loaded sequence.

        Parameters
        ----------
        n_runs : int
            Number of times to repeat the sequence. -1 = infinite.
        final_state : optional, an OutputState or sequence final value
            Final output when sequence completes.
        """
        if self.seq is None:
            raise RuntimeError("No sequence created or loaded")
        # Use default final state if not provided
        if final_state is None:
            # could compute default based on seq.getLastState() or zero
            final_state = None
        self.ps.stream(self.seq, n_runs=n_runs, final=final_state)
        self.log.info("PulseStreamer started streaming")

    def stop(self):
        """Stop the pulse streamer by forcing the final state (or abort)."""
        self.ps.forceFinal()
        self.log.info("PulseStreamer forced to final state")

    def rearm(self):
        """Re-arm the trigger if in manual rearm mode."""
        ok = self.ps.rearm()
        self.log.info(f"PulseStreamer rearmed: {ok}")
        return ok

    def has_sequence(self):
        """Return True if a sequence is loaded into the device."""
        return self.ps.hasSequence()

    def is_streaming(self):
        """Return True if a sequence is currently being streamed."""
        return self.ps.isStreaming()

    def close(self):
        """Clean up / close connection if needed."""
        # There isn't necessarily a "close" in the API, but you could reset.
        self.ps.reset()
        self.seq = None
        self.log.info("PulseStreamer reset and closed")

    def set_channel_state(self, channel: int, state: int):
        """
        Immediately set a digital channel HIGH (1) or LOW (0).
        This does not require streaming a timed sequence.
        """

        if state not in (0, 1):
            raise ValueError("State must be 0 or 1")

        # Build OutputState object
        final = OutputState()

        # Set only requested channel
        final.setDigital(channel, state)

        # Apply immediately
        self.ps.forceFinal(final)
        self.log.info(f"Channel {channel} forced to state {state}")

# -----------------------------------------------------------------------
# Microwave Modulation (instead of the AWG) 
# -----------------------------------------------------------------------

    def modulate_microwaves(self, analog_channels, mod_freq: float,
                           duty_cycle: float = 0.5, duration: float = 0.01,
                           amplitude: float = 1.0):
        """
        Create a continuous square-wave modulation on analog channel(s) using the
        latest PulseStreamer API.
        """
        if isinstance(analog_channels, int):
            analog_channels = [analog_channels]

        seq = self.ps.createSequence()

        # Time resolution
        dt = 1e-6  # 1 µs
        n_steps = int(np.ceil(duration / dt))
        t = np.linspace(0, duration, n_steps)

        # Create square-wave values: 0 (OFF) or amplitude (ON)
        square_wave = ((t % (1 / mod_freq)) < (duty_cycle / mod_freq)).astype(float) * amplitude

        for ch in analog_channels:
            # Must pass a tuple of (values, times)
            seq.setAnalog(ch, (square_wave, t))

        # Stream indefinitely
        self.ps.stream(seq, n_runs=-1)
        self.log.info(f"Started {mod_freq} Hz square-wave modulation on channels {analog_channels}, "
                      f"amplitude={amplitude} V, duty={duty_cycle*100:.1f}%")
        
        
    def modulate_microwaves_digital(
        self,
        digital_channel: int,
        mod_freq: float,
        duty_cycle: float = 0.5,
        offset_s: float = 0.0,
        ):
        """
        Generate a continuous square-wave modulation on a PulseStreamer
        digital channel.
        
        Parameters
        ----------
        digital_channel : int
            Digital output channel number.
        mod_freq : float
            Modulation frequency in Hz.
        duty_cycle : float
            Fraction of period HIGH (0–1).
        offset_s : float
            Time offset before modulation starts (seconds).
        """

        if not (0 < duty_cycle <= 1):
            raise ValueError("duty_cycle must be between 0 and 1")

        # Convert frequency to period (seconds)
        period_s = 1.0 / mod_freq

        # Convert to nanoseconds (PulseStreamer native resolution)
        period_ns = int(period_s * 1e9)
        offset_ns = int(offset_s * 1e9)

        high_time_ns = int(period_ns * duty_cycle)
        low_time_ns = period_ns - high_time_ns

        seq = self.ps.createSequence()

        pattern = []

        # Optional offset (LOW during offset)
        if offset_ns > 0:
            pattern.append((offset_ns, 0))

        # One full period
        pattern.append((high_time_ns, 1))
        pattern.append((low_time_ns, 0))

        # Set digital waveform
        seq.setDigital(digital_channel, pattern)

        # Stream indefinitely
        self.ps.stream(seq, n_runs=-1)
        self.log.info(
            f"Started digital square wave on ch {digital_channel} | "
            f"{mod_freq} Hz | duty={duty_cycle*100:.1f}% | offset={offset_s}s")
        

# -----------------------------------------------------------------------
# Pulse Sequence Generation (instead of the AWG) 
# -----------------------------------------------------------------------
    """
    Like the AWG, the PulseStreamer8/2 uses list to generate pulse sequences, 
    how it is has it's own implementation which is more user friendly, based on 
    the function ps.CreateSequence()

    For example, ps.CreateSequence = [(100,0),(200,1),(100,0)]

    Whould be a pulse sequence consisting of 100 ns at 0 V, 200 ns at 1 V, 
    and 100 ns at 0 V. The following series of functions are used to construct 
    sequences and then transmit them from a choosen channel.

    The PulseStreamer8/2 has Seven channels, that can in principle control seven 
    instruments.

    """
    def create_sequence(self):
        """Create a new Sequence object."""
        self.seq = self.ps.createSequence()
        return self.seq

    def load_sequence(self, seq):
        """Load the given Sequence to the device (but does not start)."""
        if not isinstance(seq, Sequence):
            raise ValueError("seq must be a Sequence object from pulsestreamer")
        self.seq = seq

    def set_trigger(self, start_mode, rearm_mode=TriggerRearm.AUTO):
        """
        Configure how the PulseStreamer sequence will be triggered.
        
        Parameters
        ----------
        start_mode : TriggerStart
            Source of the trigger (e.g., IMMEDIATE, SOFTWARE, HARDWARE_RISING, etc.)
        rearm_mode : TriggerRearm
            How the trigger re-arms.
        """
        self.ps.setTrigger(start_mode, rearm_mode)

    def allocate_sequence(self, sequence, channel: int):
        """
        Store a digital pulse sequence for a specific channel.
    
        Parameters
        ----------
        sequence : list of (duration_ns, level)
            Example: [(1000,0),(3000,1),(500,0)]
        channel : int
            Digital output channel number
            """

        # Validate
        for seg in sequence:
            if len(seg) != 2:
                raise ValueError("Each segment must be (duration_ns, level)")
            if seg[0] < 0:
                raise ValueError("Duration must be >= 0")

        self.channel_sequences[channel] = sequence
        
        
    def begin_pulses(self,
                 n_runs: int = -1,
                 sync_channel: int = None,
                 sync_duration_ns: int = 50):
        """
        Synchronize all loaded channel sequences and start streaming.
        
        Parameters
        ----------
        n_runs : int
            Number of repetitions (-1 = infinite)
        sync_channel : int
            Optional digital channel to output a short sync pulse
        sync_duration_ns : int
            Duration of sync pulse
        """

        if not self.channel_sequences:
            raise RuntimeError("No sequences implemented")

        seq = self.ps.createSequence()

        # -------------------------------------------------
        # Compute total duration per channel
        # -------------------------------------------------
        channel_lengths = {}
        for ch, segments in self.channel_sequences.items():
            total = sum(seg[0] for seg in segments)
            channel_lengths[ch] = total

        max_length = max(channel_lengths.values())

        # -------------------------------------------------
        # Pad sequences to equal length
        # -------------------------------------------------
        for ch, segments in self.channel_sequences.items():

            current_length = channel_lengths[ch]
            padded = list(segments)

            if current_length < max_length:
                padded.append((max_length - current_length, 0))

            seq.setDigital(ch, padded)

        # -------------------------------------------------
        # Optional sync pulse
        # -------------------------------------------------
        if sync_channel is not None:
            sync_sequence = [(sync_duration_ns, 1),
                         (max_length - sync_duration_ns, 0)]
            seq.setDigital(sync_channel, sync_sequence)

        self.seq = seq
        
        self.ps.stream(seq, n_runs=n_runs)
        self.log.info("Synchronized pulse sequence started")
        
        
        
        
        