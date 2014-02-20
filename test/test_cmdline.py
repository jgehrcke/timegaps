# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.

from __future__ import unicode_literals
import os
import sys
import logging
from py.test import raises, mark
from clitest import CmdlineInterfaceTest, CmdlineTestError, WrongExitCode

sys.path.insert(0, os.path.abspath('..'))
from timegaps import __version__

import logging
logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


RUNDIRTOP = "./cmdline-test"
TIMEGAPS_NAME = "../../../timegaps.py"
PYTHON_EXE = "python"
WINDOWS = sys.platform == "win32"

# Tests involving stdin involve creation of byte strings in this encoding.
STDINENC = "utf-8"


if WINDOWS:
    # Simple solution for LookupError: unknown encoding: cp65001 on Python
    # versions < 3.3 (works in most cases). Ref:
    # http://stackoverflow.com/a/3259271/145400
    import codecs
    codecs.register(
        lambda name: codecs.lookup('utf-8') if name == 'cp65001' else None)


class CmdlineInterfaceTestUnix(CmdlineInterfaceTest):
    rundirtop = RUNDIRTOP
    # Set PYTHONIOENCODING. When connected to pipes (as in the context of
    # py.test, sys.stdout.encoding is None otherwise.)
    preamble = 'export PYTHONIOENCODING="utf-8"\n'


class CmdlineInterfaceTestWindows(CmdlineInterfaceTest):
    shellpath = "cmd.exe"
    # Execute command (/C) and turn off echo (prompt etc, /Q).
    shellargs = ["/Q", "/C"]
    rundirtop = RUNDIRTOP
    shellscript_ext = ".bat"
    # Use PYTHONIOENCODING for enforcing stdout encoding UTF-8 on
    # Windows. I also set console code page via @chcp 65001, but
    # this is not fully analogue to utf-8. References:
    #   - http://bugs.python.org/issue1602
    #   - http://bugs.python.org/issue6058#msg97731
    #   - http://bugs.python.org/issue13216
    #   - http://bugs.python.org/issue13216#msg145901
    #   - http://stackoverflow.com/q/878972/145400
    # Good news: independent of the
    # console code page set, the stdout of the console is the unmodified
    # Python stdout bytestream, which is forced to be UTF-8 via
    # environment variable anyway. Nevertheless, @chcp 65001 is required
    # for special char command line arguments to be properly passed to Python
    # (with the Win 32 sys.argv hack on the receiving end, sys.argv becomes
    # populated with unicode objects).
    preamble = "@chcp 65001 > nul\n@set PYTHONIOENCODING=utf-8\n"


CLITest = CmdlineInterfaceTestUnix
if WINDOWS:
    CLITest = CmdlineInterfaceTestWindows


logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


class Base(object):
    """Implement methods shared by all test classes.
    """

    def setup_method(self, method):
        testname = "%s_%s" % (type(self).__name__, method.__name__)
        print("\n\n%s" % testname)
        self.cmdlinetest = CLITest(testname)

    def teardown_method(self, method):
        pass
        #self.cmdlinetest.clear()

    def run(self, arguments_unicode, rc=0, sin=None):
        cmd = "%s %s %s" % (PYTHON_EXE, TIMEGAPS_NAME, arguments_unicode)
        log.info("Test command:\n%s" % cmd)
        self.cmdlinetest.run(cmd_unicode=cmd, expect_rc=rc, stdinbytes=sin)
        return self.cmdlinetest


class TestArgparseFeatures(Base):
    """Make sure that argparse is set up properly (and works as exepected).
    """

    def test_version(self):
        t = self.run("--version")
        # argparse makes this go to stderr, weird, help goes to stdout.
        t.assert_no_stdout()
        t.assert_is_stderr("%s\n" % __version__)

    def test_help(self):
        t = self.run("--help")
        t.assert_in_stdout(["usage","RULES","ITEM"])
        t.assert_no_stderr()

    def test_extended_help(self):
        t = self.run("--extended-help")
        t.assert_in_stdout(["Input:","Output:","Actions:", "Classification"])
        t.assert_no_stderr()


