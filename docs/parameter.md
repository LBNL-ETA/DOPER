## Defining system `parameter` input

The `parameter` input consists of data used to characterize the system being optimized by the controller. In general, the data contained inside `parameter` is static and does not change between subsequent iterations of the optimization. The `parameter` object is a python dict contain sub dict and list objects. The structure and content of each of the compoents is outlined below:

 * `system`: [dict] high level information defining with DER asset types and features are to be included or enabled within the model.
 * `controller` [dict] settings data for the optimization proces
 * `objective` [dict] weights applied to different components of the optimization objective function
 * `site` [dict] general site characteristics like previous demand levels, regulation participation, etc. Note: these items may be refactored into more descriptive categories
 * `tariff` [dict] data used to characterize the rates applies to power and energy imports from the electrity grid
 * `fuels` [list] list of fuels available within the model to power generators and other assets
 * `network` [dict] data used to define a multi-node system model. Used to define network settings, nodes, connections between nodes, and the location of loads and DER assets within the network
 * `batteries` [list] list of battery objects used to define individual battery assets
 * `gensets` [list] list of genset objects used to define individual generator assets
 * `load_control` [list] list of load_control objects used to define individual sheddable load assets

---

#### 1. Defining `parameter['system']`

This dict is the top-level option to enable/disable technology types within a model. If a technology type is disabled within system, but included elsewhere in the model, an assertion error is generated.

The content of `parameter['system']` is as follows:

* `pv` [bool] option to enable pv generation within model
* `battery` [bool] option to enable battery or EV assets within model
* `genset` [bool] option to enable generator assets within model
* `load_control` [bool] option to enable controllable load shedding within model
* `external_gen` [bool] option to enable generic external generation sources within model
* `hvac_control` [bool] option to enable internal building control within model
* `reg_bidding` [bool] option to enable the generation of regulation bids within model
* `reg_response` [bool] option to enable the response to existing regulation awards within model

---

#### 2. Defining `parameter['controller']`

This dict contains basic information for configuring the optimization.

The content of `parameter['controller']` is as follows:

* `timestep` [int] controller timestep in seconds
* `horizon` [int] controller horizon in seconds
* `solver_dir` [str] path to sub-directory containing solvers

---

#### 3. Defining `parameter['objective']`

This dict contains weights to be applied to various components when constructing optimization objective.

The content of `parameter['objective']` is as follows:

* `weight_energy` [int] weight applied to electricity energy costs
* `weight_fuel` [int] weight applied to fuel energy costs
* `weight_demand` [int] weight applied to electricity power demand costs
* `weight_export` [int] weight applied to electricity energy export revenue
* `weight_regulation` [int] weight applied to regulation revenue
* `weight_degradation` [int] weight applied to battery degradation costs
* `weight_co2` [int] weight applied to CO2 [in kg] emissions
* `weight_load_shed` [int] weight applied to load shed unserved energy costs

---

#### 4. Defining `parameter['site']`

This dict contains various options related to the site data.

The content of `parameter['site']` is as follows:

* NEED TO UPDATE

---

#### 5. Defining `parameter['tariff']`

This dict contains data needed to define tariff rates.

The content of `parameter['tariff']` is as follows:

* `energy` [dict] rates applied to offpeak (0), midpeak (1), and onpeak (2) periods of a TOU rates for energy imports. units: $/kWh
* `demand` [dict] rates applied to offpeak (0), midpeak (1), and onpeak (2) periods of a TOU rates for power demand levels. unit: $/kW
* `demand_coincident` [float] rate applied to coincident demand levels ($/kW). Note: where is coincident peak time defined?
* `export` [dict] rates applied to offpeak (0), midpeak (1), and onpeak (2) periods of a TOU rates for energy exports. units: $/kWh

An example tariff object:

```
parameter['tariff'] = {
	'energy': {
		0: 0.11,
		1: 0.16,
		2: 0.22 
	},
	'power': {
		0: 0.0,
		1: 11.50,
		2: 16.75
	},
	'demand_coincident': 10.20,
	'export': {
		0: 0.11,
		1: 0.16,
		2: 0.22
	}
}
```

---

#### 6. Defining a fuel type in `parameter['fuels']`

