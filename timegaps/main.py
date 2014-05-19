#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke (http://gehrcke.de).
# See LICENSE file for details.


"""Accept or reject items based on age categorization."""


from __future__ import unicode_literals


__version__ = '0.1.1'
EXTENDED_HELP = """
Timegaps accepts or rejects file system paths (items) based their modification
time. Its input is a set of items and certain categorization rules. The items
are then, according to the rules, classified into rejected and accepted items.
In the default mode, the output is the set of rejected items. If specified,
accepted or rejected items are deleted or moved. Find the detailed program
specification below.


Input:
    ITEMs:
        By default, an ITEM value is interpreted as a path to a file system
        entry. By default, the timestamp corresponding to this item (which is
        used for item categorization) is the modification time as reported by
        stat(). Optionally, this timestamp may also be parsed from the basename
        of the path. When interpreted as paths, all ITEM values must point to
        valid file system entries. In a different mode of operation, ITEM
        values are treated as simple strings w/o path validation, in which case
        the "modification time" must be parsable from the string itself.
    RULES:
        The rules define the amount of items to be accepted for certain time
        categories. All other items become rejected. Supported time categories
        and the RULES string format specification are given in the normal help
        text output of the program (--help). The exact method of item time
        categorization is explained below.


Output:
        By default, the program writes the rejected items to stdout, whereas
        single items are separated by newline characters. Alternatively, the
        accepted items can be written out instead of the rejected ones. The
        item separator may be set to the NUL character. Log output and error
        messages are written to stderr.


Actions:
        An action can be performed on each item, based on its classification.
        Currently, the deletion (--delete) or displacement (--move DIR) of items
        is supported. By default, no action is performed. If an action is
        specified, it is by default performed on rejected items only. This
        behavior can be changed with the --accepted switch. Note that accepted
        or rejected items are written to stdout just like in non-action mode.

        Remarks: the --time-from-string mode is not allowed in combination with
        --delete or --move. The --move action renames within one file system and
        copy-deletes in all other cases (cf. bit.ly/shutilmove). File system
        interaction errors (e.g. due to invalid permissions) are written to
        stderr and the program proceeds. By default, the deletion of directories
        requires the directory to be empty. Entire directory trees can be
        removed using -r/--recursive-delete.

        TODO: Add --strict mode (or something like that) that makes file system
        entry action errors fatal?


Time categorization method:
        Each item provided as input becomes classified as either accepted or
        rejected, based on its corresponding timestamp and according to the
        time categorization rules given by the user. For understanding the basic
        meaning of the categorization rules, consider this RULES string example:

            hours12,days5,weeks4

        It translates to the following <category>:<maxcount> pairs:

            hours: 12
            days:   5
            weeks:  4

        Based on the reference time, which by default is the program's startup
        time, the program calculates the age of all ITEMs. According to
        the example rules, the program tries to identify and accept one item
        from each of the last 12 hours, one item from each of the last 5 days,
        and one item from each of the last 4 weeks.

        More specifically, according to the <hours> rule above, the program
        accepts the *newest* item in each of 12 sub-categories: the newest item
        being 1 h old, the newest item being 2 h old, ..., and the newest item
        being 12 h old, yielding at most 12 accepted items from the <hours>
        time category: zero or one for each of the sub-categories.

        An hour is a real time unit, as are all time categories except for the
        <recent> category (explained further below). An item is considered
        X [time unit] old if it is older than X [time unit], but younger than
        X+1 [time unit]. For instance, if an item being 45 days old should be
        sub-categorized within the 'months' category, it would be considered
        1 month old, because it is older than 30 days (1 month) and younger
        than 60 days (2 months). All time category units are treated as linear
        in time (see below for time category specification).

        The example rules above can accept at most 12 + 5 + 4 accepted items. If
        there are multiple items fitting into a certain sub-category (e.g.
        <3-days>), the newest of these is accepted. If there is no item fitting
        into a certain sub-category, then this sub-category stays unpopulated
        and does not yield an item. Considering the example rules above, only 11
        items are accepted from the <hours> category if the input does not
        contain an item for the <5-hours> sub-category, but at least one item
        for all other <X-hours> sub-categories.

        Younger time categories have higher priority than older ones. This is
        only relevant when, according to the rules, two <category>:<maxcount>
        pairs overlap. Example rules:

            days:  10
            weeks:  1

        An item fitting one of the <7/8/9/10-days> sub-categories would also fit
        the <1-weeks> sub-category. In this case, the <X-days> sub-categories
        will be populated first, since <days> is a younger category than
        <weeks>. If there is an 11 days old item in the input, it will populate
        the <1-week> sub-category, because it is the newest 1-week-old item not
        consumed by a younger category.


        Currently supported time categories and their mathematical meaning:

            hours:   60 minutes     (3600 seconds)
            days:    24 hours      (86400 seconds)
            weeks:    7 days      (604800 seconds)
            months:  30 days     (2592000 seconds)
            years:  365 days    (31536000 seconds)

        The special category <recent> keeps track of all items younger than the
        youngest of the categories above, i.e. younger than 1 hour. It is not
        further sub-categorized. If specified in the rules, the <maxcount>
        newest recent items become accepted.


Exit status:
    0 upon success.
    1 upon expected errors detected by the program.
    2 upon argument errors as detected by argparse.
    >0 for other (unexpected) errors.
"""


