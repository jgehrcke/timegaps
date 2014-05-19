# -*- coding: utf-8 -*-
# Copyright 2014 Jan-Philip Gehrcke. See LICENSE file for details.


"""
Command line interface tests (execution through shell).
"""


from __future__ import unicode_literals
import os
import sys
import time
import logging
from itertools import chain
from clitest import CmdlineInterfaceTest


sys.path.insert(0, os.path.abspath('..'))
from timegaps.main import __version__


logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


# Make the same code base run with Python 2 and 3.
if sys.version < '3':
    range = xrange
else:
    pass


RUNDIRTOP = "./cmdline-test"
TIMEGAPS_RUNNER = "python ../../../timegaps-runner.py"
# On travis, `python setup.py install` has been executed before and the
# `timegaps` command must be available.
if os.environ.get("TRAVIS") == "true" and os.environ.get("CI") == "true":
    TIMEGAPS_RUNNER = "timegaps"
#TIMEGAPS_RUNNER = "coverage -x ../../../timegaps-runner.py"
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
    preamble_lines = ['export PYTHONIOENCODING="utf-8"']


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
    preamble_lines = ["@chcp 65001 > nul", "@set PYTHONIOENCODING=utf-8"]


CLITest = CmdlineInterfaceTestUnix
if WINDOWS:
    CLITest = CmdlineInterfaceTestWindows


logging.basicConfig(
    format='%(asctime)s,%(msecs)-6.1f %(funcName)s# %(message)s',
    datefmt='%H:%M:%S')
log = logging.getLogger()
log.setLevel(logging.DEBUG)


class Base(object):
    """Implement methods shared by all test classes."""

    def setup_method(self, method):
        testname = "%s_%s" % (type(self).__name__, method.__name__)
        print("\n\n%s" % testname)
        self.clitest = CLITest(testname)
        self.rundir = self.clitest.rundir

    def teardown_method(self, method):
        pass
        #self.cmdlinetest.clear()

    def run(self, arguments_unicode, rc=0, sin=None):
        arguments_unicode = self._escape_args(arguments_unicode)
        cmd = "%s %s" % (TIMEGAPS_RUNNER, arguments_unicode)
        log.info("Test command:\n%s",  cmd)
        self.clitest.run(cmd_unicode=cmd, expect_rc=rc, stdinbytes=sin)
        return self.clitest

    def mfile(self, relpath, mtime=None):
        # http://stackoverflow.com/a/1160227/145400
        # Insignificant race condition.
        mtime = mtime if mtime is not None else time.time()
        p = os.path.join(self.rundir, relpath)
        with open(p, "w"):
            os.utime(p, (mtime, mtime))

    def mdir(self, relpath, mtime=None):
        mtime = mtime if mtime is not None else time.time()
        p = os.path.join(self.rundir, relpath)
        os.mkdir(p)
        os.utime(p, (mtime, mtime))

    def _escape_args(self, args):
        if WINDOWS:
            # On Windows, clitest executes the test command through a batch
            # file. Batch file processing is different from normal command line
            # processing. Regarding percent signs used in time format strings:
            # In the normal command line, single percent signs work well. In the
            # batch file, they must be escaped by another percent sign.
            # http://stackoverflow.com/a/4095133/145400
            args = args.replace("%", "%%")
        return args


class TestArgparseFeatures(Base):
    """Make sure that argparse is set up properly (and works as exepected).
    """

    def test_version(self):
        t = self.run("--version")
        # On Python < 3.4, argparse writes this to stderr (help goes to stdout).
        # http://bugs.python.org/issue18920
        if sys.version_info[0] >= 3 and sys.version_info[1] >= 4:
            t.assert_no_stderr()
            t.assert_is_stdout("%s%s" % (__version__, os.linesep))
        else:
            t.assert_no_stdout()
            t.assert_is_stderr("%s%s" % (__version__, os.linesep))

    def test_help(self):
        t = self.run("--help")
        t.assert_in_stdout(["usage", "RULES", "ITEM"])
        t.assert_no_stderr()

    def test_extended_help(self):
        t = self.run("--extended-help")
        t.assert_in_stdout(
            ["Input:", "Output:", "Actions:", "Time categorization method:"])
        t.assert_no_stderr()


