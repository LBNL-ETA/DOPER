import os
import sys
import unittest
from pyomo.environ import Objective, minimize

from doper import DOPER, get_solver, get_root
from doper.models.basemodel import base_model
from doper.models.loadControl import add_loadControl
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
        self.__class__.expObjective = 3059
        self.__class__.objTolerance = self.expObjective * self.tolerance
        
        
    def runOptimization(self):
        '''
        run optimization and store outputs as attributes of the class

        '''

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_loadControl(model, inputs, parameter)
            
            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       - model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.fuel_cost_total * parameter['objective']['weight_energy'] \
                       + model.load_shed_cost_total \
                       + model.co2_total * parameter['objective']['weight_co2']
    
            
            model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
            return model
        
        # generate input parameter and data
        parameter = example.test_default_parameter()
        parameter = example.test_parameter_add_loadcontrol(parameter)
        
        # add planned outage to ts_data to drive genset utilization
        data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
        data = example.ts_inputs_load_shed(parameter, data)
    
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
        
        # extract fuel costs for comparison test
        self.__class__.loadShedCost = model.load_shed_cost_total.value
        
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
        
    # check that fuel cost is nonzero
    def test_load_shed_cost_total_nonxero(self):
        self.assertGreater(self.loadShedCost, 0, msg='total load shed costs is zero')
        
    # check that objective is close to expected objective value
    def test_obj_tolerance(self):
        self.assertAlmostEqual(self.objective, self.expObjective, msg='objective does not match expected with 5%', delta=self.objTolerance)
        
    # check that model contains key pyomo vars as attributes
    def test_pyomo_has_imports(self):
        self.assertTrue(hasattr(self.model, 'grid_import'), msg='pyomo model is missing key var: grid_import')
        
    def test_pyomo_has_load_shed(self):
        self.assertTrue(hasattr(self.model, 'load_shed'), msg='pyomo model is missing key var: load_shed')

    # --- new attribute tests ---

    def test_pyomo_has_load_connected(self):
        self.assertTrue(hasattr(self.model, 'load_connected'),
                        msg='pyomo model is missing param: load_connected')

    def test_pyomo_has_load_transition_cost(self):
        self.assertTrue(hasattr(self.model, 'load_transition_cost'),
                        msg='pyomo model is missing param: load_transition_cost')

    def test_pyomo_has_load_shed_act_total(self):
        self.assertTrue(hasattr(self.model, 'load_shed_act_total'),
                        msg='pyomo model is missing var: load_shed_act_total')

    def test_load_shed_act_total_nonnegative(self):
        val = self.model.load_shed_act_total.value
        self.assertIsNotNone(val, msg='load_shed_act_total value is None')
        self.assertGreaterEqual(val, 0, msg='load_shed_act_total is negative')

    def test_der_shed_t1_nonnegative(self):
        """der_shed_load at t=1 must be >= 0 for all circuits (bounds enforced)."""
        model = self.model
        ts_first = model.ts.at(1)
        for c in model.load_circuits:
            val = model.der_shed_load[ts_first, c].value
            self.assertIsNotNone(val, msg=f'der_shed_load[t=1, {c}] is None')
            self.assertGreaterEqual(val, -1e-6,
                                    msg=f'der_shed_load[t=1, {c}] is negative')


