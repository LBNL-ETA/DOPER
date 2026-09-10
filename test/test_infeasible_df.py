import unittest
import pandas as pd
from pyomo.environ import Objective, minimize
from pyomo.opt import TerminationCondition

from doper import DOPER, get_solver
from doper.models.basemodel import base_model
import doper.examples as example
from doper.utility import default_output_list


def _control_model(inputs, parameter):
    """Minimal base model with a standard energy+demand objective."""
    model = base_model(inputs, parameter)

    def objective_function(model):
        return (
            model.sum_energy_cost * parameter['objective']['weight_energy']
            + model.sum_demand_cost * parameter['objective']['weight_demand']
        )

    model.objective = Objective(rule=objective_function, sense=minimize)
    return model


def _make_infeasible_res(fill_df_infeasible):
    """Build and solve an infeasible problem, returning the full result tuple."""
    parameter = example.test_default_parameter()
    # Force infeasibility: no import or export allowed while load exists
    parameter['site']['import_max'] = 0
    parameter['site']['export_max'] = 0
    parameter['controller']['fill_df_infeasible'] = fill_df_infeasible

    data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    output_list = default_output_list(parameter)
    solver_path = get_solver('cbc')

    smart = DOPER(
        model=_control_model,
        parameter=parameter,
        solver_path=solver_path,
        output_list=output_list,
    )
    return smart.do_optimization(data, print_error=False)


class TestInfeasibleDfBase(unittest.TestCase):
    """Shared setup: run one infeasible solve per subclass, cache on the class."""

    fill_df_infeasible = None # set by subclasses
    _cache = {}

    def _get_res(self):
        key = self.fill_df_infeasible
        if key not in self.__class__._cache:
            self.__class__._cache[key] = _make_infeasible_res(key)
        return self.__class__._cache[key]

    def setUp(self):
        res = self._get_res()
        self.duration, self.objective, self.df, self.model, \
            self.result, self.termination, self.parameter = res

    def test_is_infeasible(self):
        self.assertNotEqual(self.termination, TerminationCondition.optimal)

    def test_objective_is_none(self):
        self.assertIsNone(self.objective)

    def test_df_is_dataframe(self):
        self.assertIsInstance(self.df, pd.DataFrame)

    def test_df_columns_match_feasible(self):
        """Columns must match a feasible solve in set and order."""
        feasible_parameter = example.test_default_parameter()
        feasible_data = example.ts_inputs(feasible_parameter, load='B90', scale_load=150, scale_pv=100)
        output_list = default_output_list(feasible_parameter)
        solver_path = get_solver('cbc')
        smart = DOPER(
            model=_control_model,
            parameter=feasible_parameter,
            solver_path=solver_path,
            output_list=output_list,
        )
        _, _, feasible_df, _, _, _, _ = smart.do_optimization(feasible_data, print_error=False)
        self.assertEqual(list(self.df.columns), list(feasible_df.columns))


class TestInfeasibleDfFalse(TestInfeasibleDfBase):
    """fill_df_infeasible=False -> empty df with correct columns."""

    fill_df_infeasible = False

    def test_df_has_no_rows(self):
        self.assertEqual(len(self.df), 0)

    def test_df_has_columns(self):
        self.assertGreater(len(self.df.columns), 0)


class TestInfeasibleDfTrue(TestInfeasibleDfBase):
    """fill_df_infeasible=True -> df with correct columns and one row per timestep."""

    fill_df_infeasible = True

    def test_df_has_rows(self):
        self.assertGreater(len(self.df), 0)

    def test_param_columns_have_values(self):
        self.assertTrue(self.df['Tariff Energy Period [-]'].notna().all())
        self.assertTrue(self.df['Temperature [C]'].notna().all())

    def test_var_columns_are_nan(self):
        self.assertTrue(self.df['Import Power [kW]'].isna().all())
        self.assertTrue(self.df['Export Power [kW]'].isna().all())


if __name__ == '__main__':
    unittest.main()
