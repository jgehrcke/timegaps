# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


from __future__ import unicode_literals
import os
import shutil
import logging
import subprocess
import traceback


logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger("clitest")


class CmdlineTestError(Exception):
    pass


class WrongExitCode(CmdlineTestError):
    pass


class CmdlineInterfaceTest(object):
    """Command line interface test abstraction for a given CLI proram, called
    PROGRAM in the following paragraphs.

    Creates a run directory and a test shell script as a wrapper for the
    actual test (the command to be tested is provided as unicode string,
    and written to this shell script in a certain encoding as given by
    self.shellscript_encoding). This wrapper shell script becomes
    interpreted and executed by a shell of choice (e.g. bash or cmd.exe).
    stdout and stderr of this wrapper are streamed into real files in the
    file system.

    Other CLI program test environments directly use Python's subprocess module
    for invoking PROGRAM including corresponding command line arguments. While
    in real use cases PROGRAM might also become executed this way, the largest
    fraction of use cases is different: This automated method of testing the
    command line behavior of PROGRAM resembles actual user behavior as close as
    possbile. In most cases, a user would either invoke PROGRAM directly by
    typing a command in a shell or write a shell script which he/she then
    executes later.

    This test environt here also uses Python's subprocess module for
    setting the current working directory for the test, for redirecting
    stdout and stderr to files, and for actually invoking the test shell
    script via a command as simple as

        /bin/bash test-shell-script.sh

    The issues prevented with this kind of wrapper shell script technique
    are all issues related to non-obvious argument interpretation magic
    due to argv encoding done by Python's subprocess module -- which
    differs from platform to platform and between Python 2 and 3. Through
    the wrapper script, written in a self-defined encoding, we can
    guarantee under which input conditions exactly the test is executed, and we
    can also guarantee that these conditions are as close as possible to
    the command line conditions in most use cases.

    On Unix systems, the shell works in byte mode, and usually expects
    characters to be UTF-8 encoded, as given by the LANG_ and LC_* environment
    variables (cf. `locale` command in your Unix shell).

    On Windows, cmd.exe can also be made to execute batch files encoded in
    UTF-8 (code page 65001, cf. https://www.google.de/#q=Code+Page+Identifiers)
    A systematic way to reproduce Unix shell behavior w.r.t to encoding:

        @chcp 65001 > nul
        @set PYTHONIOENCODING=utf-8

    See also http://superuser.com/q/269818

    This test runner catches the exit code of the shell script wrapper, which
    should always correspond to the exit code of the last command executed,
    which is PROGRAM. For bash, this is documented: "The equivalent of a bare
    exit is exit $? or even just omitting the exit."
    (http://tldp.org/LDP/abs/html/exit-status.html)

    TODO:
        - look up behavior of cmd.exe on Windows.
        - add features for test inspection/validation
    """
    # If required, these defaults should be overridden in a sub class.
    shellpath = "/bin/bash"
    rundirtop = "."
    shellscript_encoding = "utf-8"
    shellscript_ext = ".sh"

    def __init__(self, name):
        self.name = name
        self.rundir = os.path.join(self.rundirtop, name)
        self.shellscript_name = "runtest_%s%s" % (name, self.shellscript_ext)
        errfilename = "runtest_%s.err" % (name)
        outfilename = "runtest_%s.out" % (name)
        self.errfilepath = os.path.join(self.rundir, errfilename)
        self.outfilepath = os.path.join(self.rundir, outfilename)
        self._clear_create_rundir()

    def _clear_create_rundir(self):
        self.clear()
        os.makedirs(self.rundir)

    def clear(self):
        try:
            shutil.rmtree(self.rundir)
        except OSError:
            # Does not exist, fine.
            pass

    def add_file(self, name, content_bytestring):
        assert isinstance(content_bytestring, str) # TODO: Py3
        p = os.path.join(self.rundir, name)
        with open(p, 'w') as f:
            f.write(content_bytestring)

    def run(self, cmd_unicode, expect_rc=0, log_output=True):
        shellscript_content_bytes = cmd_unicode.encode(
            self.shellscript_encoding)
        self.add_file(self.shellscript_name, shellscript_content_bytes)

        cmd = [self.shellpath, self.shellscript_name]
        of = open(self.outfilepath, "w")
        ef = open(self.errfilepath, "w")
        try:
            sp = subprocess.Popen(cmd, stdout=of, stderr=ef, cwd=self.rundir)
            sp.wait()
            rc = sp.returncode
            log.info("Test returncode: %s", rc)
        except:
            log.error("Error running test subprocess. Traceback:\n%s",
                traceback.format_exc())
            raise CmdlineTestError("Error during attempt to run child.")
        finally:
            of.close()
            ef.close()
        with open(self.outfilepath) as f:
            out = f.read()
        with open(self.errfilepath) as f:
            err = f.read()
        if log_output:
            log.info("Test stdout repr:\n%s", repr(out))
            log.info("Test stderr repr:\n%s", repr(err))
        if rc != expect_rc:
            raise WrongExitCode("Expected %s, got %s" % (expect_rc, rc))