class TestArgparseLogic(Base):
    """Test argparse argument logic and argparse error detection (also validate
    error messages).
    """

    def test_too_few_args(self):
        # argparse ArgumentParser.error() makes program exit with code 2
        # on Unix. On Windows, it seems to be 1.
        t = self.run("", rc=2)
        if sys.version < '3':
            t.assert_in_stderr("too few arguments")
        else:
            t.assert_in_stderr("arguments are required: RULES, ITEM")

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
        t.assert_in_stderr("one ITEM must be provided (-s/--stdin not set")
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

    def test_invalid_rulesstring_negative_count(self):
        # Rules are checked first, error must indicate invalid rules.
        t = self.run("days-1 nofile", rc=1)
        t.assert_in_stderr(["Invalid", "token", "days"])
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
        t.assert_in_stderr(["No ITEM must be provided", "(-s/--stdin is set)"])
        t.assert_no_stdout()

    def test_all_zero_rules(self):
        t = self.run("-a days0 .", rc=1)
        t.assert_in_stderr("one count > 0 required")
        t.assert_no_stdout()

    def test_action_string_interpr_mode_1(self):
        t = self.run("-m . --time-from-string FMT days1 .", rc=1)
        t.assert_in_stderr(["String interpretation mode is not allowed",
         "--move"])
        t.assert_no_stdout()

    def test_action_string_interpr_mode_2(self):
        t = self.run("-d --time-from-string FMT days1 .", rc=1)
        t.assert_in_stderr(["String interpretation mode is not allowed",
         "--move"])
        t.assert_no_stdout()

    def test_recursive_delete_wo_delete(self):
        t = self.run("-r days1 .", rc=1)
        t.assert_in_stderr(
            "-r/--recursive-delete not allowed without -d/--delete")
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

    timegaps interprets stdin data as byte chunks separated by a byte string
    separator. Each chunk is decoded to unicode using a certain codec. The
    inverse operation for the creation of such stdin data is:
        - create unicode item strings
        - encode these to byte strings (each of them yielding a "chunk")
        - sep.join() these chunks with `sep` being the byte string separator

    Here, we make our lives simpler. The stdin data as specified in these tests
    is usually created as unicode strings *including* separators and then, as
    a whole, encoded to UTF-8. For UTF-8 the result is the same as with the
    multi-step process described above, because \0 and \n have the same byte
    representation in UTF-8 and ASCII (and we use ASCII to create the bytes
    considered as separators: null character x00 and newline x0A).
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

    def test_stdin_one_recent_no_sep(self):
        s = ".".encode(STDINENC)
        t = self.run("-a -0 -s recent1", sin=s)
        t.assert_is_stdout(".\0")
        t = self.run("-a -s recent1", sin=s)
        t.assert_is_stdout(".\n")

    def test_stdin_two_recent_various_seps(self):
        # Missing trailing sep.
        s = ".\n.".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Additional leading sep.
        s = "\n.\n.\n".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Two separators + no trailing.
        s = ".\n\n.".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Three separators + no trailing.
        s = ".\n\n\n.".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Multi + trailing.
        s = ".\n\n.\n".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Multi + multi trailing.
        s = ".\n\n.\n\n".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()

        # Multi leading + multi + multi trailing.
        s = "\n\n.\n\n.\n\n".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout(".\n.\n")
        t.assert_no_stderr()


