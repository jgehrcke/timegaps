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

EXTENDED_HELP = """
Input:
    ITEMs:
        By default, an ITEM value is interpreted as a path to a file system
        entry. By default, the corresponding timestamp for item filtering is
        the modification time read from the inode. Optionally, this timestamp
        may also be parsed from the basename of the path. When interpreted as
        paths, all ITEM values must point to valid file system entries. In a
        different mode of operation, ITEM values are treated as simple strings
        w/o path validation, in which case a timestamp must be parsable from
        the string itself.
    FILTERRULES:
        These rules define how many items of certain time categories are to be
        accepted, while all other items become rejected. Supported time
        categories and the FILTERRULES string formatting specification are
        given in the program's normal help text. The exact method of
        classification is explained below.


Output:
        By default, the program writes the rejected items to stdout, whereas
        single items are separated by newline characters. Alternatively, the
        accepted items can be written out instead of the rejected ones. The
        item separator may be set to the NULL character. Log output and error
        messages are written to stderr.


Actions:
        Certain actions such as removal or renaming (moving) can be performed
        on items based on their classification. By default, no actions are
        performed. If not further specified, activated actions are performed on
        rejected items only.


Classification method:
        Each item provided as input becomes classified as either accepted or
        rejected, based on its corresponding timestamp and according to the
        time filter rules given by the user. For the basic meaning of the
        filter rules, consider this example FILTERRULES string:

            hours12,days5,weeks4

        It translates to the following <category>:<maxcount> pairs:

            hours: 12
            days:   5
            weeks:  4

        Based on the reference time, which by default is the program's startup
        time, the program calculates the age of all ITEMs. According to
        the example rules, the program then tries to identify and accept one
        item from each of the last 12 hours, one item from each of the last 5
        days, and one item from each of the last 4 weeks.

        More specifically, according to <hours> rule above, the program accepts
        the *newest* item in each of 12 sub-categories: the newest item being
        1 h old, the newest item being 2 h old, ..., and the newest item being
        12 h old, yielding at most 12 accepted items from the <hours> time
        category: zero or one for each of the sub-categories.

        An hour is a time unit, as are all time categories except for the
        <recent> category (explained further below). An item is considered
        X [timeunits] old if it is older than X [timeunits], but younger than
        X+1 [timeunits]. For instance, if an item being 45 days old should be
        sub-categorized within the 'months' category, it would be considered
        1 month old, because it is older than 30 days (1 month) and younger
        than 60 days (2 months). Internally, all time category units are
        treated as linear in time (see below for time category specification).

        The example rules above can accept at most 12 + 5 + 4 accepted items.
        If there are multiple items fitting into a certain sub-category (e.g.
        <3-days>), then the newest of these is accepted. If there is no item
        fitting into a certain sub-category, then this sub-category simply does
        not yield an item. Considering the example rules above, only 11 items
        are accepted from the <hours> category if the program does not find an
        item for the <5-hours> sub-category, but at least one item for the
        other <hours> sub-categories.

        Younger time categories have higher priority than older ones. This is
        only relevant when, according to the rules, two <category>:<maxcount>
        pairs overlap. Example rules:

            days:  10
            weeks:  1

        An item fitting into one of the <7/8/9/10-days> sub-categories would
        also fit the <1-weeks> sub-category. This is a rules overlap. In this
        case, the <X-days> sub-categories will be populated first, since <days>
        is the younger category than <weeks>. If there is an 11 days old item
        in the input, it will populate the <1-week> sub-category, because it is
        the newest 1-week-old item *not consumed by a younger category*.


        Time categories and their meaning:

            hours:  60 minutes (    3600 seconds)
            days:   24 hours   (   86400 seconds)
            weeks:   7 days    (  604800 seconds)
            months: 30 days    ( 2592000 seconds)
            years: 365 days    (31536000 seconds)

        The special category <recent> keeps track of all items younger than
        1 hour. It it not further sub-categorized. If specified in the rules,
        the <maxcount> newest items from this category re accepted.


Exit status:
    TODO
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
    # I
    if len(options.items) == 0:
        if not options.stdin:
            err("At least one item must be provided (if --stdin not set).")

    #
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
    for i in options.items:
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
    description = "Accept or reject files/items based on time categorization."
    parser = argparse.ArgumentParser(
        prog="timegaps",
        description=description,
        epilog="Version %s" % __version__,
        add_help=False
        )
    parser.add_argument("-h", "--help", action="help",
        help="Show help message and exit.")
    parser.add_argument("--extended-help", action="version",
        version=EXTENDED_HELP, help="Show extended help and exit.")
    parser.add_argument("--version", action="version",
        version=__version__, help="Show version information and exit.")


    parser.add_argument("rules", action="store",
        metavar="FILTERRULES",
        help=("A string defining the filter rules of the form "
            "<category><maxcount>[,<category><maxcount>[, ... ]]. "
            "Example: 'recent5,days12,months5'. "
            "Valid <category> values: %s. Valid <maxcount> values: "
            "positive integers. Default maxcount for unspecified categories: "
            "0." %
            ", ".join(TimeFilter.valid_categories))
        )
    # Require at least one arg if --stdin is not defined. Don't require any
    # arg if --stdin is defined. Overall, allow an arbitrary number, and
    # validate later.
    parser.add_argument("items", metavar="ITEM", action="store", nargs='*',
        help=("Items for filtering. Interpreted as paths to file system "
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

    # TODO:
    #   verbosity option
    #   output rejected or accepted
    #   action on rejected or accepted

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
