# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 18:41:04 2024

@author: remi
"""

from fmpy import read_model_description, dump, extract, simulate_fmu, instantiate_fmu
from fmpy.simulation import apply_start_values
from fmpy.fmi2 import FMU2Slave, FMU2Model
import pandas as pd
import numpy as np
import time

fmu = r'C:\git\plant_hp_variable.fmu'
model_description = read_model_description(fmu)
unzipdir = extract(fmu)

vars_input = {}
for k in model_description.modelVariables: 
    if k.causality == 'input':
        vars_input[k.name] = k.valueReference

vars_output = {}
for k in model_description.modelVariables: 
    if k.causality == 'output':
        vars_output[k.name] = k.valueReference
        
delete = ['CPUtime', 'EventCounter']
for k in delete:
    if k in vars_output.keys():
        del vars_output[k]


result = FMU2Slave(guid=model_description.guid,
                    unzipDirectory=unzipdir,
                    modelIdentifier=model_description.coSimulation.modelIdentifier)
result.instantiate()
result.setupExperiment(tolerance=1E-4, startTime=0.0)
result.enterInitializationMode()
result.exitInitializationMode()

t_start = 0
step = 240
rows = []
while t_start < 31536000:
    rows.append(result.getReal(list(vars_output.values())))
    result.setReal(vars_input.values(), [0, 0.11, 311, 1])
    result.doStep(currentCommunicationPoint=t_start, communicationStepSize=step)
    t_start = t_start + step
rows.append(result.getReal(list(vars_output.values())))
result.terminate()
result.freeInstance()

res = pd.DataFrame(rows, columns = vars_output.keys())



#%%

fmu = r'C:\git\plant_hp_variable.fmu'
model_description = read_model_description(fmu)
unzipdir = extract(fmu)
fmu_instance = instantiate_fmu(unzipdir=unzipdir, model_description=model_description)

t_start = 0
step = 240
rows = []
start_values = {'storage_m_flow': 0, 'load_m_flow': 0.11, 'hp_T': 311, 'hp_on': 1}

while t_start < 31536000:
    if t_start == 0:
        result = simulate_fmu(filename=unzipdir,
                              model_description=model_description,
                              fmu_instance=fmu_instance,
                              start_time = t_start, 
                              stop_time = t_start + step,  
                              start_values=start_values, 
                              fmi_type= 'CoSimulation', 
                              output_interval=step,
                              record_events=False, 
                              terminate=False, 
                              set_stop_time=False)
        res_b = np.array(result)
    else:
        apply_start_values(fmu=fmu_instance,
                            model_description=model_description, 
                            start_values={'storage_m_flow': 0, 'load_m_flow': 0.11, 'hp_T': 311, 'hp_on': 1})
        result = simulate_fmu(filename=unzipdir,
                              model_description=model_description,
                              fmu_instance=fmu_instance,
                              start_time = t_start, 
                              stop_time = t_start + step,
                              fmi_type= 'CoSimulation', 
                              output_interval=step,
                              initialize=False,
                              record_events=False, 
                              terminate=False, 
                              set_stop_time=False)
        res_b = np.concatenate((res_b, np.array(result[:1])), axis=0)
    t_start = t_start + step
fmu_instance.terminate()
fmu_instance.freeInstance()

res_b = pd.DataFrame(res_b)
