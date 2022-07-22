import os
import sys
import unittest
from pyomo.environ import Objective, minimize

from doper import DOPER, get_solver, get_root
from doper.models.basemodel import base_model, default_output_list
from doper.models.loadControl import add_loadControl
from doper.models.network import add_network_simple
import doper.examples as example

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
        self.__class__.expObjective = 22500
        self.__class__.objTolerance = self.expObjective * self.tolerance
        
        
    def runOptimization(self):
        '''
        run optimization and store outputs as attributes of the class

        '''

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_network_simple(model, inputs, parameter)
            model = add_loadControl(model, inputs, parameter)
            
            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.fuel_cost_total * parameter['objective']['weight_energy'] \
                       + model.load_shed_cost_total \
                       + model.co2_total * parameter['objective']['weight_co2']
    
            
            model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
            return model
        
        # generate input parameter and data
        parameter = example.parameter_add_network_test()
        parameter = example.parameter_add_loadcontrol_multinode_test(parameter)
        
        # add planned outage to ts_data to drive genset utilization
        data = example.ts_inputs_multinode_test(parameter)
        data = example.data = example.ts_inputs_load_shed_multinode_test(parameter, data)
    
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
        
        # print(f'obj: {objective}')
   
    
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
        
    # check that model contains correct number of nodes
    def test_node_count(self):
        nNodesIn = len(self.parameter['network']['nodes'])
        nNodesOut = len(self.model.nodes.ordered_data())
        self.assertEqual(nNodesIn, nNodesOut, msg='model node count incorrect')
        
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


if __name__ == '__main__':
    unittest.main()