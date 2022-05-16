#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

install_requires = [
    # core
    'requests',
    'pyyaml',
    'docopt',
    'jinja2',
    'pyvirtualdisplay',

    # for running models
    'pyqt5',
    'ipython',
    'matplotlib',
    'scipy',
    '2to3',
]

with open('README.md', 'r', encoding='utf-8') as f:
    long_description = f.read()


def setup_package():

    setup(
        name='nrn-modeldb-ci',
        description='NEURON ModelDB CI tools',
        url='https://github.com/neuronsimulator/nrn-modeldb-ci',
        author='EPFL Blue Brain Project & Yale',
        author_email='alexandru.savulescu@epfl.ch',
        license='BSD-3-Clause',
        packages=find_packages(),
        use_scm_version=True,
        include_package_data=True,
        install_requires=install_requires,
        setup_requires=['setuptools_scm'],
        entry_points=dict(
            console_scripts=[
                'runmodels = modeldb.commands:runmodels',
                'getmodels = modeldb.commands:getmodels',
                'diffgout = modeldb.commands:diffgout',
                'modeldb-config = modeldb.commands:modeldb_config',
                'report2html = modeldb.commands:report2html',
                'diffreports2html = modeldb.commands:diffreports2html',
            ]
        ),
        long_description=long_description,
        long_description_content_type="text/markdown",
    )


if __name__ == "__main__":
    setup_package()
