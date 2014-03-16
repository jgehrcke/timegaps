# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""timegaps.timegaps -- core data structures used by the timegaps program."""


import os
import sys
import stat
import datetime
import logging


# Make the same code base run with Python 2 and 3.
if sys.version < '3':
    text_type = unicode
    binary_type = str
else:
    text_type = str
    binary_type = bytes


log = logging.getLogger("timegaps")


class TimegapsError(Exception):
    pass


class FilterItem(object):
    """Represents item for time classification. An item has a name/description,
    simply called "text" and a modification time, called "modtime". It is up
    to the user what these entities mean in reality.

    Public interface:
        self.text:    unicode object describing this item or None.
        self.moddate: last change as local datetime object.
        self.modtime: last change as float, seconds since Unix epoch (nonlocal).
    """
    def __init__(self, modtime, text=None):
        if text is not None:
            assert isinstance(text, text_type)
        self.text = text
        if isinstance(modtime, float):
            self.modtime = modtime
        else:
            raise TimegapsError(
                "`modtime` parameter must be `float` type or `None`.")

    @property
    def moddate(self):
        """Content modification time is internally stored as Unix timestamp.
        Return datetime object corresponding to local time.
        """
        return datetime.datetime.fromtimestamp(self.modtime)

    def __str__(self):
        return "%s(text: %s, moddate: %s)" % (self.__class__.__name__,
            self.text, self.moddate)

    def __repr__(self):
        return "%s(text=%s, modtime=%s)" % (self.__class__.__name__,
            self.text, self.modtime)


class FileSystemEntry(FilterItem):
    """Represents file system entry (for later filtering). Validates path upon
    initialization, extracts information from inode, and stores inode data
    for later usage. Public interface (in addition to FilterItem's interface):
        self.type: "dir", "file", or "symlink".
        self.path: path to file system entry.
    """
    def __init__(self, path, modtime=None):
        log.debug("Creating FileSystemEntry from path %r.", path)
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
        log.debug("Detected type %s.", self.type)
        if modtime is None:
            # User may provide modification time -- if not, extract it from
            # inode. This is a Unix timestamp, seconds since epoch. Not
            # localized.
            modtime = self._stat.st_mtime
        else:
            log.debug("Don't use stat mtime, use %s.", modtime)
        self.path = path
        # FilterItem requires unicode `text` attribute, decode path if not
        # already unicode:
        t = path
        if not isinstance(t, text_type):
            t = t.decode(sys.getfilesystemencoding())
        FilterItem.__init__(self, text=t, modtime=modtime)

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

    def __str__(self):
        return "%s(path: %r, moddate: %s)" % (self.__class__.__name__,
            self.path, self.moddate)

    def __repr__(self):
        return "%s(path=%r, modtime=%s)" % (self.__class__.__name__,
            self.path, self.modtime)
