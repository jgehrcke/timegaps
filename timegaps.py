# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.
#
"""Filter items by time categories.

Usage:
    timegaps [--delete | --move=DIR] [--follow-symlinks] [--reftime=FMT]
             [--time-from-basename=FMT | --time-from-string=FMT]
             [--nullchar] FILTER_RULES ITEM ...
    timegaps --version
    timegaps --help


Arguments:
    FILTER_RULES  Filter rules as JSON string. Example: '{years:1, hours:2}'.
    ITEM          A valid path (file, dir, symlink) or any string in case of
                  --time-from-string)

Options:
    --help -h                   Show this help message and exit.
    --version                   Show version information and exit.
    --delete -d                 Attempt to delete rejected paths.
    --move=DIR -m DIR           Attempt to move rejected paths to directory DIR.
    --stdin                     Read items for filtering from stdin, separated
                                by newline characters.
    --nullsep -0                Perform input and output item separation with
                                NULL characters instead of newline characters.
    --reftime=FMT -t FMT        Parse time from formatstring FMT (cf.
                                documentation of Python's strptime() at
                                bit.ly/strptime). Use this time as reference
                                time (default is time of program invocation).
    --follow-symlinks -S        Retrieve modification time from symlink target,
                                TODO: other implications?
    --time-from-basename=FMT    Don't extract an item's modification time from
                                inode (which is the default). Instead, parse
                                time from basename of path according to
                                formatstring FMT (cf. documentation of Python's
                                strptime() at bit.ly/strptime)
    --time-from-string=FMT      Treat items as strings (don't validate paths)
                                and parse time from strings using formatstring
                                FMT (cf. bit.ly/strptime)


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
    - set some meaningful filtering defaults, such as:
        assert f.rules["years"] == 4
        assert f.rules["months"] == 12
        assert f.rules["weeks"] == 6
        assert f.rules["hours"] == 48
        assert f.rules["days"] == 10
        assert f.rules["recent"] == 5
"""

import os
import sys
import argparse
import logging
import re
import time
from logging.handlers import RotatingFileHandler
from timegaps import TimeFilter, FileSystemEntry, __version__

YEARS = 4
MONTHS = 12
WEEKS = 6
DAYS = 8
HOURS = 48
RECENT = 5


# Global for options, to be populated by argparse from cmdline arguments.
options = None





def main():
    parse_options()
    log.debug("Options: %s", options)

    # Validate options.
    if len(options.item) == 0:
        if not options.stdin:
            err("At least one item must be provided (or set --stdin).")

    log.debug("Decode rules string.")
    try:
        rules = parse_rules_from_cmdline(options.rules)
        log.info("Using rules: %s", rules)
    except ValueError as e:
        err("Error while parsing rules: '%s'." % e)

    reference_time = time.time()
    if options.reference_time is not None:
        pass
        # TODO: parse ref time from string
    log.info("Using reference time %s." % reference_time)
    timefilter = TimeFilter(rules, reference_time)

    if options.time_from_string is not None:
        pass
        # TODO: change mode to pure string parsing, w/o item-wise filesystem
        # interaction

    fses = []
    for i in options.item:
        try:
            fses.append(FileSystemEntry(path=i))
        except OSError:
            err("Cannot open '%s'." % i)

    log.info("Filtering ...")
    accepted, rejected = timefilter.filter(fses)
    rejected = list(rejected)
    log.debug("Accepted items:\n%s" % "\n".join("%s" % a for a in accepted))
    log.debug("Rejected items:\n%s" % "\n".join("%s" % r for r in rejected))

    # Build object list to be filtered via TimeFilter.


