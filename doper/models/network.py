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
import math
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pyomo.environ import ConcreteModel, Set, Param, Var, Constraint, Binary
from copy import deepcopy

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



def add_network(model, inputs, parameter):
    
    logging.warning('power flow model is currently under development. Models may not solve and/or produce accurate solutions')
        
    # create alias of node set
    # Note: pyomo doesn't seem to have ability to explicitly alias sets, so just copying nodes set
    nodesAliasList = model.nodes.ordered_data()
    model.nodesN = Set(initialize=nodesAliasList, doc='alias setnodes in the system')
    model.nNodes = len(model.nodes.ordered_data())
    
    # set simple power exchange vars to zero
    model.powerExchangeOut = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange injected from node [kW]')
    model.powerExchangeIn = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange absorbed at node [kW]')
    model.powerExchangeLosses = Var(model.ts, model.nodes, bounds=(0,0), doc='simple power exchange losses in network [kW]')
    
    model.slackNodeIndex = None
    
    # PARAMETERS
    #initialize param for node-line map
    model.node_pcc = Param(model.nodes, default=0, mutable=True, \
                                 doc='node pcc status')
    model.node_slack = Param(model.nodes, default=0, mutable=True, \
                                 doc='node slack bus status')
    model.node_connection = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='node-node connection map')
    model.node_connection_UT = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='node-node connection map - upper triangle only')
    model.line_capacity = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='branch capacity for node-connections')
    model.branch_real_imp = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='real imp in branch')
    model.branch_img_imp = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='imaginary imp in branch')
        
        
    model.line_len = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='cable length for node-connections')
    model.line_isTx = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='bin indicating line is transformer')
    model.line_powerCapacity = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='power capacity for node-connections')
    model.line_ampacity = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='cable ampacity for node-connections')
    model.line_res = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='cable resistance for node-connections')
    model.line_ind = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='cable inductance for node-connections')
        
    # define power factor by asset
    logging.warning('power factor current hardcoded in model')
    
    powerFactors = {
        'pv': 1,  
        'genset': 1,
        'batteryDisc': 1,
        'batteryChar': 1,
        'load': 1
    }
    
    cableDerating = 1
    txDerating = 1

    # define number of segments for current-square linear approx
    model.nEdges = 8
    
    
    model.slackBusVoltage = 1
    model.enableLosses = True
    genPqLimits = False
    
    model.consVoltMin = False
    model.thetaMin = -0.18
    model.thetaMax = 0.09
    model.voltMin = 0.8
    model.voltMax = 1.1
    
    # loop through nodes to define connections
    for node in parameter['network']['nodes']:
        node1Name = node['node_id']
        
        # get index of current node
        nodeIndex = model.nodes.ordered_data().index(node1Name)
        
        # check if node is pcc type
        if node['pcc'] is True:
            model.node_pcc[node1Name] = 1
            
            
        # check if node is slack/swing bus type
        if node['slack'] is True:
            model.node_slack[node1Name] = 1
            
            if model.slackNodeIndex is None:
                model.slackNodeIndex = nodeIndex
            else:
                logging.error('Multiple nodes designed as slack bus')
        
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
                lineLen = line['length']
                linePower = line['power_capacity']
                lineAmpacity = line['ampacity']
                lineRes = line['resistance']
                lineInd = line['inductance']
                
                # check if connection is a transformer
                isTx = False
                if 'isTransformer' in line.keys():
                    if line['isTransformer']:
                        isTx = True
                        
                # extract length only if connection is not transformer
                if not isTx:
                    
                    model.line_len[node1Name, node2Name] = lineLen

                
                model.node_connection[node1Name, node2Name] = 1
                model.line_capacity[node1Name, node2Name] = ((1-isTx) * cableDerating + isTx * txDerating) * lineAmpacity
                
                model.branch_real_imp[node1Name, node2Name] = ((1-isTx) * lineLen * lineRes) + (isTx * lineRes)
                model.branch_img_imp[node1Name, node2Name] = ((1-isTx) * lineLen * lineInd) + (isTx * lineInd)
                
                
                model.line_powerCapacity[node1Name, node2Name] = linePower
                # model.line_ampacity[node1Name, node2Name] = lineAmpacity
                model.line_res[node1Name, node2Name] = lineRes
                model.line_ind[node1Name, node2Name] = lineInd
                model.line_isTx[node1Name, node2Name] = isTx
                
                # get node indices from names of node1 and node2
                nodeIndex1 = list(model.nodes.ordered_data()).index(node1Name)
                nodeIndex2 = list(model.nodes.ordered_data()).index(node2Name)
                
                # update upper triangle node matrix if nodeIndex1 < nodeIndex2
                if nodeIndex1 < nodeIndex2:
                    model.node_connection_UT[node1Name, node2Name] = 1
                    
    
    # create set for non-slack nodes
    nodeListNoSlack = list(model.nodes.ordered_data())
    model.slackBusName = nodeListNoSlack.pop(model.slackNodeIndex)
    model.nodeListNoSlack = nodeListNoSlack
    
    model.nodesNoSlack = Set(initialize=nodeListNoSlack, doc='nodes in the system, omitting slack bus')
                
    # define sets for linearization of current-square
    curEdgeList = [f'edge{ii+1}' for ii in range(model.nEdges)]
    curEdgeNos = { f'edge{ii+1}':(ii+1) for ii in range(model.nEdges)} 
    model.edgeAngle = 2*3.1415 / model.nEdges 
    model.curEdges = Set(initialize=curEdgeList, ordered=True, doc='current-square edges')
    model.curEdgeNos = Param(model.curEdges, initialize=curEdgeNos, \
                                      doc='current-square edge number')
    
    # confirm newtork line properties are symmetric
    logging.info('checking network connections symmetry')
    
    # list of properties to check for symmetry
    propList = ['node_connection', 'line_len', 'line_powerCapacity',
                'line_ampacity', 'line_res', 'line_ind']
    
    for propName in propList:
        
        # for each prop, check symmetric
        propParam = getattr(model, propName)
        
        for n1 in model.nodes:
            for n2 in model.nodesN:
            
                # extract props values for n1-n2 vs n2-n1
                val1 = propParam.extract_values()[n1, n2]
                val2 = propParam.extract_values()[n2, n1]
                
                if val1 != val2:
                    
                    logging.warning(f'assymmetric data found for {propName} at nodes {n1}-{n2}')
                    
                    # use whatever is larger prop as value to mirror
                    val = max(val1, val2)
                    
                    logging.warning(f'setting value to {val}')
                    
                    propParam[n1, n2] = val
                    
                    propParam[n2, n1] = val
                    
        # update model param to reflect any changes
        setattr(model, propName, propParam)    
        
        
    # calculate network YBus and ZBus
    model = calcYandZ(model)                
    
    
    # variables
    model.electricity_var_provided = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power provided by assets at each node')
    model.electricity_var_purchased = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power from grid')
    model.electricity_var_pv = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power provided by pv at each node')
    model.electricity_var_battery = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power provided by batteries/EVs at each node')
    model.electricity_var_genset = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power provided by gensets at each node')
    
    model.electricity_var_consumed = Var(model.ts, model.nodes, bounds=(None, None), doc='total reactive power consumed at each node')
    
    model.real_power_inj = Var(model.ts, model.nodes, bounds=(None, None), doc='total real power injected at node')
    model.real_power_abs = Var(model.ts, model.nodes, bounds=(None, None), doc='total real power absorbed at node')
    model.imag_power_inj = Var(model.ts, model.nodes, bounds=(None, None), doc='total imag power injected at node')
    model.imag_power_abs = Var(model.ts, model.nodes, bounds=(None, None), doc='total imag power absorbed at node')
    
    model.voltage_real = Var(model.ts, model.nodes, bounds=(0, None), doc='real voltage at node')
    model.voltage_imag = Var(model.ts, model.nodes, bounds=(None, None), doc='imag voltage at node')
    
    model.real_branch_cur_power_square = Var(model.ts, model.nodes, model.nodesN, bounds=(0, None), doc='real branch current or power squared')
    model.imag_branch_cur_power_square = Var(model.ts, model.nodes, model.nodesN, bounds=(0, None), doc='imag branch current or power squared')
    model.real_branch_loss = Var(model.ts, model.nodes, model.nodesN, bounds=(0, None), doc='real power losses in branch')
    model.imag_branch_loss = Var(model.ts, model.nodes, model.nodesN, bounds=(0, None), doc='imag power losses in branch')
    
    model.real_branch_cur = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='real branch current')
    model.imag_branch_cur = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='imag branch current')
    
    model.real_branch_power = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='real branch power')
    model.imag_branch_power = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='imag branch power')
    
    model.real_branch_cur_power = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='real branch current or power, method dependent')
    model.imag_branch_cur_power = Var(model.ts, model.nodes, model.nodesN, bounds=(None, None), doc='imag branch current or power, method dependent')

    
    
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
        
    def pcc_var_import(model, ts, nodes):
        return model.electricity_var_purchased[ts, nodes] <= model.node_pcc[nodes] * parameter['site']['import_max']
    model.constraint_pcc_var_import = Constraint(model.ts, model.nodes, rule=pcc_var_import, \
                                                  doc='constraint pcc import')
                                                  
    def pcc_var_export(model, ts, nodes):
        return -model.electricity_var_purchased[ts, nodes] <= model.node_pcc[nodes] * parameter['site']['export_max']
    model.constraint_pcc_var_export = Constraint(model.ts, model.nodes, rule=pcc_var_export, \
                                                  doc='constraint pcc export')
        
    
                                                  
    
        
    def sum_var_provided(model, ts, nodes):
        return model.electricity_var_provided[ts, nodes] == model.electricity_var_purchased[ts, nodes] + \
                                                            model.electricity_var_pv[ts, nodes] + \
                                                            model.electricity_var_battery[ts, nodes] + \
                                                            model.electricity_var_genset[ts, nodes]
    model.constraint_sum_var_provided = Constraint(model.ts, model.nodes, rule=sum_var_provided, \
                                                  doc='constraint total var provided at node')
        
    def sum_var_consumed(model, ts, nodes):
        return model.electricity_var_consumed[ts, nodes] == model.load_served[ts, nodes] * math.tan(math.acos(powerFactors['load'])) + \
                                                            model.sum_battery_charge_grid_power[ts, nodes] * math.tan(math.acos(powerFactors['batteryChar']))
    model.constraint_sum_var_consumed = Constraint(model.ts, model.nodes, rule=sum_var_consumed, \
                                                  doc='constraint total var provided at node')
      
    # real/imaginary power absorbed/injected at each node
    def real_power_inj_eq(model, ts, nodes):
        return model.real_power_inj[ts, nodes] ==  (1/1000)*model.power_provided[ts, nodes]
    model.constraint_real_power_inj_eq = Constraint(model.ts, model.nodes, rule=real_power_inj_eq, \
                                                  doc='real power injected eq')  
        
    def real_power_abs_eq(model, ts, nodes):
        return model.real_power_abs[ts, nodes] ==  (1/1000)*model.power_consumed[ts, nodes]
    model.constraint_real_power_abs_eq = Constraint(model.ts, model.nodes, rule=real_power_abs_eq, \
                                                  doc='real power absorbed eq')  
        
    def imag_power_inj_eq(model, ts, nodes):
        return model.imag_power_inj[ts, nodes] ==  (1/1000)*model.electricity_var_provided[ts, nodes]
    model.constraint_imag_power_inj_eq = Constraint(model.ts, model.nodes, rule=imag_power_inj_eq, \
                                                  doc='imag power injected eq')  
        
    def imag_power_abs_eq(model, ts, nodes):
        return model.imag_power_abs[ts, nodes] ==  (1/1000)*model.electricity_var_consumed[ts, nodes]
    model.constraint_imag_power_abs_eq = Constraint(model.ts, model.nodes, rule=imag_power_abs_eq, \
                                                  doc='imag power absorbed eq')
    

    
    # constrain var from pv
    if not parameter['system']['pv']:
        
        # set reactive power to 0 if asset is not enabled
        def disable_reactive_pv(model, ts, nodes):
            return model.electricity_var_pv[ts, nodes] == 0
        model.constraint_disable_reactive_pv = Constraint(model.ts, model.nodes, rule=disable_reactive_pv, \
                                                              doc='disable pv var') 
            
    else:
        
        def pv_pq_constraint0(model, ts, nodes):
            if model.node_slack.extract_values()[nodes]: return Constraint.Feasible # constraint only applies if node is not slack bus
            else: return  model.electricity_var_pv[ts, nodes] == model.generation_pv[ts, nodes] * \
                math.tan(math.acos(powerFactors['pv']))
        
        model.constraint_pv_pq_constraint0 = Constraint(model.ts, model.nodes, rule=pv_pq_constraint0, \
                                                              doc='define var from powerfactor - pv') 
        
        # add PQ limits for ders, if enabled
        if genPqLimits:    
            # 1/sqrt(2)*P + 1/sqrt(2)*Q <= S
            def pv_pq_constraint1(model, ts, nodes):
                return  model.electricity_var_pv[ts, nodes] + model.generation_pv[ts, nodes] <= \
                    math.sqrt(2) * model.pv_max_s[nodes]
            
            model.constraint_pv_pq_constraint1 = Constraint(model.ts, model.nodes, rule=pv_pq_constraint1, \
                                                                  doc='reactive power constrait 1 - pv') 
            logging.warning('need to add input stream for pv inverter max S')
            
            # 1/sqrt(2)*P - 1/sqrt(2)*Q <= S
            def pv_pq_constraint2(model, ts, nodes):
                return  model.generation_pv[ts, nodes] - model.electricity_var_pv[ts, nodes] <= \
                    math.sqrt(2) * model.pv_max_s[nodes]
            
            model.constraint_pv_pq_constraint2 = Constraint(model.ts, model.nodes, rule=pv_pq_constraint2, \
                                                                  doc='reactive power constrait 2 - pv')
                
            # Q <= S
            def pv_pq_constraint3(model, ts, nodes):
                return  model.electricity_var_pv[ts, nodes] <= model.pv_max_s[nodes]
            
            model.constraint_pv_pq_constraint3 = Constraint(model.ts, model.nodes, rule=pv_pq_constraint3, \
                                                                  doc='reactive power constrait 3 - pv')
                
            # -S <= Q
            def pv_pq_constraint4(model, ts, nodes):
                return  model.electricity_var_pv[ts, nodes] >= -1 * model.pv_max_s[nodes]
            
            model.constraint_pv_pq_constraint4 = Constraint(model.ts, model.nodes, rule=pv_pq_constraint4, \
                                                                  doc='reactive power constrait 4 - pv')    
    
    
    
    
    # constrain var from gensets
    if not parameter['system']['genset']:
        
        # set reactive power to 0 if asset is not enabled
        def disable_reactive_genset(model, ts, nodes):
            return model.electricity_var_genset[ts, nodes] == 0
        model.constraint_disable_reactive_genset = Constraint(model.ts, model.nodes, rule=disable_reactive_genset, \
                                                              doc='disable genset var') 
            
    else:
        
        def genset_pq_constraint0(model, ts, nodes):
            if model.node_slack.extract_values()[nodes]: return Constraint.Feasible # constraint only applies if node is not slack bus
            else: return  model.electricity_var_genset[ts, nodes] == model.sum_genset_power[ts, nodes] * \
                math.tan(math.acos(powerFactors['genset']))
        
        model.constraint_genset_pq_constraint0 = Constraint(model.ts, model.nodes, rule=genset_pq_constraint0, \
                                                              doc='define var from powerfactor - genset') 
        
        # logging.warning('need to limit reactive power for units not operating?')
         
        # add PQ limits for ders, if enabled
        if genPqLimits:
            # 1/sqrt(2)*P + 1/sqrt(2)*Q <= S
            def genset_pq_constraint1(model, ts, nodes):
                return  model.electricity_var_genset[ts, nodes] + model.sum_genset_power[ts, nodes] <= \
                    math.sqrt(2) * sum(model.genset_max_s[gg] * model.genset_node_location[gg, nodes] for gg in model.gensets)
            
            model.constraint_genset_pq_constraint1 = Constraint(model.ts, model.nodes, rule=genset_pq_constraint1, \
                                                                  doc='reactive power constrait 1 - genset') 
            logging.warning('need to add input stream for genset  max S')
            
            # 1/sqrt(2)*P - 1/sqrt(2)*Q <= S
            def genset_pq_constraint2(model, ts, nodes):
                return  model.sum_genset_power[ts, nodes] - model.electricity_var_genset[ts, nodes] <= \
                    math.sqrt(2) * sum(model.genset_max_s[gg] * model.genset_node_location[gg, nodes] for gg in model.gensets)
            
            model.constraint_genset_pq_constraint2 = Constraint(model.ts, model.nodes, rule=genset_pq_constraint2, \
                                                                  doc='reactive power constrait 2 - genset')
                
            # Q <= S
            def genset_pq_constraint3(model, ts, nodes):
                return  model.electricity_var_genset[ts, nodes] <= sum(model.genset_max_s[gg] * model.genset_node_location[gg, nodes] for gg in model.gensets)
            
            model.constraint_genset_pq_constraint3 = Constraint(model.ts, model.nodes, rule=genset_pq_constraint3, \
                                                                  doc='reactive power constrait 3 - genset')
                
            # -S <= Q
            def genset_pq_constraint4(model, ts, nodes):
                return  model.electricity_var_genset[ts, nodes] >= -1 * sum(model.genset_max_s[gg] * model.genset_node_location[gg, nodes] for gg in model.gensets)
            
            model.constraint_genset_pq_constraint4 = Constraint(model.ts, model.nodes, rule=genset_pq_constraint4, \
                                                                  doc='reactive power constrait 4 - genset')
            

    
    # constrain var from batteries
    
    logging.warning('model does not distinguish batteries and ev when defining reactive power')
    
     # constrain var from batteries
    if not parameter['system']['battery']:
        
        # set reactive power to 0 if asset is not enabled
        def disable_reactive_battery(model, ts, nodes):
            return model.electricity_var_battery[ts, nodes] == 0
        model.constraint_disable_reactive_battery = Constraint(model.ts, model.nodes, rule=disable_reactive_battery, \
                                                              doc='disable battery var') 
            
    else:
        
        def battery_pq_constraint0(model, ts, nodes):
            if model.node_slack.extract_values()[nodes]: return Constraint.Feasible # constraint only applies if node is not slack bus
            else: return  model.electricity_var_battery[ts, nodes] == model.sum_battery_discharge_grid_power[ts, nodes] * \
                math.tan(math.acos(powerFactors['batteryDisc']))
        
        model.constraint_battery_pq_constraint0 = Constraint(model.ts, model.nodes, rule=battery_pq_constraint0, \
                                                              doc='define var from powerfactor - battery') 
        
        # add PQ limits for ders, if enabled
        if genPqLimits:    
            # 1/sqrt(2)*P + 1/sqrt(2)*Q <= S
            def battery_pq_constraint1(model, ts, nodes):
                return  model.electricity_var_battery[ts, nodes] + model.sum_battery_discharge_grid_power[ts, nodes] <= \
                    math.sqrt(2) * sum(model.bat_max_s[bb] * model.battery_node_location[bb, nodes] for bb in model.batteries)
            
            model.constraint_battery_pq_constraint1 = Constraint(model.ts, model.nodes, rule=battery_pq_constraint1, \
                                                                  doc='reactive power constrait 1 - battery') 
            logging.warning('need to add input stream for battery inverter max S')
            
            # 1/sqrt(2)*P - 1/sqrt(2)*Q <= S
            def battery_pq_constraint2(model, ts, nodes):
                return  model.sum_battery_discharge_grid_power[ts, nodes] - model.electricity_var_battery[ts, nodes] <= \
                    math.sqrt(2) * sum(model.bat_max_s[bb] * model.battery_node_location[bb, nodes] for bb in model.batteries)
            
            model.constraint_battery_pq_constraint2 = Constraint(model.ts, model.nodes, rule=battery_pq_constraint2, \
                                                                  doc='reactive power constrait 2 - battery')
                
            # Q <= S
            def battery_pq_constraint3(model, ts, nodes):
                return  model.electricity_var_battery[ts, nodes] <= sum(model.bat_max_s[bb] * model.battery_node_location[bb, nodes] for bb in model.batteries)
            
            model.constraint_battery_pq_constraint3 = Constraint(model.ts, model.nodes, rule=battery_pq_constraint3, \
                                                                  doc='reactive power constrait 3 - battery')
                
            # -S <= Q
            def battery_pq_constraint4(model, ts, nodes):
                return  model.electricity_var_battery[ts, nodes] >= -1 * sum(model.bat_max_s[bb] * model.battery_node_location[bb, nodes] for bb in model.batteries)
            
            model.constraint_battery_pq_constraint4 = Constraint(model.ts, model.nodes, rule=battery_pq_constraint4, \
                                                                  doc='reactive power constrait 4 - battery')
        
        
    # real and imag voltage constraint

    
    # fix voltages at slack bus
    for ts in model.ts:
        model.voltage_real[ts, model.slackBusName].fix(model.slackBusVoltage)
        model.voltage_imag[ts, model.slackBusName].fix(0)
    
    def pf_real_eq1(model, ts, nodes, nodesN):
                return  model.voltage_real[ts, nodes] == model.slackBusVoltage + (1/model.slackBusVoltage) * \
                   ( sum(model.realZBus[nodes, n]*(model.real_power_inj[ts, n] - model.real_power_abs[ts, n]) for n in model.nodesNoSlack) + \
                     sum(model.imagZBus[nodes, n]*(model.imag_power_inj[ts, n] - model.imag_power_abs[ts, n]) for n in model.nodesNoSlack) )
            
    model.constraint_pf_real_eq1 = Constraint(model.ts, model.nodesNoSlack, model.nodesNoSlack, rule=pf_real_eq1, \
                                                                  doc='real voltage constriant') 
        
    def pf_imag_eq1(model, ts, nodes, nodesN):
                return  model.voltage_imag[ts, nodes] == model.slackBusVoltage + (1/model.slackBusVoltage) * \
                   ( sum(model.imagZBus[nodes, n]*(model.real_power_inj[ts, n] - model.real_power_abs[ts, n]) for n in model.nodesNoSlack) - \
                     sum(model.realZBus[nodes, n]*(model.imag_power_inj[ts, n] - model.imag_power_abs[ts, n]) for n in model.nodesNoSlack) )
            
    model.constraint_pf_imag_eq1 = Constraint(model.ts, model.nodesNoSlack, model.nodesNoSlack, rule=pf_real_eq1, \
                                                                  doc='imag voltage constriant') 
        


   
    def pf_real_branch_loss_eq(model, ts, nodes, nodesN):
                return  model.real_branch_loss[ts, nodes, nodesN] == model.enableLosses * \
                    model.node_connection_UT[nodes, nodesN] * model.branch_real_imp[nodes, nodesN] * \
                    (model.real_branch_cur_power_square[ts, nodes, nodesN] + model.imag_branch_cur_power_square[ts, nodes, nodesN])
            
    model.constraint_pf_real_branch_loss_eq = Constraint(model.ts, model.nodes, model.nodesN, rule=pf_real_branch_loss_eq, \
                                                                  doc='real losses constriant') 
        
    def pf_imag_branch_loss_eq(model, ts, nodes, nodesN):
                return  model.real_branch_loss[ts, nodes, nodesN] == model.enableLosses * \
                    model.node_connection_UT[nodes, nodesN] * model.branch_imag_imp[nodes, nodesN] * \
                    (model.real_branch_cur_power_square[ts, nodes, nodesN] + model.imag_branch_cur_power_square[ts, nodes, nodesN])
            
    model.constraint_pf_imag_branch_loss_eq = Constraint(model.ts, model.nodes, model.nodesN, rule=pf_real_branch_loss_eq, \
                                                                  doc='imag losses constriant') 
        
    def pf_real_eq2(model, ts, nodes):
                return  sum(model.real_power_inj[ts, n] for n in model.nodes) == \
                    sum(model.real_power_abs[ts, n] for n in model.nodes) + \
                    sum(model.real_branch_loss[ts, n1, n2] for n1 in model.nodes for n2 in model.nodes)
            
    model.constraint_pf_real_eq2 = Constraint(model.ts, model.nodes, rule=pf_real_eq2, \
                                                                  doc='powerflow real power constriant') 
        
    def pf_imag_eq2(model, ts, nodes):
                return  sum(model.imag_power_inj[ts, n] for n in model.nodes) == \
                    sum(model.imag_power_abs[ts, n] for n in model.nodes) + \
                    sum(model.imag_branch_loss[ts, n1, n2] for n1 in model.nodes for n2 in model.nodes)
            
    model.constraint_pf_imag_eq2 = Constraint(model.ts, model.nodes, rule=pf_imag_eq2, \
                                                                  doc='powerflow imag power constriant') 
    
    
    def pf_real_cur(model, ts, nodes, nodesN):
        if model.node_connection_UT.extract_values()[nodes, nodesN]==0: return Constraint.Feasible
        else: return  model.real_branch_cur[ts, nodes, nodesN] == \
            -1 * model.realYBus[nodes, nodesN] * (model.voltage_real[ts, nodes] - model.voltage_real[ts, nodesN]) + \
            model.imagYBus[nodes, nodesN] * (model.voltage_imag[ts, nodes] - model.voltage_imag[ts, nodesN])
            
    model.constraint_pf_real_cur = Constraint(model.ts, model.nodes, model.nodesN, rule=pf_real_cur, \
                                                                  doc='powerflow real cuurent constriant')
        
    def pf_imag_cur(model, ts, nodes, nodesN):
        if model.node_connection_UT.extract_values()[nodes, nodesN]==0: return Constraint.Feasible
        else: return  model.imag_branch_cur[ts, nodes, nodesN] == \
            -1 * model.imagYBus[nodes, nodesN] * (model.voltage_real[ts, nodes] - model.voltage_real[ts, nodesN]) - \
            model.realYBus[nodes, nodesN] * (model.voltage_imag[ts, nodes] - model.voltage_imag[ts, nodesN])
            
    model.constraint_pf_imag_cur = Constraint(model.ts, model.nodes, model.nodesN, rule=pf_imag_cur, \
                                                                  doc='powerflow imag cuurent constriant')
        
    for n1 in model.nodes:
        for n2 in model.nodes:
            for ts in model.ts:
                if model.node_connection.extract_values()[n1, n2] == 0:
                    model.real_branch_cur[ts, n1, n2].fix(0)
                    model.imag_branch_cur[ts, n1, n2].fix(0)
                    
    # Bus Voltage Limits               
        
    if model.consVoltMin:
        
        model.voltMin  = model.voltMin/math.cos((abs(model.thetaMin)+abs(model.thetaMin))/2) ;
        
    def pf_volt_limit_eq1(model, ts, nodes):
        return model.voltage_imag[ts, nodes] <= \
            (math.sin(model.thetaMax)-math.sin(model.thetaMin)) / \
            (math.cos(model.thetaMax)-math.cos(model.thetaMin)) * \
            (model.voltage_real[ts, nodes]-model.voltMin*math.cos(model.thetaMin)) \
            + model.voltMin*math.sin(model.thetaMin)
            
    model.constraint_pf_volt_limit_eq1= Constraint(model.ts, model.nodes,rule=pf_volt_limit_eq1, \
                                                                  doc='bus voltage limit constriant 1')
        
    def pf_volt_limit_eq2(model, ts, nodes):
        return model.voltage_imag[ts, nodes] <= \
            (math.sin(model.thetaMax)) / \
            (math.cos(model.thetaMax)- 1) * \
            (model.voltage_real[ts, nodes]-model.voltMax)
            
    model.constraint_pf_volt_limit_eq2= Constraint(model.ts, model.nodes,rule=pf_volt_limit_eq2, \
                                                                  doc='bus voltage limit constriant 2')
        
    def pf_volt_limit_eq3(model, ts, nodes):
        return model.voltage_imag[ts, nodes] <= \
            (-1 * math.sin(model.thetaMin)) / \
            (math.cos(model.thetaMin)- 1) * \
            (model.voltage_real[ts, nodes]-model.voltMax)
            
    model.constraint_pf_volt_limit_eq3= Constraint(model.ts, model.nodes,rule=pf_volt_limit_eq3, \
                                                                  doc='bus voltage limit constriant 3')
        
    def pf_volt_limit_eq4(model, ts, nodes):
        return model.voltage_imag[ts, nodes] <= \
            model.voltage_real[ts, nodes] * math.tan(model.thetaMax)
            
    model.constraint_pf_volt_limit_eq4= Constraint(model.ts, model.nodes,rule=pf_volt_limit_eq4, \
                                                                  doc='bus voltage limit constriant 4')
        
    def pf_volt_limit_eq5(model, ts, nodes):
        return model.voltage_imag[ts, nodes] >= \
            model.voltage_real[ts, nodes] * math.tan(model.thetaMin)
            
    model.constraint_pf_volt_limit_eq5= Constraint(model.ts, model.nodes,rule=pf_volt_limit_eq5, \
                                                                  doc='bus voltage limit constriant 5')
        
    # CURRENT SQUARE APPROXIMATION AND LIMITS

    def pf_pos_imag_limit(model, ts, nodes, nodesN, edge):
        # don't apply when upper-triangle connection not present
        if model.node_connection_UT.extract_values()[nodes, nodesN]==0: return Constraint.Feasible
        # only apply for edges <= model.nEdges
        if model.curEdgeNos.extract_values()[edge] > model.nEdges/2: return Constraint.Feasible
        else:
            return model.imag_branch_cur[ts, nodes, nodesN] <= \
                math.sin(model.curEdgeNos[edge] * model.edgeAngle) * model.line_capacity[nodes, nodesN] + \
                (math.sin(model.curEdgeNos[edge] * model.edgeAngle) - math.sin((model.curEdgeNos[edge] - 1) * model.edgeAngle)) / \
                (math.cos(model.curEdgeNos[edge] * model.edgeAngle) - math.cos((model.curEdgeNos[edge] - 1) * model.edgeAngle)) * \
                (model.real_branch_cur[ts, nodes, nodesN] - math.cos(model.curEdgeNos[edge] * model.edgeAngle) * model.line_capacity[nodes, nodesN])
            
    model.constraint_pf_pos_imag_limit= Constraint(model.ts, model.nodes, model.nodes, model.curEdges ,rule=pf_pos_imag_limit, \
                                                                  doc='positive branch imag current limit linearization')

    def pf_neg_imag_limit(model, ts, nodes, nodesN, edge):
        # don't apply when upper-triangle connection not present
        if model.node_connection_UT.extract_values()[nodes, nodesN]==0: return Constraint.Feasible
        # only apply for edges <= model.nEdges
        if model.curEdgeNos.extract_values()[edge] <= model.nEdges/2: return Constraint.Feasible
        else:
            return model.imag_branch_cur[ts, nodes, nodesN] >= \
                math.sin(model.curEdgeNos[edge] * model.edgeAngle) * model.line_capacity[nodes, nodesN] + \
                (math.sin(model.curEdgeNos[edge] * model.edgeAngle) - math.sin((model.curEdgeNos[edge] - 1) * model.edgeAngle)) / \
                (math.cos(model.curEdgeNos[edge] * model.edgeAngle) - math.cos((model.curEdgeNos[edge] - 1) * model.edgeAngle)) * \
                (model.real_branch_cur[ts, nodes, nodesN] - math.cos(model.curEdgeNos[edge] * model.edgeAngle) * model.line_capacity[nodes, nodesN])
            
    model.constraint_pf_neg_imag_limit= Constraint(model.ts, model.nodes, model.nodes, model.curEdges ,rule=pf_neg_imag_limit, \
                                                                  doc='negative branch imag current limit linearization')

    # equate power/current var with current var since only method 1 currently implemented
    def pf_real_cur_eqn(model, ts, nodes, nodesN):
        return model.real_branch_cur[ts, nodes, nodesN] == model.real_branch_cur_power[ts, nodes, nodesN]
               
    model.constraint_pf_real_cur_eqn= Constraint(model.ts, model.nodes, model.nodes, rule=pf_real_cur_eqn, \
                                                                  doc='equate real cur/power to imag cur for method 1 only')

    def pf_imag_cur_eqn(model, ts, nodes, nodesN):
        return model.imag_branch_cur[ts, nodes, nodesN] == model.imag_branch_cur_power[ts, nodes, nodesN]
               
    model.constraint_pf_imag_cur_eqn= Constraint(model.ts, model.nodes, model.nodes, rule=pf_imag_cur_eqn, \
                                                                  doc='equate imag cur/power to imag cur for method 1 only')



    return model


