import json
import unittest
from io import StringIO

import pandas as pd

import doper.examples as example

from doper.opt_wrapper import DoperWrapper
from doper.utility import apply_state_thresholds, update_nested_dict


def pv_sp_processor(data, parameter):
    """Extract predicted next PV power setpoint from output-data dataframe."""
    setpoints = {"pv": {"predicted_next_power_kW": float(data["PV Power [kW]"].iloc[0])}}
    log = {"rows": len(data)}
    return setpoints, log


def fallback_setpoints(data, parameter):
    """Fallback processor that returns a fixed setpoints dict."""
    setpoints = {"fallback": True, "data_is_none": data is None}
    log = {"data_is_none": data is None}
    return setpoints, log


class TestOptWrapper(unittest.TestCase):
    """Unit tests for DoperWrapper.compute."""

    setupComplete = False
    tolerance = 0.05

    def setUp(self):
        if not hasattr(self, "setupComplete"):
            self.runCompute()
        else:
            if self.setupComplete is False:
                self.runCompute()

        self.__class__.expObjective = 5500
        self.__class__.objTolerance = self.expObjective * self.tolerance

    def runCompute(self):
        cfg = example.test_default_parameter()
        cfg['site']['tariff_name'] = 'test1'
        cfg['controller']['sp_processor'] = {
            "module": "test.test_opt_wrapper",
            "name": "pv_sp_processor",
        }
        data = example.ts_inputs(cfg, load="B90", scale_load=150, scale_pv=100)
        forecast_json = data.to_json(date_format="iso")

        state_inputs = {'controller': {'printing': False}}

        wrapper = DoperWrapper()
        wrapper.input["input-data"] = forecast_json
        wrapper.input["state-inputs"] = json.dumps(state_inputs)
        wrapper.input["config"] = json.dumps(cfg)
        wrapper.input["timeout"] = None
        wrapper.input["debug"] = True

        msg = wrapper.compute()
        self.assertEqual(msg, "Done.", msg=f"compute failed: {msg}")
        self.assertIsNotNone(wrapper.res)

        self.__class__.msg = msg
        self.__class__.wrapper = wrapper
        self.__class__.res = wrapper.res
        self.__class__.duration, self.__class__.objective, self.__class__.df, self.__class__.model, \
            self.__class__.result, self.__class__.termination, self.__class__.parameter = wrapper.res
        self.__class__.setupComplete = True

    def test_compute_returns_done(self):
        self.assertEqual(self.msg, "Done.")

    def test_output_valid_true(self):
        self.assertTrue(self.wrapper.output["valid"])

    def test_output_data_exists(self):
        self.assertIsNotNone(self.wrapper.output["output-data"])

    def test_exists_objective(self):
        self.assertTrue(hasattr(self, "objective"))

    def test_obj_tolerance(self):
        self.assertAlmostEqual(self.objective, self.expObjective,
                               delta=self.objTolerance, msg="objective outside 5% tolerance")

    def test_duration_nonzero(self):
        self.assertGreater(self.wrapper.output["duration"], 0)

    def test_pv_setpoint_is_output_and_matches_output_data(self):
        setpoints = self.wrapper.output["setpoints"]
        self.assertIsInstance(setpoints, dict)
        self.assertIn("pv", setpoints)
        self.assertIn("predicted_next_power_kW", setpoints["pv"])

        output_df = pd.read_json(StringIO(self.wrapper.output["output-data"]))
        output_df.index = pd.to_datetime(output_df.index)
        expected_setpoint = float(output_df["PV Power [kW]"].iloc[0])

        self.assertAlmostEqual(float(setpoints["pv"]["predicted_next_power_kW"]),
                               expected_setpoint, places=6)

    def test_ext_logs_contains_sp_processor_module(self):
        ext_logs = json.loads(self.wrapper.output["ext-logs"])
        self.assertIn("test.test_opt_wrapper", ext_logs)
        self.assertIn("rows", ext_logs["test.test_opt_wrapper"])

    def test_ext_logs_is_json_string(self):
        raw = self.wrapper.output["ext-logs"]
        self.assertIsInstance(raw, str)
        parsed = json.loads(raw)
        self.assertIsInstance(parsed, dict)


