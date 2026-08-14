"""
This is example script demonstrates most of the basic functionality of nspyre.
"""
import time
import logging
from pathlib import Path

import numpy as np
from nspyre import DataSource
from nspyre import experiment_widget_process_queue
from nspyre import StreamingList
from nspyre import nspyre_init_logger
# from nspyre import DataSink

from pulsestreamer import TriggerStart

from template.drivers.insmgr import MyInstrumentManager
# from pulsestreamer import TriggerStart, TriggerRearm

_HERE = Path(__file__).parent
_logger = logging.getLogger(__name__)


class SpinMeasurements:
    """Spin measurement experiments."""

    def __init__(self, queue_to_exp=None, queue_from_exp=None):
        """
        Args:
            queue_to_exp: A multiprocessing Queue object used to send messages
                to the experiment from the GUI.
            queue_from_exp: A multiprocessing Queue object used to send messages
                to the GUI from the experiment.
        """
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp

    def __enter__(self):
        """Perform experiment setup."""
        # config logging messages
        # if running a method from the GUI, it will be run in a new process
        # this logging call is necessary in order to separate log messages
        # originating in the GUI from those in the new experiment subprocess
        nspyre_init_logger(
            log_level=logging.INFO,
            log_path=_HERE / '../logs',
            log_path_level=logging.DEBUG,
            prefix=Path(__file__).stem,
            file_size=10_000_000,
        )
        _logger.info('Created SpinMeasurements instance.')

    def __exit__(self):
        """Perform experiment teardown."""
        _logger.info('Destroyed SpinMeasurements instance.')

#------------------------------------------------------------------------------
# NIR Experiments using APD and PulseSteamer8/2 - Laser and microwaves are modulated via the PS82. 
#                                The repetition frequency corresponds to the MFLI lock-in 
#                                frequency.
#------------------------------------------------------------------------------

    def NIR_initialisation_lockin(self,
                                  dataset: str,
                                  laser_on_ns: int,
                                  laser_off_ns: int,
                                  iterations: int,
                                  dwell_time: float = 0.2,
                                  integration_time: float = 1.0):

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:

            odmr_driver = mgr.odmr_driver
            ps82 = mgr.ps82

            # ----------------------------------------
            # PulseStreamer sequence configuration
            # ----------------------------------------
            ps82.channel_sequences = {}

            laser_seq = [
                (laser_on_ns, 1),
                (laser_off_ns, 0)
            ]

            ref_seq = [
                (laser_on_ns, 1),
                (laser_off_ns, 0)
            ]

            ps82.allocate_sequence(laser_seq, 1)
            ps82.allocate_sequence(ref_seq, 2)

            # Programmatically update the MFLI hardware oscillator reference frequency
            mod_freq_hz = 1e9 / (laser_on_ns + laser_off_ns)
            if hasattr(odmr_driver, 'mfli') and odmr_driver.mfli is not None:
                odmr_driver.mfli.set_demod_freq(mod_freq_hz)

            ps82.begin_pulses(n_runs=-1)
            time.sleep(0.25)

            # Initialize StreamingLists for the scope trace elements
            scope_time = StreamingList()
            scope_signal = StreamingList()
            
            # Running trace averaging variable
            running_avg_signal = None

            for i in range(iterations):
                time.sleep(dwell_time)

                # --- Fetch full scope trace from your updated MFLI driver ---
                trace_data = odmr_driver.mfli.get_scope_trace(channel=0)
                
                if trace_data is None:
                    print(f"[WARN] Frame {i}: Scope data collection missed or timed out.")
                    continue

                t_vals = trace_data["time"]       # Array of time points (ms)
                raw_signal = trace_data["signal"]  # Array of scope signals (µV)

                # --- Calculate Running / Cumulative Moving Average ---
                if running_avg_signal is None:
                    running_avg_signal = np.array(raw_signal, dtype=float)
                    
                    # Prime the streaming lists on the very first valid iteration
                    scope_time.append(t_vals)
                    scope_signal.append(running_avg_signal)
                else:
                    # Linear cumulative average formula: Avg_n = Avg_n-1 + (New - Avg_n-1) / n
                    running_avg_signal += (raw_signal - running_avg_signal) / (i + 1)
                    
                    # Update existing indexes in the streaming containers
                    scope_time[-1] = t_vals
                    scope_signal[-1] = running_avg_signal

                # Notify streaming framework of internal array updates 
                scope_time.updated_item(-1)
                scope_signal.updated_item(-1)

                # Push scope trace datasets and updated parameter metadata
                data.push({
                    'params': {
                        'laser_on_ns': laser_on_ns,
                        'laser_off_ns': laser_off_ns,
                        'iterations_target': iterations,
                        'current_iteration': i + 1,
                        'modulation_frequency_hz': mod_freq_hz
                    },
                    'title': 'Averaged Scope PL Trace Measurement',
                    'xlabel': 'Time (ms)',
                    'ylabel': 'PL Signal (µV)',
                    'datasets': {
                        'Time': scope_time,
                        'Signal': scope_signal
                    }
                })

                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    return
                
                
    def NIR_cw_odmr_sweep_linear_ps82(self,
                      dataset: str,
                      start_freq: float,
                      stop_freq: float,
                      num_points: int,
                      iterations: int,
                      modulation_freq: int,
                      rf_amplitude: int,
                      dwell_time: float = 0.1,
                      integration_time: float = 0.1):

        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
            
            odmr_driver = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82

            sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
            sg.set_output(1)
            
            ps82.channel_sequences = {}  # Clear previous
            period_ns = int(1e9 / modulation_freq) 
            high_ns = period_ns // 2
            low_ns = period_ns - high_ns
            mw_seq = ps82.square_wave(period_ns)
            #laser_seq = [(period_ns,1)]
            laser_seq = [(high_ns, 1),(low_ns, 0)]
            
            ps82.allocate_sequence(mw_seq, 0)
            ps82.allocate_sequence(laser_seq, 7)
            ps82.begin_pulses(n_runs=-1)              
            
            time.sleep(0.25)
            
            frequencies = np.linspace(start_freq, stop_freq, num_points)
            linear_order = range(num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
                
                for idx in linear_order:      
                    freqs = frequencies[idx]
                        
                    # Signal
                    sg.set_frequency(freqs)
                    time.sleep(dwell_time + integration_time)
                    sig_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time + integration_time)
                    bg_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                    background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    odmr_data.push({
                        'params': {
                            'start': start_freq,
                            'stop': stop_freq,
                            'num_points': num_points,
                            'iterations': iterations
                            },
                        'title': 'Linear ODMR Sweep',
                        'xlabel': 'Frequency (GHz)',   
                        'ylabel': 'Signal',
                        'datasets': {
                            'signal':     signal_sweeps,
                            'background': background_sweeps,
                            'time_spent': time_spent
                            }})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        return
            

