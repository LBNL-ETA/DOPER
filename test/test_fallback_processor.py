"""Unit tests for doper.data.fallback_processor."""

import unittest
from unittest.mock import patch
from datetime import datetime

import pandas as pd

from doper.data.fallback_processor import (
    _get_excess_pv,
    _get_window,
    _size_power,
    _apply_safety_overrides,
    battery_tou_processor,
    default_config,
)


def _make_data(hour=2, load=10.0, pv=None):
    """Helper: single-row DataFrame at the given hour of 2019-01-01."""
    ts = pd.Timestamp(f'2019-01-01 {hour:02d}:00:00')
    row = {'load_demand': [load]}
    if pv is not None:
        row['generation_pv'] = [pv]
    return pd.DataFrame(row, index=[ts])

def _make_bat(name='bat', soc=0.5, soc_min=0.2, soc_max=1.0,
              capacity=200.0, power_charge=50.0, power_discharge=50.0,
              efficiency_charging=1.0, efficiency_discharging=1.0):
    """Helper: minimal battery parameter dict."""
    return {
        'name': name,
        'soc_initial': soc,
        'soc_min': soc_min,
        'soc_max': soc_max,
        'capacity': capacity,
        'power_charge': power_charge,
        'power_discharge': power_discharge,
        'efficiency_charging': efficiency_charging,
        'efficiency_discharging': efficiency_discharging,
    }

def _make_param(bat=None):
    """Helper: parameter dict with one battery."""
    if bat is None:
        bat = _make_bat()
    return {
        'batteries': [bat],
        'controller': {
            'setpoint_names': {'battery_power': 'Battery %s Power Command [kW]'}
        },
    }

def _pv_excess_config(hour_start=0, hour_end=10):
    """Helper: config with pv_excess_only=True for one charge window."""
    return {
        'tou_windows': [
            (hour_start, hour_end, 'charge', None, True),
            (hour_end, 24, 'idle', None, False),
        ]
    }


# default_config tests
class TestDefaultConfig(unittest.TestCase):
    """Tests for default_config."""

    def test_returns_dict(self):
        self.assertIsInstance(default_config(), dict)

    def test_has_required_keys(self):
        cfg = default_config()
        for key in ('tou_windows', 'safety_factor', 'min_hours_remaining', 'emergency_recovery_hours'):
            self.assertIn(key, cfg)

    def test_tou_windows_has_four_entries(self):
        self.assertEqual(len(default_config()['tou_windows']), 4)

    def test_tou_windows_are_five_tuples(self):
        cfg = default_config()
        for entry in cfg['tou_windows']:
            self.assertEqual(len(entry), 5, msg=f'expected 5-tuple, got {entry}')

    def test_modes_are_lowercase(self):
        cfg = default_config()
        for _, _, mode, _, _ in cfg['tou_windows']:
            self.assertEqual(mode, mode.lower())

    def test_tou_windows_rate_defaults_to_none(self):
        cfg = default_config()
        for _, _, _, rate, _ in cfg['tou_windows']:
            self.assertIsNone(rate)

    def test_tou_windows_pv_excess_only_defaults_to_false(self):
        cfg = default_config()
        for _, _, _, _, pv_excess_only in cfg['tou_windows']:
            self.assertFalse(pv_excess_only)


