#!/usr/bin/env python
'''
    INTERNAL USE ONLY
    Module of DOPER package (v1.0)
    cgehbauer@lbl.gov

    Version info (v1.0):
        -) Initial disaggregation of old code.
'''
from pyomo.environ import ConcreteModel, Set, Param, Var, Constraint

def add_batterydegradation(model, inputs, parameter):

    model.battery_temperature = Var(model.ts, model.batteries, doc='battery temperature [C]')
    model.battery_calendaraging = Var(model.ts, model.batteries, doc='battery calendar aging [%]')
    model.battery_cycleaging = Var(model.ts, model.batteries, doc='battery cycle aging [%]')
    model.battery_degradation = Var(model.ts, model.batteries, doc='battery degradation [%]')
    model.sum_battery_degradation = Var(model.ts, doc='sum of battery degradation [%]')
    model.sum_battery_degradation_battery = Var(model.batteries, doc='battery degradation per battery [%]')
    
    #'''
    # ChrisNEW
    degradation_parameter = {'calendar': {'a0': 25727.068930200516, 'b0': 0.5685204330581881, 'b1': -70.48414456662813}, \
                             'cycle': {'a0': -0.010145570078488129, 'b0': 0.0003138082941656188, \
                                       'b1': 0.0008476522109451572, 'b2': 0.001229871720643372}}
    '''
    #V2GSim (cycle) and Wang/ChrisNEW (calendar)
    degradation_parameter = {'calendar': {'a0': 25727.068930200516, 'b0': 0.5685204330581881, 'b1': -70.48414456662813}, \
                             'cycle': {'a0': 210640.2753759454, 'b0': 0.40269429065813955, \
                                       'b1': 1.1881405336681485, 'b2': -70.2163516693157}}
    '''
    
    
        # Battery degradation
    def battery_temperature(model, ts, battery):
        # Validated with RC Model.ipynb
        R = parameter['battery']['thermal_R'][battery]
        C = parameter['battery']['thermal_C'][battery]
        if ts == model.ts[1]:
            return model.battery_temperature[ts, battery] == parameter['battery']['temperature_initial'][battery]
        else:
            Q_ext = model.battery_charge_power[ts, battery] * (1-parameter['battery']['efficiency_charging'][battery]) \
                    + model.battery_discharge_power[ts, battery] * (1-parameter['battery']['efficiency_discharging'][battery])
            Q_ext = Q_ext * 1000 # Convert to W
            T_prev = model.battery_temperature[ts-timestep, battery]
            T_out = model.outside_temperature[ts]
            return model.battery_temperature[ts, battery] == (R*Q_ext + R*C*T_prev/timestep + T_out) / \
                                                             (1 + R*C/timestep)
    model.constraint_battery_temperature = Constraint(model.ts, model.batteries, rule=battery_temperature, \
                                                      doc='calculation of battery temperature')
    def battery_calendaraging(model, ts, battery):
        days = 365
        T = model.battery_temperature[ts, battery]
        return model.battery_calendaraging[ts, battery] == (degradation_parameter['calendar']['a0'] \
                                                            + degradation_parameter['calendar']['b0'] * T \
                                                            + degradation_parameter['calendar']['b1'] * days) \
                                                           / (timestep_scale * 24 * 365) # scale year to 1 ts    
    model.constraint_battery_calendaraging = Constraint(model.ts, model.batteries, rule=battery_calendaraging, \
                                                        doc='calculation of battery calendar aging')
    def battery_cycleaging(model, ts, battery):
        T = model.battery_temperature[ts, battery]
        Vnominal = parameter['battery']['nominal_V'][battery]
        P_kW = model.battery_charge_power[ts, battery] + model.battery_discharge_power[ts, battery]
        C_rate = P_kW / parameter['battery']['capacity'][battery]
        E_Ah = (P_kW * 1) / timestep_scale * 1000 / Vnominal # P -> kWh to Ah
        ''' ATTENTION *0 ATTENTION '''
        return model.battery_cycleaging[ts, battery] == degradation_parameter['cycle']['a0'] * 0\
                                                        + degradation_parameter['cycle']['b0'] * T \
                                                        + degradation_parameter['cycle']['b1'] * C_rate \
                                                        + degradation_parameter['cycle']['b2'] * E_Ah  
    model.constraint_battery_cycleaging = Constraint(model.ts, model.batteries, rule=battery_cycleaging, \
                                                     doc='calculation of battery cycle aging')
    
    print('Cycleaging * 0')
    def battery_degradation(model, ts, battery):
        return model.battery_degradation[ts, battery] == model.battery_calendaraging[ts, battery] \
                                                         + model.battery_cycleaging[ts, battery] * 0
    model.constraint_battery_degradation = Constraint(model.ts, model.batteries, rule=battery_degradation, \
                                                      doc='calculation of total battery degradation')    
    
    def sum_battery_degradation(model, ts):
        return model.sum_battery_degradation[ts] == sum(model.battery_degradation[ts, battery] \
                                                        for battery in model.batteries)
    model.constraint_sum_battery_degradation = Constraint(model.ts, rule=sum_battery_degradation, \
                                                          doc='sum of battery degradation')
    
    def sum_battery_degradation_battery(model, battery):
        return model.sum_battery_degradation_battery[battery] == sum(model.battery_degradation[t, battery] \
                                                                     for t in accounting_ts)
    model.constraint_sum_battery_degradation_battery = Constraint(model.batteries, rule=sum_battery_degradation_battery, \
                                                                  doc='battery degradation per battery calculation')
    
    
    def sum_degradation_cost(model):
        cost = 0
        for battery in model.batteries:
            cost += model.sum_battery_degradation_battery[battery] / 100 \
                    * parameter['battery']['degradation_replacementcost'][battery]
        return model.sum_degradation_cost >= cost
    model.constraint_sum_degradation_cost = Constraint(rule=sum_degradation_cost, doc='battery degradation calculation')
    
    return model

