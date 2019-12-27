# -*- coding: utf-8 -*-


from setuptools import setup, find_packages
import os

requirement = ['watchdog',
               'mylogger',
]
description = 'Observe changes on specified directories. Import watchdog_dir.event'


with open('README.rst') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

setup(
    name='watchdog_dir',
    version='1.0',
    description=description,
    long_description=readme,
    author='Takeki Shikano',
    author_email='',
    require=requirement,
    url=None,
    license='MIT',
    packages=find_packages(exclude=('tests', 'docs')),
    package_data={'watchdog_dir': ['config/watchdog_dir.conf']}
)


