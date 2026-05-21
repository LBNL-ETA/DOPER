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
import shutil
import logging
import platform
import subprocess as sp
import numpy as np
import pandas as pd
from packaging import version
from copy import deepcopy

from .examples.example import (default_parameter,
                               parameter_add_genset,
                               parameter_add_battery,
                               parameter_add_loadcontrol)

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
                d[k, c] = int(v) if v % 1 == 0 else float(v)
    elif isinstance(df, pd.Series):
        for k,v in df.items():
            d[k] = int(v) if v % 1 == 0 else float(v)
    else:
        print('The data must be a pd.DataFrame (for multiindex) or pd.Series (single index).')
    return d


def unpack_ts_input(inputs, colName, default=None, required=True, as_string=False):
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
        vals = pandas_to_dict(inputs[colName])
        if as_string:
            vals = {k: str(v) for k, v in vals.items()}
        return vals
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

def get_solver(solver, solver_dir=None):
    '''
        Utility to return the solverpath readable for Pyomo.
    '''
    solver_path = None
    if not solver_dir:
        solver_dir = os.path.join(get_root(), 'solvers')
        # first try locally
        solver_path = shutil.which(solver)

    # otherwise try doper solvers
    if not solver_path:
        system = platform.system()
        bit = '64' if sys.maxsize > 2**32 else '32'
        if system == 'Windows':
            solver_path = os.path.join(solver_dir, 'Windows'+bit, solver+'.exe')
        solver_path = os.path.join(solver_dir, 'Linux'+bit, solver)

    return solver_path

def check_solver(solver='cbc'):
    sol = get_solver(solver)
    if os.path.exists(sol):
        return

    logging.info(f'The default "{solver}" solver was not properly installed at "{sol}". '
                    + 'Attempting automatic solver setup.')

    try:
        from .solvers.install import install_solvers
        install_solvers()
    except Exception as e:
        logging.warning(f'Automatic solver setup failed due to: {e}. '
                        + 'Need to manually set the "solver_path" and "solver_name" '
                        + 'when calling DOPER.')
        return

    sol = get_solver(solver)
    if not os.path.exists(sol):
        logging.warning(f'Automatic solver setup completed, but solver "{solver}" was still '
                        + f'not found at "{sol}". Need to manually set the "solver_path" '
                        + 'and "solver_name" when calling DOPER.')
        
    logging.info(f'The solver was installed.')

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
    shift = int(reduced_ts / data_ts / 2) # shift by half to align periods

    data_temp = data.copy(deep=True)
    data2 = data.loc[reduced_start_ix:].shift(shift).resample(f'{reduced_ts}min',
        offset=f'{reduced_start}min').asfreq().copy(deep=True)

    for c in data2.columns:
        if c in cols_fill:
            data2[c] = data.loc[reduced_start_ix-pd.DateOffset(minutes=reduced_ts):, c].shift( \
                shift).resample(f'{reduced_ts}min',
                                offset=f'{reduced_start}min').ffill()
        else:
            data2[c] = data.loc[reduced_start_ix-pd.DateOffset(minutes=reduced_ts):, c].shift( \
                shift).resample(f'{reduced_ts}min',
                                offset=f'{reduced_start}min').mean()

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

def update_nested_dict(base, updates):
    """Recursively update dict values with nested keys."""
    for key, value in updates.items():
        if isinstance(value, dict):
            if key not in base or not isinstance(base.get(key), dict):
                base[key] = deepcopy(value)
            else:
                update_nested_dict(base[key], value)
        else:
            base[key] = value

def make_config(cfg):
    # get basic config
    parameter = default_parameter()

    # update systems only
    if cfg.get("system", {}):
        parameter["system"].update(cfg["system"])

    # add model specific config
    if cfg.get("system", {}).get("battery"):
        parameter = parameter_add_battery(parameter)
    if cfg.get("system", {}).get("genset"):
        parameter = parameter_add_genset(parameter)
    if cfg.get("system", {}).get("load_control"):
        parameter = parameter_add_loadcontrol(parameter)
    
    # update full config
    update_nested_dict(parameter, cfg)

    return parameter

# Results processing
def default_output_list(parameter):
    
    output_list = [
        {
            'name': 'gridImport',
            'data': 'grid_import_site',
            'df_label': 'Import Power [kW]'
        },
        {
            'name': 'gridExport',
            'data': 'grid_export_site',
            'df_label': 'Export Power [kW]'
        },
        {
            'name': 'siteLoad',
            'data': 'load_served_site',
            'df_label': 'Load Power [kW]'
        },
        {
            'name': 'tariffEnergyPeriod',
            'data': 'tariff_energy_map',
            'df_label': 'Tariff Energy Period [-]'
        },
        {
            'name': 'tariffPowerPeriod',
            'data': 'tariff_power_map',
            'df_label': 'Tariff Power Period [-]'
        },
        {
            'name': 'outsideTemp',
            'data': 'outside_temperature',
            'df_label': 'Temperature [C]'
        }
    ]
    
    # optional entry for pv
    if parameter['system']['pv']:
        output_list +=  [
            {
                'name': 'pvPower',
                'data': 'generation_pv_site',
                'df_label': 'PV Power [kW]'
            }
        ]
        
    # optional entry for batteries
    if parameter['system']['battery']:
        output_list +=  [
            {
                'name': 'batCharge',
                'data': 'sum_battery_charge_grid_power_site',
                'df_label': 'Battery Charging Power [kW]'
            },
            {
                'name': 'batDisharge',
                'data': 'sum_battery_discharge_grid_power_site',
                'df_label': 'Battery Discharging Power [kW]'
            },
            {
                'name': 'batSOC',
                'data': 'battery_agg_soc',
                'df_label': 'Battery Aggregate SOC [-]'
            }
        ]
    
    # optional entry for gensets
    if parameter['system']['genset']:
        output_list +=  [
            {
                'name': 'gensetPower',
                'data': 'sum_genset_power_site',
                'df_label': 'Genset Power [kW]'
            }
        ]
        
    # optional entry for load control
    if parameter['system']['load_control']:
        output_list +=  [
            {
                'name': 'load_shed_site',
                'data': 'load_shed_site',
                'df_label': 'Total Shed Load [kW]'
            }
        ]
        
    # need to add optinal entries for batteries and reg modes
    
    return output_list


