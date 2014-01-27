# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
from datetime import datetime
import tempfile

sys.path.insert(0, os.path.abspath('..'))
from timegaps import Filter, FileSystemEntry, TimegapsError

WINDOWS = sys.platform == "win32"

# py.test runs tests by order of definition. This is useful for running simple,
# fundamental tests first and more complex tests later.
from py.test import raises, mark

import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f [%(process)-5d]%(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)

#LONG = 999999
#SHORTTIME = 0.01
#ALMOSTZERO = 0.00001
#LONGERTHANBUFFER = "A" * 9999999


class TestBasicFSEntry(object):
    """Test basic FileSystemEntry logic.

    Upon creation, an FSE extracts information about the given path with a
    stat() system call via Python's `stat` module. From this data, the FSE
    populates itself with various convenient attributes.

    Flow for each test_method:
        o = TestClass()
        o.setup()
        try:
            o.test_method()
        finally:
            o.teardown()
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_invalid_path(self):
        fse = FileSystemEntry(path='gibtsgarantiertnichthier')
        assert fse is None

    def test_dir(self):
        fse = FileSystemEntry(path='.')
        assert fse.type == 'dir'
        assert isinstance(fse.modtime, datetime)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as t:
            fse = FileSystemEntry(path=t.name)
            assert fse.type == 'file'
            assert isinstance(fse.modtime, datetime)

    @mark.skipif('WINDOWS')
    def test_symlink(self):
        # set up symlink
        assert False
        fse.type == 'symlink'
        assert isinstance(fse.modtime, datetime)


class TestBasicFilter(object):
    """Test basic Filter logic.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_invalid_rule_key(self):
        with raises(TimegapsError):
            Filter(rules={"days": 1, "wrong": 1})

    def test_default_rules(self):
        f = Filter(rules={})
        assert f.rules["days"] == 10
        assert f.rules["years"] == 4
        assert f.rules["months"] == 12
        assert f.rules["weeks"] == 6
        assert f.rules["hours"] == 48
        assert f.rules["zerohours"] == 5

    def test_fillup_rules(self):
        f = Filter(rules={"days": 20})
        assert f.rules["days"] == 20

    def test_singlemsg_short_bin(self):
        fse = FileSystemEntry(
            path='',
            )
        f = Filter()
        accepted, rejected = f.filter([fse])
