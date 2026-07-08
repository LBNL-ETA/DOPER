# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Base model module.
"""
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

from ..utility import pandas_to_dict, unpack_ts_input, add_second_index, pyomo_read_parameter, get_root, constructNodeInput, mapExternalGen



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
    periods = [int(k) for k in parameter['tariff']['energy'].keys()]
    model.periods = Set(initialize=periods, doc='demand periods')
   
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
        model.simplePX = None
    else:
        # if network inputs passed and multiple nodes present, create node set
        model.multiNode = True
        nodeList = [node['node_id'] for node in parameter['network']['nodes']]
        model.nodes = Set(initialize=nodeList, doc='nodes in the system')
        model.simplePX = None
        try:
            model.simplePX = parameter['network']['settings']['simplePowerExchange']
        except:
            model.simplePX = False
    
    # Parameter
    def period_map(par, periods, fill_missing=True, default=0):
        par = {int(k): v for k,v in par.items()}
        return {p: par[p] if p in par else default for p in periods}

    model.tariff_energy = Param(model.periods, initialize=period_map(parameter['tariff']['energy'], periods, False), \
                                doc='energy tariff [$/kWh]')
    model.tariff_power = Param(model.periods, initialize=period_map(parameter['tariff']['demand'], periods, False), \
                               doc='power tariff [$/kW]')
    model.tariff_energy_export = Param(model.periods, initialize=period_map(parameter['tariff']['export'], periods), \
                                       doc='export tariff [$/kWh]')
    model.pv_max_s = Param(model.nodes, initialize=0, mutable=True, \
                            doc='pv inv max apparent power [kVA]')
    # dynamic import/export limits
    dynamic_import_max = unpack_ts_input(inputs, 'import_max', parameter['site']['import_max'])
    if isinstance(dynamic_import_max, dict):
        dynamic_import_max_ub = max(dynamic_import_max.values())
    else:
        dynamic_import_max_ub = dynamic_import_max
    model.dynamic_import_max = Param(model.ts, initialize=dynamic_import_max, \
                             doc='site grid import max [kW]')
    dynamic_export_max = unpack_ts_input(inputs, 'export_max', parameter['site']['export_max'])
    if isinstance(dynamic_export_max, dict):
        dynamic_export_max_ub = max(dynamic_export_max.values())
    else:
        dynamic_export_max_ub = dynamic_export_max
    model.dynamic_export_max = Param(model.ts, initialize=dynamic_export_max, \
                             doc='site grid export max [kW]')


    # Unpack time-series inputs
    model.tariff_energy_map = Param(model.ts, initialize=unpack_ts_input(inputs,'tariff_energy_map'), \
                                    doc='energy period map [periods]') 
    model.tariff_power_map = Param(model.ts, initialize=unpack_ts_input(inputs,'tariff_power_map'), \
                                   doc='power period map [periods]') 
    model.tariff_energy_export_map = Param(model.ts, initialize=unpack_ts_input(inputs,'tariff_energy_export_map'), \
                                           doc='export period map [periods]')
    model.tariff_regulation_up = Param(model.ts, initialize=unpack_ts_input(inputs,'tariff_regup'), \
                                       doc='regulation up price [$/kWh]')
    model.tariff_regulation_dn = Param(model.ts, initialize=unpack_ts_input(inputs,'tariff_regdn'), \
                                       doc='regulation dn price [$/kWh]')

   
    # optional time-series inputs
    model.outside_temperature = Param(model.ts, initialize=unpack_ts_input(inputs, 'oat', 20, False), \
                                      doc='outside air temperature [C]')
    model.grid_available = Param(model.ts, initialize=unpack_ts_input(inputs,'grid_available', 1), \
                         doc='grid available [bool]')
    model.fuel_available = Param(model.ts, initialize=unpack_ts_input(inputs,'fuel_available', 1), \
                             doc='fuel import available [bool]')
    model.grid_co2_intensity = Param(model.ts, initialize=unpack_ts_input(inputs,'grid_co2_intensity',0), \
                         doc='grid CO2 intensity [kg/kWh]')
    model.utility_rtp = Param(model.ts, initialize=unpack_ts_input(inputs,'utility_rtp',0), \
                         doc='utility real time price [$/kWh]')

    # if 'utility_rtp' is in inputs, and 'utility_rtp_export' is not, duplicate 'utility_rtp' to 'utility_rtp_export'
    if ('utility_rtp' in inputs.columns) and ('utility_rtp_export' not in inputs.columns):
        inputs['utility_rtp_export'] = inputs['utility_rtp']

    model.utility_rtp_export = Param(model.ts, initialize=unpack_ts_input(inputs,'utility_rtp_export',0), \
                         doc='utility real time export price [$/kWh]')
     
        
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
        
            
        # set simple power exchange vars to zero
        model.powerExchangeOut = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange injected from node [kW] - disabled')
        model.powerExchangeIn = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange absorbed at node [kW] - disabled')
        model.powerExchangeLosses = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange losses in network [kW] - disabled')
        
    else:
        # for multi-node models, construct node-ts dataframe containing data for pyomo param initialization
        # this process adds columns to the input dataframe with syntax:
        # 'input_load_{node name}' or 'pv_{node name}'
        # then extracts those columns from ts input df to initialize node-indexed input params load and pv
        
        # initilize list of new node-based inputs columns in ts df
        loadNodeList = []
        pvNodeList = []
        
        # initialize simple power exchange vars that go into balance eqn
        if model.simplePX:
            # enable simple power exchange vars for simple model
            model.powerExchangeOut = Var(model.ts, model.nodes, bounds=(0, None), doc='simple power exchange injected from node [kW]')
            model.powerExchangeIn = Var(model.ts, model.nodes, bounds=(0, None), doc='simple power exchange absorbed at node [kW]')
            model.powerExchangeLosses = Var(model.ts, model.nodes, bounds=(0,None), doc='simple power exchange losses in network [kW]')
        else:
            # disable simple power exchange vars for full power-flow
            model.powerExchangeOut = Var(model.ts, model.nodes, bounds=(0, 0), doc='simple power exchange injected from node [kW] - disabled')
            model.powerExchangeIn = Var(model.ts, model.nodes, bounds=(0, 0), doc='simple power exchange absorbed at node [kW] - disabled')
            model.powerExchangeLosses = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange losses in network [kW] - disabled')
        
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
            
            # extract pv inverter max s if present
            if 'pv_maxS' in node['ders'].keys():
                model.pv_max_s[node["node_id"]] = node['ders']['pv_maxS']            

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
            
        
        
    
    # define param to external generation. 
    ext_power_dict = mapExternalGen(parameter, inputs, model)
    model.external_gen_power = Param(model.ts, model.nodes, initialize=ext_power_dict, \
                                       doc='generation power from generic external power source [kW]')
    
   
    # Variables
    model.load_served = Var(model.ts, model.nodes, bounds=(0, None), doc='total load demand served [kW]')
    model.load_served_site = Var(model.ts, bounds=(0, None), doc='total load demand served for entire site [kW]')
    model.generation_pv_site = Var(model.ts, bounds=(0, None), doc='total pv generation profile for entire site [kW]')
    model.actual_generation_pv = Var(model.ts, model.nodes, bounds=(0, None), doc='actual pv generation after curtailment (islanded only) [kW]')
    model.generation_pv_curtailed = Var(model.ts, model.nodes, bounds=(0, None), doc='curtailed pv power [kW]')
    
    model.grid_import_site = Var(model.ts, bounds=(0, dynamic_import_max_ub), doc='site total grid import [kW]')
    model.grid_export_site = Var(model.ts, bounds=(0, dynamic_export_max_ub), doc='site total grid export [kW]')
    
    model.grid_import = Var(model.ts, model.nodes, bounds=(0, dynamic_import_max_ub), doc='grid import at each node [kW]')
    model.grid_export = Var(model.ts, model.nodes,bounds=(0, dynamic_export_max_ub), doc='grid export at each node [kW]')
    
    demand_periods_prev_map = period_map(parameter['site']['demand_periods_prev'], periods)
    demand_periods_bounds = {p: (demand_periods_prev_map[p], None) for p in periods}
    def demand_charge_periods_bounds_rule(model, p):
        return demand_periods_bounds.get(p, (0, None))
    model.demand_charge_periods = Var(model.periods, bounds=demand_charge_periods_bounds_rule,
                                      doc='maximal demand [kW,periods]')
    model.demand_charge_overall = Var(bounds=(parameter['site']['demand_coincident_prev'], None),
                                      doc='maximal demand [kW]')
    
    model.power_provided = Var(model.ts, model.nodes, bounds=(None, None), doc='power provided at node [kW]')
    model.power_consumed = Var(model.ts, model.nodes, bounds=(None, None), doc='power consumed ar node [kW]')
    
    model.grid_importXORexport = Var(model.ts, doc='grid import xor export binary [-]',  domain=Binary)
    
    # total and timeseries co2 variables
    model.co2_elec_import = Var(bounds=(0, None), doc='total CO2 from elec purchases [kg]')
    model.co2_elec_export = Var(bounds=(0, None), doc='total CO2 offsts from elec exports [kg]')
    model.co2_fuels = Var(bounds=(0, None), doc='total CO2 from fuel consumption [kg]')
    model.co2_total = Var(bounds=(0, None), doc='total CO2 emissions [kg]')
    
    model.co2_profile_elec_import = Var(model.ts, bounds=(0, None), doc='timeseries profile of CO2 from elec purchases [kg]')
    model.co2_profile_elec_export = Var(model.ts, bounds=(0, None), doc='timeseries profile of CO2 offsts from elec exports [kg]')
    model.co2_profile_fuels = Var(model.ts, bounds=(0, None), doc='timeseries profile of CO2 from fuel consumption [kg]')
    model.co2_profile_total = Var(model.ts, bounds=(None, None), doc='timeseries profile of CO2 emissions [kg]')
    
    # cost and objective vars
    model.energy_cost = Var(model.ts, bounds=(0, None), doc='energy cost [$]')
    model.rtp_cost = Var(model.ts, bounds=(0, None), doc='RTP cost [$]')
    
    model.energy_export_revenue = Var(model.ts, bounds=(0, None), doc='energy export revenue [$]')
    model.rtp_export_revenue = Var(model.ts, bounds=(0, None), doc='RTP export revenue [$]')
    
    model.sum_energy_cost = Var(doc='energy cost [$]')
    model.sum_demand_cost = Var(doc='demand cost [$]')
    model.sum_rtp_cost = Var(doc='real-time price energy cost [$]')
    model.sum_export_revenue = Var(doc='export energy revenue [$]')
    model.sum_rtp_export_revenue = Var(doc='RTP export energy revenue [$]')
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
        model.load_shed_der_total = Var(bounds=(0, None), doc='total load shed derivative over horizon [-]')
        model.load_shed_act_total = Var(bounds=(0, None), doc='total load circuit activations (sum of load_circuits_on) over accounting horizon [-]')
    else:
        # if load control is disabled, set load shed and shed costs to zero
        model.load_shed = Var(model.ts, model.nodes, bounds=(0, 0), doc='load shed amount due to load control use [kW] - disabled')
        model.load_shed_cost_total = Var(bounds=(0, 0), doc='total load shed cost over horizon [$] - disabled')
        model.load_shed_site = Var(model.ts, bounds=(0, 0), doc='total load shed [kW] - disabled')
        model.load_shed_der_total = Var(bounds=(0, 0), doc='total load shed derivative over horizon [-]')
        model.load_shed_act_total = Var(bounds=(0, 0), doc='total load circuit activations over accounting horizon [-] - disabled')
      
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
        return model.grid_import[ts, nodes] <= model.grid_available[ts] * model.dynamic_import_max[ts]
    model.constraint_outage_import = Constraint(model.ts, model.nodes, rule=outage_import, \
                                                  doc='constraint outage import')
                                                  
    def outage_export(model, ts, nodes):
        return model.grid_export[ts, nodes] <= model.grid_available[ts] * model.dynamic_export_max[ts]
    model.constraint_outage_export = Constraint(model.ts, model.nodes, rule=outage_export, \
                                                  doc='constraint outage export')
 
    # Overall energy balance
    def power_provision(model, ts, nodes):
        return model.power_provided[ts, nodes] == model.grid_import[ts, nodes] \
                                    + model.sum_battery_discharge_grid_power[ts, nodes]\
                                    + model.actual_generation_pv[ts, nodes] \
                                    + model.sum_genset_power[ts, nodes] \
                                    + model.powerExchangeIn[ts, nodes] \
                                    + model.external_gen_power[ts, nodes]
    model.constraint_power_provision = Constraint(model.ts, model.nodes, rule=power_provision, \
                                                  doc='constraint power provision')
        
    def power_consumption(model, ts, nodes):
        return model.power_consumed[ts, nodes] == model.sum_battery_charge_grid_power[ts, nodes] \
                                    + model.grid_export[ts, nodes] \
                                    + model.load_served[ts,nodes] \
                                    + model.building_load_dynamic[ts,nodes] \
                                    + model.powerExchangeOut[ts, nodes]
    model.constraint_power_consumption = Constraint(model.ts, model.nodes, rule=power_consumption, \
                                                  doc='constraint power consumption')
                                                  
    # pv curtailment when islanded
    def pv_actual_power(model, ts, nodes):
        if model.grid_available[ts] == 1:
            return model.actual_generation_pv[ts, nodes] == model.generation_pv[ts, nodes]
        else:
            return model.actual_generation_pv[ts, nodes] <= model.generation_pv[ts, nodes]
    model.constraint_pv_actual_power = Constraint(model.ts, model.nodes, rule=pv_actual_power, \
                                                  doc='pv actual power with eventual curtailment')
                                                  
    def pv_curtail_power(model, ts, nodes):
        return model.generation_pv_curtailed[ts, nodes] == model.generation_pv[ts, nodes] - model.actual_generation_pv[ts, nodes]
    model.constraint_pv_curtail_power = Constraint(model.ts, model.nodes, rule=pv_curtail_power, \
                                                  doc='pv curtaied power') 
        
    # apply energy balance for single-node models
    if (not model.multiNode or len(model.nodes.ordered_data()) == 1) or model.simplePX:
        # logging.info('applying energy balance constraint for single-node model')
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
        return model.generation_pv_site[ts] == sum(model.actual_generation_pv[ts, node] for node in model.nodes)
    model.constraint_site_pv_gen_agg = Constraint(model.ts, model.nodes, 
                                                    rule=site_pv_gen_agg, doc='site-total pv gen')
    
    def demand_maximum_periods(model, ts):
        if ts == model.ts.at(len(model.ts)): return Constraint.Skip
        else: return model.demand_charge_periods[model.tariff_power_map[ts]] >= model.grid_import_site[ts]
    model.constraint_demand_maximum = Constraint(model.ts, rule=demand_maximum_periods, doc='constraint demand periods')

    def demand_maximum_overall(model, ts):
        if ts == model.ts.at(len(model.ts)): return Constraint.Skip
        else: return model.demand_charge_overall >= model.grid_import_site[ts]
    model.constraint_demand_overall = Constraint(model.ts, rule=demand_maximum_overall, doc='constraint demand overall')
    
    def limit_physical_import(model, ts):
        return model.grid_import_site[ts] <= model.dynamic_import_max[ts]
    model.constraint_limit_physical_import = Constraint(model.ts, rule=limit_physical_import, \
                                                        doc='constraint grid import limit')

    # Grid Import XOR Export
    def grid_import_XOR_export(model, ts, nodes):
        return model.grid_import[ts, nodes] <=  model.grid_importXORexport[ts] * model.dynamic_import_max[ts]
    model.constraint_grid_import_XOR_export = Constraint(model.ts, model.nodes, rule=grid_import_XOR_export, \
                                                         doc='grid import xor export')  
    def grid_export_XOR_import(model, ts, nodes):
        return model.grid_export[ts, nodes] <=  (1 - model.grid_importXORexport[ts]) * model.dynamic_export_max[ts]
    model.constraint_grid_export_XOR_import = Constraint(model.ts, model.nodes, rule=grid_export_XOR_import, \
                                                         doc='grid export xor import')  

    # CO2 Emissions
    def grid_import_emissions(model):
        return model.co2_elec_import == sum((model.grid_import_site[t]*model.grid_co2_intensity[t] / model.timestep_scale_fwd[t]) for t in accounting_ts)
    model.constraint_grid_import_emissions = Constraint(rule=grid_import_emissions, doc='grid import co2 calculation')
    
    def grid_export_emissions(model):
        return model.co2_elec_export == sum((model.grid_export_site[t]*model.grid_co2_intensity[t] / model.timestep_scale_fwd[t]) for t in accounting_ts)
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
    
    # TOU energy costs
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
    
    def sum_export_revenue(model):
        export = 0
        if parameter['site']['export_max'] > 0:
            export = sum(model.energy_export_revenue[t] for t in accounting_ts)
        return model.sum_export_revenue == export
    model.constraint_sum_export_revenue = Constraint(rule=sum_export_revenue, doc='export revenue calculation')
        
    # RTP energy costs 
    def rtp_cost_calculation(model, ts):
        if ts == model.ts.at(-1):
            return model.rtp_cost[ts] == 0
        else:
            return model.rtp_cost[ts] == \
                model.grid_import_site[ts] * model.utility_rtp[ts] \
                / model.timestep_scale_fwd[ts]
    model.constraint_rtp_cost_calculation = Constraint(model.ts, rule=rtp_cost_calculation, \
                                                          doc='constraint RTP cost calculation')
        
    def rtp_export_revenue_calculation(model, ts):
        if ts == model.ts.at(-1):
            return model.rtp_export_revenue[ts] == 0
        else:
            return model.rtp_export_revenue[ts] == \
                model.grid_export_site[ts] * model.utility_rtp_export[ts] \
                / model.timestep_scale_fwd[ts]
    model.constraint_rtp_export_revenue_calculation = Constraint(model.ts, rule=rtp_export_revenue_calculation, \
                                                                    doc='constraint RTP energy export revenue calculation')
    
    def sum_rtp_cost(model):
        return model.sum_rtp_cost == sum(model.rtp_cost[t] for t in accounting_ts)
    model.constraint_sum_rtp_cost = Constraint(rule=sum_rtp_cost, doc='RTP energy cost summation')
    
    def sum_rtp_export_revenue(model):
        export = 0
        if parameter['site']['export_max'] > 0:
            export = -1* sum(model.rtp_export_revenue[t] for t in accounting_ts)
        return model.sum_rtp_export_revenue == export
    model.constraint_sum_rtp_export_revenue = Constraint(rule=sum_rtp_export_revenue, doc='export RTP revenue calculation')
    
    # power demand costs
    def sum_demand_cost(model):
        demand = 0
        if parameter['site']['customer'] == 'Commercial':
            demand = sum(model.demand_charge_periods[p] * model.tariff_power[p] for p in model.periods)
            demand += model.demand_charge_overall * parameter['tariff']['demand_coincident']
        return model.sum_demand_cost == demand
    model.constraint_sum_demand_cost = Constraint(rule=sum_demand_cost, doc='demand cost calculation')
    
    
    
    # def sum_regulation_revenue(model):
    #     regulation = 0
    #     if parameter['site']['regulation'] or parameter['site']['regulation_reserved']:
    #         regulation = -1* sum(model.regulation_revenue[t] for t in accounting_ts)
    #     return model.sum_regulation_revenue == regulation
    # model.constraint_sum_regulation_revenue = Constraint(rule=sum_regulation_revenue, doc='regulation revenue calculation')    
        
    def total_cost(model):
        return model.total_cost == model.sum_energy_cost \
                                   + model.sum_demand_cost \
                                   - model.sum_export_revenue
    model.constraint_total_cost = Constraint(rule=total_cost, doc='total cost')
        
    return model