import os
import sys
import shutil
import argparse
import logging
import re
import time
from .timegaps import FileSystemEntry, FilterItem
from .timefilter import TimeFilter, TimeFilterError


# Make the same code base run with Python 2 and 3.
if sys.version < '3':
    text_type = unicode
    binary_type = str
    stdout_write_bytes = sys.stdout.write
    stdin_read_bytes_until_eof = sys.stdin.read
else:
    text_type = str
    binary_type = bytes
    # http://docs.python.org/3/library/sys.html#sys.stdout
    stdout_write_bytes = sys.stdout.buffer.write
    stdin_read_bytes_until_eof = sys.stdin.buffer.read


WINDOWS = sys.platform == "win32"
if WINDOWS:
    import msvcrt


log = logging.getLogger()
log.setLevel(logging.ERROR)
ch = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s,%(msecs)-6.1f - %(levelname)s: %(message)s',
    datefmt='%H:%M:%S')
ch.setFormatter(formatter)
log.addHandler(ch)


# http://cygwin.com/cygwin-ug-net/using-textbinary.html
# http://stackoverflow.com/a/4160894/145400
# http://code.activestate.com/lists/python-list/20426/
# http://msdn.microsoft.com/en-us/library/tw4k6df8.aspx
# "
#  The _setmode function sets to mode the translation mode of the file given by
#  fd. Passing _O_TEXT as mode sets text (that is, translated) mode. Carriage
#  return–line feed (CR-LF) combinations are translated into a single line feed
#  character on input. Line feed characters are translated into CR-LF
#  combinations on output. Passing _O_BINARY sets binary (untranslated) mode, in
#  which these translations are suppressed.
# "
# On Windows, change mode of stdin and stdout to _O_BINARY, i.e. untranslated
# mode. This translation might be a convenient auto-correction in many
# situations. However, in this program, I want precise control over item
# separation in stdin and stdout. So I prefer not to let Windows implicitly mess
# with the byte streams.  In untranslated mode, the program's test suite can
# largely be the same on Windows and Unix. In translated mode the specification
# of item separation in input and output unnecessarily complicated.
if WINDOWS:
    for stream in (sys.stdout, sys.stdin):
        # ValueError: redirected Stdin is pseudofile, has no fileno()
        # is possible. Seen when py.test imports the package.
        try:
            if sys.version < '3':
                msvcrt.setmode(stream.fileno(), os.O_BINARY)
            else:
                msvcrt.setmode(stream.buffer.fileno(), os.O_BINARY)
        except ValueError as e:
            log.error("Could not set mode to O_BINARY on %s: %s", stream, e)


# To be populated by argparse from cmdline arguments.
options = None


