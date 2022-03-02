#!/usr/bin/env python
# -*- coding: utf-8 -*-

import pathlib
from setuptools import setup, find_packages
import pkg_resources


def get_install_requires():
    install_requires = []
    with pathlib.Path('requirements.txt').open() as requirements_txt:
        install_requires = [
            str(requirement)
            for requirement
            in pkg_resources.parse_requirements(requirements_txt)
        ]
    return install_requires


def setup_package():

    setup(
        name='nrn-modeldb-ci',
        version='0.0.1',
        packages=find_packages(),
        install_requires=get_install_requires(),
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
    )


if __name__ == "__main__":
    setup_package()
