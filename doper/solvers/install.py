"""
Post-install solver setup utilities.

This module intentionally avoids being executed from setup.py install hooks.
It should be called explicitly after package installation (e.g. via CLI entry point).
"""

import os
import sys
import subprocess as sp
from subprocess import DEVNULL


def install_solvers(debug=False):
    """Run bundled solver setup scripts from the installed package location."""
    solvers_dir = os.path.dirname(os.path.abspath(__file__))
    stdio_kwargs = {} if debug else {'stdout': DEVNULL, 'stderr': DEVNULL}

    if 'win' not in sys.platform:
        clean_script = os.path.join(solvers_dir, 'clean_setup_solvers.sh')
        setup_script = os.path.join(solvers_dir, 'setup_solvers.sh')

        clean_result = sp.call(
            ['sh', clean_script],
            cwd=solvers_dir,
            **stdio_kwargs
        )
        if clean_result != 0:
            raise RuntimeError(f'Solver cleanup failed with exit code {clean_result}.')

        result = sp.call(
            ['sh', setup_script],
            cwd=solvers_dir,
            **stdio_kwargs
        )
    else:
        setup_script = os.path.join(solvers_dir, 'setup_solvers.bat')
        result = sp.call(
            setup_script,
            shell=True,
            cwd=solvers_dir,
            **stdio_kwargs
        )

    if result != 0:
        raise RuntimeError(f'Solver installation failed with exit code {result}.')


if __name__ == '__main__':
    install_solvers()