# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Compute tariff module.
"""

# pylint: disable=invalid-name, too-many-arguments, redefined-outer-name

def convert_tariff_dict(par=None, tariff=None):
    # tariff periods in parameter
    if par is not None:
        check_keys = ['tariff']
        for check_key in check_keys:
            if check_key in par:
                for k, v in par[check_key].items():
                    if isinstance(v, dict):
                        par[check_key][k] = {int(vk): vv for vk, vv in v.items()}
        # previous periods
        tt = par['site']['demand_periods_prev']
        par['site']['demand_periods_prev'] = {int(vk): vv for vk, vv in tt.items()}
    # standalone tariff dict: seasons / hours / energy / demand keys may be
    # strings after a JSON round-trip
    if tariff is not None:
        if 'seasons' in tariff:
            tariff['seasons'] = {int(k): v for k, v in tariff['seasons'].items()}
        if 'seasons_map' in tariff:
            tariff['seasons_map'] = {int(k): v for k, v in tariff['seasons_map'].items()}
        for season_name in tariff.get('seasons_map', {}).values():
            if season_name not in tariff:
                continue
            season = tariff[season_name]
            for key in ('energy', 'demand', 'export'):
                if key in season and isinstance(season[key], dict):
                    season[key] = {int(k): v for k, v in season[key].items()}
            if 'hours' in season and isinstance(season['hours'], dict):
                hours = season['hours']
                if 'weekday' in hours or 'weekend' in hours:
                    for daytype in list(hours.keys()):
                        if isinstance(hours[daytype], dict):
                            hours[daytype] = {int(k): v for k, v in hours[daytype].items()}
                else:
                    season['hours'] = {int(k): v for k, v in hours.items()}
    return par

def compute_periods(df, tariff, parameter, return_tariff=True, weekday_map=False, warnings=True):
    """compute tariff periods"""

    # convert dict string indices to int
    parameter = convert_tariff_dict(parameter, tariff=tariff)

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
    if 'export' in tariff[season]:
        tariff_map['export'] = tariff[season]['export']
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
