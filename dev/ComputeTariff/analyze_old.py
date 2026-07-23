# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""Distributed Optimal and Predictive Energy Resources
Analysis module.
"""

import pandas as pd
import numpy as np

def vil_to_dgp(x):
    """Calculate glare probability DGPs from vertical illuminance."""
    return x * 0.0000622 + 0.184

def calculate_energy_cost(data, tariff, types=['MPC', 'Base', 'BasePV'], ts=15, fullmonth=False,
                          tz='Etc/GMT+8', tz_local='America/Los_Angeles', daily=False,
                          weekday_map=False, del_leap=False, ghg_emissions_cols=[]):
    """Calculate energy and demand costs from load profiles against a tariff."""
    daytypes = True
    if not 'weekday' in tariff[tariff['seasons_map'][tariff['seasons'][0]]]['hours']:
        print('WARNING: No daytype in tariff. Using weekday-only legancy implementaiton.')
        daytypes = False
    if weekday_map:
        print('WARNING: Using external daytype mapping.')
        daytypes = False  
    daytype_map = {0: 'weekday', 1: 'weekday', 2: 'weekday', 3: 'weekday', 4: 'weekday',
                   5: 'weekend', 6: 'weekend'} # Monday=0, Sunday=6
    
    data = data.resample(str(ts)+'min').mean()
    idx = data.index.strftime('%Y-%m')
    cost = pd.DataFrame(index=idx.unique())
    cost_daily = pd.DataFrame()
    for ix in cost.index:
        m = int(ix.split('-')[1])
        dfx = data.iloc[idx.get_loc(ix)].copy(deep=True)#.dropna()
        season = tariff['seasons_map'][tariff['seasons'][m]]
        cost.loc[ix,'Season'] = season
        df2 = dfx.groupby(dfx.index.date).sum()
        df2.index = pd.to_datetime(df2.index)
        df2['Season'] = season
        if not dfx.empty:
            if del_leap and dfx.index[0].is_leap_year and '{}-02-29'.format(dfx.index[0].year) in dfx.index:
                dfx.loc['{}-02-29'.format(dfx.index[0].year)] = np.nan
            for t in types:
                # Filter full days only
                days = dfx.groupby(dfx.index.date).count()
                if days[t+'_Net Load [kW]'].sum() > 60/ts*24:
                    df = dfx[np.isin(dfx.index.date, days.loc[days[t+'_Net Load [kW]'] == 60/ts*24].index)].copy()
                    cost.loc[ix,t+' Measured Days'] = len(df[t+'_Net Load [kW]'])/(60/ts*24)
                    cost.loc[ix,t+' Filled Days'] = 0
                    ix_st = df.index.tz_localize(tz).tz_convert(tz_local)
                    df['hour'] = ix_st.hour
                    if daytypes:
                        df['Tariff Power Period [-]'] = ix_st.map(lambda x: tariff[season]['hours'][daytype_map[x.weekday()]][x.hour])
                    elif weekday_map:
                        df['Tariff Power Period [-]'] = df[['weekday','hour']].apply(lambda x: tariff[season]['hours'][daytype_map[x[0]]][x[1]], axis=1)
                    else:
                        df['Tariff Power Period [-]'] = ix_st.hour.map(tariff[season]['hours'])
                    df['Tariff Energy [$/kWh]'] = df['Tariff Power Period [-]'].replace(tariff[season]['energy'])
                    
                    # Calculate Energy cost
                    df[t+' Energy Cost [$]'] = df[t+'_Net Load [kW]'] * df['Tariff Energy [$/kWh]']/(60/float(ts))
                    df2[t+' Energy Cost [$]'] = df[t+' Energy Cost [$]'].groupby(df.index.date).sum()
                    df2[t+' Energy Cost Cum [$]'] = df2[t+' Energy Cost [$]'].groupby(df2.index.month).cumsum()
                    cost.loc[ix,t+' Energy [kWh]'] = df[t+'_Net Load [kW]'].groupby(df.index.month).sum().loc[m]/(60/float(ts))
                    cost.loc[ix,t+' Energy Cost [$]'] = df[t+' Energy Cost [$]'].groupby(df.index.month).sum().loc[m]
                    if fullmonth:
                        days_month = len(pd.date_range(df.index[0].date(), \
                            df.index[0].date()+pd.DateOffset(months=1), freq='D')) - 1
                        cost.loc[ix,t+' Filled Days'] = days_month - cost.loc[ix,t+' Measured Days']
                        cost.loc[ix,t+' Energy Cost [$]'] += cost.loc[ix,t+' Filled Days'] * \
                            df[[t+' Energy Cost [$]']].groupby(df.index.date).sum().mean().values[0]
                    
                    # Calculate Demand cost
                    cost.loc[ix,t+' Demand Coincident [kW]'] = df[t+'_Net Load [kW]'].groupby(df.index.month).max().loc[m]
                    df2[t+' Demand Coincident [kW]'] = df[t+'_Net Load [kW]'].groupby(df.index.date).max()
                    df2[t+' Demand Coincident Mean [kW]'] = df[t+'_Net Load [kW]'].groupby(df.index.date).mean()
                    df2[t+' Demand Coincident Cum [kW]'] = df2[t+' Demand Coincident [kW]'].groupby(df2.index.month).cummax()
                    cost.loc[ix,t+' Demand Coincident Cost [$]'] = \
                        cost.loc[ix,t+' Demand Coincident [kW]'] * tariff[season]['demand_coincident']
                    df2[t+' Demand Coincident Cost [$]'] = df2[t+' Demand Coincident [kW]'] * tariff[season]['demand_coincident']
                    df2[t+' Demand Coincident Cost Mean [$]'] = df2[t+' Demand Coincident Mean [kW]'] * tariff[season]['demand_coincident']
                    df2[t+' Demand Coincident Cost Cum [$]'] = \
                        df2[t+' Demand Coincident Cost [$]'].groupby(df2.index.month).cummax()
                    df2[t+' Demand Coincident Utilization [%]'] = \
                        (df2[t+' Demand Coincident Mean [kW]'] / df2[t+' Demand Coincident [kW]'])* 1e2
                    periods = df[t+'_Net Load [kW]'].groupby([df.index.month,df['Tariff Power Period [-]']]).max().unstack()
                    periods2 = df[t+'_Net Load [kW]'].groupby([df.index.date,df['Tariff Power Period [-]']]).max().unstack()
                    periods_mean = df[t+'_Net Load [kW]'].groupby([df.index.month,df['Tariff Power Period [-]']]).mean().unstack()
                    periods2_mean = df[t+'_Net Load [kW]'].groupby([df.index.date,df['Tariff Power Period [-]']]).mean().unstack()
                    for c in range(3):
                        cost.loc[ix,t+' Demand Period '+str(c)+' Cost [$]'] = np.nan
                        df2[t+' Demand Period '+str(c)+' Cost Cum [$]'] = np.nan                   
                    for c in periods.columns:
                        cost.loc[ix,t+' Demand Period '+str(int(c))+' [kW]'] = periods.loc[m,c]
                        cost.loc[ix,t+' Demand Period '+str(int(c))+' Mean [kW]'] = periods_mean.loc[m,c]
                        cost.loc[ix,t+' Demand Period '+str(int(c))+' Cost [$]'] = periods.loc[m,c] * \
                                                                                 tariff[season]['demand'][int(c)]
                    for c in periods2.columns:
                        df2[t+' Demand Period '+str(int(c))+' [kW]'] = periods2[c]
                        df2[t+' Demand Period '+str(int(c))+' Mean [kW]'] = periods2_mean[c]
                        df2[t+' Demand Period '+str(int(c))+' Cost [$]'] = periods2[c] * \
                                                                          tariff[season]['demand'][int(c)]
                        df2[t+' Demand Period '+str(int(c))+' Mean Cost [$]'] = periods2_mean[c] * \
                                                                          tariff[season]['demand'][int(c)]
                        df2[t+' Demand Period '+str(int(c))+' Cum [kW]'] = \
                            df2[t+' Demand Period '+str(int(c))+' [kW]'].groupby(df2.index.month).cummax().ffill()
                        df2[t+' Demand Period '+str(int(c))+' Mean Cum [kW]'] = \
                            df2[t+' Demand Period '+str(int(c))+' Mean [kW]'].groupby(df2.index.month).cummax().ffill()
                        df2[t+' Demand Period '+str(int(c))+' Cost Cum [$]'] = \
                            df2[t+' Demand Period '+str(int(c))+' Cost [$]'].groupby(df2.index.month).cummax().ffill()
                        df2[t+' Demand Period '+str(int(c))+' Mean Cost Cum [$]'] = \
                            df2[t+' Demand Period '+str(int(c))+' Mean Cost [$]'].groupby(df2.index.month).cummax().ffill()
                        df2[t+' Demand Period '+str(int(c))+' Utilization [%]'] = \
                            (df2[t+' Demand Period '+str(int(c))+' Mean [kW]'] \
                            / df2[t+' Demand Period '+str(int(c))+' [kW]']) * 1e2
                        
                    # Calculate GHG emissions
                    for em in ghg_emissions_cols:
                        df[t+f' {em} Emissions [kgCO2]'] = df[t+'_Net Load [kW]'] * df[em]/(60/float(ts))
                        df2[t+f' {em} Emissions [kgCO2]'] = df[t+f' {em} Emissions [kgCO2]'].groupby(df.index.date).sum()
                        cost.loc[ix,t+f' {em} Emissions [kgCO2]'] = df[t+f' {em} Emissions [kgCO2]'].groupby(df.index.month).sum().loc[m]
                 
                    # Period energy
                    periods3 = df[t+'_Net Load [kW]'].groupby(df['Tariff Power Period [-]']).sum()
                    for c in periods3.index:
                        cost.loc[ix,t+' Energy Period '+str(int(c))+' [kWh]'] = periods3.loc[c] /(60/float(ts))
                        
                    # Period energy cost
                    periods3 = df[t+' Energy Cost [$]'].groupby(df['Tariff Power Period [-]']).sum()
                    for c in periods3.index:
                        cost.loc[ix,t+' Energy Cost Period '+str(int(c))+' [$]'] = periods3.loc[c]
                
        if cost_daily.empty:
            cost_daily = df2.copy()
        else:
            cost_daily = pd.concat([cost_daily, df2.copy()], sort=True)
            
    # Calculate Total cost
    for t in types:
        cost[t+' Total Demand Cost [$]'] = cost[[t+' Demand Period '+str(c)+' Cost [$]' for c in range(3)]].sum(axis=1) + \
                                           cost[t+' Demand Coincident Cost [$]']
        cost[t+' Total Energy Cost [$]'] = cost[t+' Energy Cost [$]'] + cost[t+' Total Demand Cost [$]']
        cost_daily[t+' Total Demand Cost Cum [$]'] = cost_daily[[t+' Demand Period '+str(c)+' Cost Cum [$]' for c in range(3)]].sum(axis=1) + \
                                                 cost_daily[t+' Demand Coincident Cost Cum [$]']
        cost_daily[t+' Total Energy Cost Cum [$]'] = cost_daily[t+' Energy Cost Cum [$]'] + cost_daily[t+' Total Demand Cost Cum [$]']
                                                
    if daily:
        return cost, cost_daily
    else:
        return cost

def cost_comparison(cost, days=1, month=6, days_month=30, base=None):
    """Compare energy costs and demand savings across load profile types."""
    df = pd.DataFrame()
    cases = np.unique([x.split(' ')[0] for x in cost.columns]).tolist()
    cases.remove('Season')
    for c in cases:
        df.loc[c, 'Demand Cost [$]'] = cost[c+' Total Demand Cost [$]'].loc[month]
        df.loc[c, 'Energy Cost [$]'] = cost[c+' Energy Cost [$]'].loc[month] * \
                                       (1/float(days) * days_month) # full month
        if c+' Demand Period2 [kW]' in cost.columns:
            df.loc[c, 'Critical Peak Demand [W]'] = cost[c+' Demand Period 2 [kW]'].loc[month] * 1000.
        else:
            df.loc[c, 'Critical Peak Demand [W]'] = cost[c+' Demand Period 1 [kW]'].loc[month] * 1000.    
    if base:
        df['Total Cost [$]'] = df['Demand Cost [$]'] + df ['Energy Cost [$]']
        df['Demand Savings [$]'] = df.loc[base,'Demand Cost [$]'] - df['Demand Cost [$]']
        df['Demand Savings [%]'] = df['Demand Savings [$]'] / df.loc[base,'Demand Cost [$]'] * 100
        df['Energy Savings [$]'] = df.loc[base,'Energy Cost [$]'] - df['Energy Cost [$]']
        df['Energy Savings [%]'] = df['Energy Savings [$]'] / df.loc[base,'Energy Cost [$]'] * 100
        df['Demand Reduction [W]'] = df.loc[base,'Critical Peak Demand [W]'] - df['Critical Peak Demand [W]']
        df['Demand Reduction [%]'] = df['Demand Reduction [W]'] / df.loc[base,'Critical Peak Demand [W]'] * 100
        df['Total Savings [$]'] = df.loc[base,'Total Cost [$]'] - df['Total Cost [$]']
        df['Total Savings [%]'] = df['Total Savings [$]'] / df.loc[base, 'Total Cost [$]'] * 100
    return df