def main():
    parse_options()
    if options.verbose == 1:
        log.setLevel(logging.INFO)
    elif options.verbose == 2:
        log.setLevel(logging.DEBUG)

    # Be explicit about input and output encoding, at least when connected via
    # pipes. Also see http://stackoverflow.com/a/4374457/145400
    if sys.stdout.encoding is None:
        err(("Please explicitly specify the codec that should be used for "
            "decoding data read from stdin, and for encoding data that is to "
            "be written to stdout: set environment variable PYTHONIOENCODING. "
            "Example: export PYTHONIOENCODING=UTF-8."))

    log.debug("Options namespace:\n%s", options)


    # STAGE I: bootstrap, validate and process certain command line arguments.

    # argparse does not catch when the user misses to provide RULES or (one)
    # ITEM (0 ITEMs is allowed when --stdin is set). Validate RULES and
    # ITEMs here in the order as consumed by argparse (first RULES, then ITEMS).
    rules_unicode = options.rules
    if not isinstance(rules_unicode, text_type):
        # Python 3 should always create unicode/text type arguments (which is
        # implicit magic, at least on Unix, but a quite well-behaving magic
        # due to the use of surrogate de(en)coding). Python 2 argv is populated
        # with byte strings, in which case we want to manually decode the RULES
        # string before parsing it. sys.stdout.encoding is either derived from
        # LC_CTYPE (set on the typical Unix system) or from environment
        # variable PYTHONIOENCODING, which is good for overriding and making
        # guarantees.
        rules_unicode = options.rules.decode(sys.stdout.encoding)
    log.debug("Decode rules string.")
    try:
        rules = parse_rules_from_cmdline(rules_unicode)
    except ValueError as e:
        err("Error while parsing rules: '%s'." % e)
    log.info("Using rules: %s", rules)
    if not options.stdin:
        if len(options.items) == 0:
            err("At least one ITEM must be provided (-s/--stdin not set).")
    else:
        if len(options.items) > 0:
            err("No ITEM must be provided on command line (-s/--stdin is set).")

    # Determine reference time and create `TimeFilter` instance. Do this as
    # early as possible: might raise an exception.
    if options.reference_time is not None:
        log.info("Parse reference time from command line.")
        reference_time = seconds_since_epoch_from_localtime_string(
            options.reference_time, "%Y%m%d-%H%M%S")
    else:
        log.debug("Get reference time: now.")
        reference_time = time.time()
    log.info("Using reference time %s (%s).",
        reference_time, time.asctime(time.localtime(reference_time)))
    try:
        timefilter = TimeFilter(rules, reference_time)
    except TimeFilterError as e:
        err("Error upon time filter setup: %s" % e)

    if options.move is not None:
        if not os.path.isdir(options.move):
            err("--move target not a directory: '%s'" % options.move)

    # Pure string interpretation mode is currently not compatible with any type
    # of file system interaction. Forbid.
    if options.time_from_string is not None:
        if options.move or options.delete:
            err(("String interpretation mode is not allowed in combination "
                "with --move or --delete."))

    if options.recursive_delete:
        if not options.delete:
            err("-r/--recursive-delete not allowed without -d/--delete.")


    # STAGE II: collect and validate items.

    log.info("Start collecting item(s).")
    items = prepare_input()
    log.info("Collected %s item(s).", len(items))


    # STAGE III: categorize items.

    log.info("Start item classification.")
    try:
        accepted, rejected = timefilter.filter(items)
    except TimeFilterError as e:
        err("Error while filtering items: %s" % e)
    rejected = list(rejected)
    log.info("Number of accepted items: %s", len(accepted))
    log.info("Number of rejected items: %s", len(rejected))
    log.debug("Accepted item(s):\n%s", "\n".join("%s" % a for a in accepted))
    log.debug("Rejected item(s):\n%s", "\n".join("%s" % r for r in rejected))


    # STAGE IV: item action and item output.

    # - Determine "action items": either the rejected or the accepted ones
    # - For each action item:
    #       - write item to stdout
    #       - perform file system action on item, if specified

    # Write binary data to stdout. If available, use original binary data as
    # provided via input ("pass-through" mode, useful e.g. for paths on Unix,
    # easily done with Python 2) or encode unicode to output encoding, which
    # should re-create the original data as provided via input (Python 3 uses
    # surrogates when parsing argv to unicode objects).
    # If automatically chosen, sys.stdout.encoding might not always be the right
    # thing. However, via PYTHONIOENCODING sys.stdout.encoding can be explicitly
    # set by the user, which is ideal behavior.
    outenc = sys.stdout.encoding
    sep = "\0" if options.nullsep else "\n"
    sep_bytes = sep.encode(outenc)
    actionitems = rejected if not options.accepted else accepted
    for ai in actionitems:
        # If `ai` is of `FileSystemEntry` type, then `path` attribute can be
        # unicode or bytes. If bytes, then write them as they are. If unicode,
        # encode with `outenc`.
        if isinstance(ai, FileSystemEntry):
            itemstring_bytes = ai.path
            if isinstance(ai.path, text_type):
                itemstring_bytes = ai.path.encode(outenc)
        else:
            # `ai` is of type FilterItem: `text` attribute always is unicode.
            itemstring_bytes = ai.text.encode(outenc)
        # __add__ of two byte strings returns byte string with both, Py 2 and 3.
        stdout_write_bytes(itemstring_bytes + sep_bytes)
        action(ai)


