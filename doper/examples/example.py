#!/usr/bin/env python

import numpy as np
import pandas as pd
import math
import os


# Example data for running SINGLE-NODE models (development)

def default_parameter():
    parameter = {}
    parameter['system'] = {
        'pv': True,
        'battery':False,
        'genset':False,
        'load_control': False,
        'external_gen': False,
        'reg_bidding': False,
        'reg_response':False,
        'hvac_control': False,
    }

    parameter['fuels'] = [
        {
            'name': 'ng',
            'unit': 'therms',
            'rate': 3.93, # $/therm
            'conversion': 30.77, # kWh/therm
            'co2': 5.3, # kg/therm
            'reserves': 0 # therm
        },
        {
            'name': 'diesel',
            'unit': 'gallons',
            'rate': 3.4, # $/gal
            'conversion': 35.75, # kWh/gal  
            'co2': 10.18, # kg/gal 
            'reserves': 100 # gal  
        }    
    ]
    parameter['tariff'] = {}
    if False:
        parameter['tariff']['energy'] = {0:0.2,1:0.3,2:0.5} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand'] = {0:1,1:2,2:3} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand_coincident'] = 0.5 # $/kW for coincident
        parameter['tariff']['export'] = {0:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    else:
        parameter['tariff']['energy'] = {0:0.08671, 1:0.11613, 2:0.16055} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand'] = {0:0, 1:5.40, 2:19.65} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand_coincident'] = 17.74 # $/kW for coincident
        parameter['tariff']['export'] = {0:0.01} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    
    parameter['site'] = {}
    parameter['site']['customer'] = 'Commercial' # Type of customer [commercial or none]; decides if demand charge
    parameter['site']['regulation'] = False # Enables or disables the regulation bidding
    parameter['site']['regulation_min'] = None # Minial regulation bid
    parameter['site']['regulation_all'] = False # All batteries must participate in regulation
    parameter['site']['regulation_symmetric'] = False # Symmetric bidding into regulation market
    parameter['site']['regulation_xor_building'] = False # For each battery only allow regulaiton or building support
    parameter['site']['regulation_xor'] = False # Only allows bids for regup or regdown per timestep
    parameter['site']['regulation_reserved'] = False # Flag to reserve site capacity for regulation
    parameter['site']['regulation_reserved_battery'] = False # Flag to reserve battery capacity for regulation
    parameter['site']['regulation_reserved_variable_battery'] = False # Flag to reserve battery capacity for regulation (variable ts)
    parameter['site']['import_max'] = 10000 # kW
    parameter['site']['export_max'] = 10000 # kW
    parameter['site']['demand_periods_prev'] = {0:0,1:0,2:0} # kW peak previously set for periods 0-offpeak, 1-midpeak, 2-onpeak
    parameter['site']['demand_coincident_prev'] = 0 # kW peak previously set for coincident
    parameter['site']['input_timezone'] = -8 # Timezone of inputs (in hourly offset from UTC)
    parameter['site']['local_timezone'] = 'America/Los_Angeles' # Local timezone of tariff (as Python timezone string)   
    parameter['controller'] = {}
    parameter['controller']['timestep'] = 60*60 # Controller timestep in seconds
    parameter['controller']['horizon'] = 24*60*60 # Controller horizon in seconds  
    parameter['controller']['solver_dir'] = 'solvers' # Controller solver directory
      
    parameter['objective'] = {}
    parameter['objective']['weight_energy'] = 1 # Weight of tariff (energy) cost in objective
    parameter['objective']['weight_fuel'] = 1 # Weight of fuel (energy) cost in objective
    parameter['objective']['weight_demand'] = 1 # Weight of tariff (demand) cost in objective
    parameter['objective']['weight_export'] = 1 # Weight of revenue (export) in objective
    parameter['objective']['weight_regulation'] = 1 # Weight of revenue (regulation) in objective
    parameter['objective']['weight_degradation'] = 1 # Weight of battery degradation cost in objective
    
    parameter['objective']['weight_co2'] = 0 # Weight of co2 emissions (kg) cost in objective
    parameter['objective']['weight_load_shed'] = 1 # Weight of shed load costs ($/kWh)  in objective
    return parameter


def parameter_add_battery(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        {
         'name':'libat01',
        'capacity': 200,
         'degradation_endoflife': 80,
         'degradation_replacementcost': 6000.0,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'nominal_V':  400,
         'power_charge': 50,
         'power_discharge': 50,
         'maxS': 50,
         'self_discharging': 0.0,
          'soc_final': None,
         'soc_initial': 0.65,
         'soc_max': 1,
         'soc_min': 0.2,
         # 'temperature_initial': 22.0,
         'thermal_C': 100000.0,
         'thermal_R': 0.01
        }
    ]
    
    return parameter


