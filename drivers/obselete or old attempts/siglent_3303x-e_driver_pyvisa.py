# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import pyvisa
import nspyre

class _SPD3303X_E:
    
# From here, we start to define functions related to the instrument
# The first function that is always used, __init__, is a fucntion that 
# will define the instrument 
    def __init__(self, address):
        resource_manager = pyvisa.ResourceManager()
        termination_character = '\n'
        self.instrument = resource_manager.open_resource(address, read_termination=termination_character)
        self.reset()
    
# A function to reset the powersupply every time the class is called. 
# This power source does not have a built in reset function.
    def reset(self):
        self.instrument.write('CH1:VOLTage 0')
        self.instrument.write('CH2:VOLTage 0')
        self.instrument.write('CH1:CURRent 0')
        self.instrument.write('CH2:CURRent 0')
        self.instrument.write('OUTput CH1,OFF')
        self.instrument.write('OUTput CH2,OFF')
    
# These are query functions to check the status of the instrument
    def IDN(self):
        return self.instrument.query('*IDN?')
    
    def status(self):
        return self.instrument.query('SYSTem:STATus?')
    
    def version(self):
        return self.instrument.query('SYSTem:VERSion?')
    
    def operating_channel(self):
        return self.instrument.query('INSTrument?')
    
    def ask_voltage(self, channel):
        return self.instrument.query('CH{}:VOLTage?'.format(channel))
    
    def ask_current(self, channel):
        return self.instrument.query('CH{}:Current?'.format(channel))


# Write functions to control the power supply
            
    def set_channel(self, channel):
        self.instrument.write('INSTrument CH{}'.format(channel))
        
# evolution of commands, from one entry per function to a generalisable function 
# capable of setting the channel and voltage        
#    def set_voltage_CH1_old(self, voltage):
#        self.instrument.write('CH1:VOLTage 1')    
        
#    def set_voltage_CH1(self, voltage):
#        self.instrument.write('CH1:VOLTage {}'.format(voltage))

# Set limit on set_voltage to avoid damage to instruments/amplifiers
    def set_voltage(self, channel, voltage):
        self.instrument.write('CH{}:VOLTage {}'.format(channel, voltage))
        if voltage > 5:
            self.instrument.write('CH{}:VOLTage 0'.format(channel))
            raise ValueError('Error: set voltage cannot exceed 5')

# Set limit on set_current to avoid damage to instrument/amplifiers
    def set_current(self, channel, current):
        self.instrument.write('CH{}:CURRent {}'.format(channel, current))
        if current > 0.5:
            self.instrument.write('CH{}:CURRENT 0'.format(channel))
            raise ValueError('Error: set current cannot exceed 0.5')

# Add the power supply
PowerSupply_Sig = _SPD3303X_E('USB0::0xF4EC::0x1430::SPD3XJGC901346::INSTR')
# PowerSupply_Sig.VOLTage()


# Add the Arbitary Wave Generator
# ArbGen_Sig = rm.open_resource('USB0::0xF4EC::0x1102::SDG2XFBC900189::INSTR')


# Add the Oscilloscope
# Oscilloscope_Rigol = rm.open_resource('USB0::0x1AB1::0x04CE::DS1ZA26AM00587::INSTR')

# Add the Signal Generator
# I would, but I need a RS-232 cable, which has been ordered.
