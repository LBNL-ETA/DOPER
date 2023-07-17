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
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyomo.environ import ConcreteModel, Set, Param, Var, Constraint, Binary, Any

def get_root(f=None):
    try:
        if not f:
            f = __file__
        root = os.path.dirname(os.path.abspath(f))
    except:
        root = os.getcwd()
    return root
root = get_root()

from ..utility import pandas_to_dict, pyomo_read_parameter, plot_streams, get_root, extract_properties

def add_battery(model, inputs, parameter):
    
    # Check that batteries are enabled
    assert parameter['system']['battery'] is True, \
        "Batteries are not enabled in system configuration"
    # check that correct number of generators defined
    # assert parameter['batteries']['count'] == len(parameter['batteries']['data']), \
    #     f"Battery count expected ({parameter['batteries']['count']}) does not match configuration data provided ({len(parameter['batteries']['data'])})"
    
    # list of required genset parameters
    batParams =  ['capacity', 'efficiency_charging', 'efficiency_discharging', 
                     'power_charge', 'power_discharge', 'self_discharging', 
                     'soc_initial', 'soc_max', 'soc_min']
    # check that all gensets have required parameters
    for bb in range(0, len(parameter['batteries'])):
        for pp in batParams:
            assert pp in  parameter['batteries'][bb].keys(), \
                f'Battery {bb+1} missing required parameter: {pp}'
                
    # check that initial and final SOCs are within allowed bounds
    for b in range(0, len(parameter['batteries'])):
        assert parameter['batteries'][b]['soc_initial'] >= parameter['batteries'][b]['soc_min'], \
            f"Battery SOC intial < SOC min for battery {b}"
        
        assert parameter['batteries'][b]['soc_initial'] <= parameter['batteries'][b]['soc_max'], \
            f"Battery SOC initial > SOC max for battery {b}"
        # if final SOC state is given, check that it is within allowed bounds   
        if 'soc_final' in parameter['batteries'][b]:
            if parameter['batteries'][b]['soc_final'] == True:
                # if no final SOC state is given, set it to the initial SOC
                parameter['batteries'][b]['soc_final'] = parameter['batteries'][b]['soc_initial']
            # assert final SOC within bounds, if defined
            if parameter['batteries'][b]['soc_final']:
                assert parameter['batteries'][b]['soc_final'] >= parameter['batteries'][b]['soc_min'], \
                    f"Battery SOC final < SOC min for battery {b}"
                assert parameter['batteries'][b]['soc_final'] <= parameter['batteries'][b]['soc_max'], \
                    f"Battery SOC final > SOC max for battery {b}"
        else:
            parameter['batteries'][b]['soc_final'] = False
    
    # extract list of battery asset names for define pyomo set
    batteryListInput = [battery['name'] for battery in parameter['batteries']]
        
     # Sets
    model.batteries = Set(initialize=batteryListInput, doc='batteries in the system')
    
    # check for existence of battery availability and external load columns in input df
    # these are only needed if battery is an EV. If they are not present, create them 
    # with full availability and 0 external load
    for b in model.batteries:
       if f'battery_{b}_avail' not in inputs.columns:
           inputs[f'battery_{b}_avail'] = 1
           inputs[f'battery_{b}_demand'] = 0
    
    model.battery_available = Param(model.ts, model.batteries, \
                                    initialize= \
                                    pandas_to_dict(inputs[['battery_{!s}_avail'.format(b) for b in model.batteries]] ,\
                                                    columns=model.batteries, convertTs=True), \
                                    doc='battery available [-]')
    model.battery_demand_ext = Param(model.ts, model.batteries, \
                                      initialize= \
                                      pandas_to_dict(inputs[['battery_{!s}_demand'.format(b) for b in model.batteries]] ,\
                                                    columns=model.batteries, convertTs=True), \
                                      doc='battery external demand [kW]')
    
    # model.battery_available = Param(model.ts, model.batteries, \
    #                                 initialize= 1, \
    #                                 doc='battery available [-]')
    # model.battery_demand_ext = Param(model.ts, model.batteries, \
    #                                   initialize= 0, \
    #                                   doc='battery external demand [kW]')
    
    # Parameters  
    model.bat_capacity = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'capacity', batteryListInput), \
                                doc='battery capacities [kWh]')
    model.bat_eff_charge = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'efficiency_charging', batteryListInput), \
                                doc='battery charging efficiency [-]')
    model.bat_eff_discharge = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'efficiency_discharging', batteryListInput), \
                                doc='battery discharging efficiency [-]')
    model.bat_power_charge = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'power_charge', batteryListInput), \
                                doc='battery max charging power [kW]')
    model.bat_power_discharge = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'power_discharge', batteryListInput), \
                                doc='battery max discharging power [kW]')
    model.bat_self_discharge = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'self_discharging', batteryListInput), \
                                doc='battery self discharge rate [-/hr]')
    model.bat_soc_end = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'soc_final', batteryListInput), \
                                doc='battery end SOC [-]', within=Any)
    model.bat_soc_init = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'soc_initial', batteryListInput), \
                                doc='battery initial SOC [-]')
    model.bat_soc_min = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'soc_min', batteryListInput), \
                                doc='battery minimum SOC [-]')
    model.bat_soc_max = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'soc_max', batteryListInput), \
                                doc='battery maximum SOC [-]')
        
    try:
        # try to extract max S capacity
        model.bat_max_s = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'maxS', batteryListInput), \
                                doc='battery max apprent power [kVA]')
    except:
        # if missing, just use max P
        model.bat_max_s = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'power_charge', batteryListInput), \
                                doc='battery max apprent power [kVA]')
            
    
    # these parameters are only used for battery degradation, and so should be extracted only when adding degrad equations
    # model.bat_degrad_eol = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'degradation_endoflife'), \
    #                             doc='battery degradation end of life')
    # model.bat_replace_cost = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'degradation_replacementcost'), \
    #                             doc='battery replacement cost [$]')
    # model.bat_nominal_v = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'nominal_V'), \
    #                             doc='battery nominal voltage [V]')
    # model.bat_temp_init = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'temperature_initial'), \
    #                             doc='battery initial temp [C]')
    # model.bat_thermal_c = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'thermal_C'), \
    #                             doc='battery thermal C')
    # model.bat_thermal_R = Param(model.batteries, initialize=extract_properties(parameter, 'batteries', 'thermal_R'), \
    #                             doc='battery thermal R')
    
    
    #initialize param mapping battery to node. values are updated below for multinode models
    model.battery_node_location = Param(model.batteries, model.nodes, default=0, mutable=True, \
                                doc='battery node location')
    
    # populate battery_node_location based on data in parameter dict
    if not model.multiNode:
        # for single-node models, all batteries located at single node
        for nn in model.nodes:
            for bb in model.batteries:
                model.battery_node_location[bb, nn] = 1
            
    else:
        # for multinode models, create parameter mapping battery to node based on location in parameter
        for node in parameter['network']['nodes']:
            
            # extract node name
            nn = node['node_id']
            
            # first check if node has ders key
            if 'ders' in node.keys():
                
                # then check that ders is not None
                if node['ders'] is not None:
                
                    # then check if battery in ders
                    if 'battery' in node['ders'].keys():
                        
                        # extract battery input from parameter
                        batteryInput = node['ders']['battery']
                        
                        # loop through genset index to see if it's at that node
                        for bb in model.batteries:
                            
                            # check if param value is str
                            if type(batteryInput) == str:
                                if str(bb) == batteryInput:
                                    # if match found, set location to 1 in map param
                                    model.battery_node_location[bb, nn] = 1
                                    
                            # check if param value is list
                            if type(batteryInput) == list:
                                # check if current genset from set is in input genset LIST
                                if str(bb) in batteryInput:
                                    # if match found, set location to 1 in map param
                                    model.battery_node_location[bb, nn] = 1
        

    
    # Variables
    # model.sum_battery_charge_grid_power = Var(model.ts, doc='total battery charge power on AC side of inveter [kW]')
    # model.sum_battery_discharge_grid_power = Var(model.ts, doc='total battery discharge power on AC side of inveter [kW]')
    # model.sum_battery_energy = Var(model.ts, doc='total battery stored energy [kWh]')    
    model.sum_battery_selfdischarge_power = Var(model.ts, doc='total battery self-discharge [kW]')
    # model.sum_battery_charge_power = Var(model.ts, doc='total limit battery charge [kW]')
    # model.sum_battery_discharge_power = Var(model.ts, doc='total limit battery discharge [kW]')
    
    model.battery_charge_power = Var(model.ts, model.batteries, \
                                          bounds=(0, None), doc='battery cell side charge [kW]')
    model.battery_discharge_power = Var(model.ts, model.batteries, \
                                              bounds=(0, None), doc='battery cell side discharge [kW]')
    
    model.battery_chargeXORdischarge = Var(model.ts, model.batteries, domain=Binary, \
                                            doc='battery charge or discharge binary [-]')
    model.battery_soc = Var(model.ts, model.batteries, bounds=(0, None), doc='battery soc [-]')
    model.battery_agg_soc = Var(model.ts, bounds=(0, None), doc='battery aggregated state-of-charge [-]')
    
    def battery_charge_power_bounds(model, ts, battery):
        return (0, model.bat_power_charge[battery])
    model.battery_charge_grid_power = Var(model.ts, model.batteries, bounds=battery_charge_power_bounds, \
                                      doc='limit battery charge [kW]')
    def battery_discharge_power_bounds(model, ts, battery):
        return (0, model.bat_power_discharge[battery])
    model.battery_discharge_grid_power = Var(model.ts, model.batteries, bounds=battery_discharge_power_bounds, \
                                        doc='limit battery discharge [kW]')    
    
    def battery_energy_bounds(model, ts, battery):
        return (model.bat_soc_min[battery]*model.bat_capacity[battery], \
                model.bat_soc_max[battery]*model.bat_capacity[battery])
    model.battery_energy = Var(model.ts, model.batteries, bounds=battery_energy_bounds, \
                                doc='battery stored energy [kWh]')
    # Note: double check how this is implemented. Shoulds be applied to energy in storage, not bounds by a max
    # def battery_selfdischarge_bounds(model, ts, battery):
    #     return (0, model.bat_self_discharge[battery])
    model.battery_selfdischarge_power = Var(model.ts, model.batteries, bounds=(0, None), \
                                            doc='battery self-discharge [kW]')
                                            
    def battery_soc(model, ts, battery):
        return model.battery_soc[ts, battery] == model.battery_energy[ts, battery] / \
                                                 max(model.bat_capacity[battery], 1e-3)
    model.constraint_battery_soc = Constraint(model.ts, model.batteries, rule=battery_soc, \
                                              doc='constraint battery SOC calculation')
    
    # fix final state of energy in last step
    for b in model.batteries:
        if model.bat_soc_end[b]:
            model.battery_energy[model.ts.at(len(model.ts)), b] = model.bat_soc_end[b] * \
                                                                model.bat_capacity[b]
            model.battery_energy[model.ts.at(len(model.ts)), b].fixed = True
      
    # equations
    def battery_soc_aggregation(model, ts):
        return model.battery_agg_soc[ts] == sum(model.battery_energy[ts, battery] for battery in model.batteries) / \
                                            sum(model.bat_capacity[battery] for battery in model.batteries)
    model.constraint_battery_soc_aggregation = Constraint(model.ts, rule=battery_soc_aggregation, \
                                                            doc='constraint battery SOC aggregation')
    

        
    # def sum_battery_energy(model, ts):
    #     return model.sum_battery_energy[ts] == sum(model.battery_energy[ts, battery] for battery in model.batteries)
    # model.constraint_sum_battery_energy = Constraint(model.ts, rule=sum_battery_energy, \
    #                                                   doc='sum of all battery energy')
        
    # def sum_battery_selfdischarge(model, ts):
    #     return model.sum_battery_selfdischarge_power[ts] == sum(model.battery_selfdischarge_power[ts, battery] \
    #                                                             for battery in model.batteries)
    # model.constraint_sum_battery_selfdischarge = Constraint(model.ts, rule=sum_battery_selfdischarge, \
    #                                                         doc='sum of all battery self discharge')
        
    # def sum_battery_charge(model, ts):
    #     return model.sum_battery_charge_power[ts] == sum(model.battery_charge_power[ts, battery] \
    #                                                       for battery in model.batteries)
    # model.constraint_sum_battery_charge = Constraint(model.ts, rule=sum_battery_charge, \
    #                                                   doc='sum of all battery charging')
        
    # def sum_battery_discharge(model, ts):
    #     return model.sum_battery_discharge_power[ts] == sum(model.battery_discharge_power[ts, battery] \
    #                                                         for battery in model.batteries)
    # model.constraint_sum_battery_discharge = Constraint(model.ts, rule=sum_battery_discharge, \
    #                                                     doc='sum of all battery discharging') 
        
    # def sum_battery_regulation_up(model, ts):
    #     return model.sum_regulation_up[ts] == sum(model.regulation_up[ts, battery] \
    #                                               for battery in model.batteries)
    # model.constraint_sum_battery_regulation_up = Constraint(model.ts, rule=sum_battery_regulation_up, \
    #                                                         doc='sum of all battery regulation up')
    # def sum_battery_regulation_dn(model, ts):
    #     return model.sum_regulation_dn[ts] == sum(model.regulation_dn[ts, battery] \
    #                                               for battery in model.batteries)
    # model.constraint_sum_battery_regulation_dn = Constraint(model.ts, rule=sum_battery_regulation_dn, \
    #                                                         doc='sum of all battery regulation dn') 
    
    def battery_charge_losses(model, ts, battery):
        return model.battery_charge_power[ts, battery] == (model.battery_charge_grid_power[ts, battery] ) \
                                                          * model.bat_eff_charge[battery]
    model.constraint_battery_charge_losses = Constraint(model.ts, model.batteries, rule=battery_charge_losses, \
                                                          doc='constraint battery charging') 
    def battery_discharge_losses(model, ts, battery):
        return model.battery_discharge_power[ts, battery] == (model.battery_discharge_grid_power[ts, battery] )\
                                                              / model.bat_eff_discharge[battery]
    model.constraint_battery_discharge_losses = Constraint(model.ts, model.batteries, rule=battery_discharge_losses, \
                                                            doc='constraint battery discharging')   
        
    def battery_selfdischarge_losses(model, ts, battery):
        if ts == model.ts.at(1):
            return model.battery_selfdischarge_power[ts, battery] == 0
        else:
            return model.battery_selfdischarge_power[ts, battery] == model.battery_energy[ts-model.timestep[ts], battery] \
                                                                      * model.bat_self_discharge[battery] / model.timestep_scale[ts]
    model.constraint_battery_selfdischarge_losses = Constraint(model.ts, model.batteries, rule=battery_selfdischarge_losses, \
                                                                doc='constraint battery self-discharging')
    
    def battery_energy_balance(model, ts, battery):
        if ts == model.ts.at(1):
            return model.battery_energy[ts, battery] == model.bat_soc_init[battery] \
                                                        * model.bat_capacity[battery]
        else: 
            return model.battery_energy[ts, battery] == model.battery_energy[ts-model.timestep[ts], battery] \
                                                        + (+ model.battery_charge_power[ts-model.timestep[ts], battery] \
                                                            - model.battery_discharge_power[ts-model.timestep[ts], battery] \
                                                            - model.battery_selfdischarge_power[ts, battery] \
                                                            - model.battery_demand_ext[ts-model.timestep[ts], battery]) \
                                                        / model.timestep_scale[ts]

    # def battery_energy_balance(model, ts, battery):
        
    #     return model.battery_energy[ts, battery] == model.bat_soc_init[battery] * model.bat_capacity[battery]

    model.constraint_battery_energy_balance = Constraint(model.ts, model.batteries, rule=battery_energy_balance, \
                                                          doc='constraint battery energy balance')
    
    
    # Battery Charing XOR Discharging
    def battery_charge_XOR_discharge(model, ts, battery):
        return model.battery_charge_power[ts, battery] <=  model.battery_chargeXORdischarge[ts, battery] \
                                                            * model.bat_power_charge[battery] \
                                                            * model.battery_available[ts, battery]
    model.constraint_battery_charge_XOR_discharge = Constraint(model.ts, model.batteries, \
                                                                rule=battery_charge_XOR_discharge, \
                                                                doc='constraint battery charging xor discharging')  
    def battery_discharge_XOR_charge(model, ts, battery):
        return model.battery_discharge_power[ts, battery] <=  (1 - model.battery_chargeXORdischarge[ts, battery]) \
                                                                * model.bat_power_discharge[battery] \
                                                                * model.battery_available[ts, battery]
    model.constraint_battery_discharge_XOR_charge = Constraint(model.ts, model.batteries, \
                                                                rule=battery_discharge_XOR_charge, \
                                                                doc='constraint battery discharging xor charging')
    
    # # Battery Regulation XOR Building support
    # model.battery_regulationXORbuilding = Var(model.ts, model.batteries, domain=Binary, initialize=0, \
    #                                           doc='battery regulation or building binary [-]')
    # if parameter['site']['regulation_xor_building']:
    #     def battery_regulation_XOR_building(model, ts, battery):
    #         return model.battery_discharge_grid_power[ts, battery] \
    #                + model.battery_charge_grid_power[ts, battery] <= (1 - model.battery_regulationXORbuilding[ts, battery]) \
    #                                                                  * (parameter['battery']['power_charge'][battery] \
    #                                                                     + parameter['battery']['power_discharge'][battery]) \
    #                                                                  * model.battery_available[ts, battery]
    #     model.constraint_battery_regulation_XOR_building = Constraint(model.ts, model.batteries, \
    #                                                                   rule=battery_regulation_XOR_building, \
    #                                                                   doc='constraint regulation xor building')  
    #     def battery_building_XOR_regulation(model, ts, battery):
    #         return model.regulation_dn[ts, battery] \
    #                + model.regulation_up[ts, battery] <= model.battery_regulationXORbuilding[ts, battery] \
    #                                                      * (parameter['battery']['power_charge'][battery] \
    #                                                         + parameter['battery']['power_discharge'][battery]) \
    #                                                      * model.battery_available[ts, battery]
    #     model.constraint_battery_building_XOR_regulation = Constraint(model.ts, model.batteries, \
    #                                                                   rule=battery_building_XOR_regulation, \
    #                                                                   doc='constraint building xor regulation')
    
    # #else:
    # #    def battery_chargeXORdischarge(model, ts, battery):
    # #        return model.battery_charge_power[ts, battery] * model.battery_discharge_power[ts, battery] <= 0
    # #    model.constraint_battery_chargeXORdischarge = Constraint(model.ts, model.batteries, \
    # #                                                             rule=battery_chargeXORdischarge, \
    # #                                                             doc='constraint battery charge or discharge')
    
    # # Regulation Up XOR Dn
    # #if use_binary:
    # model.regulation_all = Var(model.ts, doc='regulation all binary [-]',  domain=Binary, initialize=0) 
    # if parameter['site']['regulation_all']:       
    #     def regulation_all(model, ts):
    #         return sum(model.battery_regulationXORbuilding[ts, battery] \
    #                    for battery in model.batteries) ==  model.regulation_all[ts] * parameter['battery']['count']
    #     model.constraint_regulation_all = Constraint(model.ts, rule=regulation_all, \
    #                                                  doc='constraint regulation all batteries')
        

