import unittest
import os
import sys

# Append parent directory to import DOPER
sys.path.append('../src')


from doper import DOPER, get_solver, get_root
from doper.models.basemodel import base_model, default_output_list
from doper.models.battery import add_battery
from doper.models.network import add_network
import doper.examples as example


from pyomo.environ import Objective, minimize

def create_test_parameter():
    '''
    generates input and parameter objects for testing

    '''
    
    parameter = example.default_parameter()
    
    # Add nodes and line options
    parameter['network'] = {}
    
    
    # Add network settings to define power-flow constaints
    parameter['network']['settings'] = {
        
        # turn off simepl power exchange to utilize full power-flow equations
        'simplePowerExchange': False,
        'simpleNetworkLosses': 0.05,

        'enableGenPqLimits': False, # not implemented yet

    
        # powerflow parameters
        'slackBusVoltage': 1,
        'sBase': 1000,
       'vBase': 1,
        'cableDerating': 1,
        'txDerating': 1,
    
        # power factors
        'powerFactors': {
            'pv': 1,  
            'genset': 1,
            'batteryDisc': 1,
            'batteryChar': 1,
            'load': 1
        },
    
        # powerflow model settings
        'enableLosses': True,
        'thetaMin': -0.18,
        'thetaMax': 0.09,
        'voltMin': 0.8,
        'voltMax': 1.1,
        'useConsVoltMin': False,
    }
    
    parameter['network']['nodes'] = [ # list of dict to define inputs for each node in network
        { # node 1
            'node_id': 'N1', # unique str to id node
            'pcc': True, # bool to define if node is pcc
            'slack': True, 
            'load_id': None, # str, list of str, or None to find load profile in ts data (if node is load bus) by column label
            'ders': { # dict of der assets at node, if None or not included, no ders present
                'pv_id': None, # str, list, or None to find pv profile in ts data (if pv at node) by column label
                'pv_maxS': 0,
                'battery': None, # list of str corresponding to battery assets (defined in parameter['system']['battery'])
                'genset': None, # list of str correponsing to genset assets (defined in parameter['system']['genset'])
                'load_control': None # str, list or None correponsing to genset assets (defined in parameter['system']['load_control'])
            },
            'connections': [ # list of connected nodes, and line connecting them
                {
                    'node': 'N2', # str containing unique node_id of connected node
                    'line': 'L1' # str containing unique line_id of line connection nodes, (defined in parameter['network']['lines'])
                },
                {
                    'node': 'N4',
                    'line': 'L2'
                }
            ]
        },
        { # node 2
            'node_id': 'N2',
            'pcc': True,
            'slack': False, 
            'load_id': 'pf_demand_node2',
            'ders': { 
                'pv_id': 'pf_pv_node2',
                'pv_maxS': 300,
                'battery': 'pf_bat_node2', # node can contain multiple battery assets, so should be list
                'genset': None,
                'load_control': None # node likely to only contain single load_control asset, so should be str
            },
            'connections': [
                {
                    'node': 'N1',
                    'line': 'L1'
                },
                {
                    'node': 'N3',
                    'line': 'L1'
                }
            ]
        },
        { # node 3
            'node_id': 'N3',
            'pcc': True,
            'slack': False, 
            'load_id': 'pf_pv_node3',
            'ders': { 
                'pv_id': None,
                'pv_maxS': 1200,
                'battery': 'pf_bat_node3', 
                'genset': 'pf_gen_node3',
                'load_control': None
            },
            'connections': [
                {
                    'node': 'N2',
                    'line': 'L1'
                }
            ]
        },
        { # node 4
            'node_id': 'N4',
            'pcc': True,
            'slack': False, 
            'load_id': 'pf_demand_node4',
            'ders': { 
                'pv_id': 'pf_pv_node4',
                'pv_maxS': 1000,
                'battery': 'pf_bat_node4', 
                'genset': 'pf_gen_node4',
                'load_control': 'testLc4'
            },
            'connections': [
                {
                    'node': 'N1',
                    'line': 'L2'
                },
                {
                    'node': 'N5',
                    'line': 'L3'
                }
            ]
        },
        { # node 5
            'node_id': 'N5',
            'pcc': True,
            'slack': False, 
            'load_id': 'pf_demand_node5',
            'ders': { 
                'pv_id': 'pf_pv_node5',
                'pv_maxS': 1500,
                'battery': 'pf_bat_node5', 
                'genset': 'pf_gen_node5',
                'load_control': None
            },
            'connections': [
                {
                    'node': 'N4',
                    'line': 'L3'
                }
            ]
        }
    ]
    
    parameter['network']['lines'] = [ # list of dicts define each cable/line properties
        {
            'line_id': 'L1',
            'power_capacity': 3500, # line power capacity only used for simple power=exchange
            
            'length': 1200, # line length in meters
            'resistance': 4.64e-6, # line properties are all in pu, based on SBase/VBase defined above
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'L2',
            'power_capacity': 3500,
            
            'length': 1800,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'L3',
            'power_capacity': 3500,
            
            'length': 900,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        }
    ]
    
    return parameter

