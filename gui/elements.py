"""
Example GUI elements.
"""
import numpy as np

from nspyre import FlexLinePlotWidget
from nspyre.gui.widgets.heatmap import HeatMapWidget

from nspyre import ExperimentWidget
from nspyre import DataSink
from pyqtgraph import SpinBox
from pyqtgraph.Qt import QtWidgets

import template.experiments.odmr_direct
import template.experiments.odmr_lockin

#------------------------------------------------------------------------------
# Lock-in Detection Method - Laser and microwaves are modulated via the AWG/PS82. 
#                            The repeating frequency corresponds to the lock-in 
#                            frequency.
#------------------------------------------------------------------------------

class CWODMRWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.074e9),
                    dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.075e9),
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Scan Points',
                'widget': SpinBox(value=101, int=True, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=0.1, suffix='s',
                siPrefix=True, bounds=(0.001, 10), dec=True),
            },
            'modulation_freq': {
                'display_text': 'Lock-in Mod Frequency',
                'widget': SpinBox(value=2000, suffix='Hz',
                siPrefix=True, bounds=(0, 4e6), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmr'),
            },
        }
        super().__init__(params_config, 
                        template.experiments.odmr_lockin,
                        'SpinMeasurements',
                        'cw_odmr_sweep_linear_ps82',
                        title='ODMR')


