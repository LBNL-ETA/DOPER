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

def _build_period_table(hours_map, daytypes):
    """Build a numpy lookup table mapping (daytype, hour) -> tariff period."""
    if daytypes:
        return np.array([
            [hours_map['weekday'][h] for h in range(24)],
            [hours_map['weekend'][h] for h in range(24)],
        ], dtype=np.int8)
    return None

def calculate_energy_cost(data, tariff, types=None, col_suffix='_Net Load [kW]', ts=15,
                          fullmonth=False, tz='Etc/GMT+8', tz_local='America/Los_Angeles',
                          daily=False, weekday_map=False, del_leap=False, ghg_emissions_cols=[],
                          rtp_col=None):
    """Calculate energy and demand costs from load profiles against a tariff.

    Parameters
    ----------
    data : pd.DataFrame
        DatetimeIndex DataFrame with columns ``{type}{col_suffix}``.
    tariff : dict
        Tariff dict with seasons, energy, demand, and optional export rates.
    types : list of str, optional
        Load type prefixes; auto-detected from column names if None.
    col_suffix : str
        Suffix identifying net load columns (default ``'_Net Load [kW]'``).
    ts : float
        Resampling timestep in minutes.
    fullmonth : bool
        Scale partial months to a full-month equivalent.
    tz : str
        Standard (non-DST) timezone of the input index.
    tz_local : str
        Local timezone (with DST) for tariff period mapping.
    daily : bool
        If True return ``(cost, cost_daily)``; else return ``cost`` only.
    weekday_map : bool
        Use an external weekday column instead of timestamp-derived daytype.
    del_leap : bool
        Zero out Feb 29 rows in leap years before processing.
    ghg_emissions_cols : list of str
        GHG intensity columns [kg CO2/kWh] for emissions totals.
    rtp_col : str, optional
        Column name for real-time price [$/kWh]; zero-filled when None.
    """
    # Auto-detect types from column names
    if types is None:
        types = sorted({c[:-len(col_suffix)] for c in data.columns if c.endswith(col_suffix)})
        if not types:
            raise ValueError(f'No columns with suffix "{col_suffix}" found in data.')

    # Weekday map
    daytypes = True
    if 'weekday' not in tariff[tariff['seasons_map'][tariff['seasons'][0]]]['hours']:
        print('WARNING: No daytype in tariff. Using weekday-only legancy implementaiton.')
        daytypes = False
    if weekday_map:
        print('WARNING: Using external daytype mapping.')
        daytypes = False
    daytype_map = {0: 'weekday', 1: 'weekday', 2: 'weekday', 3: 'weekday', 4: 'weekday',
                   5: 'weekend', 6: 'weekend'} # Mon=0, Sun=6

    steps_per_hour = 60 / float(ts)
    full_day = steps_per_hour * 24
    resample_rule = str(ts) + 'min'

    # Resample
    data = data.resample(resample_rule).mean()
    idx = data.index.strftime('%Y-%m')
    cost = pd.DataFrame(index=idx.unique())
    cost_daily_list = []

    # Cost for each timestep
    for ix in cost.index:
        m = int(ix.split('-')[1])
        dfx = data.iloc[idx.get_loc(ix)].copy(deep=True) #.dropna()
        season = tariff['seasons_map'][tariff['seasons'][m]]
        cost.loc[ix, 'Season'] = season

        df2 = dfx.resample('D').sum()
        df2.index.freq = None
        df2['Season'] = season

        if not dfx.empty:
            if del_leap and dfx.index[0].is_leap_year and '{}-02-29'.format(dfx.index[0].year) in dfx.index:
                dfx.loc['{}-02-29'.format(dfx.index[0].year)] = np.nan

            day_counts = dfx.resample('D').count()

            for t in types:
                load_col = t + col_suffix
                energy_cost_col = t + ' Energy Cost [$]'

                # Filter full days only
                if day_counts[load_col].sum() > full_day:
                    full_days_idx = day_counts.index[day_counts[load_col] == full_day]
                    df = dfx[dfx.index.normalize().isin(full_days_idx)].copy()
                    cost.loc[ix, t + ' Measured Days'] = len(df[load_col]) / full_day
                    cost.loc[ix, t + ' Filled Days'] = 0

                    ix_st = df.index.tz_localize(tz).tz_convert(tz_local)
                    df['hour'] = ix_st.hour

                    # Tariff period lookup
                    if daytypes:
                        hours_map = tariff[season]['hours']
                        period_table = _build_period_table(hours_map, daytypes=True)
                        is_weekend = (ix_st.weekday >= 5).astype(np.int8) # 0=weekday, 1=weekend
                        df['Tariff Power Period [-]'] = period_table[is_weekend, ix_st.hour.values]
                    elif weekday_map:
                        df['Tariff Power Period [-]'] = df[['weekday', 'hour']].apply(
                            lambda x: tariff[season]['hours'][daytype_map[x[0]]][x[1]], axis=1
                        )
                    else:
                        df['Tariff Power Period [-]'] = ix_st.hour.map(tariff[season]['hours'])
                    df['Tariff Energy [$/kWh]'] = df['Tariff Power Period [-]'].replace(
                        tariff[season]['energy']
                    )

                    # Energy cost
                    df[energy_cost_col] = df[load_col] * df['Tariff Energy [$/kWh]'] / steps_per_hour

                    # RTP cost
                    rtp_cost_col = t + ' RTP Cost [$]'
                    if rtp_col is not None and rtp_col in df.columns:
                        df[rtp_cost_col] = df[load_col] * df[rtp_col] / steps_per_hour
                    else:
                        df[rtp_cost_col] = 0.0
                    cost.loc[ix, rtp_cost_col] = df[rtp_cost_col].groupby(df.index.month).sum().loc[m]

                    # Export revenue
                    export_col = t + ' Export [kWh]'
                    export_rev_col = t + ' Export Revenue [$]'
                    if 'export' in tariff[season]:
                        export_power = df[load_col].clip(upper=0).abs()
                        export_rate = df['Tariff Power Period [-]'].map(tariff[season]['export'])
                        df[export_col] = export_power / steps_per_hour
                        df[export_rev_col] = export_power * export_rate / steps_per_hour
                    else:
                        df[export_col] = 0.0
                        df[export_rev_col] = 0.0
                    cost.loc[ix, export_col] = df[export_col].groupby(df.index.month).sum().loc[m]
                    cost.loc[ix, export_rev_col] = df[export_rev_col].groupby(df.index.month).sum().loc[m]

                    # Monthly load aggregations
                    monthly_agg = df[load_col].groupby(df.index.month).agg(['sum', 'max'])
                    cost.loc[ix, t + ' Energy [kWh]'] = monthly_agg.loc[m, 'sum'] / steps_per_hour
                    cost.loc[ix, t + ' Energy Cost [$]'] = df[energy_cost_col].groupby(df.index.month).sum().loc[m]
                    cost.loc[ix, t + ' Demand Coincident [kW]'] = monthly_agg.loc[m, 'max']

                    if fullmonth:
                        days_month = len(pd.date_range(
                            df.index[0].date(),
                            df.index[0].date() + pd.DateOffset(months=1),
                            freq='D'
                        )) - 1
                        cost.loc[ix, t + ' Filled Days'] = days_month - cost.loc[ix, t + ' Measured Days']
                        cost.loc[ix, t + ' Energy Cost [$]'] += cost.loc[ix, t + ' Filled Days'] * \
                            df[[energy_cost_col]].resample('D').sum().mean().values[0]

                    conc_rate = tariff[season]['demand_coincident']
                    cost.loc[ix, t + ' Demand Coincident Cost [$]'] = (
                        cost.loc[ix, t + ' Demand Coincident [kW]'] * conc_rate
                    )

                    # Period demand monthly
                    period_monthly = df[load_col].groupby(
                        [df.index.month, df['Tariff Power Period [-]']]
                    ).agg(['max', 'mean'])
                    periods = period_monthly['max'].unstack()
                    periods_mean = period_monthly['mean'].unstack()

                    # Period demand daily
                    period_daily_grp = df[load_col].groupby(
                        [df.index.normalize(), df['Tariff Power Period [-]']]
                    ).agg(['max', 'mean'])
                    periods2 = period_daily_grp['max'].unstack()
                    periods2_mean = period_daily_grp['mean'].unstack()

                    demand_rates = tariff[season]['demand']

                    # Monthly period placeholders
                    for c in range(3):
                        cost.loc[ix, t + ' Demand Period ' + str(c) + ' Cost [$]'] = np.nan
                    for c in periods.columns:
                        ci = int(c)
                        pfx = t + ' Demand Period ' + str(ci)
                        cost.loc[ix, pfx + ' [kW]'] = periods.loc[m, c]
                        cost.loc[ix, pfx + ' Mean [kW]'] = periods_mean.loc[m, c]
                        cost.loc[ix, pfx + ' Cost [$]'] = periods.loc[m, c] * demand_rates[ci]

                    # GHG emissions monthly
                    for em in ghg_emissions_cols:
                        em_col = t + f' {em} Emissions [kgCO2]'
                        df[em_col] = df[load_col] * df[em] / steps_per_hour
                        cost.loc[ix, em_col] = df[em_col].groupby(df.index.month).sum().loc[m]

                    # Period energy + cost
                    period_sums = df[[load_col, energy_cost_col]].groupby(
                        df['Tariff Power Period [-]']
                    ).sum()
                    for c in period_sums.index:
                        ci = int(c)
                        cost.loc[ix, t + ' Energy Period ' + str(ci) + ' [kWh]'] = (
                            period_sums.loc[c, load_col] / steps_per_hour
                        )
                        cost.loc[ix, t + ' Energy Cost Period ' + str(ci) + ' [$]'] = (
                            period_sums.loc[c, energy_cost_col]
                        )

                    daily_max = df[load_col].resample('D').max()
                    daily_mean = df[load_col].resample('D').mean()
                    energy_cost_daily = df[energy_cost_col].resample('D').sum()
                    export_rev_daily = df[export_rev_col].resample('D').sum()
                    rtp_cost_daily = df[rtp_cost_col].resample('D').sum()

                    energy_cost_cum = energy_cost_daily.groupby(energy_cost_daily.index.month).cumsum()
                    coinc_cum = daily_max.groupby(daily_max.index.month).cummax()
                    coinc_cost_cum = (daily_max * conc_rate).groupby(daily_max.index.month).cummax()
                    export_rev_cum = export_rev_daily.groupby(export_rev_daily.index.month).cumsum()
                    rtp_cost_cum = rtp_cost_daily.groupby(rtp_cost_daily.index.month).cumsum()

                    new_cols = {
                        energy_cost_col: energy_cost_daily,
                        t + ' Energy Cost Cum [$]': energy_cost_cum,
                        rtp_cost_col: rtp_cost_daily,
                        t + ' RTP Cost Cum [$]': rtp_cost_cum,
                        export_col: df[export_col].resample('D').sum(),
                        export_rev_col: export_rev_daily,
                        t + ' Export Revenue Cum [$]': export_rev_cum,
                        t + ' Demand Coincident [kW]': daily_max,
                        t + ' Demand Coincident Mean [kW]': daily_mean,
                        t + ' Demand Coincident Cum [kW]': coinc_cum,
                        t + ' Demand Coincident Cost [$]': daily_max * conc_rate,
                        t + ' Demand Coincident Cost Mean [$]': daily_mean * conc_rate,
                        t + ' Demand Coincident Cost Cum [$]': coinc_cost_cum,
                        t + ' Demand Coincident Utilization [%]': (daily_mean / daily_max) * 1e2,
                    }

                    # Period demand daily columns
                    for c in range(3):
                        new_cols[t + ' Demand Period ' + str(c) + ' Cost Cum [$]'] = np.nan

                    for c in periods2.columns:
                        ci = int(c)
                        pfx = t + ' Demand Period ' + str(ci)
                        p2 = periods2[c]
                        p2m = periods2_mean[c]
                        new_cols[pfx + ' [kW]'] = p2
                        new_cols[pfx + ' Mean [kW]'] = p2m
                        new_cols[pfx + ' Cost [$]'] = p2 * demand_rates[ci]
                        new_cols[pfx + ' Mean Cost [$]'] = p2m * demand_rates[ci]
                        new_cols[pfx + ' Cum [kW]'] = p2.groupby(p2.index.month).cummax().ffill()
                        new_cols[pfx + ' Mean Cum [kW]'] = p2m.groupby(p2m.index.month).cummax().ffill()
                        new_cols[pfx + ' Cost Cum [$]'] = (
                            (p2 * demand_rates[ci]).groupby(p2.index.month).cummax().ffill()
                        )
                        new_cols[pfx + ' Mean Cost Cum [$]'] = (
                            (p2m * demand_rates[ci]).groupby(p2m.index.month).cummax().ffill()
                        )
                        new_cols[pfx + ' Utilization [%]'] = (p2m / p2) * 1e2

                    # GHG daily
                    for em in ghg_emissions_cols:
                        em_col = t + f' {em} Emissions [kgCO2]'
                        new_cols[em_col] = df[em_col].resample('D').sum()

                    df2 = pd.concat([df2, pd.DataFrame(new_cols, index=df2.index)], axis=1)

        cost_daily_list.append(df2.copy())

    cost_daily = pd.concat(cost_daily_list, sort=True) if cost_daily_list else pd.DataFrame()

    # total cost
    for t in types:
        # Ensure all required columns exist even if no full days were processed
        for c in range(3):
            col = t + ' Demand Period ' + str(c) + ' Cost [$]'
            if col not in cost.columns:
                cost[col] = np.nan
        for col in [t + ' Demand Coincident Cost [$]', t + ' Energy Cost [$]',
                    t + ' RTP Cost [$]', t + ' Export Revenue [$]']:
            if col not in cost.columns:
                cost[col] = 0.0

        cost[t + ' Total Demand Cost [$]'] = (
            cost[[t + ' Demand Period ' + str(c) + ' Cost [$]' for c in range(3)]].sum(axis=1)
            + cost[t + ' Demand Coincident Cost [$]']
        )
        cost[t + ' Total Energy Cost [$]'] = cost[t + ' Energy Cost [$]'] + cost[t + ' Total Demand Cost [$]']
        cost[t + ' Net Energy Cost [$]'] = (
            cost[t + ' Total Energy Cost [$]']
            + cost[t + ' RTP Cost [$]']
            - cost[t + ' Export Revenue [$]']
        )
        cost_daily[t + ' Total Demand Cost Cum [$]'] = (
            cost_daily[[t + ' Demand Period ' + str(c) + ' Cost Cum [$]' for c in range(3)]].sum(axis=1)
            + cost_daily[t + ' Demand Coincident Cost Cum [$]']
        )
        cost_daily[t + ' Total Energy Cost Cum [$]'] = (
            cost_daily[t + ' Energy Cost Cum [$]'] + cost_daily[t + ' Total Demand Cost Cum [$]']
        )
        cost_daily[t + ' Net Energy Cost Cum [$]'] = (
            cost_daily[t + ' Total Energy Cost Cum [$]']
            + cost_daily[t + ' RTP Cost Cum [$]']
            - cost_daily[t + ' Export Revenue Cum [$]']
        )

    if daily:
        return cost, cost_daily
    else:
        return cost

