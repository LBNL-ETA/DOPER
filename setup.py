"""
Setup file for the Distributed Optimal and Predictive Energy Resources.
"""

import os
import sys
import json
import setuptools
import subprocess as sp

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
    version = json.loads(f.read().split('__version__ = ')[1])

# setup solvers
if INSTALL_SOLVERS:
    print('Installing Solvers...')
    if not 'win' in sys.platform:
        sp.call('sh setup_solvers.sh', shell=True, cwd=os.path.join(root, 'doper', 'solvers'))
    else:
        print('WARNING: Solvers cannot be automatically installed on Windows. ' +\
            'Please download manually from https://ampl.com/dl/open and place in doper/solvers/Windows64.')

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
                  'doper': ['solvers/*',
                            'solvers/Linux64/*',
                            'solvers/Windows64/*',
                            'data/*']},
    include_package_data=True,
    python_requires=">=3.6",
    install_requires=install_requires
)