def parse_rules_from_cmdline(s):
    tokens = s.split(",")
    if not tokens:
        raise ValueError("Error extracting rules from string '%s'" % s)
    rules = {}
    for t in tokens:
        log.debug("Analze token '%s'", t)
        if not t:
            raise ValueError("Token is empty")
        match = re.search(r'([a-z]+)([0-9]+)', t)
        if match:
            catid = match.group(1)
            timecount = match.group(2)
            if catid not in TimeFilter.valid_categories:
                raise ValueError("Time category '%s' invalid" % catid)
            rules[catid] = int(timecount)
            log.debug("Stored rule: %s: %s" % (catid, timecount))
            continue
        raise ValueError("Invalid token <%s>" % t)
    return rules


def err(s):
    log.error(s)
    log.info("Exit with code 1.")
    sys.exit(1)


def parse_options():
    global options
    parser = argparse.ArgumentParser(
        description=("Filter items by time categories."),
        epilog="Version %s" % __version__
        )
    parser.add_argument('--version', action='version', version=__version__)

    parser.add_argument("rules", action="store",
        metavar="FILTER_RULES",
        help=("Filter rules as JSON string. Example: '{years:1, hours:2}.")
        )
    # Require at least one arg if --stdin is not defined. Don't require any
    # arg if --stdin is defined. Overall, allow an arbitrary number, and
    # validate later.
    parser.add_argument("item", action="store", nargs='*',
        help=("Items for filtering. Interpreted as paths to filesystem "
            "entries by default.")
        )

    filehandlegroup = parser.add_mutually_exclusive_group()
    filehandlegroup .add_argument("-d", "--delete", action="store_true",
        help="Attempt to delete rejected paths."
        )
    filehandlegroup.add_argument("-m", "--move", action="store",
        metavar="DIR",
        help="Attempt to move rejected paths to directory DIR.")


    parser.add_argument("-s", "--stdin", action="store_true",
        help=("Read items for filtering from stdin, separated by newline "
            "by newline characters.")
        )
    parser.add_argument("-0", "--nullsep", action="store_true",
        help=("Perform input and output item separation with NULL characters "
            "instead of newline characters.")
        )
    parser.add_argument("-t", "--reference-time", action="store",
        metavar="FMT",
        help=("Parse time from formatstring FMT (cf. documentation of Python's "
            "strptime() at bit.ly/strptime). Use this time as reference time "
            "(default is time of program invocation).")
        )
    parser.add_argument("-S", "--follow-symlinks", action="store_true",
        help=("Retrieve modification time from symlink target, .. "
            "TODO: other implications?")
        )

    timeparsegroup = parser.add_mutually_exclusive_group()
    timeparsegroup.add_argument("--time-from-basename", action="store",
        metavar="FMT",
        help=("Don't extract an item's modification time from inode (which is "
            "the default). Instead, parse time from basename of path according "
            "to formatstring FMT (cf. documentation of Python's strptime() at "
            "bit.ly/strptime).")
        )
    timeparsegroup.add_argument("--time-from-string", action="store",
        metavar="FMT",
        help=("Treat items as strings (don't validate paths) and parse time "
            "from strings using formatstring FMT (cf. bit.ly/strptime).")
        )
    #arguments = docopt(__doc__, version=__version__)
    #print(arguments)
    options = parser.parse_args()


def time_from_dirname(d):
    # dirs are of type 2013.08.15_20.29.31
    return time.strptime(d, "%Y.%m.%d_%H.%M.%S")


def dirname_from_time(t):
    return time.strftime("%Y.%m.%d_%H.%M.%S", t)


if __name__ == "__main__":
    log = logging.getLogger()
    log.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    #fh = RotatingFileHandler(
    #    LOGFILE_PATH,
    #    mode='a',
    #    maxBytes=500*1024,
    #    backupCount=30,
    #    encoding='utf-8')
    formatter = logging.Formatter(
        '%(asctime)s,%(msecs)-6.1f - %(levelname)s: %(message)s',
        datefmt='%H:%M:%S')
    ch.setFormatter(formatter)
    #fh.setFormatter(formatter)
    log.addHandler(ch)
    #log.addHandler(fh)
    main()