# Converter
def convert_batterydegradation_model(model, parameter):
    columns = ['Battery Power [kW]','Import Power [kW]','Export Power [kW]','Battery Energy [kWh]','Load Power [kW]', \
               'Tariff Energy Period [-]','Tariff Power Period [-]','PV Power [kW]','Battery Self Discharge [kW]', \
               'Temperature [C]','Battery Avilable [-]','Battery External [kW]','Reg Up [kW]','Reg Dn [kW]', \
               'Tariff Reg Up [$/kWh]','Tariff Reg Dn [$/kWh]','Reg Revenue [$]','Energy Cost [$]', \
               'Energy Export Revenue [kW]']
    df = {}
    for t in model.ts:
        df[t] = [model.sum_battery_charge_power[t].value-model.sum_battery_discharge_power[t].value, \
                 model.grid_import[t].value, model.grid_export[t].value, \
                 model.sum_battery_energy[t].value, model.demand[t], model.tariff_energy_map[t], \
                 model.tariff_power_map[t], -1*model.generation_pv[t], model.sum_battery_selfdischarge_power[t].value, \
                 model.outside_temperature[t]]
        # Available
        df[t] += [sum([model.battery_available[t,b] for b in model.batteries])/len(model.batteries)]
        # External Demand
        df[t] += [sum([model.battery_demand_ext[t,b] for b in model.batteries])]
        # Regulation
        df[t] += [model.sum_regulation_up[t], model.sum_regulation_dn[t]]
        # Tariff
        df[t] += [model.tariff_regulation_up[t], model.tariff_regulation_dn[t], model.regulation_revenue[t].value, \
                  model.energy_cost[t].value, model.energy_export_revenue[t].value]
        for b in model.batteries:
            df[t] += [model.battery_charge_power[t,b].value-model.battery_discharge_power[t,b].value, \
                      model.battery_energy[t,b].value, model.battery_available[t,b], model.battery_demand_ext[t,b], \
                      model.battery_temperature[t,b].value,model.battery_degradation[t,b].value, \
                      model.battery_calendaraging[t,b].value,model.battery_cycleaging[t,b].value]
    for b in model.batteries:        
        columns += ['Battery {!s} Power [kW]'.format(b), 'Battery {!s} Energy [kWh]'.format(b), \
                    'Battery {!s} Available [-]'.format(b), 'Battery {!s} External [kW]'.format(b), \
                    'Battery {!s} Temperature [C]'.format(b), 'Battery {!s} Degradation [%]'.format(b), \
                    'Battery {!s} Calendar Aging [%]'.format(b), 'Battery {!s} Cycle Aging [%]'.format(b)]


    df = pd.DataFrame(df).transpose()
    df.columns = columns
    df.index = pd.to_datetime(df.index, unit='s')
    df['Battery SOC [-]'] = df['Battery Energy [kWh]'] / float(sum(parameter['battery']['capacity']))
    for b in model.batteries:
        df['Battery {!s} SOC [-]'.format(b)] = df['Battery {!s} Energy [kWh]'.format(b)] \
                                               / float(parameter['battery']['capacity'][b])

    df['Tariff Energy [$/kWh]'] = df[['Tariff Energy Period [-]']].replace(pyomo_read_parameter(model.tariff_energy))
    return df