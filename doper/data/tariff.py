
def get_e19_2018_tariff():
    # PG&E E-19 tariff (March 1, 2018)
    tariff = {}
    tariff['name'] = 'PG&E E-19 tariff (March 1, 2018)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:1,6:1,7:1,8:1,9:1,10:1,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}
    tariff['summer'] = {}
    tariff['summer']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                12:2,13:2,14:2,15:2,16:2,17:2,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['summer']['energy'] = {0:0.08671, 1:0.11613, 2:0.16055} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:5.40, 2:19.65} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 17.74 # $/kW for coincident
    tariff['winter'] = {}
    tariff['winter']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['winter']['energy'] = {0:0.09401, 1:0.11004, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand'] = {0:0, 1:0.12, 2:0} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand_coincident'] = 17.74 # $/kW for coincident
    return tariff

def get_e19_new_2018_tariff():
    # PG&E E-19 tariff (November 2018)
    tariff = {}
    tariff['name'] = 'PG&E E-19 tariff (November 2018; from Doug)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:2,4:2,5:1,6:1,7:1,8:1,9:1,10:1,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer',2:'winter_2'}
    tariff['summer'] = {}
    tariff['summer']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                12:0,13:0,14:0,15:1,16:1,17:2,18:2,19:2,20:2,21:2,22:1,23:1}
    tariff['summer']['energy'] = {0:0.11158, 1:0.14449, 2:0.21517} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:1e-4, 2:0.48} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 19.43 # $/kW for coincident
    tariff['winter'] = {}
    tariff['winter']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                12:0,13:0,14:0,15:0,16:0,17:2,18:2,19:2,20:2,21:2,22:0,23:0}
    tariff['winter']['energy'] = {0:0.11029, 1:0, 2:0.12935} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand'] = {0:0, 1:1e-4, 2:1e-5} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand_coincident'] = 19.43 # $/kW for coincident
    tariff['winter_2'] = {}
    tariff['winter_2']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['winter_2']['energy'] = {0:0.09384, 1:1e-4, 2:1e-5} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter_2']['demand'] = {0:0, 1:1e-4, 2:1e-5} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter_2']['demand_coincident'] = 19.43 # $/kW for coincident
    return tariff

def get_e19_2019_tariff():
    # PG&E E-19 tariff (April 24, 2019)
    tariff = {}
    tariff['name'] = 'PG&E E-19 tariff (April 24, 2019)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:1,6:1,7:1,8:1,9:1,10:1,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}
    tariff['summer'] = {}
    tariff['summer']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                12:2,13:2,14:2,15:2,16:2,17:2,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['summer']['energy'] = {0:0.08512, 1:0.11194, 2:0.15245} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:5.18, 2:18.64} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 17.57 # $/kW for coincident
    tariff['winter'] = {}
    tariff['winter']['hours'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['winter']['energy'] = {0:0.09178, 1:0.10640, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand'] = {0:0, 1:0.12, 2:0} # $/kW for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['winter']['demand_coincident'] = 17.57 # $/kW for coincident
    return tariff

def get_e19_2020_tariff():
    # PG&E E-19 tariff (May 1, 2020)
    tariff = {}
    tariff['name'] = 'PG&E E-19 tariff (May 1, 2020)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:1,6:1,7:1,8:1,9:1,10:1,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                            12:2,13:2,14:2,15:2,16:2,17:2,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['summer']['energy'] = {0:0.09496, 1:0.12656, 2:0.17427} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:6.10, 2:21.94} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 21.10 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                            12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                             
    tariff['winter']['energy']= {0:0.10280, 1:0.12002, 2:0} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0, 1:0.14, 2:0} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 21.10 # $/kW for coincident
    return tariff

def get_e19_2022_tariff():
    # PG&E E-19 tariff Secondary Voltage (June 1, 2022)
    tariff = {}
    tariff['name'] = 'PG&E E-19 tariff Secondary Voltage (June 1, 2022)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:1,6:1,7:1,8:1,9:1,10:1,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                            12:2,13:2,14:2,15:2,16:2,17:2,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['summer']['energy'] = {0:0.13432, 1:0.14030, 2:0.14030} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:14.27, 2:17.15} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 29.47 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:1,9:1,10:1,11:1, \
                                            12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:1,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                             
    tariff['winter']['energy']= {0:0.13102, 1:0.13173} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0, 1:0} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 29.47 # $/kW for coincident
    return tariff
    
