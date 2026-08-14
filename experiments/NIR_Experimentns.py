"""
This is example script demonstrates most of the basic functionality of nspyre.
"""
##This is for NIR ODMR using MFLI lock in and laser modulation using pulse streamer

import time
import logging
from pathlib import Path

import numpy as np
from nspyre import DataSource
from nspyre import experiment_widget_process_queue
from nspyre import StreamingList
from nspyre import nspyre_init_logger
# from nspyre import DataSink

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
# PulseSteamer8/2 Experiments  - Laser and microwaves are modulated via the PS82. 
#                                The repetition frequency corresponds to the lock-in 
#                                frequency.
#------------------------------------------------------------------------------

    def cw_odmr_sweep_linear_ps82(self,
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
            mw_seq = ps82.square_wave(period_ns)
            
            ps82.allocate_sequence(mw_seq, 0)
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


    