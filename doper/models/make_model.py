from pyomo.environ import Objective, minimize

from .basemodel import base_model
from .battery import add_battery
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

        if system_cfg.get("genset"):
            model = add_genset(model, inputs, parameter)

        if system_cfg.get("load_control"):
            model = add_loadControl(model, inputs, parameter)

        def objective_function(model):
            obj = 0
            weights = parameter['objective']
            if 'weight_energy' in weights:
                obj += model.sum_energy_cost * weights['weight_energy']
            if 'weight_demand' in weights:
                obj += model.sum_demand_cost * weights['weight_demand']
            if 'weight_export' in weights:
                obj += model.sum_export_revenue * weights['weight_export']
            if 'weight_fuel' in weights:
                obj += model.fuel_cost_total * weights['weight_fuel']
            if 'weight_load_shed' in weights:
                obj += model.load_shed_cost_total * weights['weight_load_shed']
            if 'weight_co2' in weights:
                obj += model.co2_total * weights['weight_co2']
            return obj
        model.objective = Objective(rule=objective_function,
                                    sense=minimize,
                                    doc='objective function')
            
        return model

    return control_model
