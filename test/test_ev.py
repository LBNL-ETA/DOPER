import unittest
import numpy as np
import pandas as pd
from pyomo.environ import Objective, minimize

from doper import DOPER, get_solver
from doper.models.basemodel import base_model
from doper.models.battery import add_battery
from doper.models.ev import add_ev, _get_sessions, _get_departures
import doper.examples as example
from doper.utility import default_output_list


# helpers
def _make_ev_parameter(min_leaving_soc=True, min_added_soc=0,
                       charging_revenue=0, discharging_cost=0):
    parameter = example.default_parameter()
    parameter['system']['battery'] = True
    parameter['system']['ev'] = True
    parameter['objective']['weight_ev_charging'] = 1
    parameter['objective']['weight_ev_discharging'] = 1
    parameter['batteries'] = [
        {
            'name': 'EV1',
            'capacity': 24,
            'power_charge': 10,
            'power_discharge': 10,
            'maxS': 10,
            'efficiency_charging': 1.0,
            'efficiency_discharging': 1.0,
            'self_discharging': 0.0,
            'soc_initial': 0.5,
            'soc_max': 1.0,
            'soc_min': 0.0,
            'min_leaving_soc': min_leaving_soc,
            'min_added_soc': min_added_soc,
            'charging_revenue': charging_revenue,
            'discharging_cost': discharging_cost,
        }
    ]
    return parameter


def _make_data_with_schedule(parameter, avail_first_half=1, avail_second_half=0):
    """Hourly data with a simple plug-in schedule (first half / second half)."""
    data = example.ts_inputs(parameter, load='B90', scale_load=5, scale_pv=0)
    n = len(data)
    mid = n // 2
    avail = [avail_first_half] * mid + [avail_second_half] * (n - mid)
    data['battery_EV1_avail'] = avail
    data['battery_EV1_demand'] = 0.0
    return data


def _run_ev_optimization(parameter, data):
    """Run a battery + EV optimization and return (duration, objective, df, model)."""

    def control_model(inputs, param):
        m = base_model(inputs, param)
        m = add_battery(m, inputs, param)
        m = add_ev(m, inputs, param)

        def obj(m):
            o = (m.sum_energy_cost * param['objective']['weight_energy']
                 + m.sum_demand_cost * param['objective']['weight_demand'])
            if param['objective'].get('weight_ev_charging', 0):
                o -= m.ev_charging_revenue * param['objective']['weight_ev_charging']
            if param['objective'].get('weight_ev_discharging', 0):
                o += m.ev_discharging_cost * param['objective']['weight_ev_discharging']
            return o

        m.objective = Objective(rule=obj, sense=minimize)
        return m

    output_list = default_output_list(parameter)
    solver_path = get_solver('cbc')
    smart = DOPER(model=control_model, parameter=parameter,
                  solver_path=solver_path, output_list=output_list)
    res = smart.do_optimization(data)
    duration, objective, df, model, result, termination, parameter = res
    return duration, objective, df, model


class TestEvHelpers(unittest.TestCase):

    def test_all_sessions_starts_plugged_in(self):
        avail = [1, 1, 0, 0, 1, 1, 0]
        ts    = [0, 1, 2, 3, 4, 5, 6]
        self.assertEqual(_get_sessions(avail, ts), [(0, 2), (4, 6)])

    def test_all_sessions_starts_unplugged(self):
        avail = [0, 0, 1, 1, 0, 1, 0]
        ts    = [0, 1, 2, 3, 4, 5, 6]
        self.assertEqual(_get_sessions(avail, ts), [(2, 4), (5, 6)])

    def test_all_sessions_no_departure(self):
        avail = [1, 1, 1, 1]
        ts    = [0, 1, 2, 3]
        self.assertEqual(_get_sessions(avail, ts), [])

    def test_all_sessions_always_unplugged(self):
        avail = [0, 0, 0]
        ts    = [0, 1, 2]
        self.assertEqual(_get_sessions(avail, ts), [])

    def test_departures_basic(self):
        avail = [1, 1, 0, 0, 1, 0]
        ts    = [0, 1, 2, 3, 4, 5]
        self.assertEqual(_get_departures(avail, ts), [2, 5])

    def test_departures_none(self):
        avail = [1, 1, 1]
        ts    = [0, 1, 2]
        self.assertEqual(_get_departures(avail, ts), [])

    def test_departures_starts_unplugged(self):
        avail = [0, 1, 0]
        ts    = [0, 1, 2]
        self.assertEqual(_get_departures(avail, ts), [2])


