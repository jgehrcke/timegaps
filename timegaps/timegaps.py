# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
import stat
import datetime
import logging
import itertools
from collections import defaultdict
from collections import OrderedDict
from operator import itemgetter


log = logging.getLogger("timegaps")


class TimegapsError(Exception):
    pass


class FileSystemEntry(object):
    def __new__(cls, path, modtime=None):
        try:
            # os.lstat(path)
            # Perform the equivalent of an lstat() system call on the given
            # path. Similar to stat(), but does not follow symbolic links.
            # On platforms that do not support symbolic links, this is an alias
            # for stat().
            statobj = os.lstat(path)
        except OSError as e:
            log.warning("Ignoring invalid path: '%s' ('%s')", path, e)
            return None
        return _FileSystemEntry(statobj, path, modtime)


class _FileSystemEntry(object):
    """Represents file system entry for later filtering. Validates path upon
    initialization, extracts information from inode, and stores inode data
    for later usage. Public interface:
        - self.moddate: last content change (mtime) as local datetime object
        - self.type: "dir", "file", or "symlink"
        - self.path: path to file system entry
    """
    def __init__(self, statobj, path, modtime=None):
        log.debug("Creating FSE with path '%s'", path)
        self.path = path
        self._set_type(statobj)
        if modtime is None:
            # User may provide modification time -- if not, extract it from
            # inode. This is a Unix timestamp, seconds since epoch. Not
            # localized.
            self.modtime = statobj.st_mtime
        elif isinstance(modtime, float) :
            self.modtime = modtime
        else:
            raise TimegapsError(
                "`modtime` parameter must be `float` object or `None`.")
        self._stat = statobj
        self.timedelta = None

    def _set_type(self, statobj):
        # Determine type from stat object `statobj`.
        # Distinguish file, dir, symbolic link
        # Either follow symbolic link or not, this should be user-given.
        if stat.S_ISREG(statobj.st_mode):
            self.type  = "file"
        elif stat.S_ISDIR(statobj.st_mode):
            self.type  = "dir"
        elif stat.S_ISLNK(statobj.st_mode):
            self.type  = "symlink"
        else:
            raise TimegapsError("Unsupported file type: '%s'", self.path)
        log.debug("Detected type %s", self.type)

    #def build_timedelta(self, reftime):
    #    self.timedelta = _Timedelta(self._modtime, reftime)

    @property
    def moddate(self):
        # Content modification time is internally stored as POSIX timestamp.
        # Return datetime object corresponding to local time.
        return datetime.datetime.fromtimestamp(self.modtime)


