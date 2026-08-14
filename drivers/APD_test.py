# -*- coding: utf-8 -*-
"""
Created on Fri Jun  5 14:38:34 2026

@author: ODMR_user
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
# Direct Detection Methods - Here, the APD must connected to the channel 1 
#                            of the TimeTagger. Signals are extracted directly
#                            from the PL counts, with backgrounds corresponding 
#                            to same measurement sequence without microwaves
#
# PulseSteamer8/2 Experiments 
#                    - Laser pulses are achieved by square wave modulation 
#                      through the AWG, and detection is achieved using 
#                      manually set modulation through the signal generator.
#------------------------------------------------------------------------------

    def odmr_sweep_linear_timetagger_ps82(self,
                   dataset: str,
                   start_freq: float,
                   stop_freq: float,
                   num_points: int,
                   iterations: int,
                   rf_amplitude: int,
                   
                   # Pulse Settings
                   init_ns: int,
                   readout_ns: int,
                   pulse_length_ns: int,
                   mw_gap_ns_1: int = 50,
                   mw_gap_ns_2: int = 50,
                   recovery_ns: float = 1e6,
                   detector_delay_ns: int = 100,    # for the PS82, this is 100 ns
                   
                   # --- TimeTagger ---
                   start_channel: int = 5, #Trigger
                   click_channel: int = 7, #APD
                   binwidth_ns: int = 1000,
                   n_bins: int = 1000,
                   integration_time: float = 1):

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
         
         sg = mgr.sg
         tt = mgr.tt20
         ps82 = mgr.ps82
         
         sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
         sg.set_output(1)
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
         laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(pulse_length_ns,0),(mw_gap_ns_2,0),(100,0),(readout_ns,1),(recovery_ns,0)]
         mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(pulse_length_ns,1),(mw_gap_ns_2,0),(100,0),(readout_ns,0),(recovery_ns,0)]
         trig_seq = [(init_ns,0),(mw_gap_ns_1,0),(pulse_length_ns,0),(mw_gap_ns_2,0),(100,1),(readout_ns,0),(recovery_ns,0)]
      
         ps82.allocate_sequence(mw_seq, 0)
         ps82.allocate_sequence(laser_seq, 1)
         ps82.allocate_sequence(trig_seq, 2)
   
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
                    
                 # --------------------------------
                 # Signal histogram → integrate
                 # --------------------------------
                 t, counts = tt.run_histogram(
                     click_channel=click_channel,
                     start_channel=start_channel,
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=detector_delay_ns * 1e3)
                 
                 sig_counts[idx] = counts.sum()
                    
                 # Background
                 sg.set_frequency(100e3)
                 
                 t, bg = tt.run_histogram(
                     click_channel=click_channel,
                     start_channel=start_channel,
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=detector_delay_ns * 1e3)
                 
                 bg_counts[idx] = bg.sum()
                    
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
                     ps82.stop()
                     return