def get_tou8_2019_tariff():
    # SCE TOU-8 tariff Option D 2-50 kV (July 26 2019)
    tariff = {}
    tariff['name'] = 'SCE TOU-8 tariff Option D 2-50 kV (July 26 2019)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:1,7:1,8:1,9:1,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:1,17:1,18:1,19:1,20:1,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.02289+0.04433-0.00007, 1:0.02289+0.06945-0.00007, 2:0.02289+0.07721-0.00007} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:0, 2:8.02+22.32} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 11.37 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}
    tariff['winter']['hours']['weekend'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}    
    tariff['winter']['energy']= {0:0.02289+0.03137-0.00007, 1:0.02289+0.04890-0.00007, 2:0.02289+0.05825-0.00007} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0, 1:0, 2:2.63+4.72} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 11.37 # $/kW for coincident
    return tariff
    
def get_tou8_2020_tariff():
    # SCE TOU-8 tariff Option D 2-50 kV (March 13 2020)
    tariff = {}
    tariff['name'] = 'SCE TOU-8 tariff Option D 2-50 kV (March 13 2020)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:1,7:1,8:1,9:1,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:1,17:1,18:1,19:1,20:1,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.02840+0.04467-0.00007, 1:0.02840+0.06997-0.00007, 2:0.02840+0.07779-0.00007} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:0, 2:9.60+22.49} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 12.36 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}
    tariff['winter']['hours']['weekend'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}    
    tariff['winter']['energy']= {0:0.02840+0.03160-0.00007, 1:0.02840+0.04926-0.00007, 2:0.02840+0.05868-0.00007} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0, 1:0, 2:3.14+4.75} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 12.36 # $/kW for coincident
    return tariff
    
def get_tou8_2022_tariff():
    # SCE TOU-8 tariff Option D 2-50 kV (June 1 2022)
    tariff = {}
    tariff['name'] = 'SCE TOU-8 tariff Option D 2-50 kV (June 1 2022)'
    tariff['tz'] = "America/Los_Angeles"
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:1,7:1,8:1,9:1,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:1,17:1,18:1,19:1,20:1,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.03791+0.05197, 1:0.03791+0.08143, 2:0.03791+0.09055} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:0, 1:0, 2:14.88+26.20} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 19.07 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}
    tariff['winter']['hours']['weekend'] = {0:1,1:1,2:1,3:1,4:1,5:1,6:1,7:1,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:2,17:2,18:2,19:2,20:2,21:1,22:1,23:1}    
    tariff['winter']['energy']= {0:0.03791+0.03673, 1:0.03791+0.05731, 2:0.03791+0.06829} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0, 1:0, 2:4.85+5.54} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 19.07 # $/kW for coincident
    return tariff
    
def get_nspc_gtds_2019_tariff():
    # Northern State Power Company - General Time of Day Service (6 January 2019)
    tariff = {}
    tariff['name'] = 'Northern State Power Company - General Time of Day Service (6 January 2019)'
    tariff['tz'] = "America/Los_Angeles" # Warning!!
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:1,7:1,8:1,9:1,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:1,10:1,11:1, \
                                            12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.02341, 1:0.04855, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:2.35, 1:14.79, 2:0} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 0 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:1,10:1,11:1, \
                                            12:1,13:1,14:1,15:1,16:1,17:1,18:1,19:1,20:1,21:0,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                                             
    tariff['winter']['energy']= {0:0.02341, 1:0.04855, 2:0} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:2.35, 1:10.49, 2:0} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 0 # $/kW for coincident
    return tariff
    
