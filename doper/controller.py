# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Controller module.
"""

# pylint: disable=import-error, redefined-outer-name, invalid-name

import pandas as pd
from pyomo.environ import Objective, minimize

from .wrapper import DOPER
from .utility import get_solver, standard_report
from .basemodel import base_model, convert_base_model
from .batterymodel import add_battery, convert_battery
from .example import example_parameter_evfleet, example_inputs_evfleet2

def control_model(inputs, parameter):
    """control model"""

    model = base_model(inputs, parameter)
    model = add_battery(model, inputs, parameter)

    if 'weight_degradation' in parameter['objective']:
        print('WARNING: No "degradation" in objective function.')
    def objective_function(model):
        """objective function"""

        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               + model.sum_export_revenue * parameter['objective']['weight_export'] \
               + model.sum_regulation_revenue * parameter['objective']['weight_regulation']
    model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
    return model

def pyomo_to_pandas(model, parameter):
    """convert pyomo to pandas"""

    df = convert_base_model(model, parameter)
    df = pd.concat([df, convert_battery(model, parameter)], axis=1)
    return df

if __name__ == '__main__':
    parameter = example_parameter_evfleet()
    data = example_inputs_evfleet2(parameter)
    del parameter['objective']['weight_degradation']

    smartDER = DOPER(model=control_model,
                     parameter=parameter,
                     solver_path=get_solver('cbc', solver_dir='solvers'))
    res = smartDER.do_optimization(data, tee=False)
    duration, objective, df, model, result, termination, parameter = res
    print(standard_report(res))
