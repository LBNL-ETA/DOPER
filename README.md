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
The following link permits users to clone the source directory containing the [DOPER](https://github.com/LBNL-ETA/DOPER) package.

The package can be installed with the `pip install .` command.

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
* `controller`: settings for the optimization horizon, timestep, and location of solvers
* `objective`: weights that can be applied when constructing the optimization objective function
* `system`: binary values indicating whether each DER or load asset is enabled or disabled
* `site`: general characteristics of the site, interconnection constraints, and regulation requirements
* `network`: for multi-node models, this optional field includes data to characterize the network topology, map loads and resources to each node, and characterize the lines connecting nodes
* `tariff`: energy and power rates. Tariff time periods are provided in the separate time-series input
* `batteries`: a list of battery dicts with technical characteristics of each battery resource. Note: this is necessary because we have enabled `battery` in the 'system' field. 
* `gensets`: a list of genset dicts with technical characteristics of each generator resource. Note: this is necessary because we have enabled `genset` in the 'system' field.
* `load_control`: a list of load control dicts with technical characteristics of each load control resource. Note: this is necessary because we have enabled `load_control` in the 'system' field. 

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
* `grid_available`: binary indicating whether grid connection is available
* `fuel_available`: binary indicating whether fuel import is available
* `grid_co2_intensity`: current CO2 intensity of grid imports [kg/kWh]
* `generation_pv`: output of all PV connected to system [kW]
* `battery_N_avail`: binary indicating whether battery N is connected to system (e.g. for EVs)
* `battery_N_demand`: external discharging load for battery N (e.g. for EVs) [kW]
* `load_shed_potential_N`: volume of load sheddable under load control resource N [kW]
* `external_gen`: generation available from generic external generation source [kW]

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
Once DOPER solves the given Pyomo model, it will generate a pandas dataframe of timeseries parameter and variable data as part of its ouput. By default, a standard list of timeseries data will be generated. However, if you  have specific instructions on which Pyomo values to pass to DOPER outputs, you can pass an optional argument `output_list` when declaring a new instance of DOPER.

The optional argument is structured as a list of dictionaries structured, like the following:
```python
my_output_list = [
    {
        'data': '{var or param name within pyomo model}',
        'df_label': '{Label for your output column}'
    },
    {
        'data': '{another var or param}',
        'df_label': '{another label for your output column}'
    } 
]
```
Then use this list when initializing a DOPER instance
```python
# Define the path to the solver executable
solver_path = get_solver('cbc', solver_dir=os.path.join(get_root(), 'solvers'))

# Initialize DOPER
smartDER = DOPER(model=control_model,
                 parameter=parameter,
                 solver_path=solver_path,
                 output_list=my_output_list)
                 
# Proceed with solving optimization as described in above step
```


## Example
To illustrate the DOPER functionality, example Jupyter notebooks can be found [here](https://github.com/LBNL-ETA/DOPER/blob/master/examples/).

[Example 1](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER Example - Battery Storage.ipynb) shows the optimal dispatch of two stantionary batteries for a medium-sized office building with behind-the-meter photovoltaic system.

[Example 2](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER Example - Fleet Electric Vehicles.ipynb) shows the optimal dispatch of a fleet of three electric vehicles for a medium-sized office building with behind-the-meter photovoltaic system. EV control uses the same technology model as stationary battery storage, but includes additional inputs defining the availability and external load from vehicle use.

[Example 3](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER Example - Generators.ipynb) shows the optimal dispatch of two generators for a medium-sized office building with behind-the-meter photovoltaic system. The example illustrates the use of generator assets for both blue-sky and outage constrained operation.

[Example 4](https://github.com/LBNL-ETA/DOPER/blob/master/examples/DOPER Example - Load Control.ipynb) shows the optimal dispatch of load control within a medium-sized office building with behind-the-meter photovoltaic system. The example illustrates the use of load shedding for both economic objectives, as well as to increase survivability during grid outage.


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