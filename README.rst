timegaps
========

Timegaps is a cross-platform command line program. It sorts a set of items into
*rejected* and *accepted* ones, based on the age of each item and user-given
time categorization rules.

Timegaps allows for thinning out a collection of items, whereas the *time gaps*
between accepted items become larger with increasing age of items. This is
useful for implementing *backup retention policies* with the goal to keep
backups "logarithmically" distributed in time, e.g. one for each of the last 24
hours, one for each of the last 30 days, one for each of the last 8 weeks, and
so on.

Timegaps is built with a focus on reliability. It is backed by a considerable
set of unit tests, including direct command line interface tests. Currently,
each commit is `automatically tested <https://travis-ci.org/jgehrcke/timegaps>`_
against CPython 2.7/3.3/3.4 on Linux via Travis CI. Releases are tested on Linux
as well as on Windows. Simplicity and compliance with the `Unix philosophy
<http://en.wikipedia.org/wiki/Unix_philosophy>`_ are the major design goals of
timegaps. Version tags follow the concept of semantic versioning.


Requirements
------------

Timegaps requires `Python <http://python.org>`_. Releases are tested on CPython
2.7/3.3/3.4, on Linux as well as on Windows. This is where you can expect it to
run properly.


Installation
------------

Installation via `pip <http://www.pip-installer.org/en/latest/>`_ is
recommended::

    $ pip install timegaps

This downloads the latest timegaps releases `from PyPI
<https://pypi.python.org/pypi/timegaps/>`_ and installs it. A previously
installed version can be upgraded via::

    $ pip install --upgrade timegaps

This is how to install the latest development version::

    $ pip install git+https://github.com/jgehrcke/timegaps


Documentation and changelog
---------------------------

- Docs and resources: the official home of this program is
  http://gehrcke.de/timegaps. The documentation consists of this ``README``,
  ``timegaps --help``, and ``timegaps --extended-help``.
- `Changelog <https://github.com/jgehrcke/timegaps/blob/master/CHANGELOG.rst>`_.


Hands-on introduction
---------------------

Consider the following situation: all ``*.tar.gz`` files in the current working
directory happen to be daily snapshots of something. The task is to accept one
snapshot for each of the last 20 days, one for each for the last 8 weeks, and
one for each of the last 12 months, and to *reject all others*. Use timegaps for
performing this categorization into rejected and accepted items and print the
rejected ones::

    $ timegaps days20,weeks8,months12 *.tar.gz | sort
    daily-2013-09-17-133413.tar.gz
    [...]
    daily-2014-02-27-070001.tar.gz

This was a read-only, non-invasive operation. By default, timegaps prints the
rejected items to stdout, separated by newline characters (for compatibility
with other Unix command line tools). Repeat the operation and count the rejected
items::

    $ timegaps days20,weeks8,months12 *.tar.gz | wc -l
    125

Given this specific set of rules and set of items, timegaps identified 125 items
to be rejected. Move them to the directory ``notneededanymore`` (and suppress
stdout)::

    $ mkdir notneededanymore
    $ timegaps --move notneededanymore days20,weeks8,months12 *.tar.gz > /dev/null

