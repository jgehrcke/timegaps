# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

import os
import sys
import time
from datetime import datetime
from itertools import chain
from random import randint, shuffle
import numpy as np
from matplotlib import pyplot as plt

from timegaps import FileSystemEntry, TimeFilter

import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f [%(process)-5d]%(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


def test_fixed_rules_8_per_cat_with_N_items(N):
    t0 = time.time()
    now = time.time()
    fses = list(fsegen(ref=now, N_per_cat=N, max_timecount=9))
    shuffle(fses)
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
    t0 = time.time()
    a, r = TimeFilter(rules, now).filter(fses)
    duration = time.time() - t0
    return duration


def bench(funcname, samplesize, Ns):
    log.info("Benching '%s' with Ns %s", funcname, Ns)
    durations = []
    for N in Ns:
        dursamples = []
        durations.append(dursamples)
        for _ in xrange(samplesize):
            dursamples.append(globals()[funcname](N))
    log.info("Durations: %s", durations)
    duration_means = [np.mean(_) for _ in durations]
    duration_stddevs = [np.std(_) for _ in durations]
    n_per_sec = Ns[-1]/duration_means[-1]
    linstring = "If linear, from last value pair: %.3f items/s" % n_per_sec
    log.info(linstring)
    log.info("Plotting durations vs. Ns.")
    plt.errorbar(x=Ns, y=duration_means, yerr=duration_stddevs, marker='o')
    plt.title("%s\n%s" % (funcname, linstring), fontsize=10)
    plt.xlabel("N")
    plt.ylabel("duration [s]")
    fname = "%s.png" % funcname
    log.info("Writing %s.", fname)
    plt.savefig(fname, dpi=200)


def main():
    bench("test_fixed_rules_8_per_cat_with_N_items", 10,
        (10**3, 10**4, 5*10**4, 10**5, int(1.5*10**5), 2*10**5, 3*10**5))


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
