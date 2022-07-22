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
    import doper
    tariff = doper.get_tariff('e19-2020')
    assert tariff['name'].startswith('PG&E E-19')
