"""Unit tests for doper.data.setpoint_processor."""

import unittest
import pandas as pd
import numpy as np

from doper.data.setpoint_processor import (
    default_config,
    battery_setpoint_processor,
)


def _make_bat(name='bat', power_kw=10.0):
    """Helper: minimal battery parameter dict."""
    return {'name': name}

def _make_param(bat=None, battery_enabled=True, setpoint_names=None):
    """Helper: parameter dict with one battery and setpoint_names configured."""
    if bat is None:
        bat = _make_bat()
    param = {
        'system': {'battery': battery_enabled},
        'batteries': [bat],
        'controller': {
            'setpoint_names': setpoint_names or {
                'battery_power': 'Battery %s Power Command [kW]',
                'battery_name_map': {},
            }
        },
    }
    return param

def _make_df(bat_name='bat', power_kw=10.0, col_template='Battery %s Net Grid Power [kW]'):
    """Helper: single-row result DataFrame with net grid power column."""
    ts = pd.Timestamp('2019-01-01 08:00:00')
    col = col_template % bat_name
    return pd.DataFrame({col: [power_kw]}, index=[ts])


class TestDefaultConfig(unittest.TestCase):
    """Tests for default_config."""

    def test_returns_dict(self):
        self.assertIsInstance(default_config(), dict)

    def test_has_battery_col_key(self):
        self.assertIn('battery_net_grid_power_col', default_config())

    def test_has_setpoint_scale_key(self):
        self.assertIn('setpoint_scale', default_config())

    def test_battery_col_is_format_string(self):
        col = default_config()['battery_net_grid_power_col']
        self.assertIn('%s', col)

    def test_setpoint_scale_default_is_one(self):
        self.assertEqual(default_config()['setpoint_scale'], 1)


class TestBatterySetpointProcessorGuards(unittest.TestCase):
    """Guard / early-return cases."""

    def test_returns_empty_when_parameter_is_none(self):
        setpoints, log = battery_setpoint_processor(_make_df(), None)
        self.assertEqual(setpoints, {})

    def test_returns_empty_when_battery_disabled(self):
        param = _make_param(battery_enabled=False)
        setpoints, log = battery_setpoint_processor(_make_df(), param)
        self.assertEqual(setpoints, {})
        self.assertEqual(log['warnings'], [])

    def test_returns_empty_when_no_batteries_key(self):
        param = {'system': {'battery': True}, 'controller': {'setpoint_names': {}}}
        setpoints, log = battery_setpoint_processor(_make_df(), param)
        self.assertEqual(setpoints, {})

    def test_returns_empty_when_batteries_list_empty(self):
        param = _make_param()
        param['batteries'] = []
        setpoints, log = battery_setpoint_processor(_make_df(), param)
        self.assertEqual(setpoints, {})

    def test_returns_empty_when_df_is_none(self):
        setpoints, log = battery_setpoint_processor(None, _make_param())
        self.assertEqual(setpoints, {})
        self.assertTrue(len(log['warnings']) > 0)

    def test_returns_empty_when_df_is_empty(self):
        setpoints, log = battery_setpoint_processor(pd.DataFrame(), _make_param())
        self.assertEqual(setpoints, {})
        self.assertTrue(len(log['warnings']) > 0)

    def test_returns_empty_when_battery_power_missing_from_setpoint_names(self):
        param = _make_param(setpoint_names={'battery_name_map': {}})
        setpoints, log = battery_setpoint_processor(_make_df(), param)
        self.assertEqual(setpoints, {})
        self.assertTrue(any('battery_power' in w for w in log['warnings']))

    def test_warns_when_source_column_missing(self):
        param = _make_param()
        df = pd.DataFrame({'other_col': [5.0]}, index=[pd.Timestamp('2019-01-01')])
        setpoints, log = battery_setpoint_processor(df, param)
        self.assertEqual(setpoints, {})
        self.assertTrue(len(log['warnings']) > 0)

    def test_warns_when_value_is_nan(self):
        param = _make_param()
        df = _make_df(power_kw=float('nan'))
        setpoints, log = battery_setpoint_processor(df, param)
        self.assertEqual(setpoints, {})
        self.assertTrue(len(log['warnings']) > 0)


class TestBatterySetpointProcessorNormal(unittest.TestCase):
    """Normal operation tests."""

    def test_returns_correct_setpoint_key(self):
        param = _make_param()
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=15.0), param)
        self.assertIn('Battery bat Power Command [kW]', setpoints)

    def test_setpoint_value_matches_df(self):
        param = _make_param()
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=12.5), param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 12.5, places=3)

    def test_negative_power_is_preserved(self):
        """Discharge (negative net power) must pass through unchanged."""
        param = _make_param()
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=-20.0), param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], -20.0, places=3)

    def test_zero_power_is_preserved(self):
        param = _make_param()
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=0.0), param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 0.0, places=3)

    def test_uses_first_row_of_dataframe(self):
        """Only the first timestep value should be used."""
        param = _make_param()
        ts1 = pd.Timestamp('2019-01-01 08:00:00')
        ts2 = pd.Timestamp('2019-01-01 09:00:00')
        col = 'Battery bat Net Grid Power [kW]'
        df = pd.DataFrame({col: [7.0, 99.0]}, index=[ts1, ts2])
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 7.0, places=3)

    def test_value_is_rounded_to_three_decimal_places(self):
        param = _make_param()
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=3.14159265), param)
        val = setpoints['Battery bat Power Command [kW]']
        self.assertEqual(val, round(val, 3))

    def test_log_has_required_keys(self):
        param = _make_param()
        _, log = battery_setpoint_processor(_make_df(), param)
        self.assertIn('messages', log)
        self.assertIn('warnings', log)

    def test_log_message_contains_battery_name(self):
        param = _make_param(_make_bat(name='libat01'))
        df = _make_df(bat_name='libat01', power_kw=5.0)
        _, log = battery_setpoint_processor(df, param)
        self.assertTrue(any('libat01' in m for m in log['messages']))