#assert not ((timestep_scale != 1) and (parameter['site']['regulation'])), \
#    assert not ((int(np.array([model.timestep[k] for k in sorted(model.timestep.keys())[1:]]).mean() /60/60) != 1) and (parameter['site']['regulation'])), \
#        "Regulation is only supported for hourly timesteps. Please set parameter['site']['regulation'] = False."
#    assert not (parameter['site']['regulation_reserved'] and parameter['site']['regulation_symmetric']), \
#        "Please disable parameter['site']['regulation_symmetric'] when parameter['site']['regulation_reserved'] is used." 
#    assert not (parameter['site']['regulation_xor'] and parameter['site']['regulation_symmetric']), \
#        "Please slect either parameter['site']['regulation_xor'] or parameter['site']['regulation_symmetric']."
        
    # if parameter['site']['regulation_xor']:
    #     model.regulation_upXORdn = Var(model.ts, doc='regulation up xor down binary [-]',  domain=Binary)
    #     def regulation_up_XOR_dn(model, ts):
    #         return model.sum_regulation_up[ts] <=  model.regulation_upXORdn[ts] * parameter['site']['import_max']
    #     model.constraint_regulation_up_XOR_dn = Constraint(model.ts, rule=regulation_up_XOR_dn, \
    #                                                        doc='constraint regulation up xor down')  
    #     def regulation_dn_XOR_up(model, ts):
    #         return model.sum_regulation_dn[ts] <=  (1 - model.regulation_upXORdn[ts]) * parameter['site']['import_max']
    #     model.constraint_regulation_dn_XOR_up = Constraint(model.ts, rule=regulation_dn_XOR_up, \
    #                                                        doc='constraint regulation down xor up') 
        
    # if parameter['site']['regulation_min']:
    #     def regulation_up_min(model, ts):
    #         return model.sum_regulation_up[ts] >= model.regulation_up_min[ts] * parameter['site']['regulation_min']
    #     model.constraint_regulation_up_min = Constraint(model.ts, rule=regulation_up_min, \
    #                                                     doc='constraint regulation up min')  
    #     def regulation_dn_min(model, ts):
    #         return model.sum_regulation_dn[ts] >= model.regulation_dn_min[ts] * parameter['site']['regulation_min']
    #     model.constraint_regulation_dn_min = Constraint(model.ts, rule=regulation_dn_min, \
    #                                                     doc='constraint regulation dn min')  
        
    # if parameter['site']['regulation_symmetric']:
    #     def regulation_sym(model, ts):
    #         return model.sum_regulation_dn[ts] == model.sum_regulation_up[ts]
    #     model.constraint_regulation_sym = Constraint(model.ts, rule=regulation_sym, \
    #                                                  doc='constraint regulation symmetric')
    # #else:
    # #    def regulation_upXORdn(model, ts):
    # #        return model.sum_regulation_up[ts] * model.sum_regulation_dn[ts] <= 0
    # #    model.constraint_regulation_upXORdn = Constraint(model.ts, rule=regulation_upXORdn, \
    # #                                                     doc='constraint regulation up or down') 
    
    # aggregate battery power output by node, works by default for single-node models
    def sum_battery_charge_grid(model, ts, nodes):
        return model.sum_battery_charge_grid_power[ts, nodes] == sum((model.battery_charge_grid_power[ts, battery] * model.battery_node_location[battery, nodes]) \
                                                              for battery in model.batteries)
    model.constraint_sum_battery_charge_grid = Constraint(model.ts, model.nodes, rule=sum_battery_charge_grid, \
                                                          doc='sum of all battery charging')
        
    def sum_battery_discharge_grid(model, ts, nodes):
        return model.sum_battery_discharge_grid_power[ts, nodes] == sum((model.battery_discharge_grid_power[ts, battery] * model.battery_node_location[battery, nodes]) \
                                                                  for battery in model.batteries)
    model.constraint_sum_battery_discharge_grid = Constraint(model.ts, model.nodes, rule=sum_battery_discharge_grid, \
                                                              doc='sum of all battery discharging')
            
    # sum site-wide battery input & output
    def site_total_battery_charge(model, ts, nodes):
        return model.sum_battery_charge_grid_power_site[ts] ==  sum(model.sum_battery_charge_grid_power[ts, node] for node in model.nodes)
    model.constraint_site_total_battery_charge = Constraint(model.ts,  model.nodes, \
                                                                    rule=site_total_battery_charge, \
                                                                    doc='site total battery charging power')
        
    def site_total_battery_discharge(model, ts, nodes):
        return model.sum_battery_discharge_grid_power_site[ts] ==  sum(model.sum_battery_discharge_grid_power[ts, node] for node in model.nodes)
    model.constraint_site_total_battery_discharge = Constraint(model.ts,  model.nodes, \
                                                                    rule=site_total_battery_discharge, \
                                                                    doc='site total battery discharging power')
    
            
        
    return model



