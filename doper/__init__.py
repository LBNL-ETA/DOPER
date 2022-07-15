"""
This is the DOPER main module.
"""

try:
    from .data.tariff import get_tariff

    from .utility import *
    from .wrapper import *
    
except Exception as e:
    print(f'ERROR importing internal DOPER functions:\n{e}')

__version__ = "0.2.1"