class TestBatterySetpointProcessorSetpointNames(unittest.TestCase):
    """Tests for setpoint_names / battery_name_map resolution."""

    def test_custom_template_produces_correct_key(self):
        param = _make_param(setpoint_names={
            'battery_power': 'BESS_%s_cmd',
            'battery_name_map': {},
        })
        setpoints, _ = battery_setpoint_processor(_make_df(), param)
        self.assertIn('BESS_bat_cmd', setpoints)
        self.assertNotIn('Battery bat Power Command [kW]', setpoints)

    def test_battery_name_map_translates_key(self):
        param = _make_param(_make_bat(name='bat1'), setpoint_names={
            'battery_power': 'Battery %s Power Command [kW]',
            'battery_name_map': {'bat1': 'Main BESS'},
        })
        df = _make_df(bat_name='bat1', power_kw=10.0)
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertIn('Battery Main BESS Power Command [kW]', setpoints)
        self.assertNotIn('Battery bat1 Power Command [kW]', setpoints)

    def test_battery_not_in_name_map_uses_internal_name(self):
        param = _make_param(_make_bat(name='bat_internal'), setpoint_names={
            'battery_power': 'Battery %s Power Command [kW]',
            'battery_name_map': {'other_bat': 'Other'},
        })
        df = _make_df(bat_name='bat_internal', power_kw=5.0)
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertIn('Battery bat_internal Power Command [kW]', setpoints)

    def test_empty_battery_name_map_uses_internal_name(self):
        param = _make_param(_make_bat(name='libat01'), setpoint_names={
            'battery_power': 'Battery %s Power Command [kW]',
            'battery_name_map': {},
        })
        df = _make_df(bat_name='libat01', power_kw=8.0)
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertIn('Battery libat01 Power Command [kW]', setpoints)


class TestBatterySetpointProcessorConfig(unittest.TestCase):
    """Tests for setpoint_processor_config overrides."""

    def test_setpoint_scale_applied(self):
        param = _make_param()
        param['setpoint_processor_config'] = {'setpoint_scale': 2}
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=10.0), param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 20.0, places=3)

    def test_custom_source_column_template(self):
        param = _make_param()
        param['setpoint_processor_config'] = {
            'battery_net_grid_power_col': 'Custom %s Col'
        }
        ts = pd.Timestamp('2019-01-01 08:00:00')
        df = pd.DataFrame({'Custom bat Col': [7.5]}, index=[ts])
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 7.5, places=3)

    def test_partial_config_override_preserves_defaults(self):
        """Overriding setpoint_scale should not remove battery_net_grid_power_col."""
        param = _make_param()
        param['setpoint_processor_config'] = {'setpoint_scale': 0.5}
        setpoints, _ = battery_setpoint_processor(_make_df(power_kw=10.0), param)
        self.assertAlmostEqual(setpoints['Battery bat Power Command [kW]'], 5.0, places=3)


class TestBatterySetpointProcessorMultipleBatteries(unittest.TestCase):
    """Tests with multiple batteries."""

    def test_each_battery_gets_setpoint(self):
        param = _make_param()
        param['batteries'] = [_make_bat('bat1'), _make_bat('bat2')]
        ts = pd.Timestamp('2019-01-01 08:00:00')
        df = pd.DataFrame({
            'Battery bat1 Net Grid Power [kW]': [10.0],
            'Battery bat2 Net Grid Power [kW]': [20.0],
        }, index=[ts])
        setpoints, _ = battery_setpoint_processor(df, param)
        self.assertIn('Battery bat1 Power Command [kW]', setpoints)
        self.assertIn('Battery bat2 Power Command [kW]', setpoints)
        self.assertAlmostEqual(setpoints['Battery bat1 Power Command [kW]'], 10.0, places=3)
        self.assertAlmostEqual(setpoints['Battery bat2 Power Command [kW]'], 20.0, places=3)

    def test_missing_column_for_one_battery_does_not_block_others(self):
        param = _make_param()
        param['batteries'] = [_make_bat('bat1'), _make_bat('bat2')]
        ts = pd.Timestamp('2019-01-01 08:00:00')
        # Only bat2 column present
        df = pd.DataFrame({'Battery bat2 Net Grid Power [kW]': [5.0]}, index=[ts])
        setpoints, log = battery_setpoint_processor(df, param)
        self.assertIn('Battery bat2 Power Command [kW]', setpoints)
        self.assertNotIn('Battery bat1 Power Command [kW]', setpoints)
        self.assertTrue(len(log['warnings']) > 0)


if __name__ == '__main__':
    unittest.main()