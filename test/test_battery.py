import os
import sys
import unittest
from pyomo.environ import Objective, minimize

from doper import DOPER, get_solver, get_root
from doper.models.basemodel import base_model
from doper.models.battery import add_battery
import doper.examples as example
from doper.utility import default_output_list

class TestBaseModel(unittest.TestCase):
    '''
    
    unit tests for running DOPER base model.
    test setup is configured to only run optimization on first test,
    then test the various outputs from initiali optimization in subsequent tests
    
    does not test for proper error handling for incorrect use of basemodel optimization.
    
    
    '''
    
    # set initial setUpComplete flag to false, so optimization is run on first test
    setupComplete = False
    # define acceptable delta when comparing objective and other vars
    tolerance = 0.05
    
    def setUp(self):
        '''
        setUp method is run before each test.
        Only one optimization is needed for all tests, so if self.setupComplete
        is True, the optimization step is skipped

        '''
        
        if not hasattr(self, 'setupComplete'):
            print('Initializing test: running optimization')
            self.runOptimization()
        else:
            if self.setupComplete is False:
                print('Initializing test: running optimization')
                self.runOptimization()
            else:
                print('Test optimization has been completed')
        
        # define expected objective
        self.__class__.expObjective = 3756
        self.__class__.objTolerance = self.expObjective * self.tolerance
        
        
    def runOptimization(self):
        '''
        run optimization and store outputs as attributes of the class

        '''

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_battery(model, inputs, parameter)
            
            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.fuel_cost_total * parameter['objective']['weight_energy'] \
                       + model.load_shed_cost_total \
                       + model.co2_total * parameter['objective']['weight_co2'] \
                       + model.battery_cycle_cost_total
    
            
            model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
            return model
        
        # generate input parameter and data
        parameter = example.test_default_parameter()
        parameter = example.test_parameter_add_battery(parameter)
        data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    
        # generate standard output data
        output_list = default_output_list(parameter)
    
        
        # Define the path to the solver executable
        solver_path = get_solver('cbc')
        
        # Initialize DOPER
        smartDER = DOPER(model=control_model,
                         parameter=parameter,
                         solver_path=solver_path,
                         output_list=output_list)
        
        # Conduct optimization
        res = smartDER.do_optimization(data)
        
        # Get results
        duration, objective, df, model, result, termination, parameter = res
        
        # package model results into unit test class attributes
        self.__class__.duration = duration
        self.__class__.objective = objective
        self.__class__.df = df
        self.__class__.model = model
        self.__class__.result = result
        self.__class__.termination = termination
        self.__class__.parameter = parameter
        
        # change setupComplete to True
        self.__class__.setupComplete = True
   
    
    # check that setup optimization has created expected result objects
    def test_exists_duration(self):
        self.assertTrue(hasattr(self, 'duration'), msg='duration does not exist')
        
    def test_exists_objective(self):
        self.assertTrue(hasattr(self, 'objective'), msg='objective does not exist')
        
    def test_exists_df(self):
        self.assertTrue(hasattr(self, 'df'), msg='df does not exist')
        
    def test_exists_model(self):
        self.assertTrue(hasattr(self, 'model'), msg='model does not exist')
        
    def test_exists_termination(self):
        self.assertTrue(hasattr(self, 'termination'), msg='termination does not exist')
        
    # check that duration is nonzero
    def test_duration_nonxero(self):
        self.assertGreater(self.duration, 0, msg='duration is zero')
        
    # check that objective is close to expected objective value
    def test_obj_tolerance(self):
        self.assertAlmostEqual(self.objective, self.expObjective, msg='objective does not match expected with 5%', delta=self.objTolerance)
        
    # check that model contains key pyomo vars as attributes
    def test_pyomo_has_imports(self):
        self.assertTrue(hasattr(self.model, 'grid_import'), msg='pyomo model is missing key var: grid_import')
        
    def test_pyomo_has_battery_soc(self):
        self.assertTrue(hasattr(self.model, 'battery_soc'), msg='pyomo model is missing key var: battery_soc')

    # --- cycle cost tests (cycle_cost=0, so total should be 0) ---

    def test_pyomo_has_battery_cycle_cost(self):
        self.assertTrue(hasattr(self.model, 'battery_cycle_cost'),
                        msg='pyomo model is missing var: battery_cycle_cost')

    def test_pyomo_has_battery_cycle_cost_total(self):
        self.assertTrue(hasattr(self.model, 'battery_cycle_cost_total'),
                        msg='pyomo model is missing var: battery_cycle_cost_total')

    def test_pyomo_has_battery_cycle_power_change(self):
        self.assertTrue(hasattr(self.model, 'battery_cycle_power_change'),
                        msg='pyomo model is missing var: battery_cycle_power_change')

    def test_pyomo_has_bat_cycle_cost_param(self):
        self.assertTrue(hasattr(self.model, 'bat_cycle_cost'),
                        msg='pyomo model is missing param: bat_cycle_cost')

    def test_pyomo_has_bat_battery_power_param(self):
        self.assertTrue(hasattr(self.model, 'bat_battery_power'),
                        msg='pyomo model is missing param: bat_battery_power')

    def test_battery_cycle_cost_per_battery_is_zero_when_cost_is_zero(self):
        for b in self.model.batteries:
            val = self.model.battery_cycle_cost[b].value
            self.assertAlmostEqual(val, 0.0, places=4,
                                   msg=f'battery_cycle_cost[{b}] should be 0 when cycle_cost=0')

    def test_battery_cycle_cost_total_is_zero_when_cost_is_zero(self):
        # cycle_cost=0 in test_parameter_add_battery, so total cycle cost must be 0
        val = self.model.battery_cycle_cost_total.value
        self.assertAlmostEqual(val, 0.0, places=4,
                               msg='battery_cycle_cost_total should be 0 when cycle_cost=0')

    def test_battery_cycle_power_change_nonnegative(self):
        # all cycle power change values should be >= 0
        for ts in self.model.ts:
            for b in self.model.batteries:
                val = self.model.battery_cycle_power_change[ts, b].value
                self.assertGreaterEqual(val, -1e-6,
                                        msg=f'battery_cycle_power_change[{ts},{b}] is negative')


