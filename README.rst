timegaps
========

Timegaps is a command line utility for Unix-like systems as well as Windows. It sorts a set of items into rejected and accepted ones, based on each item's age and a set of time categorization rules.

Timegaps is developed with a strong focus on reliability and with best intentions in mind. It follows the `Unix philosophy <http://en.wikipedia.org/wiki/Unix_philosophy>`_ and semantic versioning. It is backed by a considerable set of unit tests, including direct command line interface tests, and `automatically tested <https://travis-ci.org/jgehrcke/timegaps>`_ against Python 2.7 and 3.3 via Travis CI on Linux.


Installation
------------

timegaps is hosted on PyPI. Install the latest realease with pip::

    $ pip install timegaps
    
Install the latest development version with pip::

    $ pip install git+https://github.com/jgehrcke/timegaps
    

Quick introduction (hands-on)
-----------------------------

Obtain the age of all ``*.tar.gz`` files (which happen to be daily snapshots of something). Age is current time minus file modification time. Accept one snapshot for each of the last 20 days, one for each for the last 8 weeks, and one for each of the last 12 months. Reject all others. Print the rejected ones::

    $ timegaps days20,weeks8,months12 *.tar.gz | sort
    daily-2013-09-17-133413.tar.gz
    [...]
    daily-2014-02-27-070001.tar.gz

Count the rejected ones::

    $ timegaps days20,weeks8,months12 *.tar.gz | wc -l
    125

Move the rejected ones to the directory ``rejected``::

    $ mkdir rejected
    $ timegaps --move rejected days20,weeks8,months12 *.tar.gz > /dev/null
    $ /bin/ls -1 rejected/* | wc -l
    125

This time, do not read the item modification time from the inode via ``stat()``, but read the "modification time" from the basename (which happens to be about the same as the file modification times, in this case)::

    $ mv rejected/* .
    $ timegaps --time-from-basename daily-%Y-%m-%d-%H%M%S.tar.gz \
        days20,weeks8,months12 *.tar.gz | wc -l
    125

Now read items from stdin (newline-separated) instead of from the command line::
        
    $ /bin/ls -1 *tar.gz | timegaps --stdin days20,weeks8,months12 | wc -l
    125

Via ``-0/--nullchar``, timegaps can handle nullchar-separated items on stdin, and then also nullchar-separates items on stdout::

    $ find . -name "*tar.gz" -print0 | \
        timegaps -0 --stdin days20,weeks8,months12 | \
        tr '\0' '\n' | wc -l
    125

Use ``-t/--reference-time`` for changing the reference time from *now* to an arbitrary date (January 1st, 2020 in this case)::
    
    $ timegaps --reference-time 20200101-000000 years10 *.tar.gz | wc -l
    153

Instead of printing the rejected items (default), print the accepted ones::

    $ timegaps -a -t 20200101-000000 years10 *.tar.gz
    daily-2014-02-27-070001.tar.gz
    daily-2014-01-01-070001.tar.gz

There are some more features, such as deleting files, or a mode in which items are treated as simple strings instead of paths. See the program's help message::

    $ timegaps --help
    usage: timegaps [-h] [--extended-help] [--version] [-s] [-0] [-a] [-t TIME]
                    [--time-from-basename FMT | --time-from-string FMT]
                    [-d | -m DIR] [-r] [--follow-symlinks] [-v]
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
      --follow-symlinks     Retrieve modification time from symlink target, ..
                            TODO: other implications? Not implemented yet.
      -v, --verbose         Control verbosity. Can be specified multiple times for
                            increasing verbosity level. Levels: error (default),
                            info, debug.

    Version 0.1.0.dev


There also is ``timegaps --extended-help``, mainly specifying the time categorization behavior in all detail.


Documentation and changelog
---------------------------

    - Official docs: this ``README``, ``timegaps --help``, and ``timegaps --extended-help``. Further resources might be found at http://gehrcke.de/timegaps.
    - Changelog: `Here <https://github.com/jgehrcke/timegaps/blob/master/CHANGELOG.rst>`_,
      hosted at Github.


General description and motivation
----------------------------------

The input item set is either provided with command line arguments or read form stdin. The output is the set of rejected (or accepted) items on stdout.

Timegaps by default treats items as paths. It retrieves the modification time of the corresponding file system entries via ``stat()``. Timegaps can be used to write rejected (or accepted) items to stdout, but also delete or move the corresponding file system entries.

In a different mode, timegaps can treat items as simple strings and extract the "modification time" from each string, according to a given time string format.

Timegaps allows for thinning out a collection of items, whereas the "time gaps" between accepted items become larger with increasing age of items. This is useful for keeping backups logarithmically distributed in time, e.g. one for each of the last 24 hours, one for each of the last 10 days, and so on (years, months, weeks, days, hours, and recent items are currently supported).

Many rely on the well-established backup solution rsnapshot, which has the concept of ``hourly/daily/weekly/...`` snapshots already built in and creates such a structure on the fly. Other backup tools usually lack a useful logic for eliminating old backups. This is where timegaps comes in: you can use the backup solution of your choice for periodically (e.g. hourly) creating snapshots. You can then independently process the set of snapshots with timegaps and identify those snapshots that need to be eliminated in order to maintain a certain distribution of snapshots in time. This is the main motivation behind timegaps, but of course there different use cases.


Requirements
------------

Timegaps is tested on Python 2.7 and Python 3.3 on Linux as well as on Windows.


How can the unit tests be run?
------------------------------

If you run into troubles with timegaps, it is a good idea to run the unit test suite under your conditions. timegaps' unit tests are written for `pytest <http://pytest.org>`_. With ``timegaps/test`` being the current working directory, run the tests like this::

    $ py.test -v


Author & license
----------------

Timegaps is written and maintained by `Jan-Philip Gehrcke <http://gehrcke.de>`_. It is licensed under an MIT license (see LICENSE file).