class Filter(object):
    """ Represents concrete filter rules. Allows for filtering a list of
    `FileSystemEntry` objects.
    """
    def __init__(self, reftime=None, rules=None):
        # Define time categories (their labels) and their default filter
        # values. Must be in order past -> future.
        time_categories = OrderedDict((
                ("years", 4),
                ("months", 12),
                ("weeks", 6),
                ("days", 10),
                ("hours", 48),
                ("recent", 5),
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
                raise TimegapsError(
                    "Invalid key in rules dictionary: '%s'" % key)

        # Set missing rules to defaults.
        for label, count in time_categories.items():
            if not label in rules:
                rules[label] = count

        self.rules = rules


    def filter(self, fses):
        """ Split list of `FileSystemEntry` objects into two lists, `accepted`
        and `rejected` according to the rules.
        """
        accepted = []
        rejected = []
        #
        fses = [f for f in fses if isinstance(f, _FileSystemEntry)]
        if not fses:
            raise TimegapsError("`fses` must contain valid entries.")

        #self.years_dict = defaultdict(list)
        #self.months_dict = defaultdict(list)
        #self.weeks_dict = defaultdict(list)
        #...
        for c in self.time_categories:
            setattr(self, "%s_dict" % c, defaultdict(list))

        accepted_fses = []
        rejected_fses_lists = []

        # Categorize all filesystem entries.
        for fse in fses:
            td = _Timedelta(fse.modtime, self.reftime)
            # Automation of the following code, which uses time categories
            # explicitly:
            #       if td.years > 0:
            #           self.years_dict[td.years].append(fse)
            #       elif td.months > 0:
            #           self.years_dict[td.months].append(fse)
            #       ...
            #       elif:
            #           # Modification time later than ref - 1 hour.
            #           # td.recent is always 0 (hack for unique treatment of
            #           # categories).
            #           self.recent_dict[td.recent].append(fse)
            for catlabel in self.rules:
                timecount = getattr(td, catlabel)
                if timecount > 0:
                    # Get category dictionary, use timecount as key. This
                    # retrieves the list for all fses that are e.g. 2 years
                    # old (this would translate to years_dict[2]). Append fse
                    # to this list. Create key and list if it doesn't exist so
                    # far (this is handled by defaultdict).
                    getattr(self, "%s_dict" % catlabel)[timecount].append(fse)

        for catlabel in self.rules:
            catdict = getattr(self, "%s_dict" % catlabel)
            for timecount in catdict:
                if timecount in xrange(1, self.rules[catlabel] + 1):
                    # According to the rules given, this time category is to
                    # be kept (e.g. 2 years). Sort all items in this time
                    # category and select the newest for acceptance. Reject
                    # all other items.
                    catdict[timecount].sort(key=lambda f: f.modtime)
                    # Accept newest (i.e. last) item. Remove it from the list.
                    # pop should be O(1) for the last item.
                    accept_fses.append(catdict[timecount].pop())
                    # Reject the rest of the list.
                    rejected_fses_lists.append(catdict[timecount])

        rejected_fses = itertools.chain.from_iterable(rejected_fses_lists)
        return accepted_fses, rejected_fes


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
        if isinstance(t, time.struct_time):
            t = time.mktime(t)
        if isinstance (ref, time.struct_time):
            ref = time.mktime(ref)  + 5000000
        seconds_earlier = ref - t
        # TODO: this check might be over-cautios in the future.
        assert isinstance(seconds_earlier, float)
        if seconds_earlier < 0:
            raise TimegapsError("Time %s not earlier than reference %s" %
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

        # TODO: that's hacky, can we improve?
        self.recent = 0

def filter_items(items_with_time):
    """
    """
    now = time.localtime()
    years_dict = defaultdict(list)
    months_dict = defaultdict(list)
    weeks_dict = defaultdict(list)
    days_dict = defaultdict(list)
    hours_dict = defaultdict(list)
    for item, itemtime in items_with_time:
        delta = Timedelta(t=itemtime, ref=now)
        i = (item, itemtime)
        # Stick this item into corresponding buckets.
        years_dict[delta.years].append(i)
        months_dict[delta.months].append(i)
        weeks_dict[delta.weeks].append(i)
        days_dict[delta.days].append(i)
        hours_dict[delta.hours].append(i)

    years_dict = sort_dict(years_dict)
    months_dict = sort_dict(months_dict)
    weeks_dict = sort_dict(weeks_dict)
    days_dict = sort_dict(days_dict)
    hours_dict = sort_dict(hours_dict)
    print months_dict.keys()

    items_to_keep = []
    items_to_keep.extend(keep_from_category(years_dict, YEARS))
    items_to_keep.extend(keep_from_category(months_dict, MONTHS))
    items_to_keep.extend(keep_from_category(weeks_dict, WEEKS))
    items_to_keep.extend(keep_from_category(days_dict, DAYS))
    items_to_keep.extend(keep_from_category(hours_dict, HOURS))

    if 0 in hours_dict:
        # Also keep N newest items younger than 1 hour.
        items_to_keep.extend(hours_dict[0][:ZERO_HOURS_KEEP_COUNT])

    # Remove repetitions.
    return list(set(items_to_keep))


def keep_from_category(d, maxcount):
    items = []
    # Example: keep one item for the last 7 monts.  Go through the months dict
    # and test for month delta 1, 2, 3, ... 7. For each existing delta grab the
    # newest item, i.e. element 0.
    for delta in range(1, maxcount+1):
        if delta in d:
            items.append(d[delta][0])
    return items


def sort_dict(d):
    sd = OrderedDict(sorted(d.iteritems(), key=itemgetter(0)))
    for key, itemlist in sd.iteritems():
        # For each coarse-grained time delta (e.g. 1 year), there is a list of
        # items. Sort this list by item time, in descending order, i.e. newer
        # items first.
        sd[key] = sorted(itemlist, key=itemgetter(1), reverse=True)
    return sd


def delete_backup_dir(backup_dir):
    log.info("dummy delete for path '%s'", backup_dir)


def time_from_dirname(d):
    # dirs are of type 2013.08.15_20.29.31
    return time.strptime(d, "%Y.%m.%d_%H.%M.%S")


def dirname_from_time(t):
    return time.strftime("%Y.%m.%d_%H.%M.%S", t)

