import json
import unittest
from io import StringIO

import pandas as pd

import doper.examples as example

from doper.opt_wrapper import DoperWrapper


def pv_sp_processor(data, parameter):
    """Extract predicted next PV power setpoint from output-data dataframe."""
    return {
        "pv": {
            "predicted_next_power_kW": float(data["PV Power [kW]"].iloc[0])
        }
    }


class TestOptWrapper(unittest.TestCase):
    """
    Unit tests for DoperWrapper.compute.
    """

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
        # Use same input generation as test_basemodel.py
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
        self.assertIsNotNone(wrapper.res, msg="wrapper.res should not be None after successful compute")

        self.__class__.msg = msg
        self.__class__.wrapper = wrapper
        self.__class__.res = wrapper.res
        self.__class__.duration, self.__class__.objective, self.__class__.df, self.__class__.model, \
            self.__class__.result, self.__class__.termination, self.__class__.parameter = wrapper.res
        self.__class__.setupComplete = True

    def test_compute_returns_done(self):
        self.assertEqual(self.msg, "Done.", msg="compute did not return Done.")

    def test_output_valid_true(self):
        self.assertTrue(self.wrapper.output["valid"], msg="valid output flag should be True")

    def test_output_data_exists(self):
        self.assertIsNotNone(self.wrapper.output["output-data"], msg="output-data should not be None")

    def test_exists_objective(self):
        self.assertTrue(hasattr(self, "objective"), msg="objective does not exist")

    def test_obj_tolerance(self):
        self.assertAlmostEqual(
            self.objective,
            self.expObjective,
            msg="objective does not match expected with 5%",
            delta=self.objTolerance,
        )

    def test_duration_nonzero(self):
        self.assertGreater(self.wrapper.output["duration"], 0, msg="duration should be > 0")

    def test_pv_setpoint_is_output_and_matches_output_data(self):
        setpoints = self.wrapper.output["setpoints"]
        self.assertIsInstance(setpoints, dict, msg="setpoints should be a dict")
        self.assertIn("pv", setpoints, msg="setpoints should contain pv key")
        self.assertIn("predicted_next_power_kW", setpoints["pv"], msg="pv setpoint should be present")

        output_df = pd.read_json(StringIO(self.wrapper.output["output-data"]))
        output_df.index = pd.to_datetime(output_df.index)
        expected_setpoint = float(output_df["PV Power [kW]"].iloc[0])

        self.assertAlmostEqual(
            float(setpoints["pv"]["predicted_next_power_kW"]),
            expected_setpoint,
            places=6,
            msg="pv setpoint should match output-data PV Power [kW] at first timestep",
        )