This item contains a list of fuel objects. Users can define fuels genericly by creating a fuel dict with the items below. Once created, a fuel type can be linked to a generator or other fuel consuming asset. The consumption and cost of a fuel will be determined by its use within the optimization horizon.

The content of a fuel items includedin in the list `parameter['fuels']` is as follows:

* `name` [str] unique name of the fuel type (e.g. 'diesel'). This will be references for generators that consume this fuel type.
* `unit` [str] the unit in which the fuel is generally distributed (e.g. 'gallons'). This is to aid users when defining fuels, and converting to kWh, which is the base energy unit used within the optimization.
* `rate` [float] the unit price of the fuel, using the unit defined above ($/unit)
* `conversion` [float] the factor used to convert the user-define unit into kWh (kwh/unit)
* `co2` [float] the amount of embodies CO2 per unit (kg/unit)
* `reserves` [dict] the amount of fuel reserves on-site that can be used in the event of a fuel outage (units)

An example list of fuels:
```
parameter['fuels'] = [
    {
        'name': 'ng',
        'unit': 'therms',
        'rate': 3.93, # $/therm
        'conversion': 30.77, # kWh/therm
        'co2': 5.3, # kg/therm
        'reserves': 0 # therm
    },
    {
        'name': 'diesel',
        'unit': 'gallons',
        'rate': 3.4, # $/gal
        'conversion': 35.75, # kWh/gal  
        'co2': 10.18, # kg/gal 
        'reserves': 100 # gal  
    }    
]
```



---

#### 7. Defining a PV generation profile

If PV is enabled under `parameter['system']['pv']` the model will look for a pv generation profile in the timeseries `input` dataframe. For single-node models, this profile is expected to be found in a column named `pv generation [kW]`. 

For multi-node profiles, users may define an arbitrary number of pv generation profiles, and label their columns however they prefer. However, these column names must be reference exactly in the `pv_id` field, when defining the node. See more below in section **Creating a multi-node model**.

Because PV is non-dispatchable, no additional PV system data is required.

---

#### 8. Defining a genric external generation profile

Similar to PV, users can define a generic, non-dispatchable, external generation profile (e.g. from an asset like wind or hydro). If enabled under `parameter['system']['external_gen']` the model will look for a generation profile in the timeseries `input` dataframe. For single-node models, this profile is expected to be found in a column named `external_gen`. 

For multi-node profiles, users may define an arbitrary number of external generation profiles, and label their columns however they prefer. However, these column names must be reference exactly in the `external_gen` field, when defining the node. See more below in section **Creating a multi-node model**.

---

#### 9. Defining a battery asset in `parameter['batteries']`

This item is a list of batteries or electric vehicles present on-site. To include a battery in an optimization, add an object to the `parameter['batteries']` list with the following items:


* `name` [str] unique name of the battery that will be used to reference its dispatch profile from the optimization results.
* `capacity` [float] total energy capacity of the battery [kWh]
* `power_charge` [float] total power charging capacity of the battery [kW]
* `power_discharge` [float] total power discharging capacity of the battery [kW]
* `efficiency_charging` [float] charging efficiency of the battery [-]
* `efficiency_discharging` [float] discharging efficiency of the battery [-]
* `soc_min` [float] minimum allowable state-of-charge of the battery [-]
* `soc_max` [float] maximum allowable state-of-charge of the battery [-]
* `soc_initial` [float] state-of-charge of the battery at the start of optimization horizon [-]
* `soc_final` [float] state-of-charge of the battery at the end of optimization horizon [-]. 
	* If `True` then `soc_final` must equal `soc_initial`
	* If `False` then `soc_final` can be selected by optimization
	* If `float` then `soc_final` must equal the value provided by user
* `self_discharging` [float] fraction of stored energy lost to decay in each hour [-/hr]

The follow battery properties are required when including the optional battery degradation model in the optimization:

* `nominal_V` [float] nominal voltage of the battery [V]
* `temperature_initial` [float] initial internal temperature of the battery [°C]
* `degradation_endoflife` [float] percent of usable capacity at with battery must be replaced [%]
* `degradation_replacementcost` [float] cost to replace degraded battery [$]
* `thermal_C` [float] thermal conductivity of the battery [W/mK] Note: units correct?
* `thermal_R` [float] thermal resistance of the battery [K/W] Note: units correct?

