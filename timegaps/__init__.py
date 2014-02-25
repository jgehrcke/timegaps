# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""Core data structures and functionality used by the timegaps program."""


__version__ = '0.1.0dev'
from .timegaps import FileSystemEntry, FilterItem, TimegapsError
from .timefilter import TimeFilter, TimeFilterError
