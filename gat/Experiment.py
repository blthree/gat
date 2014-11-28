##########################################################################
#
#   MRC FGU Computational Genomics Group
#
#   $Id$
#
#   Copyright (C) 2009 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
##########################################################################
'''
Experiment.py - record keeping of experiments
=============================================

Module for record keeping of experiments. This module
is imported by most CGAT scripts. It provides convenience
methods for

   * argument parsing
   * record keeping (logging)
   * benchmarking

See :doc:`../scripts/script_template` on how to use this module.

API
---
'''

import string
import re
import sys
import time
import inspect
import os
import optparse
import logging
import random
import collections
import types
import subprocess
import gzip


class DefaultOptions:
    stdlog = sys.stdout
    stdout = sys.stdout
    stderr = sys.stderr

global_starting_time = time.time()
global_options = DefaultOptions()
global_args = None
# import hashlib
# global_id = hashlib.md5(time.asctime(time.localtime(time.time()))).hexdigest()
import uuid
global_id = uuid.uuid4()
global_benchmark = collections.defaultdict(int)


def GetHeader():
    """return a header string with command line options and
    timestamp"""
    system, host, release, version, machine = os.uname()
    return "# output generated by %s\n# job started at %s on %s -- %s\n# pid: %i, system: %s %s %s %s" %\
           (" ".join(sys.argv),
            time.asctime(time.localtime(time.time())),
            host,
            global_id,
            os.getpid(),
            system, release, version, machine)


def GetParams(options=None):
    """return a string containing script parameters.
    Parameters are all variables that start with "param_".
    """
    result = []
    if options:
        members = options.__dict__
        for k, v in sorted(members.items()):
            result.append("# %-40s: %s" % (k, str(v).encode("string_escape")))
    else:
        vars = inspect.currentframe().f_back.f_locals
        for var in filter(lambda x: re.match("param_", x), vars.keys()):
            result.append("# %-40s: %s" %
                          (var, str(vars[var]).encode("string_escape")))

    if result:
        return "\n".join(result)
    else:
        return "# no parameters."


def GetFooter():
    """return a header string with command line options and
    timestamp."""
    return "# job finished in %i seconds at %s -- %s -- %s" %\
           (time.time() - global_starting_time,
            time.asctime(time.localtime(time.time())),
            " ".join(map(lambda x: "%5.2f" % x, os.times()[:4])),
            global_id)


