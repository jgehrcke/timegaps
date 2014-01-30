# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
from base64 import b64encode
from datetime import datetime
import tempfile

sys.path.insert(0, os.path.abspath('..'))
from timegaps import Filter, FileSystemEntry, TimegapsError, _Timedelta

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


def randstring_fssafe():
    return b64encode(os.urandom(6)).replace('/','!')


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
        fse = FileSystemEntry(path="gibtsgarantiertnichthier")
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
        linkname = "/tmp/%s" % randstring_fssafe()
        try:
            os.symlink("target", linkname)
            fse = FileSystemEntry(path=linkname)
        finally:
            os.unlink(linkname)
        assert fse.type == 'symlink'
        assert isinstance(fse.modtime, datetime)


class TestBasicFilter(object):
    """Test basic Filter logic.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_reftime(self):
        t = time.time()
        f = Filter(reftime=t)
        assert f.reftime == t
        f = Filter()
        assert f.reftime >= t

    def test_invalid_rule_key(self):
        with raises(TimegapsError):
            Filter(rules={"days": 1, "wrong": 1})

    def test_default_rules1(self):
        f = Filter(rules={})
        assert f.rules["days"] == 10
        assert f.rules["years"] == 4
        assert f.rules["months"] == 12
        assert f.rules["weeks"] == 6
        assert f.rules["hours"] == 48
        assert f.rules["zerohours"] == 5

    def test_default_rules2(self):
        f = Filter()
        assert f.rules["days"] == 10
        assert f.rules["years"] == 4
        assert f.rules["months"] == 12
        assert f.rules["weeks"] == 6
        assert f.rules["hours"] == 48
        assert f.rules["zerohours"] == 5

    def test_fillup_rules(self):
        f = Filter(rules={"days": 20})
        assert f.rules["days"] == 20

    def test_no_fses(self):
        fse = FileSystemEntry(path="gibtsgarantiertnichthier")
        assert fse is None
        f = Filter()
        with raises(TimegapsError):
            f.filter([fse])


class TestTimedelta(object):
    """Test Timedelta logic and arithmetic.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_floatdiff(self):
        # Difference of time `t` and reference must be float.
        with raises(AssertionError):
            _Timedelta(t=0, ref=0)

    def test_future(self):
        # Time `t` later than reference.
        with raises(TimegapsError):
            _Timedelta(t=1.0, ref=0)

    def test_types_math_year(self):
        year_seconds =  60 * 60 * 24 * 365
        d = _Timedelta(t=0.0, ref=year_seconds)
        assert d.years == 1
        assert isinstance(d.years, int)
        assert d.years_exact == 1.0
        assert isinstance(d.years_exact, float)
        assert d.months == 12
        assert isinstance(d.months, int)
        assert d.months_exact == 365.0 / 30
        assert isinstance(d.months_exact, float)
        assert d.weeks == 52
        assert isinstance(d.weeks, int)
        assert d.weeks_exact == 365.0 / 7
        assert isinstance(d.weeks_exact, float)
        assert d.days == 365
        assert isinstance(d.days, int)
        assert d.days_exact == 365.0
        assert isinstance(d.days_exact, float)
        assert d.hours == 365 * 24
        assert isinstance(d.hours, int)
        assert d.hours_exact == 365 * 24.0
        assert isinstance(d.hours_exact, float)

    def test_types_math_hour(self):
        hour_seconds =  60 * 60
        d = _Timedelta(t=0.0, ref=hour_seconds)
        assert d.years == 0
        assert isinstance(d.years, int)
        assert d.years_exact == 1.0 / (365 * 24)
        assert isinstance(d.years_exact, float)
        assert d.months == 0
        assert isinstance(d.months, int)
        assert d.months_exact == 1.0 / (30 * 24)
        assert isinstance(d.months_exact, float)
        assert d.weeks == 0
        assert isinstance(d.weeks, int)
        assert d.weeks_exact == 1.0 / (7 * 24)
        assert isinstance(d.weeks_exact, float)
        assert d.days == 0
        assert isinstance(d.days, int)
        assert d.days_exact == 1.0 / 24
        assert isinstance(d.days_exact, float)
        assert d.hours == 1
        assert isinstance(d.hours, int)
        assert d.hours_exact == 1.0
        assert isinstance(d.hours_exact, float)