def calcYandZ(model):
    
     # calc realYBus & imagYBus
    
    realYBus = [[0] * model.nNodes for x in range(model.nNodes)]
    imagYBus = [[0] * model.nNodes for x in range(model.nNodes)]
    
    for n1, node1Name in enumerate(model.nodes):
            for n2, node2Name in enumerate(model.nodes):
                
                # skip cells along diag, will be updated later
                if n1 == n2:
                    continue
                
                # otherwise, calculate ybus real/imag values
                
                # extract props for current connection
                lineRes = model.line_res.extract_values()[node1Name, node2Name]
                lineInd = model.line_ind.extract_values()[node1Name, node2Name]
                isTx = model.line_isTx.extract_values()[node1Name, node2Name]
                lineLen = model.line_len.extract_values()[node1Name, node2Name]
                
                
                # print(f'for {node1Name}-{node2Name}:')
                # print(f'line is tx: {isTx}')
                # print(f'')
                
                # if a connection exists, update value
                if isTx or lineLen > 0:
                    
                    realYBus[n1][n2] = -lineRes/((lineRes**2 + lineInd**2)*((isTx)+(1-isTx)*lineLen))
                    imagYBus[n1][n2] = lineInd/((lineRes**2 + lineInd**2)*((isTx)+(1-isTx)*lineLen))
                    
    # write values along diaganol of realYBus & imagYBus
    for n in range(model.nNodes):
        
        realYBusDiag = -sum(realYBus[n])
        imagYBusDiag = -sum(imagYBus[n])
        
        realYBus[n][n] = realYBusDiag
        imagYBus[n][n] = imagYBusDiag
                    
                    
    # calculate realZBus & imagZBus
    
    # get Ybus values without slack bus row/cols
    realYBusNoSlack = deepcopy(realYBus)
    imagYBusNoSlack = deepcopy(imagYBus)
    
    # remove element at index of slackNodeIndex from each row
    for nn in range(model.nNodes):
        dropVal = realYBusNoSlack[nn].pop(model.slackNodeIndex)
        dropVal = imagYBusNoSlack[nn].pop(model.slackNodeIndex)
        
    # remove row at slackNodeIndex
    dropVal = realYBusNoSlack.pop(model.slackNodeIndex)
    dropVal = imagYBusNoSlack.pop(model.slackNodeIndex)
    
    # invert results matrices to get Zbus values
    # satisfying eqs
    #    Yr*Zr - Yi*Zi = I
    #    Yi*Zr + Yr*Zi = 0    
    
    # realZBus is realYBus^-1
    realYMatrix= np.array(realYBusNoSlack)
    imagYMatrix= np.array(imagYBusNoSlack)
    
    realZBus = np.linalg.inv(realYMatrix)
    imagZBus = np.matmul(realZBus, np.matmul((-1*imagYMatrix), realZBus))
    
    # convert Y & Z matrices to pyomo objects
    realYBusDict = {}
    imagYBusDict = {}
    realZBusDict = {}
    imagZBusDict = {}
    
    for n1, node1Name in enumerate(model.nodes):
            for n2, node2Name in enumerate(model.nodes):
                
                realYBusDict[node1Name, node2Name] = realYBus[n1][n2]
                imagYBusDict[node1Name, node2Name] = imagYBus[n1][n2]
                
    model.realYBus = Param(model.nodes, model.nodesN, default=realYBusDict, mutable=False, \
                                 doc='real Y bus matrix for network')
    model.imagYBus = Param(model.nodes, model.nodesN, default=imagYBusDict, mutable=False, \
                                 doc='imag Y bus matrix for network')
        
    # for Z bus, need to loop through non-slack buses only
    
    for n1, node1Name in enumerate(model.nodeListNoSlack):
            for n2, node2Name in enumerate(model.nodeListNoSlack):
                
                realZBusDict[node1Name, node2Name] = realZBus[n1][n2]
                imagZBusDict[node1Name, node2Name] = imagZBus[n1][n2]
                
            # define slack bus entries as 0
            realZBusDict[node1Name, model.slackBusName] = 0
            realZBusDict[model.slackBusName, node1Name] = 0
            realZBusDict[model.slackBusName, model.slackBusName] = 0
            imagZBusDict[node1Name, model.slackBusName] = 0
            imagZBusDict[model.slackBusName, node1Name] = 0
            imagZBusDict[model.slackBusName, model.slackBusName] = 0
                
    
    model.realZBus = Param(model.nodes, model.nodesN, default=realZBusDict, mutable=False, \
                                 doc='real Z bus matrix for network')
    model.imagZBus = Param(model.nodes, model.nodesN, default=imagZBusDict, mutable=False, \
                                 doc='imag Z bus matrix for network')
        
        
    return model