def cost_comparison(cost, days=1, month=6, days_month=30, base=None):
    """Compare energy costs and demand savings across load profile types."""
    df = pd.DataFrame()
    scale = 1 / float(days) * days_month # scale measured days to full month
    cases = np.unique([x.split(' ')[0] for x in cost.columns]).tolist()
    cases.remove('Season')
    for c in cases:
        df.loc[c, 'Demand Cost [$]'] = cost[c + ' Total Demand Cost [$]'].loc[month]
        df.loc[c, 'Energy Cost [$]'] = cost[c + ' Energy Cost [$]'].loc[month] * scale
        df.loc[c, 'RTP Cost [$]'] = cost[c + ' RTP Cost [$]'].loc[month] * scale
        df.loc[c, 'Export Revenue [$]'] = cost[c + ' Export Revenue [$]'].loc[month] * scale
        if c + ' Demand Period2 [kW]' in cost.columns:
            df.loc[c, 'Critical Peak Demand [W]'] = cost[c + ' Demand Period 2 [kW]'].loc[month] * 1000.
        else:
            df.loc[c, 'Critical Peak Demand [W]'] = cost[c + ' Demand Period 1 [kW]'].loc[month] * 1000.
    if base:
        df['Total Cost [$]'] = (
            df['Demand Cost [$]'] + df['Energy Cost [$]'] + df['RTP Cost [$]'] - df['Export Revenue [$]']
        )
        df['Demand Savings [$]'] = df.loc[base, 'Demand Cost [$]'] - df['Demand Cost [$]']
        df['Demand Savings [%]'] = df['Demand Savings [$]'] / df.loc[base, 'Demand Cost [$]'] * 100
        df['Energy Savings [$]'] = df.loc[base, 'Energy Cost [$]'] - df['Energy Cost [$]']
        df['Energy Savings [%]'] = df['Energy Savings [$]'] / df.loc[base, 'Energy Cost [$]'] * 100
        df['RTP Savings [$]'] = df.loc[base, 'RTP Cost [$]'] - df['RTP Cost [$]']
        df['RTP Savings [%]'] = df['RTP Savings [$]'] / df.loc[base, 'RTP Cost [$]'] * 100
        df['Export Revenue Increase [$]'] = df['Export Revenue [$]'] - df.loc[base, 'Export Revenue [$]']
        df['Export Revenue Increase [%]'] = df['Export Revenue Increase [$]'] / df.loc[base, 'Export Revenue [$]'] * 100
        df['Demand Reduction [W]'] = df.loc[base, 'Critical Peak Demand [W]'] - df['Critical Peak Demand [W]']
        df['Demand Reduction [%]'] = df['Demand Reduction [W]'] / df.loc[base, 'Critical Peak Demand [W]'] * 100
        df['Total Savings [$]'] = df.loc[base, 'Total Cost [$]'] - df['Total Cost [$]']
        df['Total Savings [%]'] = df['Total Savings [$]'] / df.loc[base, 'Total Cost [$]'] * 100
    return df
