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
from .utility import update_nested_dict
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
            "objective": None,
            "opt-duration": None,
            "termination": None,
            "duration": None,
            "valid": None,
        }
        self.init = True
        self.parameter = None
        self.res = None
        self.smart_der = None

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
        fname = str(self.data.index[0]).replace(' ','').replace(':','')
        with open(os.path.join(log_dir, fname+'.txt'), 'w', encoding='utf8') as f:
            json.dump(self.parameter, f)
        self.data.to_csv(os.path.join(log_dir, fname+'.csv'))

    def compute(self):
        """Main compute."""
        st = time.time()
        msg = ""
        data = None
        objective = None
        duration = None
        termination = None
        df = None

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

                    self.init = False

                # update states
                state_inputs = json.loads(self.input["state-inputs"])
                update_nested_dict(self.parameter, state_inputs)
                
                # make inputs from forecast
                data = self._to_forecast_df(self.input["input-data"])
                tariff = get_tariff(self.parameter['site']["tariff_name"])
                data, _ = compute_periods(data, tariff, self.parameter)
                data = data.round(self.parameter['controller']['inputs_cutoff'])
                if pd.isnull(data).any().any():
                    msg += 'NAN values in MPC input. Index:' + \
                            data.index[pd.isnull(data).any().to_numpy().nonzero()[0]]
                self.data = data

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
                    

                # store outputs
                if isinstance(df, pd.DataFrame):
                    data = pd.concat([df, data], axis=1).to_json()

                # Store if error or timeout
                opt_timeout = duration > self.parameter['controller']['log_overtime']
                if (not objective) or opt_timeout:
                    self.log_results()

        except Exception as e:
            msg += str(e)
            if self.input['debug']:
                msg += f'\n\n{traceback.format_exc()}'
            data = None

        # write outputs
        self.output["output-data"] = data
        self.output["valid"] = bool(objective)
        if msg:
            self.output["objective"] = float(objective) if objective is not None else None
            self.output["opt-duration"] = float(duration) if duration is not None else None
            self.output["termination"] = str(termination)
        self.output["duration"] = time.time() - st

        if not msg:
            return "Done."
        return msg