def add_network_simple(model, inputs, parameter):
        
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
    model.node_connection = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='node-node connection map')
    model.node_connection_UT = Param(model.nodes, model.nodesN, default=0, mutable=True, \
                                 doc='node-node connection map - upper triangle only')
    model.line_powerCapacity = Param(model.nodes, model.nodesN, default=0, mutable=True, \
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
                linePower = line['power_capacity']
                model.line_powerCapacity[node1Name, node2Name] = linePower
                model.node_connection[node1Name, node2Name] = 1
               
                
                # get node indices from names of node1 and node2
                nodeIndex1 = list(model.nodes.ordered_data()).index(node1Name)
                nodeIndex2 = list(model.nodes.ordered_data()).index(node2Name)
                
                # update upper triangle node matrix if nodeIndex1 < nodeIndex2
                if nodeIndex1 < nodeIndex2:
                    model.node_connection_UT[node1Name, node2Name] = 1
                
            
    logging.warning('need to confirm symmetric connections')
     
    
    
    # variables
    
    model.powerExchangeLineOut = Var(model.ts, model.nodes, model.nodes, bounds=(0,None), doc='simple power exchange injected from node [kW]')
    model.powerExchangeLineIn = Var(model.ts, model.nodes, model.nodes, bounds=(0,None), doc='simple power exchange absorbed at node [kW]')
    model.powerExchangeLineLosses = Var(model.ts, model.nodes, model.nodes, bounds=(0,None), doc='simple power exchange losses in network [kW]')    
    
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
        
    # sum power exchanges in/out of node
    def node_power_in(model, ts, nodes, nodesN):
        return model.powerExchangeIn[ts, nodes] == sum(model.powerExchangeLineIn[ts, nodes, nodesN] for nodesN in model.nodes)
    model.contraints_node_power_in = Constraint(model.ts, model.nodes, model.nodesN, rule=node_power_in, \
                                                doc = 'constraint sum power flow into node')
        
    def node_power_out(model, ts, nodes, nodesN):
        return model.powerExchangeOut[ts, nodes] == sum(model.powerExchangeLineOut[ts, nodes, nodesN] for nodesN in model.nodes)
    model.contraints_node_power_out = Constraint(model.ts, model.nodes, model.nodesN, rule=node_power_out, \
                                                doc = 'constraint sum power flow out of node')
    
        
    def node_power_loss(model, ts, nodes, nodesN):
        return model.powerExchangeLosses[ts, nodes] == sum(model.powerExchangeLineLosses[ts, nodes, nodesN] for nodesN in model.nodes)
    model.contraints_node_power_loss = Constraint(model.ts, model.nodes, model.nodesN, rule=node_power_loss, \
                                                doc = 'constraint sum power flow lost at node from power exchange')
    
    # power into line, must equal power out minus losses
    def line_flow_balance(model, ts, nodes, nodesN):
        return model.powerExchangeLineOut[ts, nodes, nodesN] == model.powerExchangeLineIn[ts, nodesN, nodes] \
            + model.powerExchangeLineLosses[ts, nodes, nodesN]
    model.contraints_line_flow_balance = Constraint(model.ts, model.nodes, model.nodesN, rule=line_flow_balance, \
                                                doc = 'constraint balance power exchange in line')
            
    # power losses proportional to power into line
    def line_flow_losses(model, ts, nodes, nodesN):
        return model.powerExchangeLineLosses[ts, nodes, nodesN] == model.powerExchangeLineIn[ts, nodes, nodesN] \
            * parameter['network']['settings']['simpleNetworkLosses']
    model.contraints_line_flow_losses = Constraint(model.ts, model.nodes, model.nodesN, rule=line_flow_losses, \
                                                doc = 'constraint power lost in line due to exchange')
    
    # line max power constraint
    def line_max_capacity(model, ts, nodes, nodesN):
        return model.powerExchangeLineIn[ts, nodes, nodesN] <= model.line_powerCapacity[nodes, nodesN]
    model.contraints_line_max_capacity = Constraint(model.ts, model.nodes, model.nodesN, rule=line_max_capacity, \
                                                doc = 'constraint line max power capacity')
 
        
    return model