class TestStringInterpretationMode(Base):
    """Test string interpretation mode, i.e. do not treat items as paths, just
    as simple strings containing time information.
    """

    fmt = "%Y%m%d-%H%M%S"

    def test_onearg(self):
        t = self.run("--time-from-string %s days1 20001112-111213" % self.fmt)
        t.assert_is_stdout("20001112-111213\n")
        t.assert_no_stderr()

    def test_onearg_debuglog(self):
        t = self.run(
            "-vv --time-from-string %s days1 20001112-111213" % self.fmt)
        t.assert_is_stdout("20001112-111213\n")
        t.assert_in_stderr([
            "INFO: --time-from-string set, don't interpret items as paths.",
            "Seconds since epoch:",
            "FilterItem(text: 20001112-111213, moddate: 2000-11-12 11:12:13)"])

    def test_onearg_fmterror_1(self):
        t = self.run("--time-from-string %s days1 xxx" % self.fmt, rc=1)
        t.assert_in_stderr(["ERROR", "xxx", "does not match format"])

    def test_onearg_fmterror_2(self):
        t = self.run(
            "--time-from-string %s days1 20000000-111213" % self.fmt, rc=1)
        t.assert_in_stderr(["ERROR", "20000000", "does not match format"])

    def test_multi_item_stdin(self):
        items = ["20001112-111213", "20001112-111214","20001112-111215"]
        s = "\n".join(items).encode(STDINENC)
        t = self.run("--stdin --time-from-string %s days1" % self.fmt, sin=s)
        t.assert_is_stdout(s + b"\n")
        t.assert_no_stderr()

        s = "\0".join(items).encode(STDINENC)
        t = self.run("-s -0 --time-from-string %s days1" % self.fmt, sin=s)
        t.assert_is_stdout(s + b"\0")
        t.assert_no_stderr()


class TestReferenceTime(Base):
    """Test -t/--reference-time parsing and logic."""

    def test_reject(self):
        t = self.run(("-t 20000101-000000 --time-from-string %Y%m%d-%H%M%S "
            "days1 19990101-000000"))
        t.assert_is_stdout("19990101-000000\n")
        t.assert_no_stderr()

    def test_accept(self):
        t = self.run(("-a -t 20000201-000000 --time-from-string %Y%m%d-%H%M%S "
            "years1 19990101-000000"))
        t.assert_is_stdout("19990101-000000\n")
        t.assert_no_stderr()

    def test_log(self):
        t = self.run(("-v -t 20000101-000000 --time-from-string %Y%m%d-%H%M%S "
            "days1 19990101-000000"))
        t.assert_is_stdout("19990101-000000\n")
        t.assert_in_stderr("INFO: Parse reference time from command line")

    def test_negative(self):
        t = self.run(("-t 20000101-000000 --time-from-string %Y%m%d-%H%M%S "
            "years1 20010101-000000"), rc=1)
        t.assert_no_stdout()
        t.assert_in_stderr(["ERROR: Error while filtering items",
            "not earlier than reference"])


class TestPathBasenameTime(Base):
    """Test --time-from-basename parsing and logic. These tests may involve
    creation of temp files."""

    def test_file_error(self):
        t = self.run(("-t 20000101-000000 --time-from-basename "
            "%Y%m%d-%H%M%S.dat days1 19990101-000000.dat"), rc=1)
        t.assert_no_stdout()
        t.assert_in_stderr(["ERROR: Cannot access", "19990101-000000.dat"])

    def test_reject(self):
        fn = "19990101-000000.dat"
        self.clitest.add_file(fn, b"")
        t = self.run(("-t 20000101-000000 --time-from-basename "
            "%Y%m%d-%H%M%S.dat days1 19990101-000000.dat"), rc=0)
        t.assert_is_stdout("19990101-000000.dat\n")
        t.assert_no_stderr()

    def test_accept(self):
        fn = "19990101-000000.dat"
        self.clitest.add_file(fn, b"")
        t = self.run(("-a -t 20000201-000000 --time-from-string "
            "%Y%m%d-%H%M%S.dat years1 19990101-000000.dat"))
        t.assert_is_stdout("19990101-000000.dat\n")
        t.assert_no_stderr()


