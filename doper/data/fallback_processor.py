# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

"""Distributed Optimal and Predictive Energy Resources
Fallback processor module.

TOU-based battery fallback for DoperWrapper:

    parameter['controller']['fb_processor'] = {
        "module": "doper.data.fallback_processor",
        "name": "battery_tou_processor"
    }
"""

from datetime import datetime, timezone
import pandas as pd

def default_config():
    """Return default TOU processor configuration dict."""
    return {
        # (start_h, end_h, mode, rate)
        # rate [kW] overrides window calculation when set
        'tou_windows': [
            (0, 10, 'charge', None),
            (10, 15, 'idle', None),
            (15, 21, 'discharge', None),
            (21, 24, 'idle', None),
        ],
        'safety_factor': 1.0, # set to greater than 1 for accelerated charging/discharging
        'min_hours_remaining': 0, # set minimal hours of discharge remaining above soc_min
        'emergency_recovery_hours': 2.0, # charging time when soc < soc_min
        'setpoint_scale': 1, # scale of setpoint
    }

def _get_window(hour_float, config):
    """Return (mode, end_h, rate) for the given fractional hour."""
    for start_h, end_h, mode, rate in config['tou_windows']:
        if start_h <= hour_float < end_h:
            return mode, end_h, rate
    return 'idle', 24, None

def _size_power(mode, hour_float, window_end_h, bat, config):
    """Return power setpoint [kW] sized from battery state and remaining window time."""
    soc = bat['soc_initial']
    soc_min = bat['soc_min']
    soc_max = bat['soc_max']
    capacity = bat['capacity']
    max_charge = bat['power_charge']
    max_discharge = bat['power_discharge']
    eff_charge = bat['efficiency_charging']
    eff_discharge = bat['efficiency_discharging']
    safety_factor = config['safety_factor']
    hours_remaining = max(window_end_h - hour_float, config['min_hours_remaining'])

    if mode == 'charge':
        energy_needed = max(0.0, (soc_max - soc) * capacity)
        if energy_needed <= 0.0:
            return 0.0
        return min(max_charge, energy_needed / eff_charge / hours_remaining * safety_factor)

    if mode == 'discharge':
        energy_needed = max(0.0, (soc - soc_min) * capacity)
        if energy_needed <= 0.0:
            return 0.0
        return -min(max_discharge, energy_needed * eff_discharge / hours_remaining * safety_factor)

    return 0.0

def _apply_safety_overrides(power_kw, mode, bat, cfg, log):
    """Apply SOC-based safety overrides; returns adjusted power_kw."""
    soc = bat['soc_initial']
    soc_min = bat['soc_min']
    soc_max = bat['soc_max']
    capacity = bat['capacity']
    max_charge = bat['power_charge']
    eff_charge = bat['efficiency_charging']
    name = bat['name']

    if soc < soc_min:
        energy_needed = max(0.0, (soc_max - soc) * capacity)
        power_kw = min(max_charge, energy_needed / eff_charge / cfg['emergency_recovery_hours'] * cfg['safety_factor'])
        log['overrides'].append(f'{name}: soc {soc:.3f} <= soc_min, emergency charge {power_kw:.2f} kW')
    elif soc >= soc_max and mode == 'charge':
        power_kw = 0.0
        log['overrides'].append(f'{name}: soc {soc:.3f} >= soc_max, switched to idle')

    return power_kw

def battery_tou_processor(data, parameter):
    """TOU fallback setpoint processor."""

    setpoints = {}
    log = {'messages': [], 'overrides': [], 'hour': None}

    # Check if battery present
    if not parameter or 'batteries' not in parameter or not parameter['batteries']:
        return setpoints, log
    batteries = parameter['batteries']

    # Get config
    cfg = default_config()
    if 'battery_tou_processor_config' in parameter:
        cfg.update(parameter['battery_tou_processor_config'])

    # Current time from data or system clock
    current_ts = None
    if isinstance(data, pd.DataFrame) and not data.empty:
        current_ts = data.index[0]
        log['messages'].append(f'using data time: {current_ts}')
    if current_ts is None:
        current_ts = pd.Timestamp(datetime.now(tz=timezone.utc))
        tz = parameter['site']['local_timezone']
        current_ts = current_ts.tz_convert(tz)
        log['messages'].append(f'using system time: {current_ts}')
    hour_float = current_ts.hour + current_ts.minute / 60.0
    log['hour'] = hour_float

    # Get active mode
    mode, window_end_h, rate = _get_window(hour_float, cfg)

    # Resolve setpoint name template
    sp_names = parameter['controller']['setpoint_names']
    template = sp_names['battery_power']
    battery_name_map = sp_names['battery_name_map'] if 'battery_name_map' in sp_names else {}

    # Apply battery setpoints
    for bat in batteries:
        power_kw = rate if rate is not None else _size_power(mode, hour_float, window_end_h, bat, cfg)
        power_kw = _apply_safety_overrides(power_kw, mode, bat, cfg, log)
        sp = float(round(power_kw * cfg['setpoint_scale'], 3))
        display_name = battery_name_map[bat['name']] if bat['name'] in battery_name_map else bat['name']
        setpoints[template % display_name] = sp

    return setpoints, log
