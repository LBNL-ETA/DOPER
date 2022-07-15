#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''
import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyomo.environ import ConcreteModel, Set, Param, Var, Constraint, Binary
import logging

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
from .utility import pandas_to_dict, add_second_index, pyomo_read_parameter, plot_streams, get_root, constructNodeInput, mapExternalGen


def base_model(inputs, parameter):
    '''
        This function sets up the optimization model used for control.

        Input
        -----
            inputs (pandas.DataFrame): The input dataframe for the optimization.
            parameter (dict): Configuration dictionary for the optimization.

        Returns
        -------
            model (pyomo.environ.ConcreteModel): The complete model to be optimized.
    '''
    inputs = inputs.copy(deep=True)
    if type(inputs.index[0]) == type(pd.to_datetime(0)):
        inputs.index = inputs.index.view(np.int64)/1e9 # Convert datetime to UNIX
        
    model = ConcreteModel()

    # Sets
    model.ts = Set(initialize=list(inputs.index.values), ordered=True, doc='timesteps')
    #timestep = model.ts[2] - model.ts[1]
    model.timestep = \
        {inputs.index[i]:np.append([0], np.diff(inputs.index.values))[i] for i in range(len(inputs.index))} # in seconds
    #timestep_scale = 3600 / float(timestep)
    model.timestep_scale = \
        {inputs.index[i]:3600/np.append([1], np.diff(inputs.index.values))[i] for i in range(len(inputs.index))} # in hours
    model.timestep_scale_fwd = \
        {inputs.index[i]:3600/np.diff(inputs.index.values)[i] for i in range(len(inputs.index)-1)} # in hours
    model.periods = Set(initialize=parameter['tariff']['energy'].keys(), doc='demand periods')
    # model.batteries = Set(initialize=range(parameter['battery']['count']), doc='batteries in the system')
    accounting_ts = [t for t in model.ts][0:-2] # Timestep for accounting (cutoff last timestep)
    model.accounting_ts = accounting_ts
    
    # Default Node set (singlnode) if network dict not in inputs, or only 1 node in input
    # check to see if network is present# check to see if network is present
    if 'network' not in parameter.keys():
        model.multiNode = False
        model.nodes = Set(initialize=['singleNode'], doc='nodes in the system')
    elif len(parameter['network']['nodes'])<=1:
        model.multiNode = False
        model.nodes = Set(initialize=['singlNode'], doc='nodes in the system')
    else:
        # if network inputs passed and multiple nodes present, create node set
        model.multiNode = True
        nodeList = [node['node_id'] for node in parameter['network']['nodes']]
        model.nodes = Set(initialize=nodeList, doc='nodes in the system')
        
    
    # Parameter
    model.outside_temperature = Param(model.ts, initialize=pandas_to_dict(inputs['oat']), \
                                      doc='outside air temperature [C]')
    model.tariff_energy = Param(model.periods, initialize=parameter['tariff']['energy'], \
                                doc='energy tariff [$/kWh]')
    model.tariff_energy_map = Param(model.ts, initialize=pandas_to_dict(inputs['tariff_energy_map']), \
                                    doc='energy period map [periods]') 
    model.tariff_power = Param(model.periods, initialize=parameter['tariff']['demand'], \
                               doc='power tariff [$/kW]')
    model.tariff_power_map = Param(model.ts, initialize=pandas_to_dict(inputs['tariff_power_map']), \
                                   doc='power period map [periods]') 
    model.tariff_energy_export = Param(model.periods, initialize=parameter['tariff']['export'], \
                                       doc='export tariff [$/kWh]')
    model.tariff_energy_export_map = Param(model.ts, initialize=pandas_to_dict(inputs['tariff_energy_export_map']), \
                                           doc='export period map [periods]')
    model.tariff_regulation_up = Param(model.ts, initialize=pandas_to_dict(inputs['tariff_regup']), \
                                       doc='regulation up price [$/kWh]')
    model.tariff_regulation_dn = Param(model.ts, initialize=pandas_to_dict(inputs['tariff_regdn']), \
                                       doc='regulation dn price [$/kWh]')
    model.demand_periods_preset = Param(model.periods, initialize=parameter['site']['demand_periods_prev'], \
                                        doc='preset demand [kW]')
        
    # load grid availability. if not present in timeseries data, assume it's always available
    if 'grid_available' in inputs.columns: 
        model.grid_available = Param(model.ts, initialize=pandas_to_dict(inputs['grid_available']), \
                         doc='grid available [bool]')
            
    else:
        model.grid_available = Param(model.ts, initialize=1, \
                             doc='grid available [bool]')
        logging.info('grid availability missing from input. Default value = 1')
        
    # load fuel availability. if not present in timeseries data, assume it's always available
    if 'fuel_available' in inputs.columns:
        model.fuel_available = Param(model.ts, initialize=pandas_to_dict(inputs['fuel_available']), \
                             doc='fuel import available [bool]')
    else:
        model.fuel_available = Param(model.ts, initialize=1, \
                             doc='fuel import available [bool]')
        logging.info('fuel availability missing from input. Default value = 1')
        
    if 'grid_co2_intensity' in inputs.columns:
        model.grid_co2_intensity = Param(model.ts, initialize=pandas_to_dict(inputs['grid_co2_intensity']), \
                         doc='grid CO2 intensity [kg/kWh]')
    else:
        model.grid_co2_intensity = Param(model.ts, initialize=0, \
                         doc='grid CO2 intensity [kg/kWh]')
        logging.info('grid CO2 missing from input. Default value = 0')
     
        
    # map load profile & pv generation profiles to nodes
    if not model.multiNode:
        
        # convert load and pv ts-data into dicts with single-node name as second index
        singleNodeLabel = model.nodes.ordered_data()[0]
        loadDataDict= add_second_index(pandas_to_dict(inputs['load_demand']), singleNodeLabel)
        pvDataDict = add_second_index(pandas_to_dict(inputs['generation_pv']), singleNodeLabel)
        
        # for single node models, define load profile and solar directly from inputs
        model.load_input = Param(model.ts, model.nodes, initialize=loadDataDict, \
                         doc='static load demand [kW] by node')
        model.generation_pv = Param(model.ts, model.nodes, initialize=pvDataDict, \
                                doc='pv generation [kW]')
        
            
        # set power injected/absorbed at node to 0
        model.power_inj = Var(model.ts, model.nodes, bounds=(0,0), doc='power injected from node [kW]')
        model.power_abs = Var(model.ts, model.nodes, bounds=(0,0), doc='power absorbed at node [kW]')
        model.power_networkLosses = Var(model.ts, model.nodes, bounds=(0,0), doc='losses in network [kW]')
        
    else:
        # for multi-node models, construct node-ts dataframe containing data for pyomo param initialization
        # this process adds columns to the input dataframe with syntax:
        # 'input_load_{node name}' or 'pv_{node name}'
        # then extracts those columns from ts input df to initialize node-indexed input params load and pv
        
        # initilize list of new node-based inputs columns in ts df
        loadNodeList = []
        pvNodeList = []
        
        for nn, node in enumerate(parameter['network']['nodes']):
            
            # Construct LOAD inputs
            
            # create new column for aggregate pv for each node
            loadColName = f'input_load_{node["node_id"]}'
            
            # check if 'load_id' in node inputs
            if 'load_id' not in node.keys():
                # if load_id is not provided in input, default profile to 0
                inputs[loadColName] = 0
            else:
                inputs = constructNodeInput(inputs, node['load_id'], loadColName)
                
            loadNodeList.append(loadColName)  
                
            # Construc PV Inputs
    
            # create new column for aggregate pv for each node
            pvColName = f'pv_{node["node_id"]}'
            
            # check if 'ders' in node inputs
            if 'ders' not in node.keys():
                # if ders is not provided in input, default pv profile to 0
                inputs[pvColName] = 0
            else:
                inputs = constructNodeInput(inputs, node['ders']['pv_id'], pvColName)
                
            pvNodeList.append(pvColName)
            

        # define load and pv params from constructed df columns
        
        model.generation_pv = Param(model.ts, model.nodes, \
                        initialize= \
                        pandas_to_dict(inputs[pvNodeList] ,\
                                        columns=model.nodes, convertTs=False), \
                        doc='pv generation [kW]')

        model.load_input = Param(model.ts, model.nodes, \
                                initialize= \
                                pandas_to_dict(inputs[loadNodeList] ,\
                                                columns=model.nodes, convertTs=False), \
                                doc='static load demand [kW] by node')
            
        # define power injected/absorbed at node (positive)
        model.power_inj = Var(model.ts, model.nodes, bounds=(0,None), doc='power injected from node [kW]')
        model.power_abs = Var(model.ts, model.nodes, bounds=(0,None), doc='power absorbed at node [kW]')
        model.power_networkLosses = Var(model.ts, model.nodes, bounds=(0,None), doc='losses in network [kW]')
        # logging.warning('power injection set to 0 for testing')
        
    
    # define param to external generation. 
    ext_power_dict = mapExternalGen(parameter, inputs, model)
    model.external_gen_power = Param(model.ts, model.nodes, initialize=ext_power_dict, \
                                       doc='generation power from generic external power source [kW]')
    
   
    # Variables
    model.load_served = Var(model.ts, model.nodes, bounds=(0, None), doc='total load demand served [kW]')
    model.load_served_site = Var(model.ts, bounds=(0, None), doc='total load demand served for entire site [kW]')
    model.generation_pv_site = Var(model.ts, bounds=(0, None), doc='total pv generation profile for entire site [kW]')
    
    model.grid_import_site = Var(model.ts, bounds=(0, parameter['site']['import_max']), doc='site total grid import [kW]')
    model.grid_export_site = Var(model.ts, bounds=(0, parameter['site']['export_max']), doc='site total grid export [kW]')
    
    model.grid_import = Var(model.ts, model.nodes, bounds=(0, parameter['site']['import_max']), doc='grid import at each node [kW]')
    model.grid_export = Var(model.ts, model.nodes,bounds=(0, parameter['site']['export_max']), doc='grid export at each node [kW]')
    
    model.demand_charge_periods = Var(model.periods, bounds=(0, None), doc='maximal demand [kW,periods]')
    model.demand_charge_overall = Var(bounds=(0, None), doc='maximal demand [kW]')
    
    model.power_provided = Var(model.ts, model.nodes, bounds=(None, None), doc='power provided at node [kW]')
    model.power_consumed = Var(model.ts, model.nodes, bounds=(None, None), doc='power consumed ar node [kW]')
    
    # model.power_injected = Var(model.ts, model.nodes, bounds=(None, None), doc='power injected at node [kW]')
    # model.power_absorbed = Var(model.ts, model.nodes, bounds=(None, None), doc='power absorbed ar node [kW]')
    
    model.grid_importXORexport = Var(model.ts, doc='grid import xor export binary [-]',  domain=Binary)
    
    # total and timeseries co2 variables
    model.co2_elec_import = Var(bounds=(None, None), doc='total CO2 from elec purchases [kg]')
    model.co2_elec_export = Var(bounds=(None, None), doc='total CO2 offsts from elec exports [kg]')
    model.co2_fuels = Var(bounds=(None, None), doc='total CO2 from fuel consumption [kg]')
    model.co2_total = Var(bounds=(None, None), doc='total CO2 emissions [kg]')
    
    model.co2_profile_elec_import = Var(model.ts, bounds=(None, None), doc='timeseries profile of CO2 from elec purchases [kg]')
    model.co2_profile_elec_export = Var(model.ts, bounds=(None, None), doc='timeseries profile of CO2 offsts from elec exports [kg]')
    model.co2_profile_fuels = Var(model.ts, bounds=(None, None), doc='timeseries profile of CO2 from fuel consumption [kg]')
    model.co2_profile_total = Var(model.ts, bounds=(None, None), doc='timeseries profile of CO2 emissions [kg]')
    
    # cost and objective vars
    model.energy_cost = Var(model.ts, bounds=(0, None), doc='energy cost [$]')
    
    model.energy_export_revenue = Var(model.ts, bounds=(0, None), doc='energy export revenue [$]')
    model.sum_energy_cost = Var(doc='energy cost [$]')
    model.sum_demand_cost = Var(doc='demand cost [$]')
    model.sum_export_revenue = Var(doc='export energy revenue [$]')
    model.sum_regulation_revenue = Var(doc='regulation revenue [$]')
    model.total_cost = Var(doc='total energy cost [$]')
   
    
   ### CONDITIONAL VARS & PARAMS for EXTERNAL TECH MODELS ### 
    
    # Disable vars for inactive model compoents
    if parameter['system']['battery']:
        # define battery charing dischargin as positive timeseries variables
        model.sum_battery_charge_grid_power = Var(model.ts, model.nodes, bounds=(0,None), doc='total battery grid charge [kW]')
        model.sum_battery_discharge_grid_power = Var(model.ts, model.nodes, bounds=(0,None), doc='total battery grid discharge [kW]')
        model.sum_battery_charge_grid_power_site = Var(model.ts, bounds=(0,None), doc='total battery grid charge [kW]')
        model.sum_battery_discharge_grid_power_site = Var(model.ts,  bounds=(0,None), doc='total battery grid discharge [kW]')
    else:
        # if batteries are disabled, fix battery charing/discharge to 0
        model.sum_battery_charge_grid_power = Var(model.ts, model.nodes, bounds=(0,0), doc='total battery grid charge [kW] - disabled')
        model.sum_battery_discharge_grid_power = Var(model.ts, model.nodes, bounds=(0,0), doc='total battery grid discharge [kW] - disabled')
        model.sum_battery_charge_grid_power_site = Var(model.ts, bounds=(0,0), doc='total battery grid charge [kW] - disabled')
        model.sum_battery_discharge_grid_power_site = Var(model.ts, bounds=(0,0), doc='total battery grid discharge [kW] - disabled')
       
        
    if parameter['system']['genset']:
        model.sum_genset_power = Var(model.ts, model.nodes, bounds=(0, None), doc='total power output from gensets at each node [kW]')
        model.sum_genset_power_site = Var(model.ts, bounds=(0, None), doc='site total power output from gensets [kW]')
        model.fuel_cost_total = Var(bounds=(0, None), doc='total fuel cost over horizon [$]')
        model.sum_genset_co2 = Var(bounds=(0, None), doc='total co2 emissions from gensets [kg]')
        model.co2_profile_genset = Var(model.ts, bounds=(0, None), doc='timeseries profile of CO2 from gensets [kg]')
    else:
        # if generators are disabled, set output and costs vars to 0
        model.sum_genset_power = Var(model.ts, model.nodes, bounds=(0, 0), doc='total power output from gensets [kW] - disabled')
        model.sum_genset_power_site = Var(model.ts, bounds=(0, 0), doc='site total power output from gensets [kW] - disabled')
        model.fuel_cost_total = Var(bounds=(0, 0), doc='total fuel cost over horizon [$] - disabled')
        model.sum_genset_co2 = Var(bounds=(0, 0), doc='total co2 emissions from gensets [kg] - disabled')
        model.co2_profile_genset = Var(model.ts, bounds=(0, 0), doc='timeseries profile of CO2 from gensets [kg] - disabled')
        
    
    # load control
    if parameter['system']['load_control']:
        model.load_shed = Var(model.ts, model.nodes, bounds=(0, None), doc='load shed amount due to load control use [kW]')
        model.load_shed_cost_total = Var(bounds=(0, None), doc='total load shed cost over horizon [$]')
        model.load_shed_site = Var(model.ts, bounds=(0, None), doc='total load shed [kW]')
    else:
        # if load control is disabled, set load shed and shed costs to zero
        model.load_shed = Var(model.ts, model.nodes, bounds=(0, 0), doc='load shed amount due to load control use [kW] - disabled')
        model.load_shed_cost_total = Var(bounds=(0, 0), doc='total load shed cost over horizon [$] - disabled')
        model.load_shed_site = Var(model.ts, bounds=(0, 0), doc='total load shed [kW] - disabled')
      
    if parameter['system']['hvac_control']:
        model.building_load_dynamic = Var(model.ts, model.nodes, bounds=(None, None), doc='dynamic building load demand [kW]')
    else:
        model.building_load_dynamic = Var(model.ts, model.nodes, bounds=(0, 0), doc='dynamic building load demand [kW]')
    
    # if parameter['site']['regulation_reserved']:
    #     model.sum_regulation_up = Param(model.ts, \
    #                                     initialize=pandas_to_dict(inputs['regulation_up']), \
    #                                     doc='regulation up preset [kW]')
    #     model.sum_regulation_dn = Param(model.ts, \
    #                                     initialize=pandas_to_dict(inputs['regulation_dn']), \
    #                                     doc='regulation dn preset [kW]')
    # else:
    #     model.sum_regulation_up = Var(model.ts, bounds=(0, None), doc='sum regulation up [kW]')
    #     model.sum_regulation_dn = Var(model.ts, bounds=(0, None), doc='sum regulation dn [kW]')
        
               
    ### Base Model Eqns ### 
        
    # grid outage constraints   
    def outage_import(model, ts, nodes):
        return model.grid_import[ts, nodes] <= model.grid_available[ts] * parameter['site']['import_max']
    model.constraint_outage_import = Constraint(model.ts, model.nodes, rule=outage_import, \
                                                  doc='constraint outage import')
                                                  
    def outage_export(model, ts, nodes):
        return model.grid_export[ts, nodes] <= model.grid_available[ts] * parameter['site']['export_max']
    model.constraint_outage_export = Constraint(model.ts, model.nodes, rule=outage_export, \
                                                  doc='constraint outage export')
 
    # Overall energy balance
    def power_provision(model, ts, nodes):
        return model.power_provided[ts, nodes] == model.grid_import[ts, nodes] \
                                    + model.sum_battery_discharge_grid_power[ts, nodes]\
                                    + model.generation_pv[ts, nodes] \
                                    + model.sum_genset_power[ts, nodes] \
                                    + model.power_abs[ts, nodes] \
                                    + model.external_gen_power[ts, nodes]
    model.constraint_power_provision = Constraint(model.ts, model.nodes, rule=power_provision, \
                                                  doc='constraint power provision')
        
    def power_consumption(model, ts, nodes):
        return model.power_consumed[ts, nodes] == model.sum_battery_charge_grid_power[ts, nodes] \
                                    + model.grid_export[ts, nodes] \
                                    + model.load_served[ts,nodes] \
                                    + model.building_load_dynamic[ts,nodes] \
                                    + model.power_inj[ts, nodes] \
                                    + model.power_networkLosses[ts, nodes]
    model.constraint_power_consumption = Constraint(model.ts, model.nodes, rule=power_consumption, \
                                                  doc='constraint power consumption')
        
        
    def energy_balance(model, ts, nodes):
        return model.power_provided[ts, nodes] == model.power_consumed[ts, nodes]
    model.constraint_energy_balance = Constraint(model.ts, model.nodes, rule=energy_balance, \
                                                 doc='constraint energy balance')
        
    def net_load_served_summation(model, ts, nodes):
        return model.load_served[ts, nodes] == model.load_input[ts, nodes] - model.load_shed[ts, nodes]
    model.constraint_net_load_served_summation = Constraint(model.ts, model.nodes, rule=net_load_served_summation, \
                                                 doc='summation of input load and load shedding')

    # Site constraints
    def site_grid_imports(model, ts, nodes):
        return model.grid_import_site[ts] == sum(model.grid_import[ts, node] for node in model.nodes)
    model.constraint_site_grid_imports = Constraint(model.ts, model.nodes, 
                                                    rule=site_grid_imports, doc='site-total grid imports aggregation')
    
    def site_grid_exports(model, ts, nodes):
        return model.grid_export_site[ts] == sum(model.grid_export[ts, node] for node in model.nodes)
    model.constraint_site_grid_exports = Constraint(model.ts, model.nodes, 
                                                    rule=site_grid_exports, doc='site-total grid exports aggregation')
    
    def site_load_served_agg(model, ts, nodes):
        return model.load_served_site[ts] == sum(model.load_served[ts, node] for node in model.nodes)
    model.constraint_site_load_served_agg = Constraint(model.ts, model.nodes, 
                                                    rule=site_load_served_agg, doc='site-total load served')
    
    def site_pv_gen_agg(model, ts, nodes):
        return model.generation_pv_site[ts] == sum(model.generation_pv[ts, node] for node in model.nodes)
    model.constraint_site_pv_gen_agg = Constraint(model.ts, model.nodes, 
                                                    rule=site_pv_gen_agg, doc='site-total pv gen')
    
    def demand_maximum_periods(model, ts):
        if ts == model.ts.at(len(model.ts)): return model.demand_charge_periods[model.tariff_power_map[ts]] >= 0
        else: return model.demand_charge_periods[model.tariff_power_map[ts]] >= model.grid_import_site[ts] \
                                                                                - model.demand_periods_preset[model.tariff_power_map[ts]]
    model.constraint_demand_maximum = Constraint(model.ts, rule=demand_maximum_periods, doc='constraint demand periods')
    
    def demand_maximum_overall(model, ts):
        if ts == model.ts.at(len(model.ts)): return model.demand_charge_overall >= 0
        else: return model.demand_charge_overall >= model.grid_import_site[ts] - parameter['site']['demand_coincident_prev']
    model.constraint_demand_overall = Constraint(model.ts, rule=demand_maximum_overall, doc='constraint demand overall')
    
    def limit_physical_import(model, ts):
        return model.grid_import_site[ts] <= parameter['site']['import_max']
    model.constraint_limit_physical_import = Constraint(model.ts, rule=limit_physical_import, \
                                                        doc='constraint grid import limit')

    # Grid Import XOR Export
    def grid_import_XOR_export(model, ts, nodes):
        return model.grid_import[ts, nodes] <=  model.grid_importXORexport[ts] * parameter['site']['import_max']
    model.constraint_grid_import_XOR_export = Constraint(model.ts, model.nodes, rule=grid_import_XOR_export, \
                                                         doc='grid import xor export')  
    def grid_export_XOR_import(model, ts, nodes):
        return model.grid_export[ts, nodes] <=  (1 - model.grid_importXORexport[ts]) * parameter['site']['import_max']
    model.constraint_grid_export_XOR_import = Constraint(model.ts, model.nodes, rule=grid_export_XOR_import, \
                                                         doc='grid export xor import')  

    # CO2 Emissions
    def grid_import_emissions(model):
        return model.co2_elec_import == sum((model.grid_import_site[t]*model.grid_co2_intensity[t]) for t in accounting_ts)
    model.constraint_grid_import_emissions = Constraint(rule=grid_import_emissions, doc='grid import co2 calculation')
    
    def grid_export_emissions(model):
        return model.co2_elec_export == sum((model.grid_export_site[t]*model.grid_co2_intensity[t]) for t in accounting_ts)
    model.constraint_grid_export_emissions = Constraint(rule=grid_export_emissions, doc='grid export co2 calculation')
    
    def grid_import_emissions_profile(model, ts):
        return model.co2_profile_elec_import[ts] == model.grid_import_site[ts]*model.grid_co2_intensity[ts]
    model.constraint_grid_import_emissions_profile= Constraint(model.ts, rule=grid_import_emissions_profile, doc='grid import co2 profile calculation')
    
    def grid_export_emissions_profile(model, ts):
        return model.co2_profile_elec_export[ts] == model.grid_export_site[ts]*model.grid_co2_intensity[ts]
    model.constraint_grid_export_emissions_profile = Constraint(model.ts, rule=grid_export_emissions_profile, doc='grid export co2 profile calculation')
    
    # sum of emissions from all fuel consumption. Right now is only from gensets, but could expand in future
    def fuel_use_emissions(model):
        return model.co2_fuels == model.sum_genset_co2
    model.constraint_fuel_use_emissions = Constraint(rule=fuel_use_emissions, doc='all fuel use co2 calculation')
    
    def total_co2_emissions(model):
        return model.co2_total == model.co2_elec_import - model.co2_elec_export + model.co2_fuels
    model.constraint_total_co2_emission = Constraint(rule=total_co2_emissions, doc='total co2 calculation')
    
    def co2_emissions_profile(model, ts):
        return model.co2_profile_total[ts] == model.co2_profile_elec_import[ts] - model.co2_profile_elec_export[ts] + model.co2_profile_genset[ts]
    model.constraint_co2_emissions_profile = Constraint(model.ts, rule=co2_emissions_profile, doc='total co2 profile calculation')
        
        
    # Define Objective
    
    def energy_cost_calculation(model, ts):
        if ts == model.ts.at(-1):
            return model.energy_cost[ts] == 0
        else:
            return model.energy_cost[ts] == \
                model.grid_import_site[ts] * model.tariff_energy[model.tariff_energy_map[ts]] \
                / model.timestep_scale_fwd[ts]
    model.constraint_energy_cost_calculation = Constraint(model.ts, rule=energy_cost_calculation, \
                                                          doc='constraint energy cost calculation')
    def energy_export_revenue_calculation(model, ts):
        if ts == model.ts.at(-1):
            return model.energy_export_revenue[ts] == 0
        else:
            return model.energy_export_revenue[ts] == \
                model.grid_export_site[ts] * model.tariff_energy_export[model.tariff_energy_export_map[ts]] \
                / model.timestep_scale_fwd[ts]
    model.constraint_energy_export_revenue_calculation = Constraint(model.ts, rule=energy_export_revenue_calculation, \
                                                                    doc='constraint energy export revenue calculation')
    
    
    def sum_energy_cost(model):
        return model.sum_energy_cost == sum(model.energy_cost[t] for t in accounting_ts)
    model.constraint_sum_energy_cost = Constraint(rule=sum_energy_cost, doc='energy cost calculation')
    
    def sum_demand_cost(model):
        demand = 0
        if parameter['site']['customer'] == 'Commercial':
            demand = sum(model.demand_charge_periods[p] * model.tariff_power[p] for p in model.periods)
            demand += model.demand_charge_overall * parameter['tariff']['demand_coincident']
        return model.sum_demand_cost == demand
    model.constraint_sum_demand_cost = Constraint(rule=sum_demand_cost, doc='demand cost calculation')
    
    def sum_export_revenue(model):
        export = 0
        if parameter['site']['export_max'] > 0:
            export = -1* sum(model.energy_export_revenue[t] for t in accounting_ts)
        return model.sum_export_revenue == export
    model.constraint_sum_export_revenue = Constraint(rule=sum_export_revenue, doc='export revenue calculation')
    
    # def sum_regulation_revenue(model):
    #     regulation = 0
    #     if parameter['site']['regulation'] or parameter['site']['regulation_reserved']:
    #         regulation = -1* sum(model.regulation_revenue[t] for t in accounting_ts)
    #     return model.sum_regulation_revenue == regulation
    # model.constraint_sum_regulation_revenue = Constraint(rule=sum_regulation_revenue, doc='regulation revenue calculation')    
        
    def total_cost(model):
        return model.total_cost == model.sum_energy_cost \
                                   + model.sum_demand_cost \
                                   + model.sum_export_revenue
    model.constraint_total_cost = Constraint(rule=total_cost, doc='total cost')
        
    return model      


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
                'data': 'sum_battery_charge_grid_power',
                'df_label': 'Battery Charging Power [kW]'
            },
            {
                'name': 'batDisharge',
                'data': 'sum_battery_discharge_grid_power',
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
            'data': 'power_inj',
            'index': 'nodes',
            'df_label': 'powerInj_'
        },
        {
            'name': 'powerAbs',
            'data': 'power_abs',
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