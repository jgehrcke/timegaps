# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import time
import logging
import itertools
from collections import defaultdict
from collections import OrderedDict


log = logging.getLogger("timefilter")


class TimeFilterError(Exception):
    pass


class TimeFilter(object):
    """Represents certain time filtering rules. Allows for filtering objects
    providing a `modtime` attribute.
    """
    def __init__(self, reftime=None, rules=None):
        # Define time categories (their labels) and their default filter
        # values. Must be in order from past to future.
        time_categories = OrderedDict((
                ("years", 0),
                ("months", 0),
                ("weeks", 0),
                ("days", 0),
                ("hours", 0),
                ("recent", 0),
            ))

        if rules is None:
            rules = OrderedDict()

        # If the reference time is not provided by the user, use current time
        # (Unix timestamp, seconds since epoch, no localization -- this is
        # directly comparable to the st_mtime inode data).
        self.reftime = time.time() if reftime is None else reftime

        # Check given rules for invalid time labels.
        for key in rules:
            if not key in time_categories:
                raise TimeFilterError(
                    "Invalid key in rules dictionary: '%s'" % key)

        # Set missing rules to defaults.
        for label, count in time_categories.items():
            if not label in rules:
                rules[label] = count
        self.rules = rules


    def filter(self, objs):
        """Split list of objects into two lists, `accepted` and `rejected`,
        according to the rules. A treatable object is required to have a
        `modtime` attribute, carrying a Unix timestamp.
        """
        # self._years_dict = defaultdict(list)
        # self._months_dict = defaultdict(list)
        # ...
        for catlabel in self.rules:
            setattr(self, "_%s_dict" % catlabel, defaultdict(list))

        accepted_objs = []
        rejected_objs_lists = []

        # Categorize all objects. Algorithm:
        # Test from longer towards shorter periods (e.g. years -> hours). Find
        # 'longest' category in which the objects fits (timecount for this
        # category > 0). Get category dictionary, use timecount as key. This
        # retrieves the list for all objs that are e.g. 2 years old (this would
        # translate to years_dict[2]). Append obj to this list. Create key and
        # list if it doesn't exist (this is handled by defaultdict).
        # Automation of the following code:
        #       if td.years > 0:
        #           self.years_dict[td.years].append(obj)
        #       elif td.months > 0:
        #           self.years_dict[td.months].append(obj)
        #       ...
        #       elif:
        #           # Modification time later than ref - 1 [smallest unit].
        #           # td.recent is always 0 (hack for unique treatment of
        #           # categories).
        #           self.recent_dict[td.recent].append(obj)
        for obj in objs:
            # Might raise AttributeError if `obj` does not have `modtime`
            # attribute or TypeError upon _Timedelta creation.
            td = _Timedelta(obj.modtime, self.reftime)
            for catlabel in self.rules:
                timecount = getattr(td, catlabel)
                if timecount > 0:
                    getattr(self, "_%s_dict" % catlabel)[timecount].append(obj)

        # Go through categorized dataset and sort it into accepted and
        # rejected items, according to the rules given.
        for catlabel in self.rules:
            catdict = getattr(self, "_%s_dict" % catlabel)
            # The `recent` dictionary needs special treatment, since all recent
            # objects are in the same list: recent items are not, like items in
            # other categories, further categorized via dictionary key. All
            # recent items are in the list with key 1 (by convention).
            if catlabel == "recent" and self.rules[catlabel] > 0:
                # Sort, accept the newest N elements, reject the others.
                catdict[1].sort(key=lambda f: f.modtime)
                accepted_objs.extend(catdict[1][-self.rules[catlabel]:])
                rejected_objs_lists.append(catdict[1][:-self.rules[catlabel]])
                break
            for timecount in catdict:
                # catdict[timecount] exists as a list with at least one item.
                log.debug("catlabel: %s, timecount: %s", catlabel, timecount)
                if timecount in xrange(1, self.rules[catlabel] + 1):
                    log.debug("timecount requested, according to rules.")
                    # According to the rules given, this time category is to
                    # be kept (e.g. 2 years). Sort all items in this time
                    # category.
                    catdict[timecount].sort(key=lambda f: f.modtime)
                    # Accept newest (i.e. last) item. Remove it from the list.
                    # pop should be O(1) for the last item.
                    accepted_objs.append(catdict[timecount].pop())
                    # Reject the rest of the list.
                    rejected_objs_lists.append(catdict[timecount])

        rejected_objs = itertools.chain.from_iterable(rejected_objs_lists)
        return accepted_objs, rejected_objs


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
        # convert struct_time objects to a second-based representatio here for
        # simpler math. TODO: is this conversion still needed?
        #if isinstance(t, time.struct_time):
        #    t = time.mktime(t)
        #if isinstance (ref, time.struct_time):
        #    ref = time.mktime(ref)
        # Expect two numeric values. Might raise TypeError for other types.
        seconds_earlier = ref - t
        # TODO: this check might be over-cautios in the future.
        assert isinstance(seconds_earlier, float)
        if seconds_earlier < 0:
            raise TimeFilterError("Time %s not earlier than reference %s" %
                (t, ref))
        self.hours_exact = seconds_earlier / 3600     # 60 * 60
        self.hours = int(self.hours_exact)
        self.days_exact = seconds_earlier / 86400     # 60 * 60 * 24
        self.days = int(self.days_exact)
        self.weeks_exact = seconds_earlier / 604800   # 60 * 60 * 24 * 7
        self.weeks = int(self.weeks_exact)
        self.months_exact = seconds_earlier / 2592000 # 60 * 60 * 24 * 30
        self.months = int(self.months_exact)
        self.years_exact = seconds_earlier / 31536000 # 60 * 60 * 24 * 365
        self.years = int(self.years_exact)

        # That's hacky, can we improve? Currently, this `recent` attr is used
        # in the `TimeFilter.filter` method as key to the recent dict:
        #   `self.recent_dict[td.recent].append(obj)`
        # This happens automatically, in analogy to
        #   `self.years_dict[td.years].append(obj)`
        # Must be 1, by convention.
        self.recent = 1
