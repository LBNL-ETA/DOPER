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
import json

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

# Append parent directory to import DOPER
sys.path.append('../src')

from DOPER.wrapper import DOPER
from DOPER.utility import get_solver, get_root, standard_report
from DOPER.basemodel import base_model, default_output_list, dev_output_list
# from DOPER.batterymodel import add_battery, convert_battery, plot_battery1
from DOPER.battery import add_battery
from DOPER.genset import add_genset
from DOPER.loadControl import add_loadControl
from DOPER.network import add_network, add_network_simple

import DOPER.example as example

from DOPER.plotting import plot_dynamic_nodes, formatExternalData
                            

from pyomo.environ import Objective, minimize

def control_model(inputs, parameter):
    model = base_model(inputs, parameter)
    
    model = add_battery(model, inputs, parameter)
    model = add_genset(model, inputs, parameter)
    # model = add_loadControl(model, inputs, parameter)
    
    model = add_network_simple(model, inputs, parameter)
    
    
    def objective_function(model):
        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               + model.sum_export_revenue * parameter['objective']['weight_export'] \
               + model.fuel_cost_total * parameter['objective']['weight_energy'] \
               + model.load_shed_cost_total
               
    def objective_function_co2(model):
        return model.co2_total
    
    model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
    return model

parameter = None

# add specific assets
parameter = example.parameter_add_battery_multinode(parameter)
parameter = example.parameter_add_genset_multinode(parameter)
# parameter = example.parameter_add_loadcontrol_multinode_test(parameter)

parameter = example.parameter_add_network_test(parameter)
# parameter = example.parameter_add_network(parameter)






# # reduce fuel prices for testing
# parameter['fuels'][0]['rate'] = 0.5
# parameter['fuels'][1]['rate'] = 0.5

# data = example_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
data = example.ts_inputs_multinode_test(parameter)
# data = example.ts_inputs_load_shed_multinode_test(parameter, data)

# add external gen for testing
# data['external_gen_1'] = 12.2
# data['external_gen_2'] = 44.3

# data1 = example.ts_inputs_variable_co2(parameter, data, scaling=[2,3,2,1])
# data2 = example.ts_inputs_variable_co2(parameter, data, scaling=[3,1,2,1])
# data = example.ts_inputs_fueloutage(parameter)
# data = example.ts_inputs_load_shed(parameter)
# add planned outage
# data = example.ts_inputs_planned_outage(parameter, data)
# data = example.ts_inputs_offgrid(parameter)
#data

# increase dmd charges for more interesting results
# parameter['tariff']['demand'] = {0:0,1:0,2:0}
# parameter['tariff']['demand_coincident'] = 25


# output_list = default_output_list(parameter)
# add individual battery charging to output list
# output_list += [
#     {
#         'name': 'gridImport',
#         'data': 'grid_import',
#         'index': 'nodes',
#         'df_label': 'Node grid import [kW]'
#     },
#     {
#         'name': 'gridExport',
#         'data': 'grid_export',
#         'index': 'nodes',
#         'df_label': 'Node grid export [kW]'
#     },
#     {
#         'name': 'loadServed',
#         'data': 'load_served',
#         'index': 'nodes',
#         'df_label': 'Node load served [kW]'
#     },
#     {
#         'name': 'pvGen',
#         'data': 'generation_pv',
#         'index': 'nodes',
#         'df_label': 'Node pv gen [kW]'
#     },
#     {
#         'name': 'powerInj',
#         'data': 'power_inj',
#         'index': 'nodes',
#         'df_label': 'Node power injected [kW]'
#     },
#     {
#         'name': 'powerAbs',
#         'data': 'power_abs',
#         'index': 'nodes',
#         'df_label': 'Node power absorbed [kW]'
#     },
#     {
#         'name': 'gensetGen',
#         'data': 'sum_genset_power',
#         'index': 'nodes',
#         'df_label': 'Node genset gen [kW]'
#     }
    
    
# ]

output_list = dev_output_list(parameter)

# output_list += [{
#     'name': 'batSoc',
#     'data': 'battery_agg_soc',
#     'df_label': 'battery_SOC_agg' 
# }]

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
    
# plotData = plot_dynamic(df, parameter, plotFile = 'test_results/test_results.png', plot_reg=False)
# plotData.savefig('test_results.png')

# try:
#     plotData = plot_dynamic_nodes(df, parameter, plotFile = 'test_results/test_results_NODES.png')
#     # plotData.savefig('test_results.png')
# except Exception as e:
#     print(e)

# reformat ts data for R plotting
# df2 = formatExternalData(df)
# df2.to_csv('test_results/test_results_R.csv')

# # dump power flow data to csv
# pfData = [['ind', 'ts', 'n1', 'n2', 'line', 'val']]
# rawData = model.line_power_real.extract_values()
# for ii, ts in enumerate(model.ts.ordered_data()):
    
#     for n1 in model.nodes.ordered_data():
        
#         for n2 in model.nodes.ordered_data():
            
#             val = rawData[(ts, n1, n2)]
#             line = f'{n1}-{n2}'
            
#             dataRow = [ii, ts, n1, n2, line, val]
            
#             pfData.append(dataRow)
            
# with open ('test_results/pf_data.csv', 'w') as fo:
#     for row in pfData:
#         row = [str(val) for val in row]
#         row = ','.join(row)
#         fo.write(row + '\n')
        
# data.to_csv('test_results/test_inputs_multinode.csv')

# with open("input_parameter_multinode.json", "w") as outfile:
#     json.dump(parameter, outfile)

def getVals(model, varName):
    
    vals = getattr(model, varName).extract_values().values()
    n = len(vals)
    
    return {
        'name': varName,
        'sum': int(sum(vals)),
        'mean': int(sum(vals)/float(n)),
        'min': min(vals),
        'max': int(max(vals)),
    }

        
varList = [
    'load_served_site', 'generation_pv_site',
    'grid_import_site', 'grid_export_site',
    'powerExchangeIn', 'powerExchangeOut'
    ]
        
for vv in varList:
    print(getVals(model, vv))