def parameter_add_genset(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['genset'] = True
    
    # Add genset options
    parameter['gensets'] = [
        {
            'capacity': 60, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.25,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'genset_1'
        },
        {
            'capacity': 80, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.30,
            'fuel': 'diesel',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'genset_2'
        } 
    ]

    return parameter


def parameter_add_loadcontrol(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['load_control'] = True
    
    # Add genset options
    parameter['load_control'] = [        
        {
            'name': 'a',
            'cost': 0.05, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'b',
            'cost': 0.3, # $/kWh not served
            'outageOnly': False
        } 
    ]

    return parameter


def parameter_add_evfleet(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        {
         'name': 'EV1',
        'capacity': 24,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 15,
         'power_discharge': 15,
         'maxS': 15,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.75,
         'soc_max': 1,
         'soc_min': 0
        },
        {
        'name': 'EV2',
        'capacity': 24,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 15,
         'power_discharge': 15,
         'maxS': 15,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.80,
         'soc_max': 1,
         'soc_min': 0
        },
        {
        'name': 'EV3',
        'capacity': 54,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 30,
         'power_discharge': 30,
         'maxS': 30,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.75,
         'soc_max': 1,
         'soc_min': 0
        }
    ]

    return parameter


# Example data for running MULTI-NODE models (development)   
    
def parameter_add_network(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # Add nodes and line options
    parameter['network'] = {}
    
    parameter['network']['settings'] = {
        'simpleNetworkLosses': 0.05,
        
        # powerflow options
        'enablePowerFlow': True, # if false, use simple power exchange
        'enableLoadVAR': False, # not implemented yet
        'enablePreOptPQLimit': False, # not implemented yet
        'enableGenPQLimit': False, # not implemented yet
        'dcNetwork': False, # not implemented yet
        
        # powerflow parameters
        'slackBusVoltage': 1,
        'sBase': 6,
        'vBase': 1,
        'cableDerating': 1,
        'txDerating': 1,
        
        # power factors
        'electricity': 1,
        'batteryCharging': 1,
        'batteryDischarging': 1,
        'gensets': 1,
        'pv': 1,
        
        # powerflow model settings
        'enableVoltConst': 1,
        'enableCurConst': 1,
        'enableLosses': 1,
        'thetaMin': -0.18,
        'thetaMax': 0.09,
        'voltMin': 0.8,
        'voltMax': 1.1,
        'conservativeVoltMin': 0,
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
            'pcc': False,
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
            'power_capacity': 3500,
            # other line props for real power flow model
            'length': 1200,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'L2',
            'power_capacity': 3500,
            # other line props for real power flow model
            'length': 1800,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'L3',
            'power_capacity': 3500,
            # other line props for real power flow model
            'length': 900,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'line_01', # str unique id for line
            'power_capacity': 2900, # currently simplified line capacity parameter for dev/testing
            # other line props for real power flow model
            'length': 500,
            'resistance': 6.43e-6,
            'inductance': 8.68e-7,
            'ampacity': 2900,
        },
        {
            'line_id': 'line_02',
            'power_capacity': 3500,
            # other line props for real power flow model
            'length': 1200,
            'resistance': 4.64e-6,
            'inductance': 8.33e-7,
            'ampacity': 3500,
        },
        {
            'line_id': 'line_03',
            'power_capacity': 4000,
            # other line props for real power flow model
            'length': 1600,
            'resistance':3.44e-6,
            'inductance': 7.98e-7,
            'ampacity': 4000,
        }
    ]

    return parameter


def parameter_add_battery_multinode(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = parameter_add_network_test()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        # {
        #   'name':'testBat1A',
        # 'capacity': 1200,
        #   'degradation_endoflife': 80,
        #   'degradation_replacementcost': 6000.0,
        #   'efficiency_charging': 0.96,
        #   'efficiency_discharging': 0.96,
        #   'nominal_V':  400,
        #   'power_charge': 400,
        #   'maxS': 400,
        #   'power_discharge': 400,
        #   'self_discharging': 0.001,
        #   'soc_final': 0.5,
        #   'soc_initial': 0.5,
        #   'soc_max': 1,
        #   'soc_min': 0.2,
        #   # 'temperature_initial': 22.0,
        #   'thermal_C': 100000.0,
        #   'thermal_R': 0.01
        # },
        # {
        # 'name':'testBat1B',
        # 'capacity': 800,
        #   'degradation_endoflife': 80,
        #   'degradation_replacementcost': 6000.0,
        #   'efficiency_charging': 0.96,
        #   'efficiency_discharging': 0.96,
        #   'nominal_V':  400,
        #   'power_charge': 200,
        #   'power_discharge': 200,
        #   'maxS': 200,
        #   'self_discharging': 0.001,
        #   'soc_final': 0.5,
        #   'soc_initial': 0.5,
        #   'soc_max': 1,
        #   'soc_min': 0.2,
        #   'temperature_initial': 22.0,
        #   'thermal_C': 100000.0,
        #   'thermal_R': 0.01
        # },
        # {
        #   'name':'testBat2',
        # 'capacity': 900,
        #   'degradation_endoflife': 80,
        #   'degradation_replacementcost': 6000.0,
        #   'efficiency_charging': 0.96,
        #   'efficiency_discharging': 0.96,
        #   'nominal_V':  400,
        #   'power_charge': 300,
        #   'power_discharge': 300,
        #   'maxS': 300,
        #   'self_discharging': 0.001,
        #   'soc_final': 0.5,
        #   'soc_initial': 0.5,
        #   'soc_max': 1,
        #   'soc_min': 0.2,
        #   # 'temperature_initial': 22.0,
        #   'thermal_C': 100000.0,
        #   'thermal_R': 0.01
        # },
        # {
        # 'name':'testBat3',
        # 'capacity': 500,
        #   'degradation_endoflife': 80,
        #   'degradation_replacementcost': 6000.0,
        #   'efficiency_charging': 0.96,
        #   'efficiency_discharging': 0.96,
        #   'nominal_V':  400,
        #   'power_charge': 125,
        #   'power_discharge': 125,
        #   'maxS': 125,
        #   'self_discharging': 0.001,
        #   'soc_final': 0.5,
        #   'soc_initial': 0.5,
        #   'soc_max': 1,
        #   'soc_min': 0.2,
        #   'temperature_initial': 22.0,
        #   'thermal_C': 100000.0,
        #   'thermal_R': 0.01
        # }
        {
          'name':'pf_bat_node2',
          'capacity': 500,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 150,
          'maxS': 150,
          'power_discharge': 150,
          'self_discharging': 0.001,
           'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
          'name':'pf_bat_node3',
          'capacity': 1000,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 350,
          'maxS': 350,
          'power_discharge': 350,
          'self_discharging': 0.001,
           'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
          'name':'pf_bat_node4',
          'capacity': 1000,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 350,
          'maxS': 350,
          'power_discharge': 350,
          'self_discharging': 0.001,
           'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
          'name':'pf_bat_node5',
          'capacity': 1000,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 350,
          'maxS': 350,
          'power_discharge': 350,
          'self_discharging': 0.001,
           'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
    ]

    return parameter


def parameter_add_genset_multinode(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['genset'] = True
    
    # Add genset options
    parameter['gensets'] = [
        # {
        #     'capacity': 200, #nameplate output kW
        #     'maxS': 200,
        #     'backupOnly': False,
        #     'efficiency': 0.33,
        #     'fuel': 'ng',
        #     'omVar': 0.01, #$/kWh O&M costs
        #     'maxRampUp': 0.5,
        #     'maxRampDown': 0.5,
        #     'timeToStart': 1,
        #     'regulation': False,
        #     'name': 'testGen1'
        # },
        # {
        #     'capacity': 200, #nameplate output kW
        #     'maxS': 200,
        #     'backupOnly': True,
        #     'efficiency': 0.30,
        #     'fuel': 'diesel',
        #     'omVar': 0.01, #$/kWh O&M costs
        #     'maxRampUp': 0.5,
        #     'maxRampDown': 0.5,
        #     'timeToStart': 1,
        #     'regulation': False,
        #     'name': 'testGen4A'
        # },
        # {
        #     'capacity': 200, #nameplate output kW
        #     'maxS': 200,
        #     'backupOnly': True,
        #     'efficiency': 0.30,
        #     'fuel': 'diesel',
        #     'omVar': 0.01, #$/kWh O&M costs
        #     'maxRampUp': 0.5,
        #     'maxRampDown': 0.5,
        #     'timeToStart': 1,
        #     'regulation': False,
        #     'name': 'testGen4B'
        # },
        # {
        #     'capacity': 1000, #nameplate output kW
        #     'maxS': 1000,
        #     'backupOnly': True,
        #     'efficiency': 0.25,
        #     'fuel': 'ng',
        #     'omVar': 0.01, #$/kWh O&M costs
        #     'maxRampUp': 0.5,
        #     'maxRampDown': 0.5,
        #     'timeToStart': 1,
        #     'regulation': False,
        #     'name': 'genset_1'
        # },
        {
            'capacity': 250, #nameplate output kW
            'maxS': 250,
            'backupOnly': False,
            'efficiency': 0.33,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'pf_gen_node3'
        },
        {
            'capacity': 500, #nameplate output kW
            'maxS': 500,
            'backupOnly': False,
            'efficiency': 0.33,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'pf_gen_node4'
        },
        {
            'capacity': 500, #nameplate output kW
            'maxS': 500,
            'backupOnly': False,
            'efficiency': 0.33,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'pf_gen_node5'
        },
    ]

    return parameter
    

def parameter_add_loadcontrol_multinode(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['load_control'] = True
    
    # Add genset options
    parameter['load_control'] = [        
        {
            'name': 'testLc1A',
            'cost': 0.25, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'testLc1B',
            'cost': 0.05, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'testLc4',
            'cost': 0.1, # $/kWh not served
            'outageOnly': False
        } 
    ]

    return parameter


# Testing Example data for running SINGLE-NODE models (unittesting)
# Changing the parameters below without updating unit tests may cause tests to fail

def test_default_parameter():
    parameter = {}
    parameter['system'] = {
        'pv': True,
        'battery':False,
        'genset':False,
        'load_control': False,
        'reg_bidding': False,
        'reg_response':False,
        'hvac_control': False,
        'external_gen': False
    }

    parameter['fuels'] = [
        {
            'name': 'ng',
            'unit': 'therms',
            'rate': 3.93, # $/therm
            'conversion': 30.77, # kWh/therm
            'co2': 5.3, # kg/therm
            'reserves': 0 # therm
        },
        {
            'name': 'diesel',
            'unit': 'gallons',
            'rate': 3.4, # $/gal
            'conversion': 35.75, # kWh/gal  
            'co2': 10.18, # kg/gal 
            'reserves': 100 # gal  
        }    
    ]
    parameter['tariff'] = {}
    if False:
        parameter['tariff']['energy'] = {0:0.2,1:0.3,2:0.5} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand'] = {0:1,1:2,2:3} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand_coincident'] = 0.5 # $/kW for coincident
        parameter['tariff']['export'] = {0:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    else:
        parameter['tariff']['energy'] = {0:0.08671, 1:0.11613, 2:0.16055} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand'] = {0:0, 1:5.40, 2:19.65} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
        parameter['tariff']['demand_coincident'] = 17.74 # $/kW for coincident
        parameter['tariff']['export'] = {0:0.01} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    
    parameter['site'] = {}
    parameter['site']['customer'] = 'Commercial' # Type of customer [commercial or none]; decides if demand charge
    parameter['site']['regulation'] = False # Enables or disables the regulation bidding
    parameter['site']['regulation_min'] = None # Minial regulation bid
    parameter['site']['regulation_all'] = False # All batteries must participate in regulation
    parameter['site']['regulation_symmetric'] = False # Symmetric bidding into regulation market
    parameter['site']['regulation_xor_building'] = False # For each battery only allow regulaiton or building support
    parameter['site']['regulation_xor'] = False # Only allows bids for regup or regdown per timestep
    parameter['site']['regulation_reserved'] = False # Flag to reserve site capacity for regulation
    parameter['site']['regulation_reserved_battery'] = False # Flag to reserve battery capacity for regulation
    parameter['site']['regulation_reserved_variable_battery'] = False # Flag to reserve battery capacity for regulation (variable ts)
    parameter['site']['import_max'] = 10000 # kW
    parameter['site']['export_max'] = 20 # kW
    parameter['site']['demand_periods_prev'] = {0:0,1:0,2:0} # kW peak previously set for periods 0-offpeak, 1-midpeak, 2-onpeak
    parameter['site']['demand_coincident_prev'] = 0 # kW peak previously set for coincident
    parameter['site']['input_timezone'] = -8 # Timezone of inputs (in hourly offset from UTC)
    parameter['site']['local_timezone'] = 'America/Los_Angeles' # Local timezone of tariff (as Python timezone string)   
    parameter['controller'] = {}
    parameter['controller']['timestep'] = 60*60 # Controller timestep in seconds
    parameter['controller']['horizon'] = 24*60*60 # Controller horizon in seconds  
    parameter['controller']['solver_dir'] = 'solvers' # Controller solver directory
      
    parameter['objective'] = {}
    parameter['objective']['weight_energy'] = 1 # Weight of tariff (energy) cost in objective
    parameter['objective']['weight_fuel'] = 1 # Weight of fuel (energy) cost in objective
    parameter['objective']['weight_demand'] = 1 # Weight of tariff (demand) cost in objective
    parameter['objective']['weight_export'] = 1 # Weight of revenue (export) in objective
    parameter['objective']['weight_regulation'] = 1 # Weight of revenue (regulation) in objective
    parameter['objective']['weight_degradation'] = 1 # Weight of battery degradation cost in objective
    
    parameter['objective']['weight_co2'] = 0 # Weight of co2 emissions (kg) cost in objective
    parameter['objective']['weight_load_shed'] = 1 # Weight of shed load costs ($/kWh)  in objective
    return parameter


def test_parameter_add_battery(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        {
         'name':'libat01',
        'capacity': 200,
         'degradation_endoflife': 80,
         'degradation_replacementcost': 6000.0,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'nominal_V':  400,
         'power_charge': 50,
         'power_discharge': 50,
         'maxS': 50,
         'self_discharging': 0.0,
          'soc_final': 0.8,
         'soc_initial': 0.3,
         'soc_max': 1,
         'soc_min': 0.2,
         # 'temperature_initial': 22.0,
         'thermal_C': 100000.0,
         'thermal_R': 0.01
        }
    ]
    
    return parameter


def test_parameter_add_genset(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['genset'] = True
    
    # Add genset options
    parameter['gensets'] = [
        {
            'capacity': 60, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.25,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'genset_1'
        },
        {
            'capacity': 80, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.30,
            'fuel': 'diesel',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'genset_2'
        } 
    ]

    return parameter


def test_parameter_add_loadcontrol(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['load_control'] = True
    
    # Add genset options
    parameter['load_control'] = [        
        {
            'name': 'a',
            'cost': 0.05, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'b',
            'cost': 0.3, # $/kWh not served
            'outageOnly': False
        } 
    ]

    return parameter


def test_parameter_add_evfleet(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        {
        'capacity': 24,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 15,
         'power_discharge': 15,
         'maxS': 15,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.5,
         'soc_max': 1,
         'soc_min': 0
        },
        {
        'capacity': 24,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 15,
         'power_discharge': 15,
         'maxS': 15,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.25,
         'soc_max': 1,
         'soc_min': 0
        },
        {
        'capacity': 54,
         'efficiency_charging': 0.96,
         'efficiency_discharging': 0.96,
         'power_charge': 30,
         'power_discharge': 30,
         'maxS': 30,
         'self_discharging': 0.003,
         # 'soc_final': 0.5,
         'soc_initial': 0.5,
         'soc_max': 1,
         'soc_min': 0
        }
    ]

    return parameter



# Testing Example data for running MULTI-NODE models (unittesting)
# Changing the parameters below without updating unit tests may cause tests to fail

def parameter_add_network_test(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # Add nodes and line options
    parameter['network'] = {}
    
    parameter['network']['settings'] = {
        'simpleNetworkLosses': 0.05, 
        'simplePowerExchange': True
    }
    
    parameter['network']['nodes'] = [ # list of dict to define inputs for each node in network
        { # node 1
            'node_id': 'TestNode1PCC', # unique str to id node
            'pcc': True, # bool to define if node is pcc
            'slack': True, 
            'load_id': 'test_load_demand_1', # str, list of str, or None to find load profile in ts data (if node is load bus) by column label
            'ders': { # dict of der assets at node, if None or not included, no ders present
                'pv_id': None, # str, list, or None to find pv profile in ts data (if pv at node) by column label
                'battery': ['testBat1A', 'textBat1B'], # list of str corresponding to battery assets (defined in parameter['system']['battery'])
                'genset': 'testGen1', # list of str correponsing to genset assets (defined in parameter['system']['genset'])
                'load_control': ['testLc1A', 'testLc1B'] # str, list or None correponsing to genset assets (defined in parameter['system']['load_control'])
            },
            'connections': [ # list of connected nodes, and line connecting them
                {
                    'node': 'TestNode2', # str containing unique node_id of connected node
                    'line': 'line_01' # str containing unique line_id of line connection nodes, (defined in parameter['network']['lines'])
                },
                {
                    'node': 'TestNode4',
                    'line': 'line_02'
                }
            ]
        },
        { # node 2
            'node_id': 'TestNode2',
            'pcc': False,
            'slack': False, 
            'load_id': ['test_load_demand_2'],
            'ders': { 
                'pv_id': ['test_generation_pv_2'],
                'battery': 'textBat2', # node can contain multiple battery assets, so should be list
                'genset': None,
                'load_control': None # node likely to only contain single load_control asset, so should be str
            },
            'connections': [
                {
                    'node': 'TestNode1PCC',
                    'line': 'line_01'
                },
                {
                    'node': 'TestNode3',
                    'line': 'line_03'
                }
            ]
        },
        { # node 3
            'node_id': 'TestNode3',
            'pcc': False,
            'slack': False, 
            'load_id': 'test_load_demand_3',
            'ders': { 
                'pv_id': None,
                'battery': 'testBat3', 
                'genset': 'testGen3',
                'load_control': None
            },
            'connections': [
                {
                    'node': 'TestNode2',
                    'line': 'line_03'
                }
            ]
        },
        { # node 4
            'node_id': 'TestNode4',
            'pcc': False,
            'slack': False, 
            'load_id': 'test_load_demand_4',
            'ders': { 
                'pv_id': ['test_generation_pv_4'],
                'battery': None, 
                'genset': 'testGen4',
                'load_control': 'testLc4'
            },
            'connections': [
                {
                    'node': 'TestNode1PCC',
                    'line': 'line_02'
                }
            ]
        }
    ]
    
    parameter['network']['lines'] = [ # list of dicts define each cable/line properties
        {
            'line_id': 'line_01', # str unique id for line
            'power_capacity': 1500, # currently simplified line capacity parameter for dev/testing
            # other line props for real power flow model
            'length': 55,
            'resistance': 0,
            'inductance': 0,
            'ampacity': 0,
        },
        {
            'line_id': 'line_02',
            'power_capacity': 1500,
            # other line props for real power flow model
            'length': 120,
            'resistance': 0,
            'inductance': 0,
            'ampacity': 0,
        },
        {
            'line_id': 'line_03',
            'power_capacity': 1300,
            # other line props for real power flow model
            'length': 500,
            'resistance': 0,
            'inductance': 0,
            'ampacity': 0,
        }
    ]

    return parameter


def parameter_add_battery_multinode_test(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = parameter_add_network_test()
    
    # enable gensets
    parameter['system']['battery'] = True
    
    # Add genset options
    parameter['batteries'] = [
        {
          'name':'testBat1A',
        'capacity': 1200,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 400,
          'maxS': 400,
          'power_discharge': 400,
          'self_discharging': 0.001,
          'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
        'name':'testBat1B',
        'capacity': 800,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 200,
          'power_discharge': 200,
          'maxS': 200,
          'self_discharging': 0.001,
          'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
          'name':'testBat2',
        'capacity': 900,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 300,
          'power_discharge': 300,
          'maxS': 300,
          'self_discharging': 0.001,
          'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          # 'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        },
        {
        'name':'testBat3',
        'capacity': 500,
          'degradation_endoflife': 80,
          'degradation_replacementcost': 6000.0,
          'efficiency_charging': 0.96,
          'efficiency_discharging': 0.96,
          'nominal_V':  400,
          'power_charge': 125,
          'power_discharge': 125,
          'maxS': 125,
          'self_discharging': 0.001,
          'soc_final': 0.5,
          'soc_initial': 0.5,
          'soc_max': 1,
          'soc_min': 0.2,
          'temperature_initial': 22.0,
          'thermal_C': 100000.0,
          'thermal_R': 0.01
        }
    ]

    return parameter


def parameter_add_genset_multinode_test(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['genset'] = True
    
    # Add genset options
    parameter['gensets'] = [
        {
            'capacity': 200, #nameplate output kW
            'backupOnly': False,
            'efficiency': 0.33,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'testGen1'
        },
        {
            'capacity': 200, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.30,
            'fuel': 'diesel',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'testGen4A'
        },
        {
            'capacity': 200, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.30,
            'fuel': 'diesel',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'testGen4B'
        },
        {
            'capacity': 1000, #nameplate output kW
            'backupOnly': True,
            'efficiency': 0.25,
            'fuel': 'ng',
            'omVar': 0.01, #$/kWh O&M costs
            'maxRampUp': 0.5,
            'maxRampDown': 0.5,
            'timeToStart': 1,
            'regulation': False,
            'name': 'genset_1'
        },
    ]

    return parameter
    

def parameter_add_loadcontrol_multinode_test(parameter=None):
    if parameter is None:
        # if no parameter given, load default
        parameter = default_parameter()
    
    # enable gensets
    parameter['system']['load_control'] = True
    
    # Add genset options
    parameter['load_control'] = [        
        {
            'name': 'testLc1A',
            'cost': 0.25, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'testLc1B',
            'cost': 0.05, # $/kWh not served
            'outageOnly': False
        },
        {
            'name': 'testLc4',
            'cost': 0.1, # $/kWh not served
            'outageOnly': False
        } 
    ]

    return parameter

# Timeseries Input Example Creation Funcs
    

def ts_inputs(parameter={}, load='Flexlab', scale_load=4, scale_pv=4):
    #scale = 1
    #scale = 30 
    if load == 'Flexlab':
        data = pd.read_csv(os.path.join(root_dir, 'ExampleData', 'Flexlab.csv'))
        data.index = pd.to_datetime(data['Date/Time'].apply(lambda x: '2018/'+x[1:6]+' '+'{:2d}'.format(int(x[8:10])-1)+x[10::]))
        del data.index.name
        data = data[['FLEXLAB-X3-ZONEA:Zone Air Heat Balance System Air Transfer Rate [W](Hourly)']]
        data.columns = ['load_demand']
        #data['load_demand'] = data['load_demand'].mask(data['load_demand']<0, data['load_demand']*-1/3.5) / 1000.
        data['load_demand'] = data['load_demand'].mask(data['load_demand']<0, data['load_demand']*-1/2.) / 1000.
        # Use only 1 day
        data = data.iloc[0:24]
        data['load_demand'] = data['load_demand']/data['load_demand'].max()
    elif load =='B90':
        data = pd.DataFrame(index=pd.date_range(start='2019-01-01 00:00', end='2019-01-01 23:00', freq='H'))
        data['load_demand'] = [2.8,  2.8,  2.9,  2.9,  3. ,  3.3,  4. ,  4.8,  4.9,  5.1,  5.3,
                               5.4,  5.4,  5.4,  5.3,  5.3,  5.2,  4.8,  3.9,  3.1,  2.9,  2.8,
                               2.8,  2.8]
        data['load_demand'] = data['load_demand']/data['load_demand'].max()
    # Scale Load data
    data['load_demand'] = data['load_demand'] * scale_load
    # Mode of OAT
    data['oat'] = np.sin(data.index.view(np.int64)/(1e12*np.pi*4))*3 + 22
    # Makeup Tariff
    data['tariff_energy_map'] = 0
    data['tariff_energy_map'] = data['tariff_energy_map'].mask((data.index.hour>=8) & (data.index.hour<22), 1)
    data['tariff_energy_map'] = data['tariff_energy_map'].mask((data.index.hour>=12) & (data.index.hour<18), 2)
    data['tariff_power_map'] = data['tariff_energy_map'] # Apply same periods to demand charge
    data['tariff_energy_export_map'] = 0
    data['generation_pv'] = 0
    data.loc[data.index[8:19], 'generation_pv'] = [np.sin(i/(10/(np.pi))) for i in range(11)]
    data['generation_pv'] = data['generation_pv'] * scale_pv
    data['tariff_regup'] = data['tariff_power_map'] * 0.05 + 0.01
    data['tariff_regdn'] = data['tariff_power_map'] * 0.01 + 0.01
    data['battery_reg'] = 0
    
    data['date_time'] = data.index
    # Resample
    if True:
        data = data.resample('5T').asfreq()
        for c in data.columns:
            if c in ['load_demand','generation_pv','oat']:
                data[c] = data[c].interpolate()
            else:
                data[c] = data[c].ffill()
        data = data.loc['2019-01-01 00:00:00':'2019-01-02 00:00:00']
    else:
        data = data.loc['2019-01-01 00:00:00':'2019-01-02 00:00:00']
    #data.index = data.index.astype(int)/1000000000
    #data = data.reset_index(drop=True)
    
    # input timeseries indicating grid availability
    data['grid_available'] = 1
    data['fuel_available'] = 1
    
    # input timeseries indicating grid availability
    data['grid_co2_intensity'] = 0.202 #kg/kWh
    return data
    
    return data

def ts_inputs_ev_schedule(parameter, data):
    
    # add randome schedules for battery availability and external load
    
    for b in range(len(parameter['batteries'])):
        np.random.seed(b)
        data['battery_{!s}_avail'.format(b)] = np.random.choice(2, len(data.index), p=[0.25, 0.75])
        np.random.seed(b+15)
        data['battery_{!s}_demand'.format(b)] = -1 * (data['battery_{!s}_avail'.format(b)] - 1) \
                                                * np.random.uniform(low=0.5, high=2.5, size=len(data.index))
    return data

    
def ts_inputs_offgrid(parameter):
    # load default data
    data = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    # overwrite grid availability to disable grid connection
    data['grid_available'] = 0
    
    return data


def ts_inputs_planned_outage(parameter, data=None):
    if data is None:
        # load default data
        data = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    
    # determine number of rows
    nrows = data.shape[0]
    # start outage in middle (integer)
    outageRow = nrows//2
    
    # overwrite grid availability to disable grid connection
    for ii in range(nrows):
        if ii > outageRow:
            data.at[data.index[ii], 'grid_available'] = 0
    
    return data


def ts_inputs_variable_co2(parameter, data=None, scaling=[1,2,1]):
    '''
    Modifies the input data (timeseries dataset) grid co2 intensity by
    applying the given scaling factors to equal portions of the time-horizon,
    based on the number of scaling factors provided in the input

    Parameters
    ----------
    parameter : TYPE
        DESCRIPTION.
    data : TYPE, optional
        DESCRIPTION. The default is None.
    scaling : List, optional
        List of scaling factors to apply to the grid co2 intenisty. 
        The default is [1,2,1].

    Returns
    -------
    data : pandas df

    '''
    if data is None:
        # load default data
        data = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    else:
        data = data.copy(deep=True)
    
    # determine number of rows
    nrows = data.shape[0]

    # define base co2 intesity
    baseCo2 = 0.202
    
    # determine number of scaling factors
    nScale = len(scaling)
    
    
    # overwrite grid availability to disable grid connection
    for ii in range(nrows):
        
        # determine which index to use for scaling
        scaleIndex = math.floor(ii/nrows*nScale)
        # print(f'for ts: {ii} or {nrows}, use scale index: {scaleIndex}')
        
        # apply the scaling factor
        data.at[data.index[ii], 'grid_co2_intensity'] = baseCo2 * scaling[scaleIndex]
    
    return data


def ts_inputs_fueloutage(parameter, data=None):
    if data is None:
        # load default data
        data = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    
    # determine number of rows
    nrows = data.shape[0]
    # start outage in middle (integer)
    outageRow = nrows//2
    
    # overwrite grid availability to disable grid connection
    for ii in range(nrows):
        if ii > outageRow:
            data.at[data.index[ii], 'fuel_available'] = 0
    
    return data


def ts_inputs_load_shed(parameter, data=None):
    if data is None:
        # load default data
        data = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
        
    # overwrite grid availability to disable grid connection
    data['load_shed_potential_a'] = 0.3 * data['load_demand']
    data['load_shed_potential_b'] = 0.15 * data['load_demand']
    
    # del data['load_demand']
    
    return data


def ts_inputs_load_shed_multinode_test(parameter, data):
        
    # overwrite grid availability to disable grid connection
    data['load_shed_potential_testLc1A'] = 0.3 * data['test_load_demand_1']
    data['load_shed_potential_testLc1B'] = 0.15 * data['test_load_demand_1']
    data['load_shed_potential_testLc4'] = 0.3 * data['test_load_demand_4']
    
    # del data['load_demand']
    
    return data


def ts_inputs_multinode(parameter, data=None):
    '''
    

    func to create example 4-node load and pv profiles

    '''
    
    
    # create data ts for each node
    data1 = ts_inputs(parameter, load='B90', scale_load=400, scale_pv=0)
    data2 = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    data3 = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=0)
    data4 = ts_inputs(parameter, load='B90', scale_load=80, scale_pv=300)
    
    # use data1 as starting point for multinode df
    data = data1.copy()
    
    # drop load and pv from multinode df
    data = data.drop(labels='load_demand', axis=1)
    data = data.drop(labels='generation_pv', axis=1)
    
    # add node specifc load and pv (where applicable)
    data['load_demand_1'] = data1['load_demand']
    data['load_demand_2'] = data2['load_demand']
    data['load_demand_3'] = data3['load_demand']
    data['load_demand_4'] = data4['load_demand']
    
    data['generation_pv_2'] = data2['generation_pv']
    data['generation_pv_4'] = data4['generation_pv']  
    
    return data

def ts_inputs_multinode_test(parameter, data=None):
    '''
    

    func to create example 4-node load and pv profiles

    '''
    
    
    # create data ts for each node
    data1 = ts_inputs(parameter, load='B90', scale_load=400, scale_pv=0)
    data2 = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
    data3 = ts_inputs(parameter, load='B90', scale_load=150, scale_pv=0)
    data4 = ts_inputs(parameter, load='B90', scale_load=80, scale_pv=300)
    
    # use data1 as starting point for multinode df
    data = data1.copy()
    
    # drop load and pv from multinode df
    data = data.drop(labels='load_demand', axis=1)
    data = data.drop(labels='generation_pv', axis=1)
    
    # add node specifc load and pv (where applicable)
    data['test_load_demand_1'] = data1['load_demand']
    data['test_load_demand_2'] = data2['load_demand']
    data['test_load_demand_3'] = data3['load_demand']
    data['test_load_demand_4'] = data4['load_demand']
    
    data['test_generation_pv_2'] = data2['generation_pv']
    data['test_generation_pv_4'] = data4['generation_pv']  
    
    return data

def ts_inputs_multinode_pf(parameter, data=None):
    '''
    

    func to create example 4-node load and pv profiles

    '''
    
    
    # create data ts for each node
    data2 = ts_inputs(parameter, load='B90', scale_load=700, scale_pv=300)
    data3 = ts_inputs(parameter, load='B90', scale_load=1200, scale_pv=1200)
    data4 = ts_inputs(parameter, load='B90', scale_load=1500, scale_pv=1000)
    data5 = ts_inputs(parameter, load='B90', scale_load=2000, scale_pv=1500)
    
    # use data1 as starting point for multinode df
    data = data2.copy()
    
    # drop load and pv from multinode df
    data = data.drop(labels='load_demand', axis=1)
    data = data.drop(labels='generation_pv', axis=1)
    
    # add node specifc load and pv (where applicable)
    data['test__demand_node2'] = data2['load_demand']
    data['pf_demand_node3'] = data3['load_demand']
    data['pf_demand_node4'] = data4['load_demand']
    data['pf_demand_node5'] = data5['load_demand']
    
    data['pf_pv_node2'] = data2['generation_pv']
    data['pf_pv_node3'] = data3['generation_pv']
    data['pf_pv_node4'] = data4['generation_pv']
    data['pf_pv_node5'] = data5['generation_pv'] 
    
    return data


if __name__ == '__main__':
    #parameter = default_parameter()
    parameter = parameter_add_evfleet()

    #data = ts_inputs(parameter)
    data = ts_inputs_ev_schedule(parameter)
    
    # print(data.index)