class MicrowaveDelayLockinWidget(ExperimentWidget):
    """
    GUI widget to run Rabi Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'delay_start_ns': {
                'display_text': 'Min Microwave Pulse Delay',
                'widget': SpinBox(
                    value=0,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'delay_stop_ns': {
                'display_text': 'Max Microwave Pulse Delay',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=30000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=60000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('mw_delay'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'microwave_delay_opt_lockin',
            title='Microwave Delay Optimisation')  


class InitialisationOptLockinWidget(ExperimentWidget):
    """
    GUI widget to optimise the initialisation pulse width 
    by measuring the contrast with a changing pulse width.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'init_start_ns': {
                'display_text': 'Min Initialisation Pulse Length',
                'widget': SpinBox(
                    value=0,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'init_stop_ns': {
                'display_text': 'Max Initialisation Pulse Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=30000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=60000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('init_opt'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'initialisation_opt_lockin',
            title='Initialisation Pulse Optimisation')  


class ReadoutPulseOptLockinWidget(ExperimentWidget):
    """
    GUI widget to run Readout Pulse Length optimisation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'readout_start_ns': {
                'display_text': 'Min Readout Pulse Length',
                'widget': SpinBox(
                    value=0,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'readout_stop_ns': {
                'display_text': 'Max Readout Pulse Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=60000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('readout_pulse_delay'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'readout_opt_lockin',
            title='Readout Pulse Optimisation')


class ReadoutPulseDelayOptLockinWidget(ExperimentWidget):
    """
    GUI widget to run Rabi Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'delay_start_ns': {
                'display_text': 'Min Readout Delay',
                'widget': SpinBox(
                    value=0,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'delay_stop_ns': {
                'display_text': 'Max Readout Delay',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=60000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('readout_delay'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'readout_delay_opt_lockin',
            title='Readout Pulse Delay Optimisation')


class RabiWidgetLockin(ExperimentWidget):
    """
    GUI widget to run Rabi Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'pulse_start_ns': {
                'display_text': 'Min Microwave Pulse Length',
                'widget': SpinBox(
                    value=0,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'pulse_stop_ns': {
                'display_text': 'Max Microwave Pulse Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=30000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=60000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('rabi'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'rabi_oscillations_lockin',
            title='Rabi Oscillations')


class Pulse_ODMRWidgetLockin(ExperimentWidget):
    """
    GUI widget to run Pulsed-detection ODMR experiment.
    """
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.074e9),
                    dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.075e9),
                    dec=True),
            },
            'pulse_length_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Recovery Time',
                'widget': SpinBox(value=6e5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('odmr'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'pulsed_odmr_sweep_linear_lockin',
            title='Pulsed-ODMR_PMT')        
        
        
class HahnEchoLockinWidget(ExperimentWidget):
    """
    GUI widget to run Hahn Echo experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'tau_start_ns': {
                'display_text': 'Min tau Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'tau_stop_ns': {
                'display_text': 'Max tau Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=0.5, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=6000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to Microwave Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'pi': {
                'display_text': 'Pi Pulse Width',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'Microwave to Readout Gap',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Relaxation Time',
                'widget': SpinBox(value=600000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('hahnecho'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'hahn_echo_lockin',
            title='Hahn Echo Spectroscopy')
        
        
class RamseyLockinWidget(ExperimentWidget):
    """
    GUI widget to run Hahn Echo experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'tau_start_ns': {
                'display_text': 'Min tau Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'tau_stop_ns': {
                'display_text': 'Max tau Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=0.5, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=6000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to Microwave Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'pi': {
                'display_text': 'Pi Pulse Width',
                'widget': SpinBox(value=570, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'Microwave to Readout Gap',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Relaxation Time',
                'widget': SpinBox(value=600000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('ramsey'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_lockin,
            'SpinMeasurements',
            'ramsey_lockin',
            title='Ramsey Spectroscopy')
        

#------------------------------------------------------------------------------
# Direct Detection Methods - Laser and microwaves are modulated via the AWG/PS82. 
#                            The data is recorded using APD on the TimeTagger
#------------------------------------------------------------------------------ 
        
class InitialisationAWGWidget(ExperimentWidget):
    """
    GUI widget to run the Initialization Time experiment.
    Note: The modulation_freq parameter is required for the "Pulsed" AWG mode. 
    If using PulseStreamer8/2, switch to the correspond method
    """
    def __init__(self):
        params_config = {
            'pulse_width': {
                'display_text': 'Laser Pulse Width',
                'widget': SpinBox(
                    value=1e3,
                    suffix='ns',
                    siPrefix=False,
                    bounds=(310, None),
                    dec=True),
            },
            'modulation_freq': {
                'display_text': 'Repetition Rate',
                'widget': SpinBox(value=100, suffix='Hz',
                siPrefix=True, bounds=(1, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(1, None), dec=True)
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Integration Time',
                'widget': SpinBox(value=1, int=True, 
                                  bounds=(0.1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('init'),
            },
        }
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'odmr_initialization_measurement',
            title='Initialization_Time')
        

class InitialisationPS82Widget(ExperimentWidget):
    """
    GUI widget to run the Initialization Time experiment.
    Note: The modulation_freq parameter is required for the "Pulsed" AWG mode. 
    If using PulseStreamer8/2, switch to the correspond method
    """
    def __init__(self):
        params_config = {
            'init_ns': {
                'display_text': 'Laser Pulse Width',
                'widget': SpinBox(
                    value=1e3,
                    suffix='ns',
                    siPrefix=False,
                    bounds=(50, None),
                    dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Cycling Time',
                'widget': SpinBox(value=1e6, suffix='ns',
                    siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=0.001, suffix='ns',
                siPrefix=False, bounds=(0.001, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(1, None), dec=True)
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Integration Time',
                'widget': SpinBox(value=1, int=True, 
                                  bounds=(0.1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('init'),
            },
        }
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'odmr_initialisation_optimisation_ps82',
            title='Initialization_Time')


class ReadoutWidget(ExperimentWidget):
    """
    GUI widget to run a read-out optimisation experiment. The goal is to 
    adjust the detector delay until the beginning of the initialisation pulse
    """
    def __init__(self):
        params_config = {
            'init_ns': {
                'display_text': 'Initialisation Pulse Length',
                'widget': SpinBox(
                    value=6000,
                    suffix='ns',
                    bounds=(320, 100000),
                    int=True,
                    dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Length',
                'widget': SpinBox(
                    value=500,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'mw_gap_ns': {
                'display_text': 'Time Gap',
                'widget': SpinBox(
                    value=50,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(
                    value=500,
                    suffix='ns',
                    bounds=(50, None),
                    int=True,
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'readout_delay_ns': {
                'display_text': 'Detector Delay',
                'widget': SpinBox(value=0, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=500, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'event_divider': {
                'display_text': 'Event Divider',
                'widget': SpinBox(value=1, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('readout'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'odmr_readout_optimisation',
            title='Readout Optimisation')


class ReadoutDelayWidget(ExperimentWidget):
    """
    GUI widget to run Rabi Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'readout_delay_start_ns': {
                'display_text': 'Minimum Readout Delay',
                'widget': SpinBox(
                    value=20,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'readout_delay_stop_ns': {
                'display_text': 'Maximum Readout Delay',
                'widget': SpinBox(
                    value=20000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=50,
                    suffix='',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Length',
                'widget': SpinBox(
                    value=2500,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Length',
                'widget': SpinBox(
                    value=500,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to Microwave Gap',
                'widget': SpinBox(
                    value=50,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(
                    value=100,
                    suffix='ns',
                    bounds=(50, 5000),
                    int=True,
                    dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'Microwave to Readout Gap',
                'widget': SpinBox(value=500, suffix='ns',
                    bounds=(0, None), int=True, dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Recycling Time',
                'widget': SpinBox(value=500000, suffix='s',
                siPrefix=True, bounds=(0, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=10, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=50, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'detector_delay_ns': {
                'display_text': 'Detector Delay',
                'widget': SpinBox(value=1000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('delay'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'optimize_readout_delay',
            title='Microwave Delay Optimisation')
               
        
class MWDelayWidget(ExperimentWidget):
    """
    GUI widget to optimise the position of a PI pulse.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'mw_delay_start_ns': {
                'display_text': 'Minimum MW Delay',
                'widget': SpinBox(
                    value=20,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'mw_delay_stop_ns': {
                'display_text': 'Maximum MW Delay',
                'widget': SpinBox(
                    value=20000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=50,
                    suffix='',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Length',
                'widget': SpinBox(
                    value=6000,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Length',
                'widget': SpinBox(
                    value=500,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'mw_gap_ns': {
                'display_text': 'Time Gap',
                'widget': SpinBox(
                    value=50,
                    suffix='ns',
                    bounds=(10, 20000),
                    int=True,
                    dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(
                    value=100,
                    suffix='ns',
                    int=True,
                    bounds=(50, 5000),
                    dec=True),
            },
            'readout_gap_ns': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'detector_delay_ns': {
                'display_text': 'Detector Delay',
                'widget': SpinBox(value=1000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=10, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=50, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Accumulation Time',
                'widget': SpinBox(value=1, int=True, 
                                  bounds=(0.1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('delay'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'optimize_mw_delay',
            title='Microwave Delay Optimisation')


class RabiWidget(ExperimentWidget):
    """
    GUI widget to run Rabi Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'pulse_start_ns': {
                'display_text': 'Min Microwave Pulse Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(0, None),
                    int=True,
                    dec=True),
            },
            'pulse_stop_ns': {
                'display_text': 'Max Microwave Pulse Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=30000, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=600000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0.1, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=10, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('rabi'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'rabi_oscillations_ps82',
            title='Rabi Oscillations')

                
class APD_CW_ODMRWidget(ExperimentWidget):
    """
    GUI widget to run APD ODMR experiment.
    """
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.074e9),
                    dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.075e9),
                    dec=True),
            },
            
            'pulse_length_ns': {
                'display_text': 'Microwave Pulse Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=6e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Spin Relaxation Time',
                'widget': SpinBox(value=30e6, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0.1, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=10, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('odmr'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'odmr_sweep_linear_timetagger_ps82',
            title='APD_CW_ODMR')        


class EDFSWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(value=3e9, suffix='Hz', siPrefix=True, 
                                  bounds=(1e3, 6.074e9), dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(value=4e9, suffix='Hz', siPrefix=True, 
                                  bounds=(1e3, 6.075e9), dec=True),
            },
            'num_points': {
                'display_text': 'Number of Scan Points',
                'widget': SpinBox(value=101, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1.0, suffix='s',
                siPrefix=True, bounds=(0.001, 10), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Length',
                'widget': SpinBox(value=2500, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Length',
                'widget': SpinBox(value=1000, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'mw_ns': {
                'display_text': 'Pi-Pulse Length',
                'widget': SpinBox(value=200, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'gap_before_mw_ns': {
                'display_text': 'Initialisation to MW Delay',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'gap_after_mw_ns': {
                'display_text': 'MW to Readout Delay',
                'widget': SpinBox(value=1000, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=10, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'rf_amp': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('edfs'),
            }}
        super().__init__(params_config, 
                        template.experiments.odmr_direct,
                        'SpinMeasurements',
                        'spin_echo_detected_freq_sweep',
                        title='ODMR')
    

class RamseyWidget(ExperimentWidget):
    """
    GUI widget to run Ramsey Oscillation experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'mw_pulse_ns': {
                'display_text': 'Pi/2 Pulse Width',
                'widget': SpinBox(value=90,
                    suffix='ns',
                    siPrefix=True,
                    bounds=(10, None),
                    dec=True),
            },
            'ramsey_start_ns': {
                'display_text': 'Min tau Length',
                'widget': SpinBox(value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'ramsey_stop_ns': {
                'display_text': 'Max tau Length',
                'widget': SpinBox(value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(value=51, int=True, bounds=(5, 2000), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=10, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('ramsey'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'ramsey_oscillations',
            title='Ramsey Oscillations')
        

class HahnEchoWidget(ExperimentWidget):
    """
    GUI widget to run Hahn Echo experiment.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'mw_pi2_ns': {
                'display_text': 'Pi/2 Pulse Width',
                'widget': SpinBox(
                    value=90,
                    suffix='ns',
                    siPrefix=True,
                    bounds=(10, None),
                    dec=True),
            },
            'ramsey_start_ns': {
                'display_text': 'Min tau Length',
                'widget': SpinBox(
                    value=10,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'ramsey_stop_ns': {
                'display_text': 'Max tau Length',
                'widget': SpinBox(
                    value=2000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=51,
                    int=True,
                    bounds=(5, 2000),
                    dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=500, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=10, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('hahnecho'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'hahn_echo',
            title='Hahn Echo Spectroscopy')
        

class DAFWidget_AWG(ExperimentWidget):
    """
    GUI widget to run Delay After Flash experiment.
    """
    def __init__(self):
        params_config = {
            'stop_ns': {
                'display_text': 'Measurement Time',
                'widget': SpinBox(value=100000, suffix='ns',
                    siPrefix=True, int=True, dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(value=101, int=True,
                    bounds=(5, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=1.5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },           
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=30, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('daf'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'delay_after_flash_awg',
            title='Delay After Flash')


class DAFWidget_PS82(ExperimentWidget):
    """
    GUI widget to run Delay After Flash experiment.
    """
    def __init__(self):
        params_config = {
            'delay_stop_ns': {
                'display_text': 'Measurement Time',
                'widget': SpinBox(value=100000, suffix='ns',
                    siPrefix=True, int=True, dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(value=101, int=True,
                    bounds=(5, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=1, suffix='s',
                siPrefix=True, bounds=(0.001, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=1.5e3, suffix='ns',
                siPrefix=False, bounds=(100, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Cycling Time',
                'widget': SpinBox(value=6e5, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },            
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=30, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('daf'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'delay_after_flash_ps82',
            title='Delay After Flash')


#-----------------------------------------------------------------------------
# 2D Experiments
#-----------------------------------------------------------------------------
class _2DPulseLengthMWDelayWidget(ExperimentWidget):
    """
    GUI widget to optimise the position of a PI pulse.
    """
    def __init__(self):
        params_config = {
            'freq_hz': {
                'display_text': 'MW Frequency',
                'widget': SpinBox(
                    value=2.87e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6e9),
                    dec=True),
            },
            'mw_delay_start_ns': {
                'display_text': 'Minimum MW Delay',
                'widget': SpinBox(
                    value=20,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'mw_delay_stop_ns': {
                'display_text': 'Maximum MW Delay',
                'widget': SpinBox(
                    value=20000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'pulse_start_ns': {
                'display_text': 'Minimum Pulse Length',
                'widget': SpinBox(
                    value=20,
                    suffix='ns',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'pulsey_stop_ns': {
                'display_text': 'Maximum Pulse Length',
                'widget': SpinBox(
                    value=20000,
                    suffix='ns',
                    bounds=(10, None),
                    int=True,
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Points',
                'widget': SpinBox(
                    value=50,
                    suffix='',
                    bounds=(1, None),
                    int=True,
                    dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Length',
                'widget': SpinBox(
                    value=6000,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Length',
                'widget': SpinBox(
                    value=500,
                    suffix='ns',
                    bounds=(320, 10000),
                    int=True,
                    dec=True),
            },
            'mw_gap_ns': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(
                    value=50,
                    suffix='ns',
                    bounds=(10, 20000),
                    int=True,
                    dec=True),
            },
            'readout_gap_ns': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=50000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'detector_delay_ns': {
                'display_text': 'Detector Delay',
                'widget': SpinBox(value=1000, suffix='ns',
                siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=10, suffix='ns',
                siPrefix=False, bounds=(10, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=50, suffix='',
                siPrefix=False, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Accumulation Time',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Dataset',
                'widget': QtWidgets.QLineEdit('3DPlotData'),
            }}
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'rabi_vs_mw_delay',
            title='Microwave Delay Optimisation')    
    
#-----------------------------------------------------------------------------
# ODMR Data Processing and Plotting 
#-----------------------------------------------------------------------------
def process_ODMR_data(sink: DataSink):
    """Subtract the signal from background trace and add it as a new 'diff' dataset."""
    diff_sweeps = []
    contrast_sweeps = []
    # 🔑 Bail out cleanly if this experiment doesn't use signal/background
    if 'signal' not in sink.datasets or 'background' not in sink.datasets:
        return
    for s,_ in enumerate(sink.datasets['signal']):
        freqs = sink.datasets['signal'][s][0]
        sig = sink.datasets['signal'][s][1]
        bg = sink.datasets['background'][s][1]
        diff_sweeps.append(np.stack([freqs, sig - bg]))
        contrast_sweeps.append(np.stack([freqs, ((sig - bg) / bg)]))
    sink.datasets['diff'] = diff_sweeps
    sink.datasets['contrast'] = contrast_sweeps
    print('x-axis values:', freqs, 'y-axis values, first signal:', sig, '... and then bkg:', bg)
    

def process_2D_ODMR_data(sink: DataSink):
    """Process 2D ODMR data: signal - background and contrast."""
    if 'signal' not in sink.datasets or 'background' not in sink.datasets:
        return
    diff_sweeps = []
    contrast_sweeps = []
    for s in range(len(sink.datasets['signal'])):
        pulse_lengths, delays, sig_2d = sink.datasets['signal'][s]
        _, _, bg_2d = sink.datasets['background'][s]

        diff_2d = sig_2d - bg_2d
        contrast_2d = diff_2d / bg_2d

        diff_sweeps.append((
            pulse_lengths,
            delays,
            diff_2d
        ))
        contrast_sweeps.append((
            pulse_lengths,
            delays,
            contrast_2d
        ))
    sink.datasets['diff'] = diff_sweeps
    sink.datasets['contrast'] = contrast_sweeps
    print(
        'Processed 2D ODMR data:',
        f'pulse_lengths={pulse_lengths.shape},',
        f'delays={delays.shape},',
        f'signal shape={sig_2d.shape}')


class FlexLinePlotWidget(FlexLinePlotWidget):
    """Add some default settings to the FlexSinkLinePlotWidget."""
    def __init__(self):
        super().__init__(data_processing_func=process_ODMR_data)
        # create some default signal plots
        self.add_plot('sig_avg',        series='signal',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('sig_latest',     series='signal',   scan_i='-1',   scan_j='',  processing='Average')
        self.add_plot('sig_first',      series='signal',   scan_i='0',    scan_j='1', processing='Average')
   #     self.add_plot('sig_latest_10',  series='signal',   scan_i='-10',  scan_j='',  processing='Average')
        self.hide_plot('sig_first')
        self.hide_plot('sig_latest')
   #     self.hide_plot('sig_latest_10')

        # create some default background plots
        self.add_plot('bg_avg',         series='background',   scan_i='',     scan_j='',  processing='Average')
        self.add_plot('bg_latest',      series='background',   scan_i='-1',   scan_j='',  processing='Average')
        self.hide_plot('bg_latest')

        # create some default diff plots
        self.add_plot('diff_avg',       series='diff',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('diff_latest',    series='diff',  scan_i='-1',    scan_j='',  processing='Average')
        self.add_plot('diff_latest_10',    series='diff',  scan_i='-1',    scan_j='',  processing='Average')
        self.hide_plot('diff_latest_10')
        self.hide_plot('diff_latest')
        
        # create some default contrast plots
        self.add_plot('contrast_avg',       series='contrast',  scan_i='',      scan_j='',  processing='Average')
        self.add_plot('contrast_latest',    series='contrast',  scan_i='-1',    scan_j='',  processing='Average')
        self.add_plot('contrast_latest_10',    series='contrast',  scan_i='-1',    scan_j='',  processing='Average')
        self.hide_plot('contrast_latest_10')
        self.hide_plot('contrast_latest')
        self.hide_plot('contrast_avg')
        
        # manually set the XY range
        self.line_plot.plot_item().setXRange(1.0, 4.0)
        self.line_plot.plot_item().setYRange(-0.0001, 0.0001)

        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))

        self.datasource_lineedit.setText('odmr')


class FluorescenceTimePlotWidget(FlexLinePlotWidget):
    """Plot fluorescence vs time."""
    def __init__(self):
        super().__init__()

        # Make sure this plot listens to the right dataset
        self.datasource_lineedit.setText('odmr')
        self.hide_plot('sig_avg')
        self.hide_plot('bg_avg')
        self.hide_plot('diff_avg')
        self.hide_plot('contrast_avg')

        # Add the fluorescence plot
        # create some default signal plots
        self.add_plot('fluorescence',        series='time_spent',   scan_i='',     scan_j='',  processing='Append')

        # Set axis ranges & labels appropriate for time-domain data
        self.line_plot.plot_item().setXRange(0.0, 10.0)  # adjust for your measurement
        self.line_plot.plot_item().setYRange(-0.0001, 0.0001)


class InitialisationTimePlotWidget(FlexLinePlotWidget):
    """Plot fluorescence vs time."""
    def __init__(self):
        super().__init__()
        # Make sure this plot listens to the right dataset
        self.datasource_lineedit.setText('init')
        self.hide_plot('sig_avg')
        self.hide_plot('bg_avg')
        self.hide_plot('diff_avg')
        self.hide_plot('contrast_avg')

        # Add the fluorescence plot
        # create some default signal plots
        self.add_plot('Initialisation',        series='histogram',   scan_i='',     scan_j='',  processing='Average')

        # Set axis ranges & labels appropriate for time-domain data
        self.line_plot.plot_item().setXRange(0.0, 10.0)  # adjust for your measurement
        self.line_plot.plot_item().setYRange(-0.0001, 0.0001)
        
        # retrieve legend object
        legend = self.line_plot.plot_widget.addLegend()
        # set the legend location
        legend.setOffset((-10, -50))
        
        
class _3DColourPlotWidget(HeatMapWidget):
    """Plot fluorescence vs delay vs microwave pulse length."""

    def __init__(self):
        super().__init__()

        # Dataset name this widget listens to
        self.set_data('x','y','3DPlotData','z')

        # Axis labels (these are for the image axes)
        self.plot_item.setLabel('bottom', 'Microwave Pulse Length (ns)')
        self.plot_item.setLabel('left', 'Delay τ (ns)')

        # Optional: set fixed color scaling (otherwise autoscale)
        # self.image_item.setLevels((0.0, 1.0))
        

#--------------------------------------------------------
#   Ce Experiments
#--------------------------------------------------------

class CeODMRWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.074e9),
                    dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.075e9),
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Scan Points',
                'widget': SpinBox(value=101, int=True, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=0.1, suffix='s',
                siPrefix=True, bounds=(0.001, 10), dec=True),
            },
            'laser_on_ns': {
                'display_text': 'Laser Pulse Width',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'laser_off_ns': {
                'display_text': 'Gap Between Laser Pulses',
                'widget': SpinBox(value=200, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'mw_period_ns': {
                'display_text': 'Microwave Pulse Period (for lock-in)',
                'widget': SpinBox(value=5e5, suffix='ns',
                siPrefix=False, bounds=(0, 1e9), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmr'),
            }}
        super().__init__(params_config, 
                        template.experiments.odmr_lockin,
                        'SpinMeasurements',
                        'ce_odmr_cw_lockin',
                        title='ODMR')


class CeODMRLockinWidget(ExperimentWidget):
    def __init__(self):
        params_config = {
            'start_freq': {
                'display_text': 'Start Frequency',
                'widget': SpinBox(
                    value=3e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.074e9),
                    dec=True),
            },
            'stop_freq': {
                'display_text': 'Stop Frequency',
                'widget': SpinBox(
                    value=4e9,
                    suffix='Hz',
                    siPrefix=True,
                    bounds=(1e3, 6.075e9),
                    dec=True),
            },
            'num_points': {
                'display_text': 'Number of Scan Points',
                'widget': SpinBox(value=101, int=True, bounds=(1, None), dec=True),
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Averaging Time',
                'widget': SpinBox(value=0.1, suffix='s',
                siPrefix=True, bounds=(0.001, 10), dec=True),
            },
            'init_ns': {
                'display_text': 'Initialisation Pulse Width',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'init_gap_ns': {
                'display_text': 'Initialisation Pulse Gap',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'num_init_pulses': {
                'display_text': 'Number of Initialisation Pulses',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'mw_gap_ns_1': {
                'display_text': 'Initialisation to MW Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'mw_ns': {
                'display_text': 'Microwave Pulse length',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'mw_gap_ns_2': {
                'display_text': 'MW to Readout Gap',
                'widget': SpinBox(value=50, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'readout_ns': {
                'display_text': 'Readout Pulse Width',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'num_readout_pulses': {
                'display_text': 'Number of Readout Pulses',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Relaxation Time',
                'widget': SpinBox(value=100, suffix='ns',
                siPrefix=False, bounds=(0, 4e6), dec=True),
            },
            'rf_amplitude': {
                'display_text': 'Microwave Amplitude',
                'widget': SpinBox(value=7.4, suffix='dBm',
                siPrefix=True, bounds=(-20, 7.4), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('odmr'),
            }}
        super().__init__(params_config, 
                        template.experiments.odmr_lockin,
                        'SpinMeasurements',
                        'ce_odmr_pulsed_sweep_linear_lockin',
                        title='ODMR')


class CeInitialisationPS82Widget(ExperimentWidget):
    """
    GUI widget to run the Initialization Time experiment.
    Note: The modulation_freq parameter is required for the "Pulsed" AWG mode. 
    If using PulseStreamer8/2, switch to the correspond method
    """
    def __init__(self):
        params_config = {
            'init_ns': {
                'display_text': 'Laser Pulse Width',
                'widget': SpinBox(value=100, suffix='ns',
                    siPrefix=False, bounds=(50, None), dec=True)
            },
            'pulse_gap': {
                'display_text': 'Pulse Spacing',
                'widget': SpinBox(value=100, suffix='ns',
                    siPrefix=False, bounds=(0, None), dec=True),
            },
            'number_of_pulses': {
                'display_text': 'Number of Pulses',
                'widget': SpinBox(value=1000, suffix='',
                    siPrefix=False, bounds=(0, None), dec=True),
            },
            'recovery_ns': {
                'display_text': 'Optical Cycling Time',
                'widget': SpinBox(value=1e6, suffix='ns',
                    siPrefix=False, bounds=(0, None), dec=True),
            },
            'binwidth_ns': {
                'display_text': 'Bin Width',
                'widget': SpinBox(value=1, suffix='ns',
                siPrefix=False, bounds=(0.001, None), dec=True),
            },
            'n_bins': {
                'display_text': 'Number of Bins',
                'widget': SpinBox(value=100, suffix='',
                siPrefix=False, bounds=(1, None), dec=True)
            },
            'iterations': {
                'display_text': 'Iterations',
                'widget': SpinBox(value=10, int=True, 
                                  bounds=(1, None), dec=True),
            },
            'integration_time': {
                'display_text': 'Integration Time',
                'widget': SpinBox(value=1, int=True, 
                                  bounds=(0.1, None), dec=True),
            },
            'dataset': {
                'display_text': 'Data Set',
                'widget': QtWidgets.QLineEdit('init'),
            },
        }
        super().__init__(
            params_config,
            template.experiments.odmr_direct,
            'SpinMeasurements',
            'ce_odmr_initialisation_optimisation_ps82',
            title='Initialization_Time')