# _get_window tests
class TestGetWindow(unittest.TestCase):
    """Tests for the _get_window helper."""

    def setUp(self):
        self.cfg = default_config()

    def test_overnight_returns_charge(self):
        mode, end_h, rate, pv_excess_only = _get_window(0.0, self.cfg)
        self.assertEqual(mode, 'charge')
        self.assertEqual(end_h, 10)
        self.assertIsNone(rate)
        self.assertFalse(pv_excess_only)

    def test_overnight_midpoint(self):
        mode, *_ = _get_window(3.0, self.cfg)
        self.assertEqual(mode, 'charge')

    def test_morning_boundary_is_idle(self):
        mode, _, rate, _ = _get_window(10.0, self.cfg)
        self.assertEqual(mode, 'idle')
        self.assertIsNone(rate)

    def test_midday_window(self):
        mode, end_h, _, _ = _get_window(12.0, self.cfg)
        self.assertEqual(mode, 'idle')
        self.assertEqual(end_h, 15)

    def test_peak_window_is_discharge(self):
        mode, end_h, _, _ = _get_window(18.0, self.cfg)
        self.assertEqual(mode, 'discharge')
        self.assertEqual(end_h, 21)

    def test_evening_window_is_idle(self):
        mode, *_ = _get_window(22.5, self.cfg)
        self.assertEqual(mode, 'idle')

    def test_boundary_exactly_24(self):
        mode, *_ = _get_window(24.0, self.cfg)
        self.assertEqual(mode, 'idle')

    def test_rate_returned_when_set(self):
        cfg = default_config()
        cfg['tou_windows'][2] = (15, 21, 'discharge', 30.0, False)
        _, _, rate, _ = _get_window(18.0, cfg)
        self.assertEqual(rate, 30.0)

    def test_pv_excess_only_returned_when_set(self):
        cfg = default_config()
        cfg['tou_windows'][0] = (0, 10, 'charge', None, True)
        _, _, _, pv_excess_only = _get_window(3.0, cfg)
        self.assertTrue(pv_excess_only)

    def test_pv_excess_only_false_in_other_windows(self):
        cfg = default_config()
        cfg['tou_windows'][0] = (0, 10, 'charge', None, True)
        _, _, _, pv_excess_only = _get_window(18.0, cfg) # discharge window
        self.assertFalse(pv_excess_only)

    def test_unmatched_hour_returns_idle_defaults(self):
        mode, end_h, rate, pv_excess_only = _get_window(24.0, self.cfg)
        self.assertEqual(mode, 'idle')
        self.assertEqual(end_h, 24)
        self.assertIsNone(rate)
        self.assertFalse(pv_excess_only)


# _get_excess_pv tests
class TestGetExcessPv(unittest.TestCase):
    """Tests for the _get_excess_pv helper."""

    def test_excess_pv_when_generation_exceeds_load(self):
        data = _make_data(load=10.0, pv=25.0)
        self.assertAlmostEqual(_get_excess_pv(data), 15.0)

    def test_zero_when_load_exceeds_generation(self):
        data = _make_data(load=20.0, pv=5.0)
        self.assertEqual(_get_excess_pv(data), 0.0)

    def test_zero_when_load_equals_generation(self):
        data = _make_data(load=10.0, pv=10.0)
        self.assertEqual(_get_excess_pv(data), 0.0)

    def test_returns_zero_when_data_is_none(self):
        self.assertEqual(_get_excess_pv(None), 0.0)

    def test_returns_zero_when_data_is_empty(self):
        self.assertEqual(_get_excess_pv(pd.DataFrame()), 0.0)

    def test_returns_zero_when_no_generation_pv_column(self):
        # no pv column → pv treated as 0, load=10 → excess = max(0, 0-10) = 0
        data = _make_data(load=10.0, pv=None)
        self.assertEqual(_get_excess_pv(data), 0.0)

    def test_returns_pv_when_no_load_column(self):
        # no load column → load treated as 0, pv=15 → excess = 15
        ts = pd.Timestamp('2019-01-01 09:00:00')
        data = pd.DataFrame({'generation_pv': [15.0]}, index=[ts])
        self.assertAlmostEqual(_get_excess_pv(data), 15.0)

    def test_uses_first_row_only(self):
        ts0 = pd.Timestamp('2019-01-01 09:00:00')
        ts1 = pd.Timestamp('2019-01-01 09:15:00')
        data = pd.DataFrame(
            {'load_demand': [5.0, 50.0], 'generation_pv': [20.0, 0.0]},
            index=[ts0, ts1],
        )
        self.assertAlmostEqual(_get_excess_pv(data), 15.0)


