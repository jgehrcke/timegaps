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
    """Represents file system entry (for later filtering). Validates path upon
    initialization, extracts information from inode, and stores inode data
    for later usage. Public interface:
        - self.moddate: last content change (mtime) as local datetime object.
        - self.type: "dir", "file", or "symlink".
        - self.path: path to file system entry.
    """
    def __init__(self, path, modtime=None):
        log.debug("Creating FileSystemEntry from path '%s'.", path)
        try:
            # os.lstat(path)
            # Perform the equivalent of an lstat() system call on the given
            # path. Similar to stat(), but does not follow symbolic links.
            # On platforms that do not support symbolic links, this is an alias
            # for stat().
            self._stat = os.lstat(path)
        except OSError as e:
            log.error("stat() failed on path: '%s' (%s).", path, e)
            raise
        self.type = self._get_type(self._stat)
        log.debug("Detected type %s", self.type)
        if modtime is None:
            # User may provide modification time -- if not, extract it from
            # inode. This is a Unix timestamp, seconds since epoch. Not
            # localized.
            self.modtime = self._stat.st_mtime
        elif isinstance(modtime, float) :
            self.modtime = modtime
        else:
            raise TimegapsError(
                "`modtime` parameter must be `float` type or `None`.")
        self.path = path

    def _get_type(self, statobj):
        """Determine file type from stat object `statobj`.
        Distinguish file, dir, symbolic link.
        """
        if stat.S_ISREG(statobj.st_mode):
            return "file"
        if stat.S_ISDIR(statobj.st_mode):
            return "dir"
        if stat.S_ISLNK(statobj.st_mode):
            return "symlink"
        raise TimegapsError("Unsupported file type: '%s'", self.path)

    @property
    def moddate(self):
        """Content modification time is internally stored as Unix timestamp.
        Return datetime object corresponding to local time.
        """
        return datetime.datetime.fromtimestamp(self.modtime)


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

