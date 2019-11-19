#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Utility Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''

import os
import sys
import platform
import pandas as pd

def pandas_to_dict(df, columns=None):
    '''
        Utility function to translate a pandas dataframe in a Python dictionary.

        Input
        -----
            df (pandas.Series): The series to be converted.

        Returns
        -------
            d (dict): Python dictionary with the series input.
    '''
    d = {}
    if isinstance(df, pd.DataFrame):
        df = df.copy(deep=True)
        if columns: df.columns = columns
        for c in df.columns:
            for k,v in df[c].iteritems():
                d[k,c] = int(v) if v % 1 == 0 else float(v)
    elif isinstance(df, pd.Series):
        for k,v in df.iteritems():
            d[k] = int(v) if v % 1 == 0 else float(v)
    else:
        print('The data must be a pd.DataFrame (for multiindex) or pd.Series (single index).')
    return d

def pyomo_read_parameter(temp):
    '''
        Utility to read pyomo objects and return the content.

        Input
        -----
            temp (pyomo.core.base.param.IndexedParam): The object ot be parsed.
            
        Returns
        -------
            d (dict): The parsed data as dictionary.

    '''
    d = {}
    for k,v in zip(temp.keys(), temp.values()):
        d[k] = v
    return d
    
def get_solver(solver, solver_dir='Solvers'):
    '''
        Utility to return the solverpath readable for Pyomo.
    '''
    system = platform.system()
    bit = '64' if sys.maxsize > 2**32 else '32'
    if system == 'Windows': return os.path.join(solver_dir, system+bit, solver+'.exe')
    else: return os.path.join(root_dir, solver_dir, system+bit, solver)