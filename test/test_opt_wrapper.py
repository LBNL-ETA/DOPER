import json
import unittest

import doper.examples as example

from doper.opt_wrapper import DoperWrapper


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

    def test_objective_not_written_on_success_path(self):
        self.assertIsNone(self.wrapper.output["objective"], msg="objective should remain None on success path")

    def test_duration_nonzero(self):
        self.assertGreater(self.wrapper.output["duration"], 0, msg="duration should be > 0")


if __name__ == "__main__":
    unittest.main()