class TestArgparseLogic(Base):
    """Test argparse argument logic and argparse error detection (also validate
    error messages).
    """

    def test_too_few_args(self):
        # argparse ArgumentParser.error() makes program exit with code 2
        # on Unix. On Windows, it seems to be 1.
        t = self.run("", rc=2)
        t.assert_in_stderr("too few arguments")

    def test_move_missingarg(self):
        t = self.run("--move", rc=2)
        t.assert_no_stdout()
        t.assert_in_stderr(["--move", "expected", "argument"])

    def test_excl_delete_move(self):
        t = self.run("--delete --move DIR", rc=2)
        t.assert_no_stdout()
        t.assert_in_stderr(["--move", "--delete", "not allowed with"])

    def test_excl_time_options(self):
        t = self.run("--time-from-string foo --time-from-basename bar", rc=2)
        t.assert_no_stdout()
        t.assert_in_stderr(["--time-from-basename",
            "not allowed with argument --time-from-string"])

    def test_excl_time_options_2(self):
        t = self.run("--time-from-string a --time-from-basename b c d", rc=2)
        t.assert_no_stdout()
        t.assert_in_stderr(["--time-from-basename",
            "not allowed with argument --time-from-string"])


class TestArgumentErrors(Base):
    """Test argument error detection not performed by argparse,
    validate error messages.
    """

    def test_valid_rules_missing_item_cmdline(self):
        # TODO: also test missing item / valid rules for stdin mode.
        t = self.run("days5", rc=1)
        t.assert_in_stderr("one ITEM must be provided (if --stdin not set")
        t.assert_no_stdout()

    def test_invalid_rulesstring_missing_item(self):
        # Rules are checked first, error must indicate invalid rules.
        t = self.run("bar", rc=1)
        t.assert_in_stderr(["Invalid", "token", "bar"])
        t.assert_no_stdout()

    def test_empty_rulesstring(self):
        # Rules are checked first, error must indicate invalid rules.
        t = self.run('""', rc=1)
        t.assert_in_stderr("Token is empty")
        t.assert_no_stdout()

    def test_invalid_rulesstring_category(self):
        # Rules are checked first, error must indicate invalid rules.
        t = self.run('peter5', rc=1)
        t.assert_in_stderr(["Time category", "invalid"])
        t.assert_no_stdout()

    def test_invalid_rulesstring_wrong_item(self):
        # Rules are checked first, error must indicate invalid rules.
        t = self.run("foo nofile", rc=1)
        t.assert_in_stderr(["Invalid", "token", "foo"])
        t.assert_no_stdout()

    def test_invalid_itempath_1(self):
        t = self.run("days5 nofile", rc=1)
        t.assert_in_stderr(["nofile", "Cannot access"])
        t.assert_no_stdout()

    def test_invalid_itempath_2(self):
        t = self.run("days5 . nofile", rc=1)
        t.assert_in_stderr(["nofile", "Cannot access"])
        t.assert_no_stdout()

    def test_invalid_move_target(self):
        t = self.run("--move nodir days5 . nofile", rc=1)
        t.assert_in_stderr("--move target not a directory")
        t.assert_no_stdout()

    def test_one_item_if_stdin(self):
        t = self.run("--stdin days5 .", rc=1)
        t.assert_in_stderr("No ITEM must be provided when --stdin")
        t.assert_no_stdout()

    def test_all_zero_rules(self):
        t = self.run("-a days0 .", rc=1)
        t.assert_in_stderr("one count > 0 required")
        t.assert_no_stdout()


class TestSimpleFilterFeaturesCWD(Base):
    """Test minimal invocation signatures that filter files. The only file
    system entry used in these tests is the current working directory, which
    has just (recently!) been modified.
    """

    def test_accept_cwd_recent(self):
        # CWD should *just* have been created, so it is recent-accepted.
        # All accepted means no stdout. No verbosity means no stderr.
        t = self.run("recent10 .")
        t.assert_no_stdout()
        t.assert_no_stderr()

    def test_accept_cwd_invert_1(self):
        t = self.run("--accepted recent10 .")
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()

    def test_accept_cwd_invert_2(self):
        # Like above, but try the argument short version.
        t = self.run("-a recent10 .")
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()

    def test_reject_cwd_years(self):
        # CWD should *just* have been created, so it's years-rejected.
        t = self.run("years1 .")
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()

    def test_reject_cwd_years_invert(self):
        # CWD is years-rejected, only print accepted -> no output.
        t = self.run("--accepted years1 .")
        t.assert_no_stdout()
        t.assert_no_stderr()

    def test_reject_cwd_years_multiple_times(self):
        # Duplicate items are treated independently, I cannot think of a
        # use case where providing duplicates makes sense. Still, this behavior
        # is nice for testing.
        t = self.run("years1 . . . . . .")
        t.assert_is_stdout(".\n.\n.\n.\n.\n.\n")
        t.assert_no_stderr()

    def test_cwd_recent_multiple_times(self):
        # Accept 10 recent, print accepted, provide 5 recent -> print 5
        t = self.run("-a recent10 . . . . .")
        t.assert_is_stdout(".\n.\n.\n.\n.\n")
        t.assert_no_stderr()
        # Accept 4 recent, print accepted, provide 5 recent -> print 4
        t = self.run("-a recent4 . . . . .")
        t.assert_is_stdout(".\n.\n.\n.\n")
        t.assert_no_stderr()
        # Accept 4 recent, print rejected, provide 5 recent -> print 1
        t = self.run("recent4 . . . . .")
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()


