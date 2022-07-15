"""
DOPER install test module.
"""


import subprocess as sp

def test_install():
    """
    This is a test to verify the install of DOPER.
    """
    import doper
    solver = doper.get_solver('cbc')
    sp.check_output(f'{solver} exit', shell=True)

def test_tariff():
    """
    This is a test to verify the tariff module of DOPER.
    """
    #import doper
    #from doper.data.tariff import get_tariff
    #tariff = get_tariff('e19-2020')
    
    import os
    import doper
    solver = doper.get_solver('cbc')
    print(os.path.join(solver, '..', '..'))
    print(os.listdir(os.path.join(solver.replace('cbc', ''), '..', '..')))
    with open(os.path.join(solver.replace('cbc', ''), '..', '..', '__init__.py')) as f:
        print(f.read())
    
    tariff = doper.get_tariff('e19-2020')
    assert tariff['name'].startswith('PG&E E-19')
    
