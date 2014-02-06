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
    def __init__(self, rules, reftime=None):
        # Define time categories (their labels) and their default filter
        # values. Must be in order from past to future (old -> young).
        time_categories = OrderedDict((
                ("years", 0),
                ("months", 0),
                ("weeks", 0),
                ("days", 0),
                ("hours", 0),
                ("recent", 0),
            ))

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
        for label, count in userrules.iteritems():
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
        for catlabel in self.rules:
            setattr(self, "_%s_dict" % catlabel, defaultdict(list))

        accepted_objs = []
        rejected_objs_lists = [[]]

        # Categorize given objects. Younger categories have higher priority
        # than older ones.
        for obj in objs:
            # Might raise AttributeError if `obj` does not have `modtime`
            # attribute or other exceptions upon `_Timedelta` creation.
            td = _Timedelta(obj.modtime, self.reftime)
            # If the timecount in youngest category after 'recent' is 0, then
            # this is a recent item.
            if td.hours == 0:
                self._recent_dict[1].append(obj)
                continue
            # Iterate through all categories from young to old, w/o 'recent'.
            for catlabel in ("hours", "days", "weeks", "months", "years"):
                timecount = getattr(td, catlabel)
                if 0 < timecount <= self.rules[catlabel]:
                    # `obj` is X hours/days/weeks/months/years old with X > 1.
                    # X is requested in current category, e.g. when 3 days are
                    # requested (`self.rules[catlabel]` == 3), and category is
                    # days and X is 2, then put it into `self._days_dict` with
                    # key 2.
                    #log.debug("Put %s into %s/%s.", obj, catlabel, timecount)
                    getattr(self, "_%s_dict" % catlabel)[timecount].append(obj)
                    break
            else:
                # For loop did not break: `obj` does not fit into any of the
                # requested categories. Reject it. The first item in
                # `rejected_objs_lists` is a list for items rejected during
                # categorization.
                rejected_objs_lists[0].append(obj)
                #log.debug("Rejected %s during categorizing.", obj)



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
                #log.debug("Accept recent: %s", self.rules[catlabel])
                #log.debug("Length recent: %s", len(catdict[1]))
                catdict[1].sort(key=lambda f: f.modtime)
                #log.debug("Accept list:\n%s", catdict[1][-self.rules[catlabel]:])
                #log.debug("Reject list:\n%s", catdict[1][:-self.rules[catlabel]])
                accepted_objs.extend(catdict[1][-self.rules[catlabel]:])
                rejected_objs_lists.append(catdict[1][:-self.rules[catlabel]])
                break
            for timecount in catdict:
                # catdict[timecount] exists as a list with at least one item.
                #log.debug("catlabel: %s, timecount: %s", catlabel, timecount)
                if timecount in xrange(1, self.rules[catlabel] + 1):
                    #log.debug("Accept %s/%s.", catlabel, timecount)
                    # According to the rules given, this time category is to
                    # be kept (e.g. 2 years). Sort all items in this time
                    # category.
                    catdict[timecount].sort(key=lambda f: f.modtime)
                    # Accept newest (i.e. last) item. Remove it from the list.
                    # pop should be O(1) for the last item.
                    accepted_objs.append(catdict[timecount].pop())
                    #log.debug("Accepted %s: %s/%s.",
                    #    accepted_objs[-1], catlabel, timecount)
                # Reject the (modified) list (accepted item has been popped).
                #log.debug("Reject list:\n%s", catdict[timecount])
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
