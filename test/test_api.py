# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
from base64 import b64encode
from datetime import datetime
from itertools import chain
from random import randint, shuffle
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


# A simple valid filter rules dictionary .
DAY1 = {"days": 1}


def fsegen(ref, N_per_cat, max_timecount):
    N = N_per_cat
    c = max_timecount
    nowminusXyears =   (ref-60*60*24*365*i for i in nrandint(N, 1, c))
    nowminusXmonths =  (ref-60*60*24*30 *i for i in nrandint(N, 1, c))
    nowminusXweeks =   (ref-60*60*24*7  *i for i in nrandint(N, 1, c))
    nowminusXdays =    (ref-60*60*24    *i for i in nrandint(N, 1, c))
    nowminusXhours =   (ref-60*60       *i for i in nrandint(N, 1, c))
    nowminusXseconds = (ref-1           *i for i in nrandint(N, 1, c))
    times = chain(
        nowminusXyears,
        nowminusXmonths,
        nowminusXweeks,
        nowminusXdays,
        nowminusXhours,
        nowminusXseconds,
        )
    return (FileSystemEntryMock(modtime=t) for t in times)


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
        f = TimeFilter(rules=DAY1, reftime=t)
        assert f.reftime == t
        time.sleep(SHORTTIME)
        f = TimeFilter(rules=DAY1)
        assert f.reftime > t

    def test_invalid_rule_key(self):
        with raises(TimeFilterError):
            TimeFilter(rules={"days": 1, "wrong": 1})

    def test_invalid_rule_value(self):
        with raises(AssertionError):
            f = TimeFilter(rules={"days": None})

    def test_all_counts_zero(self):
        with raises(TimeFilterError):
            f = TimeFilter(rules={"days": 0})

    def test_emtpy_rules_dict(self):
        with raises(TimeFilterError):
            f = TimeFilter(rules={})

    def test_wrong_rules_type(self):
        with raises(AssertionError):
            f = TimeFilter(rules=None)

    def test_fillup_rules_default_rules(self):
        f = TimeFilter(rules={"days": 20})
        assert f.rules["days"] == 20
        for c in ("years", "months", "weeks", "hours", "recent"):
            assert f.rules[c] == 0


class TestTimeFilterFilter(object):
    """Test TimeFilter.filter method call signature.
    """
    def test_invalid_object(self):
        f = TimeFilter(rules=DAY1)
        with raises(AttributeError):
            # AttributeError: 'NoneType' object has no attribute 'modtime'
            f.filter([None])

    def test_not_iterable(self):
        f = TimeFilter(rules=DAY1)
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


