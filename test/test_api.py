# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
from base64 import b64encode
from datetime import datetime
from itertools import chain
from random import randint
import collections
import tempfile

sys.path.insert(0, os.path.abspath('..'))
from timegaps.timegaps import FileSystemEntry, TimegapsError
from timegaps.timefilter import TimeFilter, _Timedelta, TimeFilterError

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
SHORTTIME = 0.01
#ALMOSTZERO = 0.00001
#LONGERTHANBUFFER = "A" * 9999999


class FileSystemEntryMock(FileSystemEntry):
    def __init__(self, modtime):
        self.modtime = modtime

    def __str__(self):
        return "%s(moddate: %s)" % (self.__class__.__name__, self.moddate)

    def __repr__(self):
        return "%s(modtime=%s)" % (self.__class__.__name__, self.modtime)


def nrandint(n, min, max):
    for _ in xrange(n):
        yield randint(min, max)


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
        with raises(OSError):
            fse = FileSystemEntry(path="gibtsgarantiertnichthier")

    def test_dir(self):
        fse = FileSystemEntry(path='.')
        assert fse.type == 'dir'
        assert isinstance(fse.moddate, datetime)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as t:
            fse = FileSystemEntry(path=t.name)
            assert fse.type == 'file'
            assert isinstance(fse.moddate, datetime)

    @mark.skipif('WINDOWS')
    def test_symlink(self):
        linkname = "/tmp/%s" % randstring_fssafe()
        try:
            os.symlink("target", linkname)
            fse = FileSystemEntry(path=linkname)
        finally:
            os.unlink(linkname)
        assert fse.type == 'symlink'
        assert isinstance(fse.moddate, datetime)


class TestTimeFilterInit(object):
    """Test TimeFilter initialization logic.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_reftime(self):
        t = time.time()
        f = TimeFilter(reftime=t)
        assert f.reftime == t
        time.sleep(SHORTTIME)
        f = TimeFilter()
        assert f.reftime > t

    def test_invalid_rule_key(self):
        with raises(TimeFilterError):
            TimeFilter(rules={"days": 1, "wrong": 1})

    def test_default_rules(self):
        with raises(TimeFilterError):
            f = TimeFilter(rules={})
        f = TimeFilter(rules={"days": 1})
        for c in ("years", "months", "weeks", "hours", "recent"):
            assert f.rules[c] == 0
        assert f.rules["days"] == 1

    def test_fillup_rules(self):
        f = TimeFilter(rules={"days": 20})
        assert f.rules["days"] == 20
        for c in ("years", "months", "weeks", "hours", "recent"):
            assert f.rules[c] == 0

    def test_invalid_object(self):
        f = TimeFilter()
        with raises(AttributeError):
            # AttributeError: 'NoneType' object has no attribute 'modtime'
            f.filter([None])

    def test_not_iterable(self):
        f = TimeFilter()
        with raises(TypeError):
            # TypeError: 'NoneType' object is not iterable
            f.filter(None)


class TestTimedelta(object):
    """Test Timedelta logic and arithmetic.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_wrongtypes(self):
        with raises(TypeError):
            # unsupported operand type(s) for -: 'str' and 'NoneType'
            _Timedelta(t=None, ref="a")

    def test_floatdiff(self):
        # Difference of time `t` and reference must be float.
        with raises(AssertionError):
            _Timedelta(t=0, ref=0)

    def test_future(self):
        # Time `t` later than reference.
        with raises(TimeFilterError):
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