class TestOptWrapperStateLogs(unittest.TestCase):
    """Tests for expected-state logging and update_states_thr threshold logic."""

    def _make_battery_cfg(self, update_states_thr=None):
        cfg = example.test_parameter_add_battery()
        cfg['site']['tariff_name'] = 'test1'
        if update_states_thr is not None:
            cfg['controller']['update_states_thr'] = update_states_thr
        return cfg

    def _make_forecast_json(self, cfg):
        data = example.ts_inputs(cfg, load='B90', scale_load=150, scale_pv=100)
        return data.to_json(date_format='iso')

    def _run_wrapper(self, cfg, state_inputs=None):
        if state_inputs is None:
            state_inputs = {}
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = self._make_forecast_json(cfg)
        wrapper.input['state-inputs'] = json.dumps(state_inputs)
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        msg = wrapper.compute()
        return wrapper, msg

    # --- state_log structure ---

    def test_state_log_is_dataframe_after_compute(self):
        cfg = self._make_battery_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        self.assertIsInstance(wrapper.state_log, pd.DataFrame)

    def test_state_log_has_expected_and_provided_columns(self):
        cfg = self._make_battery_cfg()
        wrapper, _ = self._run_wrapper(cfg)
        cols = list(wrapper.state_log.columns)
        for state_key in ('soc_initial', 'battery_power'):
            self.assertIn(f'batteries_libat01_{state_key}_expected', cols)
            self.assertIn(f'batteries_libat01_{state_key}_provided', cols)

    def test_state_log_has_one_row_after_one_compute(self):
        cfg = self._make_battery_cfg()
        wrapper, _ = self._run_wrapper(cfg)
        self.assertEqual(len(wrapper.state_log), 1)

    # --- expected / provided values ---

    def test_state_log_expected_matches_initial_parameter_on_first_call(self):
        cfg = self._make_battery_cfg()
        wrapper, msg = self._run_wrapper(cfg, state_inputs={})
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        row = wrapper.state_log.iloc[0]
        self.assertAlmostEqual(row['batteries_libat01_soc_initial_expected'],
                               cfg['batteries'][0]['soc_initial'], places=6)
        self.assertAlmostEqual(row['batteries_libat01_battery_power_expected'],
                               cfg['batteries'][0]['battery_power'], places=6)

    def test_state_log_provided_is_none_when_not_in_state_inputs(self):
        cfg = self._make_battery_cfg()
        wrapper, _ = self._run_wrapper(cfg, state_inputs={})
        row = wrapper.state_log.iloc[0]
        self.assertIsNone(row['batteries_libat01_soc_initial_provided'])
        self.assertIsNone(row['batteries_libat01_battery_power_provided'])

    def test_state_log_provided_matches_state_inputs_values(self):
        cfg = self._make_battery_cfg()
        provided_soc, provided_power = 0.55, 5.0
        state_inputs = {'batteries': [{'soc_initial': provided_soc, 'battery_power': provided_power}]}
        wrapper, msg = self._run_wrapper(cfg, state_inputs=state_inputs)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        row = wrapper.state_log.iloc[0]
        self.assertAlmostEqual(row['batteries_libat01_soc_initial_provided'], provided_soc, places=6)
        self.assertAlmostEqual(row['batteries_libat01_battery_power_provided'], provided_power, places=6)

    # --- expected_states from optimization ---

    def test_expected_states_updated_after_successful_optimization(self):
        cfg = self._make_battery_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        self.assertIsNotNone(wrapper.expected_states)
        bat = wrapper.expected_states['batteries'][0]
        self.assertIn('soc_initial', bat)
        self.assertIn('battery_power', bat)

    def test_expected_states_soc_within_battery_bounds(self):
        cfg = self._make_battery_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        bat_cfg = cfg['batteries'][0]
        soc_next = wrapper.expected_states['batteries'][0]['soc_initial']
        self.assertGreaterEqual(soc_next, bat_cfg['soc_min'] - 1e-6)
        self.assertLessEqual(soc_next, bat_cfg['soc_max'] + 1e-6)

    # --- accumulation over multiple calls ---

    def test_state_log_accumulates_rows_over_multiple_computes(self):
        cfg = self._make_battery_cfg()
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        for call_idx in range(3):
            wrapper.input['input-data'] = forecast_json
            wrapper.input['state-inputs'] = json.dumps({})
            msg = wrapper.compute()
            self.assertEqual(msg, 'Done.', msg=f'compute {call_idx} failed: {msg}')
        self.assertEqual(len(wrapper.state_log), 3)

    def test_second_call_expected_reflects_optimization_prediction(self):
        cfg = self._make_battery_cfg()
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True

        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()
        expected_after_first = wrapper.expected_states['batteries'][0]['soc_initial']

        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()

        second_row_expected = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_expected']
        self.assertAlmostEqual(second_row_expected, expected_after_first, places=6)

    # --- update_states_thr threshold filtering ---

    def test_threshold_not_exceeded_uses_expected_value(self):
        """When |expected - provided| <= threshold, parameter reverts to expected."""
        cfg = self._make_battery_cfg()
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()
        expected_soc = wrapper.expected_states['batteries'][0]['soc_initial']

        provided_soc = expected_soc + 0.05
        wrapper.parameter['controller']['update_states_thr'] = {'soc_initial': 1.0}
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({'batteries': [{'soc_initial': provided_soc}]})
        wrapper.compute()

        log_expected = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_expected']
        log_provided = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_provided']
        self.assertAlmostEqual(log_provided, provided_soc, places=6)
        self.assertAlmostEqual(log_expected, expected_soc, places=6)

    def test_threshold_exceeded_uses_provided_value(self):
        """When |expected - provided| > threshold, provided value is kept."""
        cfg = self._make_battery_cfg()
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()
        expected_soc = wrapper.expected_states['batteries'][0]['soc_initial']

        wrapper.parameter['controller']['update_states_thr'] = {'soc_initial': 0.0}
        provided_soc = min(expected_soc + 0.1, cfg['batteries'][0]['soc_max'])
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({'batteries': [{'soc_initial': provided_soc}]})
        wrapper.compute()

        log_provided = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_provided']
        self.assertAlmostEqual(log_provided, provided_soc, places=6)

    def test_empty_threshold_dict_always_uses_provided(self):
        """Empty update_states_thr means state_inputs always overrides parameter."""
        cfg = self._make_battery_cfg()
        provided_soc = 0.55
        state_inputs = {'batteries': [{'soc_initial': provided_soc}]}
        wrapper, msg = self._run_wrapper(cfg, state_inputs=state_inputs)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        row = wrapper.state_log.iloc[0]
        self.assertAlmostEqual(row['batteries_libat01_soc_initial_provided'], provided_soc, places=6)

    # --- soc_initial boundary and invalid-value overrides (direct unit tests) ---

    def test_soc_below_soc_min_keeps_provided_despite_threshold(self):
        """When provided soc_initial <= soc_min, provided value is kept despite threshold."""
        soc_min, soc_max, expected_soc = 0.2, 1.0, 0.5
        provided_soc = soc_min
        parameter = {'batteries': [{'soc_initial': expected_soc, 'soc_min': soc_min, 'soc_max': soc_max}]}
        expected_states = {'batteries': [{'soc_initial': expected_soc}]}
        state_inputs = {'batteries': [{'soc_initial': provided_soc}]}

        update_nested_dict(parameter, state_inputs)
        apply_state_thresholds(parameter, expected_states, state_inputs,
                               update_states_thr={'soc_initial': 1.0})

        self.assertAlmostEqual(parameter['batteries'][0]['soc_initial'], provided_soc, places=6,
                               msg='soc at soc_min should bypass threshold and keep provided value')

    def test_soc_at_soc_max_keeps_provided_despite_threshold(self):
        """When provided soc_initial >= soc_max, provided value is kept despite threshold."""
        soc_min, soc_max, expected_soc = 0.2, 1.0, 0.5
        provided_soc = soc_max
        parameter = {'batteries': [{'soc_initial': expected_soc, 'soc_min': soc_min, 'soc_max': soc_max}]}
        expected_states = {'batteries': [{'soc_initial': expected_soc}]}
        state_inputs = {'batteries': [{'soc_initial': provided_soc}]}

        update_nested_dict(parameter, state_inputs)
        apply_state_thresholds(parameter, expected_states, state_inputs,
                               update_states_thr={'soc_initial': 1.0})

        self.assertAlmostEqual(parameter['batteries'][0]['soc_initial'], provided_soc, places=6,
                               msg='soc at soc_max should bypass threshold and keep provided value')

    def test_negative_soc_uses_expected_value(self):
        """When provided soc_initial < 0 (invalid), expected value is used instead."""
        soc_min, soc_max, expected_soc = 0.2, 1.0, 0.5
        parameter = {'batteries': [{'soc_initial': expected_soc, 'soc_min': soc_min, 'soc_max': soc_max}]}
        expected_states = {'batteries': [{'soc_initial': expected_soc}]}
        state_inputs = {'batteries': [{'soc_initial': -0.1}]}

        update_nested_dict(parameter, state_inputs)
        apply_state_thresholds(parameter, expected_states, state_inputs,
                               update_states_thr={'soc_initial': 0.0})

        self.assertAlmostEqual(parameter['batteries'][0]['soc_initial'], expected_soc, places=6,
                               msg='negative soc_initial should be rejected; expected value used')


