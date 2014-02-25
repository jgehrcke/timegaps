# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


from __future__ import unicode_literals
import os
import sys
import shutil
import logging
import subprocess
import traceback


# Make the same code base run with Python 2 and 3.
if sys.version < '3':
    text_type = unicode
    binary_type = str
else:
    text_type = str
    binary_type = bytes


WINDOWS = sys.platform == "win32"


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


class WrongFile(CmdlineTestError):
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
    Seems to be the same behavior for cmd.exe on Windows 7 (reference?).
    """
    # If required, these defaults should be overridden in a sub class.
    shellpath = "/bin/bash"
    rundirtop = "."
    shellscript_encoding = "utf-8"
    shellscript_ext = ".sh"
    preamble_lines = []
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
        assert isinstance(content_bytestring, binary_type)
        p = os.path.join(self.rundir, name)
        # 'b' mode is required on Python 3, otherwise
        # TypeError: must be str, not bytes.
        with open(p, "wb") as f:
            f.write(content_bytestring)

    def _script_contents(self, cmd_unicode):
        # Use \r\n for separating lines. The batch file is written in 'b' mode,
        # i.e. with Windows' _O_BINARY flag set. This disables magic \n -> \r\n
        # translation. It looks like most of the times a batch file works with
        # \n line breaks. Tests involving special chars, however, show that \n
        # fails where the native Windows line break (\r\n) succeeds.
        return os.linesep.join(self.preamble_lines + [cmd_unicode] + [""])

    def run(self, cmd_unicode, expect_rc=0, stdinbytes=None, log_output=True):
        if stdinbytes is not None:
            log.debug("Prepare stdin data file.")
            log.debug("stdin data repr:\n%r", stdinbytes)
            assert isinstance(stdinbytes, binary_type)
            bn = "_clitest_stdin"
            # Open in 'binary' mode. Is noop on Unix, but disables newline-
            # processing on Windows.
            with open(os.path.join(self.rundir, bn), "wb") as f:
                f.write(stdinbytes)
            if not WINDOWS:
                cmd_unicode = "cat %s | %s" % (bn, cmd_unicode)
            else:
                # type is Windows' analogue command to Unix' cat.
                cmd_unicode = "type %s | %s" % (bn, cmd_unicode)

        shellscript_content_bytes = self._script_contents(cmd_unicode).encode(
            self.shellscript_encoding)
        self.add_file(self.shellscript_name, shellscript_content_bytes)

        cmd = [self.shellpath]
        # If additional args are defined, append them (noop if list is empty).
        cmd.extend(self.shellargs)
        cmd.append(self.shellscript_name)
        of = open(self.outfilepath, "wb")
        ef = open(self.errfilepath, "wb")
        log.debug("Popen with cmd: %s", cmd)
        try:
            sp = subprocess.Popen(
                cmd, stdout=of, stderr=ef, stdin=None, cwd=self.rundir)
            #sp.stdin.write(stdin)
            #sp.stdin.close()
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
        # Open in 'b' mode for retrieving binary contents in Python 3.
        with open(self.outfilepath, "rb") as f:
            self.rawout = f.read()
        with open(self.errfilepath, "rb") as f:
            self.rawerr = f.read()
        if log_output:
            try:
                log.info("Test stdout:\n%s", self.rawout.decode(
                    sys.stdout.encoding))
            except UnicodeDecodeError as e:
                log.info("Cannot decode stdout: %s", e)
            log.info("Test stdout repr:\n%r", self.rawout)
            try:
                log.info("Test stderr:\n%s", self.rawerr.decode(
                    sys.stdout.encoding))
            except UnicodeDecodeError as e:
                log.info("Cannot decode stderr: %s", e)
            log.info("Test stderr repr:\n%r", self.rawerr)
        if rc != expect_rc:
            raise WrongExitCode("Expected %s, got %s" % (expect_rc, rc))

    def assert_no_stderr(self):
        """Raise `WrongStderr` if standard error is not empty."""
        if not self.rawerr == b"":
            raise WrongStderr("stderr not empty.")

    def assert_no_stdout(self):
        """Raise `WrongStdout` if standard output is not empty."""
        if not self.rawout == b"":
            raise WrongStdout("stdout not empty.")

    def assert_in_stdout(self, strings, encoding=None):
        """Verify that one or more strings is/are in standard output.

        If `strings` is byte string search for byte needle in byte
        haystack. If it is unicode string, decode haystack and search for
        unicode needle in unicode haystack. In the latter case, use
        `self.shellscript_encoding` if `encoding` is not provided.

        `strings` can be either a single byte or unicode string or a
        list of strings of the same type.

        Raises:
            `WrongStdout` in case of mismatch.
        """
        out, expected = self._klazonk(self.rawout, strings, encoding)
        for s in expected:
            if s not in out:
                raise WrongStdout("'%r' not in stdout." % s)

    def assert_not_in_stdout(self, strings, encoding=None):
        """Verify that one or more strings is/are not in standard output.

        If `strings` is byte string search for byte needle in byte
        haystack. If it is unicode string, decode haystack and search for
        unicode needle in unicode haystack. In the latter case, use
        `self.shellscript_encoding` if `encoding` is not provided.

        `strings` can be either a single byte or unicode string or a list of
        strings of the same type.

        Raises:
            `WrongStdout` in case of mismatch.
        """
        out, forbidden = self._klazonk(self.rawout, strings, encoding)
        for s in forbidden:
            if s in out:
                raise WrongStdout("'%r' must not be in stdout." % s)

    def assert_in_stderr(self, strings, encoding=None):
        """Verify that one or more strings is/are in standard error.

        If `strings` is byte string search for byte needle in byte
        haystack. If it is unicode string, decode haystack and search for
        unicode needle in unicode haystack. In the latter case, use
        `self.shellscript_encoding` if `encoding` is not provided.

        `strings` can be either a single byte or unicode string or a
        list of strings of the same type.

        Raises:
            `WrongStderr` in case of mismatch.
        """
        err, expected = self._klazonk(self.rawerr, strings, encoding)
        for s in expected:
            if s not in err:
                raise WrongStderr("'%r' not in stderr." % s)

    def assert_not_in_stderr(self, strings, encoding=None):
        """Verify that one or more strings is/are not in standard error.

        If `strings` is byte string search for byte needle in byte
        haystack. If it is unicode string, decode haystack and search for
        unicode needle in unicode haystack. In the latter case, use
        `self.shellscript_encoding` if `encoding` is not provided.

        `strings` can be either a single byte or unicode string or a list of
        strings of the same type.

        Raises:
            `WrongStderr` in case of mismatch.
        """
        err, forbidden = self._klazonk(self.rawerr, strings, encoding)
        for s in forbidden:
            if s in err:
                raise WrongStderr("'%r' must not be in stderr." % s)

    def assert_is_stdout(self, s, encoding=None):
        """Validate that `s` is standard output of test process.

        If `s` is unicode type, decode binary stdout data before comparison.

        Raises:
            `WrongStdout` in case of mismatch.
        """
        out = self.rawout
        if isinstance(s, text_type):
            out = self._decode(self.rawout, encoding)
        if s != out:
            raise WrongStdout("stdout is not '%r'." % s)

    def assert_is_stderr(self, s, encoding=None):
        """Validate that `s` is standard error of test process.

        If `s` is unicode type, decode binary stderr data before comparison.

        Raises:
            `WrongStderr` in case of mismatch.
        """
        err = self.rawerr
        if isinstance(s, text_type):
            err = self._decode(self.rawerr, encoding)
        if s != err:
            raise WrongStderr("stderr is not '%r'." % s)

    def _klazonk(self, out_or_err, string_or_stringlist, encoding):
        """Validate that `string_or_stringlist` is either a byte or unicode
        string, or a list of only byte strings or only unicode strings.
        `out_or_err` must be a byte string. If the type of the single string or
        the elements in the string list is unicode, then decode `out_or_err`
        using the `encoding` specified.

        Return (out_or_err, stringlist) tuple. `stringlist` is a list with at
        least one element, `out_or_err` is either byte string or unicode string.
        """
        assert isinstance(out_or_err, binary_type)
        stringtype, stringlist = _list_string_type(string_or_stringlist)
        if stringtype == text_type:
            out_or_err = self._decode(out_or_err, encoding)
        return out_or_err, stringlist

    def _decode(self, raw, encoding):
        if encoding is None:
            encoding = self.shellscript_encoding
        return raw.decode(encoding)

    def assert_paths_exist(self, p):
        """Validate that path(s) exist relative to run directory.

        `p` must be a single string or a list of strings (byte or unicode).
        Use os.path.exists, which fails for broken symbolic links any may fail
        for invalid permissions.
        """
        self._paths_exist(p)

    def assert_paths_not_exist(self, p):
        """Validate that path(s) do not exist relative to run directory.

        `p` must be a single string or a list of strings (byte or unicode).
        Use os.path.exists, which fails for broken symbolic links any may fail
        for invalid permissions.
        """
        self._paths_exist(p, invert=True)

    def _paths_exist(self, p, invert=False):
        _, pathlist = _list_string_type(p)
        for path in pathlist:
            assert isinstance(path, binary_type) or isinstance(path, text_type)
            testpath = os.path.join(self.rundir, path)
            if not os.path.exists(testpath):
                if not invert:
                    raise WrongFile("Path does not exist: '%s'" % path)
                return
            if invert:
                raise WrongFile("Path should not exist: '%s'" % path)


def _list_string_type(o):
    """`o` must be a string or a list of strings. A string must either be byte
    string or unicode string. If `o` is a list, all elements must be of same
    type. If `o` is a single string, transform it to a 1-element-list.

    Return (stringtype, stringlist).
    """
    if not isinstance(o, list):
        o = [o]
    ts = list(set(type(_) for _ in o))
    if len(ts) > 1:
        raise Exception("List %r must contain only one data type." % o)
    t = ts[0]
    if t == binary_type or t == text_type:
        return t, o
    raise Exception(("Invalid %r: must be a string (byte or unicode) or a list "
        "of strings (of the same type)." % o))
