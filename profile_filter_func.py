# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
from datetime import datetime
from itertools import chain
from random import randint, shuffle
import cProfile, pstats, StringIO

from timegaps import FileSystemEntry, TimeFilter

import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f [%(process)-5d]%(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def main():
    t0 = time.time()
    now = time.time()
    fses = list(fsegen(ref=now, N_per_cat=5*10**4, max_timecount=9))
    shuffle(fses)
    nbr_fses = len(fses)
    n = 8
    rules = {
        "years": n,
        "months": n,
        "weeks": n,
        "days": n,
        "hours": n,
        "recent": n
        }
    sduration = time.time() - t0
    log.info("Setup duration: %.3f s", sduration)
    log.info("Profiling...")
    pr = cProfile.Profile()
    pr.enable()
    a, r = TimeFilter(rules, now).filter(fses)
    pr.disable()
    s = StringIO.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('time')
    ps.print_stats(20)
    print s.getvalue()


class FileSystemEntryMock(FileSystemEntry):
    def __init__(self, modtime):
        self.modtime = modtime

    def __str__(self):
        return "%s(moddate: %s)" % (self.__class__.__name__, self.moddate)

    def __repr__(self):
        return "%s(modtime=%s)" % (self.__class__.__name__, self.modtime)


def nrandint(n, min, max):
    for _ in xrange(n):
        yield randint(min, max)


def fsegen(ref, N_per_cat, max_timecount):
    N = N_per_cat
    c = max_timecount
    nowminusXyears =   (ref-60*60*24*365*i for i in nrandint(N, 1, c))
    nowminusXmonths =  (ref-60*60*24*30 *i for i in nrandint(N, 1, c))
    nowminusXweeks =   (ref-60*60*24*7  *i for i in nrandint(N, 1, c))
    nowminusXdays =    (ref-60*60*24    *i for i in nrandint(N, 1, c))
    nowminusXhours =   (ref-60*60       *i for i in nrandint(N, 1, c))
    nowminusXseconds = (ref-1           *i for i in nrandint(N, 1, c))
    times = chain(
        nowminusXyears,
        nowminusXmonths,
        nowminusXweeks,
        nowminusXdays,
        nowminusXhours,
        nowminusXseconds,
        )
    return (FileSystemEntryMock(modtime=t) for t in times)


if __name__ == "__main__":
    main()