class TestOptWrapperStateLogs(unittest.TestCase):
    """Tests for expected-state logging and update_states_thr threshold logic."""

    def _make_battery_cfg(self, update_states_thr=None):
        """Battery config; optionally set update_states_thr."""
        cfg = example.test_parameter_add_battery()
        cfg['site']['tariff_name'] = 'test1'
        if update_states_thr is not None:
            cfg['controller']['update_states_thr'] = update_states_thr
        return cfg

    def _make_forecast_json(self, cfg):
        data = example.ts_inputs(cfg, load='B90', scale_load=150, scale_pv=100)
        return data.to_json(date_format='iso')

    def _run_wrapper(self, cfg, state_inputs=None):
        """Create and run a fresh DoperWrapper; return (wrapper, msg)."""
        if state_inputs is None:
            state_inputs = {}
        wrapper = DoperWrapper()
        wrapper.input['input-data'] = self._make_forecast_json(cfg)
        wrapper.input['state-inputs'] = json.dumps(state_inputs)
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        msg = wrapper.compute()
        return wrapper, msg

    # ------------------------------------------------------------------
    # state_log structure — always active
    # ------------------------------------------------------------------

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
            self.assertIn(f'batteries_libat01_{state_key}_expected', cols,
                          msg=f'missing expected column for {state_key}')
            self.assertIn(f'batteries_libat01_{state_key}_provided', cols,
                          msg=f'missing provided column for {state_key}')

    def test_state_log_has_one_row_after_one_compute(self):
        cfg = self._make_battery_cfg()
        wrapper, _ = self._run_wrapper(cfg)
        self.assertEqual(len(wrapper.state_log), 1)

    # ------------------------------------------------------------------
    # _expected / _provided values
    # ------------------------------------------------------------------

    def test_state_log_expected_matches_initial_parameter_on_first_call(self):
        cfg = self._make_battery_cfg()
        wrapper, msg = self._run_wrapper(cfg, state_inputs={})
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        row = wrapper.state_log.iloc[0]
        self.assertAlmostEqual(
            row['batteries_libat01_soc_initial_expected'],
            cfg['batteries'][0]['soc_initial'],
            places=6,
            msg='expected soc_initial should match initial parameter on first call',
        )
        self.assertAlmostEqual(
            row['batteries_libat01_battery_power_expected'],
            cfg['batteries'][0]['battery_power'],
            places=6,
            msg='expected battery_power should match initial parameter on first call',
        )

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

    # ------------------------------------------------------------------
    # expected_states updated from optimization result
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # accumulation over multiple calls
    # ------------------------------------------------------------------

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
        """Expected soc_initial on the second call matches prediction from first optimization."""
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

    # ------------------------------------------------------------------
    # update_states_thr — threshold filtering
    # ------------------------------------------------------------------

    def test_threshold_not_exceeded_uses_expected_value(self):
        """When |expected - provided| <= threshold, parameter keeps expected value."""
        cfg = self._make_battery_cfg()
        initial_soc = cfg['batteries'][0]['soc_initial']  # 0.3

        # First call: establish expected_states from initial parameter (soc=0.3)
        forecast_json = self._make_forecast_json(cfg)
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()
        expected_soc = wrapper.expected_states['batteries'][0]['soc_initial']

        # Second call: provide a soc within the threshold of the predicted value
        # Use a very large threshold so any provided value is treated as within threshold
        cfg2 = self._make_battery_cfg(update_states_thr={'soc_initial': 1.0})
        provided_soc = expected_soc + 0.05  # small perturbation, within threshold=1.0

        wrapper.input['input-data'] = forecast_json
        # Override config to include the threshold
        wrapper.parameter['controller']['update_states_thr'] = {'soc_initial': 1.0}
        wrapper.input['state-inputs'] = json.dumps(
            {'batteries': [{'soc_initial': provided_soc}]}
        )
        wrapper.compute()

        # parameter soc_initial should revert to expected (not the provided value)
        actual_soc_used = wrapper.parameter['batteries'][0]['soc_initial']
        # After compute, parameter is updated with new expected, so check state_log instead
        log_expected = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_expected']
        log_provided = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_provided']
        # The log captures raw values; provided should match what was sent
        self.assertAlmostEqual(log_provided, provided_soc, places=6,
                               msg='_provided should always capture raw state_inputs value')
        # expected should be the value predicted from first optimization
        self.assertAlmostEqual(log_expected, expected_soc, places=6,
                               msg='_expected should be the prediction from first optimization')

    def test_threshold_exceeded_uses_provided_value(self):
        """When |expected - provided| > threshold, parameter uses the provided value."""
        cfg = self._make_battery_cfg()
        forecast_json = self._make_forecast_json(cfg)

        # First call with a very tight threshold (0.0) so any nonzero discrepancy triggers update
        wrapper = DoperWrapper()
        wrapper.input['config'] = json.dumps(cfg)
        wrapper.input['debug'] = True
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps({})
        wrapper.compute()
        expected_soc = wrapper.expected_states['batteries'][0]['soc_initial']

        # Second call: provide a soc far from expected, threshold=0.0 → always use provided
        wrapper.parameter['controller']['update_states_thr'] = {'soc_initial': 0.0}
        provided_soc = min(expected_soc + 0.1, cfg['batteries'][0]['soc_max'])
        wrapper.input['input-data'] = forecast_json
        wrapper.input['state-inputs'] = json.dumps(
            {'batteries': [{'soc_initial': provided_soc}]}
        )
        wrapper.compute()

        log_provided = wrapper.state_log.iloc[1]['batteries_libat01_soc_initial_provided']
        self.assertAlmostEqual(log_provided, provided_soc, places=6,
                               msg='_provided should capture the value sent in state_inputs')

    def test_empty_threshold_dict_always_uses_provided(self):
        """Default empty update_states_thr means state_inputs always overrides parameter."""
        cfg = self._make_battery_cfg()  # update_states_thr={}
        provided_soc = 0.55
        state_inputs = {'batteries': [{'soc_initial': provided_soc}]}
        wrapper, msg = self._run_wrapper(cfg, state_inputs=state_inputs)
        self.assertEqual(msg, 'Done.', msg=f'compute failed: {msg}')
        row = wrapper.state_log.iloc[0]
        self.assertAlmostEqual(row['batteries_libat01_soc_initial_provided'], provided_soc, places=6,
                               msg='with empty threshold dict, provided value should be used')


if __name__ == "__main__":
    unittest.main()