An example battery item:
```
parameter['batteries'] = [
    {
		'name':'example_bat',
		'capacity': 200,
		'power_charge': 50,
		'power_discharge': 50,
		'efficiency_charging': 0.96,
		'efficiency_discharging': 0.96,
		'soc_min': 0.2,
		'soc_max': 1,
		'soc_initial': 0.65,
		'soc_final': True,
		'self_discharging': 0.0,

		# optional properties
		'nominal_V':  400,
		'temperature_initial': 22.0,
		'degradation_endoflife': 80,
		'degradation_replacementcost': 6000.0,
		'thermal_C': 100000.0,
		'thermal_R': 0.01
    }
]
```

---

#### 10. Defining an electric vehicle (EV) asset in `parameter['batteries']`

In the optimization model, EVs can be modeled using the same structure as stationary batteries. To model an EV, define its battery properties as described above. To capture the expected availability of the EV battery, and its power demand related for trips. Include the following columns in the timeseries `input` dataframe:

* `battery_{name}_avail` [bool] indicates when EV is connected to on-site charging station
* `battery_{name}_demand` [float] power demand to serve transport requirements within each timestep.

Where `{name}` corresponds to the battery name listed in the EV's battery definition. If the demand and availability columns are not found in 'input', then the battery will be modeled as a stationary asset.

## Note: should battery asset contain EV flag and assertion to check availability and demand columns exist? Currently, small errors could result in EVs being treated as regular batteries without clear warning to user.


---

#### 11. Defining a generator asset in `parameter['gensets']`

This item is a list of generators present on-site. To include a generator in an optimization, add an object to the `parameter['gensets']` list with the following items:


* `name` [str] unique name of the genset that will be used to reference its dispatch profile from the optimization results.
* `capacity` [float] total output power capacity of the genset [kW]
* `efficiency` [float] efficiency of unit [kWh electric/kWh fuel]
* `fuel` [str] name of fuel-type used to power unit. Fuel reference here must exist in `paremeter['fuels]`
* `backupOnly` [bool] option to limit genset use to periods when grid electricity is not available

Note: the following input items have not been fully implemented in current release

* `omVar` [float] O&M costs per unit output [$/kWh]
* `maxRampUp` [float] Maximum ramp-up rate [kW/hr]
* `maxRampDown` [float] Maximum ramp-down rate [kW/hr]
* `timeToStart` [float] time required to start genset [hr]
* `regulation` [bool] whether genset can be used in regulation [kW]

An example genset item:
```
parameter['gensets'] = [
    {
        'name': 'example genset',
        'capacity': 60,
        'efficiency': 0.25,
        'fuel': 'ng',
        'backupOnly': True,
        
        # dev-only inputs
        'omVar': 0.01,
        'maxRampUp': 0.5,
        'maxRampDown': 0.5,
        'timeToStart': 1,
        'regulation': False
        
    }
]
```


---

#### 12. Defining a load control asset in `parameter['load_control']`

This item is a list of sheddable load assets present on-site. To include a sheddable load in an optimization, add an object to the `parameter['load_control']` list with the following items:

The content of `parameter['load_control']` is as follows:

* `name` [str] unique name of load control circuit
* `cost` [float] costs or value of lost load (VoLL) of shed load [$/kWh]
* `outageOnly` [bool] whether load can be shed only when grid electricty is not available

The value of a given load control asset is defined in the timeseries `input` data. For load control to work correctly, there must be a column in the `input` dataframe with the name `load_shed_potential_{asset name}`, where asset name corresponds to the field `name` in the above dict. If this column is missing from the `input` dataframe, an assert error will be thrown.

An example load control asset:
```
parameter['load_control'] = [        
    { # Note: input must contain col named 'load_shed_potential_exampleA'
        'name': 'exampleA',
        'cost': 0.05, # $/kWh not served
        'outageOnly': False
    },
    { # Note: input must contain col named 'load_shed_potential_exampleB'
        'name': 'exampleB',
        'cost': 0.3, # $/kWh not served
        'outageOnly': True
    } 
]
```

---

#### 13. Creating a multi-node model using `parameter['network']`

This dict is an optional input used to define and configure a multi-node system. If this items is omitted from `parameter`, the model is assumed to be a single-node system. All defined DER assets are assumed to exits within that simple system, and no power-flow constraints are imposed.