# Converter
def convert_battery(model, parameter):
    columns = ['Battery Power [kW]','Battery Energy [kWh]','Battery Self Discharge [kW]',
               'Battery Avilable [-]','Battery External [kW]','Battery AC Power [kW]','Site Regulation [-]']
    df = {}
    for t in model.ts:
        df[t] = [model.sum_battery_charge_power[t].value-model.sum_battery_discharge_power[t].value,
                 model.sum_battery_energy[t].value, model.sum_battery_selfdischarge_power[t].value]
        # Available
        df[t] += [sum([model.battery_available[t,b] for b in model.batteries])/len(model.batteries)]
        # External Demand
        df[t] += [sum([model.battery_demand_ext[t,b] for b in model.batteries])]
        # External Demand
        df[t] += [model.sum_battery_charge_grid_power[t].value-model.sum_battery_discharge_grid_power[t].value]
        # Regulation
        df[t] += [model.regulation_all[t].value]
        for b in model.batteries:
            df[t] += [model.battery_charge_power[t,b].value-model.battery_discharge_power[t,b].value,
                      model.battery_energy[t,b].value, model.battery_available[t,b], model.battery_demand_ext[t,b],
                      model.battery_charge_grid_power[t,b].value-model.battery_discharge_grid_power[t,b].value,
                      model.battery_regulationXORbuilding[t,b].value]
            if parameter['site']['regulation_reserved_battery']:
                df[t] += [model.regulation_up[t,b], model.regulation_dn[t,b],
                          model.regulation_dn[t,b]-model.regulation_up[t,b]]
            else:
                df[t] += [model.regulation_up[t,b].value, model.regulation_dn[t,b].value,
                          model.regulation_dn[t,b].value-model.regulation_up[t,b].value]
    for b in model.batteries:        
        columns += ['Battery {!s} Power [kW]'.format(b), 'Battery {!s} Energy [kWh]'.format(b),
                    'Battery {!s} Available [-]'.format(b), 'Battery {!s} External [kW]'.format(b),
                    'Battery {!s} AC Power [kW]'.format(b), 'Battery {!s} Regulation [-]'.format(b),
                    'Battery {!s} Reg Up [kW]'.format(b), 'Battery {!s} Reg Dn [kW]'.format(b),
                    'Battery {!s} Reg Power [kW]'.format(b)]


    df = pd.DataFrame(df).transpose()
    df.columns = columns
    df.index = pd.to_datetime(df.index, unit='s')
    df['Battery SOC [%]'] = df['Battery Energy [kWh]'] / float(sum(parameter['battery']['capacity']))
    for b in model.batteries:
        df['Battery {!s} SOC [%]'.format(b)] = df['Battery {!s} Energy [kWh]'.format(b)] \
                                               / float(parameter['battery']['capacity'][b])
    return df
    
