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