class TestStdinAndSeparation(Base):
    """Test minimal invocation signatures, use --stdin mode and NUL character
    separation of items. The only file system entry used in these tests is the
    current working directory, which has just (recently!) been modified.
    """
    def test_simple_nullcharsep_1(self):
        # CWD should just have been modified, so it is years-rejected.
        t = self.run("--nullsep years1 .")
        t.assert_is_stdout(".\0")
        t.assert_no_stderr()

    def test_simple_nullcharsep_2(self):
        t = self.run("-0 years1 . . . . . .")
        t.assert_is_stdout(".\0.\0.\0.\0.\0.\0")
        t.assert_no_stderr()

    def test_stdin_one_recent_newline(self):
        # CWD is recently modified.
        s = ".\n".encode(STDINENC)
        t = self.run("--stdin recent1", sin=s)
        t.assert_no_stdout()
        t.assert_no_stderr()
        t = self.run("-s recent1", sin=s)
        t.assert_no_stdout()
        t.assert_no_stderr()
        t = self.run("-a -s recent1", sin=s)
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()

    def test_stdin_one_recent_null(self):
        # CWD is recently modified.
        s = ".\0".encode(STDINENC)
        t = self.run("--nullsep --stdin recent1", sin=s)
        t.assert_no_stdout()
        t.assert_no_stderr()
        t = self.run("-0 -s recent1", sin=s)
        t.assert_no_stdout()
        t.assert_no_stderr()
        t = self.run("-a -0 -s recent1", sin=s)
        t.assert_is_stdout(".\0")
        t.assert_no_stderr()


class TestFileFilter(Base):
    """Tests that involve filtering of file system entries. Involves creation
    of temporary mock files in the file system.
    """
    pass


class TestFileFilterActions(Base):
    """Tests that involve filtering of file system entries. Tests apply actions
    (delete, move). Involves creation and modification of temporary files in the
    file system.
    """
    pass


class TestMisc(Base):
    """Tests that do not fit in other categories.
    """
    def test_multiswitch_1(self):
        # Program should ignore multiple occurrences of simple switches.
        # This is a test from above, with redundant args.
        t = self.run("-a -a recent10 .")
        t.assert_is_stdout(".\n")
        t.assert_no_stderr()

    def test_verbosity_setting_0(self):
        t = self.run("-m nodir days5 nofile", rc=1)
        t.assert_in_stderr(["ERROR", "not a directory"])
        t.assert_not_in_stderr(["DEBUG", "INFO"])
        t.assert_no_stdout()

    def test_verbosity_setting_1(self):
        t = self.run("-v -m nodir days5 nofile", rc=1)
        t.assert_in_stderr(["ERROR", "not a directory"])
        t.assert_in_stderr(
            ["INFO", "Using reference time", "Using rules", "Exit with code 1"])
        t.assert_not_in_stderr("DEBUG")
        t.assert_no_stdout()

    def test_verbosity_setting_2(self):
        t = self.run("-vv -m nodir days5 nofile", rc=1)
        t.assert_in_stderr(["ERROR", "not a directory"])
        t.assert_in_stderr(
            ["INFO", "Using reference time", "Using rules", "Exit with code 1"])
        t.assert_in_stderr(
            ["DEBUG", "Options namespace", "Decode rules", "TimeFilter"])
        t.assert_no_stdout()


class TestSpecialChars(Base):
    """Tests of all classes, involving Unicode challenges.
    """
    def test_invalid_rulesstring_smiley(self):
        t = self.run("☺", rc=1)
        t.assert_in_stderr(["Invalid", "token", "☺"])

