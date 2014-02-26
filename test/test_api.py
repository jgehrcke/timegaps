# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""
Test timegaps.timegaps and timegaps.timefilter API. Most importantly, this
module tests the time categorization logic.
"""


from __future__ import unicode_literals
import os
import sys
import time
from base64 import b64encode
from datetime import datetime
from itertools import chain
from random import randint, shuffle
import collections
import tempfile


# Make the same code base run with Python 2 and 3.
if sys.version < '3':
    range = xrange
else:
    pass


# py.test runs tests in order of definition. This is useful for running simple,
# fundamental tests first and more complex tests later.
from py.test import raises, mark


sys.path.insert(0, os.path.abspath('..'))
from timegaps.timegaps import FileSystemEntry, TimegapsError, FilterItem
from timegaps.timefilter import TimeFilter, _Timedelta, TimeFilterError


import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


WINDOWS = sys.platform == "win32"
SHORTTIME = 0.01


def nrndint(n, imin, imax):
    for _ in range(n):
        yield randint(imin, imax)


def randstring_fssafe():
    return b64encode(os.urandom(6)).replace(b'/', b'!')


def fsegen(ref, N_per_cat, max_timecount):
    N = N_per_cat
    c = max_timecount
    nowminusXyears =   (ref - 60 * 60 * 24 * 365 * i for i in nrndint(N, 1, c))
    nowminusXmonths =  (ref - 60 * 60 * 24 * 30  * i for i in nrndint(N, 1, c))
    nowminusXweeks =   (ref - 60 * 60 * 24 * 7   * i for i in nrndint(N, 1, c))
    nowminusXdays =    (ref - 60 * 60 * 24       * i for i in nrndint(N, 1, c))
    nowminusXhours =   (ref - 60 * 60            * i for i in nrndint(N, 1, c))
    nowminusXseconds = (ref - 1                  * i for i in nrndint(N, 1, c))
    times = chain(
        nowminusXyears,
        nowminusXmonths,
        nowminusXweeks,
        nowminusXdays,
        nowminusXhours,
        nowminusXseconds,
        )
    return (FilterItem(modtime=t) for t in times)


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
            FileSystemEntry(path="gibtsgarantiertnichthier")

    def test_dir(self):
        fse = FileSystemEntry(path=".")
        assert fse.type == "dir"
        assert isinstance(fse.moddate, datetime)

    def test_file(self):
        with tempfile.NamedTemporaryFile() as t:
            fse = FileSystemEntry(path=t.name)
            assert fse.type == "file"
            assert isinstance(fse.moddate, datetime)

    def test_custom_modtime(self):
        with tempfile.NamedTemporaryFile() as t:
            fse = FileSystemEntry(path=t.name, modtime=1.0)
            assert fse.type == "file"
            assert isinstance(fse.moddate, datetime)

    def test_custom_modtime_wrongtype(self):
        with tempfile.NamedTemporaryFile() as t:
            with raises(TimegapsError):
                FileSystemEntry(path=t.name, modtime=1)
            with raises(TimegapsError):
                FileSystemEntry(path=t.name, modtime="foo")

    @mark.skipif("WINDOWS")
    def test_symlink(self):
        linkname = "/tmp/%s" % randstring_fssafe()
        try:
            os.symlink("target", linkname)
            fse = FileSystemEntry(path=linkname)
        finally:
            os.unlink(linkname)
        assert fse.type == "symlink"
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
        f = TimeFilter(rules={"days": 1}, reftime=t)
        assert f.reftime == t
        time.sleep(SHORTTIME)
        f = TimeFilter(rules={"days": 1})
        assert f.reftime > t

    def test_invalid_rule_key(self):
        with raises(TimeFilterError):
            TimeFilter(rules={"days": 1, "wrong": 1})

    def test_invalid_rule_value(self):
        with raises(AssertionError):
            TimeFilter(rules={"days": None})

    def test_all_counts_zero(self):
        with raises(TimeFilterError):
            TimeFilter(rules={"days": 0})

    def test_one_count_negative(self):
        with raises(TimeFilterError):
            TimeFilter(rules={"days": -1})

    def test_emtpy_rules_dict(self):
        with raises(TimeFilterError):
            TimeFilter(rules={})

    def test_wrong_rules_type(self):
        with raises(AssertionError):
            TimeFilter(rules=None)

    def test_fillup_rules_default_rules(self):
        f = TimeFilter(rules={"days": 20})
        assert f.rules["days"] == 20
        for c in ("years", "months", "weeks", "hours", "recent"):
            assert f.rules[c] == 0


class TestTimeFilterFilterSig(object):
    """Test TimeFilter.filter method call signature.
    """
    def test_invalid_object(self):
        f = TimeFilter(rules={"days": 1})
        with raises(AttributeError):
            # AttributeError: 'NoneType' object has no attribute 'modtime'
            f.filter([None])

    def test_not_iterable(self):
        f = TimeFilter(rules={"days": 1})
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
        fse = FilterItem(modtime=time.time()-60*60*1.5)
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
        fse1 = FilterItem(modtime=time.time()-60*60*1.5)
        fse2 = FilterItem(modtime=time.time()-60*60*1.6)
        a, r = f.filter(objs=[fse1, fse2])
        r = list(r)
        # The younger one must be accepted.
        assert a[0] == fse1
        assert len(a) == 1
        assert r[0] == fse2
        assert len(r) == 1

    def test_two_recent(self):
        fse1 = FilterItem(modtime=time.time())
        time.sleep(SHORTTIME)
        fse2 = FilterItem(modtime=time.time())
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
        fse1 = FilterItem(modtime=time.time())
        time.sleep(SHORTTIME)
        fse2 = FilterItem(modtime=time.time())
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
        fse1 = FilterItem(modtime=nowminus10years)
        fse2 = FilterItem(modtime=nowminus09years)
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
        fse1 = FilterItem(modtime=nowminus10years)
        fse2 = FilterItem(modtime=nowminus09years)
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
        fse1 = FilterItem(modtime=nowminus10years)
        fse2 = FilterItem(modtime=nowminus09years)
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
        afses = [FilterItem(modtime=t) for t in atimes]
        rfses = [FilterItem(modtime=t) for t in rtimes]
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

    def test_10_days_overlap(self):
        # Category 'overlap' must be possible (10 days > 1 week).
        # Having 15 FSEs, 1 to 15 days in age, the first 10 of them must be
        # accepted according to the 10-day-rule. The last 5 must be rejected.
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXdays]
        rules = {"days": 10}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 10
        assert len(r) == 5
        for fse in fses[:10]:
            assert fse in a
        for fse in fses[10:]:
            assert fse in r

    def test_10_days_order(self):
        # Having 15 FSEs, 1 to 15 days in age, the first 10 of them must be
        # accepted according to the 10-day-rule. The last 5 must be rejected.
        # This test is focused on the right internal ordering when making the
        # decision to accept or reject an item. The newest ones are expected to
        # be accepted, while the oldest ones are expected to be rejected.
        # In order to test robustness against input order, the list of mock
        # FSEs is shuffled before filtering. The filtering and checks are
        # repeated a couple of times.
        # It is tested whether all of the youngest 10 FSEs are accepted. It is
        # not tested if these 10 FSEs have a certain order within the accepted-
        # list, because we don't make any guarantees about the
        # accepted-internal ordering.
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXdays]
        rules = {"days": 10}
        shuffledfses = fses[:]
        for _ in range(100):
            shuffle(shuffledfses)
            a, r = TimeFilter(rules, now).filter(shuffledfses)
            r = list(r)
            assert len(a) == 10
            assert len(r) == 5
            for fse in fses[:10]:
                assert fse in a
            for fse in fses[10:]:
                assert fse in r

    def test_create_recent_allow_old(self):
        now = time.time()
        nowminusXseconds = (now - (i + 1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXseconds]
        rules = {"years": 1}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 0
        assert len(r) == 15

    def test_create_old_allow_recent(self):
        # Create a few old items, between 1 and 15 years. Then only request one
        # recent item. This discovered a mean bug, where items to be rejected
        # ended up in the recent category.
        now = time.time()
        nowminusXyears = (now-(60*60*24*365 * i + 1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXyears]
        rules = {"recent": 1}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 0
        assert len(r) == 15

    def test_create_recent_dont_request_recent(self):
        # Create a few young items (recent ones). Then don't request any.
        now = time.time()
        nowminusXseconds = (now - (i + 1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXseconds]
        rules = {"years": 1, "recent": 0}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 0
        assert len(r) == 15

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
        nowminusXdays = (now-(60*60*24*i+1) for i in range(1, 16))
        fses = [FilterItem(modtime=t) for t in nowminusXdays]
        rules = {"days": 10, "weeks": 2}
        a, r = TimeFilter(rules, now).filter(fses)
        r = list(r)
        assert len(a) == 12
        # Check if first 11 fses are in accepted list (order can be predicted
        # according to current implementation, but should not be tested, as it
        # is not guaranteed according to the current specification).
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
    now = time.time()
    N = 1200
    # In all likelihood, each time category is present with 9 different
    # timecount values (1-9). Probability for occurrence of at least 1 item of
    # e.g. value 2: 1 - (8/9)^N = 1 - 4E-62 for N == 1200
    fses9 = list(fsegen(ref=now, N_per_cat=N, max_timecount=9))
    shuffle(fses9)
    # Probability: 1 - (61/62)^N = 1 - 3E-9 for N == 1200
    fses62 = list(fsegen(ref=now, N_per_cat=N, max_timecount=62))
    shuffle(fses62)
    def setup(self):
        pass

    def teardown(self):
        pass

    def test_singlecat_rules(self):
        n = 8
        ryears = {"years": n}
        rmonths = {"months": n}
        rweeks = {"weeks": n}
        rdays = {"days": n}
        rhours = {"hours": n}
        rrecent = {"recent": n}
        # Run single-category filter on these fses.
        for rules in (ryears, rmonths, rweeks, rdays, rhours, rrecent):
            a, r = TimeFilter(rules, self.now).filter(self.fses9)
            # There must be 8 accepted items (e.g. 8 in hour category).
            assert len(a) == n
            # There are 6 time categories, N items for each category, and only
            # n acceptances (for one single category), so N*6-n items must be
            # rejected.
            assert len(list(r)) == self.N * 6 - n

    def test_fixed_rules_week_month_overlap(self):
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
        #   'Younger' categories can steal from older ones. The 'recent'
        #   cat cannot steal anything:
        #   -> 8 items expected for the hours category.
        #   category. 8 hours have no overlap with days (8 hours are 0 days),
        #   so the hours category cannot steal from the days category
        #   -> 8 items expected for the days category.
        # 8 days:
        #   day 7 and 8 could be categorized as 1 week, but become categorized
        #   within the days dict (7 and 8 days are requested per days-rule).
        #   Non-reducing overlap: 9 to 13 days are categorized as 1 week, which
        #   is requested, and 9-day-old items actually are in the data set.
        #   They are not stolen by younger categories (than week) and end up
        #   in the 1-week-list.
        #   -> 8 items expected from the weeks category.
        # 8 weeks:
        #   1-month-olds are all stolen by the 8-weeks-rule.
        #   Items of age 8 weeks, i.e. 8*7 days = 56 days could be categorized
        #   as 1 month, but become categorized within the weeks dictionary
        #   (8 weeks old, which is requested per weeks-rule).
        #   Reducing overlap: 9-week-old items in the data set, which are not
        #   requested per weeks-rule are 9*7 days = 63 days old, i.e. 2 months
        #   (2 months are 2*30 days = 60 days). These 2-month-old items are
        #   not affected by younger data sets (than months), so they end up in
        #   the 2-months-list.
        #   -> In other words: there is no 1-month-list, since items of these
        #   ages are *entirely* consumed by the weeks-rule. The oldest item
        #   classified as 8 weeks old is already 2 months old:
        #   8.99~ weeks == 62.00~ days > 60 days == 2 months.
        #   -> the months-rule returns only 7 items (not 8, like the others)
        # 8 months:
        #   no overlap with years (0 years for all requested months)
        a, r = TimeFilter(rules, self.now).filter(self.fses9)
        # 8 items for all categories except for months (7 items expected).
        assert len(a) == 6*8-1
        assert len(list(r)) == self.N*6 - (6*8-1)

    def test_fixed_rules_days_months_overlap(self):
        rules = {
            "years": 0,
            "months": 2,
            "weeks": 0,
            "days": 62,
            "hours": 0,
            "recent": 0
            }
        a, r = TimeFilter(rules, self.now).filter(self.fses62)
        # 62 items are expected as of the 62-days-rule. No item is expected
        # for 1-month-categorization. One item is expected for 2-month-catego-
        # rization: items between 60 an 90 days can be categorized as 2 months
        # old. A 9-week-old is in the data set, i.e. 63 days old, i.e. it's not
        # collected by the 62-days rule, so it ends up being categorized as
        # 2 months old.
        assert len(a) == 63
        assert len(list(r)) == self.N*6 - (63)

    def test_1_day(self):
        rules = {"days": 1}
        a, r = TimeFilter(rules, self.now).filter(self.fses9)
        assert len(a) == 1
        assert len(list(r)) == self.N*6 - 1

    def test_1_recent_1_years(self):
        rules = {
            "years": 1,
            "recent": 1
            }
        a, r = TimeFilter(rules, self.now).filter(self.fses9)
        assert len(a) == 2
        assert len(list(r)) == self.N*6 - 2

    def test_realistic_scheme(self):
        rules = {
            "years": 4,
            "months": 12,
            "weeks": 6,
            "days": 10,
            "hours": 48,
            "recent": 5
            }
        a, r = TimeFilter(rules, self.now).filter(self.fses62)
        # 4+12+6+10+48+5 = 85; there is 1 reducing overlap between hours and
        # days -> 84 accepted items are expected.
        assert len(a) == 84
        assert len(list(r)) == self.N*6 - 84