def action(item):
    """Perform none or one action on item.

    Currently, this implements file system actions (delete and move).
    """
    if not isinstance(item, FileSystemEntry):
        return
    if options.move:
        tdir = options.move
        log.info("Moving %s to directory %s: %s", item.type, tdir, item.path)
        try:
            shutil.move(item.path, tdir)
        except OSError as e:
            log.error("Cannot move '%s': %s", item.path, e)
        return
    if options.delete:
        log.info("Deleting %s: %s", item.type, item.path)
        if item.type == "dir":
            if options.recursive_delete:
                # shutil.rmtree: Delete an entire directory tree; path must
                # point to a directory (but not a symbolic link to a directory).
                try:
                    shutil.rmtree(item.path)
                except OSError as e:
                    log.error("Error while recursively deleting '%s': %s",
                        item.path, e)
                return
            try:
                # Raises OSError if dir not empty.
                os.rmdir(item.path)
            except OSError as e:
                log.error("Cannot rmdir '%s': %s", item.path, e)
            return
        elif item.type == "file":
            try:
                os.remove(item.path)
            except OSError as e:
                log.error("Cannot delete file '%s': %s", item.path, e)
            return
        else:
            raise NotImplementedError


def read_items_from_stdin():
    """Read items from standard input.

    Regarding stdin decoding: http://stackoverflow.com/a/16549381/145400
    Reading a stream of chunks/records with a different separator than newline
    is not easily possible with stdlib (http://bugs.python.org/issue1152248).
    Take simplest approach for now: read all data (processing cannot start
    before that anyway), then split data (byte string) at sep byte occurrences
    (NUL or newline), then decode each record and return list of unicode
    strings.
    """
    log.debug("Read binary data from standard input, until EOF.")
    try:
        bytedata = stdin_read_bytes_until_eof()
    except (OSError, IOError) as e:
        err("Error reading from stdin: %s" % e)
    log.debug("%s bytes have been read.", len(bytedata))

    enc = sys.stdout.encoding
    sep = "\0" if options.nullsep else "\n"
    sep_bytes = sep.encode(enc)
    log.debug("Split binary stdin data on byte separator %r.", sep_bytes)
    chunks = bytedata.split(sep_bytes)
    log.debug("Decode non-empty chunks using %s.", enc)
    # `split()` is the inverse of `join()`, i.e. it introduces empty strings for
    # leading and trailing separators, and for separator sequences. That is why
    # the `if c` part below is essential. Also see
    # http://stackoverflow.com/a/2197493/145400
    items_unicode = [c.decode(enc) for c in chunks if c]
    log.debug("Identified %s item(s).", len(items_unicode))
    return items_unicode


