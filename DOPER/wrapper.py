#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Optimization Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''

from time import time
import pandas as pd
import logging
import copy
from pyomo.opt import SolverFactory, TerminationCondition

logger = logging.getLogger(__name__)
    
class DOPER(object):
    def __init__(self, model=None, parameter=None, solver_path='ipopt', pyomo_to_pandas=None,
                 singnal_handle=False, debug=False):
        '''
            Initialization function of the DOPER package.

            Input
            -----
                model (function): The optimization model as a pyomo.environ.ConcreteModel function.
                parameter (dict): Configuration dictionary for the optimization. (default=None)
                solver_path (str): Full path to the solver. (default='ipopt')
                pyomo_to_pandas (function): The function to convert the model output to a 
                    pandas.DataFrame. (default=None)
                singnal_handle (bool): Flag to turn on the Python signal handling. It is recommended to
                    use False in multiprocessing applications. (default=False)
                debug (bool): Flag to enable debug mode. (default=False)
        '''
        if model:
            if type(model) == type(lambda x:x):
                self.model = model
            else:
                logger.error('The model is a type {%s}, not a type {!s}'.format \
                             (type(pyomo_to_pandas), type(lambda x:x)))
        else:
            logger.error('No model funciton supplied. Please supply a pyomo.environ.ConcreteModel object.')
        self.model_loaded = False
        self.parameter = copy.deepcopy(parameter)
        self.solver_path = solver_path
        if pyomo_to_pandas:
            if type(pyomo_to_pandas) == type(lambda x:x):
                self.pyomo_to_pandas = pyomo_to_pandas
            else:
                logger.error('The pyomo_to_pandas is a type {%s}, not a type {!s}'.format \
                             (type(pyomo_to_pandas), type(lambda x:x)))
        else:
            logger.warning('No pyomo_to_pandas function supplied. No output dataframe will be processed.')
            self.pyomo_to_pandas = None
        self.singnal_handle = singnal_handle
        self.debug = debug
        
        self.signal_handling_toggle()
        
    def signal_handling_toggle(self):
        '''
            Toggle the Python signal handling. 
            
            It is recommended to use disable signal handling in multiprocessing applications. But
            this can lead to memory leak and Zombie processes.
        '''
        import pyutilib.subprocess.GlobalData
        pyutilib.subprocess.GlobalData.DEFINE_SIGNAL_HANDLERS_DEFAULT = self.singnal_handle
        
    def initialize_model(self, data):
        '''
            Loads the model with its parameters.
            
            Input
            -----
                data (pandas.DataFrame): The input dataframe for the optimization.
        '''
        self.model = self.model(data, self.parameter)
        self.model_loaded = True
            
    def do_optimization(self, data, parameter=None, tee=False, options={}):
        '''
            Integrated function to conduct the optimization for control purposes.

            Input
            -----
                data (pandas.DataFrame): The input dataframe for the optimization.
                parameter (dict): Configuration dictionary for the optimization. (default=None)
                tee (bool): Prints the solver output. (default=False)
                options (dict): Options to be set for solver. (default={})

            Returns
            -------
                duration (float): Duration of the optimization.
                objective (float): Value of the objective function.
                df (pandas.DataFrame): The resulting dataframe with the optimization result.
                model (pyomo.environ.ConcreteModel): The optimized model.
                result (pyomo.opt.SolverFactory): The optimization result object.
                termination (str): Termination statement of optimization.
        '''
        if parameter:
            # Update parameter, if supplied
            self.parameter = copy.deepcopy(parameter)        
        if not self.model_loaded:
            # Instantiate the model, if not already
            self.initialize_model(data)
        with SolverFactory(self.solver_path) as solver:
            t_start = time()
            for k in options.keys():
                solver.options[k] = options[k]
            result = solver.solve(self.model, load_solutions=False, tee=tee)
            termination = result.solver.termination_condition
            if termination != TerminationCondition.optimal:
                logger.warning('Solver did not report optimality:\n{!s}'.format(result.solver))
            self.model.solutions.load_from(result)
            objective = self.model.objective()
            if self.pyomo_to_pandas:
                df = self.pyomo_to_pandas(self.model, self.parameter)
            else:
                df = pd.DataFrame()

        return [time()-t_start, objective, df, self.model, result, termination]