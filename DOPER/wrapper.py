#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Optimization Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''
import os
import sys
from time import time
import pandas as pd
import logging
import copy
from pyomo.opt import SolverFactory, TerminationCondition

def get_root(f=None):
    try:
        if not f:
            f = __file__
        root = os.path.dirname(os.path.abspath(f))
    except:
        root = os.getcwd()
    return root
root = get_root()

#sys.path.insert(0, os.path.join(root, '..'))
from .utility import pyomo_read_parameter
from .basemodel import default_output_list, generate_summary_metrics

logger = logging.getLogger(__name__)
    
class DOPER(object):
    def __init__(self, model=None, parameter=None, solver_name='', solver_path='ipopt', output_list=None,
                 singnal_handle=False, debug=False, pyomo_logger=logging.WARNING):
        '''
            Initialization function of the DOPER package.

            Input
            -----
                model (function): The optimization model as a pyomo.environ.ConcreteModel function.
                parameter (dict): Configuration dictionary for the optimization. (default=None)
                solver_name (str): Name of the solver. (default='')
                solver_path (str): Full path to the solver. (default='ipopt')
                pyomo_to_pandas (function): The function to convert the model output to a 
                    pandas.DataFrame. (default=None)
                singnal_handle (bool): Flag to turn on the Python signal handling. It is recommended to
                    use False in multiprocessing applications. (default=False)
                debug (bool): Flag to enable debug mode. (default=False)
        '''
        logging.getLogger('pyomo.core').setLevel(pyomo_logger)
        if model:
            if type(model) == type(lambda x:x):
                self._model = model
            else:
                logger.error('The model is a type {%s}, not a type {!s}'.format \
                             (type(model), type(lambda x:x)))
        else:
            logger.error('No model funciton supplied. Please supply a pyomo.environ.ConcreteModel object.')
        self.model_loaded = False
        self.parameter = copy.deepcopy(parameter)
        self.solver_name = solver_name
        self.solver_path = solver_path
        # if pyomo_to_pandas:
        #     if type(pyomo_to_pandas) == type(lambda x:x):
        #         self.pyomo_to_pandas = pyomo_to_pandas
        #     else:
        #         logger.error('The pyomo_to_pandas is a type {%s}, not a type {!s}'.format \
        #                      (type(pyomo_to_pandas), type(lambda x:x)))
        # else:
        #     logger.warning('No pyomo_to_pandas function supplied. No output dataframe will be processed.')
        #     self.pyomo_to_pandas = None
        self.output_list = output_list
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
        self.model = self._model(data, self.parameter)
        self.model_loaded = True
        
    def write_ts_results(self):
        '''
            function dynamicly generates timeseries results dataframe, based on 
            settings defined in parameter['system']
            
            Parameters
            ----------
            model : pyomo.core.base.PyomoModel.ConcreteModel
                solved pyomo model
            parameter : dict
                input parameter dict with 'system' field
            conversion_data: list of dicts
                list of dicts containing instructions
                for which pyomo timeseries params and vars to include in results df
                if none is provided, will be generated automatically
            
            Returns
            -------
            df : pandas.core.frame.DataFrame
                DESCRIPTION.
        
        '''
        
        # list of results data to be extracted
        # name: generic name of data
        # data: var or param object in pyomo model where data is extracted
        # df_label: label to be used for dataframe column
        # isVar: whether data is pyomo param or var
        # include: bool on whether to include data - dynamicly determined from
        #   parameter['system']
        
        model = self.model
        parameter = self.parameter
        output_list = self.output_list
        
        if output_list is None:
            output_list = default_output_list(self.parameter)        
            
        # create empty df indexed by timestamps
        df = pd.DataFrame(model.ts.ordered_data(), columns = ['timestep'])
        df.set_index('timestep',inplace = True)
        
        # iterate through output instructions to add to df
        for outputItem in output_list:
            dfColName = outputItem['df_label'] = outputItem['df_label']
            tsDataDict = getattr(model, outputItem['data']).extract_values()
            # if output is only indexed by timestamp, add to dataframe
            if 'index' not in outputItem.keys():
                # create new df for output item
                itemDf = pd.DataFrame.from_dict(tsDataDict, orient='index', columns=[dfColName])
                # if df is empty, replace with itemDf, else merge with existing df
                # if df.shape[0]==0:
                #     df = itemDf
                # else:
                df = pd.merge(df, itemDf, left_index=True, right_index=True)
                
            else:
                # process data for multi-dim timeseries data
                
                # get items in second index set
                # index2 = list(getattr(model, outputItem['index']).keys())
                index2 = list(getattr(model, outputItem['index']).ordered_data())
                
                # iterate through index 2 values
                for ii in index2:
                    # create indexed column name for df
                    # first try string interpolation
                    try:
                        dfColNameIndexed = dfColName %ii
                    except:
                        # otherwise just append
                        dfColNameIndexed = f'{dfColName}{ii}'
                    # create empty dict
                    dataDictIndexed = {}
                    
                    for val in tsDataDict.items():
                        
                        # check value of second index, if matches ii, add to dict
                        # val is in nested tuple form ((ts, index), value)
                        if val[0][1] == ii:
                            dataDictIndexed[val[0][0]] = val[1]
                            
                    # add new indexed ts dict to main df
                    itemDf = pd.DataFrame.from_dict(dataDictIndexed, orient='index', columns=[dfColNameIndexed])
                    df = pd.merge(df, itemDf, left_index=True, right_index=True)
                
            
        # construct extracted data into pandas dataframe
        # df = pd.DataFrame(df).transpose()
        # df.columns = columns
        df.index = pd.to_datetime(df.index, unit='s')
        
        # add energy price
        if 'Tariff Energy Period [-]' in df.columns:
            df['Tariff Energy [$/kWh]'] = df[['Tariff Energy Period [-]']].replace(pyomo_read_parameter(model.tariff_energy))
        
        self.results_df = df
        
        return df
            
    def do_optimization(self, data, parameter=None, tee=False, options={}, print_error=True):
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
        #if not self.model_loaded:
        # Instantiate the model, if not already
        self.initialize_model(data)
        with SolverFactory(self.solver_name, executable=self.solver_path) as solver:
            t_start = time()
            for k in options.keys():
                solver.options[k] = options[k]
            result = solver.solve(self.model, load_solutions=False, tee=tee)
            termination = result.solver.termination_condition
            if termination == TerminationCondition.optimal and 'cbc' in str(result.solver).lower() and not 'objective' in result.solver.message:
                termination = 'infeasible' # CBC does not report infeasible
            if termination != TerminationCondition.optimal and print_error:
                logger.warning('Solver did not report optimality:\n{!s}'.format(result.solver))
            try:
                self.model.solutions.load_from(result)
            except Exception as e:
                if print_error:
                    logger.warning('Could not load solutions:\n{!s}'.format(e))
            if termination == TerminationCondition.optimal:
                objective = self.model.objective()
                df = self.write_ts_results()
                self.summary = generate_summary_metrics(self.model)
            else:
                objective = None
                df = pd.DataFrame()
            # if self.pyomo_to_pandas and termination == TerminationCondition.optimal:
            #     df = self.pyomo_to_pandas(self.model, self.parameter)
            # else:
            #     df = pd.DataFrame()

        return [time()-t_start, objective, df, self.model, result, termination, self.parameter]
    
    
   
