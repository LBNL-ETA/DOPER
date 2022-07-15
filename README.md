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

## Example
To illustrate the DOPER functionality, example Jupyter notebooks can be found [here](https://github.com/LBNL-ETA/DOPER/blob/master/examples/).

[Test 1](https://github.com/LBNL-ETA/DOPER/blob/master/examples/Test1.ipynb) *In development*.

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