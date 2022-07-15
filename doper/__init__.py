"""
This is the DOPER main module.
"""

try:
    from .utility import *
    from .wrapper import *
    from .data.tariff import get_tariff
except Exception as e:
    print(f'ERROR importing internal DOPER functions:\n{e}')

__version__ = "0.2.1"