class TestFileFilter(Base):
    """Filter tests involving temp files. Test various features, but no
    actions.
    """

    def test_10_days_2_weeks_noaction_files(self):
        self._10_days_2_weeks_noaction_dirs_or_files(self.mfile)

    def test_10_days_2_weeks_noaction_dirs(self):
        self._10_days_2_weeks_noaction_dirs_or_files(self.mdir)

    def _10_days_2_weeks_noaction_dirs_or_files(self, mfile_or_dir):
        # `mfile_or_dir` is either self.mfile or self.mdir, so that this test
        # can easily be run against a set of files or dirs.
        # Logically, this is a copy of test_10_days_2_weeks in test_api.py.
        # This time, use real files.
        # FSEs 1-11,14 must be accepted (12 FSEs). 15 FSEs are used as input
        # (1 to 15 days old), i.e. 3 are to be rejected (FSEs 12, 13, 15).
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in range(1,16))
        name_time_pairs = [
            ("f%s" % (i+1,), t) for i,t in enumerate(nowminusXdays)]
        for name, mtime in name_time_pairs:
            mfile_or_dir(name, mtime)

        itemargs = " ".join(name for name, _ in name_time_pairs)
        a = ["f%s\n" % _ for _ in (1,2,3,4,5,6,7,8,9,10,11,14)]
        r = ["f12\n", "f13\n", "f15\n"]

        t = self.run("days10,weeks2 %s" % itemargs)
        t.assert_in_stdout(r)
        t.assert_not_in_stdout(a)
        t.assert_no_stderr()

        # Invert output.
        t = self.run("-a days10,weeks2 %s" % itemargs)
        t.assert_in_stdout(a)
        t.assert_not_in_stdout(r)
        t.assert_no_stderr()

        # Use stdin input.
        s = "\n".join(itemargs.split()).encode(STDINENC)
        t = self.run("-s -a days10,weeks2", sin=s)
        t.assert_in_stdout(a)
        t.assert_not_in_stdout(r)
        t.assert_no_stderr()

        # Use stdin input, nullchar separation.
        s = "\0".join(itemargs.split()).encode(STDINENC)
        t = self.run("-0 -s -a days10,weeks2", sin=s)
        t.assert_in_stdout(["f%s\0" % _ for _ in (1,2,3,4,5,6,7,8,9,10,11,14)])
        t.assert_not_in_stdout(["f12\0", "f13\0", "f15\0"])
        t.assert_no_stderr()


