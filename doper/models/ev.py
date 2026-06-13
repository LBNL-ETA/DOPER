# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
EV model module.
"""

import numpy as np
from pyomo.environ import Var, Constraint


def _get_avail(inputs, b):
    """Convert availability to list."""
    avail = inputs[f'battery_{b}_avail']
    ts = (avail.index.view(np.int64) / 1e9).tolist()
    return avail.tolist(), ts

def _get_sessions(avail, ts):
    """Return (ts_in, ts_out) pairs for every complete plug-in session."""
    sessions = []
    n = len(avail)
    ts_in = ts[0] if avail[0] == 1 else None
    for i in range(1, n):
        if avail[i - 1] == 0 and avail[i] == 1:
            ts_in = ts[i]
        elif ts_in is not None and avail[i - 1] == 1 and avail[i] == 0:
            sessions.append((ts_in, ts[i]))
            ts_in = None
    return sessions

def _get_departures(avail, ts):
    """Return all timestamps where avail transitions 1->0."""
    return [ts[i] for i in range(1, len(avail)) if avail[i - 1] == 1 and avail[i] == 0]

def add_ev(model, inputs, parameter):
    """Add EV constraints and revenue/cost equations."""

    batt_param_map = {b['name']: b for b in parameter['batteries']}
    batt_sessions = {}
    counter = 0

    # make min_leaving_soc constraints
    for b in model.batteries:

        # battery parameters
        bp = batt_param_map[b]
        min_soc = bp.get('min_leaving_soc', False)
        added = bp.get('min_added_soc', 0) or 0

        # skip
        if min_soc is False:
            continue

        # convert plug-in times
        avail, ts = _get_avail(inputs, b)
        changed = any(avail[i] != avail[i - 1] for i in range(1, len(avail)))

        # get all sessions [(ts_in, ts_out)]
        batt_sessions[b] = _get_sessions(avail, ts)

        # capacity
        cap = model.bat_capacity[b]

        if min_soc is True:
            # do nothing if no full session
            if not changed:
                continue
            # apply constraint for every complete session
            for ts_in, ts_out in batt_sessions[b]:
                model.add_component(
                    f'constraint_ev_min_leaving_energy_{b}_{counter}',
                    Constraint(expr=(
                        model.battery_energy[ts_out, b]
                        >= model.battery_energy[ts_in, b] + added * cap
                    ))
                )
                counter += 1
        else:
            # fixed >= min_soc when unplug
            min_soc_b = float(min_soc) * cap + added * cap
            for ts_out in _get_departures(avail, ts):
                model.add_component(
                    f'constraint_ev_min_leaving_energy_{b}_{counter}',
                    Constraint(expr=(model.battery_energy[ts_out, b] >= min_soc_b))
                )
                counter += 1

    # ev charging revenue
    model.battery_ev_charging_revenue = Var(model.batteries, doc='per-battery EV charging revenue [$]',
                                            bounds=(None, None))
    model.ev_charging_revenue = Var(doc='total EV charging revenue [$]', bounds=(None, None))

    for b in model.batteries:
        rate = batt_param_map[b].get('charging_revenue', 0)
        sessions = batt_sessions.get(b, [])

        if rate and sessions:
            # revenue for each charging session
            expr = model.battery_ev_charging_revenue[b] == sum(
                rate * (model.battery_energy[ts_out, b] - model.battery_energy[ts_in, b])
                for ts_in, ts_out in sessions
            )
        else:
            # no session
            expr = model.battery_ev_charging_revenue[b] == 0

        model.add_component(
            f'constraint_battery_ev_charging_revenue_{b}',
            Constraint(expr=expr)
        )
    # total ev chrging revenue
    model.constraint_ev_charging_revenue = Constraint(
        expr=model.ev_charging_revenue == sum(
            model.battery_ev_charging_revenue[b] for b in model.batteries
        )
    )

    # ev discharging cost
    model.battery_ev_discharging_cost = Var(model.batteries, doc='per-battery EV discharging cost [$]',
                                            bounds=(0, None))
    model.ev_discharging_cost = Var(doc='total EV discharging cost [$]', bounds=(0, None))

    for b in model.batteries:
        rate = batt_param_map[b].get('discharging_cost', 0)
        if rate:
            # apply rate
            expr = model.battery_ev_discharging_cost[b] == rate * sum(
                model.battery_discharge_grid_power[ts, b] / model.timestep_scale[ts]
                for ts in model.ts
            )
        else:
            # no cost
            expr = model.battery_ev_discharging_cost[b] == 0

        model.add_component(
            f'constraint_battery_ev_discharging_cost_{b}',
            Constraint(expr=expr)
        )
    # total ev discharging cost
    model.constraint_ev_discharging_cost = Constraint(
        expr=model.ev_discharging_cost == sum(
            model.battery_ev_discharging_cost[b] for b in model.batteries
        )
    )

    return model
