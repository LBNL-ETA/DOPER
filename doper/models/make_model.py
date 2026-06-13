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

def formulate_objective_function(model, parameter):
    """Build objective function from parameter['objective']."""
    objective_terms = {
        "weight_energy": "sum_energy_cost",
        "weight_demand": "sum_demand_cost",
        "weight_export": "sum_export_revenue",
        "weight_regulation": "sum_regulation_revenue",
        "weight_fuel": "fuel_cost_total",
        "weight_load_shed": "load_shed_cost_total",
        "weight_co2": "co2_total",
    }

    objective = 0
    objective_cfg = parameter.get("objective", {})
    for weight_key, model_term in objective_terms.items():
        if weight_key in objective_cfg and hasattr(model, model_term):
            objective += getattr(model, model_term) * objective_cfg[weight_key]
    return objective

def construct_model_function():
    """Return a DOPER instance."""

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
            if weights.get('weight_energy', False):
                obj += model.sum_energy_cost * weights['weight_energy']
            if weights.get('weight_demand', False):
                obj += model.sum_demand_cost * weights['weight_demand']
            if weights.get('weight_export', False):
                obj += model.sum_export_revenue * weights['weight_export']
            if weights.get('weight_fuel', False):
                obj += model.fuel_cost_total * weights['weight_fuel']
            if weights.get('weight_load_shed', False):
                obj += model.load_shed_cost_total * weights['weight_load_shed']
            if weights.get('weight_co2', False):
                obj += model.co2_total * weights['weight_co2']
            if weights.get('weight_ev_charging', False):
                obj -= model.ev_charging_revenue * weights['weight_ev_charging']
            if weights.get('weight_ev_discharging', False):
                obj += model.ev_discharging_cost * weights['weight_ev_discharging']
            return obj
        model.objective = Objective(rule=objective_function,
                                    sense=minimize,
                                    doc='objective function')
            
        return model

    return control_model