def Start(parser=None,
          argv=sys.argv,
          quiet=False,
          add_csv_options=False,
          add_mysql_options=False,
          add_psql_options=False,
          add_pipe_options=True,
          add_cluster_options=False,
          add_output_options=False):
    """set up an experiment.

    returns a tuple containing (options, args).

    The options class is extended with a logger module.
    """

    if not parser:
        parser = optparse.OptionParser(
            version="%prog version: $Id: Experiment.py 2803 2009-10-22 13:41:24Z andreas $")

    global global_options, global_args, global_starting_time

    global_starting_time = time.time()

    parser.add_option("-v", "--verbose", dest="loglevel", type="int",
                      help="loglevel [%default]. The higher, the more output.")

    parser.add_option("--timeit", dest='timeit_file', type="string",
                      help="store timeing information in file [%default].")
    parser.add_option("--timeit-name", dest='timeit_name', type="string",
                      help="name in timing file for this class of jobs [%default].")
    parser.add_option("--timeit-header", dest='timeit_header', action="store_true",
                      help="add header for timing information [%default].")

    if quiet:
        parser.set_defaults(loglevel=0)
    else:
        parser.set_defaults(loglevel=1)

    parser.set_defaults(
        timeit_file=None,
        timeit_name='all',
        timeit_header=None,
    )

    if add_csv_options:
        parser.add_option("--dialect", dest="csv_dialect", type="string",
                          help="csv dialect to use [%default].")

        parser.set_defaults(
            csv_dialect="excel-tab",
            csv_lineterminator="\n",
        )

    if add_psql_options:
        parser.add_option("-C", "--connection", dest="psql_connection", type="string",
                          help="psql connection string [%default].")
        parser.add_option("-U", "--user", dest="user", type="string",
                          help="database user name [%default].")

        parser.set_defaults(psql_connection="db:andreas")
        parser.set_defaults(user="")

    if add_cluster_options:
        parser.add_option("--use-cluster", dest="use_cluster", action="store_true",
                          help="use cluster [%default].")
        parser.add_option("--cluster-priority", dest="cluster_priority", type="int",
                          help="set job priority on cluster [%default].")
        parser.add_option("--cluster-queue", dest="cluster_queue", type="string",
                          help="set cluster queue [%default].")
        parser.add_option("--cluster-num-jobs", dest="cluster_num_jobs", type="int",
                          help="number of jobs to submit to the queue execute in parallel [%default].")
        parser.add_option("--cluster-options", dest="cluster_options", type="string",
                          help="additional options for cluster jobs, passed on to qrsh [%default].")

        parser.set_defaults(use_cluster=False,
                            cluster_queue="medium_jobs.q",
                            cluster_priority=-10,
                            cluster_num_jobs=100,
                            cluster_options="")

    if add_output_options:
        parser.add_option("-P", "--output-filename-pattern", dest="output_filename_pattern", type="string",
                          help="OUTPUT filename pattern for various methods [%default].")

        parser.add_option("-F",
                          "--force-output",
                          "--force", dest="output_force", action="store_true",
                          help="force over-writing of existing files.")

        parser.set_defaults(output_filename_pattern="%s",
                            output_force=False)

    if add_pipe_options:
        parser.add_option("-I", "--stdin", dest="stdin", type="string",
                          help="file to read stdin from [default = stdin].",
                          metavar="FILE")
        parser.add_option("-L", "--log", dest="stdlog", type="string",
                          help="file with logging information [default = stdout].",
                          metavar="FILE")
        parser.add_option("-E", "--error", dest="stderr", type="string",
                          help="file with error information [default = stderr].",
                          metavar="FILE")
        parser.add_option("-S", "--stdout", dest="stdout", type="string",
                          help="file where output is to go [default = stdout].",
                          metavar="FILE")

        parser.set_defaults(stderr=sys.stderr)
        parser.set_defaults(stdout=sys.stdout)
        parser.set_defaults(stdlog=sys.stdout)
        parser.set_defaults(stdin=sys.stdin)

    if add_mysql_options:
        parser.add_option("-H", "--host", dest="host", type="string",
                          help="mysql host [%default].")
        parser.add_option("-D", "--database", dest="database", type="string",
                          help="mysql database [%default].")
        parser.add_option("-U", "--user", dest="user", type="string",
                          help="mysql username [%default].")
        parser.add_option("-P", "--password", dest="password", type="string",
                          help="mysql password [%default].")
        parser.add_option("-O", "--port", dest="port", type="int",
                          help="mysql port [%default].")

        parser.set_defaults(host="db",
                            port=3306,
                            user="",
                            password="",
                            database="")

    (global_options, global_args) = parser.parse_args(argv[1:])

    if add_pipe_options:
        if global_options.stdout != sys.stdout:
            global_options.stdout = open(global_options.stdout, "w")
        if global_options.stderr != sys.stderr:
            if global_options.stderr == "stderr":
                global_options.stderr = global_options.stderr
            else:
                global_options.stderr = open(global_options.stderr, "w")
        if global_options.stdlog != sys.stdout:
            global_options.stdlog = open(global_options.stdlog, "a")
        if global_options.stdin != sys.stdin:
            global_options.stdin = open(global_options.stdin, "r")
    else:
        global_options.stderr = sys.stderr
        global_options.stdout = sys.stdout
        global_options.stdlog = sys.stdout
        global_options.stdin = sys.stdin

    if global_options.loglevel >= 1:
        global_options.stdlog.write(GetHeader() + "\n")
        global_options.stdlog.write(GetParams(global_options) + "\n")
        global_options.stdlog.flush()

    # configure logging
    # map from 0-10 to logging scale
    # 0: quiet
    # 1: little verbositiy
    # >1: increased verbosity
    if global_options.loglevel == 0:
        lvl = logging.ERROR
    elif global_options.loglevel == 1:
        lvl = logging.INFO
    else:
        lvl = logging.DEBUG

    if global_options.stdout == global_options.stdlog:
        logging.basicConfig(
            level=lvl,
            format='# %(asctime)s %(levelname)s %(message)s',
            stream=global_options.stdlog)
    else:
        logging.basicConfig(
            level=lvl,
            format='%(asctime)s %(levelname)s %(message)s',
            stream=global_options.stdlog)

    return global_options, global_args


