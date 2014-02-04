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
