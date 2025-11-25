# -*- coding: utf-8 -*-
"""
Created on Wed Feb  5 00:06:27 2025

@author: remi
"""

def test(u, state):
    [t_bottom,t_sec] = u
    soc = 0.5
    if state == None:
        state = {'number_times': 0}
    else:
        state['number_times'] = state['number_times'] + 1
        if state['number_times'] > 20:
            soc = 0.3
    boiler_on = 0
    if t_bottom > 90 + 273.15:
        hp_on = 0
    else:        
        hp_on = 12
    return[[hp_on, boiler_on, soc], state]

def hope(u, state):
    [a, b] = u
    if state == None:
        state = {'number_times': 0}
    else:
        state['number_times'] = state['number_times'] + 1
    return [[a + b + 1, a], state]