def create_test_input(parameter):
    
    # create data ts for each node
    data2 = example.ts_inputs(parameter, load='B90', scale_load=700, scale_pv=300)
    data3 = example.ts_inputs(parameter, load='B90', scale_load=1200, scale_pv=1200)
    data4 = example.ts_inputs(parameter, load='B90', scale_load=1500, scale_pv=1000)
    data5 = example.ts_inputs(parameter, load='B90', scale_load=2000, scale_pv=1500)
    
    # use data1 as starting point for multinode df
    data = data2.copy()
    
    # drop load and pv from multinode df
    data = data.drop(labels='load_demand', axis=1)
    data = data.drop(labels='generation_pv', axis=1)
    
    # add node specifc load and pv (where applicable)
    data['pf_demand_node2'] = data2['load_demand']
    data['pf_demand_node3'] = data3['load_demand']
    data['pf_demand_node4'] = data4['load_demand']
    data['pf_demand_node5'] = data5['load_demand']
    
    data['pf_pv_node2'] = data2['generation_pv']
    data['pf_pv_node3'] = data3['generation_pv']
    data['pf_pv_node4'] = data4['generation_pv']
    data['pf_pv_node5'] = data5['generation_pv'] 
    
    return data

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
        self.__class__.expObjective = 160000
        self.__class__.objTolerance = self.expObjective * self.tolerance
        
        
    def runOptimization(self):
        '''
        run optimization and store outputs as attributes of the class

        '''

        def control_model(inputs, parameter):
            model = base_model(inputs, parameter)
            model = add_network(model, inputs, parameter)
            # model = add_battery(model, inputs, parameter)
            
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
        parameter = create_test_parameter()
        data = create_test_input(parameter)
    
        # generate standard output data
        output_list = default_output_list(parameter)
    
        
        # Define the path to the solver executable
        solver_path = get_solver('cbc', solver_dir=os.path.join(get_root(), 'solvers'))
        
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
        
    # check that objective is close to expected objective value
    def test_obj_tolerance(self):
        self.assertAlmostEqual(self.objective, self.expObjective, msg='objective does not match expected with 5%', delta=self.objTolerance)
        
    # check that model contains key pyomo vars as attributes
    def test_pyomo_has_voltage(self):
        self.assertTrue(hasattr(self.model, 'voltage_real'), msg='pyomo model is missing key var: voltage_real')
        
    def test_pyomo_has_current(self):
        self.assertTrue(hasattr(self.model, 'real_branch_cur'), msg='pyomo model is missing key var: real_branch_cur')
        
    def test_pyomo_has_current_square(self):
        self.assertTrue(hasattr(self.model, 'real_branch_cur_square'), msg='pyomo model is missing key var: real_branch_cur_square')


if __name__ == '__main__':
    unittest.main()