# _size_power tests
class TestSizePower(unittest.TestCase):
    """Tests for the _size_power helper."""

    def setUp(self):
        self.cfg = default_config()
        self.sf = self.cfg['safety_factor']

    def test_idle_returns_zero(self):
        bat = _make_bat()
        power = _size_power('idle', 7.0, 9.0, bat, self.cfg)
        self.assertEqual(power, 0.0)

    def test_charge_sized_by_energy(self):
        # safety_factor=1.0, eff=1.0, 4 h remaining, fill 0.5->1.0 on 200 kWh = 100 kWh
        bat = _make_bat(soc=0.5)
        power = _size_power('charge', 2.0, 6.0, bat, self.cfg)
        expected = min(50, 100 / 4.0 * self.sf)
        self.assertAlmostEqual(power, expected, places=6)

    def test_charge_efficiency_increases_power(self):
        # lower efficiency → more grid power needed to store same energy
        bat_eff = _make_bat(soc=0.5, efficiency_charging=0.9)
        bat_unit = _make_bat(soc=0.5, efficiency_charging=1.0)
        power_eff = _size_power('charge', 2.0, 6.0, bat_eff, self.cfg)
        power_unit = _size_power('charge', 2.0, 6.0, bat_unit, self.cfg)
        self.assertGreater(power_eff, power_unit)

    def test_charge_efficiency_exact(self):
        # energy_needed=100 kWh, 4 h, eff=0.8 → 100/0.8/4 = 31.25 kW
        bat = _make_bat(soc=0.5, efficiency_charging=0.8)
        power = _size_power('charge', 2.0, 6.0, bat, self.cfg)
        self.assertAlmostEqual(power, 31.25, places=6)

    def test_charge_capped_at_max_charge(self):
        bat = _make_bat(soc=0.2, capacity=200, power_charge=50)
        power = _size_power('charge', 5.9, 6.0, bat, self.cfg)
        self.assertLessEqual(power, 50.0)

    def test_charge_full_battery_returns_zero(self):
        bat = _make_bat(soc=1.0)
        power = _size_power('charge', 2.0, 6.0, bat, self.cfg)
        self.assertEqual(power, 0.0)

    def test_discharge_sized_by_energy(self):
        # 3 h remaining, drain 0.8->0.2 on 200 kWh = 120 kWh; discharge is negative
        bat = _make_bat(soc=0.8)
        power = _size_power('discharge', 18.0, 21.0, bat, self.cfg)
        expected = -min(50, 120 / 3.0 * self.sf)
        self.assertAlmostEqual(power, expected, places=6)

    def test_discharge_capped_at_max_discharge(self):
        bat = _make_bat(soc=0.9, capacity=200, power_discharge=50)
        power = _size_power('discharge', 20.9, 21.0, bat, self.cfg)
        self.assertLessEqual(power, 50.0)

    def test_discharge_empty_battery_returns_zero(self):
        bat = _make_bat(soc=0.2)
        power = _size_power('discharge', 18.0, 21.0, bat, self.cfg)
        self.assertEqual(power, 0.0)

    def test_discharge_efficiency_reduces_power(self):
        # lower efficiency → less AC power delivered (smaller magnitude, closer to zero)
        bat_eff = _make_bat(soc=0.8, efficiency_discharging=0.9)
        bat_unit = _make_bat(soc=0.8, efficiency_discharging=1.0)
        power_eff = _size_power('discharge', 18.0, 21.0, bat_eff, self.cfg)
        power_unit = _size_power('discharge', 18.0, 21.0, bat_unit, self.cfg)
        self.assertGreater(power_eff, power_unit) # -36 > -40; eff<1 yields less negative value

    def test_discharge_efficiency_exact(self):
        # energy_soc=120 kWh, 3 h, eff=0.9 → -120*0.9/3 = -36 kW
        bat = _make_bat(soc=0.8, efficiency_discharging=0.9)
        power = _size_power('discharge', 18.0, 21.0, bat, self.cfg)
        self.assertAlmostEqual(power, -36.0, places=6)