class TestEvModelVariables(unittest.TestCase):
    """Check that add_ev adds expected Pyomo variables to the model."""

    setUpComplete = False

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter()
            data = _make_data_with_schedule(parameter)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_has_battery_ev_charging_revenue(self):
        self.assertTrue(hasattr(self.model, 'battery_ev_charging_revenue'))

    def test_has_ev_charging_revenue(self):
        self.assertTrue(hasattr(self.model, 'ev_charging_revenue'))

    def test_has_battery_ev_discharging_cost(self):
        self.assertTrue(hasattr(self.model, 'battery_ev_discharging_cost'))

    def test_has_ev_discharging_cost(self):
        self.assertTrue(hasattr(self.model, 'ev_discharging_cost'))

    def test_ev_charging_revenue_has_value(self):
        val = self.model.ev_charging_revenue.value
        self.assertIsNotNone(val)

    def test_ev_discharging_cost_has_value(self):
        val = self.model.ev_discharging_cost.value
        self.assertIsNotNone(val)

    def test_per_battery_charging_revenue_indexed(self):
        self.assertIn('EV1', list(self.model.battery_ev_charging_revenue.keys()))

    def test_per_battery_discharging_cost_indexed(self):
        self.assertIn('EV1', list(self.model.battery_ev_discharging_cost.keys()))


class TestEvMinLeavingSocTrue(unittest.TestCase):
    """When min_leaving_soc=True and EV starts plugged in, energy at departure
    must be >= energy at plug-in."""

    setUpComplete = False

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=True)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.parameter = parameter
            self.__class__.setUpComplete = True

    def _get_energy_values(self):
        return sorted(
            [(ts, self.model.battery_energy[ts, 'EV1'].value)
             for ts in self.model.ts],
            key=lambda x: x[0]
        )

    def test_departure_energy_gte_plug_in_energy(self):
        energies = self._get_energy_values()
        ts_list = [e[0] for e in energies]
        avail = [self.model.battery_available[ts, 'EV1'] for ts in ts_list]

        dep_idx = None
        for i in range(1, len(avail)):
            if avail[i - 1] == 1 and avail[i] == 0:
                dep_idx = i
                break

        self.assertIsNotNone(dep_idx, 'No departure found in avail schedule')
        initial_energy = energies[0][1]
        departure_energy = energies[dep_idx][1]
        self.assertGreaterEqual(
            departure_energy, initial_energy - 1e-4,
            msg=f'Departure energy {departure_energy:.3f} < plug-in energy {initial_energy:.3f}'
        )


class TestEvMinLeavingSocFalse(unittest.TestCase):
    """When min_leaving_soc=False no departure constraint is added."""

    setUpComplete = False

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=False)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_no_min_leaving_energy_constraints(self):
        names = [c for c in dir(self.model) if 'constraint_ev_min_leaving' in c]
        self.assertEqual(len(names), 0,
                         msg='Unexpected leaving-SOC constraints found when min_leaving_soc=False')

    def test_model_solves_successfully(self):
        self.assertIsNotNone(self.model.ev_charging_revenue.value)


class TestEvMinLeavingSocFloat(unittest.TestCase):
    """When min_leaving_soc is a float, departure energy >= float * capacity."""

    setUpComplete = False
    MIN_SOC = 0.6

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=self.MIN_SOC)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_departure_energy_gte_float_floor(self):
        capacity = self.model.bat_capacity['EV1']
        floor = self.MIN_SOC * capacity
        energies = sorted(
            [(ts, self.model.battery_energy[ts, 'EV1'].value) for ts in self.model.ts],
            key=lambda x: x[0]
        )
        ts_list = [e[0] for e in energies]
        avail = [self.model.battery_available[ts, 'EV1'] for ts in ts_list]
        for i in range(1, len(avail)):
            if avail[i - 1] == 1 and avail[i] == 0:
                dep_energy = energies[i][1]
                self.assertGreaterEqual(
                    dep_energy, floor - 1e-4,
                    msg=f'Departure energy {dep_energy:.3f} < floor {floor:.3f}'
                )


class TestEvMinAddedSoc(unittest.TestCase):
    """min_added_soc raises the departure floor by added_soc * capacity."""

    setUpComplete = False
    ADDED_SOC = 0.1

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=True,
                                           min_added_soc=self.ADDED_SOC)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_departure_energy_gte_plug_in_plus_added(self):
        capacity = self.model.bat_capacity['EV1']
        energies = sorted(
            [(ts, self.model.battery_energy[ts, 'EV1'].value) for ts in self.model.ts],
            key=lambda x: x[0]
        )
        ts_list = [e[0] for e in energies]
        avail = [self.model.battery_available[ts, 'EV1'] for ts in ts_list]
        initial_energy = energies[0][1]
        floor = initial_energy + self.ADDED_SOC * capacity
        for i in range(1, len(avail)):
            if avail[i - 1] == 1 and avail[i] == 0:
                dep_energy = energies[i][1]
                self.assertGreaterEqual(
                    dep_energy, floor - 1e-4,
                    msg=f'Departure energy {dep_energy:.3f} < floor {floor:.3f}'
                )
                break


