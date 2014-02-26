# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""
timegaps.timefilter -- generic time categorization logic as used by timegaps.
"""


from __future__ import unicode_literals
import time
import logging
from itertools import chain
from collections import defaultdict
from collections import OrderedDict


log = logging.getLogger("timefilter")


class TimeFilterError(Exception):
    pass


class TimeFilter(object):
    """Represents certain time filtering rules. Allows for filtering objects
    providing a `modtime` attribute.
    """
    # Define valid categories in order from past to future (old -> young).
    valid_categories = ("years", "months", "weeks", "days", "hours", "recent")

    def __init__(self, rules, reftime=None):
        # Define time categories (their labels) and their default filter
        # values. Must be in order from past to future (old -> young).
        time_categories = OrderedDict((c, 0) for c in self.valid_categories)

        # If the reference time is not provided by the user, use current time
        # (Unix timestamp, seconds since epoch, no localization -- this is
        # directly comparable to the st_mtime inode data).
        self.reftime = time.time() if reftime is None else reftime
        assert isinstance(self.reftime, float)

        # Give 'em a more descriptive name.
        userrules = rules
        # Validate given rules.
        assert isinstance(userrules, dict), "`rules` parameter must be dict."
        if not len(userrules):
            raise TimeFilterError("Rules dictionary must not be emtpy.")
        greaterzerofound = False
        # `items()` is Py2/3 portable, performance impact on Py2 negligible.
        for label, count in userrules.items():
            assert isinstance(count, int), "`rules` dict values must be int."
            if count > 0:
                greaterzerofound = True
            if count < 0:
                raise TimeFilterError(
                    "'%s' count must be positive integer." % label)
            if not label in time_categories:
                raise TimeFilterError(
                    "Invalid key in rules dictionary: '%s'" % label)
        if not greaterzerofound:
            raise TimeFilterError(
                "Invalid rules dictionary: at least one count > 0 required.")

        # Build up `self.rules` dict. Set rules not given by user to defaults,
        # keep order of `time_categories` dict (order is crucial).
        self.rules = OrderedDict()
        # `items()` is Py2/3 portable, performance impact on Py2 negligible.
        for label, defaultcount in time_categories.items():
            if label in userrules:
                self.rules[label] = userrules[label]
            else:
                self.rules[label] = defaultcount
        log.debug("TimeFilter set up with reftime %s and rules %s",
            self.reftime, self.rules)

    def filter(self, objs):
        """Split list of objects into two lists, `accepted` and `rejected`,
        according to the rules. A treatable object is required to have a
        `modtime` attribute, carrying a Unix timestamp.
        """
        # Upon categorization, items are put into category-timecount buckets,
        # for instance into the 2-year bucket (category: year, timecount: 2).
        # Each bucket may contain multiple items. Therefore, each category
        # (years, months, etc) is represented as a dictionary, whereas the
        # buckets are represented as lists. The timecount for a certain bucket
        # is used as a key for storing the list (value) in the dictionary.
        # For example, `self._years_dict[2]` stores the list representing the
        # 2-year bucket. These dictionaries and their key-value-pairs are
        # created on the fly.
        #
        # There is no timecount distinction in 'recent' category, therefore
        # only one list is used for storing recent items.
        #
        # `accepted_objs` and `rejected_objs_lists` are the containers for
        # accepted and rejected items/objects. Eventually, all objects in `objs`
        # are to be inserted into either of both containers. Items to
        # be accepted are identified individually, and each single accepted
        # item will be stored via `accepted_objs.append(obj)`. Items to be
        # rejected will usually be detected block-wise, so `rejected_objs_lists`
        # is populated with multiple list objects. Later on, this function
        # returns an iterable over rejected items via itertools'
        # `chain.from_iterable()`.

        for catlabel in list(self.rules.keys())[:-1]:
            setattr(self, "_%s_dict" % catlabel, defaultdict(list))
        self._recent_items = []
        accepted_objs = []
        rejected_objs_lists = [[]]

        # Categorize given objects.
        # Younger categories have higher priority than older ones. While
        # categorizing, already reject those objects that don't fit any rule.
        for obj in objs:
            # Might raise AttributeError if `obj` does not have `modtime`
            # attribute or other exceptions upon `_Timedelta` creation.
            td = _Timedelta(obj.modtime, self.reftime)
            # If timecount in youngest category after 'recent' is 0, then this
            # is a recent item.
            if td.hours == 0:
                if self.rules["recent"] > 0:
                    self._recent_items.append(obj)
                else:
                    # This is a recent item, but we don't want to keep any.
                    rejected_objs_lists[0].append(obj)
                continue
            # Iterate through all categories from young to old, w/o 'recent'.
            # Sign. performance impact, don't go with self.rules.keys()[-2::-1]
            for catlabel in ("hours", "days", "weeks", "months", "years"):
                timecount = getattr(td, catlabel)
                if 0 < timecount <= self.rules[catlabel]:
                    # `obj` is X hours/days/weeks/months/years old with X >= 1.
                    # X is requested in current category, e.g. when 3 days are
                    # requested (`self.rules[catlabel]` == 3), and category is
                    # days and X is 2, then X <= 3, so put `obj` into
                    # self._days_dict` with timecount (2) key.
                    #log.debug("Put %s into %s/%s.", obj, catlabel, timecount)
                    getattr(self, "_%s_dict" % catlabel)[timecount].append(obj)
                    break
            else:
                # For loop did not break: `obj` is not recent and does not fit
                # to any of the rules provided. Reject it (the first item in
                # `rejected_objs_lists` is a list for items rejected during
                # categorization).
                rejected_objs_lists[0].append(obj)
                #log.debug("Rejected %s during categorizing.", obj)

        # Sort all category-timecount buckets internally and finish filtering:
        # Accept the newest element from each bucket, reject all others.
        # The 'recent' items list needs special treatment. Sort, accept the
        # newest N elements, reject the others.
        self._recent_items.sort(key=lambda f: f.modtime)
        accepted_objs.extend(self._recent_items[-self.rules["recent"]:])
        rejected_objs_lists.append(self._recent_items[:-self.rules["recent"]])
        # Iterate through all other categories except for 'recent'.
        # `catdict[timecount]` occurrences are lists with at least one item.
        # The newest item in each of these category-timecount buckets is to
        # be accepted. Remove newest from the list via pop() (should be of
        # constant time complexity for the last item of a list). Then reject
        # the (modified, if item has been popped) list.
        for catlabel in list(self.rules.keys())[:-1]:
            catdict = getattr(self, "_%s_dict" % catlabel)
            for timecount in catdict:
                catdict[timecount].sort(key=lambda f: f.modtime)
                accepted_objs.append(catdict[timecount].pop())
                rejected_objs_lists.append(catdict[timecount])
                #log.debug("Accepted %s: %s/%s.",
                #    accepted_objs[-1], catlabel, timecount)
                #log.debug("Rejected list:\n%s", catdict[timecount])

        return accepted_objs, chain.from_iterable(rejected_objs_lists)


class _Timedelta(object):
    """
    Represent how many years, months, weeks, days, hours time `t` (float,
    seconds) is earlier than reference time `ref`. Represent these metrics
    with integer attributes (floor division, numbers are cut, i.e. 1.9 years
    would be 1 year).
    There is no implicit summation, each of the numbers is to be considered
    independently. Time units are considered strictly linear: months are
    30 days, years are 365 days, weeks are 7 days, one day is 24 hours.
    """
    def __init__(self, t, ref):
        # Expect two numeric values. Might raise TypeError for other types.
        seconds_earlier = ref - t
        assert isinstance(seconds_earlier, float)
        if seconds_earlier < 0:
            raise TimeFilterError("Time %s not earlier than reference %s" %
                (t, ref))
        self.hours_exact = seconds_earlier / 3600      # 60 * 60
        self.hours = int(self.hours_exact)
        self.days_exact = seconds_earlier / 86400      # 60 * 60 * 24
        self.days = int(self.days_exact)
        self.weeks_exact = seconds_earlier / 604800    # 60 * 60 * 24 * 7
        self.weeks = int(self.weeks_exact)
        self.months_exact = seconds_earlier / 2592000  # 60 * 60 * 24 * 30
        self.months = int(self.months_exact)
        self.years_exact = seconds_earlier / 31536000  # 60 * 60 * 24 * 365
        self.years = int(self.years_exact)
