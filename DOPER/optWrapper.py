import sys
import os
import logging
import pandas as pd
import numpy as np
import json
from fmlc import eFMU
from pyomo.environ import Objective, minimize

# import optimization modules
from wrapper import DOPER
from utility import get_solver, get_root, standard_report
from basemodel import base_model, plot_standard1, plot_pv_only, plot_dynamic, default_output_list
from battery import add_battery
from genset import add_genset
from loadControl import add_loadControl
from example import (example_inputs, example_parameter_add_genset, 
                    example_inputs_offgrid, example_inputs_planned_outage, 
                    example_parameter_add_battery, example_parameter_add_loadcontrol, 
                    example_inputs_load_shed, example_inputs_fueloutage, example_inputs_variable_co2)



class OptimizationWrapper(eFMU):
    def __init__(self):
        self.input = {
            'timeseries-data': None, #json-ized df of timeseries input data
            'parameter-data': None, # dict of model/setting parameters
            'output-list': None, # list of dict of output instructions for custom ouputs
        }      
        
        self.output = {
            'opt-summary': None,
            'output-data': None,
        }
        
        # initialize input attributes
        self.tsInputs = None
        self.modelParams = None
        self.userOutputs = None
        
        # initialize internal attributes
        self.model = None
        self.results = None
        self.outputList = None
        self.solverPath  = None
        
        # initialize output attributes
        self.duration = None
        self.objective = None
        self.termination = None
        self.tsResults = None
        self.modelPyomo = None
        self.resultPyomo = None
        
        self.tsResultsJson = None
        self.optSummary = None
        
        self.msg = None
        
        
    def construct_model_function(self, inputs, parameter):
        '''
        method returns a function for constructing an optimization model,
        used by Doper wrapper to run optimization.
        
        dynamically constructs pyomo model based on content of parameters['system']
        
        constructs objective for all current costs, using the weight values
        in parameter['objective']

        Parameters
        ----------
        inputs : pandas df
            timeseries data input for optimization model.
        parameter : dict
            dict defining system and parameters.

        Returns
        -------
        func
            function to construct optimization model

        '''
        
        
        def control_model(inputs, parameter):
            # construct pyomo model based on assets included in parameters
            model = base_model(inputs, parameter)
            if parameter['system']['battery']:
                model = add_battery(model, inputs, parameter)
            if parameter['system']['genset']:
                model = add_genset(model, inputs, parameter)
            if parameter['system']['load_control']:
                model = add_loadControl(model, inputs, parameter)
            
            # construct objective function based on weights include in parameters
            def objective_function(model):
                return model.sum_energy_cost * parameter['objective']['weight_energy'] \
                       + model.sum_demand_cost * parameter['objective']['weight_demand'] \
                       + model.sum_export_revenue * parameter['objective']['weight_export'] \
                       + model.sum_regulation_revenue * parameter['objective']['weight_regulation'] \
                       + model.fuel_cost_total * parameter['objective']['weight_fuel'] \
                       + model.load_shed_cost_total * parameter['objective']['weight_load_shed'] \
                       + model.co2_total * parameter['objective']['weight_co2'] \
                       
            
            model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
            
            return model
        
        return control_model
        
       
    def compute(self):
        
        # initialize msg to return
        self.msg = None
        self.errorFlag = False
        
        # unpack inputs
        self.tsInputs = self.input['timeseries-data']
        self.modelParams = self.input['parameter-data']
        self.userOutputs = self.input['output-list']
        
        # initialize model objects to empty values
        self.model = None
        self.results = None
        self.duration = None
        self.objective = None
        self.termination = None
        self.tsResults = None
        self.modelPyomo = None
        self.resultPyomo = None
        self.tsResultsJson = None
        self.optSummary = {
            'duration': -1,
            'objective': 0,
            'termination': 'failed' 
        }
        
        
        # try to convert tsInput from json to df
        try:
            self.tsInputs = pd.read_json(self.tsInputs)
        except Exception as e:
            self.msg = 'ERROR: Input processing failed' + str(e)
            self.tsInputs = None
            self.errorFlag = True
            
        
        # check if required inputs have been passed
        if(self.tsInputs is None or self.modelParams is None):
            self.msg = 'Error: required inputs missing'
            self.errorFlag = True
        else:
            try:
                # define model and objective func using construct_model_function method
                self.modelConstructor = self.construct_model_function(self.tsInputs, self.modelParams)
            except Exception as e:
                self.msg = 'ERROR: model contructor failed ' + str(e)
                self.errorFlag = True                
        
        # use user-specfied inputs, if provied
        if self.userOutputs is not None:
            self.outputList = self.userOutputs
        else:
            # otherwise, load default output list
            self.outputList = default_output_list(self.modelParams)

        
        # try to run optimization
        if not self.errorFlag:
            try:
                # Define the path to the solver executable
                self.solverPath = get_solver(self.modelParams['solver']['solver_name'], solver_dir=self.modelParams['solver']['solver_path'])
                
                # Initialize DOPER
                self.model = DOPER(model=self.modelConstructor,
                                 parameter=self.modelParams,
                                 solver_path=self.solverPath ,
                                 output_list=self.outputList)
                
                # Conduct optimization
                self.results = self.model.do_optimization(self.tsInputs)
                
                # Get results
                duration, objective, tsResults, modelPyomo, resultPyomo, termination, parameter = self.results
                
                # extract results and store as attributes
                self.duration = duration
                self.objective = objective
                self.termination = str(termination)
                
                self.tsResults = tsResults
                self.modelPyomo = modelPyomo
                self.resultPyomo = resultPyomo
                
                # process results for self.output
                self.tsResultsJson = self.tsResults.to_json()
                self.optSummary = {
                    'duration': self.duration,
                    'objective': self.objective,
                    'termination': self.termination 
                }

            except Exception as e:
                self.msg = 'ERROR: Optimization failed' + str(e)
            
            
            # pack optimization outputs into self.output
            self.output['opt-summary'] = self.optSummary
            self.output['output-data'] = self.tsResultsJson
        

        # if no msg has been define, default to Done
        if self.msg is None:
             self.msg = 'Done.'
        
        # Return status message
        return self.msg


if __name__ == '__main__':
    
    # set logging
    logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S')

    # define parameter from example module
    parameter = None
    # parameter = example_parameter_evfleet()
    parameter = example_parameter_add_genset(parameter)
    # parameter = example_parameter_add_loadcontrol(parameter)
    parameter = example_parameter_add_battery(parameter)
    
    # add solver name and path to parameter
    parameter['solver'] = {
        'solver_name': 'cbc',
        'solver_path': os.path.join(get_root(), 'solvers')
    }
    
    # define timeseries data from example module
    tsData = example_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    
    # convert df to json
    tsData = tsData.to_json()
    
    # define custom outputs to add
    myOutputs = [{
        'name': 'batSOC',
        'data': 'battery_energy',
        'index': 'batteries',
        'df_label': 'Energy in Battery %s'
    }]
    

    input = {
        'timeseries-data': tsData, #json-ized df of timeseries input data
        'parameter-data': parameter, # dict of model/setting parameters
        'output-list': myOutputs,
    }
    

    # instantiate forecast framework wrapper
    newWrapper = OptimizationWrapper()

    # pass inputs
    newWrapper.input = input

    # run compute method to train and predict
    newWrapper.compute()
    
    print(newWrapper.msg)
    
    print(standard_report(newWrapper.results))
