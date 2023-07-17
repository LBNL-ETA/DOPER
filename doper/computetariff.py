# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Compute tariff module.
"""

# pylint: disable=invalid-name, too-many-arguments, redefined-outer-name

def compute_periods(df, tariff, parameter, return_tariff=True, weekday_map=False, warnings=True):
    """compute tariff periods"""

    daytypes = True
    if not 'weekday' in tariff[tariff['seasons_map'][tariff['seasons'][0]]]['hours']:
        if warnings:
            print('WARNING: No daytype in tariff. Using weekday-only legancy implementaiton.')
        daytypes = False
    daytype_map = {0: 'weekday', 1: 'weekday', 2: 'weekday', 3: 'weekday', 4: 'weekday',
                   5: 'weekend', 6: 'weekend'} # Monday=0, Sunday=6
    if weekday_map:
        if warnings:
            print('WARNING: Using external daytype mapping.')
        daytypes = False

    tz_df = parameter['site']['input_timezone']
    tz_local = parameter['site']['local_timezone']
    # Shift to local time
    df.index = df.index.tz_localize(f'Etc/GMT{-1*tz_df:+d}') \
        .tz_convert(tz_local)
    season = tariff['seasons_map'][tariff['seasons'][df.index[0].month]]
    # Generate tariff map for selected season
    tariff_map = {}
    tariff_map['energy'] = tariff[season]['energy']
    tariff_map['demand'] = tariff[season]['demand']
    tariff_map['demand_coincident'] = tariff[season]['demand_coincident']
    parameter['tariff'].update(tariff_map)
    # Build table
    df['hour'] = df.index.hour
    if daytypes:
        df['tariff_energy_map'] = \
            df.index.map(lambda x: tariff[season]['hours'][daytype_map[x.weekday()]][x.hour])
    elif weekday_map:
        df['tariff_energy_map'] = \
            df[['weekday','hour']].apply(lambda x: \
                tariff[season]['hours'][daytype_map[x[0]]][x[1]], axis=1)
    else:
        df['tariff_energy_map'] = \
            [tariff[season]['hours'][h] for h in df.index.hour]
    df['tariff_power_map'] = df['tariff_energy_map']
    df['tariff_energy_export_map'] = 0
    df['tariff_regup'] = 0
    df['tariff_regdn'] = 0
    df.index = df.index.tz_convert(f'Etc/GMT{-1*tz_df:+d}') \
        .tz_localize(None)
    if return_tariff:
        return df, parameter
    return df
