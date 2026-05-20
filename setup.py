"""
Setup file for the Distributed Optimal and Predictive Energy Resources.
"""

import os
import sys
import json
import setuptools
import subprocess as sp
from setuptools.command.install import install
from setuptools.command.develop import develop

root = os.path.dirname(os.path.abspath(__file__))

INSTALL_SOLVERS = True

# description
with open('README.md', 'r', encoding='utf8') as f:
    long_description = f.read()

# requirements
with open('requirements.txt', 'r', encoding='utf8') as f:
    install_requires = f.read().splitlines()

# version
with open('doper/__init__.py', 'r', encoding='utf8') as f:
    version = json.loads(f.read().split('__version__ = ')[1].split('\n')[0])

def install_solvers():
    print('Installing Solvers...')
    solvers_dir = os.path.join(root, 'doper', 'solvers')

    if not 'win' in sys.platform:
        clean_result = sp.call(['sh', 'clean_setup_solvers.sh'], cwd=solvers_dir)
        if clean_result != 0:
            raise RuntimeError(f'Solver cleanup failed with exit code {clean_result}.')

        result = sp.call(['sh', 'setup_solvers.sh'], cwd=solvers_dir)
    else:
        result = sp.call('setup_solvers.bat', shell=True, cwd=solvers_dir)

    if result != 0:
        raise RuntimeError(f'Solver installation failed with exit code {result}.')

    print('done.')


class InstallCommand(install):
    def run(self):
        super().run()
        if INSTALL_SOLVERS:
            install_solvers()


class DevelopCommand(develop):
    def run(self):
        super().run()
        if INSTALL_SOLVERS:
            install_solvers()


setuptools.setup(
    name="DOPER",
    version=version,
    author="Gehbauer, Christoph",
    description="Distributed Optimal and Predictive Energy Resources",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license_files = ['license.txt'],
    url="https://github.com/LBNL-ETA/DOPER",
    project_urls={
        "Bug Tracker": "https://github.com/LBNL-ETA/DOPER/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    packages=['doper'],
    package_data={'': ['*.txt.', '*.md'], 
                  'doper': ['models/*',
                            'solvers/*',
                            'solvers/Linux64/*',
                            'solvers/Windows64/*',
                            'data/*',
                            'examples/*',
                            'resources/*',
                            'resources/pvlib/*']},
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=install_requires,
    cmdclass={
        'install': InstallCommand,
        'develop': DevelopCommand,
    },
)
