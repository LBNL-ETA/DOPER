
import os
import sys

# Append parent directory to import DOPER
sys.path.append('../src')

from DOPER.wrapper import DOPER
from DOPER.utility import get_solver, get_root, standard_report
from DOPER.basemodel import base_model, default_output_list

from DOPER.battery import add_battery
from DOPER.genset import add_genset
from DOPER.battery import add_battery
from DOPER.loadControl import add_loadControl

import DOPER.example as example

from DOPER.plotting import plot_dynamic

from pyomo.environ import Objective, minimize



def control_model(inputs, parameter):
    model = base_model(inputs, parameter)
    model = add_battery(model, inputs, parameter)
    # model = add_genset(model, inputs, parameter)
    # model = add_loadControl(model, inputs, parameter)
    
    def objective_function(model):
        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               + model.sum_export_revenue * parameter['objective']['weight_export'] \
               + model.fuel_cost_total * parameter['objective']['weight_energy'] \
               + model.load_shed_cost_total \
               + model.co2_total * parameter['objective']['weight_co2']

    
    model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
    return model

### PARAMETER & TS DEFS GO HERE: ###


parameter = example.default_parameter()
parameter = example.parameter_add_battery(parameter)

data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
# offgrid_data = example.ts_inputs_offgrid(parameter)


### --- ###

# generate standard output data
# output_list = default_output_list(parameter)


# Define the path to the solver executable
solver_path = get_solver('cbc', solver_dir=os.path.join(get_root(), 'solvers'))
# print(solver_path)

# Initialize DOPER
smartDER = DOPER(model=control_model,
                 parameter=parameter,
                 solver_path=solver_path)

# Conduct optimization
res = smartDER.do_optimization(data)

# Get results
duration, objective, df, model, result, termination, parameter = res
print(standard_report(res))


        
       