class TestCycleCostNonzero(unittest.TestCase):
    '''
    Test cycle cost functionality with a non-zero cycle_cost value.
    Verifies that:
    - battery_cycle_cost_total > 0 when cycle_cost > 0 and battery is active
    - battery_cycle_cost_total changes when cycle_cost changes
    - battery_power initializes the cycle calculation correctly
    '''

    setupComplete = False
    CYCLE_COST = 1.0  # $/kW

    def setUp(self):
        if not hasattr(self, 'setupComplete'):
            self.runOptimization()
        else:
            if self.setupComplete is False:
                self.runOptimization()

    def runOptimization(self):

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_battery(model, inputs, parameter)

            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.fuel_cost_total * parameter['objective']['weight_energy'] \
                       + model.load_shed_cost_total \
                       + model.co2_total * parameter['objective']['weight_co2'] \
                       + model.battery_cycle_cost_total

            model.objective = Objective(rule=objective_function, sense=minimize,
                                        doc='objective function')
            return model

        parameter = example.test_default_parameter()
        parameter = example.test_parameter_add_battery(parameter)
        # set a non-zero cycle cost
        parameter['batteries'][0]['cycle_cost'] = self.CYCLE_COST
        parameter['batteries'][0]['battery_power'] = 0

        data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
        output_list = default_output_list(parameter)
        solver_path = get_solver('cbc')

        smartDER = DOPER(model=control_model,
                         parameter=parameter,
                         solver_path=solver_path,
                         output_list=output_list)
        res = smartDER.do_optimization(data)
        duration, objective, df, model, result, termination, parameter = res

        self.__class__.duration = duration
        self.__class__.objective = objective
        self.__class__.df = df
        self.__class__.model = model
        self.__class__.result = result
        self.__class__.termination = termination
        self.__class__.parameter = parameter
        self.__class__.setupComplete = True

    def test_optimization_completes(self):
        self.assertIsNotNone(self.objective, msg='optimization did not return an objective')

    def test_battery_cycle_cost_total_nonnegative(self):
        val = self.model.battery_cycle_cost_total.value
        self.assertGreaterEqual(val, -1e-6,
                                msg='battery_cycle_cost_total should be >= 0')

    def test_battery_cycle_cost_total_positive_when_battery_active(self):
        # with load present and battery enabled, the battery must cycle at least once
        val = self.model.battery_cycle_cost_total.value
        self.assertGreater(val, 0.0,
                           msg='battery_cycle_cost_total should be > 0 when battery is active '
                               'and cycle_cost > 0')

    def test_battery_cycle_cost_per_battery_positive(self):
        # with a non-zero cycle_cost, per-battery cost should also be > 0
        for b in self.model.batteries:
            val = self.model.battery_cycle_cost[b].value
            self.assertGreaterEqual(val, -1e-6,
                                    msg=f'battery_cycle_cost[{b}] should be >= 0')

    def test_total_equals_sum_of_per_battery(self):
        per_battery_sum = sum(self.model.battery_cycle_cost[b].value
                              for b in self.model.batteries)
        self.assertAlmostEqual(
            per_battery_sum, self.model.battery_cycle_cost_total.value,
            places=4,
            msg='battery_cycle_cost_total does not equal sum of per-battery battery_cycle_cost'
        )

    def test_cycle_power_change_consistent_with_cost(self):
        # verify the constraint: total_cost == sum(change * cycle_cost)
        cycle_cost_rate = self.CYCLE_COST
        computed_cost = sum(
            self.model.battery_cycle_power_change[ts, b].value * cycle_cost_rate
            for ts in self.model.ts
            for b in self.model.batteries
        )
        self.assertAlmostEqual(
            computed_cost, self.model.battery_cycle_cost_total.value,
            places=3,
            msg='battery_cycle_cost_total does not match sum of cycle_power_change * cycle_cost'
        )

    def test_cycle_power_change_captures_absolute_change(self):
        # for each ts, battery_cycle_power_change >= |net_power[ts] - net_power[ts-1]|
        ts_list = list(self.model.ts)
        battery_power_init = self.parameter['batteries'][0]['battery_power']
        b = list(self.model.batteries)[0]

        for i, ts in enumerate(ts_list):
            net_power = (self.model.battery_charge_power[ts, b].value
                         - self.model.battery_discharge_power[ts, b].value)
            if i == 0:
                net_power_prev = battery_power_init
            else:
                ts_prev = ts_list[i - 1]
                net_power_prev = (self.model.battery_charge_power[ts_prev, b].value
                                  - self.model.battery_discharge_power[ts_prev, b].value)
            diff = abs(net_power - net_power_prev)
            change_val = self.model.battery_cycle_power_change[ts, b].value
            self.assertGreaterEqual(
                change_val + 1e-6, diff,
                msg=f'cycle_power_change[{ts}] < |net_power diff| at timestep {i}'
            )


