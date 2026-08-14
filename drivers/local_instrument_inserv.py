#!/usr/bin/env python
"""
Start up an instrument server to host drivers. For the purposes of this demo,
it's assumed that this is running on the same system that will run experimental
code.
"""
from pathlib import Path
import logging

from nspyre import InstrumentServer
# from nspyre import InstrumentGateway
from nspyre import nspyre_init_logger
from nspyre import serve_instrument_server_cli

_HERE = Path(__file__).parent

# log to the console as well as a file inside the logs folder
nspyre_init_logger(
    logging.INFO,
    log_path=_HERE / '../logs',
    log_path_level=logging.DEBUG,
    prefix='local_inserv',
    file_size=10_000_000)

""" 
NOTE: You can comment out the TimeTagger so that you can monitor the data on Swabian's software
"""

with InstrumentServer() as local_inserv, InstrumentServer(port=42067) as remote_gw:
    # -------------------------------------------------- #
    # Microwave equipment drivers
    # -------------------------------------------------- #
    local_inserv.add('subs', _HERE / 'subsystems_driver.py', 'SubsystemsDriver', args=[local_inserv, remote_gw], local_args=True)
    local_inserv.add('mfli', _HERE / 'working_MFLI_driver.py', '_MFLI', args=['DEV6813'], local_args=True)
    local_inserv.add('sg', _HERE / 'working_SG396_driver.py', '_SG396', args=['ASRL8::INSTR'], local_args=True)
    local_inserv.add('awg', _HERE / 'George_SDG2042X_driver.py', 'SDG2000X', args=['USB0::0xF4EC::0x1102::SDG2XFBC900189::INSTR'], local_args=True)
    local_inserv.add('hmc', _HERE / 'working_HMC-T2100_driver.py', '_HMCT2100', args=['ASRL12::INSTR'], local_args=True)
    
    # -------------------------------------------------- #
    #Powermeter, polarimeter etc. drivers
    # -------------------------------------------------- #
 #   local_inserv.add('pm',_HERE / 'working_PM100D_driver.py', 'PM100D', args=[
 #       r'C:\Program Files\IVI Foundation\VISA\Win64\Bin\TLPM_64.dll'],local_args=True)
   
    
    # local_inserv.add('scope_driver', _HERE / 'working_DS1054Z_driver.py', '_DS1000Z', args=['USB0::0x1AB1::0x04CE::DS1ZA26AM00587::INSTR'], local_args=True)   
   
  #  local_inserv.add('tt20', _HERE / 'working_TimeTagger20_driver.py', 'TimeTagger20', args=["2434001CEJ"], local_args=True)
    local_inserv.add('ps82', _HERE / 'working_PulseStreamer_driver.py', 'PulseStreamer82', args=['169.254.8.2'], local_args=True)
    
    # -------------------------------------------------- #
    # Optical equipment drivers
    # -------------------------------------------------- #
    local_inserv.add('laser',_HERE / 'sacher_laser_final.py', 'SacherLaserDriver', args=[
        r'C:\Users\ODMR_user\odmr_python_files\template\src\template\drivers\EposCMD64.dll',
        'USB1'], local_args=True)
   # local_inserv.add('laser', _HERE / 'pycobolt.py', 'CoboltLaser', args=["COM4"], local_args=True)
    
    # -------------------------------------------------- #
    # Coordination Python Scripts
    # -------------------------------------------------- #
    local_inserv.add('odmr_driver', _HERE / 'odmr_driver.py', '_odmr_driver', local_args=True) # contains higher-level functions
    
    # run a CLI (command-line interface) that allows the user to enter
    # commands to control the server
    serve_instrument_server_cli(local_inserv)