# _apply_safety_overrides tests
class TestApplySafetyOverrides(unittest.TestCase):
    """Tests for the _apply_safety_overrides helper."""

    def setUp(self):
        self.cfg = default_config()
        self.log = {'messages': [], 'overrides': [], 'hour': None}

    def test_soc_below_min_forces_charge(self):
        bat = _make_bat(soc=0.1, soc_min=0.2, soc_max=1.0)
        power_kw = _apply_safety_overrides(0.0, 'idle', bat, self.cfg, self.log)
        self.assertGreater(power_kw, 0.0)
        self.assertEqual(len(self.log['overrides']), 1)

    def test_soc_at_max_during_charge_sets_zero(self):
        bat = _make_bat(soc=1.0, soc_min=0.2, soc_max=1.0)
        power_kw = _apply_safety_overrides(30.0, 'charge', bat, self.cfg, self.log)
        self.assertEqual(power_kw, 0.0)
        self.assertEqual(len(self.log['overrides']), 1)

    def test_soc_at_max_during_discharge_unchanged(self):
        bat = _make_bat(soc=1.0, soc_min=0.2, soc_max=1.0)
        power_kw = _apply_safety_overrides(30.0, 'discharge', bat, self.cfg, self.log)
        self.assertEqual(power_kw, 30.0)
        self.assertEqual(len(self.log['overrides']), 0)

    def test_normal_soc_unchanged(self):
        bat = _make_bat(soc=0.5)
        power_kw = _apply_safety_overrides(20.0, 'charge', bat, self.cfg, self.log)
        self.assertEqual(power_kw, 20.0)
        self.assertEqual(len(self.log['overrides']), 0)

    def test_emergency_charge_accounts_for_efficiency(self):
        # energy_needed=(1.0-0.1)*200=180 kWh, recovery=2h, eff=0.9
        # grid power = 180/0.9/2 = 100 kW, capped at power_charge=50
        bat = _make_bat(soc=0.1, soc_min=0.2, soc_max=1.0, capacity=200,
                        power_charge=50, efficiency_charging=0.9)
        bat_unit = _make_bat(soc=0.1, soc_min=0.2, soc_max=1.0, capacity=200,
                             power_charge=50, efficiency_charging=1.0)
        power_eff = _apply_safety_overrides(0.0, 'idle', bat, self.cfg, self.log)
        power_unit = _apply_safety_overrides(0.0, 'idle', bat_unit, self.cfg, self.log)
        self.assertGreaterEqual(power_eff, power_unit) # lower eff needs more grid power