def prepare_input():
    """Return a list of objects that can be categorized by `TimeFilter.filter`.
    """
    if not options.stdin:
        itemstrings = options.items
        # `itemstrings` can be either unicode or byte strings. On Unix, we
        # want to keep cmdline arguments as raw binary data as long as possible.
        # On Python 3 argv already comes in as sequence of unicode strings.
        # In file system mode on Python 2, treat items (i.e. paths) as byte
        # strings. In time-from-string mode, decode itemstrings (later).
    else:
        itemstrings = read_items_from_stdin()
        # `itemstrings` as returned by `read_items_from_stdin()` are unicode.

    if options.time_from_string is not None:
        log.info("--time-from-string set, don't interpret items as paths.")
        fmt = options.time_from_string
        # Decoding of each single item string.
        # If items came from stdin, they are already unicode. If they came from
        # argv and Python 2 on Unix, they are still byte strings.
        if isinstance(itemstrings[0], binary_type):
            # Again, use sys.stdout.encoding to decode item byte strings, which
            # can be set/overridden via PYTHONIOENCODING.
            itemstrings = [s.decode(sys.stdout.encoding) for s in itemstrings]
        items = []
        for s in itemstrings:
            log.debug("Parsing seconds since epoch from item: %r", s)
            mtime = seconds_since_epoch_from_localtime_string(s, fmt)
            log.debug("Seconds since epoch: %s", mtime)
            items.append(FilterItem(modtime=mtime, text=s))
        return items

    log.info("Interpret items as paths.")
    log.info("Validate paths and extract modification time.")
    fses = []
    for path in itemstrings:
        log.debug("Type of path string: %s.", type(path))
        # On the one hand, a unicode-aware Python program should only use
        # unicode type strings internally. On the other hand, when it comes
        # to file system interaction, byte strings are the more portable choice
        # on Unix-like systems.
        # See https://wiki.python.org/moin/Python3UnicodeDecodeError:
        # "A robust program will have to use only the bytes type to make sure
        #  that it can open / copy / remove any file or directory."
        #
        # On Python 3, which automatically populates argv with unicode objects,
        # we could therefore re-encode towards byte strings. See:
        # http://stackoverflow.com/a/7077803/145400
        # http://bugs.python.org/issue8514
        # https://github.com/oscarbenjamin/opster/commit/61f693a2c553944394ba286baed20abc31958f03
        # On the other hand, there is http://www.python.org/dev/peps/pep-0383/
        # which describes how surrogate encoding is used by Python 3 for
        # auto-correcting argument decoding issues (unknown byte sequences are
        # conserved and re-created upon encoding). Interesting in this regard:
        # http://stackoverflow.com/a/846931/145400

        # Definite choice for Python 2 and Unix: keep paths as byte strings.
        modtime = None
        if options.time_from_basename:
            bn = os.path.basename(path)
            fmt = options.time_from_basename
            log.debug("Parsing modification time from basename: %r", bn)
            modtime = seconds_since_epoch_from_localtime_string(bn, fmt)
            log.debug("Modification time (seconds since epoch): %s", modtime)
        try:
            fses.append(FileSystemEntry(path, modtime))
        except OSError:
            err("Cannot access '%s'." % path)
    log.debug("Created %s item(s) (type: file system entry).", len(fses))
    return fses


def seconds_since_epoch_from_localtime_string(s, fmt):
    """Extract local time from string `s` according to format string `fmt`.

    Return floating point number, indicating seconds since epoch (non-localized
    time, compatible with e.g. stat result st_mtime.
    """
    try:
        # Python 2.7's strptime can deal with `s` and `fmt` being byte string or
        # unicode. Python 3's strptime requires both to be unicode type. Since
        # argv is populated with unicode strings in Py 3, this requirement is
        # always fulfilled.
        time_struct_local = time.strptime(s, fmt)
    except Exception as e:
        err("Error while parsing time from item string. Error: %s" % e)
    try:
        seconds_since_epoch = time.mktime(time_struct_local)
    except Exception as e:
        err(("Error while converting time struct to seconds since epoch. "
            "Struct: %s. Error: %s" % (time_struct_local, e)))
    return seconds_since_epoch


def parse_rules_from_cmdline(s):
    """Parse strings such as 'hours12,days5,weeks4' into rules dictionary.
    """
    assert isinstance(s, text_type)
    tokens = s.split(",")
    rules = {}
    for t in tokens:
        log.debug("Analyze token <%s>", t)
        if not t:
            raise ValueError("Token is empty")
        match = re.search(r'([a-z]+)([0-9]+)', t)
        if match:
            catid = match.group(1)
            timecount = match.group(2)
            if catid not in TimeFilter.valid_categories:
                raise ValueError("Time category '%s' invalid" % catid)
            rules[catid] = int(timecount)
            log.debug("Stored rule: %s: %s", catid, timecount)
            continue
        raise ValueError("Invalid token <%s>" % t)
    return rules


def err(s):
    """Log message `s` with ERROR level and exit with code 1."""
    log.error(s)
    log.info("Exit with code 1.")
    sys.exit(1)