def plot_battery1(df, model, plot=True, tight=True):
    '''
        A standard plotting template to present results.

        Input
        -----
            df (pandas.DataFrame): The resulting dataframe with the optimization result.
            plot (bool): Flag to plot or return the figure. (default=True)
            plot_times (bool): Flag if time separation should be plotted. (default=True)
            tight (bool): Flag to use tight_layout. (default=True)
            
        Returns
        -------
            None if plot == True.
            else:
                fig (matplotlib figure): Figure of the plot.
                axs (numpy.ndarray of matplotlib.axes._subplots.AxesSubplot): Axis of the plot.
    '''
    n = 5
    if 'Battery 0 Temperature [C]' in df.columns:
        n += 1
    fig, axs = plt.subplots(n,1, figsize=(12, n*3), sharex=True, sharey=False, gridspec_kw = {'width_ratios':[1]})
    axs = axs.ravel()
    plot_streams(axs[0], df[['Battery Power [kW]','Load Power [kW]','PV Power [kW]']], \
                 title='Overview', ylabel='Power [kW]\n(<0:supply; >0:demand)', \
                 legend=['Battery','Load','PV'])
    plot_streams(axs[1], df[['Battery Power [kW]']+['Battery {!s} Power [kW]'.format(b) for b in model.batteries]], \
                 title='Battery Utilization', ylabel='Power [kW]\n(<0:discharge; >0:charge)', \
                 legend=['Total']+['Battery {!s}'.format(b) for b in model.batteries])
    plot_streams(axs[2], df[['Battery SOC [%]']+['Battery {!s} SOC [%]'.format(b) for b in model.batteries]]*100, \
                 title='Battery State of Charge', ylabel='SOC [%]', \
                 legend=['Total']+['Battery {!s}'.format(b) for b in model.batteries])
    plot_streams(axs[3], df[['Battery Avilable [-]']+['Battery {!s} Available [-]'.format(b) for b in model.batteries]], \
             title='Battery Availability', ylabel='Availability [-]\n(0:False; 1:True)', \
             legend=['Total']+['Battery {!s}'.format(b) for b in model.batteries])
    plot_streams(axs[4], df[['Battery External [kW]']+['Battery {!s} External [kW]'.format(b) for b in model.batteries]], \
             title='Battery External Demand', ylabel='Power [kW]', \
             legend=['Total']+['Battery {!s}'.format(b) for b in model.batteries])
    if 'Battery 0 Temperature [C]' in df.columns: 
        plot_streams(axs[5], df[['Temperature [C]']+['Battery {!s} Temperature [C]'.format(b) for b in model.batteries]], \
                 title='Battery Temperature', ylabel='Temperature [C]', \
                 legend=['Outside']+['Battery {!s}'.format(b) for b in model.batteries])
    if plot:
        if tight:
            plt.tight_layout()
        plt.show()
    else: return fig, axs