If `parameter['network']` is included, the model will attempt to construct a multi-node models from the other inputs provided by the user, including:
* defining individual nodes
* mapping the location of loads and DER assets to each of those nodes
* defining the connections between nodes
* managing power exchange between nodes in accordance with line capacities and power flow constraints

Adding multi-node functionality does not change how DER assests as defined in the `parameter` input, as described above, but does require additional information to be provided in the `parameter['network']` sub-dictionary.


`parameter['network']` contains the following fields:
* `settings` [dict] general settings for configuring the system network
* `nodes` [list] a list of node objects, indicating all internal nodes to be modelled within the network
* `lines` [list] a list of line objects, indicating all individual lines connecting nodes with the newtork

##### 13.1. Network Settings

Currently contains the following items. Additional settings options will be added as the full power-flow model implementation is completed.

* `simpleNetworkLosses` [float] fraction of exchanged power lost in line when using the simple power exchange model [-]


##### 13.2. Nodes

A list of all nodes in network. Each node object is composed of the following items:

* `node_id` [str] unique name used to identify the node
* `pcc` [bool] indicates if node is point-of-common-coupling (pcc) node, able to import/export from grid
* `load_id` - label of any loads connected at node
	* if `str` - a col with this name must exist in `input` dataframe, corresponding to this load profile
	* if `list` of `str` - each str  must have corresponding col in `input` dataframe, profiles are summed for node
	* if `None` - no load is applied at node

* `ders` [dict] indicates any DER assets connected at this node. Values to items listed below can be `str`, `list` of `str`, or `None`. Connected assets should correspond to defined DER assets and match the given name. From `pv`, names should match columns in `input` dataframe corresponding to PV generation profiles
	* `pv_id` - names of pv generation profiles in `input`
	* 'battery' - names of battery assets, including EVs, connected to node
	* 'genset' - names of genset assets connected to node
	* 'load_control' - names of load_control assets connected to node
	* `external_gen` - names of any external generation profiles in `input`

* `connections` [list] indicates any existing connections between this node to other defined nodes. Each line item is a `dict` composed of the following items:
	* `node` - name of node connected
	* `line` - name of line-type connecting the nodes. (See below for defining line-types)

An example node:
```
example_node = {
'node_id': 'node1', # unique str to id node
        'pcc': True, # bool to define if node is pcc
        'load_id': 'load_demand_1', # str, list of str, or None to find load profile in ts data (if node is load bus) by column label
        'ders': { # dict of der assets at node, if None or not included, no ders present
            'pv_id': None, # str, list, or None to find pv profile in ts data (if pv at node) by column label
            'battery': 'bat1', # list of str corresponding to battery assets (defined in parameter['system']['battery'])
            'genset': 'genset_1', # list of str correponsing to genset assets (defined in parameter['system']['genset'])
            'load_control': None, # str, list or None correponsing to genset assets (defined in parameter['system']['load_control'])
            'external_gen': 'external_gen_1'
        },
        'connections': [ # list of connected nodes, and line connecting them
            {
                'node': 'Node2', # str containing unique node_id of connected node
                'line': 'line_01' # str containing unique line_id of line connection nodes, (defined in parameter['network']['lines'])
            },
            {
                'node': 'Node4',
                'line': 'line_02'
            }
        ]
}


Note: Asset names are unique and can only be applied to a single node. If identical assets exist at different nodes, users must define these assets separately (e.g. battery1, battery2). Applying the same asset to multiple nodes using the same name will throw assert errors.

```

##### 13.3. Lines

###### Note: power-flow model under development. Outputs listed below may not be fully implemented in current release and are subject to change

A list of all line types used to connect nodes within the network. Each line object is composed of the following items:

* `line_id` [str] unique name used to identify the line type
* `power_capacity` [float] power capacity of line [kW]
* `length` [float] length of line [m]
* `resistance` [float] line resistance [unit]
* `inductance` [float] line inductance [unit]
* `ampacity` [float] line ampacity [unit]

An example line object:
```
example_line =  {
    'line_id': 'line_01',
    'power_capacity': 1500, 
    'length': 55,
    'resistance': 0,
    'inductance': 0,
    'ampacity': 0,
}
```

Note: Unlike DER assets, line-types are generic and can be applied to multiple node connections in duplicate without requiring multiple defined line types.