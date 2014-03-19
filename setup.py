# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


import re
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


timegapsversion = re.search(
    "^__version__\s*=\s*'(.*)'",
    open('timegaps/main.py').read(),
    re.M
    ).group(1)
assert timegapsversion


setup(
    name = "timegaps",
    packages = ["timegaps"],
    entry_points = {
        "console_scripts": ["timegaps = timegaps.main:main"]
        },
    version = timegapsversion,
    description = "Accept or reject items based on age categorization.",
    long_description=open("README.rst", "rb").read().decode('utf-8'),
    author = "Jan-Philip Gehrcke",
    author_email = "jgehrcke@googlemail.com",
    url = "http://gehrcke.de/timegaps",
    keywords = ["time", "categorization", "backup", "deletion"],
    platforms = ["POSIX", "Windows"],
    classifiers = [
        "Programming Language :: Python",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX",
        "Operating System :: Microsoft :: Windows",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
        "Topic :: System :: Archiving :: Backup",
        "Topic :: System :: Filesystems",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities",
        "Environment :: Console",
        "Intended Audience :: System Administrators",
        "Intended Audience :: End Users/Desktop",
        ],
    )
