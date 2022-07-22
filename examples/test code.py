# -*- coding: utf-8 -*-
"""
Created on Wed Dec  9 14:00:49 2020

@author: nicholas
"""

import os
import sys
import pandas as pd
import matplotlib.pyplot as plt
from pprint import pprint
import logging

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

# Append parent directory to import DOPER
sys.path.append('../src')

from DOPER.wrapper import DOPER
from DOPER.utility import get_solver, get_root, standard_report
from DOPER.basemodel import base_model, default_output_list
# from DOPER.batterymodel import add_battery, convert_battery, plot_battery1
from DOPER.battery import add_battery
from DOPER.genset import add_genset
from DOPER.loadControl import add_loadControl
from DOPER.example import (example_inputs, example_parameter_add_genset, 
                            example_inputs_offgrid, example_inputs_planned_outage, 
                            example_parameter_add_battery, example_parameter_add_loadcontrol, 
                            example_inputs_load_shed, example_inputs_fueloutage, example_inputs_variable_co2)
                            

from pyomo.environ import Objective, minimize

def control_model(inputs, parameter):
    model = base_model(inputs, parameter)
    model = add_battery(model, inputs, parameter)
    model = add_genset(model, inputs, parameter)
    # model = add_loadControl(model, inputs, parameter)
    # model = add_battery(model, inputs, parameter)
    
    def objective_function(model):
        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               + model.sum_export_revenue * parameter['objective']['weight_export'] \
               + model.sum_regulation_revenue * parameter['objective']['weight_regulation'] \
               + model.fuel_cost_total * parameter['objective']['weight_energy'] \
               + model.load_shed_cost_total
               
    def objective_function_co2(model):
        return model.co2_total
    
    model.objective = Objective(rule=objective_function_co2, sense=minimize, doc='objective function')
    return model

parameter = None
# parameter = example_parameter_evfleet()
parameter = example_parameter_add_genset(parameter)
# parameter = example_parameter_add_loadcontrol(parameter)
parameter = example_parameter_add_battery(parameter)
#parameter

data = example_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
data1 = example_inputs_variable_co2(parameter, data, scaling=[2,3,2,1])
data2 = example_inputs_variable_co2(parameter, data, scaling=[3,1,2,1])
# data = example_inputs_fueloutage(parameter)
# data = example_inputs_load_shed(parameter)
# add planned outage
# data = example_inputs_planned_outage(parameter, data)
# data = example_inputs_offgrid(parameter)
#data


output_list = default_output_list(parameter)
# add individual battery charging to output list
output_list.append({
                    'name': 'batSOC',
                    'data': 'battery_energy',
                    'index': 'batteries',
                    'df_label': 'Energy in Battery %s'
                })

# Define the path to the solver executable
solver_path = get_solver('cbc', solver_dir=os.path.join(get_root(), 'solvers'))
print(solver_path)
# Initialize DOPER
smartDER = DOPER(model=control_model,
                 parameter=parameter,
                 solver_path=solver_path,
                 output_list=output_list)

# Conduct optimization
res = smartDER.do_optimization(data)

# Get results
duration, objective, df, model, result, termination, parameter = res
print(standard_report(res))
      
# for t in model.ts:
#     print(model.sum_battery_charge_grid_power[t].value)

df.to_csv('test_results/test_results.csv')
    
plotData = plot_dynamic(df, parameter, plotFile = 'test_results/test_results.png', plot_reg=False)
# plotData.savefig('test_results.png')