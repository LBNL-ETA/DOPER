# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Model construction module.
"""
from pyomo.environ import Objective, minimize

from .basemodel import base_model
from .battery import add_battery
from .ev import add_ev
from .genset import add_genset
from .loadControl import add_loadControl
from ..utility import OBJECTIVE_TERMS


def construct_model_function():
    """Return a DOPER control model function."""

    def control_model(inputs, parameter):
        """Construct pyomo model and objective from enabled systems."""
        model = base_model(inputs, parameter)
        system_cfg = parameter.get("system", {})

        if system_cfg.get("battery"):
            model = add_battery(model, inputs, parameter)

        if system_cfg.get("ev"):
            model = add_ev(model, inputs, parameter)

        if system_cfg.get("genset"):
            model = add_genset(model, inputs, parameter)

        if system_cfg.get("load_control"):
            model = add_loadControl(model, inputs, parameter)

        def objective_function(model):
            obj = 0
            weights = parameter['objective']
            for weight_key, model_var, sign in OBJECTIVE_TERMS:
                if weights.get(weight_key, False) and hasattr(model, model_var):
                    obj += sign * getattr(model, model_var) * weights[weight_key]
            return obj

        model.objective = Objective(rule=objective_function,
                                    sense=minimize,
                                    doc='objective function')
        return model

    return control_model
