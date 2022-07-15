#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

'''
import os
import sys
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyomo.environ import ConcreteModel, Set, Param, Var, Constraint, Binary

def get_root(f=None):
    try:
        if not f:
            f = __file__
        root = os.path.dirname(os.path.abspath(f))
    except:
        root = os.getcwd()
    return root
root = get_root()
sys.path.insert(0, os.path.join(root, '..'))
from DOPER.utility import pandas_to_dict, pyomo_read_parameter, plot_streams, get_root, extract_properties    


def add_genset(model, inputs, parameter):
        
    # Check that gensets are enabled
    assert parameter['system']['genset'] is True, \
        "Gensets are not enabled in system configuration"
    
    # list of required genset parameters
    gensetParams =  ['capacity', 'backupOnly', 'efficiency', 'fuel', 'omVar', 'maxRampUp', 'maxRampDown', 'timeToStart', 'regulation']   
    # check that all gensets have required parameters
    for gg in range(0, len(parameter['gensets'])):
        for pp in gensetParams:
            assert pp in  parameter['gensets'][gg].keys(), \
                f'Genset {gg+1} missing required parameter: {pp}'
    
    # extract list of fuels and gensets from parameter input
    fuelListInput = [fuel['name'] for fuel in parameter['fuels']]  
    gensetListInput = [genset['name'] for genset in parameter['gensets']]
   
    # Sets
    model.gensets = Set(initialize=gensetListInput, doc='gensets in the system')
    model.fuels = Set(initialize=fuelListInput, doc='fuel types available')
    
    # Parameters  
    model.genset_capacities = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'capacity', gensetListInput), \
                                doc='genset capacities [kWh]')
    model.genset_backupOnly = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'backupOnly', gensetListInput), \
                                doc='genset backup only [1/0]')
    model.genset_effs = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'efficiency', gensetListInput), \
                                doc='genset efficiencies [-]')
    model.genset_omVarRates = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'omVar', gensetListInput), \
                                doc='varaible O&M rates [$/kWh]')
    model.genset_maxRampUp = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'maxRampUp', gensetListInput), \
                                doc='max ramp rate up [-/hr]')
    model.genset_maxRampDown = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'maxRampDown', gensetListInput), \
                                doc='max ramp rate down [-/hr]')
    model.genset_timeToStart = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'timeToStart', gensetListInput), \
                                doc='min time to start [ht]]')
    model.genset_regulation = Param(model.gensets, initialize=extract_properties(parameter, 'gensets', 'regulation', gensetListInput), \
                                doc='able to participate in reg [1/0]')
    
    model.genset_fuels = Param(model.gensets, model.fuels, default=0, mutable=True, \
                                doc='genset fuel type')
    model.fuel_prices = Param(model.fuels, default=0, mutable=True, \
                                doc='fuel prices')
    model.fuel_co2 = Param(model.fuels, default=0, mutable=True, \
                                doc='fuel CO2 intentisties')
    model.fuel_reserves = Param(model.fuels, default=0, mutable=True, \
                                doc='fuel reserves in kWh')
    
    # construct 2-d fuel type table
    # bool indicating what fuel type each genset uses
    genset_fuels = extract_properties(parameter, 'gensets', 'fuel', gensetListInput)
    for gg in model.gensets:
        for ff in model.fuels:
            if genset_fuels[gg] == ff:
                model.genset_fuels[gg,ff] = 1
                
    # construct fuel price list
    for fuelDict in parameter['fuels']:
        ff = fuelDict['name']
        model.fuel_prices[ff] = fuelDict['rate'] / fuelDict['conversion']
        model.fuel_co2[ff] = fuelDict['co2'] / fuelDict['conversion']
        if 'reserves' in fuelDict.keys():
            model.fuel_reserves[ff] = fuelDict['reserves']* fuelDict['conversion']
        else:
            model.fuel_reserves[ff] = 0
            logging.info('fuel reserves missing, default value = 0')
            
    #initialize param mapping genset to node. values are updated below for multinode models      
    model.genset_node_location = Param(model.gensets, model.nodes, default=0, mutable=True, \
                                doc='genset node location')
            
    # populate battery_node_location based on data in parameter dict        
    if not model.multiNode:
        # for single-node models, all genset output is at single node
        for nn in model.nodes:
            for gg in model.gensets:
                model.genset_node_location[gg, nn] = 1
            
    else:
        # for multinode models, create parameter mapping genset to node based on location in parameter
        for node in parameter['network']['nodes']:
            
            # extract node name
            nn = node['node_id']
            
            # first check if node has ders key
            if 'ders' in node.keys():
                
                # then check that ders is not None
                if node['ders'] is not None:
                
                    # then check if genset in ders
                    if 'genset' in node['ders'].keys():
                        
                        # extract genset input from parameter
                        gensetInput = node['ders']['genset']
                        
                        # loop through genset index to see if it's at that node
                        for gg in model.gensets:
                            
                            # check if param value is str
                            if type(gensetInput) == str:
                                if str(gg) == gensetInput:
                                    # if match found, set location to 1 in map param
                                    model.genset_node_location[gg, nn] = 1
                                    
                            # check if param value is list
                            if type(gensetInput) == list:
                                # check if current genset from set is in input genset LIST
                                if str(gg) in gensetInput:
                                    # if match found, set location to 1 in map param
                                    model.genset_node_location[gg, nn] = 1
                                    
                                    
    
    # Variables
    # model.sum_genset_power = Var(model.ts, bounds=(0, None), doc='total power output from gensets [kW]')
    # def genset_power_bounds(model, ts, genset):
    #     return (0, model.bat_power_discharge[battery])
    model.genset_power = Var(model.ts, model.gensets, \
                                             bounds=(0, None), doc='genset power output [kW]')
    model.genset_fuel_consumption = Var(model.ts, model.gensets, model.fuels, \
                                             bounds=(0, None), doc='genset fuel consumption rate [kW]')
    model.genset_fuel_consumption_profile = Var(model.ts, model.fuels, \
                                             bounds=(0, None), doc='genset fuel consumption timeseries [kW]')
    model.genset_fuel_import_profile = Var(model.ts, model.fuels, \
                                             bounds=(0, None), doc='genset fuel imported from utility timeseries [kW]')
    model.genset_fuel_from_reserves_profile = Var(model.ts, model.fuels, \
                                             bounds=(0, None), doc='genset fuel consumed from reserves timeseries [kW]')
    model.genset_fuel_consumption_volume = Var(model.fuels, \
                                             bounds=(0, None), doc='genset fuel consumption over horizon [kWh]')
    model.genset_fuel_cost_total = Var(model.fuels, \
                                             bounds=(0, None), doc='fuel cost over horizon by fuel type[$]')
    # model.fuel_cost_total = Var(bounds=(0, None), doc='total fuel cost over horizon [$]')
    
    
    # genset output below max capacity
    def genset_max_output(model, ts, genset):
        return model.genset_power[ts, genset] <=  (model.genset_backupOnly[genset] * (1-model.grid_available[ts]) \
                                                     + (1 - model.genset_backupOnly[genset])) * model.genset_capacities[genset]
    model.constraint_genset_max_output = Constraint(model.ts, model.gensets, \
                                                                rule=genset_max_output, \
                                                                doc='constraint max genset output power')
    

    
    # fuel consumption based on efficiency
    def genset_fuel_consumption(model, ts, genset, fuel):
        return model.genset_fuel_consumption[ts, genset, fuel] ==  model.genset_power[ts, genset] \
            * model.genset_effs[genset] * model.genset_fuels[genset, fuel]
    model.constraint_genset_fuel_consumption = Constraint(model.ts, model.gensets, model.fuels, \
                                                                rule=genset_fuel_consumption, \
                                                                doc='constraint genset fuel consumption')
    
    # total fuel consumption by fuel type by timestep
    def total_genset_fuel_consumption_profile(model, ts, fuel):
        return model.genset_fuel_consumption_profile[ts, fuel] ==  sum(model.genset_fuel_consumption[ts, genset, fuel] \
                                                                for genset in model.gensets)
    model.constraint_total_genset_fuel_consumption_profile = Constraint(model.ts, model.fuels, \
                                                                rule=total_genset_fuel_consumption_profile, \
                                                                doc='constraint total genset fuel consumption profile')    
        
    # total fuel consumption by fuel type
    def total_genset_fuel_consumption(model, fuel):
        return model.genset_fuel_consumption_volume[fuel] ==  sum(model.genset_fuel_consumption[ts, genset, fuel] \
                                                                  for ts in model.ts for genset in model.gensets)
    model.constraint_total_genset_fuel_consumption = Constraint(model.fuels, \
                                                                rule=total_genset_fuel_consumption, \
                                                                doc='constraint total genset fuel consumption')
    
    # total cost based on cost of fuels
    def total_genset_fuel_cost(model):
        return model.fuel_cost_total == sum(model.genset_fuel_consumption_volume[fuel] * model.fuel_prices[fuel] for fuel in model.fuels)
    model.constraint_total_genset_fuel_cost = Constraint(rule=total_genset_fuel_cost, \
                                                                doc='constraint total genset fuel cost')
        
    # total CO2 emssions from genset fuel consumption
    def total_genset_co2(model):
        return model.sum_genset_co2 == sum(model.genset_fuel_consumption_volume[fuel] * model.fuel_co2[fuel] for fuel in model.fuels)
    model.constraint_total_genset_co2 = Constraint(rule=total_genset_co2, \
                                                                doc='constraint total genset co2 emissions')
      
    # total CO2 emssions profile from genset fuel consumption
    def genset_co2_profile(model, ts):
        return model.co2_profile_genset[ts] == sum(model.genset_fuel_consumption[ts, genset, fuel]  * model.fuel_co2[fuel] for fuel in model.fuels \
                                                                   for genset in model.gensets)
    model.constraint_genset_co2_profile = Constraint(model.ts, rule=genset_co2_profile, \
                                                                doc='constraint total genset co2 emissions')
        
        
    # Fuel Outage Equations
    def total_genset_fuel_consumption_source(model, ts, fuel):
        return model.genset_fuel_consumption_profile[ts, fuel] ==  model.genset_fuel_import_profile[ts, fuel] + model.genset_fuel_from_reserves_profile[ts, fuel]
    model.constraint_total_genset_fuel_consumption_source = Constraint(model.ts, model.fuels, \
                                                                rule=total_genset_fuel_consumption_source, \
                                                                doc='constraint total genset fuel consumption source')
    # fuel imports are zero if not available    
    def genset_fuel_import_limit(model, ts, fuel):
        return model.genset_fuel_import_profile[ts, fuel] <=  1e9 * model.fuel_available[ts]
    model.constraint_genset_fuel_import_limit = Constraint(model.ts, model.fuels, \
                                                                rule=genset_fuel_import_limit, \
                                                                doc='constraint total genset fuel import limit')
    # fuel from reserves disabled if available from utility import    
    def genset_fuel_reserves_limit(model, ts, fuel):
        return model.genset_fuel_from_reserves_profile[ts, fuel] <=  1e9 * (1 - model.fuel_available[ts])
    model.constraint_genset_fuel_reserves_limit = Constraint(model.ts, model.fuels, \
                                                                rule=genset_fuel_reserves_limit, \
                                                                doc='constraint total genset fuel reserves limit')
    # total fuel reserves consumed must be less than reserves on hand
    def total_genset_reserves_volume(model, ts, fuel):
        return model.fuel_reserves[fuel] >=  sum(model.genset_fuel_from_reserves_profile[ts, fuel] \
                                                                  for ts in model.ts)
    model.constraint_total_genset_reserves_volume = Constraint(model.ts, model.fuels, \
                                                                rule=total_genset_reserves_volume, \
                                                                doc='constraint total genset fuel consumption from reserves')
        
    # aggregate genset power output by node, works by default for single-node models
    def total_genset_output(model, ts, gensets, nodes):
        return model.sum_genset_power[ts, nodes] ==  sum((model.genset_power[ts, genset] * model.genset_node_location[genset, nodes]) for genset in model.gensets)
    model.constraint_total_genset_output = Constraint(model.ts, model.gensets, model.nodes, \
                                                                    rule=total_genset_output, \
                                                                    doc='constraint total genset output power')
            
    # sum site-wide genset output
    def site_total_genset_output(model, ts, nodes):
        return model.sum_genset_power_site[ts] ==  sum(model.sum_genset_power[ts, node] for node in model.nodes)
    model.constraint_site_total_genset_output = Constraint(model.ts,  model.nodes, \
                                                                    rule=site_total_genset_output, \
                                                                    doc='site total genset output power')
    
    return model


# Converter
def convert_gesnet(model, parameter):
    pass