class TestOptWrapperFallbackProcessor(unittest.TestCase):
    """Tests for fb_processor fallback behaviour."""

    def _base_cfg(self):
        cfg = example.test_default_parameter()
        cfg['site']['tariff_name'] = 'test1'
        return cfg

    def _make_forecast_json(self, cfg):
        data = example.ts_inputs(cfg, load='B90', scale_load=150, scale_pv=100)
        return data.to_json(date_format='iso')

    def _run_wrapper(self, cfg, state_inputs=None, forecast_json=None):
        if state_inputs is None:
            state_inputs = {}
        if forecast_json is None:
            forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps(state_inputs)
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        msg = wrapper.compute()
        return wrapper, msg

    # --- fb_processor not configured (default None) ---

    def test_fb_processor_none_by_default(self):
        """fb_processor attribute is None when not configured."""
        cfg = self._base_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.')
        self.assertIsNone(wrapper.fb_processor)

    def test_setpoints_empty_when_no_fb_processor_and_success(self):
        """setpoints output is {} on success when no sp_processor or fb_processor configured."""
        cfg = self._base_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.')
        self.assertEqual(wrapper.output['setpoints'], {})

    # --- fb_processor called on optimization failure ---

    def test_fb_processor_called_when_bad_input_data(self):
        """fb_processor is invoked when input data is missing on a subsequent call (msg is set).

        The fb_processor is resolved during the first successful compute(); a later call that
        fails before or during optimization still triggers the fallback.
        """
        cfg = self._base_cfg()
        cfg['controller']['fb_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'fallback_setpoints',
        }
        forecast_json = self._make_forecast_json(cfg)

        # first call succeeds → initialises fb_processor
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        msg1 = wrapper.compute()
        self.assertEqual(msg1, 'Done.', msg=f'first compute failed: {msg1}')

        # second call with missing input-data → msg set → fallback fires
        wrapper.input['input-data'] = None
        msg2 = wrapper.compute()

        self.assertNotEqual(msg2, 'Done.')
        setpoints = wrapper.output['setpoints']
        self.assertIsInstance(setpoints, dict)
        self.assertTrue(setpoints.get('fallback'))

    def test_fb_processor_receives_none_data_on_failure(self):
        """fb_processor receives data=None when compute fails after initialisation."""
        cfg = self._base_cfg()
        cfg['controller']['fb_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'fallback_setpoints',
        }
        forecast_json = self._make_forecast_json(cfg)

        # first call succeeds → initialises fb_processor
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.compute()

        # second call with missing input-data → data stays None
        wrapper.input['input-data'] = None
        wrapper.compute()

        setpoints = wrapper.output['setpoints']
        self.assertTrue(setpoints.get('data_is_none'))

    # --- fb_processor NOT called on success ---

    def test_fb_processor_not_called_on_success(self):
        """When optimization succeeds, fb_processor must NOT overwrite sp_processor setpoints."""
        cfg = self._base_cfg()
        cfg['controller']['sp_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'pv_sp_processor',
        }
        cfg['controller']['fb_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'fallback_setpoints',
        }
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.')
        setpoints = wrapper.output['setpoints']
        self.assertIn('pv', setpoints)
        self.assertNotIn('fallback', setpoints)

    def test_ext_logs_contains_fb_processor_module_on_failure(self):
        """ext-logs has fb_processor module key when fallback fires."""
        cfg = self._base_cfg()
        cfg['controller']['fb_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'fallback_setpoints',
        }
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.compute()
        # second call fails → fb_processor fires
        wrapper.input['input-data'] = None
        wrapper.compute()

        ext_logs = json.loads(wrapper.output['ext-logs'])
        self.assertIn('test.test_opt_wrapper', ext_logs)

    def test_ext_logs_no_custom_processors(self):
        """ext-logs contains only the default sp_processor when no custom processors configured."""
        cfg = self._base_cfg()
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.')
        ext_logs = json.loads(wrapper.output['ext-logs'])
        # default sp_processor (battery_setpoint_processor) is always configured; no custom modules
        self.assertNotIn('test.test_opt_wrapper', ext_logs)

    # --- fb_processor initialised same way as sp_processor ---

    def test_fb_processor_attribute_set_after_init(self):
        """After first compute, fb_processor attribute is a callable."""
        cfg = self._base_cfg()
        cfg['controller']['fb_processor'] = {
            'module': 'test.test_opt_wrapper',
            'name': 'fallback_setpoints',
        }
        wrapper, msg = self._run_wrapper(cfg)
        self.assertEqual(msg, 'Done.')
        self.assertTrue(callable(wrapper.fb_processor))

    def test_fb_processor_invalid_spec_raises_on_first_compute(self):
        """An invalid fb_processor spec causes compute to return an error message."""
        cfg = self._base_cfg()
        cfg['controller']['fb_processor'] = {
            'module': 'nonexistent.module',
            'name': 'some_func',
        }
        wrapper, msg = self._run_wrapper(cfg)
        self.assertNotEqual(msg, 'Done.')

    # --- battery_tou_processor as actual fb_processor ---

    def test_battery_tou_processor_as_fb_processor_fires_on_failure(self):
        """battery_tou_processor produces battery power setpoints when fallback fires."""
        cfg = example.test_parameter_add_battery()
        cfg['site']['tariff_name'] = 'test1'
        cfg['controller']['fb_processor'] = {
            'module': 'doper.data.fallback_processor',
            'name': 'battery_tou_processor',
        }
        forecast_json = self._make_forecast_json(cfg)

        # first call succeeds → initialises fb_processor
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        msg1 = wrapper.compute()
        self.assertEqual(msg1, 'Done.', msg=f'first compute failed: {msg1}')

        # second call fails → battery_tou_processor fires
        wrapper.input['input-data'] = None
        wrapper.compute()

        setpoints = wrapper.output['setpoints']
        key = 'Battery libat01 Power Command [kW]'
        self.assertIn(key, setpoints)
        self.assertIsInstance(setpoints[key], float)

    def test_battery_tou_processor_ext_log_contains_hour(self):
        """ext-logs from battery_tou_processor contain the hour field."""
        cfg = example.test_parameter_add_battery()
        cfg['site']['tariff_name'] = 'test1'
        cfg['controller']['fb_processor'] = {
            'module': 'doper.data.fallback_processor',
            'name': 'battery_tou_processor',
        }
        forecast_json = self._make_forecast_json(cfg)

        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.compute()

        wrapper.input['input-data'] = None
        wrapper.compute()

        ext_logs = json.loads(wrapper.output['ext-logs'])
        self.assertIn('doper.data.fallback_processor', ext_logs)
        log = ext_logs['doper.data.fallback_processor']
        self.assertIn('hour', log)

    def test_battery_tou_processor_config_via_parameter(self):
        """battery_tou_processor_config in parameter overrides TOU schedule through wrapper."""
        cfg = example.test_parameter_add_battery()
        cfg['site']['tariff_name'] = 'test1'
        cfg['controller']['fb_processor'] = {
            'module': 'doper.data.fallback_processor',
            'name': 'battery_tou_processor',
        }
        # Force a fixed discharge rate regardless of hour
        cfg['battery_tou_processor_config'] = {
            'tou_windows': [(0, 24, 'discharge', 10.0)]
        }
        forecast_json = self._make_forecast_json(cfg)

        wrapper = DoperWrapper()
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.compute()

        wrapper.input['input-data'] = None
        wrapper.compute()

        setpoints = wrapper.output['setpoints']
        self.assertAlmostEqual(setpoints['Battery libat01 Power Command [kW]'], 10.0, places=3)


if __name__ == "__main__":
    unittest.main()