def get_nspc_gs_2019_tariff():
    # Northern State Power Company - General Service (6 January 2019)
    tariff = {}
    tariff['name'] = 'Northern State Power Company - General Service (6 January 2019)'
    tariff['tz'] = "America/Los_Angeles" # Warning!!
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:1,7:1,8:1,9:1,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}

    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.03407, 1:0, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:14.79, 1:0, 2:0} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 0 # $/kW for coincident

    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                                             
    tariff['winter']['energy']= {0:0.03407, 1:0, 2:0} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:10.49, 1:0, 2:0} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 0 # $/kW for coincident
    return tariff

def get_bge_gs_2019_tariff():
    # Baltimore Gas and Electric Company - General Service (17 December 2019)
    tariff = {}
    tariff['name'] = 'Baltimore Gas and Electric Company - General Service (17 December 2019)'
    tariff['tz'] = "America/Los_Angeles" # Warning!!
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}
    '''
    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.03407, 1:0, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:14.79, 1:0, 2:0} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 0 # $/kW for coincident
    '''
    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                                             
    tariff['winter']['energy']= {0:0.01686+0.0689} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:3.81} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 0 # $/kW for coincident
    return tariff
    
def get_bge_gs_2022_tariff():
    # Baltimore Gas and Electric Company - General Service (1 January 2022)
    tariff = {}
    tariff['name'] = 'Baltimore Gas and Electric Company - General Service (1 January 2022)'
    tariff['tz'] = "America/Los_Angeles" # Warning!!
    tariff['seasons'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0,12:0}
    tariff['seasons_map'] = {0:'winter',1:'summer'}
    '''
    tariff['summer'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['summer']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['summer']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}    
    tariff['summer']['energy'] = {0:0.03407, 1:0, 2:0} # $/kWh for periods 0-offpeak, 1-midpeak, 2-onpeak
    tariff['summer']['demand'] = {0:14.79, 1:0, 2:0} # $/kW for periods 0-offpeak, 2-onpeak
    tariff['summer']['demand_coincident'] = 0 # $/kW for coincident
    '''
    tariff['winter'] = {'hours': {}, 'energy': {}, 'demand': {}, 'demand_coincident': {}}
    tariff['winter']['hours']['weekday'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}
    tariff['winter']['hours']['weekend'] = {0:0,1:0,2:0,3:0,4:0,5:0,6:0,7:0,8:0,9:0,10:0,11:0, \
                                            12:0,13:0,14:0,15:0,16:0,17:0,18:0,19:0,20:0,21:0,22:0,23:0}                                             
    tariff['winter']['energy']= {0:0.03808} # $/kWh for periods 0-superoffpeak, 1-offpeak, 2-midpea
    tariff['winter']['demand'] = {0:0} # $/kW for periods 0-superoffpeak, 2-midpeak
    tariff['winter']['demand_coincident'] = 0 # $/kW for coincident
    return tariff

def get_tariff(tariff='e19-2018'):
    if tariff == 'e19-2018':
        return get_e19_2018_tariff()
    elif tariff == 'e19-2018-new':
        return get_e19_new_2018_tariff()
    elif tariff == 'e19-2019':
        return get_e19_2019_tariff()
    elif tariff == 'e19-2020':
        return get_e19_2020_tariff()
    elif tariff == 'e19-2022':
	    return get_e19_2022_tariff()
    elif tariff == 'tou8-2019':
        return get_tou8_2019_tariff()
    elif tariff == 'tou8-2020':
        return get_tou8_2020_tariff()
    elif tariff == 'tou8-2022':
        return get_tou8_2022_tariff()
    elif tariff == 'nspc-gtds-2019':
        return get_nspc_gtds_2019_tariff()
    elif tariff == 'nspc-gs-2019':
        return get_nspc_gs_2019_tariff()
    elif tariff == 'bge-gs-2019':
        return get_bge_gs_2019_tariff()
    elif tariff == 'bge-gs-2022':
        return get_bge_gs_2022_tariff()
    else:
	    raise ValueError('Tariff "{}" not found.'.format(tariff))
        
if __name__ == '__main__':
    print(get_tariff('tou8-2020'))