class TestEvChargingRevenue(unittest.TestCase):
    """charging_revenue causes ev_charging_revenue to reflect net energy charged."""

    setUpComplete = False
    RATE = 0.20

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=False,
                                           charging_revenue=self.RATE)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_per_battery_revenue_has_value(self):
        val = self.model.battery_ev_charging_revenue['EV1'].value
        self.assertIsNotNone(val)

    def test_aggregate_equals_per_battery(self):
        per_bat = self.model.battery_ev_charging_revenue['EV1'].value
        total = self.model.ev_charging_revenue.value
        self.assertAlmostEqual(per_bat, total, places=4)

    def test_revenue_zero_when_rate_is_zero(self):
        parameter = _make_ev_parameter(min_leaving_soc=False, charging_revenue=0)
        data = _make_data_with_schedule(parameter)
        _, _, _, model = _run_ev_optimization(parameter, data)
        self.assertAlmostEqual(model.ev_charging_revenue.value, 0.0, places=4)


class TestEvDischargingCost(unittest.TestCase):
    """discharging_cost causes ev_discharging_cost to be >= 0."""
    setUpComplete = False
    RATE = 0.10

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=False,
                                           discharging_cost=self.RATE)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=0)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_discharging_cost_nonnegative(self):
        val = self.model.ev_discharging_cost.value
        self.assertGreaterEqual(val, -1e-6)

    def test_per_battery_cost_nonnegative(self):
        val = self.model.battery_ev_discharging_cost['EV1'].value
        self.assertGreaterEqual(val, -1e-6)

    def test_aggregate_equals_per_battery(self):
        per_bat = self.model.battery_ev_discharging_cost['EV1'].value
        total = self.model.ev_discharging_cost.value
        self.assertAlmostEqual(per_bat, total, places=4)

    def test_cost_zero_when_rate_is_zero(self):
        parameter = _make_ev_parameter(min_leaving_soc=False, discharging_cost=0)
        data = _make_data_with_schedule(parameter)
        _, _, _, model = _run_ev_optimization(parameter, data)
        self.assertAlmostEqual(model.ev_discharging_cost.value, 0.0, places=4)


class TestEvStartsUnplugged(unittest.TestCase):
    """When min_leaving_soc=True and EV starts unplugged but has a complete
    plug-in/plug-out session, the constraint is added for that session."""

    setUpComplete = False

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=True)
            data = example.ts_inputs(parameter, load='B90', scale_load=5, scale_pv=0)
            n = len(data)
            q = n // 4
            avail = [0] * q + [1] * q + [0] * (n - 2 * q)
            data['battery_EV1_avail'] = avail
            data['battery_EV1_demand'] = 0.0
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_constraint_added_for_mid_horizon_session(self):
        names = [c for c in dir(self.model) if 'constraint_ev_min_leaving' in c]
        self.assertGreater(len(names), 0,
                           msg='Leaving-SOC constraint should exist for mid-horizon plug-in/plug-out')

    def test_model_solves_successfully(self):
        self.assertIsNotNone(self.model.ev_charging_revenue.value)


class TestEvNoStateChange(unittest.TestCase):
    """When min_leaving_soc=True but there is no state change, no constraint added."""

    setUpComplete = False

    def setUp(self):
        if not self.__class__.setUpComplete:
            parameter = _make_ev_parameter(min_leaving_soc=True)
            data = _make_data_with_schedule(parameter,
                                            avail_first_half=1,
                                            avail_second_half=1)
            _, _, _, model = _run_ev_optimization(parameter, data)
            self.__class__.model = model
            self.__class__.setUpComplete = True

    def test_no_leaving_soc_constraints_when_no_state_change(self):
        names = [c for c in dir(self.model) if 'constraint_ev_min_leaving' in c]
        self.assertEqual(len(names), 0,
                         msg='No leaving-SOC constraints should exist when EV never unplugs')

    def test_model_solves_successfully(self):
        self.assertIsNotNone(self.model.ev_charging_revenue.value)


if __name__ == '__main__':
    unittest.main()
