# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
import stat
import datetime
import logging
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
    """ Represents file system entry for later filtering. Validates path and
    extracts information from inode upon construction and stores inode data
    for later usage. Public interface attributes:
        - self.modtime: last content change (mtime) as local datetime object
        - self.type: "dir", "file", or "symlink"
        - self.path: path to file system entry
    """
    def __init__(self, statobj, path, modtime=None):
        log.debug("Creating FSE with path '%s'", path)
        self.path = path
        self._set_type(statobj)
        if modtime is None:
            self._modtime = statobj.st_mtime
        elif isinstance(modtime, float) :
            self._modtime = modtime
        else:
            raise TimegapsError(
                "`modtime` parameter must be `float` object or `None`.")
        self._stat = statobj

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

    @property
    def modtime(self):
        # Content modification time is internally stored as POSIX timestamp.
        # Return datetime object corresponding to local time.
        return datetime.datetime.fromtimestamp(self._modtime)


class Filter(object):
    """ Implements concrete filter rules. Allows for filtering a list of
    `FileSystemEntry` objects.
    """
    def __init__(self, rules=None):
        defaults = {
            "years": 4,
            "months": 12,
            "weeks": 6,
            "days": 10,
            "hours": 48,
            "zerohours": 5,
            }

        if rules is None:
            rules = dict()

        # Check given rules for invalid time labels.
        for key in rules:
            if not key in defaults:
                raise TimegapsError(
                    "Invalid key in rules dictionary: '%s'" % key)

        # Set missing rules to defaults.
        for label, count in defaults.items():
            if not label in rules:
                rules[label] = count

        self.rules = rules

    def filter(self, fses):
        """ Split list of `FileSystemEntry` objects into two lists, `accepted`
        and `rejected` according to the rules.
        """
        accepted = []
        rejected = []
        fses = [f for f in fses if isinstance(f, _FileSystemEntry)]
        if not fses:
            raise TimegapsError("`fses` must contain valid entries.")
        return accepted, rejected


class Timedelta(object):
    """
    Represents how many years, months, weeks, days, hours time `t` (float,
    seconds) is earlier than reference time `ref`. Show all this
    with integer attributes (floor division, numbers are cut, i.e. 1.9 years
    would be 1 year).
    There is no implicit summation, each of the numbers can be considered
    independently. Time units are considered strictly linear: months are
    30 days, years are 365 days, weeks are 7 days, one day is 24 hours.
    """
    def __init__(self, t, ref):
        # convert struct_time objects to a second-based representatio here for
        # simpler math.
        if isinstance(t, time.struct_time):
            t = time.mktime(t)
        if isinstance (ref, time.struct_time):
            ref = time.mktime(ref)  + 5000000
        seconds_earlier = ref - t
        self.hours = int(seconds_earlier // 3600)     # 60 * 60
        self.days = int(seconds_earlier // 86400)     # 60 * 60 * 24
        self.weeks = int(seconds_earlier // 604800)   # 60 * 60 * 24 * 7
        self.months = int(seconds_earlier // 2592000) # 60 * 60 * 24 * 30
        self.years = int(seconds_earlier // 31536000) # 60 * 60 * 24 * 365


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

