#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

'''
import os
import sys
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

from ..utility import pandas_to_dict, pyomo_read_parameter, plot_streams, get_root, extract_properties    

def add_loadControl(model, inputs, parameter):
        
    # Check that load control enabled
    assert parameter['system']['load_control'] is True, \
        "Load Control is not enabled in system configuration"
    
    # list of required genset parameters
    loadParams =  ['name', 'cost', 'outageOnly']   
    # check that all load circuits have required parameters
    for cc in range(0, len(parameter['load_control'])):
        
        # if no name for load circuit provided, overwrite with number
        if 'name' not in parameter['load_control'][cc].keys():
            parameter['load_control'][cc]['name'] = f'{cc+1}'
        
        
        for pp in loadParams:
            assert pp in  parameter['load_control'][cc].keys(), \
                f'Load circuit {cc+1} missing required parameter: {pp}'
                
        # assert that inputs has load column for given circuit
        target_circuit_name = parameter['load_control'][cc]['name']
        target_col_name = f'load_shed_potential_{target_circuit_name}'
        assert target_col_name in inputs.columns, \
            f'Load profile for circuit {target_circuit_name} missing from input data'
        
   
    # Sets
    load_circuits = [circuit['name'] for circuit in parameter['load_control']]
    model.load_circuits = Set(initialize=load_circuits, doc='load circuits in the system')
    
    # Parameters  
    model.load_cost = Param(model.load_circuits, initialize=extract_properties(parameter, 'load_control', 'cost', load_circuits), \
                                doc='load control shed cost [$/kWh]')
    model.load_outageOnly = Param(model.load_circuits, initialize=extract_properties(parameter, 'load_control', 'outageOnly', load_circuits), \
                                doc='load control backup only [1/0]')
        
    # read in load_shed_potential ts-data by circuit name
    # data should exist as a column with name 'load_shed_potential_{c}', where c is name of load control circuit
    model.load_shed_potential = Param(model.ts, model.load_circuits, \
                                    initialize= \
                                    pandas_to_dict(inputs[[f'load_shed_potential_{c}' for c in model.load_circuits]] ,\
                                                    columns=model.load_circuits, convertTs=True), \
                                    doc='load she potential per circuit [kW]')
        
        
    # construct mapping of loadshed assest to node location
    model.loadshed_node_location = Param(model.load_circuits, model.nodes, default=0, mutable=True, \
                                doc='load shed asset to node location map')
        
    if not model.multiNode:
        # for single-node models, all load shed is applied at single node
        for nn in model.nodes:
            for cc in model.load_circuits:
                model.loadshed_node_location[cc, nn] = 1
            
    else:
        # for multinode models, create parameter mapping load shed assets to node based on location in parameter
        for node in parameter['network']['nodes']:
            
            # extract node name
            nn = node['node_id']
            
            # first check if node has ders key
            if 'ders' in node.keys():
                
                # then check that ders is not None
                if node['ders'] is not None:
                
                    # then check if load_control in ders
                    if 'load_control' in node['ders'].keys():
                        
                        # extract load_control input from parameter
                        loadControlInput = node['ders']['load_control']
                        
                        # loop through genset index to see if it's at that node
                        for cc in model.load_circuits:
                            
                            # check if param value is str
                            if type(loadControlInput) == str:
                                if str(cc) == loadControlInput:
                                    # if match found, set location to 1 in map param
                                    model.loadshed_node_location[cc, nn] = 1
                                    
                            # check if param value is list
                            if type(loadControlInput) == list:
                                # check if current genset from set is in input genset LIST
                                if str(cc) in loadControlInput:
                                    # if match found, set location to 1 in map param
                                    model.loadshed_node_location[cc, nn] = 1
        
    
                
    
    # # Variables
    model.load_circuits_on = Var(model.ts, model.load_circuits, \
                                              domain=Binary, doc='binary var indicating if load circuit is on [1/0]')    
    model.load_shed_circuit = Var(model.ts, model.load_circuits, bounds=(0, None), \
                                  doc='load shed amount due to load control use for each load circuit [kW]')
    
    # vars defined in basemodel
    # model.load_shed = Var(model.ts, model.nodes, bounds=(0, None), doc='load shed amount due to load control use [kW]')
    # model.load_shed_cost_total = Var(bounds=(0, None), doc='total load shed cost over horizon [$]')
        
    
    
    ## Constraints
    
    # load circuit must be on for outage-only if grid available
    def outage_shed_constraint(model, ts, load_circuit):
        return model.load_circuits_on[ts, load_circuit] >=  model.load_outageOnly[load_circuit] * model.grid_available[ts]
    model.constraint_outage_shed = Constraint(model.ts, model.load_circuits, \
                                                    rule=outage_shed_constraint, \
                                                    doc='constraint load shed for outage only')
        
    # load shed volume by circuit
    def circuit_shed_load(model, ts, load_circuit):
        return model.load_shed_circuit[ts, load_circuit] ==  model.load_shed_potential[ts, load_circuit] * (1 - model.load_circuits_on[ts, load_circuit])
    model.constraint_circuit_shed_load = Constraint(model.ts, model.load_circuits, \
                                                    rule=circuit_shed_load, \
                                                    doc='constraint load shed volume by circuit')
    
    # total load shed across all circuits
    def total_shed_load(model, ts):
        return model.load_shed_site[ts] ==  sum(model.load_shed_potential[ts, circuit] * (1 - model.load_circuits_on[ts, circuit]) \
                                              for circuit in model.load_circuits)
    model.constraint_total_shed_load= Constraint(model.ts, \
                                                    rule=total_shed_load, \
                                                    doc='constraint total load shed profile for all nodes/circuits')
    
    # load shed cost is the sum of load shed cost by time each circuit is off
    def total_shed_cost(model):
        return model.load_shed_cost_total ==  sum((model.load_cost[circuit] * model.load_shed_circuit[ts, circuit]) / model.timestep_scale[ts] \
                                              for circuit in model.load_circuits for ts in model.ts)
    model.constraint_total_shed_cost = Constraint(rule=total_shed_cost, \
                                                    doc='constraint net total shed cost')
        

    # map utilized load shed to node. Eqn works for single-node models by default
    def node_load_shed(model, ts, nodes):
        return model.load_shed[ts, nodes] ==  sum((model.load_shed_circuit[ts, load_circuit] * model.loadshed_node_location[load_circuit, nodes]) for load_circuit in model.load_circuits)
    model.constraint_node_load_shed = Constraint(model.ts, model.nodes, \
                                                                    rule=node_load_shed, \
                                                                    doc='constraint nodel load shed power')
        

    return model