class TestTimeFilterBasic(object):
    """Test TimeFilter logic and arithmetics with small, well-defined mock
    object lists.
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
        # Category 'overlap' must be possible (10 days > 1 week). Create
        # Having 15 FSEs, 1 to 15 days in age, the first 10 of them must be
        # accepted according to the 10-day-rule. The last 5 must be rejected.
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in xrange(1,16))
        fses = [FileSystemEntryMock(modtime=t) for t in nowminusXdays]
        rules = {"days": 10}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 10
        assert len(r) == 5
        #assert fses[:10] == a # This test makes an assumption about the order.
        for fse in fses[:10]:
            assert fse in a
        for fse in fses[10:]:
            assert fse in r

    def test_10_days_2_weeks(self):
        # Further define category 'overlap' behavior. {"days": 10, "weeks": 2}
        # -> week 0 is included in the 10 days, week 1 is only partially
        # included in the 10 days, and week 2 (14 days and older) is not
        # included in the 10 days.
        # Having 15 FSEs, 1 to 15 days in age, the first 10 of them must be
        # accepted according to the 10-day-rule. The 11th, 12th, 13th FSE (11,
        # 12, 13 days old) are categorized as 1 week old (their age A fulfills
        # 7 days <= A < 14 days). According to the 2-weeks-rule, the most
        # recent 1-week-old not affected by younger categories has to be
        # accepted, which is the 11th FSE. Also according to the 2-weeks-rule,
        # the most recent 2-week-old (not affected by a younger category, this
        # is always condition) has to be accepted, which is the 14th FSE.
        # In total FSEs 1-11,14 must be accepted, i.e. 12 FSEs. 15 FSEs are
        # used as input (1-15 days old), i.e. 3 are to be rejected (FSEs 12,
        # 13, 15).
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in xrange(1,16))
        fses = [FileSystemEntryMock(modtime=t) for t in nowminusXdays]
        rules = {"days": 10, "weeks": 2}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 12
        # Check if first 11 fses are in accepted list (order can be predicted
        # according to current implementation, but should not tested, as it is
        # not guaranteed according to the current specification).
        for fse in fses[:11]:
            assert fse in a
        # Check if 14th FSE is accepted.
        assert fses[13] in a
        # Check if FSEs 12, 13, 15 are rejected.
        assert len(r) == 3
        for i in (11, 12, 14):
            assert fses[i] in r


class TestTimeFilterMass(object):
    """Test TimeFilter logic and arithmetics with largish mock object lists.
    """
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_singlecat_rules(self):
        # Evaluate generator, store FSEs, shuffle FSEs (make sure order does
        # not play a role).
        now = time.time()
        N = 1000
        fses = list(fsegen(ref=now, N_per_cat=N, max_timecount=9))
        shuffle(fses)
        # In all likelihood, each time category is present with 9 different
        # values (1-9). Request 8 of them (1-8).
        # (Likelihood: dice with 9 eyes, N throws -- likelihood that there is
        #  at least one 1: 1 - (8/9)^N = 1 - 7E-52 for N == 1000)
        n = 8
        ryears = {"years": n}
        rmonths = {"months": n}
        rweeks = {"weeks": n}
        rdays = {"days": n}
        rhours = {"hours": n}
        rrecent = {"recent": n}
        # Run single-category filter on these fses.
        for rules in (ryears, rmonths, rweeks, rdays, rhours, rrecent):
            a, r = TimeFilter(rules, now).filter(fses)
            # There must be 8 accepted items (e.g. 8 in hour category).
            assert len(a) == n
            # There are 6 time categories, N items for each category, and only
            # n acceptances (for one single category), so N*6-n items must be
            # rejected.
            assert len(list(r)) == N * 6 - n

    def test_fixed_rules_week_month_overlap(self):
        now = time.time()
        N = 1000
        fses = list(fsegen(ref=now, N_per_cat=N, max_timecount=9))
        shuffle(fses)
        n = 8
        rules = {
            "years": n,
            "months": n,
            "weeks": n,
            "days": n,
            "hours": n,
            "recent": n
            }
        # See test_random_times_mass_singlecat_rules for likelihood discussion.
        # The rules say that we want 8 items accepted of each time category.
        # There are two time categories with a 'reducing overlap' in this case:
        # weeks and months. All other category pairs do not overlap at all or
        # overlap without reduction. Explanation/specification:
        # 8 hours:
        #   no overlap with days (0 days for all requested hours).
        # 8 days:
        #   day 7 and 8 could be categorized as 1 week, but become categorized
        #   within the days dict (7 and 8 days are requested per days-rule).
        #   Non-reducing overlap: 9 to 13 days are categorized as 1 week, which
        #   is requested, and 9-day-old items actually are in the data set.
        #   They are not affected by younger categories (than week) and end up
        #   in the 1-week-list.
        #   -> 8 items expected from each, the days and weeks categories.
        # 8 weeks:
        #   Items of age 8 weeks, i.e. 8*7 days = 56 days could be categorized
        #   as 1 month, but become categorized within the weeks dictionary
        #   (8 weeks old, which is requested per weeks-rule).
        #   Reducing overlap: 9-week-old items in the data set, which are not
        #   requested per weeks-rule are 9*7 days = 63 days old, i.e. 2 months
        #   (2 months are 2*30 days = 60 days). These 2-month-old items are
        #   not affected by younger data sets (than months), so
        #   they end up in the 2-months-list.
        #   -> In other words: there is no 1-month-list, since items of these
        #   ages are *entirely* consumed by the weeks-rule. The oldest item
        #   classified as 8 weeks old is already 2 months old:
        #   8.99~ weeks == 62.00~ days > 60 days == 2 months.
        #   -> the months-rule returns only 7 items (not 8, like the others)
        # 8 months:
        #   no overlap with years (0 years for all requested months)
        a, r = TimeFilter(rules, now).filter(fses)
        # 8 items for all categories except for months (7 items expected).
        assert len(a) == 6*8-1
        assert len(list(r)) == N*6 - (6*8-1)