class TestTimeFilter(object):
    """Test TimeFilter logic and arithmetics.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_minimal_functionality_and_types(self):
        # Create filter with reftime NOW (if not specified otherwise)
        # and simple rules.
        f = TimeFilter(rules={"hours": 1})
        # Create mock that is 1.5 hours old. Must end up in accepted list,
        # since it's 1 hour old and one item should be kept from the 1-hour-
        # old-category
        fse = FileSystemEntryMock(modtime=time.time()-60*60*1.5)
        a, r = f.filter(objs=[fse])
        # http://stackoverflow.com/a/1952655/145400
        assert isinstance(a, collections.Iterable)
        assert isinstance(r, collections.Iterable)
        assert a[0] == fse
        # Rejected list `r` is expected to be an interator, so convert to
        # list before evaluating length.
        assert len(list(r)) == 0

    def test_hours_one_accepted_one_rejected(self):
        f = TimeFilter(rules={"hours": 1})
        fse1 = FileSystemEntryMock(modtime=time.time()-60*60*1.5)
        fse2 = FileSystemEntryMock(modtime=time.time()-60*60*1.6)
        a, r = f.filter(objs=[fse1, fse2])
        r = list(r)
        # The younger one must be accepted.
        assert a[0] == fse1
        assert len(a) == 1
        assert r[0] == fse2
        assert len(r) == 1

    def test_two_recent(self):
        fse1 = FileSystemEntryMock(modtime=time.time())
        time.sleep(SHORTTIME)
        fse2 = FileSystemEntryMock(modtime=time.time())
        # fse2 is a little younger than fse1.
        time.sleep(SHORTTIME) # Make sure ref is newer than fse2.modtime.
        a, r = TimeFilter(rules={"recent": 1}).filter(objs=[fse1, fse2])
        r = list(r)
        # The younger one must be accepted.
        assert a[0] == fse2
        assert len(a) == 1
        assert r[0] == fse1
        assert len(r) == 1

    def test_2_recent_10_allowed(self):
        # Request to keep more than available.
        fse1 = FileSystemEntryMock(modtime=time.time())
        time.sleep(SHORTTIME)
        fse2 = FileSystemEntryMock(modtime=time.time())
        time.sleep(SHORTTIME)
        a, r = TimeFilter(rules={"recent": 10}).filter(objs=[fse1, fse2])
        r = list(r)
        # All should be accepted. Within `recent` category,
        # items must be sorted by modtime, with the newest element being the
        # last element.
        assert a[0] == fse1
        assert a[1] == fse2
        assert len(a) == 2
        assert len(r) == 0

    def test_2_years_10_allowed_past(self):
        # Request to keep more than available.
        # Produce one 9 year old, one 10 year old, keep 10 years.
        nowminus10years = time.time() - (60*60*24*365 * 10 + 1)
        nowminus09years = time.time() - (60*60*24*365 *  9 + 1)
        fse1 = FileSystemEntryMock(modtime=nowminus10years)
        fse2 = FileSystemEntryMock(modtime=nowminus09years)
        a, r = TimeFilter(rules={"years": 10}).filter(objs=[fse1, fse2])
        r = list(r)
        # All should be accepted.
        assert len(a) == 2
        assert len(r) == 0

    def test_2_years_10_allowed_recent(self):
        # Request to keep more than available.
        # Produce one 1 year old, one 2 year old, keep 10 years.
        nowminus10years = time.time() - (60*60*24*365 * 2 + 1)
        nowminus09years = time.time() - (60*60*24*365 * 1 + 1)
        fse1 = FileSystemEntryMock(modtime=nowminus10years)
        fse2 = FileSystemEntryMock(modtime=nowminus09years)
        a, r = TimeFilter(rules={"years": 10}).filter(objs=[fse1, fse2])
        r = list(r)
        # All should be accepted.
        assert len(a) == 2
        assert len(r) == 0

    def test_2_years_2_allowed(self):
        # Request to keep more than available.
        # Produce one 1 year old, one 2 year old, keep 10 years.
        nowminus10years = time.time() - (60*60*24*365 * 2 + 1)
        nowminus09years = time.time() - (60*60*24*365 * 1 + 1)
        fse1 = FileSystemEntryMock(modtime=nowminus10years)
        fse2 = FileSystemEntryMock(modtime=nowminus09years)
        a, r = TimeFilter(rules={"years": 2}).filter(objs=[fse1, fse2])
        r = list(r)
        # All should be accepted.
        assert len(a) == 2
        assert len(r) == 0

    def test_all_categories_1acc_1rej(self):
        now = time.time()
        nowminus1year = now -  (60*60*24*365 * 1 + 1)
        nowminus1month = now - (60*60*24*30  * 1 + 1)
        nowminus1week = now -  (60*60*24*7   * 1 + 1)
        nowminus1day = now -   (60*60*24     * 1 + 1)
        nowminus1hour = now -  (60*60        * 1 + 1)
        nowminus1second = now - 1
        nowminus2year = now -  (60*60*24*365 * 2 + 1)
        nowminus2month = now - (60*60*24*30  * 2 + 1)
        nowminus2week = now -  (60*60*24*7   * 2 + 1)
        nowminus2day = now -   (60*60*24     * 2 + 1)
        nowminus2hour = now -  (60*60        * 2 + 1)
        nowminus2second = now - 2
        atimes = (
            nowminus1year,
            nowminus1month,
            nowminus1week,
            nowminus1day,
            nowminus1hour,
            nowminus1second,
            )
        rtimes = (
            nowminus2year,
            nowminus2month,
            nowminus2week,
            nowminus2day,
            nowminus2hour,
            nowminus2second,
            )
        afses = [FileSystemEntryMock(modtime=t) for t in atimes]
        rfses = [FileSystemEntryMock(modtime=t) for t in rtimes]
        cats = ("days", "years", "months", "weeks", "hours", "recent")
        rules = {c:1 for c in cats}
        a, r = TimeFilter(rules, now).filter(chain(afses, rfses))
        r = list(r)
        # All nowminus1* must be accepted, all nowminus2* must be rejected.
        assert len(a) == 6
        for fse in afses:
            assert fse in a
        for fse in rfses:
            assert fse in r
        assert len(r) == 6

    def test_10_days(self):
        # Category 'overlap' must be possible (10 days > 1 week).
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in xrange(1,15))
        fses = (FileSystemEntryMock(modtime=t) for t in nowminusXdays)
        rules = {"days": 10}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 10
        print a

    def test_random_times_fixed_rules(self):
        now = time.time()
        N = 20000
        return
        #print (list(nrandint(100, 0, 17)))
        #return
        def fsegen():
            nowminusXyears =   (now-60*60*24*365*i for i in nrandint(N, 1, 17))
            nowminusXmonths =  (now-60*60*24*30 *i for i in nrandint(N, 1, 11))
            nowminusXweeks =   (now-60*60*24*7  *i for i in nrandint(N, 1, 3))
            nowminusXdays =    (now-60*60*24    *i for i in nrandint(N, 1, 6))
            nowminusXhours =   (now-60*60       *i for i in nrandint(N, 1, 17))
            nowminusXseconds = (now-1           *i for i in nrandint(N, 1, 17))
            times = chain(
                nowminusXyears,
                nowminusXmonths,
                nowminusXweeks,
                nowminusXdays,
                nowminusXhours,
                nowminusXseconds,
                )
            return (FileSystemEntryMock(modtime=t) for t in times)
        n = 15
        rules = {
            "years": 0,
            "months": 0,
            "weeks": 0,
            "days": 0,
            "hours": 0,
            "recent": 0
            }
        # Perform categorizing 10 times with different sets of randomly
        # generated fses.
        for _ in xrange(1):
            a, r = TimeFilter(rules, now).filter(fsegen())
            r = list(r)
            assert len(a) + len(r) == 6 * N
            assert len(a) <= n * 6
            print len(a)