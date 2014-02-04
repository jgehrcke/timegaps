# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""
Feature / TODO brainstorm:
    - reference implementation with cmdline interface
    - comprehensive API for systematic unit testing and library usage
    - remove or move or noop mode
    - extensive logging
    - parse mtime from path (file/dirname)
    - symlink support (elaborate specifics)
    - file system entry input via positional cmdline args or via null-character
      separated paths at stdin
    - add a mode where time-encoding nullchar-separated strings are read as
      input and then filtered. The output is a set of rejected strings (no
      involvement of the file system at all, just timestamp filtering)
    - add cmdline option for reference time input
    - otherwise: reference time is time at program startup
    - define default rules in cmdline tool, not in underlying
      implementation
    - rework FileSystemEntry / _FileSystemEntry __new__ mechanism
    - set some meaningful filtering defaults, such as:
        assert f.rules["days"] == 10
        assert f.rules["years"] == 4
        assert f.rules["months"] == 12
        assert f.rules["weeks"] == 6
        assert f.rules["hours"] == 48
        assert f.rules["recent"] == 5
"""

import os
import sys
import logging
import time
from logging.handlers import RotatingFileHandler


from deletebytime import Filter, FileSystemEntry


YEARS = 1
MONTHS = 12
WEEKS = 6
DAYS = 8
HOURS = 48
ZERO_HOURS_KEEP_COUNT = 5
LOGFILE_PATH = "/mnt/two_3TB_disks/jpg_private/home/progg0rn/nas_scripts/delete_pc_backups/delete_backups.log"


def main():
    paths = sys.argv[1:]
    log.info("Got %s backup paths via cmdline.", len(backup_dirs))
    backup_times = [time_from_dirname(d) for d in backup_dirs]
    items_with_time = zip(backup_dirs, backup_times)

    items_to_keep = filter_items(items_with_time)
    keep_dirs = [i[0] for i in items_to_keep]

    keep_dirs_str = "\n".join(keep_dirs)
    log.info("Keep these %s directories:\n%s", len(keep_dirs), keep_dirs_str)

    delete_paths = [p for p in backup_dirs if p not in keep_dirs]
    log.info("Delete %s paths", len(delete_paths))

    for p in delete_paths:
        delete_backup_dir(p)


if __name__ == "__main__":
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    fh = RotatingFileHandler(
        LOGFILE_PATH,
        mode='a',
        maxBytes=500*1024,
        backupCount=30,
        encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    fh.setFormatter(formatter)
    log.addHandler(ch)
    log.addHandler(fh)
    main()


if __name__ == "__main__":
    main()
