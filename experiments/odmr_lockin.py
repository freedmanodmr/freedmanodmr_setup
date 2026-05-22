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

    def cw_odmr_sweep_random(self,
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


    def cw_odmr_sweep_linear(self,
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


    def pulsed_odmr_sweep_linear_lockin(self,
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
