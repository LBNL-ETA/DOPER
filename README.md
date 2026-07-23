# Distributed Optimal and Predictive Energy Resources (DOPER)

![Actions Status](https://github.com/LBNL-ETA/DOPER/workflows/Syntax/badge.svg)
![Actions Status](https://github.com/LBNL-ETA/DOPER/workflows/UnitTests/badge.svg)

#### Predictive Control Solution for Distributed Energy Resources and Integrated Energy Systems
----------------------------------------------------------------------------------------

This package is an optimal control framework for behind-the-meter battery storage, Photovoltaic generation, and other Distributed Energy Resources.

## General
The DOPER controller is implemented as a [Model Predictive Control](https://facades.lbl.gov/model-predictive-controls) (MPC), where an internal mathematical model is evaluated and solved to a global optimum, at each controller evaluation. The inputs are forecasts of weather data, Photovoltaic (PV) generation, and load for the upcoming 24 hours. The objective is to maximize the revenue (by minimizing the total energy cost) for the asset owner, while providing additional services to the grid. The grid services explored include time-varying pricing schemes and the response to critical periods in the grid. DOPER can optimally control the battery by charging it during periods with excess generation and discharging it during the critical afternoon hours (i.e. [Duck Curve](https://en.wikipedia.org/wiki/Duck_curve)). This active participation in the grid management helps to maximize the amount of renewables that can be connected to the grid.
![Overview](https://github.com/LBNL-ETA/DOPER/blob/master/docs/overview.jpg)
The DOPER controller was evaluated in annual simulations and in a field test conducted at the Flexgrid test facility at LBNL. The following plot shows example results for a field test conducted at LBNL's [FLEXGRID](https://flexlab.lbl.gov/flexgrid) facility. The base load without energy storage is shown in turquoise, the computed optimal result in purple, and the measured load in yellow.
![Performance](https://github.com/LBNL-ETA/DOPER/blob/master/docs/fieldperformance1.jpg)
Peak demand and total energy cost was significantly reduced. Annual simulations indicate cost savings of up to 35 percent, with a payback time of about 6 years. This is significantly shorter than the lifetime of typical batteries.

Further information can be found in the full project report listed in the [Cite](https://github.com/LBNL-ETA/DOPER#cite) section.

## Getting Started
The following link permits users to clone the source directory containing the [DOPER](https://github.com/LBNL-ETA/DOPER) package and then locally install with the `pip install .` command.

Alternatively, DOPER can be directly installed with `pip install git+https://github.com/LBNL-ETA/DOPER`.

Note that the [CBC](https://github.com/coin-or/Cbc) solver will be automatically installed and set as default solver for Linux and Windows systems. On MacOS please install the desired solver manually. For CBC please follow the installation instructions [here](https://github.com/coin-or/Cbc#binaries), and point the `solver_path` argument of DOPER to the `cbc` executable on your system.

## Use

Standard usage of the DOPER library follows the sequence of steps outlined in the example here:

#### 1. Instatiate Model & Define Objective
First import DOPER sub-modules 
```python
from doper import DOPER, get_solver, standard_report
from doper.models.basemodel import base_model, convert_model_dynamic, plot_dynamic
from doper.models.battery import add_battery
import doper.example as example
```
Then create an instance of a control model, which consists of a Pyomo Model and function describing the model's objective function. The control model takes system parameters and optimization (time-series) inputs as inputs and will be used by the DOPER wrapper to optimize the model.

Here, we define the Pyomo model using the DOPER `base_model` method. We then use the DOPER battery model `add_battery` method to add battery constraints to our model.

The objective function here simply includes electricity tariff energy and demand charges, as well as revenue from electricity exports. The objective function can be modified to suit your application's requirements.

```python
from pyomo.environ import Objective, minimize

def control_model(inputs, parameter):
    model = base_model(inputs, parameter)
    model = add_battery(model, inputs, parameter)
    
    def objective_function(model):
        return model.sum_energy_cost * parameter['objective']['weight_energy'] \
               + model.sum_demand_cost * parameter['objective']['weight_demand'] \
               - model.sum_export_revenue * parameter['objective']['weight_export']]
    model.objective = Objective(rule=objective_function, sense=minimize, doc='objective function')
    return model
```

#### 2. Define System Parameters
The system `parameter` object is a dictionary containing generally static values describing the system -- in particular the portfolio of available DERs and their performance characteristics. The DOPER sublibrary `example` contains functions to generate default parameter files, as well as methods to add generic technologies, such as battery storage in the example below.

```python
# load generic project parameter from example
parameter = example.default_parameter()

# add battery resources to existing parameter dict
parameter = example.parameter_add_battery(parameter)
```

Please refer to documentation on [Defining Parameter Object](https://github.com/LBNL-ETA/DOPER/blob/master/docs/parameter.md) for details on all model options, settings, and DER technologies that can be defined within the `parameter` object.


The `parameter` input contains the following entries:
* `controller`: settings for the optimization horizon, timestep, solver location, setpoint processing, fallback processing, and state-input filtering (see [State Input Filtering](#state-input-filtering) below)
* `objective`: weights that can be applied when constructing the optimization objective function
* `system`: binary values indicating whether each DER or load asset is enabled or disabled
* `site`: general characteristics of the site, interconnection constraints, and regulation requirements
* `network`: for multi-node models, this optional field includes data to characterize the network topology, map loads and resources to each node, and characterize the lines connecting nodes
* `tariff`: energy and power rates. Tariff time periods are provided in the separate time-series input. See [Tariff](#tariff) section below for details on loading built-in or custom tariffs.
* `batteries`: a list of battery dicts with technical characteristics of each battery resource. Note: this is necessary because we have enabled `battery` in the 'system' field. 
* `gensets`: a list of genset dicts with technical characteristics of each generator resource. Note: this is necessary because we have enabled `genset` in the 'system' field.
* `load_control`: a list of load control dicts with technical characteristics of each load control resource. Note: this is necessary because we have enabled `load_control` in the 'system' field. See [Load Control](#load-control) below for all available fields.

#### Load Control

When `parameter['system']['load_control'] = True`, DOPER can shed controllable load circuits to reduce energy cost or improve grid-outage survivability. Each entry in `parameter['load_control']` configures one circuit:

| Field | Required | Default | Description |
|---|---|---|---|
| `name` | ✓ | — | Unique circuit identifier (string) |
| `cost` | ✓ | — | Cost of shedding this circuit [$/kWh not served] |
| `outageOnly` | ✓ | — | If `True`, circuit can only be shed during a grid outage |
| `transition_cost` | | `0` | Cost applied each time the circuit transitions from **on → off** (a shedding activation) [$/activation] |
| `load_connected` | | `1` | Initial connection state before the optimisation horizon starts (`1` = connected, `0` = disconnected). Used to seed the shedding-activation calculation at the first timestep. |

The `transition_cost` and `load_connected` fields drive two objective-level variables:

* **`load_shed_act_total`** — total weighted shedding activations over the accounting horizon:  
  `load_shed_act_total = Σ der_shed_load[t, c] × transition_cost[c]` over all circuits `c` and accounting timesteps `t`.  
  `der_shed_load[t, c]` captures the falling edge of `load_circuits_on` (i.e., it is ≥ 1 only when a circuit switches from on to off).

* **`weight_load_shed_act`** (in `parameter['objective']`, default `0`) — scales `load_shed_act_total` in the objective. Set to a positive value to penalise frequent shedding activations.

**Initialisation at the first timestep** — `load_connected` seeds the derivative constraint at `t=1`:

```
der_shed_load[t=1, c] >= load_connected[c] - load_circuits_on[t=1, c]
```

This means:
- `load_connected = 1` (connected before the horizon): if the optimizer sheds the circuit at `t=1`, `der_shed_load[t=1]` ≥ 1, correctly counting that event toward `load_shed_act_total`.
- `load_connected = 0` (already off): the constraint is non-binding at `t=1`; continuing to shed incurs no additional activation cost.

The constraint is an **inequality** (`>=`), so the optimizer retains full flexibility to disconnect a circuit at the first timestep even when `load_connected = 1`.

**Example configuration:**

```python
parameter = example.default_parameter()
parameter['system']['load_control'] = True
parameter['load_control'] = [
    {
        'name': 'hvac_zone_a',
        'cost': 0.05,          # $/kWh not served
        'outageOnly': False,
        'transition_cost': 2,  # $2 per shedding activation
        'load_connected': 1,   # circuit was on before the horizon
    },
    {
        'name': 'ev_charger',
        'cost': 0.10,
        'outageOnly': False,
        'transition_cost': 0,  # no activation penalty
        'load_connected': 0,   # charger was already off
    }
]
# Penalise frequent activations in the objective
parameter['objective']['weight_load_shed'] = 1       # $/kWh weight
parameter['objective']['weight_load_shed_act'] = 1   # activation cost weight
```

The time-series input must include a column `load_shed_potential_{name}` [kW] for each circuit, giving the maximum sheddable power at each timestep.

#### Setpoint Processor and Fallback Processor

The `controller` section exposes two optional callable hooks that can post-process optimization results:

* `sp_processor` — `None` (default) or a dict `{"module": "my_module", "name": "my_sp_processor"}`. Called after a **successful** optimization run when the result DataFrame `df` is available. Receives `(data, parameter)` and must return `(setpoints, log)`.

* `fb_processor` — `None` (default) or a dict `{"module": "my_module", "name": "my_fb_processor"}`. Called as a **fallback** whenever the optimization did not produce valid results, i.e. when `msg or not objective or not isinstance(df, pd.DataFrame)`. Receives `(data, parameter)` and must return `(setpoints, log)`.

Both callables are resolved once at wrapper initialisation using `resolve_wrapper_callable` and called on every subsequent `compute()` invocation where their trigger condition is met. The `log` value (any JSON-serializable type) is stored in the `"ext-logs"` output keyed by the processor's module name.

```python
# In the parameter dict
parameter['controller']['sp_processor'] = {
    "module": "my_package.processors",
    "name": "my_sp_processor"
}
# expected signature: my_sp_processor(data, parameter) -> (setpoints: dict, log)

parameter['controller']['fb_processor'] = {
    "module": "my_package.processors",
    "name": "my_fb_processor"
}
# expected signature: my_fb_processor(data, parameter) -> (setpoints: dict, log)
```

A ready-to-use **setpoint processor** for battery storage is provided in `doper.data.setpoint_processor` and is configured as the default in `default_parameter()`. It reads the optimized net grid power (`battery_net_grid_power`) from the result DataFrame and maps it to setpoint keys:

```python
parameter['controller']['sp_processor'] = {
    "module": "doper.data.setpoint_processor",
    "name": "battery_setpoint_processor"
}
```

The processor reads `'Battery %s Net Grid Power [kW]'` columns from the result DataFrame (one per battery), applies an optional `setpoint_scale`, and writes the value to the setpoint key defined by `parameter['controller']['setpoint_names']['battery_power']`. It silently skips when `parameter['system']['battery']` is `False`. The `log` contains `messages` and `warnings`.

Processor behaviour can be tuned via `parameter['setpoint_processor_config']`:

```python
parameter['setpoint_processor_config'] = {
    'battery_net_grid_power_col': 'Battery %s Net Grid Power [kW]', # source column template
    'setpoint_scale': 1,  # multiply power value before writing to setpoints
}
```

A ready-to-use TOU-based fallback for battery storage is provided in `doper.data.fallback_processor`:

```python
parameter['controller']['fb_processor'] = {
    "module": "doper.data.fallback_processor",
    "name": "battery_tou_processor"
}
```

The fallback processor returns `(setpoints, log)` where `setpoints` keys are formatted strings (battery display name substituted via `%s`) and values are plain floats. `log` contains `hour`, `messages`, and `overrides`. The key template is **required** and must be provided via `parameter['controller']['setpoint_names']['battery_power']`.

##### Setpoint names

To ensure that `sp_processor` and `fb_processor` produce **identical setpoint key names**, both processors should read their key templates from a shared location in `parameter`:

```python
parameter['controller']['setpoint_names'] = {
    'battery_power': 'Battery %s Power Command [kW]',  # format string; %s = display name
    'battery_name_map': {
        # optional: map internal battery name -> display name inserted into the template
        # 'libat01': 'Main BESS',
    },
}
```

`battery_tou_processor` reads this dict automatically. Any custom `sp_processor` should do the same:

```python
def my_sp_processor(data, parameter):
    sp_names = {}
    if 'controller' in parameter and 'setpoint_names' in parameter['controller']:
        sp_names = parameter['controller']['setpoint_names']
    template = sp_names['battery_power'] if 'battery_power' in sp_names else 'Battery %s Power Command [kW]'
    battery_name_map = sp_names['battery_name_map'] if 'battery_name_map' in sp_names else {}

    setpoints = {}
    for bat in parameter['batteries']:
        display_name = battery_name_map[bat['name']] if bat['name'] in battery_name_map else bat['name']
        setpoints[template % display_name] = ...  # computed value
    return setpoints, {}
```

When `battery_name_map` is empty (the default), the internal battery `name` is used as-is. When a battery is not listed in `battery_name_map`, it also falls back to the internal name.

The TOU schedule and all sizing parameters can be overridden via `parameter['battery_tou_processor_config']`:

```python
parameter['battery_tou_processor_config'] = {
    # (start_h, end_h, mode, rate, pv_excess_only)
    # rate [kW]: when set, used directly instead of the energy/time calculation
    # pv_excess_only: when True, charge power is capped at excess PV generation
    #   excess PV = max(0, data["generation_pv"] - data["load_demand"])
    'tou_windows': [
        (0,  6,  'charge',    None,  True),   # charge from excess PV only, size to 06:00
        (6,  9,  'idle',      None,  False),
        (9,  15, 'charge',    None,  False),  # charge normally, size to 15:00
        (15, 21, 'discharge', 30.0,  False),  # fixed 30 kW discharge
        (21, 24, 'idle',      None,  False),
    ],
    'safety_factor': 1.15,            # headroom above average rate (default 1.0)
    'min_hours_remaining': 0.25,      # minimum window remainder [h] (default 0)
    'emergency_recovery_hours': 2.0,  # recovery window when soc < soc_min
    'setpoint_scale': 1,              # multiply power_kW before writing to setpoints
}
```

##### `pv_excess_only` flag

Each TOU window entry is a 5-tuple `(start_h, end_h, mode, rate, pv_excess_only)`. When `pv_excess_only=True` on a `charge` window, the energy/time sizing calculation and any fixed `rate` are bypassed. Instead, the battery charges at the full available excess PV, capped only by the hardware maximum charge power:

```
excess_pv    = max(0, data["generation_pv"].iloc[0] - data["load_demand"].iloc[0])
charge_power = min(excess_pv, bat["power_charge"])
```

This absorbs all surplus solar that would otherwise be exported, without limiting the rate to what a time-based sizing calculation would recommend. If `generation_pv` is absent from the data or there is no excess (load ≥ PV), charge power is `0`. The flag has no effect on `discharge` or `idle` windows. A log message is written to `log["messages"]` whenever the mode is active.

Safety overrides always apply on top of the rate or calculated power:
- `soc < soc_min` → emergency charge sized to recover within `emergency_recovery_hours`
- `soc >= soc_max` during a charge window → power set to 0

The `"ext-logs"` output is a JSON string keyed by processor module name and is always present (empty `{}` when no processor ran):

```python
import json
ext_logs = json.loads(wrapper.output["ext-logs"])
# e.g. {"my_package.processors": <log value>}
```

#### State Input Filtering

The `DoperWrapper` applies measured states (e.g. battery SOC) from `state-inputs` to `parameter` before each optimization run. The `controller` section exposes one key to control how these measurements are accepted or rejected:

* `update_states_thr` — `dict`, default `{}`. Maps each state key (e.g. `"soc_initial"`) to a threshold. When `|expected − measured| ≤ threshold` the measured value is considered too close to the model prediction to be meaningful, and the optimization runs with the internally predicted value instead. An empty dict (the default) always accepts the measured value.

```python
parameter['controller']['update_states_thr'] = {
    'soc_initial': 0.05  # ignore measurements within 5% of predicted SOC
}
```

**SOC boundary override** — regardless of `update_states_thr`, `soc_initial` is always accepted from measurements when the battery is at a limit:

| Condition | Behaviour |
|---|---|
| `measured_soc <= soc_min` | always use measured value |
| `measured_soc >= soc_max` | always use measured value |
| `measured_soc < 0` | invalid reading — use internally predicted value |

This ensures the optimizer correctly handles a fully depleted or fully charged battery even if the change is within the configured threshold.

#### Tariff

DOPER provides a helper function `get_tariff` (importable from `doper.data.tariff`) that returns a tariff dict ready to be assigned to `parameter['tariff']`. It accepts three types of input:

* **Named string** — one of the built-in tariff identifiers (default: `'e19-2018'`):

  | Identifier | Description |
  |---|---|
  | `'e19-2018'` | PG&E E-19 tariff (March 1, 2018) |
  | `'e19-2018-new'` | PG&E E-19 tariff (November 2018) |
  | `'e19-2019'` | PG&E E-19 tariff (April 24, 2019) |
  | `'e19-2020'` | PG&E E-19 tariff (May 1, 2020) |
  | `'e19-2022'` | PG&E E-19 tariff Secondary Voltage (June 1, 2022) |
  | `'tou8-2019'` | SCE TOU-8 Option D 2-50 kV (July 26, 2019) |
  | `'tou8-2020'` | SCE TOU-8 Option D 2-50 kV (March 13, 2020) |
  | `'tou8-2022'` | SCE TOU-8 Option D 2-50 kV (June 1, 2022) |
  | `'nspc-gtds-2019'` | Northern State Power Company – General Time of Day Service (January 6, 2019) |
  | `'nspc-gs-2019'` | Northern State Power Company – General Service (January 6, 2019) |
  | `'bge-gs-2019'` | Baltimore Gas and Electric – General Service (December 17, 2019) |
  | `'bge-gs-2022'` | Baltimore Gas and Electric – General Service (January 1, 2022) |
  | `'test1'` | Synthetic test tariff |

* **Custom dict** — a fully user-defined tariff dict is returned unchanged.
* **JSON string** — a JSON-encoded tariff dict is parsed and returned as a dict.

```python
from doper.data.tariff import get_tariff

# Load a built-in tariff by name
parameter['tariff'] = get_tariff('e19-2020')

# Pass a custom tariff dict directly
my_tariff = {'name': 'custom', 'tz': 'America/Los_Angeles', ...}
parameter['tariff'] = get_tariff(my_tariff)

# Pass a JSON-encoded tariff string
import json
parameter['tariff'] = get_tariff(json.dumps(my_tariff))
```

---

#### 3. Define Optimization (Time-series) Input
The optimization also needs timeseries data to indicate the values for time-variable model parameters (e.g. building load or PV generation). In application, these will often be linked to forecast models, but for this example, we simply load timeseries data from the `example_inputs` function.

```python
data = example.ts_inputs(parameter, load='B90', scale_load=150, scale_pv=100)
```

The time-series input should be in the form of a pandas dataframe, indexed by timestamp, may include columns that contains the following data:
* `load_demand`: system load profile [kW]
* `oat`: outside air temperature [C]
* `tariff_energy_map`: mapping of time-period to tariff TOU period
* `tariff_power_map`: mapping of time-period to tariff TOU power demand period
* `tariff_energy_export_map`: mapping of time-period to energy export price
* `utility_rtp`: real-time price utility rate [$/kWh] (optional, default = 0)
* `utility_rtp_export`: real-time price export rate [$/kWh] (optional, default = utility_rtp)
* `grid_available`: binary indicating whether grid connection is available
* `fuel_available`: binary indicating whether fuel import is available
* `grid_co2_intensity`: current CO2 intensity of grid imports [kg/kWh]
* `generation_pv`: output of all PV connected to system [kW]
* `battery_{name}_avail`: binary indicating whether battery `{name}` is connected to system (e.g. for EVs)
* `battery_{name}_demand`: external discharging load for battery `{name}` (e.g. for EVs) [kW]
* `load_shed_potential_N`: volume of load sheddable under load control resource N [kW]
* `external_gen`: generation available from generic external generation source [kW]
* `import_max`: optional time-varying site import capacity [kW]
* `export_max`: optional time-varying site export capacity [kW]

The required columns will vary between single-node and multi-node models. Please refer to documentation on [Defining Time-series Input Object](https://github.com/LBNL-ETA/DOPER/blob/master/docs/input.md) for details on required and optional fields that may be passed to the model using the timeseries input object.

#### 4. Optimize Model
With these settings selected, we can create an instance of DOPER, using the `control_model`, `parameter`, and output instructions (`pyomo_to_pandas`) function. With the DOPER model instantiated, we can solve using the `.do_optimization` method. 
```python
# Define the path to the solver executable
solver_path = get_solver('cbc')

# Initialize DOPER
smartDER = DOPER(model=control_model,
                 parameter=parameter,
                 solver_path=solver_path)

# Conduct optimization
res = smartDER.do_optimization(data)

# Get results
duration, objective, df, model, result, termination, parameter = res
print(standard_report(res))
```

`standard_report` reports high level metrics for the optimization.
```output
Solver          CBC
Duration [s]    1.97
Objective [$]   8380.34         3726.89 (Total Cost)
Cost [$]        4875.04 (Energy)    3505.3 (Demand)
Revenue [$]     0.0 (Export)        0.0 (Regulation)
```

#### 5. Requesting Custom Timeseries Ouputs
Once DOPER solves the given Pyomo model, it will generate a pandas dataframe of timeseries parameter and variable data as part of its ouput. By default, a standard list of timeseries data will be generated. However, if one has specific instructions on which Pyomo values to pass to DOPER outputs, an optional argument `output_list` can be passed when declaring a new instance of DOPER. It consists of a `data` label to identify the variable within the optimzaiton model, `df_label` to specify the output column name, and the optional `index` argument if additional indices (besides time) are required. In the example below it can be seen that the model includes multiple batteries, indexed by the variable `battery`. Note that the `df_label` needs to include the string formatter `%s` to pass the custom index, e.g., battery index, to the output dataframe.

The optional argument is structured as a list of dictionaries structured, like the following:
```python
my_output_list = [
    {
        'data': '{var or param name within pyomo model}',
        'df_label': '{Label for your output column}'
    },
    {
        'data': 'battery_charge_grid_power',
        'df_label': 'Battery Charging Power (Battery %s) [kW]',
        'index': 'batteries'
    } 
]
```
Then use this list when initializing a DOPER instance
```python
# Define the path to the solver executable
solver_path = get_solver('cbc')

# Initialize DOPER
smartDER = DOPER(model=control_model,
                 parameter=parameter,
                 solver_path=solver_path,
                 output_list=my_output_list)
                 
# Proceed with solving optimization as described in above step
```


## Example
To illustrate the DOPER functionality, example Jupyter notebooks can be found [here](https://github.com/LBNL-ETA/DOPER/blob/master/examples/).

[Example 1](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER%20Example%20-%20Battery%20Storage.ipynb) shows the optimal dispatch of two stantionary batteries for a medium-sized office building with behind-the-meter photovoltaic system.

[Example 2](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER%20Example%20-%20EV%20Fleet.ipynb) shows the optimal dispatch of a fleet of three electric vehicles for a medium-sized office building with behind-the-meter photovoltaic system. EV control uses the same technology model as stationary battery storage, but includes additional inputs defining the availability and external load from vehicle use.

[Example 3](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER%20Example%20-%20Generator.ipynb) shows the optimal dispatch of two generators for a medium-sized office building with behind-the-meter photovoltaic system. The example illustrates the use of generator assets for both blue-sky and outage constrained operation.

[Example 4](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER%20Example%20-%20Load%20Control.ipynb) shows the optimal dispatch of load control within a medium-sized office building with behind-the-meter photovoltaic system. The example illustrates the use of load shedding for both economic objectives, as well as to increase survivability during grid outage.


## License
Distributed Optimal and Predictive Energy Resources (DOPER) Copyright (c) 2019, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Dept. of Energy). All rights reserved.

If you have questions about your rights to use or distribute this software, please contact Berkeley Lab's Intellectual Property Office at IPO@lbl.gov.

NOTICE. This Software was developed under funding from the U.S. Department of Energy and the U.S. Government consequently retains certain rights. As such, the U.S. Government has been granted for itself and others acting on its behalf a paid-up, nonexclusive, irrevocable, worldwide license in the Software to reproduce, distribute copies to the public, prepare derivative works, and perform publicly and display publicly, and to permit other to do so.

## Cite
To cite the DOPER package, please use:

```bibtex
@article{gehbauer2021photovoltaic,
 title={Photovoltaic and Behind-the-Meter Battery Storage: Advanced Smart Inverter Controls and Field Demonstration},
 author={Gehbauer, Christoph and Mueller, Joscha and Swenson, Tucker and Vrettos, Evangelos},
 year={2021},
 journal={California Energy Commission},
 url={https://escholarship.org/uc/item/62w660v3}
}
```