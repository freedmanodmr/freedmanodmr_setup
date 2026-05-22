# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import numpy as np
import matplotlib.pyplot as plt

import qcodes as qc
import zhinst.qcodes as ziqc

mfli = ziqc.MFLI("dev6813", "127.0.0.1", interface="pcie")
