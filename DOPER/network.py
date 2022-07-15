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
sys.path.append(root)
from utility import pandas_to_dict, pyomo_read_parameter, plot_streams, get_root, extract_properties



def add_network(model, inputs, parameter):
        
    # create alias of node set
    # Note: pyomo doesn't seem to have ability to explicitly alias sets, so just copying nodes set
    nodesAliasList = model.nodes.ordered_data()
    model.nodesN = Set(initialize=nodesAliasList, doc='alias setnodes in the system')
    
    # PARAMETERS
    #initialize param for node-line map
    model.node_pcc = Param(model.nodes, default=0, mutable=True, \
                                 doc='node pcc status')
    model.node_node_map = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='node-node connection map')
    model.line_capacities = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='power capacity for node-connections')
    
    # loop through nodes to define connections
    for node in parameter['network']['nodes']:
        node1Name = node['node_id']
        
        # check if node is pcc type
        if node['pcc'] is True:
            model.node_pcc[node1Name] = 1
        
        # check if node has any connection
        if 'connections' not in node.keys():
            continue
        if type(node['connections']) is not list:
            continue
        else:
            for connection in node['connections']:
                
                node2Name = connection['node']
                
                # HERE, extract line properties for other network params
                lineName = connection['line']

                # locate line in params
                line = [lineData for lineData in parameter['network']['lines'] if lineData['line_id']==lineName]
                
                if len(line)==0:
                    logging.warning(f'line {lineName} could not be found in inputs')
                elif len(line)>1:
                    logging.warnring(f'multiple inputs found for line {lineName}')
                else:
                    line = line[0]
                
                # extract capacity and define
                lineCap = line['power_capacity']
                
                model.node_node_map[node1Name, node2Name] = 1
                model.line_capacities[node1Name, node2Name] = lineCap
                
            
    logging.warning('need to confirm symmetric connections')
     
    
    
    # variables
    
    # real power flow between lines
    model.line_power_real = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='power flow real between nodes [kW]')
    model.line_power_inj_real = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='power flow real between nodes [kW]')
    model.line_power_abs_real = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='power flow real between nodes [kW]')
    
    # model.line_power_real = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='power flow real between nodes [kW]')
    # model.line_power_real = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='power flow real between nodes [kW]')
    
    
    # equations
    
    # PCC import/export constraints   
    def pcc_import(model, ts, nodes):
        return model.grid_import[ts, nodes] <= model.node_pcc[nodes] * parameter['site']['import_max']
    model.constraint_pcc_import = Constraint(model.ts, model.nodes, rule=pcc_import, \
                                                  doc='constraint pcc import')
                                                  
    def pcc_export(model, ts, nodes):
        return model.grid_export[ts, nodes] <= model.node_pcc[nodes] * parameter['site']['export_max']
    model.constraint_pcc_export = Constraint(model.ts, model.nodes, rule=pcc_export, \
                                                  doc='constraint pcc export')
    
    # line balance (inj to and abs from line must sum to 0)
    def line_power_balance(model, ts, nodes, nodesN):
        return model.line_power_real[ts, nodes, nodesN] == -model.line_power_real[ts, nodesN, nodes]
    model.constraint_line_power_balance = Constraint(model.ts, model.nodes, model.nodesN, rule=line_power_balance, \
                                                            doc='constraint line power balnce')
    
    # line capacity (total inj and total abs must be below line power cap)
    
    # node balance (inj summed across alias nodes must equal inj total for node, abs also)
    def node_line_agg(model, ts, nodes):
        return (model.power_inj[ts, nodes] - model.power_abs[ts, nodes]) == sum(model.line_power_real[ts, nodes, nodesN] for nodesN in model.nodesN)
    model.constraint_node_line_agg = Constraint(model.ts, model.nodes, rule=node_line_agg, \
                                                            doc='constraint node power to lines')
        
    # def node_line_inj_agg(model, ts, nodes):
    #     return (model.power_inj[ts, nodes]) == sum(model.line_power_inj_real[ts, nodes, nodesN] for nodesN in model.nodesN)
    # model.constraint_node_line_inj_agg = Constraint(model.ts, model.nodes, rule=node_line_inj_agg, \
    #                                                         doc='constraint node power to lines')
        
    # def node_line_abs_agg(model, ts, nodes):
    #     return (model.power_abs[ts, nodes]) == sum(model.line_power_abs_real[ts, nodes, nodesN] for nodesN in model.nodesN)
    # model.constraint_node_line_abs_agg = Constraint(model.ts, model.nodes, rule=node_line_abs_agg, \
    #                                                         doc='constraint node power to lines')
    
    # calculate simple line losses based on power injected into mg network
    def network_losses_simple(model, ts, nodes):
        return model.power_networkLosses[ts, nodes] == \
            parameter['network']['settings']['simpleNetworkLosses'] * model.power_inj[ts, nodes]
    model.constraint_network_losses_simple = Constraint(model.ts, model.nodes, rule=network_losses_simple, \
                                                            doc='constraint simple line losses')
    
    # upper line capacity constraint
    def line_cap_upper(model, ts, nodes, nodesN):
        return model.line_power_real[ts, nodes, nodesN] <= model.line_capacities[nodes, nodesN]
    model.constraint_line_cap_upper = Constraint(model.ts, model.nodes, model.nodesN, rule=line_cap_upper, \
                                                            doc='constraint line capacity upper') 
        
    # lower line capacity constraint
    def line_cap_lower(model, ts, nodes, nodesN):
        return model.line_power_real[ts, nodes, nodesN] >= -model.line_capacities[nodes, nodesN]
    model.constraint_line_cap_lower = Constraint(model.ts, model.nodes, model.nodesN, rule=line_cap_lower, \
                                                            doc='constraint line capacity lower') 
        
    
   
        
 
        
    return model

