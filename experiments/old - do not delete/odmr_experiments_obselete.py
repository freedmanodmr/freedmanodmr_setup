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
# Lock-in Detection Method - Laser and microwaves are modulated via the AWG/PS82. 
#                            The repeating frequency corresponds to the lock-in 
#                            frequency.
#------------------------------------------------------------------------------

    def odmr_sweep_random(self,
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


    def odmr_sweep_linear(self,
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
                    

    def rabi_oscillations_lockin(
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
                       return


    def odmr_sweep_linear_PMT_lockin(self,
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
         
         trig_seq = [(init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns + 
                      init_ns + mw_gap_ns_1 + pulse_length_ns + mw_gap_ns_2 + readout_ns + recovery_ns,0)]
      
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
                    
                 # Signal
                 time.sleep(dwell_time + integration_time)
                 sig_counts[idx] = odmr.cnts(integration_time)
                    
                 # Background
                 sg.set_frequency(100e3)
                 time.sleep(dwell_time + integration_time)
                 bg_counts[idx] = odmr.cnts(integration_time)
                    
                 # --- collect elapsed time since sweep start ---
                 time_counts[idx] = time.time() - sweep_start_time
                    
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
                       "title": "APD ODMR",
                       "xlabel": " Frequency / GHz",
                       "ylabel": "Integrated Counts",
                       "datasets": {
                         "signal": signal_sweeps,
                         "background": background_sweeps,
                         "time": time_spent}})
                 
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     ps82.stop()
                     return


    def hahn_echo_lockin(
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


    def microwave_delay_opt_lockin(
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


    def initialisation_opt_lockin(
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


    def readout_opt_lockin(
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


    def readout_delay_opt_lockin(
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


    def ramsey_lockin(
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


#------------------------------------------------------------------------------
# Direct Detection Methods - Here, the APD must connected to the channel 1 
#                            of the TimeTagger. Signals are extracted directly
# NOTE: These use            from the PL counts, with backgrounds corresponding 
# the AWG, not the best      to same measurement sequence without microwaves
#------------------------------------------------------------------------------
                                 
    def odmr_sweep_linear_timetagger(self,
                   dataset: str,
                   start_freq: float,
                   stop_freq: float,
                   num_points: int,
                   iterations: int,
                   rf_amplitude: int,
                   
                   # Pulse Settings
                   # --- AWG timing defaults ---
                   init_ns: int,
                   readout_ns: int,
                   pulse_length_ns: int,
                   ch1_delay_ns: int = 50,   # -3879 <-- this is the measured time difference between channel 1 and channel 2 using the test script, but it aint true here!
                   ch2_delay_ns: int = 4279,      # <-- this was 22005 for 10000, 2279 for 1000, now 1279 for 500. Looks like 2 microseconds per 500 us sequence
                   total_time_us: float = 2000,   # This needs to be understood, should correspond to length of nparray of zeros...
                   mw_gap_ns_1: int = 5,
                   mw_gap_ns_2: int = 5,
                   sample_rate: float = 75e6,
                   detector_delay_ns: int = 1250,    # Laser channel delay, to be 
                                                     # determined by readout optimisation - apparently 1250. Can be checked on the oscilloscope
                   # --- TimeTagger ---
                   start_channel: int = 2,
                   click_channel: int = 1,
                   binwidth_ns: int = 1000,
                   n_bins: int = 1000,
                   integration_time: float = 1,   # time for accumulations of pulse sequences
                   ):

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
         
         odmr = mgr.odmr_driver
         sg = mgr.sg
         awg = mgr.awg
         tt = mgr.tt20
         
         sg.set_amplitude_rf(rf_amplitude)  # Maximum amp is 7.4 dBm from the sig gen.
         sg.set_output(1)
         
         # --------------------------------
         # AWG burst configuration (ONCE)
         # --------------------------------
         awg.instrument.write("C1:BSWV PHSE,-0.8")
         awg.instrument.write("C1:BTWV PRD,0.004")    # Increase to T_opt for phosphorescent material
         awg.output(1, True)
         awg.set_arb_mode(1)
         awg.set_burst_mode(1, True)
         awg.set_amplitude(1,8)
         
         awg.output(2, True)
         awg.set_arb_mode(2)
         awg.set_burst_mode(2, True)
         awg.set_amplitude(2,8)
         awg.instrument.write("C2:BSWV PHSE,-0.01") 
         awg.instrument.write("C2:BTWV PRD,0.004")    # Increase to T_opt for phosphorescent material
         
         time.sleep(0.05)
                     
         # --------------------------------
         # Sweep definition
         # --------------------------------
         freqs = np.linspace(start_freq, stop_freq, num_points)
         
         # --- LINEAR ORDER replaces random permutation ---
         linear_order = range(num_points)
         
         # --------------------------------
         # AWG time base
         # --------------------------------
         total_time_s = total_time_us * 1e-6
         num_pts = int(round(sample_rate * total_time_s))
         
         # --------------------------------
         # Streaming containers
         # --------------------------------
         signal_sweeps = StreamingList()
         background_sweeps = StreamingList()
         time_sweeps = StreamingList()
         sweep_start_time = time.time()
         
         # --------------------------------
         # Iterations
         # --------------------------------
         for it in range(iterations):
             sig_counts = np.full(num_points, np.nan)
             bg_counts = np.full(num_points, np.nan)
             t_elapsed = np.full(num_points, np.nan)
             
             signal_sweeps.append(np.stack([freqs, sig_counts]))
             background_sweeps.append(np.stack([freqs, bg_counts]))
             time_sweeps.append(np.stack([freqs, t_elapsed]))
             
             # --------------------------------
             # MW freq sweep
             # --------------------------------
             # --- MAIN SWEEP LOOP: NOW LINEAR ---
             for idx in linear_order:      
                 freq = freqs[idx]
                
                 sg.set_frequency(freq)

                 # --------------------------------
                 # Pulse timing
                 # --------------------------------
                 init_t = init_ns * 1e-9
                 read_t = readout_ns * 1e-9
                 gap_t1 = mw_gap_ns_1 * 1e-9
                 gap_t2 = mw_gap_ns_2 * 1e-9
                 pulse_length_ns_t = pulse_length_ns * 1e-9
                 
                 # --------------------------------
                 # Channel 2 delay
                 # --------------------------------
                 ch1_delay_s = ch1_delay_ns * 1e-9
                 ch2_delay_s = ch2_delay_ns * 1e-9
                     
                 mw_start = ch1_delay_s + init_t + gap_t1
                 read_start = ch2_delay_s + mw_start + pulse_length_ns_t + gap_t1 + gap_t2
                     
                 # Histogram gate delay (readout only)
                 detector_delay_s = detector_delay_ns * 1e-9
                 gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))

                 # ====================================================
                 # SIGNAL SEQUENCE (with MW)
                 # ====================================================
                 w_mw = np.zeros(num_pts)
                 w_laser = np.zeros(num_pts)
                 
                 odmr.apply_pulse(w_laser, ch2_delay_s, init_t, 8.0, sample_rate)
                 odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)    # Turn off for a phosphorescent material
                 odmr.apply_pulse(w_mw, mw_start, pulse_length_ns_t, 8.0, sample_rate)
                                   
                 odmr.load_arbitrary_waveform_burst(
                     channel=1,
                     data=w_mw,
                     name="mw",
                     sample_rate=sample_rate,
                     )
                 
                 odmr.load_arbitrary_waveform_burst(
                     channel=2,
                     data=w_laser,
                     name="laser",
                     sample_rate=sample_rate,
                     )
                  
                 # --------------------------------
                 # Signal histogram → integrate
                 # --------------------------------
                 t, counts = tt.run_histogram(
                     click_channel=click_channel,
                     start_channel=start_channel,
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=gate_delay_ps,
                     )
                 
                 sig_counts[idx] = counts.sum()
             
                 # ====================================================
                 # BACKGROUND SEQUENCE (no MW)
                 # ====================================================
                 # On reflection, this is a stupid way to turn off the microwaves. 
                 # I should either change the frequency or turn off the microwaves at the source.
                 
                 #sg.set_frequency(100e3) # For some reason, this created a problem with the bkg
                 
                 w_mw[:] = 0.0
                 
                 odmr.load_arbitrary_waveform_burst(
                     channel=1,
                     data=w_mw,
                     name="mw_bg",
                     sample_rate=sample_rate,
                     )
                 
                 odmr.load_arbitrary_waveform_burst(
                     channel=2,
                     data=w_laser,
                     name="laser",
                     sample_rate=sample_rate,
                     )
                 
                 t, bg = tt.run_histogram(
                     click_channel=click_channel,
                     start_channel=start_channel,
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=gate_delay_ps,
                     )
                 
                 bg_counts[idx] = bg.sum()
                 
                 # --------------------------------
                 # Streaming updates
                 # --------------------------------
                 t_elapsed[idx] = time.time() - sweep_start_time
                 
                 signal_sweeps[-1] = np.stack([freqs/1e9, sig_counts])
                 background_sweeps[-1] = np.stack([freqs/1e9, bg_counts])
                 time_sweeps[-1] = np.stack([freqs/1e9, t_elapsed])
                 
                 signal_sweeps.updated_item(-1)
                 background_sweeps.updated_item(-1)
                 time_sweeps.updated_item(-1)
                 
                 data.push({
                     "title": "APD ODMR",
                     "xlabel": " Frequency / GHz",
                     "ylabel": "Integrated Counts",
                     "datasets": {
                         "signal": signal_sweeps,
                         "background": background_sweeps,
                         "time": time_sweeps,
                         },
                     })
                 
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     awg.output(2, False)
                     awg.output(1, False)
                     return


    def rabi_oscillations(
            self,
            dataset: str,
            freq_hz: float,
            pulse_start_ns: float,
            pulse_stop_ns: float,
            num_points: int,
            iterations: int,
            
            # --- AWG timing defaults ---
            rf_amplitude: int,
            init_ns: int,
            readout_ns: int,
            ch1_delay_ns: int = 50,   # -3879 <-- this is the measured time difference between channel 1 and channel 2 using the test script, but it aint true here!
            ch2_delay_ns: int = 2179,    # For 10000 us, this number should be 22005, For 500 us it should be 1179 (note: 100 ns less from APD CW Exp)
            total_time_us: float = 1000,   # This needs to be understood
            mw_gap_ns_1: int = 5,
            mw_gap_ns_2: int = 50000,
            sample_rate: float = 75e6,
            gate_delay_ns: int = 2500,    # Laser channel delay, - apparently 2500. Can be checked on the oscilloscope (note twice as long as single-pulse upload experiments)
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using AWG + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            tt = mgr.tt20
            odmr = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            # --------------------------------
            # AWG burst configuration (ONCE)
            # --------------------------------
            awg.instrument.write("C1:BSWV PHSE,-0.8")
            awg.instrument.write("C1:BTWV PRD,0.001")
            awg.output(1, True)
            awg.set_arb_mode(1)
            awg.set_burst_mode(1, True)
            awg.set_amplitude(1,8)
            
            awg.output(2, True)
            awg.set_arb_mode(2)
            awg.set_burst_mode(2, True)
            awg.set_amplitude(2,8)
            awg.instrument.write("C2:BSWV PHSE,-0.01")
            awg.instrument.write("C2:BTWV PRD,0.001")
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            pulse_lengths_ns = np.linspace(pulse_start_ns, pulse_stop_ns, num_points)
            
            # --------------------------------
            # AWG time base
            # --------------------------------
            total_time_s = total_time_us * 1e-6
            num_pts = int(round(sample_rate * total_time_s))
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            time.sleep(0.02)
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                sig_counts = np.full(num_points, np.nan)
                bg_counts = np.full(num_points, np.nan)
                t_elapsed = np.full(num_points, np.nan)
                
                signal_sweeps.append(np.stack([pulse_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([pulse_lengths_ns, bg_counts]))
                time_sweeps.append(np.stack([pulse_lengths_ns, t_elapsed]))
                
                # --------------------------------
                # MW pulse sweep
                # --------------------------------
                for idx, mw_ns in enumerate(pulse_lengths_ns):
                    
                    # --------------------------------
                    # Pulse timing - remember, the native units of python is seconds, but the TT is picoseconds
                    # --------------------------------
                    init_t = init_ns * 1e-9
                    mw_t = mw_ns * 1e-9
                    read_t = readout_ns * 1e-9
                    gap_t1 = mw_gap_ns_1 * 1e-9
                    gap_t2 = mw_gap_ns_2 * 1e-9
                    ch2_delay_t = ch2_delay_ns * 1e-9
                    
                    mw_start = init_t + gap_t1
                    read_start = ch2_delay_t + init_t + gap_t1 + mw_t + gap_t2
                    
                    # ======================================================================================
                    # gate_delay_ns = delay from Aux sync pulse to initialisation pulse.
                    # read_start = end of the microwave pulse and beginning of the readout pulse
                    # ======================================================================================
                    gate_delay_ps = (gate_delay_ns * 1e3) * ((read_start) * 1e12)   # read start converted from seconds, to ps, and gate_delay from ns, to ps

                    # ======================================================================================
                    # SIGNAL SEQUENCE (with MW)
                    # ======================================================================================
                    w_laser = np.zeros(num_pts)
                    w_mw = np.zeros(num_pts)
                    
                    odmr.apply_pulse(w_laser, ch2_delay_t, init_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_mw, mw_start, mw_t, 8.0, sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                       channel=1,
                       data=w_mw,
                       name="rabi_mw",
                       sample_rate=sample_rate,
                       )
                                                 
                    odmr.load_arbitrary_waveform_burst(
                        channel=2,
                        data=w_laser,
                        name="rabi_laser",
                        sample_rate=sample_rate,
                        )
                    
                    time.sleep(0.01)
                    
                    # --------------------------------
                    # Signal histogram → integrate
                    # --------------------------------
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    
                    sig_counts[idx] = counts.sum()
                
                    # ====================================================
                    # BACKGROUND SEQUENCE (no MW)
                    # ====================================================
                    # This has been changed to an off-resonance frequency
                    sg.set_frequency(100e3)   # For some reason, niether of these work properly
                    
                    time.sleep(0.01)
                    
                    #w_mw[:] = 0.0
                    
                    #odmr.load_arbitrary_waveform_burst(
                    #    channel=1,
                    #    data=w_mw,
                    #    name="rabi_mw_bg",
                    #    sample_rate=sample_rate,
                    #    )
                    
                    #odmr.load_arbitrary_waveform_burst(
                    #    channel=2,
                    #    data=w_laser,
                    #   name="rabi_laser",
                    #    sample_rate=sample_rate,
                    #    )   
                    
                    t, bg = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    
                    bg_counts[idx] = bg.sum()
                    
                    # --------------------------------
                    # Streaming updates
                    # --------------------------------
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    signal_sweeps[-1] = np.stack([pulse_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([pulse_lengths_ns, bg_counts])
                    time_sweeps[-1] = np.stack([sig_counts, t_elapsed])
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_sweeps.updated_item(-1)
                    
                    data.push({
                        "title": "Pulsed Rabi",
                        "xlabel": "MW Pulse Length / ns",
                        "ylabel": "Integrated Counts",
                        "datasets": {
                            "signal": signal_sweeps,
                            "background": background_sweeps,
                            "time": time_sweeps,
                            },
                        })
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        awg.output(2, False)
                        awg.output(1, False)
                        return
          
                    
    def spin_echo_detected_freq_sweep(
            self,
            dataset: str,
                
            # --- Microwave sweep ---
            start_freq: float,
            stop_freq: float,
            num_points: int,
            iterations: int,
            rf_amp: int,
            
            # --- Pulse timing (ns) ---
            init_ns: int,
            mw_ns: int,
            readout_ns: int,  
            gap_before_mw_ns: int,
            gap_after_mw_ns: int,
            ch1_delay_ns: int = 1350,
            detector_delay_ns: int = 1000,     # to be determined from readout optmisation
            
            # --- AWG ---
            total_time_us: float = 10000.0,
            sample_rate: float = 75e6,
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1.0,     # time for accumulations of pulse sequences
            ):
        """
        Spin-echo–detected microwave frequency sweep using a single MW pulse.
    
        Measurement strategy:
            - Measure each frequency ONCE per sweep
            - Repeat full sweep `iterations` times
        """
    
        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
                tt = mgr.tt20
                odmr = mgr.odmr_driver
                sg = mgr.sg
                awg = mgr.awg
                
                # --------------------------------
                # AWG burst configuration (ONCE)
                # --------------------------------
                awg.set_arb_mode(1)
                awg.set_burst_mode(1, True)
                awg.set_amplitude(1,8)
                awg.instrument.write("C1:BSWV PHSE,0.0")
                awg.instrument.write("C1:BTWV PRD,0.050")
                awg.output(1, True)
                
                awg.set_arb_mode(2)
                awg.set_burst_mode(2, True)
                awg.set_amplitude(2,8)
                awg.instrument.write("C2:BSWV PHSE,-0.01")
                awg.instrument.write("C2:BTWV PRD,0.050")
                awg.output(2, True)
                
                sg.set_amplitude_rf(rf_amp)
                
                # --------------------------------
                # Frequency sweep
                # --------------------------------
                freqs = np.linspace(start_freq, stop_freq, num_points)
                
                # --------------------------------
                # AWG time base
                # --------------------------------
                total_time_s = total_time_us * 1e-6
                num_pts = int(round(sample_rate * total_time_s))
                
                # --------------------------------
                # Convert timing to seconds
                # --------------------------------
                init_t = init_ns * 1e-9
                mw_t = mw_ns * 1e-9
                read_t = readout_ns * 1e-9
                gap1_t = gap_before_mw_ns * 1e-9
                gap2_t = gap_after_mw_ns * 1e-9
                
                ch1_delay_t = ch1_delay_ns * 1e-9
                
                mw_start = ch1_delay_t + init_t + gap1_t
                read_start = mw_start + mw_t + gap2_t
                
                detector_delay_s = detector_delay_ns * 1e-9
                
                gate_delay_ps = int(round(detector_delay_s + read_start * 1e12))
                
                print(gate_delay_ps, init_t, mw_start, read_start)
                # --------------------------------
                # Streaming containers
                # --------------------------------
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                time_sweeps = StreamingList()
                
                sweep_start_time = time.time()
                
                sig_counts = np.zeros(num_points)
                bg_counts = np.zeros(num_points)
                t_elapsed = np.zeros(num_points)
                
                signal_sweeps.append(np.stack([freqs, sig_counts]))
                background_sweeps.append(np.stack([freqs, bg_counts]))
                time_sweeps.append(np.stack([freqs, t_elapsed]))
                
                # --------------------------------
                # Build waveforms (ONCE)
                # --------------------------------
                w_mw_sig = np.zeros(num_pts)
                # w_mw_bg = np.zeros(num_pts)
                w_laser = np.zeros(num_pts)
                
                odmr.apply_pulse(w_laser, 0.0, init_t, 10.0, sample_rate)
                odmr.apply_pulse(w_laser, read_start, read_t, 10.0, sample_rate)
                odmr.apply_pulse(w_mw_sig, mw_start, mw_t, 10.0, sample_rate)
                
                # --------------------------------
                # Repeat full frequency sweep
                # --------------------------------
                for it in range(iterations):
                                        
                    for idx, freq in enumerate(freqs):
                        
                        sg.set_frequency(freq)
                        
                        # CAN THIS BE MOVED OUTSIDE AND REPLACED 
                        # WITH AWG.OUTPUT(1,TRUE/FALSE)?    
                        # --------------------------------
                        # Upload waveforms
                        # --------------------------------
                        odmr.load_arbitrary_waveform_burst(
                            channel=1,
                            data=w_mw_sig,
                            name="mw_signal",
                            sample_rate=sample_rate,
                            )
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=2,
                            data=w_laser,
                            name="laser_pulses",
                            sample_rate=sample_rate,
                            )
                                                
                        time.sleep(0.01)
                        
                        # -------- Signal --------
                        _, counts = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        sig_counts[idx] += counts.sum()
                        
                        sg.set_frequency(100e3)
                                                
                        # Background waveform once per sweep
                        #odmr.load_arbitrary_waveform_burst(
                        #    channel=1,
                        #    data=w_mw_bg,
                        #    name="mw_background",
                        #    sample_rate=sample_rate,
                        #    )
                        
                        time.sleep(0.01)
                        
                        # -------- Background --------
                        _, bg = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        bg_counts[idx] += bg.sum()
                        
                        # --------------------------------
                        # Update averages after each sweep
                        # --------------------------------
                        signal_sweeps[-1] = np.stack([freqs/1e9, sig_counts / (it + 1)])
                        background_sweeps[-1] = np.stack([freqs/1e9, bg_counts / (it + 1)])
                        
                        t_elapsed[:] = time.time() - sweep_start_time
                        time_sweeps[-1] = np.stack([freqs/1e9, t_elapsed])
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_sweeps.updated_item(-1)
                        
                        data.push({
                            "title": "Spin-echo–detected frequency sweep",
                            "xlabel": "Microwave Frequency / GHz",
                            "ylabel": "Integrated Counts",
                            "datasets": {
                                "signal": signal_sweeps,
                                "background": background_sweeps,
                                "time": time_sweeps,
                                },
                            })
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                            awg.output(2, False)
                            awg.output(1, False)
                            return
    
    
    def delay_after_flash(
            self,
            dataset: str,
            num_points: int,
            iterations: int,
            
            # --- AWG timing defaults ---
            init_ns: int,
            readout_ns: int,
            
            stop_ns: float,
            start_ns: float = 100,
            
            ch2_delay_ns: int = 22000,
            total_time_us: float = 10000,
            init_readout_delay_ns: int = 10,
            sample_rate: float = 75e6,
            detector_delay_ns: int = 1000,
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,
            ):
        """
        Delay-after-flash (excited state lifetime) measurement.

        Sequence:
            init pulse → variable delay → readout pulse

        Stored data:
            x-axis → delay between init and readout (ns)
            y-axis → integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            tt = mgr.tt20
            odmr = mgr.odmr_driver
            awg = mgr.awg
            
            # --------------------------------
            # AWG configuration (ONCE)
            # --------------------------------
            awg.output(1, False)
            
            awg.output(2, True)
            awg.set_arb_mode(2)
            awg.set_burst_mode(2, True)
            awg.set_amplitude(2, 8)
            awg.instrument.write("C2:BSWV PHSE,-0.01")
            awg.instrument.write("C2:BTWV PRD,0.001")
            time.sleep(0.01)
            
            # --------------------------------
            # Delay sweep definition
            # --------------------------------
            delay_lengths_ns = np.linspace(start_ns, stop_ns, num_points)
            
            # --------------------------------
            # AWG time base
            # --------------------------------
            total_time_s = total_time_us * 1e-6
            num_pts = int(round(sample_rate * total_time_s))
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            bkg_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                sig_counts = np.full(num_points, np.nan)
                bkg_counts = np.full(num_points, np.nan)
                t_elapsed = np.full(num_points, np.nan)
                
                signal_sweeps.append(np.stack([delay_lengths_ns, sig_counts]))
                bkg_sweeps.append(np.stack([delay_lengths_ns, bkg_counts]))
                time_sweeps.append(np.stack([delay_lengths_ns, t_elapsed]))
                
                # --------------------------------
                # Delay sweep
                # --------------------------------
                for idx, delay_ns in enumerate(delay_lengths_ns):
                    
                    # --------------------------------
                    # Pulse timing (seconds)
                    # --------------------------------
                    init_t = init_ns * 1e-9
                    read_t = readout_ns * 1e-9
                    fixed_gap_t = init_readout_delay_ns * 1e-9
                    swept_delay_t = delay_ns * 1e-9
                    
                    # Readout starts AFTER the swept delay
                    read_start = (init_t + fixed_gap_t + swept_delay_t)
                    
                    # Histogram gate delay (readout only)
                    detector_delay_s = detector_delay_ns * 1e-9
                    gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))
                    gate_delay_ps_bkg = int(round((detector_delay_s) * 1e12))
                    
                    # --------------------------------
                    # Build laser waveform
                    # --------------------------------
                    w_laser = np.zeros(num_pts)
                    bkg_laser = np.zeros(num_pts)
                    
                    # Init pulse
                    odmr.apply_pulse(w_laser, 0.0, init_t, 8.0, sample_rate)
                    
                    # Readout pulse
                    odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=2,
                        data=w_laser,
                        name="daf_laser",
                        sample_rate=sample_rate,
                        )
                    
                    # --------------------------------
                    # Histogram → integrate
                    # --------------------------------
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    
                    sig_counts[idx] = counts.sum()
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    odmr.apply_pulse(bkg_laser, 0.0, read_t, 8.0, sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=2,
                        data=bkg_laser,
                        name="daf_bkg_laser",
                        sample_rate=sample_rate,
                        )
                    
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps_bkg,
                        )
                    
                    bkg_counts[idx] = counts.sum()
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    # --------------------------------
                    # Streaming updates
                    # --------------------------------
                    signal_sweeps[-1] = np.stack([delay_lengths_ns, sig_counts])
                    bkg_sweeps[-1] = np.stack([delay_lengths_ns, bkg_counts])
                    time_sweeps[-1] = np.stack([delay_lengths_ns, t_elapsed])
                    
                    signal_sweeps.updated_item(-1)
                    bkg_sweeps.updated_item(-1)
                    time_sweeps.updated_item(-1)
                    
                    data.push({
                        "title": "Delay After Flash",
                        "xlabel": "Init–Readout Delay / ns",
                        "ylabel": "Integrated Counts",
                        "datasets": {
                            "signal": signal_sweeps,
                            "background": bkg_sweeps,
                            "time": time_sweeps,
                            }})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        awg.output(2, False)
                        awg.output(1, False)
                        return
     

    def ramsey_oscillations(
            self,
            dataset: str,
            freq_hz: float,

            ramsey_start_ns: float,
            ramsey_stop_ns: float,
            num_points: int,
            iterations: int,
            
            # --- Pulse widths ---
            rf_amplitude: int,
            mw_pulse_ns: int,        # π/2 pulse width, to be optimised by Rabi
            init_ns: int,
            readout_ns: int,
            
            # --- Timing ---
            ch2_delay_ns: int = 21990,
            total_time_us: float = 10000,
            mw_gap_ns: int = 50,      # gap before first MW and after second MW
            sample_rate: float = 75e6,
            detector_delay_ns: int = 1000,
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,
            ):
        """
        Pulsed Ramsey experiment using AWG + TimeTagger.
        Signal:
            init + MW(π/2) + τ + MW(π/2) + readout
        Background:
            init + readout (no MW)
        Stored data:
            x-axis → Ramsey delay τ (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            tt = mgr.tt20
            odmr = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            # --------------------------------
            # Microwave setup
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            # --------------------------------
            # AWG burst configuration (ONCE)
            # --------------------------------
            awg.instrument.write("C1:BSWV PHSE,-0.8")
            awg.instrument.write("C1:BTWV PRD,0.050")
            awg.output(1, True)
            awg.set_arb_mode(1)
            awg.set_burst_mode(1, True)
            awg.set_amplitude(1, 8)
            
            awg.output(2, True)
            awg.set_arb_mode(2)
            awg.set_burst_mode(2, True)
            awg.set_amplitude(2, 8)
            awg.instrument.write("C2:BSWV PHSE,-0.01")
            awg.instrument.write("C2:BTWV PRD,0.050")
            time.sleep(0.05)
            
            # --------------------------------
            # Ramsey delay sweep
            # --------------------------------
            ramsey_delays_ns = np.linspace(ramsey_start_ns, ramsey_stop_ns, num_points)
            
            # --------------------------------
            # AWG time base
            # --------------------------------
            total_time_s = total_time_us * 1e-6
            num_pts = int(round(sample_rate * total_time_s))
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                sig_counts = np.full(num_points, np.nan)
                bg_counts = np.full(num_points, np.nan)
                t_elapsed = np.full(num_points, np.nan)
                
                signal_sweeps.append(np.stack([ramsey_delays_ns, sig_counts]))
                background_sweeps.append(np.stack([ramsey_delays_ns, bg_counts]))
                time_sweeps.append(np.stack([ramsey_delays_ns, t_elapsed]))
                
                # --------------------------------
                # Ramsey sweep
                # --------------------------------
                for idx, tau_ns in enumerate(ramsey_delays_ns):
                    
                    # --------------------------------
                    # Convert to seconds
                    # --------------------------------
                    init_t = init_ns * 1e-9
                    mw_t = mw_pulse_ns * 1e-9
                    read_t = readout_ns * 1e-9
                    gap_t = mw_gap_ns * 1e-9
                    tau_t = tau_ns * 1e-9
                    ch2_delay_s = ch2_delay_ns * 1e-9
                    
                    # --------------------------------
                    # Timing
                    # --------------------------------
                    mw1_start = init_t + gap_t
                    mw2_start = mw1_start + mw_t + tau_t
                    read_start = (ch2_delay_s + mw2_start + mw_t + gap_t)
                    
                    # Histogram gate delay
                    detector_delay_s = detector_delay_ns * 1e-9
                    gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))
                    
                    # --------------------------------
                    # SIGNAL SEQUENCE
                    # --------------------------------
                    w_mw = np.zeros(num_pts)
                    w_laser = np.zeros(num_pts)
                    
                    # Laser
                    odmr.apply_pulse(w_laser, ch2_delay_s, init_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
                    
                    # MW π/2 pulses
                    odmr.apply_pulse(w_mw, mw1_start, mw_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_mw, mw2_start, mw_t, 8.0, sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=1,
                        data=w_mw,
                        name="ramsey_mw",
                        sample_rate=sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=2,
                        data=w_laser,
                        name="ramsey_laser",
                        sample_rate=sample_rate)
                    
                    time.sleep(0.02)
                    
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps)
                    
                    sig_counts[idx] = counts.sum()
                    
                    # --------------------------------
                    # BACKGROUND (no MW)
                    # --------------------------------
                    
                    sg.set_frequency(100e3)
                    
                    #w_mw[:] = 0.0
                    
                    #odmr.load_arbitrary_waveform_burst(
                    #    channel=1,
                    #    data=w_mw,
                    #    name="ramsey_mw_bg",
                    #    sample_rate=sample_rate,
                    #    )
                    #time.sleep(0.02)
                    
                    t, bg = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps)
                    
                    bg_counts[idx] = bg.sum()
                    
                    # --------------------------------
                    # Streaming updates
                    # --------------------------------
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    signal_sweeps[-1] = np.stack([ramsey_delays_ns, sig_counts])
                    background_sweeps[-1] = np.stack([ramsey_delays_ns, bg_counts])
                    time_sweeps[-1] = np.stack([ramsey_delays_ns, t_elapsed])
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_sweeps.updated_item(-1)
                    
                    data.push({
                        "title": "Ramsey Oscillations",
                        "xlabel": "Free Evolution Time τ / ns",
                        "ylabel": "Integrated Counts",
                        "datasets": {
                            "signal": signal_sweeps,
                            "background": background_sweeps,
                            "time": time_sweeps,
                            },
                        })
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        awg.output(2, False)
                        awg.output(1, False)
                        return


    def hahn_echo(
            self,
            dataset: str,
            freq_hz: float,
            
            tau_start_ns: float,
            tau_stop_ns: float,
            num_points: int,
            iterations: int,
            
            # --- Pulse widths ---
            rf_amplitude: int,
            mw_pi2_ns: int,          # π/2 pulse width
            init_ns: int,
            readout_ns: int,

            # --- Timing ---
            ch2_delay_ns: int = 21990,
            total_time_us: float = 10000,
            mw_gap_ns: int = 50,
            sample_rate: float = 75e6,
            detector_delay_ns: int = 1000,
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,
            ):
        """
        Hahn Echo experiment using AWG + TimeTagger.
        Signal:
            init + π/2 – τ/2 – π – τ/2 – π/2 + readout
        Background:
            init + readout (no MW)
        Stored data:
            x-axis → τ (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            
            tt = mgr.tt20
            odmr = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            # --------------------------------
            # Microwave setup
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            # --------------------------------
            # AWG burst configuration (ONCE)
            # --------------------------------
            awg.instrument.write("C1:BSWV PHSE,-0.8")
            awg.instrument.write("C1:BTWV PRD,0.050")
            awg.output(1, True)
            awg.set_arb_mode(1)
            awg.set_burst_mode(1, True)
            awg.set_amplitude(1, 8)
            
            awg.output(2, True)
            awg.set_arb_mode(2)
            awg.set_burst_mode(2, True)
            awg.set_amplitude(2, 8)
            awg.instrument.write("C2:BSWV PHSE,-0.01")
            awg.instrument.write("C2:BTWV PRD,0.050")
            time.sleep(0.05)
            
            # --------------------------------
            # τ sweep
            # --------------------------------
            tau_ns = np.linspace(tau_start_ns, tau_stop_ns, num_points)
            
            # --------------------------------
            # AWG time base
            # --------------------------------
            total_time_s = total_time_us * 1e-6
            num_pts = int(round(sample_rate * total_time_s))
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                sig_counts = np.full(num_points, np.nan)
                bg_counts = np.full(num_points, np.nan)
                t_elapsed = np.full(num_points, np.nan)
                
                signal_sweeps.append(np.stack([tau_ns, sig_counts]))
                background_sweeps.append(np.stack([tau_ns, bg_counts]))
                time_sweeps.append(np.stack([tau_ns, t_elapsed]))
                
                # --------------------------------
                # Hahn echo sweep
                # --------------------------------
                for idx, tau in enumerate(tau_ns):
                    
                    # --------------------------------
                    # Convert to seconds
                    # --------------------------------
                    init_t = init_ns * 1e-9
                    read_t = readout_ns * 1e-9
                    mw_pi2_t = mw_pi2_ns * 1e-9
                    mw_pi_t = 2 * mw_pi2_t
                    gap_t = mw_gap_ns * 1e-9
                    tau_t = tau * 1e-9
                    ch2_delay_s = ch2_delay_ns * 1e-9
                    
                    # --------------------------------
                    # MW timing
                    # --------------------------------
                    mw1_start = init_t + gap_t
                    mw_pi_start = mw1_start + mw_pi2_t + tau_t / 2
                    mw2_start = mw_pi_start + mw_pi_t + tau_t / 2
                    
                    read_start = (ch2_delay_s + mw2_start + mw_pi2_t + gap_t)
                    
                    # Histogram gate delay
                    detector_delay_s = detector_delay_ns * 1e-9
                    gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))
                    
                    # --------------------------------
                    # SIGNAL sequence
                    # --------------------------------
                    w_mw = np.zeros(num_pts)
                    w_laser = np.zeros(num_pts)
                    
                    # Laser pulses
                    odmr.apply_pulse(w_laser, ch2_delay_s, init_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
                    
                    # MW pulses
                    odmr.apply_pulse(w_mw, mw1_start, mw_pi2_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_mw, mw_pi_start, mw_pi_t, 8.0, sample_rate)
                    odmr.apply_pulse(w_mw, mw2_start, mw_pi2_t, 8.0, sample_rate)
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=1,
                        data=w_mw,
                        name="hahn_mw",
                        sample_rate=sample_rate,
                        )
                    
                    odmr.load_arbitrary_waveform_burst(
                        channel=2,
                        data=w_laser,
                        name="hahn_laser",
                    sample_rate=sample_rate,
                    )
                    time.sleep(0.01)
                    
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    sig_counts[idx] = counts.sum()
                        
                    # --------------------------------
                    # BACKGROUND (no MW)
                    # --------------------------------
                    
                    sg.set_frequency(100e3)
                    
                    #w_mw[:] = 0.0
                    
                    #odmr.load_arbitrary_waveform_burst(
                    #    channel=1,
                    #    data=w_mw,
                    #    name="hahn_mw_bg",
                    #    sample_rate=sample_rate,
                    #    )
                    #time.sleep(0.02)
                    
                    t, bg = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    bg_counts[idx] = bg.sum()
                    
                    # --------------------------------
                    # Streaming updates
                    # --------------------------------
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    signal_sweeps[-1] = np.stack([tau_ns, sig_counts])
                    background_sweeps[-1] = np.stack([tau_ns, bg_counts])
                    time_sweeps[-1] = np.stack([tau_ns, t_elapsed])
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_sweeps.updated_item(-1)
                    
                    data.push({
                        "title": "Hahn Echo",
                        "xlabel": "Total Evolution Time τ / ns",
                        "ylabel": "Integrated Counts",
                        "datasets": {
                            "signal": signal_sweeps,
                            "background": background_sweeps,
                            "time": time_sweeps,
                            },})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        awg.output(2, False)
                        awg.output(1, False)
                        return


#------------------------------------------------------------------------------
# Optimisation Experiments - Simple Experiments to Visual the Initialisation
# and Readout Pulses and Optimise the Delay Timings
#------------------------------------------------------------------------------

    def odmr_initialization_measurement(
            self,
            dataset: str,
            pulse_width: float,
            modulation_freq: float,
            binwidth_ns: int,
            n_bins: int,
            iterations: int,
            integration_time: float = 1,
            ):
        """
        ODMR initialization (timing) measurement.
        Measures photon arrival time histogram relative to the pulse sequence.
        """
        
        with MyInstrumentManager() as mgr, DataSource(dataset) as odmr_data:
            
            sg = mgr.sg
            tt20 = mgr.tt20
            awg = mgr.awg
            
            # ------------------------------------------------
            # Microwave configuration
            # ------------------------------------------------
            sg.set_output(0)
            
            # ------------------------------------------------
            # AWG pulse sequence
            # ------------------------------------------------
            awg.set_waveform(2, "PULS")
            awg.set_frequency(2, modulation_freq)
            awg.set_amplitude(2, 8)
            awg.set_pulse_width(2, pulse_width / 1e9)
            awg.set_burst_mode(2, True)
            awg.output(2, True)
        
            awg.output(1, False)
            
            time.sleep(0.01)
            
            # ------------------------------------------------
            # Streaming datasets
            # ------------------------------------------------
            hist_sweeps = StreamingList()
            
            # Time axis in ns for plotting (FORCE LOCAL ARRAY)
            time_axis = np.asarray(
                np.arange(n_bins) * binwidth_ns * 1e-3,
                dtype=float)
            
            gate_delay_ps = 0 * 1e3    # integer is in units of nanoseconds
            
            # ------------------------------------------------
            # Measurement loop
            # ------------------------------------------------
            for i in range(iterations):
                
                t_ps, counts = tt20.run_histogram(
                    click_channel=1,     # detector
                    start_channel=2,     # AWG trigger / sync
                    binwidth_ps=binwidth_ns * 1e3,
                    n_bins=n_bins,
                    capture_time_s=integration_time,
                    start_delay=gate_delay_ps)
                
                counts = np.asarray(counts, dtype=float)
                
                hist_sweeps.append(np.stack((time_axis, counts), axis=0))
                hist_sweeps.updated_item(-1)
                
                # ------------------------------------------------
                # Push data
                # ------------------------------------------------
                odmr_data.push({
                    'params': {
                        'pulse_width_s': pulse_width,
                        'modulation_freq_hz': modulation_freq,
                        'binwidth_ps': binwidth_ns,
                        'n_bins': n_bins,
                        'iterations': iterations,
                        },
                    'title': 'ODMR Initialization Measurement',
                    'xlabel': 'Time / microseconds',
                    'ylabel': 'Counts',
                    'datasets': {
                        'histogram': hist_sweeps,
                        }})
                
                if experiment_widget_process_queue(self.queue_to_exp) == 'stop':
                    awg.output(2, False)
                    awg.output(1, False)
                    return
              
                
    def odmr_readout_optimisation(
             self,
             dataset: str,
             iterations: int,
             
             # --- AWG timing defaults ---
             init_ns: int,
             readout_ns: int,
             mw_ns: int,
             readout_delay_ns = 0,
             total_time_us: float = 500,
             mw_gap_ns: int = 50,
             sample_rate: float = 75e6,
             ch2_delay_ns: float = 1250,
             
             # --- TimeTagger ---
             start_channel: int = 2,
             click_channel: int = 1,
             binwidth_ns: int = 1000,
             n_bins: int = 1000,
             integration_time: float = 1,   # time for accumulations of pulse sequences
             event_divider: int = 1,  # Reduce the number of events counted
             ):
         """
         Pulsed Rabi oscillation experiment using AWG + TimeTagger.        
         Signal      = init + MW + readout
         Background  = init + readout (no MW)

         Stored data:
             x-axis → MW pulse length (ns)
             y-axis → Integrated photon counts
         """

         with MyInstrumentManager() as mgr, DataSource(dataset) as data:
             tt20 = mgr.tt20
             odmr = mgr.odmr_driver
             awg = mgr.awg
                         
             # --------------------------------
             # AWG burst configuration (ONCE)
             # --------------------------------
             awg.instrument.write("C1:BSWV PHSE,-0.8")
             awg.instrument.write("C1:BTWV PRD,0.001")
             awg.output(1, True)
             awg.set_arb_mode(1)
             awg.set_burst_mode(1, True)
             awg.set_amplitude(1,8)
             
             awg.output(2, True)
             awg.set_arb_mode(2)
             awg.set_burst_mode(2, True)
             awg.set_amplitude(2,8)
             awg.instrument.write("C2:BSWV PHSE,-0.01")
             awg.instrument.write("C2:BTWV PRD,0.001")
             time.sleep(0.01)
                         
             # --------------------------------
             # AWG time base
             # --------------------------------
             total_time_s = total_time_us * 1e-6
             num_pts = int(round(sample_rate * total_time_s))
             
             # ------------------------------------------------
             # Streaming datasets
             # ------------------------------------------------
             hist_sweeps = StreamingList()
             
             # Time axis in ns for plotting (FORCE LOCAL ARRAY)
             time_axis = np.asarray(
                 np.arange(n_bins) * binwidth_ns * 1e-3,
                 dtype=float)
             
             # --------------------------------
             # Pulse timing
             # --------------------------------
             init_t = init_ns * 1e-9
             mw_t = mw_ns * 1e-9
             read_t = readout_ns * 1e-9
             gap_t = mw_gap_ns * 1e-9
             ch2_delay_t = ch2_delay_ns * 1e-9
             
             mw_start = init_t + gap_t
             read_start = ch2_delay_t + init_t + mw_t + gap_t
             
             gate_delay_ps = readout_delay_ns * 1e3

             # ====================================================
             # SIGNAL SEQUENCE (with MW)
             # ====================================================
             w_laser = np.zeros(num_pts)
             w_mw = np.zeros(num_pts)
             
             odmr.apply_pulse(w_laser, ch2_delay_t, init_t, 8.0, sample_rate)
             odmr.apply_pulse(w_laser, read_start, read_t, 8.0, sample_rate)
             odmr.apply_pulse(w_mw, mw_start, mw_t, 8.0, sample_rate)
             
             odmr.load_arbitrary_waveform_burst(
                channel=1,
                data=w_mw,
                name="rabi_mw",
                sample_rate=sample_rate,
                )
                                          
             odmr.load_arbitrary_waveform_burst(
                 channel=2,
                 data=w_laser,
                 name="rabi_laser",
                 sample_rate=sample_rate,
                 )
             
             time.sleep(0.1)
             
             # ------------------------------------------------
             # Measurement loop
             # ------------------------------------------------
             for i in range(iterations):
                 
                 t, counts = tt20.run_histogram(
                     click_channel=1,     # detector
                     start_channel=2,     # AWG trigger / sync
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=gate_delay_ps,
                     event_divider=event_divider,
                     )

                 counts = np.asarray(counts, dtype=float)
                
                 hist_sweeps.append(
                    np.stack((time_axis, counts), axis=0)
                    )
                 
                 hist_sweeps.updated_item(-1)
                 # ------------------------------------------------
                 # Push data
                 # ------------------------------------------------
                 data.push({
                     'params': {
                         'initialisation_pulse_width_ns': init_ns,
                         'readout_pulse_width_ns': readout_ns,
                         'binwidth_ps': binwidth_ns,
                         'n_bins': n_bins,
                         'iterations': iterations,
                         },
                     'title': 'ODMR Readout Optimisation',
                     'xlabel': 'Time / microseconds',
                     'ylabel': 'Counts',
                     'datasets': {
                         'histogram': hist_sweeps,
                         }
                     })
                     
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     awg.output(2, False)
                     awg.output(1, False)
                     return
                 
    
    def optimize_mw_delay(
                self,
                dataset: str,
                freq_hz: float,
                
                # --- MW delay sweep ---
                mw_delay_start_ns: float,
                mw_delay_stop_ns: float,
                num_points: int,
                mw_ns: float,    
                iterations: int,
                
                # --- Pulse timing ---
                init_ns: int,
                readout_ns: int,
      #          ch1_delay_ns: int = -3879, # This is the measured time difference between channel 1 and channel 2.
                ch2_delay_ns: int = 23000,  # This is the experimental difference.
                mw_gap_ns: int = 50,
                readout_gap_ns: int = 50000,
                total_time_us: float = 10000,
                sample_rate: float = 75e6,
                detector_delay_ns: int = 1000,
                
                # --- TimeTagger ---
                start_channel: int = 2,
                click_channel: int = 1,
                binwidth_ns: int = 1000,
                n_bins: int = 1000,
                integration_time: float = 1,
                ):
        
            """
            Optimize the relative timing between laser initialization and microwave pulse.
            Signal sequence:
                Laser init → MW (fixed length, swept delay) → Laser readout
            Background sequence:
                Laser init → (NO MW) → Laser readout

            Stored data:
                x-axis → MW delay (ns)
                signal → Integrated counts with MW
                background → Integrated counts without MW
            """

            with MyInstrumentManager() as mgr, DataSource(dataset) as data:
                tt = mgr.tt20
                odmr = mgr.odmr_driver
                sg = mgr.sg
                awg = mgr.awg
                
                # --------------------------------
                # Microwave frequency
                # --------------------------------
                sg.set_frequency(freq_hz)
                
                # --------------------------------
                # AWG configuration (ONCE)
                # --------------------------------
                awg.instrument.write("C1:BSWV PHSE,-0.8")
                awg.instrument.write("C1:BTWV PRD,0.001")
                awg.output(1, True)
                awg.set_arb_mode(1)
                awg.set_burst_mode(1, True)
                awg.set_amplitude(1, 8)
                
                awg.instrument.write("C2:BSWV PHSE,-0.01")
                awg.instrument.write("C2:BTWV PRD,0.001")
                awg.output(2, True)
                awg.set_arb_mode(2)
                awg.set_burst_mode(2, True)
                awg.set_amplitude(2, 8)
                
                time.sleep(0.01)
                
                # --------------------------------
                # Sweep definition
                # --------------------------------
                mw_delays_ns = np.linspace(mw_delay_start_ns, mw_delay_stop_ns, num_points)
                
                # --------------------------------
                # AWG time base
                # --------------------------------
                total_time_s = total_time_us * 1e-6
                num_pts = int(round(sample_rate * total_time_s))
                
                # --------------------------------
                # Streaming containers
                # --------------------------------
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                time_sweeps = StreamingList()
                sweep_start_time = time.time()
                
                # --------------------------------
                # Iterations
                # --------------------------------
                for it in range(iterations):
                    sig_counts = np.full(num_points, np.nan)
                    bg_counts = np.full(num_points, np.nan)
                    t_elapsed = np.full(num_points, np.nan)
                    
                    signal_sweeps.append(np.stack([mw_delays_ns, sig_counts]))
                    background_sweeps.append(np.stack([mw_delays_ns, bg_counts]))
                    time_sweeps.append(np.stack([mw_delays_ns, t_elapsed]))
                    
                    # --------------------------------
                    # MW delay sweep
                    # --------------------------------
                    for idx, mw_delay_ns in enumerate(mw_delays_ns):
                        
                        # --- Timing (seconds) ---
                        init_t = init_ns * 1e-9
                        mw_delay_t = mw_delay_ns * 1e-9
                        mw_t = mw_ns * 1e-9
                        read_t = readout_ns * 1e-9
                        gap_t = mw_gap_ns * 1e-9
     #                   ch1_delay_s = ch1_delay_ns * 1e-9
                        ch2_delay_s = ch2_delay_ns * 1e-9
                        readout_gap_t = readout_gap_ns * 1e-9
                        
                        # --- Absolute timing ---
                        mw_start = mw_delay_t
                        read_start = (ch2_delay_s + init_t + gap_t + mw_t + readout_gap_t)
                        
                        # --- Histogram gate ---
                        detector_delay_s = detector_delay_ns * 1e-9
                        gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))
                        
                        # --------------------------------
                        # Build waveforms
                        # --------------------------------
                        w_mw = np.zeros(num_pts)
                        w_laser = np.zeros(num_pts)
                        
                        # Laser init
                        odmr.apply_pulse(w_laser,ch2_delay_s,init_t,8.0,sample_rate)
                        
                        # Laser readout
                        odmr.apply_pulse(w_laser,read_start,read_t,8.0,sample_rate)
                        
                        # --------------------------------
                        # SIGNAL sequence (MW ON)
                        # --------------------------------
                        odmr.apply_pulse(w_mw, mw_start, mw_t, 8.0, sample_rate)
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=1,
                            data=w_mw,
                            name="mw_signal",
                            sample_rate=sample_rate,
                            )
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=2,
                            data=w_laser,
                            name="laser",
                            sample_rate=sample_rate,
                            )    
                        time.sleep(0.001)
                        
                        _, counts_sig = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        
                        sig_counts[idx] = counts_sig.sum()
                        
                        # --------------------------------
                        # BACKGROUND sequence (MW OFF)
                        # --------------------------------
                        # Changed to more efficient off-resonance method.
                        
                        sg.set_frequency(100e3)
                        
                        #w_mw[:] = 0.0
                        
                        #odmr.load_arbitrary_waveform_burst(
                        #    channel=1,
                        #    data=w_mw,
                        #    name="mw_background",
                        #    sample_rate=sample_rate,
                        #    )
                        #time.sleep(0.01)
                        
                        _, counts_bg = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        
                        bg_counts[idx] = counts_bg.sum()
                        
                        # --------------------------------
                        # Streaming updates
                        # --------------------------------
                        t_elapsed[idx] = time.time() - sweep_start_time
                        
                        signal_sweeps[-1] = np.stack([mw_delays_ns, sig_counts])
                        background_sweeps[-1] = np.stack([mw_delays_ns, bg_counts])
                        time_sweeps[-1] = np.stack([mw_delays_ns, t_elapsed])
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_sweeps.updated_item(-1)
                        
                        data.push({
                            "title": "MW Delay Optimization",
                            "xlabel": "MW Delay / ns",
                            "ylabel": "Integrated Counts",
                            "datasets": {
                                "signal": signal_sweeps,
                                "background": background_sweeps,
                                "time": time_sweeps,
                                },
                            })
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                            awg.output(1, False)
                            awg.output(2, False)
                            return


    def optimize_readout_delay(
                self,
                dataset: str,
                freq_hz: float,
                
                # --- MW delay sweep ---
                readout_delay_start_ns: float,
                readout_delay_stop_ns: float,
                num_points: int,
                mw_ns: float,    
                iterations: int,
                
                # --- Pulse timing ---
                init_ns: int,
                readout_ns: int,
    
                ch2_delay_ns: int = 21980,
                mw_gap_ns: int = 50,
                total_time_us: float = 10000,
                sample_rate: float = 75e6,
                detector_delay_ns: int = 1000,
                
                # --- TimeTagger ---
                start_channel: int = 2,
                click_channel: int = 1,
                binwidth_ns: int = 1000,
                n_bins: int = 1000,
                integration_time: float = 1,
                ):
        
            """
            Optimize the relative timing between laser initialization and microwave pulse.
            Signal sequence:
                Laser init → MW (fixed length, swept delay) → Laser readout
            Background sequence:
                Laser init → (NO MW) → Laser readout

            Stored data:
                x-axis → MW delay (ns)
                signal → Integrated counts with MW
                background → Integrated counts without MW
            """

            with MyInstrumentManager() as mgr, DataSource(dataset) as data:
                tt = mgr.tt20
                odmr = mgr.odmr_driver
                sg = mgr.sg
                awg = mgr.awg
                
                # --------------------------------
                # Microwave frequency
                # --------------------------------
                sg.set_frequency(freq_hz)
                
                # --------------------------------
                # AWG configuration (ONCE)
                # --------------------------------
                awg.instrument.write("C1:BSWV PHSE,-0.8")
                awg.instrument.write("C1:BTWV PRD,0.001")
                awg.output(1, True)
                awg.set_arb_mode(1)
                awg.set_burst_mode(1, True)
                awg.set_amplitude(1, 8)
                
                awg.instrument.write("C2:BSWV PHSE,-0.01")
                awg.instrument.write("C2:BTWV PRD,0.001")
                awg.output(2, True)
                awg.set_arb_mode(2)
                awg.set_burst_mode(2, True)
                awg.set_amplitude(2, 8)
                
                time.sleep(0.01)
                
                # --------------------------------
                # Sweep definition
                # --------------------------------
                readout_delays_ns = np.linspace(readout_delay_start_ns, 
                                                readout_delay_stop_ns, num_points)
                
                # --------------------------------
                # AWG time base
                # --------------------------------
                total_time_s = total_time_us * 1e-6
                num_pts = int(round(sample_rate * total_time_s))
                
                # --------------------------------
                # Streaming containers
                # --------------------------------
                signal_sweeps = StreamingList()
                background_sweeps = StreamingList()
                time_sweeps = StreamingList()
                sweep_start_time = time.time()
                
                # --------------------------------
                # Iterations
                # --------------------------------
                for it in range(iterations):
                    sig_counts = np.full(num_points, np.nan)
                    bg_counts = np.full(num_points, np.nan)
                    t_elapsed = np.full(num_points, np.nan)
                    
                    signal_sweeps.append(np.stack([readout_delays_ns, sig_counts]))
                    background_sweeps.append(np.stack([readout_delays_ns, bg_counts]))
                    time_sweeps.append(np.stack([readout_delays_ns, t_elapsed]))
                    
                    # --------------------------------
                    # MW delay sweep
                    # --------------------------------
                    for idx, mw_gap_ns_2 in enumerate(readout_delays_ns):
                        
                        # --- Timing (seconds) ---
                        init_t = init_ns * 1e-9
                        mw_t = mw_ns * 1e-9
                        read_t = readout_ns * 1e-9
                        gap_t = mw_gap_ns * 1e-9
                        ch2_delay_s = ch2_delay_ns * 1e-9
                        
                        # --- Absolute timing ---
                        mw_start = init_t + gap_t
                        read_start = (ch2_delay_s + init_t + gap_t + mw_t + mw_gap_ns_2)
                        
                        # --- Histogram gate ---
                        detector_delay_s = detector_delay_ns * 1e-9
                        gate_delay_ps = int(round((detector_delay_s + read_start) * 1e12))
                        
                        # --------------------------------
                        # Build waveforms
                        # --------------------------------
                        w_mw = np.zeros(num_pts)
                        w_laser = np.zeros(num_pts)
                        
                        # Laser init
                        odmr.apply_pulse(w_laser,ch2_delay_s,init_t,8.0,sample_rate)
                        
                        # Laser readout
                        odmr.apply_pulse(w_laser,read_start,read_t,8.0,sample_rate)
                        
                        # --------------------------------
                        # SIGNAL sequence (MW ON)
                        # --------------------------------
                        odmr.apply_pulse(w_mw, mw_start, mw_t, 8.0, sample_rate)
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=1,
                            data=w_mw,
                            name="mw_signal",
                            sample_rate=sample_rate,
                            )
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=2,
                            data=w_laser,
                            name="laser",
                            sample_rate=sample_rate,
                            )    
                        time.sleep(0.01)
                        
                        _, counts_sig = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        
                        sig_counts[idx] = counts_sig.sum()
                        
                        # --------------------------------
                        # BACKGROUND sequence (MW OFF)
                        # --------------------------------
                        # Changed to an off-resonance frequency because 
                        # re-loading a blank pulse is really dumb
                        
                        sg.set_frequency(100e3)
                        
                        #w_mw[:] = 0.0
                        
                        #odmr.load_arbitrary_waveform_burst(
                        #    channel=1,
                        #    data=w_mw,
                        #    name="mw_background",
                        #    sample_rate=sample_rate,
                        #    )
                        #time.sleep(0.01)
                        
                        _, counts_bg = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        
                        bg_counts[idx] = counts_bg.sum()
                        
                        # --------------------------------
                        # Streaming updates
                        # --------------------------------
                        t_elapsed[idx] = time.time() - sweep_start_time
                        
                        signal_sweeps[-1] = np.stack([readout_delays_ns, sig_counts])
                        background_sweeps[-1] = np.stack([readout_delays_ns, bg_counts])
                        time_sweeps[-1] = np.stack([readout_delays_ns, t_elapsed])
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_sweeps.updated_item(-1)
                        
                        data.push({
                            "title": "Readout Delay Optimization",
                            "xlabel": "Readout Delay / ns",
                            "ylabel": "Integrated Counts",
                            "datasets": {
                                "signal": signal_sweeps,
                                "background": background_sweeps,
                                "time": time_sweeps,
                                },
                            })
                        
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                            awg.output(1, False)
                            awg.output(2, False)
                            return


    def rabi_vs_mw_delay(
            self,
            dataset: str,
            freq_hz: float,
            
            # --- MW pulse sweep ---
            pulse_start_ns: float,
            pulse_stop_ns: float,
            num_pulse_points: int,
            
            # --- MW delay sweep ---
            mw_delay_start_ns: float,
            mw_delay_stop_ns: float,
            num_delay_points: int,
            
            iterations: int,
            
            # --- Pulse timing ---
            init_ns: int,
            readout_ns: int,
            rf_amplitude: int = 7.4,
            ch2_delay_ns: int = 22000,
            mw_gap_ns: int = 50,
            readout_gap_ns: int = 50000,
            total_time_us: float = 10000,
            sample_rate: float = 75e6,
            detector_delay_ns: int = 1000,
            
            # --- TimeTagger ---
            start_channel: int = 2,
            click_channel: int = 1,
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,
            ):
        """
        3D experiment: Rabi oscillations vs MW delay.
        
        Dimensions:
            x → MW pulse length (ns)
            y → MW delay after init (ns)
            z → Integrated photon counts
            
            Signal      = init + MW + readout
            Background  = init + readout
        """
            
        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            tt = mgr.tt20
            odmr = mgr.odmr_driver
            sg = mgr.sg
            awg = mgr.awg
            
            # --------------------------------
            # Microwave source
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
            
            # --------------------------------
            # AWG configuration (ONCE)
            # --------------------------------
            awg.instrument.write("C1:BSWV PHSE,-0.8")
            awg.instrument.write("C1:BTWV PRD,0.001")
            awg.output(1, True)
            awg.set_arb_mode(1)
            awg.set_burst_mode(1, True)
            awg.set_amplitude(1, 8)
            
            awg.instrument.write("C2:BSWV PHSE,-0.01")
            awg.instrument.write("C2:BTWV PRD,0.001")
            awg.output(2, True)
            awg.set_arb_mode(2)
            awg.set_burst_mode(2, True)
            awg.set_amplitude(2, 8)
            
            time.sleep(0.01)
            
            # --------------------------------
            # Sweep definitions
            # --------------------------------
            pulse_lengths_ns = np.linspace(
                pulse_start_ns, pulse_stop_ns, num_pulse_points
                )
            mw_delays_ns = np.linspace(
                mw_delay_start_ns, mw_delay_stop_ns, num_delay_points
                )
            
            # --------------------------------
            # AWG time base
            # --------------------------------
            total_time_s = total_time_us * 1e-6
            num_pts = int(round(sample_rate * total_time_s))
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                
                sig_counts = np.full((num_delay_points, num_pulse_points), np.nan)
                bg_counts = np.full_like(sig_counts, np.nan)
                t_elapsed = np.full(num_delay_points, np.nan)
                
                signal_sweeps.append(sig_counts.copy())
                background_sweeps.append(bg_counts.copy())
                time_sweeps.append(t_elapsed.copy())
                
                # --------------------------------
                # MW delay sweep (outer loop)
                # --------------------------------
                for d_idx, mw_delay_ns in enumerate(mw_delays_ns):
                    
                    init_t = init_ns * 1e-9
                    mw_delay_t = mw_delay_ns * 1e-9
                    read_t = readout_ns * 1e-9
                    gap_t = mw_gap_ns * 1e-9
                    readout_gap_t = readout_gap_ns * 1e-9
                    ch2_delay_s = ch2_delay_ns * 1e-9
                    
                    # Laser timing
                    mw_start_base = mw_delay_t
                    read_start_base = (ch2_delay_s + init_t + gap_t + readout_gap_t)
                    
                    detector_delay_s = detector_delay_ns * 1e-9
                    
                    # --------------------------------
                    # MW pulse length sweep (inner loop)
                    # --------------------------------
                    for p_idx, mw_ns in enumerate(pulse_lengths_ns):
                        
                        mw_t = mw_ns * 1e-9
                        read_start = read_start_base + mw_t
                        gate_delay_ps = int(
                            round((detector_delay_s + read_start) * 1e12)
                            )
                        
                        # --------------------------------
                        # Build waveforms
                        # --------------------------------
                        w_mw = np.zeros(num_pts)
                        w_laser = np.zeros(num_pts)
                        
                        # Laser init
                        odmr.apply_pulse(
                            w_laser, ch2_delay_s, init_t, 8.0, sample_rate
                            )
                        
                        # Laser readout
                        odmr.apply_pulse(
                            w_laser, read_start, read_t, 8.0, sample_rate
                            )
                        
                        # MW pulse
                        odmr.apply_pulse(
                            w_mw, mw_start_base, mw_t, 8.0, sample_rate
                            )
                        
                        odmr.load_arbitrary_waveform_burst(
                            channel=1,
                            data=w_mw,
                            name="mw_signal",
                            sample_rate=sample_rate,
                            )
                        odmr.load_arbitrary_waveform_burst(
                            channel=2,
                            data=w_laser,
                            name="laser",
                            sample_rate=sample_rate,
                            )
                        
                        time.sleep(0.01)
                        
                        # --------------------------------
                        # Signal
                        # --------------------------------
                        _, counts = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        sig_counts[d_idx, p_idx] = counts.sum()
                        
                        # --------------------------------
                        # Background (MW OFF)
                        # --------------------------------
                        
                        sg.set_frequency(100e3)
                        
                        #w_mw[:] = 0.0
                        
                        #odmr.load_arbitrary_waveform_burst(
                        #    channel=1,
                        #    data=w_mw,
                        #    name="mw_background",
                        #    sample_rate=sample_rate,
                        #    )
                        #time.sleep(0.01)
                        
                        _, counts_bg = tt.run_histogram(
                            click_channel=click_channel,
                            start_channel=start_channel,
                            binwidth_ps=binwidth_ns * 1e3,
                            n_bins=n_bins,
                            capture_time_s=integration_time,
                            start_delay=gate_delay_ps,
                            )
                        bg_counts[d_idx, p_idx] = counts_bg.sum()
                        
                        # --------------------------------
                        # Streaming update (per delay slice)
                        # --------------------------------
                        t_elapsed[d_idx] = time.time() - sweep_start_time
                        
                        signal_sweeps[-1] = sig_counts.copy()
                        background_sweeps[-1] = bg_counts.copy()
                        time_sweeps[-1] = t_elapsed.copy()
                        
                        signal_sweeps.updated_item(-1)
                        background_sweeps.updated_item(-1)
                        time_sweeps.updated_item(-1)
                        
                        data.push({
                            "title": "Rabi vs MW Delay",
                            "btm_label": "MW Pulse Length / ns",
                            "lft_label": "MW Delay / ns",
                            "zlabel": "Integrated Counts",
                            "datasets": {
                                "signal": {
                                    "x": pulse_lengths_ns,
                                    "y": mw_delays_ns,
                                    "z": sig_counts.copy(),
                                    },
                                "background": {
                                    "x": pulse_lengths_ns,
                                    "y": mw_delays_ns,
                                    "z": bg_counts.copy(),
                                    },
                                "time": {
                                    "y": mw_delays_ns,
                                    "t": t_elapsed.copy(),
                                    },
                                },
                            })
                        if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                            awg.output(1, False)
                            awg.output(2, False)
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


#------------------------------------------------------------------------------
# PulseSteamer8/2 Experiments 
#                    - Laser pulses are achieved by square wave modulation 
#                      through the AWG, and detection is achieved using 
#                      manually set modulation through the signal generator.
#------------------------------------------------------------------------------

    def rabi_oscillations_ps82(
            self,
            dataset: str,
            
            freq_hz: float,
            pulse_start_ns: float,
            pulse_stop_ns: float,
            num_points: int,
            iterations: int,
            rf_amplitude: int,
            
            # --- PulseStreamer8/2 ---
            init_ns: int,
            readout_ns: int,
            mw_gap_ns_1: int = 5,
            mw_gap_ns_2: int = 50000,
            recovery_ns: int = 10000,
            
            # --- TimeTagger ---
            gate_delay_ns: int = 100, # Gate_delay_measured using TimeTagger
            start_channel: int = 5,    # For ps82, I have chosen port 5 of the timetagger as the trigger.
            click_channel: int = 1,
            
            binwidth_ns: int = 1000,
            n_bins: int = 1000,
            integration_time: float = 1,   # time for accumulations of pulse sequences
            ):
        """
        Pulsed Rabi oscillation experiment using AWG + TimeTagger.        
        Signal      = init + MW + readout
        Background  = init + readout (no MW)

        Stored data:
            x-axis → MW pulse length (ns)
            y-axis → Integrated photon counts
        """

        with MyInstrumentManager() as mgr, DataSource(dataset) as data:
            tt = mgr.tt20
            ps82 = mgr.ps82
            sg = mgr.sg
          
            # --------------------------------
            # Microwave frequency
            # --------------------------------
            sg.set_frequency(freq_hz)
            sg.set_amplitude_rf(rf_amplitude)
                        
            # --------------------------------
            # Sweep definition
            # --------------------------------
            pulse_lengths_ns = np.linspace(pulse_start_ns, pulse_stop_ns, num_points)
            
            # --------------------------------
            # Streaming containers
            # --------------------------------
            signal_sweeps = StreamingList()
            background_sweeps = StreamingList()
            time_sweeps = StreamingList()
            sweep_start_time = time.time()
            
            # --------------------------------
            # Iterations
            # --------------------------------
            for it in range(iterations):
                sig_counts = np.full(num_points, np.nan)
                bg_counts = np.full(num_points, np.nan)
                t_elapsed = np.full(num_points, np.nan)
                
                signal_sweeps.append(np.stack([pulse_lengths_ns, sig_counts]))
                background_sweeps.append(np.stack([pulse_lengths_ns, bg_counts]))
                time_sweeps.append(np.stack([pulse_lengths_ns, t_elapsed]))
                
                # --------------------------------
                # MW pulse sweep
                # --------------------------------
                for idx, mw_ns in enumerate(pulse_lengths_ns):
                    
                    sg.set_frequency(freq_hz)
                    ps82.channel_sequences = {}  # Clear previous
                    
                    # --------------------------------
                    # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                    # --------------------------------
                    laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),
                                 (mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
                    mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),
                              (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
                    trig_seq = [(100, 1),(init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + readout_ns + recovery_ns - 100, 0)]

                    ps82.allocate_sequence(mw_seq, 0)
                    ps82.allocate_sequence(laser_seq, 1)
                    ps82.allocate_sequence(trig_seq, 2)

                    ps82.begin_pulses(n_runs=-1)              
                    
                    # ======================================================================================
                    # gate_delay_ns = delay from Aux sync pulse to initialisation pulse.
                    # the remainder is the length of the pulse sequence up to the readout pulse
                    # ======================================================================================
                    gate_delay_ps = (gate_delay_ns + (init_ns + mw_gap_ns_1 + mw_ns +
                                mw_gap_ns_2) * 1e3)
                    
                    # --------------------------------
                    # Signal histogram → integrate
                    # --------------------------------
                    t, counts = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps)
                    
                    sig_counts[idx] = counts.sum()
                
                    # ====================================================
                    # BACKGROUND SEQUENCE (off-resonance MW)
                    # ====================================================
                    # This has been changed to an off-resonance frequency
                    sg.set_frequency(100e3)  
                    
                    time.sleep(0.01)
                    
                    t, bg = tt.run_histogram(
                        click_channel=click_channel,
                        start_channel=start_channel,
                        binwidth_ps=binwidth_ns * 1e3,
                        n_bins=n_bins,
                        capture_time_s=integration_time,
                        start_delay=gate_delay_ps,
                        )
                    
                    bg_counts[idx] = bg.sum()
                    
                    # --------------------------------
                    # Streaming updates
                    # --------------------------------
                    t_elapsed[idx] = time.time() - sweep_start_time
                    
                    signal_sweeps[-1] = np.stack([pulse_lengths_ns, sig_counts])
                    background_sweeps[-1] = np.stack([pulse_lengths_ns, bg_counts])
                    time_sweeps[-1] = np.stack([sig_counts, t_elapsed])
                    
                    signal_sweeps.updated_item(-1)
                    background_sweeps.updated_item(-1)
                    time_sweeps.updated_item(-1)
                    
                    data.push({
                        "title": "Pulsed Rabi",
                        "xlabel": "MW Pulse Length / ns",
                        "ylabel": "Integrated Counts",
                        "datasets": {
                            "signal": signal_sweeps,
                            "background": background_sweeps,
                            "time": time_sweeps,
                            },})
                    
                    if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        ps82.stop()
                        return


    def odmr_readout_optimisation_ps82(
             self,
             dataset: str,
             iterations: int,
             
             # --- PS82 timing defaults ---
             init_ns: int,
             readout_ns: int,
             mw_ns: int,
             readout_delay_ns = 0,
             mw_gap_ns_1: int = 50,
             mw_gap_ns_2: int = 50,
             recovery_ns: int = 600000,
             
             # --- TimeTagger ---
             start_channel: int = 5,
             click_channel: int = 1,
             binwidth_ns: int = 1000,
             n_bins: int = 1000,
             detector_delay_ns: int = 100, # as measured on the TimeTagger
             integration_time: float = 1,   # time for accumulations of pulse sequences
             event_divider: int = 1,  # Reduce the number of events counted
             ):
         """
         Pulsed Rabi oscillation experiment using AWG + TimeTagger.        
         Signal      = init + MW + readout
         Background  = init + readout (no MW)

         Stored data:
             x-axis → MW pulse length (ns)
             y-axis → Integrated photon counts
         """

         with MyInstrumentManager() as mgr, DataSource(dataset) as data:
             
             tt20 = mgr.tt20
             ps82 = mgr.ps82
                         
             # ------------------------------------------------
             # Streaming datasets
             # ------------------------------------------------
             hist_sweeps = StreamingList()
             
             # Time axis in ns for plotting (FORCE LOCAL ARRAY)
             time_axis = np.asarray(
                 np.arange(n_bins) * binwidth_ns * 1e-3,
                 dtype=float)
             
             # --------------------------------
             # Pulse timing
             # --------------------------------
             ps82.channel_sequences = {}  # Clear previous
                    
             # --------------------------------
             # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
             # --------------------------------
             laser_seq = [(init_ns,1),(mw_gap_ns_1,0),(mw_ns,0),
                                 (mw_gap_ns_2,0),(readout_ns,1),(recovery_ns,0)]
             mw_seq = [(init_ns,0),(mw_gap_ns_1,0),(mw_ns,1),
                              (mw_gap_ns_2,0),(readout_ns,0),(recovery_ns,0)]
             trig_seq = [(100, 1),(init_ns + mw_gap_ns_1 + mw_ns + mw_gap_ns_2 + 
                                   readout_ns + recovery_ns - 100, 0)]

             ps82.allocate_sequence(mw_seq, 0)
             ps82.allocate_sequence(laser_seq, 1)
             ps82.allocate_sequence(trig_seq, 2)

             ps82.begin_pulses(n_runs=-1)    
             
             time.sleep(0.1)
             
             # ------------------------------------------------
             # Measurement loop
             # ------------------------------------------------
             for i in range(iterations):
                 
                 t, counts = tt20.run_histogram(
                     click_channel=1,     # detector
                     start_channel=2,     # AWG trigger / sync
                     binwidth_ps=binwidth_ns * 1e3,
                     n_bins=n_bins,
                     capture_time_s=integration_time,
                     start_delay=0,
                     event_divider=event_divider,
                     )

                 counts = np.asarray(counts, dtype=float)
                
                 hist_sweeps.append(
                    np.stack((time_axis, counts), axis=0)
                    )
                 
                 hist_sweeps.updated_item(-1)
                 # ------------------------------------------------
                 # Push data
                 # ------------------------------------------------
                 data.push({
                     'params': {
                         'initialisation_pulse_width_ns': init_ns,
                         'readout_pulse_width_ns': readout_ns,
                         'binwidth_ps': binwidth_ns,
                         'n_bins': n_bins,
                         'iterations': iterations,
                         },
                     'title': 'ODMR Readout Optimisation',
                     'xlabel': 'Time / microseconds',
                     'ylabel': 'Counts',
                     'datasets': {
                         'histogram': hist_sweeps,
                         }
                     })
                     
                 if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                     ps82.stop()
                     return    


    def delay_after_flash_ps82(
             self,
             dataset: str,
             
             num_points: int,
             iterations: int,
             init_ns: int,
             readout_ns: int,
             
             delay_stop_ns: float,
             delay_start_ns: float = 100,
             recovery_ns: int = 550000,
             
             # --- TimeTagger ---
             start_channel: int = 5,
             click_channel: int = 1,
             binwidth_ns: int = 1000,
             n_bins: int = 1000,
             integration_time: float = 1,   # time for accumulations of pulse sequences
             detector_delay_ns: int = 100,
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

             ps82 = mgr.ps82
             tt = mgr.tt20
                         
             # --------------------------------
             # Sweep definition
             # --------------------------------
             delay_lengths_ns = np.linspace(delay_start_ns, delay_stop_ns, num_points)
             
             signal_sweeps = StreamingList()
             bkg_sweeps = StreamingList()
             
             for i in range(iterations):
                 
                 sig_counts = np.empty(num_points)
                 sig_counts[:] = np.nan
                 bkg_counts = np.empty(num_points)
                 bkg_counts[:] = np.nan
                 
                 # Append initial empty arrays to all StreamingLists
                 signal_sweeps.append(np.stack([delay_lengths_ns, sig_counts]))
                 bkg_sweeps.append(np.stack([delay_lengths_ns, bkg_counts]))
                 
                 detector_delay_s = detector_delay_ns * 1e-9
                 gate_delay_ps = int(round(detector_delay_s * 1e12))
            
                 for idx, gap_ns in enumerate(delay_lengths_ns):
                     
                     ps82.channel_sequences = {}  # Clear previous
                     
                     # --------------------------------
                     # Pulse timing - ps82 units is nanoseconds, but the TT is picoseconds
                     # --------------------------------
                     laser_seq = [(init_ns,1),(gap_ns,0),(200,0),(readout_ns,1),(recovery_ns - gap_ns,0)]
                     trig_seq = [(init_ns,0),(gap_ns,0),(200,1),(readout_ns,0),(recovery_ns  - gap_ns,0)]
                
                     ps82.allocate_sequence(laser_seq, 1)
                     ps82.allocate_sequence(trig_seq, 2)
                
                     ps82.begin_pulses(n_runs=-1)              
                     
                     # --------------------------------
                     # Histogram → integrate
                     # --------------------------------
                     t, counts = tt.run_histogram(
                         click_channel=click_channel,
                         start_channel=start_channel,
                         binwidth_ps=binwidth_ns * 1e3,
                         n_bins=n_bins,
                         capture_time_s=integration_time,
                         start_delay=gate_delay_ps,
                         )
                     
                     sig_counts[idx] = counts.sum()
                     
                     bkg_seq = [(200,0),(readout_ns,1),(recovery_ns  - gap_ns,0)]
                     trig_seq = [(200,1),(readout_ns,0),(recovery_ns  - gap_ns,0)]
                
                     ps82.allocate_sequence(bkg_seq, 1)
                     ps82.allocate_sequence(trig_seq, 2)
                     
                     ps82.begin_pulses(n_runs=-1)
                     
                     t, counts = tt.run_histogram(
                         click_channel=click_channel,
                         start_channel=start_channel,
                         binwidth_ps=binwidth_ns * 1e3,
                         n_bins=n_bins,
                         capture_time_s=integration_time,
                         start_delay=gate_delay_ps,
                         )
                     
                     bkg_counts[idx] = counts.sum()
                     
                     # --------------------------------
                     # Streaming updates
                     # --------------------------------
                     signal_sweeps[-1] = np.stack([delay_lengths_ns, sig_counts])
                     bkg_sweeps[-1] = np.stack([delay_lengths_ns, bkg_counts])
                     
                     signal_sweeps.updated_item(-1)
                     bkg_sweeps.updated_item(-1)
                     
                     data.push({
                         "title": "Delay After Flash",
                         "xlabel": "Init–Readout Delay / ns",
                         "ylabel": "Integrated Counts",
                         "datasets": {
                             "signal": signal_sweeps,
                             "background": bkg_sweeps}})           
                     
                     if experiment_widget_process_queue(self.queue_to_exp) == "stop":
                        ps82.stop()
                        return 


if __name__ == '__main__':
    exp = SpinMeasurements()
    exp.odmr_sweep_random('odmr', 1e9, 4e9, 101, 10)
