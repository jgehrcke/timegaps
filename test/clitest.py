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


class WrongStdout(CmdlineTestError):
    pass


class WrongStderr(CmdlineTestError):
    pass


class CmdlineInterfaceTest(object):
    """Command line interface test abstraction for a given CLI program, called
    PROGRAM from here on.

    Creates a run directory and a test shell script as a wrapper for the
    actual test. The command to be tested is provided as unicode string,
    and written to this shell script in a certain encoding as given by
    self.shellscript_encoding. This wrapper shell script becomes
    interpreted and executed by a shell of choice (e.g. bash or cmd.exe).
    stdout and stderr of this wrapper are streamed into real files.

    Other CLI program test environments directly use Python's subprocess module
    for invoking PROGRAM including corresponding command line arguments. While
    in real use cases PROGRAM might also become executed this way, the largest
    fraction of use cases is different. This test runner's method of testing the
    command line behavior of PROGRAM resembles actual user behavior as close as
    possible: in most cases, a user would either invoke PROGRAM directly by
    typing a command in a shell or write a shell script which the user executes
    later.

    This test environment here also uses Python's subprocess module for
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
    preamble = None
    shellargs = []

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

    def _script_contents(self, cmd_unicode):
        preamble = self.preamble if self.preamble else ""
        return "%s%s\n" % (preamble, cmd_unicode)

    def run(self, cmd_unicode, expect_rc=0, log_output=True):
        shellscript_content_bytes = self._script_contents(cmd_unicode).encode(
            self.shellscript_encoding)
        self.add_file(self.shellscript_name, shellscript_content_bytes)

        cmd = [self.shellpath]
        # If additional args are defined, append them (noop if list is empty).
        cmd.extend(self.shellargs)
        cmd.append(self.shellscript_name)
        of = open(self.outfilepath, "w")
        ef = open(self.errfilepath, "w")
        log.debug("Popen with cmd: %s", cmd)
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
            self.rawout = f.read()
        with open(self.errfilepath) as f:
            self.rawerr = f.read()
        if log_output:
            log.info("Test stdout repr:\n%s", repr(self.rawout))
            log.info("Test stderr repr:\n%s", repr(self.rawerr))
        if rc != expect_rc:
            raise WrongExitCode("Expected %s, got %s" % (expect_rc, rc))

    def assert_no_stderr(self):
        if not self.rawerr == "":
            raise WrongStderr("stderr not empty.")

    def assert_no_stdout(self):
        if not self.rawout == "":
            raise WrongStdout("stdout not empty.")

    def assert_in_stderr(self, expect_in_stderr, encoding=None):
        """ TODO: Implement proper data handling: It should be possible to
        - provide byte string: then search for byte needle in byte haystack
        - unicode string: then decode haystack and search for unicode needle
          in unicode haystack.
        In the latter case, the default codec is `self.shellscript_encoding`.
        If `encoding` is provided, use this.
        """
        # Process expect_in_stderr/out. Each might be None, a single strings or
        # a list of strings.
        if encoding is None:
            encoding = self.shellscript_encoding
        err = self.rawerr.decode(encoding)
        expect_in_stderr = _validate_stringlist(expect_in_stderr)
        for s in expect_in_stderr:
            if s not in err:
                raise WrongStderr("'%s' not in stderr." % s)

    def assert_in_stdout(self, expect_in_stdout, encoding=None):
        if encoding is None:
            encoding = self.shellscript_encoding
        out = self.rawout.decode(encoding)
        expect_in_stdout = _validate_stringlist(expect_in_stdout)
        for s in expect_in_stdout:
            if s not in out:
                raise WrongStdout("'%s' not in stdout." % s)

    def assert_is_stdout(self, expect_stdout, encoding=None):
        """ TODO: Same encoding rules as above.
        """
        if isinstance(expect_stdout, unicode):
            if encoding is None:
                encoding = self.shellscript_encoding
            out = self.rawout.decode(encoding)
        else:
            out = self.rawout
        if expect_stdout != out:
            raise WrongStdout("stdout is not '%s'." % expect_stdout)

    def assert_is_stderr(self, expect_stderr, encoding=None):
        """ TODO: Same encoding rules as above.
        """
        if isinstance(expect_stderr, unicode):
            if encoding is None:
                encoding = self.shellscript_encoding
            err = self.rawerr.decode(encoding)
        else:
            err = self.rawerr
        if expect_stderr != err:
            raise WrongStderr("stderr is not '%s'." % expect_stder)


def _validate_stringlist(stringlist):
    """Make sure that the object returned is a list with at least one item,
    where all items are unicode objects. If a single unicode item is provided,
    transform it to a 1-element-list.
    """
    if not isinstance(stringlist, list):
        stringlist = [stringlist]
    for s in stringlist:
        assert isinstance(s, unicode) # TODO: Py3.
    return stringlist