# Results processing
def dev_output_list(parameter):
    
    output_list = [
        {
            'name': 'gridImport',
            'data': 'grid_import_site',
            'df_label': 'gridImport_site'
        },
        {
            'name': 'gridExport',
            'data': 'grid_export_site',
            'df_label': 'gridExport_site'
        },
        {
            'name': 'siteLoad',
            'data': 'load_served_site',
            'df_label': 'load_site'
        }
    ]
    
    # optional entry for pv
    if parameter['system']['pv']:
        output_list +=  [
            {
                'name': 'pvPower',
                'data': 'generation_pv_site',
                'df_label': 'pvGen_site'
            }
        ]
        
    # optional entry for batteries
    if parameter['system']['battery']:
        output_list +=  [
            {
                'name': 'batCharge',
                'data': 'sum_battery_charge_grid_power_site',
                'df_label': 'batCharge_site'
            },
            {
                'name': 'batDisharge',
                'data': 'sum_battery_discharge_grid_power_site',
                'df_label': 'batDischarge_site'
            }
        ]
    
    # optional entry for gensets
    if parameter['system']['genset']:
        output_list +=  [
            {
                'name': 'gensetPower',
                'data': 'sum_genset_power_site',
                'df_label': 'genset_site'
            }
        ]
        
    # optional entry for load control
    if parameter['system']['load_control']:
        output_list +=  [
            # {
            #     'name': 'load_total_shed',
            #     'data': 'load_total_shed',
            #     'df_label': 'Total Shed Load [kW]'
            # }
        ]
        
    # need to add optinal entries for batteries and reg modes
    
    # entries for node values
    output_list += [
        {
            'name': 'gridImport',
            'data': 'grid_import',
            'index': 'nodes',
            'df_label': 'gridImport_'
        },
        {
            'name': 'gridExport',
            'data': 'grid_export',
            'index': 'nodes',
            'df_label': 'gridExport_'
        },
        {
            'name': 'loadServed',
            'data': 'load_served',
            'index': 'nodes',
            'df_label': 'load_'
        },
        {
            'name': 'pvGen',
            'data': 'generation_pv',
            'index': 'nodes',
            'df_label': 'pvGen_'
        },
        {
            'name': 'powerInj',
            'data': 'powerExchangeOut',
            'index': 'nodes',
            'df_label': 'powerInj_'
        },
        {
            'name': 'powerAbs',
            'data': 'powerExchangeIn',
            'index': 'nodes',
            'df_label': 'powerAbs_'
        },
        {
            'name': 'gensetGen',
            'data': 'sum_genset_power',
            'index': 'nodes',
            'df_label': 'genset_'
        },
        {
            'name': 'batCharge',
            'data': 'sum_battery_charge_grid_power',
            'index': 'nodes',
            'df_label': 'batCharge_'
        },
        {
            'name': 'batDisharge',
            'data': 'sum_battery_discharge_grid_power',
            'index': 'nodes',
            'df_label': 'batDischarge_'
        }
    ]
    
    if 'network' in parameter.keys():
        if not parameter['network']['settings']['simplePowerExchange']:
            # add node voltages if power-flow model is enabled
            output_list += [
                {
                    'name': 'voltage_real',
                    'data': 'voltage_real',
                    'index': 'nodes',
                    'df_label': 'voltageReal_'
                },
                {
                    'name': 'voltage_imag',
                    'data': 'voltage_imag',
                    'index': 'nodes',
                    'df_label': 'voltageImag_'
                },
            ]
    
    return output_list

def generate_summary_metrics(model):
    '''
    

    Returns
    -------
        summary (dict): dictionary of metrics related to economic and energy results

    '''
    
    summary = {
        'cost': {},
        'energy': {},
        'power': {}
    }
    
    summary['cost']['total'] = model.objective.expr()
    summary['cost']['elec_energy'] = model.sum_energy_cost.value
    summary['cost']['elec_demand'] = model.sum_demand_cost.value
    summary['cost']['fuelcost_ng'] = 0
    summary['cost']['fuelcost_diesel'] = 0
    summary['cost']['load_curtail'] = None
    summary['cost']['export_rev'] = model.sum_export_revenue.value
    summary['cost']['reg_rev'] = model.sum_regulation_revenue.value
    
    summary['energy']['load'] = model.objective.expr()
    summary['energy']['pv_gen'] = model.objective.expr()
    summary['energy']['genset_gen'] = model.objective.expr()
    summary['energy']['batt_charge'] = model.objective.expr()
    summary['energy']['batt_discharge'] = model.objective.expr()
    summary['energy']['exported'] = model.objective.expr()
    summary['energy']['curtailed_load'] = model.objective.expr()
    summary['energy']['ng_used'] = model.objective.expr()
    summary['energy']['diesel_used'] = model.objective.expr()
    
    summary['power']['peak_load'] = model.objective.expr()
    summary['power']['peak_import'] = model.objective.expr()
    summary['power']['peak_export'] = model.objective.expr()
    
    return summary
