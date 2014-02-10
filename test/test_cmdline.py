# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys

# py.test runs tests in order of definition. This is useful for running simple,
# fundamental tests first and more complex tests later.
from py.test import raises, mark

# https://pypi.python.org/pypi/scripttest
from scripttest import TestFileEnvironment

#sys.path.insert(0, os.path.abspath('..'))
#from timegaps.timegaps import FileSystemEntry, TimegapsError, FilterItem
#from timegaps.timefilter import TimeFilter, _Timedelta, TimeFilterError


import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger("test_cmdline")
log.setLevel(logging.DEBUG)


RUNDIR = './cmdline-test-'

os.environ["PYTHONIOENCODING"] = "utf-8"

class TestBasic(object):
    """Test basic functionality.
    """
    def setup(self):
        self.env = TestFileEnvironment()

    def teardown(self):
        pass

    def run(self, *args, **kwargs):
        self.env.run("python", "../../timegaps.py", *args, **kwargs)

    def test_invalid_itempath_1(self):
        self.run("-v", "days5", "nofile")