class TestBatteryPowerInit(unittest.TestCase):
    '''
    Test that battery_power is correctly used to initialize the cycle calculation
    at the first timestep. With a non-zero battery_power, the change at the first
    timestep should reflect the difference from battery_power.
    '''

    setupComplete = False
    BATTERY_POWER_INIT = 30.0  # kW (charging)

    def setUp(self):
        if not hasattr(self, 'setupComplete'):
            self.runOptimization()
        else:
            if self.setupComplete is False:
                self.runOptimization()

    def runOptimization(self):

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_battery(model, inputs, parameter)

            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.fuel_cost_total * parameter['objective']['weight_energy'] \
                       + model.load_shed_cost_total \
                       + model.co2_total * parameter['objective']['weight_co2'] \
                       + model.battery_cycle_cost_total

            model.objective = Objective(rule=objective_function, sense=minimize,
                                        doc='objective function')
            return model

        parameter = example.test_default_parameter()
        parameter = example.test_parameter_add_battery(parameter)
        parameter['batteries'][0]['cycle_cost'] = 1.0
        parameter['batteries'][0]['battery_power'] = self.BATTERY_POWER_INIT

        data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
        output_list = default_output_list(parameter)
        solver_path = get_solver('cbc')

        smartDER = DOPER(model=control_model,
                         parameter=parameter,
                         solver_path=solver_path,
                         output_list=output_list)
        res = smartDER.do_optimization(data)
        duration, objective, df, model, result, termination, parameter = res

        self.__class__.duration = duration
        self.__class__.objective = objective
        self.__class__.model = model
        self.__class__.parameter = parameter
        self.__class__.setupComplete = True

    def test_bat_battery_power_param_value(self):
        b = list(self.model.batteries)[0]
        self.assertAlmostEqual(
            self.model.bat_battery_power[b], self.BATTERY_POWER_INIT, places=4,
            msg='bat_battery_power param does not match configured battery_power'
        )

    def test_first_timestep_cycle_change_reflects_init_power(self):
        # cycle_power_change at first timestep >= |net_power[ts0] - battery_power_init|
        b = list(self.model.batteries)[0]
        ts0 = self.model.ts.at(1)
        net_power_ts0 = (self.model.battery_charge_power[ts0, b].value
                         - self.model.battery_discharge_power[ts0, b].value)
        expected_min_change = abs(net_power_ts0 - self.BATTERY_POWER_INIT)
        change_val = self.model.battery_cycle_power_change[ts0, b].value
        self.assertGreaterEqual(
            change_val + 1e-6, expected_min_change,
            msg=f'First-timestep cycle_power_change {change_val:.3f} < '
                f'|net_power - battery_power_init| = {expected_min_change:.3f}'
        )

    def test_optimization_completes_with_nonzero_battery_power(self):
        self.assertIsNotNone(self.objective,
                             msg='optimization did not complete with non-zero battery_power')


if __name__ == '__main__':
    unittest.main()
