# -*- coding: utf-8 -*-
"""
Created on Fri Jan  8 12:54:45 2021

@author: nicholas
"""

#assert not ((timestep_scale != 1) and (parameter['site']['regulation'])), \
    assert not ((int(np.array([model.timestep[k] for k in sorted(model.timestep.keys())[1:]]).mean() /60/60) != 1) and (parameter['site']['regulation'])), \
        "Regulation is only supported for hourly timesteps. Please set parameter['site']['regulation'] = False."
    assert not (parameter['site']['regulation_reserved'] and parameter['site']['regulation_symmetric']), \
        "Please disable parameter['site']['regulation_symmetric'] when parameter['site']['regulation_reserved'] is used." 
    assert not (parameter['site']['regulation_xor'] and parameter['site']['regulation_symmetric']), \
        "Please slect either parameter['site']['regulation_xor'] or parameter['site']['regulation_symmetric']."