#------------------------------------------------------------------------------
# Lock-in Detection Method - Laser and microwaves are modulated via the AWG. 
#                            The repeating frequency corresponds to the lock-in 
#                            frequency.
#------------------------------------------------------------------------------
    def cw_odmr_sweep_random_awg(self,
                      dataset: str,
                      start_freq: float,
                      stop_freq: float,
                      num_points: int,
                      iterations: int,
                      modulation_freq: int,
                      rf_amplitude: int,
                      dwell_time: float = 0.01,
                      integration_time: float = 0.1):

        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
            
            odmr_driver = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
            sg.set_output(1)
            
            awg.set_waveform(1, "SQU")
            awg.set_frequency(1, modulation_freq)
            awg.set_amplitude(1, 8)
            awg.set_burst_mode(1, False)
            awg.output(1, True)
            
            awg.set_burst_mode(2, False)
            awg.output(2, False)
            
            time.sleep(0.01)
            
            frequencies = np.linspace(start_freq, stop_freq, num_points)
            rng = np.random.default_rng()
            random_order = rng.permutation(num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
                
                for idx in random_order:      
                    freq = frequencies[idx]
                        
                    # Signal
                    sg.set_frequency(freq)
                    time.sleep(dwell_time + integration_time)
                    sig_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # Background
                    odmr_driver.set_frequency(100e3)
                    time.sleep(dwell_time + integration_time)   # sleep doesn't need to be set to include the integration time?
                    bg_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                    background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    odmr_data.push({
                        'params': {
                            'start': start_freq,
                            'stop': stop_freq,
                            'num_points': num_points,
                            'iterations': iterations
                            },
                        'title': 'Random ODMR Sweep',
                        'xlabel': 'Frequency (GHz)',   
                        'ylabel': 'Signal',         # Used to be "counts"
                        'datasets': {
                            'signal':     signal_sweeps,
                            'background': background_sweeps,
                            'time_spent': time_spent      # Tracks the time the measurement has run for
                            }})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        return


    def cw_odmr_sweep_linear_awg(self,
                      dataset: str,
                      start_freq: float,
                      stop_freq: float,
                      num_points: int,
                      iterations: int,
                      modulation_freq: int,
                      rf_amplitude: int,
                      dwell_time: float = 0.1,
                      integration_time: float = 0.1):

        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
            
            odmr_driver = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
            sg.set_output(1)
            
            awg.set_waveform(1, "SQU")
            awg.set_frequency(1, modulation_freq)
            awg.set_amplitude(1, 8)
            awg.set_burst_mode(1, False)
            awg.output(1, True)
            
            awg.set_burst_mode(2, False)
            awg.output(2, False)
            
            time.sleep(0.5)
            
            frequencies = np.linspace(start_freq, stop_freq, num_points)
            linear_order = range(num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
                
                for idx in linear_order:      
                    freqs = frequencies[idx]
                        
                    # Signal
                    sg.set_frequency(freqs)
                    time.sleep(dwell_time + integration_time)
                    sig_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time + integration_time)
                    bg_counts[idx] = odmr_driver.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                    background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    odmr_data.push({
                        'params': {
                            'start': start_freq,
                            'stop': stop_freq,
                            'num_points': num_points,
                            'iterations': iterations
                            },
                        'title': 'Linear ODMR Sweep',
                        'xlabel': 'Frequency (GHz)',   
                        'ylabel': 'Signal',
                        'datasets': {
                            'signal':     signal_sweeps,
                            'background': background_sweeps,
                            'time_spent': time_spent
                            }})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        return


#------------------------------------------------------------------------------
# PulseSteamer8/2 Experiments  - Laser and microwaves are modulated via the PS82. 
#                                The repetition frequency corresponds to the lock-in 
#                                frequency.
#------------------------------------------------------------------------------



    def cw_odmr_sweep_linear_ps82_newbkg(self,
                          dataset: str,
                          start_freq: float,
                          stop_freq: float,
                          num_points: int,
                          iterations: int,
                          modulation_freq: int,
                          rf_amplitude: int,
                          dwell_time: float = 0.05,
                          integration_time: float = 0.1):

            with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
                
                odmr_driver = mgr.odmr_driver
                sg = mgr.sg
                ps82 = mgr.ps82
                mfli = mgr.mfli
                
                sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
                sg.set_output(1)
                
                ps82.channel_sequences = {}  # Clear previous
                period_ns = int(1e9 / modulation_freq)  
                mw_seq = ps82.square_wave(period_ns)
                
                ps82.allocate_sequence(mw_seq, 0)
                ps82.begin_pulses(n_runs=-1)              
                
                time.sleep(0.25)
                
                frequencies = np.linspace(start_freq, stop_freq, num_points)
                linear_order = range(num_points)

                # --- NEW independent dataset ---
                time_spent_signal = StreamingList()
                time_spent_bkg = StreamingList()
                sweep_start_time = time.time()
                
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                
                for i in range(iterations):
                    
                    sig_counts = np.empty(num_points)
                    sig_counts[:] = np.nan
                    bg_counts = np.empty(num_points)
                    bg_counts[:] = np.nan
                    
                    # --- NEW per-iteration time array ---
                    time_counts = np.empty(num_points)
                    time_counts[:] = np.nan
                    
                    # Append initial empty arrays to all StreamingLists
                    signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                    background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                    time_spent_signal.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
                    time_spent_bkg.append(np.stack([time_counts, bg_counts]))
                    
                    for idx in linear_order:      
                        freqs = frequencies[idx]
                            
                        # Signal
                        sg.set_frequency(freqs)
                        time.sleep(dwell_time)  #  + integration_time
                        sig_counts[idx] = odmr_driver.cnts(integration_time)
                        
                        # Background
                        sg.set_frequency(100e3)
                        time.sleep(dwell_time)   #  + integration_time
                        bg_counts[idx] = mfli.get_background_PL(integration_time, 0)
                        
                        # --- collect elapsed time since sweep start ---
                        time_counts[idx] = time.time() - sweep_start_time
                        
                        # Update streaming entries
                        signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                        background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                        time_spent_signal[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                        time_spent_bkg[-1] = np.stack([time_counts, bg_counts])
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_spent_signal.updated_item(-1)
                        time_spent_bkg.updated_item(-1)
                        
                        # Push dataset including new time series
                        odmr_data.push({
                            'params': {
                                'start': start_freq,
                                'stop': stop_freq,
                                'num_points': num_points,
                                'iterations': iterations},
                            'title': 'Linear ODMR Sweep',
                            'xlabel': 'Frequency (GHz)',   
                            'ylabel': 'Signal',
                            'datasets': {
                                'signal':     signal_sweeps,
                                'background': background_sweeps,
                                'time_spent_signal': time_spent_signal,
                                'time_spent_bkg': time_spent_bkg}})
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            sg.set_output(0)
                            return    


    def cw_odmr_sweep_random_ps82_newbkg(self,
                          dataset: str,
                          start_freq: float,
                          stop_freq: float,
                          num_points: int,
                          iterations: int,
                          modulation_freq: int,
                          rf_amplitude: int,
                          dwell_time: float = 0.025,
                          integration_time: float = 0.1):

            with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
                
                odmr_driver = mgr.odmr_driver
                sg = mgr.sg
                ps82 = mgr.ps82
                mfli = mgr.mfli
                
                sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
                sg.set_output(1)
                
                ps82.channel_sequences = {}  # Clear previous
                period_ns = int(1e9 / modulation_freq)  
                mw_seq = ps82.square_wave(period_ns)
                
                ps82.allocate_sequence(mw_seq, 0)
                ps82.begin_pulses(n_runs=-1)              
                
                time.sleep(0.1)
                
                frequencies = np.linspace(start_freq, stop_freq, num_points)
                rng = np.random.default_rng()
                random_order = rng.permutation(num_points)

                # --- NEW independent dataset ---
                time_spent_signal = StreamingList()
                time_spent_bkg = StreamingList()
                sweep_start_time = time.time()
                
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                
                for i in range(iterations):
                    
                    sig_counts = np.empty(num_points)
                    sig_counts[:] = np.nan
                    bg_counts = np.empty(num_points)
                    bg_counts[:] = np.nan
                    
                    # --- NEW per-iteration time array ---
                    time_counts = np.empty(num_points)
                    time_counts[:] = np.nan
                    
                    # Append initial empty arrays to all StreamingLists
                    signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                    background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                    time_spent_signal.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
                    time_spent_bkg.append(np.stack([time_counts, bg_counts]))
                    
                    for idx in random_order:      
                        freqs = frequencies[idx]
                            
                        # Signal
                        sg.set_frequency(freqs)
                        time.sleep(dwell_time)  #  + integration_time
                        sig_counts[idx] = odmr_driver.cnts(integration_time)
                        
                        # Background
                        sg.set_frequency(1e6)
                        time.sleep(dwell_time)   #  + integration_time
                        bg_counts[idx] = mfli.get_background_PL(integration_time, 0)
                        
                        # --- collect elapsed time since sweep start ---
                        time_counts[idx] = time.time() - sweep_start_time
                        
                        # Update streaming entries
                        signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                        background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                        time_spent_signal[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                        time_spent_bkg[-1] = np.stack([time_counts, bg_counts])
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_spent_signal.updated_item(-1)
                        time_spent_bkg.updated_item(-1)
                        
                        # Push dataset including new time series
                        odmr_data.push({
                            'params': {
                                'start': start_freq,
                                'stop': stop_freq,
                                'num_points': num_points,
                                'iterations': iterations},
                            'title': 'Linear ODMR Sweep',
                            'xlabel': 'Frequency (GHz)',   
                            'ylabel': 'Signal',
                            'datasets': {
                                'signal':     signal_sweeps,
                                'background': background_sweeps,
                                'time_spent_signal': time_spent_signal,
                                'time_spent_bkg': time_spent_bkg}})
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                            sg.set_output(0)
                            return    


    def cw_odmr_probepeaks_ps82(
        self,
        dataset: str,
        probe_frequencies: list,
        iterations: int,
        modulation_freq: int,
        rf_amplitude: float,
        dwell_time: float = 0.025,
        integration_time: float = 0.05):

 #       if len(probe_frequencies) != 13:
 #            raise ValueError("Exactly 13 probe frequencies must be supplied.")

        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:

            odmr_driver = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
            mfli = mgr.mfli

            sg.set_amplitude_rf(rf_amplitude)
            sg.set_output(1)

            # ---------------------------------------
            # PulseStreamer microwave modulation
            # ---------------------------------------

            ps82.channel_sequences = {}

            period_ns = int(1e9 / modulation_freq)
            mw_seq = ps82.square_wave(period_ns)

            ps82.allocate_sequence(mw_seq, 0)
            ps82.begin_pulses(n_runs=-1)

            if isinstance(probe_frequencies, str):
                probe_frequencies = [
                    float(freq.strip())
                    for freq in probe_frequencies.split(',')]
                
            time.sleep(0.15)

            # ---------------------------------------
            # Allocate data arrays
            # ---------------------------------------
            time_counts = np.full(iterations, np.nan)

            sig_counts_1 = np.full(iterations, np.nan)
            bkg_counts_1 = np.full(iterations, np.nan)
            
            sig_counts_2 = np.full(iterations, np.nan)
            bkg_counts_2 = np.full(iterations, np.nan)

            sig_counts_3 = np.full(iterations, np.nan)
            bkg_counts_3 = np.full(iterations, np.nan)

            sig_counts_4 = np.full(iterations, np.nan)
            bkg_counts_4 = np.full(iterations, np.nan)

            sig_counts_5 = np.full(iterations, np.nan)
            bkg_counts_5 = np.full(iterations, np.nan)
            
            sig_counts_6 = np.full(iterations, np.nan)
            bkg_counts_6 = np.full(iterations, np.nan)
            
            sig_counts_7 = np.full(iterations, np.nan)
            bkg_counts_7 = np.full(iterations, np.nan)
            
            sig_counts_8 = np.full(iterations, np.nan)
            bkg_counts_8 = np.full(iterations, np.nan)
            
            sig_counts_9 = np.full(iterations, np.nan)
            bkg_counts_9 = np.full(iterations, np.nan)
            
            sig_counts_10 = np.full(iterations, np.nan)
            bkg_counts_10 = np.full(iterations, np.nan)
            
            sig_counts_11 = np.full(iterations, np.nan)
            bkg_counts_11 = np.full(iterations, np.nan)
            
            sig_counts_12 = np.full(iterations, np.nan)
            bkg_counts_12 = np.full(iterations, np.nan)
            
            sig_counts_13 = np.full(iterations, np.nan)
            bkg_counts_13 = np.full(iterations, np.nan)
            
            sig_1 = StreamingList()
            bkg_1 = StreamingList()
            
            sig_2 = StreamingList()
            bkg_2 = StreamingList()
            
            sig_3 = StreamingList()
            bkg_3 = StreamingList()
            
            sig_4 = StreamingList()
            bkg_4 = StreamingList()
            
            sig_5 = StreamingList()
            bkg_5 = StreamingList()
            
            sig_6 = StreamingList()
            bkg_6 = StreamingList()
            
            sig_7 = StreamingList()
            bkg_7 = StreamingList()
            
            sig_8 = StreamingList()
            bkg_8 = StreamingList()
            
            sig_9 = StreamingList()
            bkg_9 = StreamingList()
            
            sig_10 = StreamingList()
            bkg_10 = StreamingList()
            
            sig_11 = StreamingList()
            bkg_11 = StreamingList()
            
            sig_12 = StreamingList()
            bkg_12 = StreamingList()
            
            sig_13 = StreamingList()
            bkg_13 = StreamingList()
            
            sig_1.append(np.stack([time_counts, sig_counts_1]))
            bkg_1.append(np.stack([time_counts, bkg_counts_1]))
            
            sig_2.append(np.stack([time_counts, sig_counts_2]))
            bkg_2.append(np.stack([time_counts, bkg_counts_2]))
            
            sig_3.append(np.stack([time_counts, sig_counts_3]))
            bkg_3.append(np.stack([time_counts, bkg_counts_3]))
            
            sig_4.append(np.stack([time_counts, sig_counts_4]))
            bkg_4.append(np.stack([time_counts, bkg_counts_4]))
            
            sig_5.append(np.stack([time_counts, sig_counts_5]))
            bkg_5.append(np.stack([time_counts, bkg_counts_5]))
            
            sig_6.append(np.stack([time_counts, sig_counts_6]))
            bkg_6.append(np.stack([time_counts, bkg_counts_6]))
            
            sig_7.append(np.stack([time_counts, sig_counts_7]))
            bkg_7.append(np.stack([time_counts, bkg_counts_7]))
            
            sig_8.append(np.stack([time_counts, sig_counts_8]))
            bkg_8.append(np.stack([time_counts, bkg_counts_8]))
            
            sig_9.append(np.stack([time_counts, sig_counts_9]))
            bkg_9.append(np.stack([time_counts, bkg_counts_9]))
            
            sig_10.append(np.stack([time_counts, sig_counts_10]))
            bkg_10.append(np.stack([time_counts, bkg_counts_10]))
            
            sig_11.append(np.stack([time_counts, sig_counts_11]))
            bkg_11.append(np.stack([time_counts, bkg_counts_11]))
            
            sig_12.append(np.stack([time_counts, sig_counts_12]))
            bkg_12.append(np.stack([time_counts, bkg_counts_12]))
            
            sig_13.append(np.stack([time_counts, sig_counts_13]))
            bkg_13.append(np.stack([time_counts, bkg_counts_13]))
            
            sweep_start_time = time.time()
            
            # ---------------------------------------
            # Main acquisition loop
            # ---------------------------------------
            for i in range(iterations):
                    # Frequency 1
                    sg.set_frequency(probe_frequencies[0])
                    time.sleep(dwell_time)
                    sig_counts_1[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_1[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 2
                    sg.set_frequency(probe_frequencies[1])
                    time.sleep(dwell_time)
                    sig_counts_2[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_2[i] = mfli.get_background_PL(integration_time, 0)
                    
                    # Frequency 3
                    sg.set_frequency(probe_frequencies[2])
                    time.sleep(dwell_time)
                    sig_counts_3[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_3[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 4
                    sg.set_frequency(probe_frequencies[3])
                    time.sleep(dwell_time)
                    sig_counts_4[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_4[i] = mfli.get_background_PL(integration_time, 0)
                    
                    # Frequency 5
                    sg.set_frequency(probe_frequencies[4])
                    time.sleep(dwell_time)
                    sig_counts_5[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_5[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 6
                    sg.set_frequency(probe_frequencies[5])
                    time.sleep(dwell_time)
                    sig_counts_6[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_6[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 7
                    sg.set_frequency(probe_frequencies[6])
                    time.sleep(dwell_time)
                    sig_counts_7[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_7[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 8
                    sg.set_frequency(probe_frequencies[7])
                    time.sleep(dwell_time)
                    sig_counts_8[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_8[i] = mfli.get_background_PL(integration_time, 0)
                    
                    # Frequency 9
                    sg.set_frequency(probe_frequencies[8])
                    time.sleep(dwell_time)
                    sig_counts_9[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_9[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 10
                    sg.set_frequency(probe_frequencies[9])
                    time.sleep(dwell_time)
                    sig_counts_10[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_10[i] = mfli.get_background_PL(integration_time, 0)
                    
                    # Frequency 11
                    sg.set_frequency(probe_frequencies[10])
                    time.sleep(dwell_time)
                    sig_counts_11[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_11[i] = mfli.get_background_PL(integration_time, 0)
                   
                    # Frequency 12
                    sg.set_frequency(probe_frequencies[8])
                    time.sleep(dwell_time)
                    sig_counts_12[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_12[i] = mfli.get_background_PL(integration_time, 0)

                    # Frequency 13
                    sg.set_frequency(probe_frequencies[9])
                    time.sleep(dwell_time)
                    sig_counts_13[i] = odmr_driver.cnts(integration_time)

                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)
                    bkg_counts_13[i] = mfli.get_background_PL(integration_time, 0)
                    
                    time_counts[i] = i                  # ti.time() - sweep_start_time
                    
                    # ---------------------------------------
                    # Update StreamingLists
                    # ---------------------------------------
                    sig_1[-1] = np.stack([time_counts, sig_counts_1])
                    bkg_1[-1] = np.stack([time_counts, bkg_counts_1])

                    sig_2[-1] = np.stack([time_counts, sig_counts_2])
                    bkg_2[-1] = np.stack([time_counts, bkg_counts_2])

                    sig_3[-1] = np.stack([time_counts, sig_counts_3])
                    bkg_3[-1] = np.stack([time_counts, bkg_counts_3])

                    sig_4[-1] = np.stack([time_counts, sig_counts_4])
                    bkg_4[-1] = np.stack([time_counts, bkg_counts_4])
                    
                    sig_5[-1] = np.stack([time_counts, sig_counts_5])
                    bkg_5[-1] = np.stack([time_counts, bkg_counts_5])

                    sig_6[-1] = np.stack([time_counts, sig_counts_6])
                    bkg_6[-1] = np.stack([time_counts, bkg_counts_6])
                    
                    sig_7[-1] = np.stack([time_counts, sig_counts_7])
                    bkg_7[-1] = np.stack([time_counts, bkg_counts_7])

                    sig_8[-1] = np.stack([time_counts, sig_counts_8])
                    bkg_8[-1] = np.stack([time_counts, bkg_counts_8])

                    sig_9[-1] = np.stack([time_counts, sig_counts_9])
                    bkg_9[-1] = np.stack([time_counts, bkg_counts_9])

                    sig_10[-1] = np.stack([time_counts, sig_counts_10])
                    bkg_10[-1] = np.stack([time_counts, bkg_counts_10])
                    
                    sig_11[-1] = np.stack([time_counts, sig_counts_11])
                    bkg_11[-1] = np.stack([time_counts, bkg_counts_11])

                    sig_12[-1] = np.stack([time_counts, sig_counts_12])
                    bkg_12[-1] = np.stack([time_counts, bkg_counts_12])

                    sig_13[-1] = np.stack([time_counts, sig_counts_13])
                    bkg_13[-1] = np.stack([time_counts, bkg_counts_13])
                    
                    sig_1.updated_item(-1)
                    bkg_1.updated_item(-1)
                    sig_2.updated_item(-1)
                    bkg_2.updated_item(-1)
                    sig_3.updated_item(-1)
                    bkg_3.updated_item(-1)
                    sig_4.updated_item(-1)
                    bkg_4.updated_item(-1)
                    sig_5.updated_item(-1)
                    bkg_5.updated_item(-1)
                    sig_6.updated_item(-1)
                    bkg_6.updated_item(-1)
                    sig_7.updated_item(-1)
                    bkg_7.updated_item(-1)
                    sig_8.updated_item(-1)
                    bkg_8.updated_item(-1)
                    sig_9.updated_item(-1)
                    bkg_9.updated_item(-1)
                    sig_10.updated_item(-1)
                    bkg_10.updated_item(-1)
                    sig_11.updated_item(-1)
                    bkg_11.updated_item(-1)
                    sig_12.updated_item(-1)
                    bkg_12.updated_item(-1)
                    sig_13.updated_item(-1)
                    bkg_13.updated_item(-1)
                    
                    # ---------------------------------------
                    # Push data
                    # ---------------------------------------
                    odmr_data.push({
                        'params': {
                            'probe_frequencies': probe_frequencies,
                            'iterations': iterations
                            },
                        'title': 'CW ODMR Probe',
                        'xlabel': 'Time (s)',
                        'ylabel': 'Counts',
                        'datasets': {
                            'sig_1': sig_1,
                            'bkg_1': bkg_1,
                            'sig_2': sig_2,
                            'bkg_2': bkg_2,
                            'sig_3': sig_3,
                            'bkg_3': bkg_3,
                            'sig_4': sig_4,
                            'bkg_4': bkg_4,
                            'sig_5': sig_5,
                            'bkg_5': bkg_5,
                            'sig_6': sig_6,
                            'bkg_6': bkg_6,
                            'sig_7': sig_7,
                            'bkg_7': bkg_7,
                            'sig_8': sig_8,
                            'bkg_8': bkg_8,
                            'sig_9': sig_9,
                            'bkg_9': bkg_9,
                            'sig_10': sig_10,
                            'bkg_10': bkg_10,
                            'sig_11': sig_11,
                            'bkg_11': bkg_11,
                            'sig_12': sig_12,
                            'bkg_12': bkg_12,
                            'sig_13': sig_13,
                            'bkg_13': bkg_13,
                            }})
                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        sg.set_amplitude_rf(-20)
                        sg.set_output(0)
                        return


    def rabi_oscillations_lockin_ps82(
            self,
            dataset: str,
            freq_hz: float,
            pulse_start_ns: float,
            pulse_stop_ns: float,
            num_points: int,
            iterations: int,
            
            rf_amplitude: int,
            init_ns: int,
            readout_ns: int,
            mw_gap_ns_1: int = 50,
            mw_gap_ns_2: int = 50000,
            recovery_ns: int = 550000,
            
            dwell_time: float = 0.2,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using PulseStreamer8/2 + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
     #       mfli = mgr.mfli
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            time.sleep(0.01)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            pulse_lengths_ns = np.linspace(pulse_start_ns, pulse_stop_ns, num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([pulse_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([pulse_lengths_ns, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
           
                for idx, mw_ns in enumerate(pulse_lengths_ns):
                    
                   # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                   # mfli.set_demod_freq(mfli_mod_freq) 
                   
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_ns,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_ns,0),(readout_ns,1),(recovery_ns,0)]
                    
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),(mw_gap_ns_2 - mw_ns,0),(readout_ns,0),(recovery_ns,0),
                              (init_ns + mw_gap_ns_1 + mw_ns + (mw_gap_ns_2 - mw_ns) + readout_ns + recovery_ns,0)]
                    
                    trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(mw_ns,1),(mw_gap_ns_2 - mw_ns,1),(readout_ns,1),(recovery_ns,1),
                                (init_ns,0),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_ns,0),(readout_ns,0),(recovery_ns,0)]
               
                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)
               
                    ps82.begin_pulses(n_runs=-1)              
                                      
                    # Signal
                    time.sleep(dwell_time)# + integration_time)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time) #+ integration_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([pulse_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([pulse_lengths_ns, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    data.push({
                       'params': {
                           'start': pulse_start_ns,
                           'stop': pulse_stop_ns,
                           'num_points': num_points,
                           'iterations': iterations},
                       'title': 'Rabi ODMR Sweep',
                       'xlabel': 'Microwave Pulse Length / ns',   
                       'ylabel': 'Signal',
                       'datasets': {
                           'signal':     signal_sweeps,
                           'background': background_sweeps}})                 
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                       sg.set_amplitude_rf(-30)
                       ps82.stop()
                       return


    def pulsed_odmr_sweep_linear_lockin_ps82(self,
                   dataset: str,
                   start_freq: float,
                   stop_freq: float,
                   num_points: int,
                   iterations: int,
                   rf_amplitude: int,
                   
                   # --- PulseStreamer 8/2 ---
                   init_ns: int,
                   readout_ns: int,
                   pulse_length_ns: int,
                   mw_gap_ns_1: int = 5,
                   mw_gap_ns_2: int = 5,
                   recovery_ns: int = 600000,

                   detector_delay_ns: int = 100,    # Laser channel delay, to be 
                                                    # determined by readout optimisation on TimeTagger. Can be checked on the oscilloscope
                   dwell_time: float = 0.05,                                
                   integration_time: float = 1,   # time for accumulations of pulse sequences
                   ):

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
         
         odmr = mgr.odmr_driver
         sg = mgr.sg
         ps82 = mgr.ps82
       #  mfli = mgr.mfli
         
         sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
         sg.set_output(1)
         
         time.sleep(0.01)
                     
         # --------------------------------
         # Sweep definition
         # --------------------------------
         freqs = np.linspace(start_freq, stop_freq, num_points)
         linear_order = range(num_points)
         
         # --- NEW independent dataset ---
         time_spent = StreamingList()
         sweep_start_time = time.time()
         
         signal_sweeps = StreamingList()
         background_sweeps = StreamingList()
         
         ps82.channel_sequences = {}  # Clear previous
            
         # --------------------------------
         # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
         # --------------------------------
         laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(pulse_length_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0),
                      (init_ns,1),(mw_gap_ns_1,0),(pulse_length_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
         
         mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(pulse_length_ns,1),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0),
                   (init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
         
         red_q = [(init_ns,0),(mw_gap_ns_1,1),(pulse_length_ns,1),(mw_gap_ns_2,1),(readout_ns,1),(recovery_ns,0),
                   (init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
         
         trig_seq = [(init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns + 
                      init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
      
         ps82.allocate_sequence(mw_seq, 0)
         ps82.allocate_sequence(laser_seq, 1)
         ps82.allocate_sequence(trig_seq, 2)
         ps82.allocate_sequence(red_q, 4)
   
         ps82.begin_pulses(n_runs=-1)       
         
         for i in range(iterations):
             
            sig_counts = np.empty(num_points)
            sig_counts[:] = np.nan
            bg_counts = np.empty(num_points)
            bg_counts[:] = np.nan
            
            # --- NEW per-iteration time array ---
            time_counts = np.empty(num_points)
            time_counts[:] = np.nan
             
            # Append initial empty arrays to all StreamingLists
            signal_sweeps.append(np.stack([freqs/1e9, sig_counts]))
            background_sweeps.append(np.stack([freqs/1e9, bg_counts]))
            time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
             
            # --------------------------------
            # MW freq sweep
            # --------------------------------
            for idx in linear_order:      
                 freq = freqs[idx]
                
                 sg.set_frequency(freq)
                    
                 # Signal
                 time.sleep(dwell_time)
                 sig_counts[idx] = odmr.cnts(integration_time)
                    
                 # Background
                 sg.set_frequency(100e3)
                 time.sleep(dwell_time)
                 bg_counts[idx] = odmr.cnts(integration_time)
                    
                 # --- collect elapsed time since sweep start ---
                 time_counts[idx] = time.time() - sweep_start_time
                    
                 # Update streaming entries
                 signal_sweeps[-1] = np.stack([freqs/1e9, sig_counts])
                 background_sweeps[-1] = np.stack([freqs/1e9, bg_counts])
                 time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                 signal_sweeps.updated_item(-1)
                 background_sweeps.updated_item(-1)
                 time_spent.updated_item(-1)
                
                 data.push({
                       'params': {
                           'start': start_freq,
                           'stop': stop_freq,
                           'num_points': num_points,
                           'iterations': iterations},
                       "title": "PMT ODMR",
                       "xlabel": " Frequency / GHz",
                       "ylabel": "Integrated Counts",
                       "datasets": {
                         "signal": signal_sweeps,
                         "background": background_sweeps,
                         "time": time_spent}})
                 
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     sg.set_output(0)
                     ps82.stop()
                     return


    def hahn_echo_lockin_ps82(
                self,
                dataset: str,
                freq_hz: float,
                tau_start_ns: float,
                tau_stop_ns: float,
                num_points: int,
                iterations: int,
                
                rf_amplitude: int,
                init_ns: int,
                readout_ns: int,
                mw_gap_ns_1: int = 50,
                pi: int = 570,
                mw_gap_ns_2: int = 50000,
                recovery_ns: int = 550000,
                
                dwell_time: float = 0.20,
                integration_time: float = 1,   # time for accumulations of pulse sequences
                ):
            """
            Pulsed Hahn-Echo experiment using PulseStreamer8/2 + Lock-in Amplifier.        
            Signal      = init + MW + readout
            Background  = init + readout (no MW)

            Stored data:
                x-axis → MW pulse length (ns)
                y-axis → Integrated photon counts
            """

            with MyInstrumentManager() as mgr, DataSource(dataset) as data:
                
                odmr = mgr.odmr_driver
                sg = mgr.sg
                ps82 = mgr.ps82
         #       mfli = mgr.mfli
                
                # --------------------------------
                # Microwave frequency
                # --------------------------------
                sg.set_frequency(freq_hz)
                sg.set_amplitude_rf(rf_amplitude)
                
                time.sleep(0.01)
                            
                # --------------------------------
                # Sweep definition
                # --------------------------------
                tau_lengths_ns = np.linspace(tau_start_ns, tau_stop_ns, num_points)

                # --- NEW independent dataset ---
                time_spent = StreamingList()
                sweep_start_time = time.time()
                
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                
                for i in range(iterations):
                    
                    sig_counts = np.empty(num_points)
                    sig_counts[:] = np.nan
                    bg_counts = np.empty(num_points)
                    bg_counts[:] = np.nan
                    
                    # --- NEW per-iteration time array ---
                    time_counts = np.empty(num_points)
                    time_counts[:] = np.nan
                    
                    # Append initial empty arrays to all StreamingLists
                    signal_sweeps.append(np.stack([tau_lengths_ns, sig_counts]))
                    background_sweeps.append(np.stack([tau_lengths_ns, bg_counts]))
                    time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
               
                    for idx, tau in enumerate(tau_lengths_ns):
                        
                       # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                       # mfli.set_demod_freq(mfli_mod_freq)
                       
                        sg.set_frequency(freq_hz)
                        
                        pi_half = pi/2
                        
                        ps82.channel_sequences = {}  # Clear previous
                        
                        # --------------------------------
                        # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                        # --------------------------------
                        laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,1),(recovery_ns,0),
                                     (init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,1),(recovery_ns,0)]
                        
                        mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(pi_half,1),(tau,0),(pi,1),(tau,0),(pi_half,1),(mw_gap_ns_2 - 2*tau,0),(readout_ns,0),(recovery_ns,0),
                                  (init_ns,0),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,0),(recovery_ns,0)]
                        
                        trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,0),(recovery_ns,0),
                                  (init_ns,0),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,0),(recovery_ns,0)]
                   
                        # Not yet modified - need updating with ANALOG signals -1, 0, +1
                        IQ_seq = [(init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - 2*tau,0),(readout_ns,1),(recovery_ns,0)]
                    
                        ps82.allocate_sequence(mw_seq, 0)
                        ps82.allocate_sequence(laser_seq, 1)
                        ps82.allocate_sequence(trig_seq, 2)
                   
                        ps82.begin_pulses(n_runs=-1)              
                                          
                        # Signal
                        time.sleep(dwell_time) # + integration_time)
                        sig_counts[idx] = odmr.cnts(integration_time)
                        
                        # Background
                        sg.set_frequency(100e3)
                        time.sleep(dwell_time) # + integration_time)
                        bg_counts[idx] = odmr.cnts(integration_time)
                        
                        # --- collect elapsed time since sweep start ---
                        time_counts[idx] = time.time() - sweep_start_time
                        
                        # Update streaming entries
                        signal_sweeps[-1] = np.stack([tau_lengths_ns, sig_counts])
                        background_sweeps[-1] = np.stack([tau_lengths_ns, bg_counts])
                        time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_spent.updated_item(-1)
                        
                        # Push dataset including new time series
                        data.push({
                           'params': {
                               'start': tau_start_ns,
                               'stop': tau_stop_ns,
                               'num_points': num_points,
                               'iterations': iterations},
                           'title': 'Hahn Echo',
                           'xlabel': '2tau / ns',   
                           'ylabel': 'Signal',
                           'datasets': {
                               'signal':     signal_sweeps,
                               'background': background_sweeps,
                               "time": time_spent}})
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                           ps82.stop() 
                           return


    def microwave_delay_opt_lockin_ps82(
            self,
            dataset: str,
            freq_hz: float,
            delay_start_ns: float,
            delay_stop_ns: float,
            num_points: int,
            iterations: int,
            
            rf_amplitude: int,
            init_ns: int,
            readout_ns: int,
            mw_ns: int = 0,
            mw_gap_ns_2: int = 50000,
            recovery_ns: int = 550000,
            
            dwell_time: float = 0.2,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using PulseStreamer8/2 + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
     #       mfli = mgr.mfli
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            time.sleep(0.01)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            delay_lengths_ns = np.linspace(delay_start_ns, delay_stop_ns, num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([delay_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([delay_lengths_ns, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
           
                for idx, mw_gap_ns_1 in enumerate(delay_lengths_ns):
                    
                   # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                   # mfli.set_demod_freq(mfli_mod_freq)
                   
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_gap_ns_1,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_gap_ns_1,0),(readout_ns,1),(recovery_ns,0)]
                    
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),(mw_gap_ns_2 - mw_gap_ns_1,0),(readout_ns,0),(recovery_ns,0),
                              (init_ns + mw_gap_ns_1 + mw_ns + (mw_gap_ns_2 - mw_gap_ns_1) + readout_ns + recovery_ns,0)]
                    
                    trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(mw_ns,1),(mw_gap_ns_2 - mw_gap_ns_1,1),(readout_ns,1),(recovery_ns,1),
                                (init_ns,0),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_gap_ns_1,0),(readout_ns,0),(recovery_ns,0)]
               
                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)
               
                    ps82.begin_pulses(n_runs=-1)              
                                      
                    # Signal
                    time.sleep(dwell_time)   #+ integration_time)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)    # + integration_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([delay_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([delay_lengths_ns, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    data.push({
                       'params': {
                           'start': delay_start_ns,
                           'stop': delay_stop_ns,
                           'num_points': num_points,
                           'iterations': iterations},
                       'title': 'Microwave Delay ODMR Sweep',
                       'xlabel': 'Initialisation to Microwave Delay / ns',   
                       'ylabel': 'Signal',
                       'datasets': {
                           'signal':     signal_sweeps,
                           'background': background_sweeps}})                 
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                       return


    def initialisation_opt_lockin_ps82(
            self,
            dataset: str,
            freq_hz: float,
            init_start_ns: float,
            init_stop_ns: float,
            num_points: int,
            iterations: int,
            rf_amplitude: int,
            
            readout_ns: int,
            mw_ns: int = 0,
            mw_gap_ns_1: int = 50,
            mw_gap_ns_2: int = 50000,
            recovery_ns: int = 550000,
            
            dwell_time: float = 0.2,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using PulseStreamer8/2 + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
     #       mfli = mgr.mfli
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            time.sleep(0.01)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            init_lengths_ns = np.linspace(init_start_ns, init_stop_ns, num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([init_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([init_lengths_ns, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
           
                for idx, init_ns in enumerate(init_lengths_ns):
                    
                   # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                   # mfli.set_demod_freq(mfli_mod_freq)
                   
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
                    
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0),
                              (init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
                    
                    trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(mw_ns,1),(mw_gap_ns_2,1),(readout_ns,1),(recovery_ns,1),
                                (init_ns,0),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
               
                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)
               
                    ps82.begin_pulses(n_runs=-1)              
                                      
                    # Signal
                    time.sleep(dwell_time)   #+ integration_time)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)    # + integration_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([init_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([init_lengths_ns, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    data.push({
                       'params': {
                           'start': init_start_ns,
                           'stop': init_stop_ns,
                           'num_points': num_points,
                           'iterations': iterations},
                       'title': 'Iniitalisation Pulse Optimisation Sweep',
                       'xlabel': 'Initialisation Pulse Length / ns',   
                       'ylabel': 'Signal',
                       'datasets': {
                           'signal':     signal_sweeps,
                           'background': background_sweeps}})                 
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                       ps82.stop() 
                       return


    def readout_opt_lockin_ps82(
            self,
            dataset: str,
            freq_hz: float,
            readout_start_ns: float,
            readout_stop_ns: float,
            num_points: int,
            iterations: int,
            rf_amplitude: int,
            
            init_ns: int,
            mw_ns: int = 0,
            mw_gap_ns_1: int = 50,
            mw_gap_ns_2: int = 50000,
            recovery_ns: int = 600000,
            
            dwell_time: float = 0.2,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using PulseStreamer8/2 + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
     #       mfli = mgr.mfli
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            time.sleep(0.01)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            readout_lengths_ns = np.linspace(readout_start_ns, readout_stop_ns, num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([readout_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([readout_lengths_ns, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
           
                for idx, readout_ns in enumerate(readout_lengths_ns):
                    
                   # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                   # mfli.set_demod_freq(mfli_mod_freq)
                   
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - readout_ns,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - readout_ns,0),(readout_ns,1),(recovery_ns,0)]
                    
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),(mw_gap_ns_2 - readout_ns,0),(readout_ns,0),(recovery_ns,0),
                              (init_ns + mw_gap_ns_1 + mw_ns + (mw_gap_ns_2 - readout_ns) + readout_ns + recovery_ns,0)]
                    
                    trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(mw_ns,1),(mw_gap_ns_2 - readout_ns,1),(readout_ns,1),(recovery_ns,1),
                                (init_ns,0),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - readout_ns,0),(readout_ns,0),(recovery_ns,0)]
               
                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)
               
                    ps82.begin_pulses(n_runs=-1)              
                                      
                    # Signal
                    time.sleep(dwell_time)   #+ integration_time)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)    # + integration_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([readout_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([readout_lengths_ns, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    data.push({
                       'params': {
                           'start': readout_start_ns,
                           'stop': readout_stop_ns,
                           'num_points': num_points,
                           'iterations': iterations},
                       'title': 'Readout Pulse Optimisation Sweep',
                       'xlabel': 'Readout Pulse Length / ns',   
                       'ylabel': 'Signal',
                       'datasets': {
                           'signal':     signal_sweeps,
                           'background': background_sweeps}})                 
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                       ps82.stop()
                       return


    def readout_delay_opt_lockin_ps82(
            self,
            dataset: str,
            freq_hz: float,
            delay_start_ns: float,
            delay_stop_ns: float,
            num_points: int,
            iterations: int,
            rf_amplitude: int,
            
            init_ns: int,
            mw_ns: int = 0,
            mw_gap_ns_1: int = 50,
            readout_ns: int = 50000,
            recovery_ns: int = 600000,
            
            dwell_time: float = 0.2,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        An experiment optimise the contrast by determining the optimum readout 
        delay using PulseStreamer8/2 + Lock-in amplifier (PMT)        
        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → Readout Pulse Delay length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
     #       mfli = mgr.mfli
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            time.sleep(0.01)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            delay_lengths_ns = np.linspace(delay_start_ns, delay_stop_ns, num_points)

            # --- NEW independent dataset ---
            time_spent = StreamingList()
            sweep_start_time = time.time()
            
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            
            for i in range(iterations):
                
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan
                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan
                
                # --- NEW per-iteration time array ---
                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
                
                # Append initial empty arrays to all StreamingLists
                signal_sweeps.append(np.stack([delay_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([delay_lengths_ns, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
           
                for idx, mw_gap_ns_2 in enumerate(delay_lengths_ns):
                    
                   # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                   # mfli.set_demod_freq(mfli_mod_freq)
                   
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0),
                                 (init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
                    
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0),
                              (init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
                    
                    trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(mw_ns,1),(mw_gap_ns_2,1),(readout_ns,1),(recovery_ns,1),
                                (init_ns,0),(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
               
                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)
               
                    ps82.begin_pulses(n_runs=-1)              
                                      
                    # Signal
                    time.sleep(dwell_time)   #+ integration_time)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    # Background
                    sg.set_frequency(100e3)
                    time.sleep(dwell_time)    # + integration_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    # --- collect elapsed time since sweep start ---
                    time_counts[idx] = time.time() - sweep_start_time
                    
                    # Update streaming entries
                    signal_sweeps[-1] = np.stack([delay_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([delay_lengths_ns, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                    
                    # Push dataset including new time series
                    data.push({
                       'params': {
                           'start': delay_start_ns,
                           'stop': delay_stop_ns,
                           'num_points': num_points,
                           'iterations': iterations},
                       'title': 'Readout Pulse Delay Optimisation Sweep',
                       'xlabel': 'Readout Delay Length / ns',   
                       'ylabel': 'Signal',
                       'datasets': {
                           'signal':     signal_sweeps,
                           'background': background_sweeps}})                 
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                       ps82.stop()
                       return


    def ramsey_lockin_ps82(
                self,
                dataset: str,
                freq_hz: float,
                tau_start_ns: float,
                tau_stop_ns: float,
                num_points: int,
                iterations: int,
                
                rf_amplitude: int,
                init_ns: int,
                readout_ns: int,
                mw_gap_ns_1: int = 50,
                pi: int = 570,
                mw_gap_ns_2: int = 50000,
                recovery_ns: int = 550000,
                
                dwell_time: float = 0.20,
                integration_time: float = 1,   # time for accumulations of pulse sequences
                ):
            """
            Pulsed Hahn-Echo experiment using PulseStreamer8/2 + Lock-in Amplifier.        
            Signal      = init + MW + readout
            Background  = init + readout (no MW)

            Stored data:
                x-axis → MW pulse length (ns)
                y-axis → Integrated photon counts
            """

            with MyInstrumentManager() as mgr, DataSource(dataset) as data:
                
                odmr = mgr.odmr_driver
                sg = mgr.sg
                ps82 = mgr.ps82
         #       mfli = mgr.mfli
                
                # --------------------------------
                # Microwave frequency
                # --------------------------------
                sg.set_frequency(freq_hz)
                sg.set_amplitude_rf(rf_amplitude)
                
                time.sleep(0.01)
                            
                # --------------------------------
                # Sweep definition
                # --------------------------------
                tau_lengths_ns = np.linspace(tau_start_ns, tau_stop_ns, num_points)

                # --- NEW independent dataset ---
                time_spent = StreamingList()
                sweep_start_time = time.time()
                
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                
                for i in range(iterations):
                    
                    sig_counts = np.empty(num_points)
                    sig_counts[:] = np.nan
                    bg_counts = np.empty(num_points)
                    bg_counts[:] = np.nan
                    
                    # --- NEW per-iteration time array ---
                    time_counts = np.empty(num_points)
                    time_counts[:] = np.nan
                    
                    # Append initial empty arrays to all StreamingLists
                    signal_sweeps.append(np.stack([tau_lengths_ns, sig_counts]))
                    background_sweeps.append(np.stack([tau_lengths_ns, bg_counts]))
                    time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
               
                    for idx, tau in enumerate(tau_lengths_ns):
                        
                       # mfli_mod_freq = 1/((init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns)*1e-9)  
                       # mfli.set_demod_freq(mfli_mod_freq)
                       
                        sg.set_frequency(freq_hz)
                        
                        pi_half = pi/2
                        
                        ps82.channel_sequences = {}  # Clear previous
                        
                        # --------------------------------
                        # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                        # --------------------------------
                        laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - tau,0),(readout_ns,1),(recovery_ns,0),
                                     (init_ns,1),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - tau,0),(readout_ns,1),(recovery_ns,0)]
                        
                        mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(pi_half,1),(tau,0),(pi_half,1),(mw_gap_ns_2 - tau,0),(readout_ns,0),(recovery_ns,0),
                                  (init_ns,0),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - tau,0),(readout_ns,0),(recovery_ns,0)]
                        
                        trig_seq = [(init_ns,1),(mw_gap_ns_1,1),(pi_half,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - tau,0),(readout_ns,0),(recovery_ns,0),
                                  (init_ns,0),(mw_gap_ns_1,0),(pi_half,0),(tau,0),(pi_half,0),(mw_gap_ns_2 - tau,0),(readout_ns,0),(recovery_ns,0)]
                   
                        ps82.allocate_sequence(mw_seq, 0)
                        ps82.allocate_sequence(laser_seq, 1)
                        ps82.allocate_sequence(trig_seq, 2)
                   
                        ps82.begin_pulses(n_runs=-1)              
                                          
                        # Signal
                        time.sleep(dwell_time) # + integration_time)
                        sig_counts[idx] = odmr.cnts(integration_time)
                        
                        # Background
                        sg.set_frequency(100e3)
                        time.sleep(dwell_time) # + integration_time)
                        bg_counts[idx] = odmr.cnts(integration_time)
                        
                        # --- collect elapsed time since sweep start ---
                        time_counts[idx] = time.time() - sweep_start_time
                        
                        # Update streaming entries
                        signal_sweeps[-1] = np.stack([tau_lengths_ns, sig_counts])
                        background_sweeps[-1] = np.stack([tau_lengths_ns, bg_counts])
                        time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_spent.updated_item(-1)
                        
                        # Push dataset including new time series
                        data.push({
                           'params': {
                               'start': tau_start_ns,
                               'stop': tau_stop_ns,
                               'num_points': num_points,
                               'iterations': iterations},
                           'title': 'Ramsey Spectroscopy',
                           'xlabel': 'tau / ns',   
                           'ylabel': 'Signal',
                           'datasets': {
                               'signal':     signal_sweeps,
                               'background': background_sweeps,
                               "time": time_spent}})
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                           ps82.stop() 
                           return


    def two_pulsed_odmr_sweep_linear_lockin_ps82_awg(self,
                   dataset: str,
                   start_freq: float,
                   stop_freq: float,
                   sg_freq: float,
                   num_points: int,
                   iterations: int,
                   rf_amplitude: int,
                   
                   # --- PulseStreamer 8/2 ---
                   init_ns: int,
                   readout_ns: int,
                   sg_pulse_length_ns: int,
                   hmc_pulse_length_ns: int,
                   mw_gap_ns_1: int = 5,
                   mw_gap_ns_2: int = 5,
                   recovery_ns: int = 600000,
                   
                   # AWG Bullshit
                   total_time_us: float = 1000,   # This needs to be understood
                   sample_rate: float = 75e6,

                   detector_delay_ns: int = 100,    # Laser channel delay, to be 
                                                    # determined by readout optimisation on TimeTagger. Can be checked on the oscilloscope
                   dwell_time: float = 0.05,                                
                   integration_time: float = 1,   # time for accumulations of pulse sequences
                   ):

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
         
         odmr = mgr.odmr_driver
         sg = mgr.sg
         ps82 = mgr.ps82
         hmc = mgr.hmc
         awg = mgr.awg
       #  mfli = mgr.mfli
         
         sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
         sg.set_frequency(sg_freq)
         sg.set_output(1)
         
         hmc.set_amplitude(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
         hmc.set_output(1)
         
         # --------------------------------
         # AWG burst configuration (ONCE)
         # --------------------------------
   #      awg.instrument.write("C1:BTWV PRD,0.002460005")
         awg.instrument.write("C1:BTWV PRD,0.003")
         awg.output(2, True)
         awg.set_arb_mode(2)
         awg.set_burst_mode(2, True)
         awg.set_amplitude(2,8)
         
         # --------------------------------
         # AWG time base
         # --------------------------------
         total_time_s = total_time_us * 1e-6
         num_pts = int(round(sample_rate * total_time_s))
         
         time.sleep(0.01)
                     
         # --------------------------------
         # Sweep definition
         # --------------------------------
         freqs = np.linspace(start_freq, stop_freq, num_points)
         linear_order = range(num_points)
         
         # --- NEW independent dataset ---
         time_spent = StreamingList()
         sweep_start_time = time.time()
         
         signal_sweeps = StreamingList()
         background_sweeps = StreamingList()
                  
         # --------------------------------
         # AWG Pulse timing - remember, the native units of python is seconds, but the TT is picoseconds
         # --------------------------------
         init_ns = init_ns * 1e-9
         hmc_pulse_length_ns = hmc_pulse_length_ns * 1e-9
         sg_pulse_length_ns = sg_pulse_length_ns * 1e-9
         readout_ns = readout_ns * 1e-9
         mw_gap_ns_1 = mw_gap_ns_1 * 1e-9
         mw_gap_ns_2 = mw_gap_ns_2 * 1e-9
         recovery_ns = recovery_ns * 1e-9
        # ch2_delay_t = ch2_delay_ns * 1e-9
         
         mw_start = init_ns + mw_gap_ns_1
        
         # ======================================================================================
         # AWG SIGNAL SEQUENCE (with MW)
         # ======================================================================================
         w_mw = np.zeros(num_pts)
         
         odmr.apply_pulse(w_mw, mw_start, sg_pulse_length_ns, 8.0, sample_rate)
         
         odmr.load_arbitrary_waveform_burst(
            channel=2,
            data=w_mw,
            name="rabi_mw",
            sample_rate=sample_rate)
         
         
         ps82.channel_sequences = {}  # Clear previous
            
         # --------------------------------
         # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
         # --------------------------------
         laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(sg_pulse_length_ns,0),(hmc_pulse_length_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0),
                      (init_ns,1),(mw_gap_ns_1,0),(sg_pulse_length_ns,0),(hmc_pulse_length_ns,0),(mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
         
   #      sg_mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(sg_pulse_length_ns,0),(hmc_pulse_length_ns,1),(mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0),
   #                (init_ns + mw_gap_ns_1 + sg_pulse_length_ns + hmc_pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
         
         hmc_mw_seq = [(init_ns,0),(mw_gap_ns_1,1),(sg_pulse_length_ns,1),(hmc_pulse_length_ns,0),(mw_gap_ns_2,1),(readout_ns,1),(recovery_ns,0),
                   (init_ns + mw_gap_ns_1 + sg_pulse_length_ns + hmc_pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
         
         trig_seq = [(init_ns + mw_gap_ns_1 + sg_pulse_length_ns + hmc_pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns + 
                      init_ns + mw_gap_ns_1 + sg_pulse_length_ns + hmc_pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
      
    #     ps82.allocate_sequence(sg_mw_seq, 0)
         ps82.allocate_sequence(laser_seq, 1)
         ps82.allocate_sequence(trig_seq, 2)
         ps82.allocate_sequence(hmc_mw_seq, 4)
   
         ps82.begin_pulses(n_runs=-1, trigger=TriggerStart.HARDWARE_RISING)     # Triggering from the AUX output of the AWG 
                                      
         time.sleep(0.01)
         
         for i in range(iterations):
             
            sig_counts = np.empty(num_points)
            sig_counts[:] = np.nan
            bg_counts = np.empty(num_points)
            bg_counts[:] = np.nan
            
            # --- NEW per-iteration time array ---
            time_counts = np.empty(num_points)
            time_counts[:] = np.nan
             
            # Append initial empty arrays to all StreamingLists
            signal_sweeps.append(np.stack([freqs/1e9, sig_counts]))
            background_sweeps.append(np.stack([freqs/1e9, bg_counts]))
            time_spent.append(np.stack([time_counts, sig_counts]))  # uses sig_counts as Y
             
            # --------------------------------
            # MW freq sweep
            # --------------------------------
            for idx in linear_order:      
                 freq = freqs[idx]
                
                 hmc.set_frequency(freq)
                    
                 # Signal
                 time.sleep(dwell_time)
                 sig_counts[idx] = odmr.cnts(integration_time)
                    
                 # Background
                 sg.set_frequency(100e3)
                 time.sleep(dwell_time)
                 bg_counts[idx] = odmr.cnts(integration_time)
                    
                 # --- collect elapsed time since sweep start ---
                 time_counts[idx] = time.time() - sweep_start_time
                    
                 # Update streaming entries
                 signal_sweeps[-1] = np.stack([freqs/1e9, sig_counts])
                 background_sweeps[-1] = np.stack([freqs/1e9, bg_counts])
                 time_spent[-1] = np.stack([time_counts, sig_counts])  # time x, signal y
                    
                 signal_sweeps.updated_item(-1)
                 background_sweeps.updated_item(-1)
                 time_spent.updated_item(-1)
                
                 data.push({
                       'params': {
                           'start': start_freq,
                           'stop': stop_freq,
                           'num_points': num_points,
                           'iterations': iterations},
                       "title": "PMT ODMR",
                       "xlabel": " Frequency / GHz",
                       "ylabel": "Integrated Counts",
                       "datasets": {
                         "signal": signal_sweeps,
                         "background": background_sweeps,
                         "time": time_spent}})
                 
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     sg.set_output(0)
                     ps82.stop()
                     return
#------------------------------------------------------------------------------
# Cerium Experiments - Laser pulses are achieved by square wave modulation 
#                      through the AWG, and detection is achieved using 
#                      manually set modulation through the signal generator.
#------------------------------------------------------------------------------

    def ce_odmr_cw_lockin(
        self,
        dataset: str,
        start_freq: float,
        stop_freq: float,
        num_points: int,
        iterations: int,
        rf_amplitude: int,

        # Laser pulse parameters
        laser_on_ns: int,
        laser_off_ns: int,

        # Lock-in parameters
        mw_period_ns: int,       # full period (e.g. 100_000 ns → 10 kHz)
        mw_offset_ns: int = 0,   # phase offset

        # Sequence control
        sequence_duration_ns: int = 1_000_000,  # total sequence length (e.g. 1 ms)

        dwell_time: float = 0.1,
        integration_time: float = 0.1):

        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:

            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
            
            # ----------------------------------------
            # Microwave setup
            # ----------------------------------------
            sg.set_amplitude_rf(rf_amplitude)
            sg.set_output(1)

            time.sleep(0.1)
            
            frequencies = np.linspace(start_freq, stop_freq, num_points)
            linear_order = range(num_points)
            
            # ----------------------------------------
            # Build LASER sequence (fast pulses)
            # ----------------------------------------
            laser_on_ns = int(laser_on_ns)
            laser_off_ns = int(laser_off_ns)
            
            pulse_period = laser_on_ns + laser_off_ns
            
            # Number of pulses needed to fill total duration
            num_pulses = sequence_duration_ns // pulse_period
            
            laser_seq = [(laser_on_ns, 1), (laser_off_ns, 0)] * int(num_pulses)
            
            # Handle remainder to EXACTLY match total duration
            elapsed = sum(t for t, _ in laser_seq)
            remaining = sequence_duration_ns - elapsed
            
            if remaining > 0:
                if remaining <= laser_on_ns:
                    laser_seq.append((remaining, 1))
                else:
                    laser_seq.append((laser_on_ns, 1))
                    laser_seq.append((remaining - laser_on_ns, 0))

            # Final check
            total_laser = sum(t for t, _ in laser_seq)
            if total_laser != sequence_duration_ns:
                raise RuntimeError("Laser sequence duration mismatch")

            # ----------------------------------------
            # Build MW square wave (lock-in modulation)
            # ----------------------------------------
            mw_seq = ps82.square_wave(
                total_duration_ns=sequence_duration_ns,
                period_ns=mw_period_ns,
                duty_cycle=0.5,
                offset_ns=mw_offset_ns)

            # ----------------------------------------
            # Trigger (lock-in reference)
            # Same as MW but clean 50% duty, no offset
            # ----------------------------------------
            trig_seq = ps82.square_wave(
                total_duration_ns=sequence_duration_ns,
                period_ns=mw_period_ns,
                duty_cycle=0.5,
                offset_ns=0)

            print(f"Lock-in frequency ≈ {1e9 / mw_period_ns:.2f} Hz")

            # ----------------------------------------
            # Load PulseStreamer
            # ----------------------------------------
            ps82.allocate_sequence(mw_seq, 0)
            ps82.allocate_sequence(laser_seq, 1)
            ps82.allocate_sequence(trig_seq, 2)
            
            ps82.begin_pulses(n_runs=-1)

            # --------------------------------------------------------
            # Streaming datasets
            # --------------------------------------------------------

            time_spent = StreamingList()
            sweep_start_time = time.time()
         
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()

            for i in range(iterations):
             
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan

                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan

                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
             
                signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))

                for idx in linear_order:

                    freq = frequencies[idx]
                    
                    # Only frequency changes — modulation handled in hardware
                    sg.set_frequency(freq)
                    
                    time.sleep(dwell_time)
                    
                    # Lock-in output (already demodulated)
                    sig_counts[idx] = odmr.cnts(integration_time)
                    
                    
                    sg.set_frequency(100e3)
                    
                    time.sleep(dwell_time)
                    bg_counts[idx] = odmr.cnts(integration_time)
                    
                    time_counts[idx] = time.time() - sweep_start_time
                     
                    signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                    background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                    time_spent[-1] = np.stack([time_counts, sig_counts])
                     
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_spent.updated_item(-1)
                     
                    odmr_data.push({
                         'params': {
                             'start': start_freq,
                             'stop': stop_freq,
                             'num_points': num_points,
                             'iterations': iterations
                             },
                         'title': 'Linear ODMR Sweep',
                         'xlabel': 'Frequency (GHz)',
                         'ylabel': 'Signal',
                         'datasets': {
                             'signal': signal_sweeps,
                             'background': background_sweeps,
                             'time_spent': time_spent
                             }})

                    if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                        ps82.stop()
                        return


    def ce_odmr_pulsed_sweep_linear_lockin(self,
                   dataset: str,
                   start_freq: float,
                   stop_freq: float,
                   num_points: int,
                   iterations: int,
                   rf_amplitude: int,

                   num_init_pulses: int,
                   num_readout_pulses: int,
                   
                   #---- ps82 ----#
                   init_ns: int,
                   init_gap_ns: int,
                   mw_gap_ns_1: int,
                   mw_ns: int,
                   mw_gap_ns_2: int,
                   readout_ns: int,
                   recovery_ns: int,
                   
                   dwell_time: float = 0.1,
                   integration_time: float = 0.1):

         with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
         
            odmr = mgr.odmr_driver
            sg = mgr.sg
            ps82 = mgr.ps82
         
            sg.set_amplitude_rf(rf_amplitude)
            sg.set_output(1)
         
            time.sleep(0.1)
         
            frequencies = np.linspace(start_freq, stop_freq, num_points)
            linear_order = range(num_points)
         
            # --------------------------------------------------------
            # Build pulse trains
            # --------------------------------------------------------
            num_init_pulses = int(num_init_pulses)
            num_readout_pulses = int(num_readout_pulses)
            init_train = [(init_ns,1),(init_gap_ns,0)] * num_init_pulses
            readout_train = [(readout_ns,1),(readout_ns,0)] * num_readout_pulses

            init_total = sum(t for t,_ in init_train)
            readout_total = sum(t for t,_ in readout_train)

             # --------------------------------------------------------
             # Laser sequence
             # --------------------------------------------------------

            laser_seq = (
                 init_train +
                 [(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_ns,0)] +
                 readout_train +
                 [(recovery_ns,0)] +
                 init_train +
                 [(mw_gap_ns_1,0),(mw_ns,0),(mw_gap_ns_2 - mw_ns,0)] +
                 readout_train +
                 [(recovery_ns,0)])

             # --------------------------------------------------------
             # Microwave sequence
             # --------------------------------------------------------

            mw_seq = [
                 (init_total,0),
                 (mw_gap_ns_1,0),
                 (mw_ns,1),
                 (mw_gap_ns_2 - mw_ns,0),
                 (readout_total,0),
                 (recovery_ns,0),
                 (init_total,0),
                 (mw_gap_ns_1,0),
                 (mw_ns,0),
                 (mw_gap_ns_2 - mw_ns,0),
                 (readout_total,0),
                 (recovery_ns,0)]

         # --------------------------------------------------------
         # Trigger sequence
         # --------------------------------------------------------

            trig_seq = [
                  (init_total,1),
                  (mw_gap_ns_1,0),
                  (mw_ns,0),
                  (mw_gap_ns_2 - mw_ns,0),
                  (readout_total,0),
                  (recovery_ns,0),
                  (init_total,0),
                  (mw_gap_ns_1,0),
                  (mw_ns,0),
                  (mw_gap_ns_2 - mw_ns,0),
                  (readout_total,0),
                  (recovery_ns,0)]

            ps82.allocate_sequence(mw_seq, 0)
            ps82.allocate_sequence(laser_seq, 1)
            ps82.allocate_sequence(trig_seq, 2)

            ps82.begin_pulses(n_runs=-1)

            # --------------------------------------------------------
            # Streaming datasets
            # --------------------------------------------------------

            time_spent = StreamingList()
            sweep_start_time = time.time()
         
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()

            for i in range(iterations):
             
                sig_counts = np.empty(num_points)
                sig_counts[:] = np.nan

                bg_counts = np.empty(num_points)
                bg_counts[:] = np.nan

                time_counts = np.empty(num_points)
                time_counts[:] = np.nan
             
                signal_sweeps.append(np.stack([frequencies/1e9, sig_counts]))
                background_sweeps.append(np.stack([frequencies/1e9, bg_counts]))
                time_spent.append(np.stack([time_counts, sig_counts]))

                for idx in linear_order:
                     freq = frequencies[idx]

                     # -----------------------------
                     # Signal measurement
                     # -----------------------------
                     
                     sg.set_frequency(freq)
                     
                     time.sleep(dwell_time)
                     sig_counts[idx] = odmr.cnts(integration_time)
                     
                     # -----------------------------
                     # Background measurement
                     # -----------------------------

                     sg.set_frequency(100e3)
                     
                     time.sleep(dwell_time)
                     bg_counts[idx] = odmr.cnts(integration_time)
                     
                     # -----------------------------
                     # Time tracking
                     # -----------------------------
                     
                     time_counts[idx] = time.time() - sweep_start_time
                     
                     signal_sweeps[-1] = np.stack([frequencies/1e9, sig_counts])
                     background_sweeps[-1] = np.stack([frequencies/1e9, bg_counts])
                     time_spent[-1] = np.stack([time_counts, sig_counts])
                     
                     signal_sweeps.updated_item(-1)
                     background_sweeps.updated_item(-1)
                     time_spent.updated_item(-1)
                     
                     odmr_data.push({
                         'params': {
                             'start': start_freq,
                             'stop': stop_freq,
                             'num_points': num_points,
                             'iterations': iterations
                             },
                         'title': 'Linear ODMR Sweep',
                         'xlabel': 'Frequency (GHz)',
                         'ylabel': 'Signal',
                         'datasets': {
                             'signal': signal_sweeps,
                             'background': background_sweeps,
                             'time_spent': time_spent
                             }})
                     
                     if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                         ps82.stop()
                         return




class PLEMeasurements_:

    def __init__(self,
                 queue_to_exp=None,
                 queue_from_exp=None):

        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp
        
    def PLE_scan(
        self,
        dataset: str,
        start_wavelength: float,
        stop_wavelength: float,
        num_points: int,
        modulation_frequency: float,
        integration_time: float,
        averages: int,
        settle_time: float = 0.1):


        with MyInstrumentManager() as mgr, DataSource(dataset) as ple_data:

            laser = mgr.laser
            awg = mgr.awg
            mfli = mgr.mfli
            pm = mgr.pm
                         
    # --------------------------------------------------
    # Check requested wavelength range
    # --------------------------------------------------

            min_wl, max_wl = laser.get_limits()

            if start_wavelength < min_wl:
                raise ValueError(
            f"Requested start wavelength {start_wavelength} nm "
            f"is below laser limit {min_wl} nm."
            )

            if stop_wavelength > max_wl:
                raise ValueError(
            f"Requested stop wavelength {stop_wavelength} nm "
            f"is above laser limit {max_wl} nm."
            )


        # --------------------------------------------------
        # Configure AWG
        # --------------------------------------------------

            awg.output(1, False)
            awg.output(2, False)

            awg.set_waveform(1, "SQU")
            awg.set_waveform(2, "SQU")

            awg.set_frequency(1, modulation_frequency)
            awg.set_frequency(2, modulation_frequency)

            awg.set_amplitude(1, 2.0)
            awg.set_amplitude(2, 3.0)

            awg.set_offset(1, 1.0)
            awg.set_offset(2, 1.5)

            awg.output(1, True)
            awg.output(2, True)

            time.sleep(0.5)

        # --------------------------------------------------
        # wavelength axis
        # --------------------------------------------------

            wavelengths = np.linspace(
            start_wavelength,
            stop_wavelength,
            num_points
        )

        # --------------------------------------------------
        # streaming datasets
        # --------------------------------------------------

            ple_sweeps = StreamingList()

            running_average_dataset = StreamingList()

            running_sum = np.zeros(num_points)

        # --------------------------------------------------
        # averaging loop
        # --------------------------------------------------
            # --------------------------------------------------
        # averaging loop
        # --------------------------------------------------
            for avg_num in range(averages):

                sweep_signal = np.full(num_points, np.nan)

                ple_sweeps.append(
                    np.stack([wavelengths, sweep_signal])
                )

                # ----------------------------------------------
                # Determine scan direction (even scans forward, odd scans backward)
                # ----------------------------------------------
                # If avg_num is even (0, 2, 4...): scan forward
                # If avg_num is odd (1, 3, 5...): scan backward
                if avg_num % 2 == 0:
                    scan_indices = list(range(num_points))
                else:
                    scan_indices = list(range(num_points))[::-1] # Reverse the indices!

                # ----------------------------------------------
                # wavelength scan
                # ----------------------------------------------
                for idx in scan_indices:
                    wl = wavelengths[idx]  # Look up corresponding wavelength
                    
                    print("laser =", laser)
                    print("mgr =", mgr)
                    
                    # Move laser
                    laser.move_to_wl(float(wl))

                    # Allow laser to settle
                    time.sleep(settle_time)

                    # ------------------------------------------
                    # MFLI integration
                    # ------------------------------------------
                    start_time = time.time()
                    r_values = []

                    while (time.time() - start_time) < integration_time:
                        signal = mfli.get_signal()
                        if signal["r"] is not None:
                            r_values.append(signal["r"])
                        time.sleep(0.001)

                    if len(r_values) > 0:
                        measured_r = np.mean(r_values)
                    else:
                        measured_r = np.nan

                    # Write data back to its correct index so the running average math remains aligned!
                    sweep_signal[idx] = measured_r
                    running_sum[idx] += measured_r
                    running_average = running_sum / (avg_num + 1)

                    # ------------------------------------------
                    # Update datasets
                    # ------------------------------------------
                    ple_sweeps[-1] = np.stack(
                        [wavelengths, sweep_signal]
                    )
                    ple_sweeps.updated_item(-1)

                    if len(running_average_dataset) == 0:
                        running_average_dataset.append(
                            np.stack([wavelengths, running_average])
                        )
                    else:
                        running_average_dataset[-1] = np.stack(
                            [wavelengths, running_average]
                        )
                        running_average_dataset.updated_item(-1)

                    # ------------------------------------------
                    # Push data to GUI
                    # ------------------------------------------
                    ple_data.push({
                        'params': {
                            'start_wavelength': start_wavelength,
                            'stop_wavelength': stop_wavelength,
                            'num_points': num_points,
                            'modulation_frequency': modulation_frequency,
                            'integration_time': integration_time,
                            'averages': averages
                        },
                        'title': 'PLE Scan',
                        'xlabel': 'Wavelength (nm)',
                        'ylabel': 'Demodulated Amplitude R',
                        'datasets': {
                            'individual_sweeps': ple_sweeps,
                            'running_average': running_average_dataset
                        }
                    })

                    # ------------------------------------------
                    # Stop button
                    # ------------------------------------------
                    if (
                        experiment_widget_process_queue(
                            self.queue_to_exp
                        ) == 'stop'
                    ):
                        awg.output(1, False)
                        awg.output(2, False)
                        return

        # --------------------------------------------------
        # Finish (Outside the loops, but inside 'with')
        # --------------------------------------------------
            awg.output(1, False)
            awg.output(2, False)



class PLEMeasurements2: #power normalization is performed

    def __init__(
        self,
        queue_to_exp=None,
        queue_from_exp=None,
    ):
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp

    def PLE_scan(
        self,
        dataset: str,
        start_wavelength: float,
        stop_wavelength: float,
        num_points: int,
        modulation_frequency: float,
        integration_time: float,
        averages: int,
        settle_time: float = 0.1,
    ):

        with MyInstrumentManager() as mgr, DataSource(dataset) as ple_data:

            laser = mgr.laser
            awg = mgr.awg
            mfli = mgr.mfli
            pm = mgr.pm

            # --------------------------------------------------
            # Check requested wavelength range
            # --------------------------------------------------

            min_wl, max_wl = laser.get_limits()

            if start_wavelength < min_wl:
                raise ValueError(
                    f"Requested start wavelength "
                    f"{start_wavelength} nm is below "
                    f"laser limit {min_wl} nm."
                )

            if stop_wavelength > max_wl:
                raise ValueError(
                    f"Requested stop wavelength "
                    f"{stop_wavelength} nm is above "
                    f"laser limit {max_wl} nm."
                )

            if num_points < 1:
                raise ValueError("num_points must be at least 1.")

            if averages < 1:
                raise ValueError("averages must be at least 1.")

            if integration_time <= 0:
                raise ValueError(
                    "integration_time must be greater than zero."
                )

            # --------------------------------------------------
            # Configure AWG
            # --------------------------------------------------

            awg.output(1, False)
            awg.output(2, False)

            try:
                awg.set_waveform(1, "SQU")
                awg.set_waveform(2, "SQU")

                awg.set_frequency(
                    1,
                    float(modulation_frequency),
                )
                awg.set_frequency(
                    2,
                    float(modulation_frequency),
                )

                awg.set_amplitude(1, 2.0)
                awg.set_amplitude(2, 3.0)

                awg.set_offset(1, 1.0)
                awg.set_offset(2, 1.5)

                awg.output(1, True)
                awg.output(2, True)

                time.sleep(0.5)

                # --------------------------------------------------
                # Wavelength axis
                # --------------------------------------------------

                wavelengths = np.linspace(
                    float(start_wavelength),
                    float(stop_wavelength),
                    int(num_points),
                )

                # --------------------------------------------------
                # Individual-sweep datasets
                # --------------------------------------------------

                raw_sweeps = StreamingList()
                power_sweeps = StreamingList()
                normalized_sweeps = StreamingList()

                # --------------------------------------------------
                # Running-average datasets
                # --------------------------------------------------

                raw_running_average_dataset = StreamingList()
                power_running_average_dataset = StreamingList()
                normalized_running_average_dataset = StreamingList()

                # Sums and valid-sample counts are maintained
                # separately so failed measurements do not corrupt
                # the averages.

                raw_sum = np.zeros(num_points, dtype=float)
                power_sum = np.zeros(num_points, dtype=float)
                normalized_sum = np.zeros(num_points, dtype=float)

                raw_valid_count = np.zeros(num_points, dtype=int)
                power_valid_count = np.zeros(
                    num_points,
                    dtype=int,
                )
                normalized_valid_count = np.zeros(
                    num_points,
                    dtype=int,
                )

                # Store the PM wavelength last sent to reduce
                # unnecessary USB commands.
                last_pm_wavelength = None

                # --------------------------------------------------
                # Averaging loop
                # --------------------------------------------------

                for avg_num in range(averages):

                    raw_sweep = np.full(
                        num_points,
                        np.nan,
                        dtype=float,
                    )
                    power_sweep = np.full(
                        num_points,
                        np.nan,
                        dtype=float,
                    )
                    normalized_sweep = np.full(
                        num_points,
                        np.nan,
                        dtype=float,
                    )

                    raw_sweeps.append(
                        np.stack(
                            [wavelengths, raw_sweep]
                        )
                    )
                    power_sweeps.append(
                        np.stack(
                            [wavelengths, power_sweep]
                        )
                    )
                    normalized_sweeps.append(
                        np.stack(
                            [wavelengths, normalized_sweep]
                        )
                    )

                    # Even-numbered sweeps scan forward.
                    # Odd-numbered sweeps scan backward.
                    if avg_num % 2 == 0:
                        scan_indices = range(num_points)
                    else:
                        scan_indices = range(
                            num_points - 1,
                            -1,
                            -1,
                        )

                    # --------------------------------------------------
                    # Wavelength scan
                    # --------------------------------------------------

                    for idx in scan_indices:

                        wl = float(wavelengths[idx])

                        # Move laser.
                        laser.move_to_wl(wl)

                        # Let the laser settle before setting the
                        # PM100D correction wavelength and measuring.
                        time.sleep(settle_time)

                        # PM100D correction wavelength is rounded
                        # to the nearest integer by the driver.
                        pm_wavelength = float(
                            np.floor(wl + 0.5)
                        )

                        if pm_wavelength != last_pm_wavelength:
                            pm.set_wavelength(
                                pm_wavelength,
                                round_to_integer=False,
                            )
                            last_pm_wavelength = pm_wavelength

                        # --------------------------------------------------
                        # Simultaneous MFLI and power integration
                        # --------------------------------------------------

                        r_values = []
                        power_values = []

                        start_time = time.monotonic()

                        while (
                            time.monotonic() - start_time
                            < integration_time
                        ):
                            # Read the lock-in.
                            try:
                                signal = mfli.get_signal()
                                r_value = signal.get("r")

                                if r_value is not None:
                                    r_value = float(r_value)

                                    if np.isfinite(r_value):
                                        r_values.append(r_value)

                            except Exception as exc:
                                _logger.warning(
                                    "MFLI read failed at "
                                    "%.6f nm: %s",
                                    wl,
                                    exc,
                                )

                            # Read the power meter within the
                            # same integration window.
                            try:
                                power_value = float(
                                    pm.get_power()
                                )

                                if (
                                    np.isfinite(power_value)
                                    and power_value >= 0
                                ):
                                    power_values.append(
                                        power_value
                                    )

                            except Exception as exc:
                                _logger.warning(
                                    "PM100D read failed at "
                                    "%.6f nm: %s",
                                    wl,
                                    exc,
                                )

                            # The PM100D read itself takes some
                            # time, so a 5 ms delay is sufficient.
                            time.sleep(0.005)

                        # --------------------------------------------------
                        # Calculate point values
                        # --------------------------------------------------

                        if r_values:
                            measured_r = float(
                                np.mean(r_values)
                            )
                        else:
                            measured_r = np.nan

                        if power_values:
                            measured_power = float(
                                np.mean(power_values)
                            )
                        else:
                            measured_power = np.nan

                        # Prevent division by zero or invalid power.
                        if (
                            np.isfinite(measured_r)
                            and np.isfinite(measured_power)
                            and measured_power > 0
                        ):
                            normalized_r = (
                                measured_r / measured_power
                            )
                        else:
                            normalized_r = np.nan

                        # Store point in the correct wavelength index.
                        raw_sweep[idx] = measured_r
                        power_sweep[idx] = measured_power
                        normalized_sweep[idx] = normalized_r

                        # --------------------------------------------------
                        # Update running sums and counts
                        # --------------------------------------------------

                        if np.isfinite(measured_r):
                            raw_sum[idx] += measured_r
                            raw_valid_count[idx] += 1

                        if np.isfinite(measured_power):
                            power_sum[idx] += measured_power
                            power_valid_count[idx] += 1

                        if np.isfinite(normalized_r):
                            normalized_sum[idx] += normalized_r
                            normalized_valid_count[idx] += 1

                        # Create arrays filled with NaN, then place
                        # averages only where valid measurements exist.

                        raw_running_average = np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )
                        power_running_average = np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )
                        normalized_running_average = np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )

                        raw_valid = raw_valid_count > 0
                        power_valid = power_valid_count > 0
                        normalized_valid = (
                            normalized_valid_count > 0
                        )

                        raw_running_average[raw_valid] = (
                            raw_sum[raw_valid]
                            / raw_valid_count[raw_valid]
                        )

                        power_running_average[power_valid] = (
                            power_sum[power_valid]
                            / power_valid_count[power_valid]
                        )

                        normalized_running_average[
                            normalized_valid
                        ] = (
                            normalized_sum[normalized_valid]
                            / normalized_valid_count[
                                normalized_valid
                            ]
                        )

                        # --------------------------------------------------
                        # Update StreamingLists
                        # --------------------------------------------------

                        raw_sweeps[-1] = np.stack(
                            [wavelengths, raw_sweep]
                        )
                        raw_sweeps.updated_item(-1)

                        power_sweeps[-1] = np.stack(
                            [wavelengths, power_sweep]
                        )
                        power_sweeps.updated_item(-1)

                        normalized_sweeps[-1] = np.stack(
                            [wavelengths, normalized_sweep]
                        )
                        normalized_sweeps.updated_item(-1)

                        # Raw running average.
                        raw_average_stack = np.stack(
                            [
                                wavelengths,
                                raw_running_average,
                            ]
                        )

                        if (
                            len(
                                raw_running_average_dataset
                            )
                            == 0
                        ):
                            raw_running_average_dataset.append(
                                raw_average_stack
                            )
                        else:
                            raw_running_average_dataset[-1] = (
                                raw_average_stack
                            )
                            raw_running_average_dataset.updated_item(
                                -1
                            )

                        # Power running average.
                        power_average_stack = np.stack(
                            [
                                wavelengths,
                                power_running_average,
                            ]
                        )

                        if (
                            len(
                                power_running_average_dataset
                            )
                            == 0
                        ):
                            power_running_average_dataset.append(
                                power_average_stack
                            )
                        else:
                            power_running_average_dataset[-1] = (
                                power_average_stack
                            )
                            power_running_average_dataset.updated_item(
                                -1
                            )

                        # Normalized running average.
                        normalized_average_stack = np.stack(
                            [
                                wavelengths,
                                normalized_running_average,
                            ]
                        )

                        if (
                            len(
                                normalized_running_average_dataset
                            )
                            == 0
                        ):
                            normalized_running_average_dataset.append(
                                normalized_average_stack
                            )
                        else:
                            normalized_running_average_dataset[
                                -1
                            ] = normalized_average_stack
                            normalized_running_average_dataset.updated_item(
                                -1
                            )

                        # --------------------------------------------------
                        # Push data to GUI
                        # --------------------------------------------------

                        ple_data.push(
                            {
                                "params": {
                                    "start_wavelength":
                                        start_wavelength,
                                    "stop_wavelength":
                                        stop_wavelength,
                                    "num_points":
                                        num_points,
                                    "modulation_frequency":
                                        modulation_frequency,
                                    "integration_time":
                                        integration_time,
                                    "averages":
                                        averages,
                                    "settle_time":
                                        settle_time,
                                    "current_average":
                                        avg_num + 1,
                                    "current_wavelength":
                                        wl,
                                    "pm_wavelength":
                                        pm_wavelength,
                                },

                                "title": "PLE Scan",

                                "xlabel":
                                    "Wavelength (nm)",

                                # This general ylabel is retained
                                # for compatibility. Individual
                                # plots should set their own labels.
                                "ylabel":
                                    "PLE Signal / Power",

                                "datasets": {
                                    # Existing names retained for
                                    # compatibility with your
                                    # original PLE plot.
                                    "individual_sweeps":
                                        raw_sweeps,

                                    "running_average":
                                        raw_running_average_dataset,

                                    # New power data.
                                    "power_sweeps":
                                        power_sweeps,

                                    "power_running_average":
                                        power_running_average_dataset,

                                    # New normalized PLE data.
                                    "normalized_sweeps":
                                        normalized_sweeps,

                                    "normalized_running_average":
                                        normalized_running_average_dataset,
                                },
                            }
                        )

                        # --------------------------------------------------
                        # Stop button
                        # --------------------------------------------------

                        if (
                            experiment_widget_process_queue(
                                self.queue_to_exp
                            )
                            == "stop"
                        ):
                            return

            finally:
                # This executes after a normal finish, a stop request,
                # or an exception.
                try:
                    awg.output(1, False)
                except Exception:
                    _logger.exception(
                        "Failed to disable AWG channel 1."
                    )

                try:
                    awg.output(2, False)
                except Exception:
                    _logger.exception(
                        "Failed to disable AWG channel 2."
                    )                

class PLEMeasurements:
    """
    PLE measurement with:

    - Mechanical chopper modulation
    - MFLI external-reference lock-in detection
    - PM100D power measurement
    - Raw PLE
    - Power-normalized PLE
    - Power vs wavelength

    The MFLI is assumed to already be configured to lock to
    the external chopper reference.
    """

    def __init__(
        self,
        queue_to_exp=None,
        queue_from_exp=None,
    ):
        self.queue_to_exp = queue_to_exp
        self.queue_from_exp = queue_from_exp

    def PLE_scan(
        self,
        dataset: str,
        start_wavelength: float,
        stop_wavelength: float,
        num_points: int,
        integration_time: float,
        averages: int,
        settle_time: float = 0.1,
    ):

        with MyInstrumentManager() as mgr, DataSource(dataset) as ple_data:

            laser = mgr.laser
            mfli = mgr.mfli
            pm = mgr.pm

            # ==================================================
            # Validate parameters
            # ==================================================

            min_wl, max_wl = laser.get_limits()

            if start_wavelength < min_wl:
                raise ValueError(
                    f"Requested start wavelength "
                    f"{start_wavelength} nm is below "
                    f"laser limit {min_wl} nm."
                )

            if stop_wavelength > max_wl:
                raise ValueError(
                    f"Requested stop wavelength "
                    f"{stop_wavelength} nm is above "
                    f"laser limit {max_wl} nm."
                )

            if num_points < 2:
                raise ValueError(
                    "num_points must be at least 2."
                )

            if averages < 1:
                raise ValueError(
                    "averages must be at least 1."
                )

            if integration_time <= 0:
                raise ValueError(
                    "integration_time must be greater than zero."
                )

            if settle_time < 0:
                raise ValueError(
                    "settle_time cannot be negative."
                )

            # ==================================================
            # Wavelength axis
            # ==================================================

            wavelengths = np.linspace(
                float(start_wavelength),
                float(stop_wavelength),
                int(num_points),
            )

            # ==================================================
            # Individual sweep datasets
            # ==================================================

            raw_sweeps = StreamingList()
            power_sweeps = StreamingList()
            normalized_sweeps = StreamingList()

            # ==================================================
            # Running-average datasets
            # ==================================================

            raw_running_average_dataset = StreamingList()
            power_running_average_dataset = StreamingList()
            normalized_running_average_dataset = StreamingList()

            # ==================================================
            # Running sums
            # ==================================================

            raw_sum = np.zeros(
                num_points,
                dtype=float,
            )

            power_sum = np.zeros(
                num_points,
                dtype=float,
            )

            normalized_sum = np.zeros(
                num_points,
                dtype=float,
            )

            # ==================================================
            # Number of valid measurements at each wavelength
            # ==================================================

            raw_valid_count = np.zeros(
                num_points,
                dtype=int,
            )

            power_valid_count = np.zeros(
                num_points,
                dtype=int,
            )

            normalized_valid_count = np.zeros(
                num_points,
                dtype=int,
            )

            # ==================================================
            # Power-meter wavelength tracking
            # ==================================================
            #
            # Avoid repeatedly sending the same wavelength
            # correction value to the PM100D.

            last_pm_wavelength = None

            # ==================================================
            # DataServer heartbeat interval
            # ==================================================
            #
            # Important for long integrations.
            #
            # With a 100 s integration the DataSource previously
            # remained idle for ~100 s. Push status every 5 s
            # instead.

            heartbeat_interval = 5.0

            # ==================================================
            # Helper function for DataSource pushes
            # ==================================================

            def push_data(
                avg_num,
                wl,
                pm_wavelength,
                status,
                integration_elapsed=0.0,
                integration_remaining=0.0,
            ):

                ple_data.push(
                    {
                        "params": {
                            "start_wavelength":
                                start_wavelength,

                            "stop_wavelength":
                                stop_wavelength,

                            "num_points":
                                num_points,

                            "integration_time":
                                integration_time,

                            "averages":
                                averages,

                            "settle_time":
                                settle_time,

                            "current_average":
                                avg_num + 1,

                            "current_wavelength":
                                wl,

                            "pm_wavelength":
                                pm_wavelength,

                            "reference_source":
                                "external chopper",

                            "status":
                                status,

                            "integration_elapsed":
                                integration_elapsed,

                            "integration_remaining":
                                integration_remaining,
                        },

                        "title":
                            "PLE Scan",

                        "xlabel":
                            "Wavelength (nm)",

                        "ylabel":
                            "PLE Measurement",

                        "datasets": {

                            # Raw PLE
                            "individual_sweeps":
                                raw_sweeps,

                            "running_average":
                                raw_running_average_dataset,

                            # Laser power
                            "power_sweeps":
                                power_sweeps,

                            "power_running_average":
                                power_running_average_dataset,

                            # Power-normalized PLE
                            "normalized_sweeps":
                                normalized_sweeps,

                            "normalized_running_average":
                                normalized_running_average_dataset,
                        },
                    }
                )

            # ==================================================
            # Averaging loop
            # ==================================================

            for avg_num in range(averages):

                # --------------------------------------------------
                # Create new sweep arrays
                # --------------------------------------------------

                raw_sweep = np.full(
                    num_points,
                    np.nan,
                    dtype=float,
                )

                power_sweep = np.full(
                    num_points,
                    np.nan,
                    dtype=float,
                )

                normalized_sweep = np.full(
                    num_points,
                    np.nan,
                    dtype=float,
                )

                # --------------------------------------------------
                # Add current sweep to StreamingLists
                # --------------------------------------------------

                raw_sweeps.append(
                    np.stack(
                        [
                            wavelengths,
                            raw_sweep,
                        ]
                    )
                )

                power_sweeps.append(
                    np.stack(
                        [
                            wavelengths,
                            power_sweep,
                        ]
                    )
                )

                normalized_sweeps.append(
                    np.stack(
                        [
                            wavelengths,
                            normalized_sweep,
                        ]
                    )
                )

                # ==================================================
                # Alternate scan direction
                # ==================================================
                #
                # Even averages:
                #     low wavelength -> high wavelength
                #
                # Odd averages:
                #     high wavelength -> low wavelength

                if avg_num % 2 == 0:

                    scan_indices = range(
                        num_points
                    )

                else:

                    scan_indices = range(
                        num_points - 1,
                        -1,
                        -1,
                    )

                # ==================================================
                # Wavelength scan
                # ==================================================

                for idx in scan_indices:

                    wl = float(
                        wavelengths[idx]
                    )

                    # --------------------------------------------------
                    # Move laser
                    # --------------------------------------------------

                    laser.move_to_wl(wl)

                    # --------------------------------------------------
                    # Allow laser / lock-in to settle
                    # --------------------------------------------------

                    time.sleep(
                        settle_time
                    )

                    # --------------------------------------------------
                    # Set PM100D wavelength correction
                    # --------------------------------------------------
                    #
                    # PM100D correction wavelength is rounded
                    # to nearest integer wavelength.

                    pm_wavelength = float(
                        np.floor(
                            wl + 0.5
                        )
                    )

                    if (
                        pm_wavelength
                        != last_pm_wavelength
                    ):

                        pm.set_wavelength(
                            pm_wavelength,
                            round_to_integer=False,
                        )

                        last_pm_wavelength = (
                            pm_wavelength
                        )

                    # ==================================================
                    # Integration
                    # ==================================================
                    #
                    # MFLI and PM100D are sampled within the same
                    # integration window.

                    r_values = []
                    power_values = []

                    start_time = (
                        time.monotonic()
                    )

                    last_heartbeat = (
                        start_time
                    )

                    # --------------------------------------------------
                    # Initial push before long integration
                    # --------------------------------------------------

                    push_data(
                        avg_num=avg_num,
                        wl=wl,
                        pm_wavelength=pm_wavelength,
                        status="integrating",
                        integration_elapsed=0.0,
                        integration_remaining=
                            integration_time,
                    )

                    # ==================================================
                    # Long integration loop
                    # ==================================================

                    while True:

                        now = (
                            time.monotonic()
                        )

                        elapsed = (
                            now
                            - start_time
                        )

                        if (
                            elapsed
                            >= integration_time
                        ):
                            break

                        # ----------------------------------------------
                        # Read MFLI
                        # ----------------------------------------------

                        try:

                            signal = (
                                mfli.get_signal()
                            )

                            r_value = (
                                signal.get("r")
                            )

                            if (
                                r_value
                                is not None
                            ):

                                r_value = float(
                                    r_value
                                )

                                if np.isfinite(
                                    r_value
                                ):
                                    r_values.append(
                                        r_value
                                    )

                        except Exception as exc:

                            _logger.warning(
                                "MFLI read failed at "
                                "%.6f nm: %s",
                                wl,
                                exc,
                            )

                        # ----------------------------------------------
                        # Read PM100D
                        # ----------------------------------------------

                        try:

                            power_value = float(
                                pm.get_power()
                            )

                            if (
                                np.isfinite(
                                    power_value
                                )
                                and power_value >= 0
                            ):

                                power_values.append(
                                    power_value
                                )

                        except Exception as exc:

                            _logger.warning(
                                "PM100D read failed at "
                                "%.6f nm: %s",
                                wl,
                                exc,
                            )

                        # ----------------------------------------------
                        # Check Stop button DURING integration
                        # ----------------------------------------------
                        #
                        # This is important when integration_time
                        # is 100 seconds or longer.

                        if (
                            experiment_widget_process_queue(
                                self.queue_to_exp
                            )
                            == "stop"
                        ):

                            push_data(
                                avg_num=
                                    avg_num,

                                wl=
                                    wl,

                                pm_wavelength=
                                    pm_wavelength,

                                status=
                                    "stopped",

                                integration_elapsed=
                                    elapsed,

                                integration_remaining=
                                    max(
                                        0.0,
                                        integration_time
                                        - elapsed,
                                    ),
                            )

                            return

                        # ----------------------------------------------
                        # DataServer heartbeat
                        # ----------------------------------------------

                        now = (
                            time.monotonic()
                        )

                        if (
                            now
                            - last_heartbeat
                            >= heartbeat_interval
                        ):

                            elapsed = (
                                now
                                - start_time
                            )

                            remaining = max(
                                0.0,
                                integration_time
                                - elapsed,
                            )

                            push_data(
                                avg_num=
                                    avg_num,

                                wl=
                                    wl,

                                pm_wavelength=
                                    pm_wavelength,

                                status=
                                    "integrating",

                                integration_elapsed=
                                    elapsed,

                                integration_remaining=
                                    remaining,
                            )

                            last_heartbeat = (
                                now
                            )

                        # ----------------------------------------------
                        # Small delay between reads
                        # ----------------------------------------------

                        time.sleep(
                            0.005
                        )

                    # ==================================================
                    # Calculate completed wavelength point
                    # ==================================================

                    if r_values:

                        measured_r = float(
                            np.mean(
                                r_values
                            )
                        )

                    else:

                        measured_r = np.nan

                    if power_values:

                        measured_power = float(
                            np.mean(
                                power_values
                            )
                        )

                    else:

                        measured_power = np.nan

                    # --------------------------------------------------
                    # Normalize PLE by measured laser power
                    # --------------------------------------------------

                    if (
                        np.isfinite(
                            measured_r
                        )
                        and
                        np.isfinite(
                            measured_power
                        )
                        and
                        measured_power > 0
                    ):

                        normalized_r = (
                            measured_r
                            / measured_power
                        )

                    else:

                        normalized_r = (
                            np.nan
                        )

                    # ==================================================
                    # Store completed point
                    # ==================================================

                    raw_sweep[idx] = (
                        measured_r
                    )

                    power_sweep[idx] = (
                        measured_power
                    )

                    normalized_sweep[idx] = (
                        normalized_r
                    )

                    # ==================================================
                    # Update running sums
                    # ==================================================

                    if np.isfinite(
                        measured_r
                    ):

                        raw_sum[idx] += (
                            measured_r
                        )

                        raw_valid_count[
                            idx
                        ] += 1

                    if np.isfinite(
                        measured_power
                    ):

                        power_sum[idx] += (
                            measured_power
                        )

                        power_valid_count[
                            idx
                        ] += 1

                    if np.isfinite(
                        normalized_r
                    ):

                        normalized_sum[idx] += (
                            normalized_r
                        )

                        normalized_valid_count[
                            idx
                        ] += 1

                    # ==================================================
                    # Calculate running averages
                    # ==================================================

                    raw_running_average = (
                        np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )
                    )

                    power_running_average = (
                        np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )
                    )

                    normalized_running_average = (
                        np.full(
                            num_points,
                            np.nan,
                            dtype=float,
                        )
                    )

                    raw_valid = (
                        raw_valid_count > 0
                    )

                    power_valid = (
                        power_valid_count > 0
                    )

                    normalized_valid = (
                        normalized_valid_count
                        > 0
                    )

                    raw_running_average[
                        raw_valid
                    ] = (
                        raw_sum[
                            raw_valid
                        ]
                        /
                        raw_valid_count[
                            raw_valid
                        ]
                    )

                    power_running_average[
                        power_valid
                    ] = (
                        power_sum[
                            power_valid
                        ]
                        /
                        power_valid_count[
                            power_valid
                        ]
                    )

                    normalized_running_average[
                        normalized_valid
                    ] = (
                        normalized_sum[
                            normalized_valid
                        ]
                        /
                        normalized_valid_count[
                            normalized_valid
                        ]
                    )

                    # ==================================================
                    # Update current sweep StreamingLists
                    # ==================================================

                    raw_sweeps[-1] = (
                        np.stack(
                            [
                                wavelengths,
                                raw_sweep,
                            ]
                        )
                    )

                    raw_sweeps.updated_item(
                        -1
                    )

                    power_sweeps[-1] = (
                        np.stack(
                            [
                                wavelengths,
                                power_sweep,
                            ]
                        )
                    )

                    power_sweeps.updated_item(
                        -1
                    )

                    normalized_sweeps[-1] = (
                        np.stack(
                            [
                                wavelengths,
                                normalized_sweep,
                            ]
                        )
                    )

                    normalized_sweeps.updated_item(
                        -1
                    )

                    # ==================================================
                    # Raw PLE running average
                    # ==================================================

                    raw_average_stack = (
                        np.stack(
                            [
                                wavelengths,
                                raw_running_average,
                            ]
                        )
                    )

                    if (
                        len(
                            raw_running_average_dataset
                        )
                        == 0
                    ):

                        raw_running_average_dataset.append(
                            raw_average_stack
                        )

                    else:

                        raw_running_average_dataset[
                            -1
                        ] = raw_average_stack

                        raw_running_average_dataset.updated_item(
                            -1
                        )

                    # ==================================================
                    # Power running average
                    # ==================================================

                    power_average_stack = (
                        np.stack(
                            [
                                wavelengths,
                                power_running_average,
                            ]
                        )
                    )

                    if (
                        len(
                            power_running_average_dataset
                        )
                        == 0
                    ):

                        power_running_average_dataset.append(
                            power_average_stack
                        )

                    else:

                        power_running_average_dataset[
                            -1
                        ] = power_average_stack

                        power_running_average_dataset.updated_item(
                            -1
                        )

                    # ==================================================
                    # Normalized PLE running average
                    # ==================================================

                    normalized_average_stack = (
                        np.stack(
                            [
                                wavelengths,
                                normalized_running_average,
                            ]
                        )
                    )

                    if (
                        len(
                            normalized_running_average_dataset
                        )
                        == 0
                    ):

                        normalized_running_average_dataset.append(
                            normalized_average_stack
                        )

                    else:

                        normalized_running_average_dataset[
                            -1
                        ] = normalized_average_stack

                        normalized_running_average_dataset.updated_item(
                            -1
                        )

                    # ==================================================
                    # Push completed wavelength point
                    # ==================================================

                    push_data(
                        avg_num=avg_num,
                        wl=wl,
                        pm_wavelength=pm_wavelength,
                        status="point complete",
                        integration_elapsed=
                            integration_time,
                        integration_remaining=
                            0.0,
                    )

                    # ==================================================
                    # Stop check between wavelength points
                    # ==================================================

                    if (
                        experiment_widget_process_queue(
                            self.queue_to_exp
                        )
                        == "stop"
                    ):

                        return



if __name__ == '__main__':
    exp = SpinMeasurements()
    exp.odmr_sweep_random('odmr', 1e9, 4e9, 101, 10)