class TestLoadConnectedFlexibility(unittest.TestCase):
    '''
    Tests that load_connected seeds der_shed_load at t=1 correctly AND that
    the model retains full flexibility to disconnect a circuit at the first
    timestep even when load_connected=1.

    A scenario where shedding cost is zero makes it optimal for the optimizer
    to shed all load circuits for the entire horizon, including t=1. This
    verifies that the >= constraint (not ==) does not prevent the optimizer
    from choosing to disconnect at t=1.
    '''

    setupComplete = False

    def setUp(self):
        if not hasattr(self, 'setupComplete') or not self.setupComplete:
            print('Initializing TestLoadConnectedFlexibility: running optimization')
            self.runOptimization()
        else:
            print('TestLoadConnectedFlexibility optimization has been completed')

    def runOptimization(self):

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_loadControl(model, inputs, parameter)

            def objective_function(model):
                # Only energy and demand cost — shedding is free (weight_load_shed=0)
                # This makes it optimal to shed everything to reduce import
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.load_shed_cost_total * parameter['objective']['weight_load_shed'] \
                       + model.load_shed_act_total * parameter['objective']['weight_load_shed_act']

            model.objective = Objective(rule=objective_function, sense=minimize,
                                        doc='objective function')
            return model

        parameter = example.test_default_parameter()
        parameter = example.test_parameter_add_loadcontrol(parameter)

        # Set load_connected=1 for all circuits (connected before horizon start)
        # Set transition_cost=1 to populate load_transition_cost param,
        # but weight_load_shed_act=0 so the cost does not enter the objective —
        # this allows us to check der_shed_load values without distorting the solution
        for circuit in parameter['load_control']:
            circuit['load_connected'] = 1
            circuit['transition_cost'] = 1

        # Free shedding: shedding cost is zero, so optimizer sheds everything
        parameter['objective']['weight_load_shed'] = 0
        parameter['objective']['weight_load_shed_act'] = 0

        data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
        data = example.ts_inputs_load_shed(parameter, data)

        output_list = default_output_list(parameter)
        solver_path = get_solver('cbc')

        smartDER = DOPER(model=control_model,
                         parameter=parameter,
                         solver_path=solver_path,
                         output_list=output_list)

        res = smartDER.do_optimization(data)
        duration, objective, df, model, result, termination, parameter = res

        self.__class__.model = model
        self.__class__.parameter = parameter
        self.__class__.setupComplete = True

    def test_can_disconnect_at_t1(self):
        '''Model must be free to disconnect a circuit at t=1 despite load_connected=1.'''
        model = self.model
        ts_first = model.ts.at(1)
        # With zero shedding cost the optimizer will shed all circuits at all timesteps
        any_disconnected = any(
            (model.load_circuits_on[ts_first, c].value is not None and
             model.load_circuits_on[ts_first, c].value < 0.5)
            for c in model.load_circuits
        )
        self.assertTrue(any_disconnected,
                        msg='Model failed to disconnect any circuit at t=1 '
                            'even though shedding is free and load_connected=1')

    def test_der_shed_t1_geq_one_when_disconnected(self):
        '''When load_connected=1 and circuit disconnects at t=1, der_shed_load[t=1] >= 1.'''
        model = self.model
        ts_first = model.ts.at(1)
        for c in model.load_circuits:
            on_val = model.load_circuits_on[ts_first, c].value
            der_val = model.der_shed_load[ts_first, c].value
            if on_val is not None and on_val < 0.5:
                # Circuit was shed at t=1; der_shed_load must reflect the 1->0 transition
                self.assertGreaterEqual(
                    der_val, 0.5,
                    msg=f'Circuit {c} disconnected at t=1 with load_connected=1 '
                        f'but der_shed_load[t=1] = {der_val} (expected >= 1)'
                )

    def test_load_shed_act_total_reflects_t1_transition(self):
        '''load_shed_act_total equals sum of transition_cost * der_shed_load over accounting_ts.'''
        model = self.model
        # Manually compute the expected value
        expected = sum(
            model.der_shed_load[ts, c].value * model.load_transition_cost[c]
            for c in model.load_circuits
            for ts in model.accounting_ts
        )
        actual = model.load_shed_act_total.value
        self.assertIsNotNone(actual, msg='load_shed_act_total is None')
        self.assertAlmostEqual(actual, expected, places=4,
                               msg='load_shed_act_total does not match manual sum of '
                                   'der_shed_load * transition_cost over accounting_ts')


if __name__ == '__main__':
    unittest.main()