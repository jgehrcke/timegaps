# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke (http://gehrcke.de).
# See LICENSE file for details.

from __future__ import unicode_literals

"""Accept or reject files/items based on time categorization.

Feature / TODO brainstorm:
    - symlink support (elaborate specifics)
"""


EXTENDED_HELP = """
timegaps accepts or rejects file system entries based on modification time
categorization. Its input is a set of paths and a set of classification rules.
In the default mode, the output is to two sets of paths, the rejected and the
accepted ones. Details are described below.


Input:
    ITEMs:
        By default, an ITEM value is interpreted as a path to a file system
        entry. By default, the timestamp corresponding to this item (which is
        used for item filtering) is the modification time as reported by
        stat(). Optionally, this timestamp may also be parsed from the basename
        of the path. When interpreted as paths, all ITEM values must point to
        valid file system entries. In a different mode of operation, ITEM
        values are treated as simple strings w/o path validation, in which case
        a timestamp must be parsable from the string itself.
    RULES:
        These rules define the amount of items to be accepted for certain time
        categories. All other items become rejected. Supported time categories
        and the RULES string formatting specification are given in the
        program's normal help text. The exact method of classification is
        explained below.


Output:
        By default, the program writes the rejected items to stdout, whereas
        single items are separated by newline characters. Alternatively, the
        accepted items can be written out instead of the rejected ones. The
        item separator may be set to the NUL character. Log output and error
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
        filter rules, consider this RULES string example:

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
from timegaps import TimeFilter, TimeFilterError, FileSystemEntry, __version__


WINDOWS = sys.platform == "win32"
log = logging.getLogger()
log.setLevel(logging.ERROR)
ch = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s,%(msecs)-6.1f - %(levelname)s: %(message)s',
    datefmt='%H:%M:%S')
ch.setFormatter(formatter)
log.addHandler(ch)

# Global for options, to be populated by argparse from cmdline arguments.
options = None


def main():
    parse_options()
    if options.verbose == 1:
        log.setLevel(logging.INFO)
    elif options.verbose == 2:
        log.setLevel(logging.DEBUG)

    # Be explicit about input and output encoding.
    # Also see http://stackoverflow.com/a/4374457/145400
    if sys.stdout.encoding is None:
        err(("Please explicitly specify the codec that should be used for "
            "decoding data read from stdin, and for encoding data that is to "
            "be written to stdout: set environment variable PYTHONIOENCODING. "
            "Example: export PYTHONIOENCODING=UTF-8."))

    log.debug("Options namespace:\n%s", options)

    # SECTION I: bootstrap. validate and process some arguments.
    # ==========================================================
    # If the user misses to provide either RULES or an ITEM, it is not catched
    # by argparse (0 ITEMs is allowed when --stdin is set). Validate RULES and
    # ITEMs here in the order as consumed by argparse (first RULES, then ITEMS).
    # Doing it the other way round could produce confusing error messages.
    # Parse RULES argument.
    # sys.stdout.encoding is either derived from LC_CTYPE (set on your typical
    # Unix system) or from environment variable PYTHONIOENCODING, which is good
    # for overriding and making guarantees, e.g. on Windows.
    rules_unicode = options.rules
    if not isinstance(rules_unicode, unicode): # TODO: Py3
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

    # Determine reference time and set up `TimeFilter` instance. Do this as
    # early as possible: might raise error.
    if options.reference_time is not None:
        log.debug("Parse reference time from command line.")
        raise NotImplemented
    else:
        log.debug("Get reference time: now.")
        reference_time = time.time()
    log.info("Using reference time %s (%s)." % (
        reference_time, time.asctime(time.localtime(reference_time))))
    try:
        timefilter = TimeFilter(rules, reference_time)
    except TimeFilterError as e:
        err("Error upon time filter setup: %s" % e)

    if options.move is not None:
        if not os.path.isdir(options.move):
            err("--move target not a directory: '%s'" % options.move)


    # SECTION II: collect and validate items.
    # =======================================
    log.info("Start collecting item(s).")
    items = prepare_input()
    log.info("Collected %s item(s).", len(items))


    # SECTION 3) item classification.
    # ===============================
    log.info("Start item classification.")
    accepted, rejected = timefilter.filter(items)
    rejected = list(rejected)
    log.info("Number of accepted items: %s", len(accepted))
    log.info("Number of rejected items: %s", len(rejected))
    log.debug("Accepted item(s):\n%s" % "\n".join("%s" % a for a in accepted))
    log.debug("Rejected item(s):\n%s" % "\n".join("%s" % r for r in rejected))


    # SECTION 4) item output.
    # =======================
    # Write binary data to stdout. Use pre-existing binary data ("pass-through"
    # mode, useful e.g. for paths on Unix) or encode unicode to output encoding.
    # If automatically chosen, sys.stdout.encoding might not always be the right
    # thing:
    # http://drj11.wordpress.com/2007/05/14/python-how-is-sysstdoutencoding-chosen/
    # However, via PYTHONIOENCODING sys.stdout.encoding can be explicitly set
    # by the user, which is ideal behavior (an educated guess is still a guess).
    outenc = sys.stdout.encoding
    sep = "\0" if options.nullsep else "\n"
    sep_bytes = sep.encode(outenc)
    actionitems = rejected if not options.accepted else accepted
    for ai in actionitems:
        # If `ai` is of FileSystemEntry type, then `path` attribute can be
        # unicode or bytes. If bytes, then write them as they are. If unicode,
        # encode with `outenc`.
        if isinstance(ai, FileSystemEntry):
            itemstring_bytes = ai.path
            if isinstance(ai.path, unicode): # TODO: Py3.
                itemstring_bytes = ai.path.encode(outenc)
        else:
            # `ai` is of type FilterItem: `text` attribute always is unicode.
            itemstring_bytes = ai.text.encode(outenc)
        sys.stdout.write("%s%s" % (itemstring_bytes, sep_bytes))
        # In Python 3, write bytes to stdout buffer (after detach).


def read_items_from_stdin():
    # Regarding stdin decoding: http://stackoverflow.com/a/16549381/145400
    # Reading a stream of chunks/records with a different separator than newline
    # is not easily possible with stdlib (http://bugs.python.org/issue1152248).
    # Take simplest approach for now: read all data (processing cannot start
    # before that anyway), then split data (byte string) at sep byte occurrences
    # (NUL or newline), then decode each record and return list of unicode
    # strings.
    # Read until EOF.
    log.debug("Read binary data from standard input, until EOF.")

    # Python 3 opens stdin in text mode (i.e. decodes to unicode). Python 2
    # opens stdin in normal "r" (newline flattening) mide, not in binary mode.
    # Get the binary data, depending on the Python version.

    # In Python 2 on Windows, change mode to binary. Otherwise, two bytes \r\n
    # end up to be only one byte \n. This might be a convenient auto-correction,
    # in certain situations, when the user does not take great care of item
    # separation in stdin, this might make the input to magically work. However,
    # prefer not to magically, implicitly mess with the byte stream on standard
    # input.
    # http://cygwin.com/cygwin-ug-net/using-textbinary.html
    # http://stackoverflow.com/a/4160894/145400
    # http://code.activestate.com/lists/python-list/20426/
    if WINDOWS:
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)

    # TODO: protect with try/except.
    bytedata = sys.stdin.read()
    log.debug("%s bytes have been read.", len(bytedata))

    # TODO: Py3
    enc = sys.stdout.encoding
    sep = "\n"
    if options.nullsep:
        sep = "\0"
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
    """Return a list of objects that can be classified by a `TimeFilter`
    instance.
    """
    if not options.stdin:
        # `itemstrings` can be either unicode or byte strings. On Unix, we
        # want to keep cmdline arguments as raw binary data. In FS mode, keep
        # paths as byte strings. In time-from-string mode, decode itemstrings
        # later.
        itemstrings = options.items
    else:
        # `itemstrings` are only unicode objects.
        itemstrings = read_items_from_stdin()

    if options.time_from_string is not None:
        # TODO: change mode to pure string parsing, w/o item-wise file system
        # interaction
        raise NotImplemented
        # Decoding of *each single item string*.
        if isinstance(itemstrings[0], str): # TODO: Py3
            # Either console or filesystem encoding would make sense here..
            # Use the one that can be easiest changed by the user, i.e.
            # set via PYTHONIOENCODING, i.e. sys.stdout.encoding.
            itemstrings = [s.decode(sys.stdout.encoding) for s in itemstrings]
        # return list_of_items_from_strings

    log.info("Interprete items as file system entries.")
    log.info("Validate paths and extract modification time.")
    fses = []
    for path in itemstrings:
        log.debug("Type of path string: %s.", type(path))

        # On the one hand, a unicode-aware Python program should only use
        # unicode type strings internally. On the other hand, when it comes
        # to file system interaction, bytestrings are the more portable choice
        # on Unix-like systems.
        # See https://wiki.python.org/moin/Python3UnicodeDecodeError:
        # "A robust program will have to use only the bytes type to make sure
        # that it can open / copy / remove any file or directory."
        #
        # On Python 3, which automatically populates argv with unicode objects,
        # we could therefore re-encode towards bytestrings. See:
        # http://stackoverflow.com/a/7077803/145400
        # http://bugs.python.org/issue8514
        # https://github.com/oscarbenjamin/opster/commit/61f693a2c553944394ba286baed20abc31958f03
        # On the other hand,
        # there is http://www.python.org/dev/peps/pep-0383/ which describes how
        # surrogate encoding is used by Python 3 for auto-correcting issues
        # related to wrongly decoded arguments (the encoding assumption upon
        # decoding might have been wrong).
        # Also, interesting in this respect:
        # http://stackoverflow.com/a/846931/145400

        # Definite choice for Python 2 and Unix:
        # keep paths as byte strings.
        modtime = None
        if options.time_from_basename:
            modtime = time_from_basename(path)
        try:
            fses.append(FileSystemEntry(path, modtime))
        except OSError:
            err("Cannot access '%s'." % path)
    log.debug("Created %s item(s) (type: file system entry).", len(fses))
    return fses


def time_from_basename(path):
    """Parse `path`, extract time from basename, according to format string
    in `options.time_from_basename`. Treat time string as local time.

    Return non-localized Unix timestamp.
    """
    # When extracting time from path (basename), use path and format string as
    # unicode objects.
    #
    # On Python 3, argv comes as unicode objects (possibly with surrogate
    # chars).
    #
    # On Python 2, both the format string and the path
    # come as byte strings from sys.argv. By default, attempt to decode
    # both using sys.getfilesystemencoding(), as the best possible
    # guess. Or let the user override via --encoding-args



    #
    raise NotImplemented
    # use options.time_from_basename for parsing string.


def parse_rules_from_cmdline(s):
    """Parse strings such as 'hours12,days5,weeks4' into rules dictionary.
    """
    assert isinstance(s, unicode) # TODO: Py3
    tokens = s.split(",")
    # never happens: http://docs.python.org/2/library/stdtypes.html#str.split
    #if not tokens:
    #    raise ValueError("Error extracting rules from string '%s'" % s)
    rules = {}
    for t in tokens:
        log.debug("Analyze token '%s'", t)
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
    """Log error message as ERROR level and exit with code 1."""
    log.error(s)
    log.info("Exit with code 1.")
    sys.exit(1)


def parse_options():
    """Define and parse command line options using argparse."""
    class ExtHelpAction(argparse.Action):
        def __call__(self, parser, namespace, values, option_string=None):
            print(EXTENDED_HELP)
            sys.exit(0)

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
    parser.add_argument("--extended-help", action=ExtHelpAction, nargs=0,
        help="Show extended help and exit.")
    parser.add_argument("--version", action="version",
        version=__version__, help="Show version information and exit.")


    parser.add_argument("rules", action="store",
        metavar="RULES",
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
            "entries by default. Must be omitted in --stdin mode. It is your "
            "responsibility to not provide duplicate items.")
        )

    filehandlegroup = parser.add_mutually_exclusive_group()
    filehandlegroup .add_argument("-d", "--delete", action="store_true",
        help="Attempt to delete rejected paths."
        )
    filehandlegroup.add_argument("-m", "--move", action="store",
        metavar="DIR",
        help="Attempt to move rejected paths to directory DIR.")


    parser.add_argument("-s", "--stdin", action="store_true",
        help=("Read input items from stdin (default separator: newline).")
        )
    parser.add_argument("-0", "--nullsep", action="store_true",
        help=("Input and output item separator is NUL character "
            "instead of newline character.")
        )
    parser.add_argument("-t", "--reference-time", action="store",
        metavar="FMT",
        help=("Parse time from formatstring FMT (cf. documentation of Python's "
            "strptime() at bit.ly/strptime). Use this time as reference time "
            "(default is time of program invocation).")
        )
    parser.add_argument("--follow-symlinks", action="store_true",
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

    parser.add_argument('-a', '--accepted', action='store_true',
        help=("Output accepted items and perform actions on accepted items "
            "instead of (on) rejected ones.")
        )

    parser.add_argument('-v', '--verbose', action='count', default=0,
        help=("Control verbosity. Can be specified multiple times for "
            "increasing logging level. Levels: error (default), info, debug.")
        )

    options = parser.parse_args()


def time_from_dirname(d):
    # dirs are of type 2013.08.15_20.29.31
    return time.strptime(d, "%Y.%m.%d_%H.%M.%S")


def dirname_from_time(t):
    return time.strftime("%Y.%m.%d_%H.%M.%S", t)


# TODO: Py3 (this hack should not be necessary for 3.3, at least).
if WINDOWS:
    def win32_unicode_argv():
        """Uses shell32.GetCommandLineArgvW to get sys.argv as a list of Unicode
        strings.

        Versions 2.x of Python don't support Unicode in sys.argv on
        Windows, with the underlying Windows API instead replacing multi-byte
        characters with '?'.

        Solution copied from http://stackoverflow.com/a/846931/145400
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
