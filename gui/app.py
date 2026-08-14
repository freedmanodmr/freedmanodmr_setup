#!/usr/bin/env python
"""
This is an example script that demonstrates the basic functionality of nspyre.
"""
import logging
from pathlib import Path

import nspyre.gui.widgets.save
import nspyre.gui.widgets.load
import nspyre.gui.widgets.flex_line_plot
import nspyre.gui.widgets.subsystem
from nspyre import MainWidget
from nspyre import MainWidgetItem
from nspyre import nspyre_init_logger
from nspyre import nspyreApp

# in order for dynamic reloading of code to work, you must pass the specifc
# module containing your class to MainWidgetItem, since the python reload()
# function does not recursively reload modules
import template.gui.elements
from template.drivers.insmgr import MyInstrumentManager

_HERE = Path(__file__).parent

def main():
    # Log to the console as well as a file inside the logs folder.
    nspyre_init_logger(
        log_level=logging.INFO,
        log_path=_HERE / '../logs',
        log_path_level=logging.DEBUG,
        prefix=Path(__file__).stem,
        file_size=10_000_000,
    )

    with MyInstrumentManager() as insmgr:
        # Create Qt application and apply nspyre visual settings.
        app = nspyreApp()

        # Create the GUI.
        main_widget = MainWidget(
            {
                'Direct-Detection Experiments':{
                    'APD Pulsed-ODMR': MainWidgetItem(template.gui.elements, 'APD_Pulsed_ODMRWidget', stretch=(1, 1)),
                    'Rabi': MainWidgetItem(template.gui.elements, 'RabiWidget', stretch=(1, 1)),
                    'EDFS': MainWidgetItem(template.gui.elements, 'EDFSWidget', stretch=(1, 1)),
                    'Delay After Flash': MainWidgetItem(template.gui.elements, 'DAFWidget_PS82', stretch=(1, 1)),
                    'Ramsey': MainWidgetItem(template.gui.elements, 'RamseyWidget', stretch=(1, 1)),
                    'HahnEcho': MainWidgetItem(template.gui.elements, 'HahnEchoWidget', stretch=(1, 1)),
                    'Initialisation Opt': MainWidgetItem(template.gui.elements, 'InitialisationPS82Widget', stretch=(1, 1)),
                    'Readout Pulse Observation': MainWidgetItem(template.gui.elements, 'ReadoutWidget', stretch=(1, 1)),
                    'Readout Delay Opt': MainWidgetItem(template.gui.elements, 'ReadoutDelayWidget', stretch=(1, 1)),
                    'MW Delay Opt': MainWidgetItem(template.gui.elements, 'MWDelayWidget', stretch=(1, 1)),
                },
                'Lock-in Experiments':{
                    'CW-ODMR': MainWidgetItem(template.gui.elements, 'CWODMRWidget', stretch=(1, 1)),
                    'Pulse-ODMR Lock-in': MainWidgetItem(template.gui.elements, 'Pulse_ODMRWidgetLockin', stretch=(1, 1)),
                    'Rabi Lock-in': MainWidgetItem(template.gui.elements, 'RabiWidgetLockin', stretch=(1, 1)),
                    'Hahn-Echo Lock-in': MainWidgetItem(template.gui.elements, 'HahnEchoLockinWidget', stretch=(1, 1)),
                    'Ramsey Lock-in': MainWidgetItem(template.gui.elements, 'RamseyLockinWidget', stretch=(1, 1)),
                    'T1 Relaxation Lock-in': MainWidgetItem(template.gui.elements, 'T1RelaxationLockinWidget', stretch=(1, 1)),
                    'Mod Freq CW': MainWidgetItem(template.gui.elements, 'ModODMRWidget', stretch=(1, 1)),
                    'Initialisation Opt Lock-in': MainWidgetItem(template.gui.elements, 'InitialisationOptLockinWidget', stretch=(1, 1)),
                    'Readout Pulse Opt Lock-in': MainWidgetItem(template.gui.elements, 'ReadoutPulseOptLockinWidget', stretch=(1, 1)),
                    'Readout Delay Opt Lock-in': MainWidgetItem(template.gui.elements, 'ReadoutPulseDelayOptLockinWidget', stretch=(1, 1)),
                    'MW Delay Opt Lock-in': MainWidgetItem(template.gui.elements, 'MicrowaveDelayLockinWidget', stretch=(1, 1)),
                    'Temp Peak Track Lock-in': MainWidgetItem(template.gui.elements, 'TempPeakTrackCWODMRWidget', stretch=(1, 1)),
                    'TwoPulse-ODMR Lock-in': MainWidgetItem(template.gui.elements, 'TwoPulse_ODMRWidgetLockin', stretch=(1, 1)),
                },
                'Ce Experiments':{
                    'CW-ODMR': MainWidgetItem(template.gui.elements, 'CeODMRWidget', stretch=(1, 1)),
                    'Pulsed-ODMR Lock-in': MainWidgetItem(template.gui.elements, 'CeODMRLockinWidget', stretch=(1, 1)),
                    'Initialisation': MainWidgetItem(template.gui.elements, 'CeInitialisationPS82Widget', stretch=(1, 1)),
                    #'Readout': MainWidgetItem(template.gui.elements, 'CeReadoutWidget', stretch=(1, 1)),
                    #'MW Delay': MainWidgetItem(template.gui.elements, 'CeMWDelayWidget', stretch=(1, 1)),
                    #'Rabi': MainWidgetItem(template.gui.elements, 'CeRabiWidget', stretch=(1, 1)),
                    #'EDFS': MainWidgetItem(template.gui.elements, 'CeEDFSWidget', stretch=(1, 1)),
                    #'Delay After Flash': MainWidgetItem(template.gui.elements, 'CeDAFWidget', stretch=(1, 1)),
                    #'Ramsey': MainWidgetItem(template.gui.elements, 'RamseyWidget', stretch=(1, 1)),
                    #'Relaxation': MainWidgetItem(template.gui.elements, 'CeRelaxationWidget', stretch=(1, 1)),
                    #'HahnEcho': MainWidgetItem(template.gui.elements, 'RelaxationWidget', stretch=(1, 1)),
                },
                'NIR Experiments':{
                    'APD CW-ODMR': MainWidgetItem(template.gui.elements, 'NIR_CW_ODMR_APD', stretch=(1, 1)),
                    'NIR_initialization': MainWidgetItem(template.gui.elements, 'NIR_initialisation_lockin', stretch=(1, 1)),
                    'PLE': MainWidgetItem(template.gui.elements, 'PLE_Widget', stretch=(1, 1)),
                    },
                'Subsystems': MainWidgetItem(nspyre.gui.widgets.subsystem, 'SubsystemsWidget', args=[insmgr.subs.subsystems], stretch=(1, 1)),
                'Plots': {
                    'ODMR': MainWidgetItem(
                        template.gui.elements,
                        'FlexLinePlotWidget',
                        stretch=(100, 100),
                    ),
                    'Signal vs. t': MainWidgetItem(
                        template.gui.elements,
                        'FluorescenceTimePlotWidget',
                        stretch=(100, 100),
                    ),
                    'Time Tagger Plots': MainWidgetItem(
                        template.gui.elements,
                        'InitialisationTimePlotWidget',
                        stretch=(100, 100),
                    ),
                    'Peak Tracking Plot': MainWidgetItem(
                        template.gui.elements,
                        'SpecificFlexLinePlotWidget',
                        stretch=(100, 100),
                    ),
                    '2D Plots': MainWidgetItem(
                        template.gui.elements,
                        '_3DColourPlotWidget',
                        stretch=(100, 100),
                    ),
                    'PLE': MainWidgetItem(
                        template.gui.elements,
                        'PLEPlotWidget',
                        stretch=(100, 100),
                    ),
                    'PLE Power': MainWidgetItem(
                        template.gui.elements,
                        'PLEPowerPlotWidget',
                        stretch=(100, 100),
                    ),
                },
                'Save': MainWidgetItem(nspyre.gui.widgets.save, 'SaveWidget', stretch=(1, 1)),
                'Load': MainWidgetItem(nspyre.gui.widgets.load, 'LoadWidget', stretch=(1, 1)),
            }
        )
        main_widget.show()

        # Run the GUI event loop.
        app.exec()


# if using the nspyre ProcessRunner, the main code must be guarded with if __name__ == '__main__':
# see https://docs.python.org/2/library/multiprocessing.html#windows
if __name__ == '__main__':
    main()