Count files in the newly created directory for validation purposes (must also be
125)::

    $ /bin/ls -1 notneededanymore/* | wc -l
    125

Okay, so far the item modification time was determined from the inode via the
``stat()`` system call. In a different mode of operation (``--time-from-
basename``), timegaps can read the "modification time" from the basename. The
file names of the tarred snapshots in this hands-on session carry meaningful
time information, in a certain format (``daily-%Y-%m-%d-%H%M%S.tar.gz``).
Providing this format string, we can instruct timegaps to parse the time from
these file names::

    $ mv notneededanymore/* .
    $ timegaps --time-from-basename daily-%Y-%m-%d-%H%M%S.tar.gz \
        days20,weeks8,months12 *.tar.gz | wc -l
    125

The above can be useful in cases where the actual file modification time is
screwed, and the real timing information is only contained in the file name. In
another mode of operation (``--stdin``), timegaps can read newline-separated
items from stdin, instead of reading items from the command line::

    $ /bin/ls -1 *tar.gz | timegaps --stdin days20,weeks8,months12 | wc -l
    125

Given ``-0/--nullsep``, timegaps can handle NUL character-separated items on
stdin. In this mode of operation, timegaps also NUL-separates the items on
stdout::

    $ find . -name "*tar.gz" -print0 | \
        timegaps -0 --stdin days20,weeks8,months12 | \
        tr '\0' '\n' | wc -l
    125

By default, the reference time for determining the age of items is the time of
program invocation. Use ``-t/--reference-time`` for changing the reference time
from *now* to an arbitrary date (January 1st, 2020 in this case)::

    $ timegaps --reference-time 20200101-000000 years10 *.tar.gz | wc -l
    153

With a different reference time and different rules the number of rejected items
obviously changed (from 125 to 153). Instead of printing the rejected items,
timegaps can invert the output and print the accepted ones::

    $ timegaps -a -t 20200101-000000 years10 *.tar.gz
    daily-2014-02-27-070001.tar.gz
    daily-2014-01-01-070001.tar.gz

There are more features, such as deleting files, or a mode in which items are
treated as simple strings instead of paths. See the help message::

    $ timegaps --help
    usage: timegaps [-h] [--extended-help] [--version] [-s] [-0] [-a] [-t TIME]
                    [--time-from-basename FMT | --time-from-string FMT]
                    [-d | -m DIR] [-r] [-v]
                    RULES [ITEM [ITEM ...]]

    Accept or reject items based on age categorization.

    positional arguments:
      RULES                 A string defining the categorization rules. Must be of
                            the form <category><maxcount>[,<category><maxcount>[,
                            ... ]]. Example: 'recent5,days12,months5'. Valid
                            <category> values: years, months, weeks, days, hours,
                            recent. Valid <maxcount> values: positive integers.
                            Default maxcount for unspecified categories: 0.
      ITEM                  Treated as path to file system entry (default) or as
                            string (--time-from-string mode). Must be omitted in
                            --stdin mode. Warning: duplicate items are treated
                            independently.

    optional arguments:
      -h, --help            Show help message and exit.
      --extended-help       Show extended help message and exit.
      --version             Show version information and exit.
      -s, --stdin           Read items from stdin. The default separator is one
                            newline character.
      -0, --nullsep         Input and output item separator is NUL character
                            instead of newline character.
      -a, --accepted        Output accepted items and perform actions on accepted
                            items. Overrides default, which is to output rejected
                            items (and act on them).
      -t TIME, --reference-time TIME
                            Parse reference time from local time string TIME.
                            Required format is YYYYmmDD-HHMMSS. Overrides default
                            reference time, which is the time of program
                            invocation.
      --time-from-basename FMT
                            Parse item modification time from the item path
                            basename, according to format string FMT (cf. Python's
                            strptime() docs at bit.ly/strptime). This overrides
                            the default behavior, which is to extract the
                            modification time from the inode.
      --time-from-string FMT
                            Treat items as strings (do not validate paths). Parse
                            time from item string using format string FMT (cf.
                            bit.ly/strptime).
      -d, --delete          Attempt to delete rejected paths.
      -m DIR, --move DIR    Attempt to move rejected paths to directory DIR.
      -r, --recursive-delete
                            Enable deletion of non-empty directories.
      -v, --verbose         Control verbosity. Can be specified multiple times for
                            increasing verbosity level. Levels: error (default),
                            info, debug.

    Version 0.1.0


For a detailed specification of program behavior and the time categorization
method, please confer ``timegaps --extended-help``.


General description
-------------------

Timegaps' input item set is either provided with command line arguments or read
from stdin. The output is the set of rejected or accepted items, written to
stdout.

Timegaps by default treats items as paths. It retrieves the modification time
(``st_mtime``) of the corresponding file system entries via the ``stat`` system
call. By default, timegaps works in a non-invasive read-only mode and simply
lists the rejected (or accepted) items. If explicitly requested, timegaps can
also directly delete or move the corresponding file system entries, using well-
established functions from Python's standard ``shutil`` module.

In a special mode of operation, timegaps can treat items as simple strings
without path validation and extract the "modification time" from each string,
according to a given time string format. This feature can be used for filtering
any kind of time-dependent data, but also for filtering e.g. ZFS snapshots.


Main motivation
---------------

The well-established backup solution `rsnapshot <http://www.rsnapshot.org/>`_
has the useful concept of ``hourly / daily / weekly / ...`` snapshots already
built in and creates such a structure on the fly. Unfortunately, other backup
approaches often lack such a fine-grained backup retention logic, and people
tend to hack simple filters themselves. Furthermore, even rsnapshot is not able
to post-process and thin out an existing set of snapshots. This is where
timegaps comes in: you can use the backup solution of your choice for
periodically (e.g. hourly) creating a snapshot. You can then — independently
and at any time — process this set of snapshots with timegaps and identify
those snapshots that need to be eliminated (removed or displaced) in order to
maintain a certain “logarithmic” distribution of snapshots in time. This is the
main motivation behind timegaps, but of course you can use it for filtering any
kind of time-dependent data.


How can the unit tests be run?
------------------------------

If you run into troubles with timegaps, or if you want to verify whether it
properly runs on your platform, it is a good idea to run the unit test suite
under your conditions. Timegaps' unit tests are written for `pytest
<http://pytest.org>`_. With ``timegaps/test`` being the current working
directory, run the tests like this::

    $ py.test -v


Author & license
----------------

Timegaps is written and maintained by `Jan-Philip Gehrcke <http://gehrcke.de>`_.
It is licensed under an MIT license (see LICENSE file).

