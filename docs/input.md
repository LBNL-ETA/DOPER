## Defining timeseries input

This input to the optimization must be in the form of a pandas dataframe, indexed by a datetime. For each optimization, the model requires a time-series data frame containing known or predict values for the optimization time horizon, including fields such as building loads, energy prices, and resource availability (e.g. PV output profiles)

Depending on the configuration of your model, and the DER assets included, some fields within the timeseries data are required, while others are optional. Descriptions of each of these field types are outlined below for (1) Single node, and (2) Multi-Node models.

---

#### 1. Single Node Input

##### 1.1. Required Fields

The following fields must be included in the time-series data for single node models. Without these fields, the model with return an error when trying to optimize. The names of the items listed below must match exactly with columns in 

* `load_demand`: system load profile [kW]
* `oat`: outside air temperature [C]
* `tariff_energy_map`: mapping of time-period to tariff TOU period
* `tariff_power_map`: mapping of time-period to tariff TOU power demand period
* `tariff_energy_export_map`: mapping of time-period to energy export price
* `generation_pv`: output of all PV connected to system [kW]. If no PV is present, set values to 0.

##### 1.2. Optional Fields

The following fields may be included if certain features of the model (e.g. electricity or fuel outages) are to be included in the solution. If these fields are not found in the input, default values are used.

* `grid_available`: binary indicating whether grid connection is available. If not provided, defaults to 1-grid always available
* `fuel_available`: binary indicating whether fuel import is available. If not provided, defaults to 1-fuel import always available
* `grid_co2_intensity`: current CO2 intensity of grid imports [kg/kWh]. If not provided, defaults to 0. If carbon values are included in the optimization objective, a warning will be raised

##### 1.3. DER-specific Fields

The following fields may be included if certain DER assets and features are to be used during the model. Note, some items are optional and some required for a given DER asset type, as indicated below.

* `battery_N_avail`: binary indicating whether battery N is connected to system. Optional input to model an EV as a battery. If missing, asset is treated as a stationary battery
* `battery_N_demand`: external discharging load for battery N [kW]. Optional input to model an EV as a battery. If missing, asset is treated as a stationary battery
* `load_shed_potential_X`: volume of load sheddable under load control resource with the name field set to 'X' [kW]. If load control is enabled for a model, the corresponding load_shed_potential field must be included in the input data. Number of load control assets must match the number of shed potential profiles. Missing items will generate an error.
* `external_gen`: generation available from generic external generation source [kW]. If `parameter['system']['external_gen']` is set to `True`, then this field must be included in the input data

---

#### 2. Multi-Node Input

##### 2.1. Required Fields

The following fields must be included in the time-series data for multi-node models. Without these fields, the model with return an error when trying to optimize. The names of the items listed below must match exactly with columns in 

* `oat`: outside air temperature [C]
* `tariff_energy_map`: mapping of time-period to tariff TOU period
* `tariff_power_map`: mapping of time-period to tariff TOU power demand period
* `tariff_energy_export_map`: mapping of time-period to energy export price

##### 2.2. Optional Fields

The following fields may be included if certain features of the model (e.g. electricity or fuel outages) are to be included in the solution. If these fields are not found in the input, default values are used.

* `grid_available`: binary indicating whether grid connection is available. If not provided, defaults to 1-grid always available
* `fuel_available`: binary indicating whether fuel import is available. If not provided, defaults to 1-fuel import always available
* `grid_co2_intensity`: current CO2 intensity of grid imports [kg/kWh]. If not provided, defaults to 0. If carbon values are included in the optimization objective, a warning will be raised

##### 2.3. Node-specifc Fields

The following fields should be included for some or all nodes of a multi-node model. The name of these fields are user-selected. However, the names chosen for these fields must match those used in the corresponding sections of `parameter['network']['nodes']`. 

* `{node load_id}`: users can define a load profile assigned to a node. The nodal load_id used in the `parameter` file must be found in the timeseries data. Users can assign multiple load_id items to a single node. In such a case, all load_id items must be found in the timeseries data.
* `{node pv_id}`: users can define a pv profile assigned to a node. The nodal pv_id used in the `parameter` file must be found in the timeseries data. Users can assign multiple pv_id items to a single node. In such a case, all pv_id items must be found in the timeseries data.

##### 2.3. DER-specific Fields

The following fields may be included if certain DER assets and features are to be used during the model. Note, some items are optional and some required for a given DER asset type, as indicated below.

* `battery_N_avail`: binary indicating whether battery N is connected to system. Optional input to model an EV as a battery. If missing, asset is treated as a stationary battery
* `battery_N_demand`: external discharging load for battery N [kW]. Optional input to model an EV as a battery. If missing, asset is treated as a stationary battery
* `load_shed_potential_X`: volume of load sheddable under load control resource with the name field set to 'X' [kW]. If load control is enabled for a model, the corresponding load_shed_potential field must be included in the input data. Number of load control assets must match the number of shed potential profiles. Missing items will generate an error.
* `external_gen`: generation available from generic external generation source [kW]. If `parameter['system']['external_gen']` is set to `True`, then this field must be included in the input data
