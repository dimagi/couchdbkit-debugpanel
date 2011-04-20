#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
    name='couchdebugpanel',
    version='0.0.1',
    description='A CouchDBkit panel for the django debug toolbar',
    author='Dimagi',
    author_email='information@dimagi.com',
    url='http://www.dimagi.com/',
    packages = find_packages(exclude=['*.pyc']),
    include_package_data = True,
    install_requires = [
        "restkit", "couchdbkit", "django-debug-toolbar",
    ],
)