def Stop():
    """stop the experiment."""

    if global_options.loglevel >= 1 and global_benchmark:
        t = time.time() - global_starting_time
        global_options.stdlog.write(
            "######### Time spent in benchmarked functions ###################\n")
        global_options.stdlog.write("# function\tseconds\tpercent\n")
        for key, value in global_benchmark.items():
            global_options.stdlog.write(
                "# %s\t%6i\t%5.2f%%\n" % (key, value, (100.0 * float(value) / t)))
        global_options.stdlog.write(
            "#################################################################\n")

    if global_options.loglevel >= 1:
        global_options.stdlog.write(GetFooter() + "\n")

    # close files
    if global_options.stdout != sys.stdout:
        global_options.stdout.close()
    # do not close log, otherwise the following error occurs:
    # Error in sys.exitfunc:
    # Traceback (most recent call last):
    #   File "/net/cpp-group/server/lib/python2.6/atexit.py", line 24, in _run_exitfuncs
    #     func(*targs, **kargs)
    #   File "/net/cpp-group/server/lib/python2.6/logging/__init__.py", line 1472, in shutdown
    #     h.flush()
    #   File "/net/cpp-group/server/lib/python2.6/logging/__init__.py", line 740, in flush
    #     self.stream.flush()
    # ValueError: I/O operation on closed file
    # if global_options.stdlog != sys.stdout: global_options.stdlog.close()
    if global_options.stderr != sys.stderr:
        global_options.stderr.close()

    if global_options.timeit_file:

        outfile = open(global_options.timeit_file, "a")

        if global_options.timeit_header:
            outfile.write("\t".join(("name", "wall", "user", "sys", "cuser", "csys",
                                     "host", "system", "release", "machine",
                                     "start", "end", "path", "cmd")) + "\n")

        csystem, host, release, version, machine = map(str, os.uname())
        uusr, usys, c_usr, c_sys = map(lambda x: "%5.2f" % x, os.times()[:4])
        t_end = time.time()
        c_wall = "%5.2f" % (t_end - global_starting_time)

        if sys.argv[0] == "run.py":
            cmd = global_args[0]
            if len(global_args) > 1:
                cmd += " '" + "' '".join(global_args[1:]) + "'"
        else:
            cmd = sys.argv[0]

        result = "\t".join((global_options.timeit_name,
                            c_wall, uusr, usys, c_usr, c_sys,
                            host, csystem, release, machine,
                            time.asctime(time.localtime(global_starting_time)),
                            time.asctime(time.localtime(t_end)),
                            os.path.abspath(os.getcwd()),
                            cmd)) + "\n"

        outfile.write(result)
        outfile.close()


def benchmark(func):
    """decorator collecting wall clock time spent in decorated method."""

    def wrapper(*arg):
        t1 = time.time()
        res = func(*arg)
        t2 = time.time()
        key = "%s:%i" % (func.func_name, func.func_code.co_firstlineno)
        global_benchmark[key] += t2 - t1
        global_options.stdlog.write(
            '## benchmark: %s completed in %6.4f s\n' % (key, (t2 - t1)))
        global_options.stdlog.flush()
        return res
    return wrapper

# there are differences whether you cache a function or
# an objects method


def cachedmethod(function):
    '''decorator for caching a method.'''
    return Memoize(function)


class Memoize(object):

    def __init__(self, fn):
        self.cache = {}
        self.fn = fn

    def __get__(self, instance, cls=None):
        self.instance = instance
        return self

    def __call__(self, *args):
        if args in self.cache:
            return self.cache[args]
        else:
            object = self.cache[args] = self.fn(self.instance, *args)
            return object


def log(loglevel, message):
    """log message at loglevel."""
    logging.log(loglevel, message)


def info(message):
    '''log information message, see the :mod:`logging` module'''
    logging.info(message)


def warning(message):
    '''log warning message, see the :mod:`logging` module'''
    logging.warning(message)


def warn(message):
    '''log warning message, see the :mod:`logging` module'''
    logging.warning(message)


def debug(message):
    '''log debugging message, see the :mod:`logging` module'''
    logging.debug(message)


def error(message):
    '''log error message, see the :mod:`logging` module'''
    logging.error(message)


def critical(message):
    '''log critical message, see the :mod:`logging` module'''
    logging.critical(message)


def getOutputFile(section):
    '''return filename to write to.'''
    return re.sub("%s", section, global_options.output_filename_pattern)


def openOutputFile(section, mode="w"):
    """open file for writing substituting section in the
    output_pattern (if defined).

    If the filename ends with ".gz", the output is opened
    as a gzip'ed file.
    """

    fn = getOutputFile(section)
    try:
        if fn == "-":
            return global_options.stdout
        else:
            if not global_options.output_force and os.path.exists(fn):
                raise OSError(
                    "file %s already exists, use --force to overwrite existing files." % fn)
            if fn.endswith(".gz"):
                return gzip.open(fn, mode)
            else:
                return open(fn, mode)
    except AttributeError:
        return global_options.stdout


class Counter(object):

    '''a counter class.

    The counter acts both as a dictionary and
    a object permitting attribute access.

    Counts are automatically initialized to 0.

    Instantiate and use like this::

       c = Counter()
       c.input += 1
       c.output += 2
       c["skipped"] += 1

       print str(c)
    '''

    __slots__ = ["_counts"]

    def __init__(self):
        """Store data returned by function."""
        object.__setattr__(self, "_counts", collections.defaultdict(int))

    def __setitem__(self, key, value):
        self._counts[key] = value

    def __getitem__(self, key):
        return self._counts[key]

    def __getattr__(self, name):
        return self._counts[name]

    def __setattr__(self, name, value):
        self._counts[name] = value

    def __str__(self):
        return ", ".join("%s=%i" % x for x in self._counts.iteritems())

    def __iadd__(self, other):
        try:
            for key, val in other.iteritems():
                self._counts[key] += val
        except:
            raise TypeError("unknown type")
        return self

    def iteritems(self):
        return self._counts.iteritems()


def run(cmd):
    '''executed a command line cmd.

    raises OSError if process failed or was terminated.
    '''

    retcode = subprocess.call(cmd, shell=True)
    if retcode < 0:
        raise OSError("process was terminated by signal %i" % -retcode)
    return retcode