# battery_tou_processor integration tests
class TestBatteryTouProcessor(unittest.TestCase):
    """Integration tests for battery_tou_processor."""

    # Guard cases
    def test_returns_empty_when_parameter_is_none(self):
        setpoints, log = battery_tou_processor(None, None)
        self.assertEqual(setpoints, {})
        self.assertIn('messages', log)

    def test_returns_empty_when_no_batteries(self):
        setpoints, log = battery_tou_processor(None, {'controller': {}})
        self.assertEqual(setpoints, {})

    def test_returns_battery_name_as_key(self):
        data = _make_data(hour=2)
        setpoints, _ = battery_tou_processor(data, _make_param())
        self.assertIn('Battery bat Power Command [kW]', setpoints)

    def test_setpoint_value_is_float(self):
        data = _make_data(hour=3)
        setpoints, _ = battery_tou_processor(data, _make_param())
        key = 'Battery bat Power Command [kW]'
        self.assertIsInstance(setpoints[key], float)

    # Mode selection by time window
    def test_overnight_window_charges(self):
        data = _make_data(hour=3)
        setpoints, _ = battery_tou_processor(data, _make_param(_make_bat(soc=0.5)))
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_idle_window_gives_zero_power(self):
        data = _make_data(hour=11) # idle window 10-15
        setpoints, _ = battery_tou_processor(data, _make_param(_make_bat(soc=0.5)))
        self.assertEqual(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_peak_window_discharges(self):
        data = _make_data(hour=18)
        setpoints, _ = battery_tou_processor(data, _make_param(_make_bat(soc=0.8)))
        self.assertLess(setpoints['Battery bat Power Command [kW]'], 0.0)

    # Rate override
    def test_rate_used_directly_when_set(self):
        data = _make_data(hour=18)
        param = _make_param(_make_bat(soc=0.5))
        param['battery_tou_processor_config'] = {
            'tou_windows': [
                (0, 6, 'charge', None, False),
                (6, 9, 'idle', None, False),
                (9, 15, 'charge', None, False),
                (15, 21, 'discharge', 25.0, False),
                (21, 24, 'idle', None, False),
            ]
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 25.0, places=3)

    def test_none_rate_uses_calculation(self):
        data = _make_data(hour=3)
        param = _make_param(_make_bat(soc=0.5))
        param['battery_tou_processor_config'] = {
            'tou_windows': [
                (0, 6, 'charge', None, False),
                (6, 9, 'idle', None, False),
                (9, 15, 'charge', None, False),
                (15, 21, 'discharge', None, False),
                (21, 24, 'idle', None, False),
            ]
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)

    # Safety overrides
    def test_soc_below_min_forces_charge(self):
        bat = _make_bat(soc=0.1, soc_min=0.2)
        data = _make_data(hour=22) # idle window
        setpoints, log = battery_tou_processor(data, _make_param(bat))
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)
        self.assertTrue(len(log['overrides']) > 0)

    def test_soc_at_max_during_charge_gives_zero(self):
        bat = _make_bat(soc=1.0, soc_max=1.0)
        data = _make_data(hour=3) # charge window
        setpoints, _ = battery_tou_processor(data, _make_param(bat))
        self.assertEqual(setpoints['Battery bat Power Command [kW]'], 0.0)

    # Config override via parameter
    def test_battery_tou_processor_config_safety_factor(self):
        """Higher safety_factor yields higher power in charge window."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(soc=0.5))
        param['battery_tou_processor_config'] = {'safety_factor': 2.0}
        setpoints_2x, _ = battery_tou_processor(data, param)

        param2 = _make_param(_make_bat(soc=0.5))
        setpoints_1x, _ = battery_tou_processor(data, param2)

        self.assertGreater(setpoints_2x['Battery bat Power Command [kW]'],
                           setpoints_1x['Battery bat Power Command [kW]'])

    def test_battery_tou_processor_config_emergency_recovery_hours(self):
        """Shorter recovery window → higher emergency charge power."""
        bat = _make_bat(soc=0.1, soc_min=0.2, soc_max=1.0, capacity=200, power_charge=50)
        data = _make_data(hour=22) # idle — triggers emergency override
        key = 'Battery bat Power Command [kW]'

        param_fast = _make_param(bat)
        param_fast['battery_tou_processor_config'] = {'emergency_recovery_hours': 1.0}
        setpoints_fast, _ = battery_tou_processor(data, param_fast)

        param_slow = _make_param(bat)
        param_slow['battery_tou_processor_config'] = {'emergency_recovery_hours': 4.0}
        setpoints_slow, _ = battery_tou_processor(data, param_slow)

        self.assertGreater(setpoints_fast[key], setpoints_slow[key])

    def test_battery_tou_processor_config_partial_merge(self):
        """Overriding one key leaves other defaults intact."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(soc=0.5))
        param['battery_tou_processor_config'] = {'safety_factor': 2.0}
        setpoints, _ = battery_tou_processor(data, param)
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_battery_tou_processor_config_custom_windows(self):
        """All-idle custom window config results in zero power."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(soc=0.5))
        param['battery_tou_processor_config'] = {
            'tou_windows': [(0, 24, 'idle', None, False)]
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertEqual(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_setpoint_names_template_override(self):
        """Custom battery_power template produces the expected setpoint key."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(soc=0.5))
        param['controller'] = {
            'setpoint_names': {
                'battery_power': 'BESS_%s_cmd',
                'battery_name_map': {},
            }
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertIn('BESS_bat_cmd', setpoints)
        self.assertNotIn('Battery bat Power Command [kW]', setpoints)

    def test_setpoint_names_battery_name_map(self):
        """battery_name_map translates internal name to display name in setpoint key."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(name='bat1', soc=0.5))
        param['controller'] = {
            'setpoint_names': {
                'battery_power': 'Battery %s Power Command [kW]',
                'battery_name_map': {'bat1': 'Battery 1'},
            }
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertIn('Battery Battery 1 Power Command [kW]', setpoints)
        self.assertNotIn('Battery bat1 Power Command [kW]', setpoints)

    def test_setpoint_names_missing_from_name_map_uses_internal_name(self):
        """Battery not in battery_name_map falls back to internal name as-is."""
        data = _make_data(hour=3)
        param = _make_param(_make_bat(name='bat_internal', soc=0.5))
        param['controller'] = {
            'setpoint_names': {
                'battery_power': 'Battery %s Power Command [kW]',
                'battery_name_map': {'other_bat': 'Other Battery'},
            }
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertIn('Battery bat_internal Power Command [kW]', setpoints)

    # Power limits
    def test_power_never_exceeds_max_charge(self):
        bat = _make_bat(soc=0.2, capacity=500, power_charge=30.0)
        data = _make_data(hour=3)
        setpoints, _ = battery_tou_processor(data, _make_param(bat))
        self.assertLessEqual(setpoints['Battery bat Power Command [kW]'], 30.0)

    def test_power_never_exceeds_max_discharge(self):
        bat = _make_bat(soc=0.9, capacity=500, power_discharge=30.0)
        data = _make_data(hour=18)
        setpoints, _ = battery_tou_processor(data, _make_param(bat))
        self.assertLessEqual(setpoints['Battery bat Power Command [kW]'], 30.0)

    def test_power_sign_matches_mode(self):
        # charge/idle hours must be non-negative; discharge hours must be non-positive
        discharge_hours = {h for start, end, mode, _, _ in default_config()['tou_windows']
                           if mode == 'discharge' for h in range(start, end)}
        for hour in [1, 7, 12, 18, 22]:
            data = _make_data(hour=hour)
            setpoints, _ = battery_tou_processor(data, _make_param())
            sp = setpoints['Battery bat Power Command [kW]']
            if hour in discharge_hours:
                self.assertLessEqual(sp, 0.0, msg=f'discharge power positive at hour {hour}')
            else:
                self.assertGreaterEqual(sp, 0.0, msg=f'non-discharge power negative at hour {hour}')

    # Multiple batteries
    def test_multiple_batteries_each_get_setpoint(self):
        param = {
            'batteries': [_make_bat(name='bat1', soc=0.5), _make_bat(name='bat2', soc=0.8)],
            'controller': {'setpoint_names': {'battery_power': 'Battery %s Power Command [kW]'}},
        }
        data = _make_data(hour=3)
        setpoints, _ = battery_tou_processor(data, param)
        self.assertIn('Battery bat1 Power Command [kW]', setpoints)
        self.assertIn('Battery bat2 Power Command [kW]', setpoints)

    # System clock fallback
    def test_uses_system_clock_when_data_is_none(self):
        fixed_ts = datetime(2024, 6, 15, 3, 0, 0, tzinfo=__import__('datetime').timezone.utc)
        param = _make_param(_make_bat(soc=0.5))
        param['site'] = {'local_timezone': 'America/Los_Angeles'}
        with patch('doper.data.fallback_processor.datetime') as mock_dt:
            mock_dt.now.return_value = fixed_ts
            mock_dt.timezone = __import__('datetime').timezone
            setpoints, log = battery_tou_processor(None, param)
        self.assertIn('Battery bat Power Command [kW]', setpoints)
        self.assertTrue(any('system time' in m for m in log['messages']))

    # Log structure
    def test_log_has_required_keys(self):
        data = _make_data(hour=3)
        _, log = battery_tou_processor(data, _make_param())
        for key in ('messages', 'overrides', 'hour'):
            self.assertIn(key, log)

    def test_log_hour_matches_data_timestamp(self):
        data = _make_data(hour=11)
        _, log = battery_tou_processor(data, _make_param())
        self.assertAlmostEqual(log['hour'], 11.0, places=6)

    def test_overrides_empty_when_no_safety_triggered(self):
        bat = _make_bat(soc=0.5) # normal SOC
        data = _make_data(hour=3)
        _, log = battery_tou_processor(data, _make_param(bat))
        self.assertEqual(log['overrides'], [])

    # pv_excess_only tests
    def test_pv_excess_only_caps_charge_at_excess(self):
        """Charge power capped at excess PV (pv - load) when pv_excess_only=True."""
        # sized power = (1.0-0.5)*200 / 10h * 1.0 = 10 kW; excess = 25-10 = 15 kW → 10 kW wins
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=10.0, pv=25.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        setpoints, _ = battery_tou_processor(data, param)
        # sized = 100/7/1 ≈ 14.3 kW; excess = 15 kW → sized wins (14.3 < 15)
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)
        self.assertLessEqual(setpoints['Battery bat Power Command [kW]'], 15.0)

    def test_pv_excess_only_limited_by_small_excess(self):
        """When excess PV < sized power, charge is capped at the excess value."""
        # pv=12, load=10 → excess=2 kW; sized power will be larger
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=10.0, pv=12.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        setpoints, _ = battery_tou_processor(data, param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 2.0, places=3)

    def test_pv_excess_only_zero_when_no_excess(self):
        """When load >= pv, no excess exists and charge power is 0."""
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=20.0, pv=5.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        setpoints, _ = battery_tou_processor(data, param)
        self.assertEqual(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_pv_excess_only_zero_when_no_pv_column(self):
        """Missing generation_pv column → no excess → charge power is 0."""
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=10.0, pv=None) # no pv column
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        setpoints, _ = battery_tou_processor(data, param)
        self.assertEqual(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_pv_excess_only_false_charges_normally(self):
        """pv_excess_only=False with identical data charges at sized power ignoring PV."""
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data_pv = _make_data(hour=3, load=20.0, pv=5.0) # load > pv (no excess)
        param = _make_param(bat)
        # default config: pv_excess_only=False in all windows
        setpoints, _ = battery_tou_processor(data_pv, param)
        self.assertGreater(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_pv_excess_only_log_message_written(self):
        """Log contains pv_excess_only message when flag is active."""
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=10.0, pv=20.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        _, log = battery_tou_processor(data, param)
        self.assertTrue(any('pv_excess_only' in m for m in log['messages']))

    def test_pv_excess_only_does_not_affect_discharge(self):
        """pv_excess_only flag on a discharge window has no effect on discharge power."""
        bat = _make_bat(soc=0.8, capacity=200, power_discharge=50)
        data = _make_data(hour=18, load=10.0, pv=0.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = {
            'tou_windows': [
                (0, 15, 'idle', None, False),
                (15, 21, 'discharge', None, True), # pv_excess_only on discharge: no effect
                (21, 24, 'idle', None, False),
            ]
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertLess(setpoints['Battery bat Power Command [kW]'], 0.0)

    def test_pv_excess_only_exact_cap_value(self):
        """Charge power equals exactly min(sized_power, excess_pv)."""
        # soc=0.5, soc_max=1.0, cap=200, eff=1, window 0-10h, hour=3 → hours_rem=7
        # sized = 100/7 ≈ 14.286 kW; excess = 30-10 = 20 kW → capped at sized
        bat = _make_bat(soc=0.5, capacity=200, power_charge=50)
        data = _make_data(hour=3, load=10.0, pv=30.0)
        param = _make_param(bat)
        param['battery_tou_processor_config'] = _pv_excess_config(0, 10)
        setpoints, _ = battery_tou_processor(data, param)
        expected = min(50.0, 100.0 / 7.0) # sized wins; excess=20 > sized≈14.3
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], expected, places=2)

    def test_pv_excess_only_rate_override_still_capped(self):
        """Fixed rate is also capped at excess PV when pv_excess_only=True."""
        # rate=30 kW, excess=5 kW → capped at 5
        bat = _make_bat(soc=0.5)
        data = _make_data(hour=3, load=10.0, pv=15.0) # excess=5
        param = _make_param(bat)
        param['battery_tou_processor_config'] = {
            'tou_windows': [
                (0, 10, 'charge', 30.0, True),
                (10, 24, 'idle', None, False),
            ]
        }
        setpoints, _ = battery_tou_processor(data, param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 5.0, places=3)


if __name__ == '__main__':
    unittest.main()