def parse_options():
    """Define and parse command line options using argparse."""
    class ExtHelpAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print(EXTENDED_HELP)
            sys.exit(0)

    description = __doc__  # Use docstring of *this* module.
    parser = argparse.ArgumentParser(
        prog="timegaps",
        description=description,
        epilog="Version %s" % __version__,
        add_help=False
        )
    parser.add_argument("-h", "--help", action="help",
        help="Show help message and exit."
        )
    parser.add_argument("--extended-help", action=ExtHelpAction, nargs=0,
        help="Show extended help message and exit."
        )
    parser.add_argument("--version", action="version",
        version=__version__, help="Show version information and exit."
        )

    parser.add_argument("rules", action="store",
        metavar="RULES",
        help=("A string defining the categorization rules. Must be of the form "
            "<category><maxcount>[,<category><maxcount>[, ... ]]. "
            "Example: 'recent5,days12,months5'. "
            "Valid <category> values: %s. Valid <maxcount> values: "
            "positive integers. Default maxcount for unspecified categories: "
            "0." %
            ", ".join(TimeFilter.valid_categories))
        )
    # Allow an arbitrary number if ITEMs and validate later.
    parser.add_argument("items", metavar="ITEM", action="store", nargs='*',
        help=("Treated as path to file system entry (default) or as "
            "string (--time-from-string mode). Must be omitted in --stdin "
            "mode. Warning: duplicate items are treated independently.")
        )

    parser.add_argument("-s", "--stdin", action="store_true",
        help=("Read items from stdin. The default separator is one "
            "newline character.")
        )
    parser.add_argument("-0", "--nullsep", action="store_true",
        help=("Input and output item separator is NUL character "
            "instead of newline character.")
        )
    parser.add_argument('-a', '--accepted', action='store_true',
        help=("Output accepted items and perform actions on accepted items. "
            "Overrides default, which is to output rejected items (and act on "
            "them).")
        )
    parser.add_argument("-t", "--reference-time", action="store",
        metavar="TIME",
        help=("Parse reference time from local time string TIME. Required "
            "format is YYYYmmDD-HHMMSS. Overrides default reference time, "
            "which is the time of program invocation.")
        )

    timeparsegroup = parser.add_mutually_exclusive_group()
    timeparsegroup.add_argument("--time-from-basename", action="store",
        metavar="FMT",
        help=("Parse item modification time from the item path basename, "
            "according to format string FMT (cf. Python's "
            "strptime() docs at bit.ly/strptime). This overrides the default "
            "behavior, which is to extract the modification time from the "
            "inode.")
        )
    timeparsegroup.add_argument("--time-from-string", action="store",
        metavar="FMT",
        help=("Treat items as strings (do not validate paths). Parse time "
            "from item string using format string FMT (cf. bit.ly/strptime).")
        )

    filehandlegroup = parser.add_mutually_exclusive_group()
    filehandlegroup .add_argument("-d", "--delete", action="store_true",
        help="Attempt to delete rejected paths."
        )
    filehandlegroup.add_argument("-m", "--move", action="store",
        metavar="DIR",
        help="Attempt to move rejected paths to directory DIR."
        )

    parser.add_argument("-r", "--recursive-delete", action="store_true",
        help="Enable deletion of non-empty directories.")
    #parser.add_argument("--follow-symlinks", action="store_true",
    #    help=("Retrieve modification time from symlink target, .. "
    #        "TODO: other implications? Not implemented yet.")
    #    )
    parser.add_argument('-v', '--verbose', action='count', default=0,
        help=("Control verbosity. Can be specified multiple times for "
            "increasing verbosity level. Levels: error (default), info, debug.")
        )

    global options
    options = parser.parse_args()


if WINDOWS and sys.version < '3':
    def win32_unicode_argv():
        """Use shell32.GetCommandLineArgvW to get sys.argv as a list of unicode
        strings. Credits: http://stackoverflow.com/a/846931/145400

        Python 2 does not support unicode in sys.argv on Windows, and replaces
        multi-byte characters with '?'. This hack uses the recommended Windows
        API for retrieving unicode code points. Not necessary for Python 3.
        """
        from ctypes import POINTER, byref, cdll, c_int, windll
        from ctypes.wintypes import LPCWSTR, LPWSTR
        GetCommandLineW = cdll.kernel32.GetCommandLineW
        GetCommandLineW.argtypes = []
        GetCommandLineW.restype = LPCWSTR
        CommandLineToArgvW = windll.shell32.CommandLineToArgvW
        CommandLineToArgvW.argtypes = [LPCWSTR, POINTER(c_int)]
        CommandLineToArgvW.restype = POINTER(LPWSTR)
        cmd = GetCommandLineW()
        argc = c_int(0)
        argv = CommandLineToArgvW(cmd, byref(argc))
        if argc.value > 0:
            # Remove Python executable and commands if present
            start = argc.value - len(sys.argv)
            return [argv[i] for i in
                    xrange(start, argc.value)]

    # Populate sys.argv with unicode objects.
    sys.argv = win32_unicode_argv()


if __name__ == "__main__":
    main()
