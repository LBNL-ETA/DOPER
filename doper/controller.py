#!/usr/bin/env python

'''
    INTERNAL USE ONLY
    Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''

import os
import sys
import numpy as np
import pandas as pd
from time import time
import matplotlib.pyplot as plt
from pyomo.environ import Objective, minimize

from wrapper import DOPER
from utility import get_solver, get_root, standard_report
from basemodel import base_model, convert_base_model, plot_standard1
from batterymodel import add_battery, convert_battery, plot_battery1
from example import example_parameter_evfleet, example_inputs_evfleet2

def control_model(inputs, parameter):
    model = base_model(inputs, parameter)
    model = add_battery(model, inputs, parameter)

    if 'weight_degradation' in parameter['objective']:
        print('WARNING: No "degradation" in objective function.')
    def objective_function(model):
        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               + model.sum_export_revenue * parameter['objective']['weight_export'] \
               + model.sum_regulation_revenue * parameter['objective']['weight_regulation']
    model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
    return model
    
def pyomo_to_pandas(model, parameter):
    df = convert_base_model(model, parameter)
    df = pd.concat([df, convert_battery(model, parameter)], axis=1)
    return df 
    
if __name__ == '__main__':
    parameter = example_parameter_evfleet()
    data = example_inputs_evfleet2(parameter)
    del parameter['objective']['weight_degradation']

    smartDER = DOPER(model=control_model,
                     parameter=parameter,
                     solver_path=get_solver('cbc', solver_dir='solvers'),
                     pyomo_to_pandas=pyomo_to_pandas)
    res = smartDER.do_optimization(data, tee=False)
    duration, objective, df, model, result, termination, parameter = res
    print(standard_report(res))