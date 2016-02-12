#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

setup(
    name = 'pyramid_torque_engine_notifications',
    version = '0.0.1',
    description = 'Pyramid torque engine notification system based on nTorque based dual queue work engine system.',
    author = 'Andre Prado',
    author_email = 'username: andreprado88, domain: gmail.com',
    url = 'http://github.com/andrecp/pyramid_torque_engine_notifications',
    classifiers = [
        'Development Status :: 3 - Alpha',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: Public Domain',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Framework :: Pylons',
        'Topic :: Internet :: WWW/HTTP :: WSGI',
    ],
    packages = find_packages('src'),
    package_dir = {'': 'src'},
    include_package_data = True,
    zip_safe = False,
    install_requires=[
        'fysom',
        'pyramid_basemodel',
        'pyramid_simpleauth',
        'pyramid_torque_engine',
        'pyramid_postmark',
        'transaction',
        'zope.interface'
    ],
    tests_require = [
        'coverage',
        'nose',
        'mock'
    ],
    entry_points = {
        'console_scripts': [
            'pyramid_notification = pyramid_torque_engine_notifications.notification_executer:run'
        ]
    }
)
