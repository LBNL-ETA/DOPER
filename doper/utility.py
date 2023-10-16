# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Utility module.
"""

# pylint: disable=invalid-name, import-outside-toplevel, bare-except, dangerous-default-value
# pylint: disable=unused-variable, too-many-arguments, chained-comparison

import os
import sys
import logging
import platform
import subprocess as sp
import numpy as np
import pandas as pd
from packaging import version

def fix_bug_pyomo():
    """Fix bug in pyomo when intializing solver (timeout after 5s)"""
    from importlib import reload
    import pyomo
    path_pyomo = os.path.dirname(pyomo.__file__)
    path_pyomo_asl = os.path.join(path_pyomo, 'solvers', 'plugins', 'solvers', 'ASL.py')
    if os.path.exists(path_pyomo_asl):
        with open(path_pyomo_asl, 'r', encoding='utf8') as f:
            pyomo_asl = f.read()
        if '[solver_exec, "-v"]' in pyomo_asl:
            pyomo_asl = pyomo_asl.replace('[solver_exec, "-v"]', '[solver_exec, "-v", "exit"]')
            try: 
                with open(path_pyomo_asl, 'w', encoding='utf8') as f:
                    f.write(pyomo_asl)
            except Exception as e:
                print(f'WARNING: pyomo solver bug was not fixed by doper due to: {e}')
        elif '[solver_exec, "-v", "exit"]' in pyomo_asl:
            pass
        else:
            raise ValueError('The snippet [solver_exec, "-v"] does not exist' + \
                f' in Pyomo ASL.py at {path_pyomo_asl}.')
    else:
        raise ValueError(f'The Pyomo ASL.py file does not exist at {path_pyomo_asl}.')
    reload(pyomo)

def get_root(f=None):
    """get the root location"""
    try:
        if not f:
            f = __file__
        root = os.path.dirname(os.path.abspath(f))
    except:
        root = os.getcwd()
    return root

def download_cbc(cbc_version='2.10.8', root=get_root()):
    """helper function to download cbc solver"""
    cbc_repo = 'https://github.com/coin-or/Cbc/releases/download/releases%2F'
    if version.parse(cbc_version) < version.parse('2.10.9'):
        fname = f'Cbc-releases.{cbc_version}-x86_64-ubuntu18-gcc750-static.tar.gz'
    else:
        fname = f'Cbc-releases.{cbc_version}-x86_64-ubuntu20-gcc940-static.tar.gz'
    cmd = 'rm -rf tmp_solvers && mkdir tmp_solvers && cd tmp_solvers'
    cmd += f'&& wget -q {cbc_repo}{cbc_version}/{fname}'
    cmd += f' && tar -xvzf {fname}'
    cmd += f' && rm {fname}'
    cmd += f' && mv bin/cbc ../cbc_{cbc_version}'
    cmd += ' && cd .. && rm -rf tmp_solvers'
    sp.check_output(cmd, shell=True, cwd=root)
    return os.path.join(root, f'cbc_{cbc_version}')

def pandas_to_dict(df, columns=None, convertTs=False):
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

    if convertTs:
        # convert timestamp index to unix time
        df.index = df.index.view(np.int64)/1e9

    if isinstance(df, pd.DataFrame):
        df = df.copy(deep=True)
        if columns:
            df.columns = columns
        for c in df.columns:
            for k,v in df[c].items():
                d[k,c] = int(v) if v % 1 == 0 else float(v)
    elif isinstance(df, pd.Series):
        for k,v in df.items():
            d[k] = int(v) if v % 1 == 0 else float(v)
    else:
        print('The data must be a pd.DataFrame (for multiindex) or pd.Series (single index).')
    return d


def unpack_ts_input(inputs, colName, default=None, required=True):
    '''
    function attempts to unpack timeseries inputs using:
    inputs - timeseries input dataframe.
    colName - name of column in inputs to extract (may not exist).
    default - value to use for input if colName is not found in inputs.
    required - flag if input is required.

    returns dict that can be used as Pyomo param initialize argument
    '''                       
        
    # attempt to load colName from inputs df
    if colName in inputs.columns: 
        return pandas_to_dict(inputs[colName])
    # otherwise return default, if provided        
    elif default is not None:
        if required:
            logging.info(f'{colName} missing from input. Default value = {default}')
        return default
    # otherwise, raise error (required input is missing)
    else:
        raise ValueError(f'Required field: "{colName}" missing from input.')



def add_second_index(dataDict, newIndex):
    '''
    function addes a static second key to dataDict.
    Needed for when intializing node-indexed data for single-node models
    applied to output of pandas_to_dict function for load and pv profiles

    Parameters
    ----------
    dataDict : dict
        1-d dictionary produced by panads_to_dict function (above).
    newIndex : TYPE
        DESCRIPTION.

    Returns
    -------
    dict
        2-d dict with newIndex added as second key
        e.g. (key1) -> (key1, {newIndex})
    '''

    # initilize new dict
    dataDict2 = {}

    #loop through keys, added second static key
    for key in dataDict.keys():
        dataDict2[key, newIndex] = dataDict[key]

    return dataDict2

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

def get_solver(solver, solver_dir=os.path.join(get_root(), 'solvers')):
    '''
        Utility to return the solverpath readable for Pyomo.
    '''
    system = platform.system()
    bit = '64' if sys.maxsize > 2**32 else '32'
    if system == 'Windows':
        return os.path.join(solver_dir, 'Windows'+bit, solver+'.exe')
    return os.path.join(solver_dir, 'Linux'+bit, solver)
    
def check_solver(solver='cbc'):
    sol = get_solver(solver)
    if not os.path.exists(sol):
        logging.warning(f'The default "cbc" solver was not properly installed at "{sol}". ' \
                        + 'Need to manually set the "solver_path" and "solver_name" ' \
                        + 'when calling DOPER.')

def extract_properties(parameter, tech_name, prop_name, set_list=None):
    '''
    Parameters
    ----------
    parameter : dict
        full input parameter dict.
    tech_name : str
        name of technology type (e.g. 'gensets') from where property is extracted.
    prop_name : str
        name of property extracted from each technology item
    set_list : list or None
        list of strs representing set item names

    Returns
    -------
    dataDict : TYPE
        DESCRIPTION.
    '''
    # if no set list is provided, extract data and assingn to numeric index
    if set_list is None:
        n = len(parameter[tech_name])
        data = parameter[tech_name]
        dataDict = { ii : data[ii][prop_name] for ii in range(n) }
    # if set list is provided, use values of set list to extract data using name as dict key
    else:
        dataDict = {}
        for pp in parameter[tech_name]:
            dataDict[pp['name']] = pp[prop_name]
    return dataDict

def resample_variable_ts(data, reduced_start=60, reduced_ts=30, cols_fill=[]):
    '''
    data (pandas.DataFrame): The input dataframe.
    reduced_start (int): Time offset when variable ts starts, in minutes. (default=60)
    reduced_ts (int): Resampled timestep for reduced ts, in minutes. (default=60)
    cols_fill (list): Columns which require ffill method instead of mean. (default=[])
    '''
    if 'date_time' in data.keys():
        del data['date_time']
    # Resample Data
    reduced_start_ix = data.index[0]+pd.DateOffset(minutes=reduced_start)
    data_ts = (data.index[1] - data.index[0]).total_seconds()/60 # minutes
    #shift = int(reduced_ts / data_ts / 2) # shift by half
    shift = 0

    data_temp = data.copy(deep=True)
    data2 = data.loc[reduced_start_ix:].shift(shift).resample(f'{reduced_ts}T',
        offset=f'{reduced_start}T').asfreq().copy(deep=True)

    for c in data2.columns:
        if c in cols_fill:
            data2[c] = data.loc[reduced_start_ix-pd.DateOffset(minutes=reduced_ts):, c].shift( \
                shift).resample(f'{reduced_ts}T',
                                offset=f'{reduced_start}T').ffill()
        else:
            data2[c] = data.loc[reduced_start_ix-pd.DateOffset(minutes=reduced_ts):, c].shift( \
                shift).resample(f'{reduced_ts}T',
                                offset=f'{reduced_start}T').mean()

    data = pd.concat([data.loc[:reduced_start_ix-pd.DateOffset(minutes=data_ts)],
                      data2.loc[reduced_start_ix:]],
                     sort=True)
    data = data.iloc[:-1]
    data.loc[data_temp.index[-1]] = data_temp.loc[data_temp.index[-1]]
    return data

def standard_report(res, only_solver=False):
    """standard report for simulaiton result"""
    duration, objective, df, model, result, termination, parameter = res
    output = ''
    try:
        msg = ' '.join(result['Solver'][0]['Message'].split(' ')[:2])
        output += f'Solver\t\t\t{msg}\n'
    except:
        pass
    output += f'Duration [s]\t\t{round(duration, 2)}\n'
    if not only_solver and objective:
        output += f'Objective [$]\t\t{round(objective, 2)}\t\t\t'
        output += f'{round(model.total_cost.value, 2)} (Total Cost)\n'
        ce = round(model.sum_energy_cost.value * parameter['objective']['weight_energy'], 2)
        cd = round(model.sum_demand_cost.value * parameter['objective']['weight_demand'], 2)
        output += f'Cost [$]\t\t{ce} (Energy)\t{cd} (Demand)\n' \
        # model.sum_degradation_cost.value * parameter['objective']['weight_degradation'], 2))
        # model.sum_export_revenue.value * parameter['objective']['weight_export'], 2), \
        # model.sum_regulation_revenue.value * parameter['objective']['weight_regulation'], 2))
        output += f'CO2 Emissions [kg]\t\t{round(model.co2_total.value, 2)}\n'
        #output += str(round(df[['Reg Revenue [$]']].sum().values[0], 2))
    return output

def plot_streams(axs, temp, title=None, ylabel=None, legend=False, loc=1, times=[8,12,18,22]):
    '''
        Utility to simplify plotting of subplots.

        Input
        -----
            axs (matplotlib.axes._subplots.AxesSubplot): The axis to be plotted.
            temp (pandas.Series): The stream to be plotted.
            title (str): Title of the plot. (default = None)
            ylabel (str): Label for y-axis. (default = None)
            legend (bool): Show legend in plot. (default = False)
            loc (int): Location of legend. (default = 1)
            times (list): List of tariff times. Four elements. (default = [8,12,18,22])
    '''
    axs.plot(temp)
    axs.legend(temp.columns, loc=2)
    if times:
        idx0 = temp.index[temp.index.minute==0]
        if times[0] is not None:
            axs.plot([idx0[idx0.hour==times[0]],idx0[idx0.hour==times[0]]],
                      [temp.values.min(),temp.values.max()], color='orange', linestyle=':')
        if times[1] is not None:
            axs.plot([idx0[idx0.hour==times[1]],idx0[idx0.hour==times[1]]],
                      [temp.values.min(),temp.values.max()], color='red', linestyle=':')
        if times[2] is not None:
            axs.plot([idx0[idx0.hour==times[2]],idx0[idx0.hour==times[2]]],
                      [temp.values.min(),temp.values.max()], color='red', linestyle=':')
        if times[3] is not None:
            axs.plot([idx0[idx0.hour==times[3]],idx0[idx0.hour==times[3]]],
                      [temp.values.min(),temp.values.max()], color='orange', linestyle=':')
        if temp.values.min() < 0 and temp.values.max() > 0:
            axs.plot([idx0[0],idx0[-1]],[0,0], color='black', linestyle=':')
    if title:
        axs.set_title(title)
    if ylabel:
        axs.set_ylabel(ylabel)
    if legend:
        axs.legend(legend, loc=loc)

def constructNodeInput(inputDf, colParam, nodeColName):
    '''
    Parameters
    ----------
    inputDf : pandas df
        timeseries input dataframe.
    colParam : None, list, or str
        str or list of strings with column names to be used for new node input sereies.
    nodeColName : str
        name of new node-specific input sereies to be added to timeseries input df.

    Returns
    -------
    inputDf: pandas df with new node input defined and appended to existing df
    '''

    if colParam is None:
        # if colParam is set to None in input, default pv profile to 0
        inputDf[nodeColName] = 0
    elif isinstance(colParam, str):
        # if single colParam (i.e. str) is provided, set directly as column
        inputDf[nodeColName] = inputDf[colParam]
    elif isinstance(colParam, list):
        # if multiple colParam (i.e. list) vals are provided provided, sum, then set as col
        inputDf[nodeColName] = inputDf[colParam].sum(axis=1)
    return inputDf

def mapExternalGen(parameter, data, model):
    '''
    function to extract external generation profiles from ts-data file based on data
    in the parameter dict.
    
    for multinode models, function will map generation profile to node-location

    Parameters
    ----------
    parameter : dict
        full model parameter input dict.
    data : df
        full model ts data dataframe.
    model : pyomo model
        full pyomo model, containing necessary indices: model.ts, model.nodes

    Returns
    -------
    ext_power_dict - dict indexed by (ts, node) with power profile
    '''

    # check if external_gen flag is present in param
    if 'external_gen' not in parameter['system'].keys():
        logging.info('external generation flag not found. default to 0.')
        return 0

    # check if external_gen flag is enabled
    if not parameter['system']['external_gen']:
        return 0

    # if not multinode, look for column 'external_gen' in ts-data
    if not model.multiNode:
        # convert load and pv ts-data into dicts with single-node name as second index
        singleNodeLabel = model.nodes.ordered_data()[0]
        ext_power_dict = add_second_index(pandas_to_dict(data['external_gen']), singleNodeLabel)
    else:
        # initilize list of new node-based inputs columns in ts df
        exGenNodeList = []

        for nn, node in enumerate(parameter['network']['nodes']):
            # Construct LOAD inputs
            # create new column for aggregate pv for each node
            genColName = f'external_gen_{node["node_id"]}'
            # check if 'load_id' in node inputs
            if 'external_gen' not in node['ders'].keys():
                # if load_id is not provided in input, default profile to 0
                data[genColName] = 0
            else:
                data = constructNodeInput(data, node['ders']['external_gen'], genColName)
            exGenNodeList.append(genColName)
        # convert df cols to dict
        ext_power_dict = pandas_to_dict(data[exGenNodeList],  columns=model.nodes)
    return ext_power_dict