class TestFileFilterActions(Base):
    """Tests that involve filtering of file system entries. Tests apply actions
    (delete, move). Tests involve creation and modification of temporary files
    in the test run directory.
    """
    def test_simple_delete_file(self):
        self._test_simple_delete_file_or_dir(self.mfile)

    def test_simple_delete_dir(self):
        self._test_simple_delete_file_or_dir(self.mdir)

    def _test_simple_delete_file_or_dir(self, mfile_or_dir):
        mfile_or_dir("test")
        t = self.run("--delete days1 test")
        t.assert_in_stdout("test")
        t.assert_no_stderr()
        t.assert_paths_not_exist("test")

    def gen_files_or_dirs(self, mfile_or_dir):
        # `mfile_or_dir` is either self.mfile or self.mdir, so that this test
        # can easily be run against a set of files or dirs.
        # Test logic is explained in test_api: 10_days_2_weeks.
        now = time.time()
        nowminusXdays = (now-(60*60*24*i+1) for i in range(1,16))
        name_time_pairs = [
            ("t%s" % (i+1,), t) for i,t in enumerate(nowminusXdays)]
        # Create dir or file of name `name` for each name-mtime pair.
        for name, mtime in name_time_pairs:
            mfile_or_dir(name, mtime)
        itemargs = " ".join(name for name, _ in name_time_pairs)
        a_paths = ["t%s" % _ for _ in (1,2,3,4,5,6,7,8,9,10,11,14)]
        r_paths = ["t12", "t13", "t15"]
        a = ["%s\n" % _ for _ in a_paths]
        r = ["%s\n" % _ for _ in r_paths]
        return a, r, a_paths, r_paths, itemargs

    def test_10_days_2_weeks_move_files(self):
        self._10_days_2_weeks_move_dirs_or_files(self.mfile)

    def test_10_days_2_weeks_move_dirs(self):
        self._10_days_2_weeks_move_dirs_or_files(self.mdir)

    def _10_days_2_weeks_move_dirs_or_files(self, mfile_or_dir):
        a, r, a_paths, r_paths, itemargs = self.gen_files_or_dirs(mfile_or_dir)
        tdir = "movehere"
        a_paths_moved = [os.path.join(tdir, _) for _ in a_paths]
        r_paths_moved = [os.path.join(tdir, _) for _ in r_paths]

        os.mkdir(os.path.join(self.rundir, tdir))
        t = self.run("--move %s days10,weeks2 %s" % (tdir, itemargs))
        t.assert_in_stdout(r)
        t.assert_not_in_stdout(a)
        t.assert_no_stderr()
        t.assert_paths_exist(list(chain(a_paths, r_paths_moved)))

    def test_10_days_2_weeks_delete_files(self):
        self._10_days_2_weeks_delete_dirs_or_files(self.mfile)

    def test_10_days_2_weeks_delete_dirs(self):
        self._10_days_2_weeks_delete_dirs_or_files(self.mdir)

    def _10_days_2_weeks_delete_dirs_or_files(self, mfile_or_dir):
        a, r, a_paths, r_paths, itemargs = self.gen_files_or_dirs(mfile_or_dir)
        t = self.run("--delete days10,weeks2 %s" % itemargs)
        t.assert_in_stdout(r)
        t.assert_not_in_stdout(a)
        t.assert_no_stderr()
        t.assert_paths_not_exist(r_paths)
        t.assert_paths_exist(a_paths)

    def test_delete_notempty(self):
        d = "testdir"
        f = "testfile"
        now = time.time()
        self.mdir(d, now)
        self.mfile(os.path.join(d, f), now)
        t = self.run("--delete days1 %s" % d)
        t.assert_in_stdout(d)
        t.assert_in_stderr(["ERROR", "Cannot rmdir", "not", "empty"])
        # TODO: think about specification. Should this be a positive error
        # code, even in non-strict mode?

    def test_delete_recursive(self):
        d = "notempty"
        f = "testfile"
        now = time.time()
        self.mdir(d, now)
        self.mfile(os.path.join(d, f), now)
        t = self.run("--delete --recursive-delete days1 %s" % d)
        t.assert_in_stdout(d)
        t.assert_no_stderr()
        t.assert_paths_not_exist(d)


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

    def test_delete_file(self):
        self.mfile("☺")
        t = self.run("--delete days1 ☺")
        t.assert_in_stdout("☺")
        t.assert_no_stderr()
        t.assert_paths_not_exist("☺")

    def test_move_file(self):
        self.mfile("☺")
        self.mdir("rejected")
        t = self.run("--move rejected days1 ☺")
        t.assert_in_stdout("☺")
        t.assert_no_stderr()
        t.assert_paths_exist("rejected/☺")

    def test_stdin_one_recent(self):
        self.mfile("☺")
        s = "☺".encode(STDINENC)
        t = self.run("-a -0 -s recent1", sin=s)
        t.assert_is_stdout("☺\0")
        t = self.run("-a -s recent1", sin=s)
        t.assert_is_stdout("☺\n")

    def test_stdin_two_recent(self):
        self.mfile("☺")
        s = "☺\n☺".encode(STDINENC)
        t = self.run("-a -s recent2", sin=s)
        t.assert_is_stdout("☺\n☺\n")
