# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""Distributed Optimal and Predictive Energy Resources
Setpoint processor module.

Default battery setpoint processor for DoperWrapper, translating
optimization result columns to setpoint keys defined in
parameter['controller']['setpoint_names']:

    parameter['controller']['sp_processor'] = {
        "module": "doper.data.setpoint_processor",
        "name": "battery_setpoint_processor"
    }
"""

import pandas as pd

def default_config():
    """Return default setpoint processor configuration dict."""
    return {
        'battery_net_grid_power_col': 'Battery %s Net Grid Power [kW]', # source column
        'setpoint_scale': 1, # scaling
    }

def battery_setpoint_processor(data, parameter):
    """Default battery setpoint processor.

    Reads the first-timestep net grid power for each battery from the
    optimization result DataFrame and maps it to setpoint keys.
    """
    setpoints = {}
    log = {'messages': [], 'warnings': []}

    # Check if batteries are enabled and present
    if not parameter or not parameter['system']['battery']:
        return setpoints, log
    if 'batteries' not in parameter or not parameter['batteries']:
        return setpoints, log
    if not isinstance(data, pd.DataFrame) or data.empty:
        log['warnings'].append('Result DataFrame is empty or invalid.')
        return setpoints, log
    batteries = parameter['batteries']

    # Get config
    cfg = default_config()
    if 'setpoint_processor_config' in parameter:
        cfg.update(parameter['setpoint_processor_config'])

    # Resolve setpoint name template and battery name map
    sp_names = parameter['controller']['setpoint_names']
    if 'battery_power' not in sp_names:
        log['warnings'].append("'battery_power' not found in parameter['controller']['setpoint_names'].")
        return setpoints, log
    template = sp_names['battery_power']
    battery_name_map = sp_names['battery_name_map'] if 'battery_name_map' in sp_names else {}

    # Compute setpoints
    for bat in batteries:
        bat_name = bat['name']
        src_col = cfg['battery_net_grid_power_col'] % bat_name

        if src_col not in data.columns:
            log['warnings'].append(f'{src_col} not found in result DataFrame.')
            continue

        power_kw = data[src_col].iloc[0]
        if power_kw is None or (hasattr(power_kw, '__float__') and pd.isna(power_kw)):
            log['warnings'].append(f'{src_col} value is NaN at first timestep.')
            continue

        power_kw = float(power_kw) * cfg['setpoint_scale']
        display_name = battery_name_map[bat_name] if bat_name in battery_name_map else bat_name
        setpoints[template % display_name] = round(power_kw, 3)
        log['messages'].append(f'{bat_name}: {power_kw:.3f} kW -> {template % display_name}')

    return setpoints, log
