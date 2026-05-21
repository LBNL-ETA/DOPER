"""
Post-install solver setup utilities.

This module intentionally avoids being executed from setup.py install hooks.
It should be called explicitly after package installation (e.g. via CLI entry point).
"""

import os
import sys
import subprocess as sp


def install_solvers():
    """Run bundled solver setup scripts from the installed package location."""
    solvers_dir = os.path.dirname(os.path.abspath(__file__))

    print(f'Installing Solvers in: {solvers_dir}')

    if 'win' not in sys.platform:
        clean_script = os.path.join(solvers_dir, 'clean_setup_solvers.sh')
        setup_script = os.path.join(solvers_dir, 'setup_solvers.sh')

        clean_result = sp.call(['sh', clean_script], cwd=solvers_dir)
        if clean_result != 0:
            raise RuntimeError(f'Solver cleanup failed with exit code {clean_result}.')

        result = sp.call(['sh', setup_script], cwd=solvers_dir)
    else:
        setup_script = os.path.join(solvers_dir, 'setup_solvers.bat')
        result = sp.call(setup_script, shell=True, cwd=solvers_dir)

    if result != 0:
        raise RuntimeError(f'Solver installation failed with exit code {result}.')

    print('Solver installation done.')


if __name__ == '__main__':
    install_solvers()