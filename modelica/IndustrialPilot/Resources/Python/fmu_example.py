# -*- coding: utf-8 -*-
"""
Created on Wed Jun 11 07:08:43 2025

@author: remi
"""

import os
import numpy as np
import time

from pyfmi import load_fmu

fmu_path = r'C:\git\pbd-industrial\pilot\models\IndustrialPilot\Resources\Python\Plant_fmu.fmu'

final_time = 10000
start_time  = 0
ini = start_time
step = 600
int_time = 0
ncp = 1

while int_time < final_time:
    int_time = ini + step
    pumboi = 6
    pumhea = 6
    socset = 1
    if ini == 0:
        values = [[ini, pumboi, pumhea, socset]]
    else:
        values = np.vstack([values, [ini, pumboi, pumhea, socset]])
    
    input_object = (['pumboi', 'pumhea', 'socset'], np.array([[0, pumboi, pumhea, socset]]))
    model = load_fmu(fmu_path)
    res = model.simulate(start_time = start_time, final_time=int_time, input=input_object, options={'ncp': ncp})
    
    time_sim = res['time']
    cost = res['costtot']
    qprod = res['yqprod']
    
    ini = int_time
    ncp = ncp + 1
    
print(time_sim)
print(cost)
print(qprod)
print(int_time)
