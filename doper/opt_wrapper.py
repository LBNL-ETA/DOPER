# Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019
# The Regents of the University of California, through Lawrence Berkeley
# National Laboratory (subject to receipt of any required approvals
# from the U.S. Dept. of Energy). All rights reserved.

""""Distributed Optimal and Predictive Energy Resources
Controller wrapper module.
"""

import os
import io
import time
import json
import traceback
import pandas as pd

from fmlc import eFMU

from .computetariff import compute_periods
from .data.tariff import get_tariff
from .utility import (update_nested_dict, resolve_wrapper_callable, build_objectives_dict,
                      init_expected_states, log_state_comparison,
                      apply_state_thresholds, update_expected_states_from_result)
from .wrapper import make_doper

class DoperWrapper(eFMU):
    """FMLC wrapper for DOPER."""

    def __init__(self):
        """Initialize wrapper."""
        self.input = {
            "input-data": None,
            "state-inputs": None,
            "config": None,
            "timeout": None,
            "debug": None,
        }
        self.output = {
            "output-data": None,
            "objectives": None,
            "opt-duration": None,
            "termination": None,
            "duration": None,
            "valid": None,
            "setpoints": None,
            "ext-logs": None,
        }
        self.init = True
        self.parameter = None
        self.res = None
        self.smart_der = None
        self.sp_processor = None
        self.fb_processor = None
        self.expected_states = None
        self.state_log = None

    def _to_forecast_df(self, fc):
        """Convert forecast JSON into dataframe."""
        df = pd.read_json(io.StringIO(fc))
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        return df

    def log_results(self):
        """Function to log opt inputs."""
        # make dir
        log_dir = os.path.join(self.parameter['controller']['log_dir'],
                               str(self.parameter['controller']['instance_id']))
        os.makedirs(log_dir, exist_ok=True)

        # log
        fname = str(self.data.index[0]).replace(' ', '').replace(':', '')
        with open(os.path.join(log_dir, fname+'.txt'), 'w', encoding='utf8') as f:
            json.dump(self.parameter, f)
        self.data.to_csv(os.path.join(log_dir, fname+'.csv'))

    def compute(self):
        """Main compute."""
        st = time.time()
        msg = ""
        data = None
        objective = None
        objectives = {'total': None}
        duration = None
        termination = None
        df = None
        model = None
        setpoints = {}
        ext_logs = {}

        msg += self.check_data(self.input["input-data"], True)

        if not msg:
            msg += self.check_data(self.input["state-inputs"], True)

        try:
            if not msg:
                if self.init:

                    # load config
                    if self.input["config"]:
                        cfg = json.loads(self.input["config"])

                    # init doper
                    self.smart_der = make_doper(cfg)
                    self.parameter = self.smart_der.parameter

                    # setpoint processor
                    self.sp_processor = resolve_wrapper_callable(
                        self.parameter['controller']['sp_processor'],
                        spec_name='sp_processor'
                    )

                    # fallback processor
                    self.fb_processor = resolve_wrapper_callable(
                        self.parameter['controller']['fb_processor'],
                        spec_name='fb_processor'
                    )

                    # initialize expected states from initial parameter
                    self.expected_states = init_expected_states(self.parameter)
                    self.state_log = pd.DataFrame()

                    self.init = False

                # parse state_inputs before applying (needed for comparison logging)
                state_inputs = json.loads(self.input["state-inputs"])

                # update states from state_inputs
                update_nested_dict(self.parameter, state_inputs)

                # apply per-state thresholds
                apply_state_thresholds(
                    self.parameter, self.expected_states, state_inputs,
                    self.parameter['controller']['update_states_thr']
                )

                # make inputs from forecast
                data = self._to_forecast_df(self.input["input-data"])
                tariff = get_tariff(self.parameter['site']["tariff_name"])
                data, _ = compute_periods(data, tariff, self.parameter)
                data = data.round(self.parameter['controller']['inputs_cutoff'])
                if pd.isnull(data).any().any():
                    msg += 'NAN values in MPC input. Index:' + \
                            data.index[pd.isnull(data).any().to_numpy().nonzero()[0]]
                self.data = data

                # log expected vs provided states
                self.state_log = log_state_comparison(
                    self.expected_states, state_inputs, self.parameter,
                    self.data.index[0], self.state_log
                )

                if not msg:
                    # run doper
                    printing = self.parameter['controller']['printing']
                    solver_options = self.parameter['controller']['solver_options']
                    self.res = self.smart_der.do_optimization(self.data,
                                                              parameter=self.parameter,
                                                              options=solver_options,
                                                              tee=printing,
                                                              print_error=printing)
                    duration, objective, df, model, result, termination, parameter = self.res
                    objectives = build_objectives_dict(model, self.parameter, objective)

                    # update expected states from optimization result for the next call
                    if objective:
                        self.expected_states = update_expected_states_from_result(
                            self.smart_der.model, self.parameter
                        )
                        # propagate expected states into parameter as defaults for next run
                        if self.expected_states is not None:
                            update_nested_dict(self.parameter, self.expected_states)

                # store outputs
                if isinstance(df, pd.DataFrame):
                    data = pd.concat([df, data], axis=1)

                    # process setpoints
                    if self.sp_processor:
                        setpoints, log = self.sp_processor(data, self.parameter)
                        ext_logs[self.sp_processor.__module__] = log

                    data = data.to_json()

                # Store if error or timeout
                opt_timeout = duration > self.parameter['controller']['log_overtime']
                if (not objective) or opt_timeout:
                    self.log_results()

        except Exception as e:
            msg += str(e)
            if self.input['debug']:
                msg += f'\n\n{traceback.format_exc()}'
            data = None

        # fallback processor
        if msg or not objective or not isinstance(df, pd.DataFrame):
            if self.fb_processor:
                setpoints, log = self.fb_processor(self.data, self.parameter)
                ext_logs[self.fb_processor.__module__] = log

        # write outputs
        self.output["output-data"] = data
        self.output["valid"] = bool(objective)
        self.output["objectives"] = objectives
        self.output["opt-duration"] = float(duration) if duration is not None else None
        self.output["termination"] = str(termination)
        self.output["setpoints"] = setpoints
        self.output["ext-logs"] = json.dumps(ext_logs)
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg