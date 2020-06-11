#!/usr/bin/env python3.7

from __future__ import print_function

import difflib
import hashlib
import os
import shutil
import subprocess
import sys
from io import StringIO
from optparse import OptionParser

import appdirs

worktrees_to_look_at = "master", "develop", "factory"

cache_dir = appdirs.user_cache_dir("Nuitka-Speedcenter", None)
git_dir = os.path.join(cache_dir, "git")
clone_dir = os.path.join(git_dir, "Nuitka.git")


def executeCommand(command):
    print("Execute: ", command)

    assert 0 == os.system(command)


def getNuitkaWorktreeDir(worktree):
    return os.path.join(git_dir, worktree)


def makedirs(path, mode=0o755):
    if not os.path.isdir(path):
        os.makedirs(path, mode)


def updateNuitkaSoftware():
    if not os.path.exists(clone_dir):
        makedirs(git_dir)
        executeCommand(
            "cd '%s'; git clone --bare --mirror http://github.com/Nuitka/Nuitka.git"
            % git_dir
        )
    else:
        executeCommand("cd '%s'; git fetch -p" % clone_dir)

    for worktree in worktrees_to_look_at:
        worktree_dir = getNuitkaWorktreeDir(worktree)

        if not os.path.exists(worktree_dir):
            executeCommand(
                "cd '%s'; git worktree add '%s' '%s'"
                % (clone_dir, worktree_dir, worktree)
            )
        else:
            executeCommand("cd '%s'; git reset --hard '%s'" % (worktree_dir, worktree))


def generateConstructGraph(
    name,
    python_version,
    cpython_value,
    nuitka_master_value,
    nuitka_develop_value,
    nuitka_factory_value,
):

    graph_title = "Construct %s" % name

    graph_values = [
        cpython_value,
        nuitka_master_value,
        nuitka_develop_value,
        nuitka_factory_value,
    ]

    graph_xlabels = [
        "CPython %s" % python_version,
        "Nuitka (master)",
        "Nuitka (develop)",
        "Nuitka (factory)",
    ]

    # Also return the rest for pygal plug-in:
    return """
.. chart:: Bar
    :title: '%(graph_title)s'
    :x_labels: %(graph_xlabels)s

    'Ticks', %(graph_values)s
    """ % {
        "graph_title": graph_title,
        "graph_xlabels": repr(graph_xlabels),
        "graph_values": repr(graph_values),
    }


def getHomeDir():
    return os.path.normpath(os.path.dirname(__file__))


def getDataDir():
    data_dir = os.path.join(cache_dir, "performance-data")

    makedirs(data_dir)

    return data_dir


def fetchDocs():
    makedirs("doc/images")

    # TODO: We only use one of those really here, and it could become a
    # reference to nuitka.net
    for filename in (
        "doc/images/Nuitka-Logo-Horizontal.png",
        "doc/images/Nuitka-Logo-Vertical.png",
        "doc/images/Nuitka-Logo-Symbol.png",
    ):
        command = (
            "curl -s http://nuitka.net/gitweb/?p=Nuitka.git;a=blob_plain;f=%s;hb=refs/heads/factory"
            % filename
        )
        output = subprocess.check_output(command.split())

        with open(filename, "wb") as out_file:
            out_file.write(output)


def getSourcesDir():
    sources_dir = os.path.join(getDataDir(), "construct-sources")

    makedirs(sources_dir)

    return sources_dir


def getPythonVersions():
    data_dir = getDataDir()

    python_versions = []

    for python_version in sorted(os.listdir(data_dir)):
        if python_version == "construct-sources":
            continue

        python_versions.append(python_version)

    return python_versions


def readDataFile(filename):
    values = {}

    if os.path.exists(filename):
        try:
            exec(open(filename, "r").read(), values)
        except ValueError:
            return None

        del values["__builtins__"]
        return values
    else:
        return None


def updateConstructGraphs():
    home_dir = getHomeDir()
    data_dir = getDataDir()

    graphs = {}
    graph_data = {}

    python_versions = getPythonVersions()

    construct_names = set()

    for python_version in python_versions:
        print("Python version:", python_version)

        master_data_dir = os.path.join(data_dir, python_version, "master")

        develop_data_dir = os.path.join(data_dir, python_version, "develop")

        factory_data_dir = os.path.join(data_dir, python_version, "factory")

        cpython_data_dir = os.path.join(data_dir, python_version, "cpython")

        for entry in sorted(os.listdir(master_data_dir)):
            if not entry.endswith(".data"):
                continue

            construct_name = entry.split(".")[0]
            construct_names.add(construct_name)

            cpython_values = readDataFile(os.path.join(cpython_data_dir, entry))

            factory_values = readDataFile(os.path.join(factory_data_dir, entry))

            develop_values = readDataFile(os.path.join(develop_data_dir, entry))

            master_values = readDataFile(os.path.join(master_data_dir, entry))

            graph_data[python_version, construct_name] = dict(
                cpython=cpython_values["CPYTHON_CONSTRUCT"],
                master=master_values["NUITKA_CONSTRUCT"],
                develop=develop_values["NUITKA_CONSTRUCT"],
                factory=factory_values["NUITKA_CONSTRUCT"],
            )

            graphs[python_version, construct_name] = generateConstructGraph(
                name=construct_name,
                python_version=python_version,
                cpython_value=cpython_values["CPYTHON_CONSTRUCT"],
                nuitka_master_value=master_values["NUITKA_CONSTRUCT"],
                nuitka_develop_value=develop_values["NUITKA_CONSTRUCT"],
                nuitka_factory_value=factory_values["NUITKA_CONSTRUCT"],
            )

    for construct_name in sorted(construct_names):
        construct_rst = os.path.join(
            home_dir, "constructs", "construct-%s.rst" % construct_name
        )

        makedirs(os.path.dirname(construct_rst))

        tags = []

        def makeTag(tag):
            return python_version.replace(".", "") + "_" + tag

        emit = lambda tag: tags.append(makeTag(tag))

        def isLessTicksThan(value1, value2):
            if abs(value1 - value2) / float(value1) < 0.001:
                return False

            if abs(value1 - value2) < 1000:
                return False

            return value1 < value2

        assert isLessTicksThan(102528524, 77178450) is False
        assert isLessTicksThan(77178450, 102528524) is True
        assert isLessTicksThan(99858, 99542) is False
        assert isLessTicksThan(99542, 99858) is False

        for python_version in python_versions:
            key = python_version, construct_name

            if key not in graph_data:
                continue

            case_data = graph_data[key]

            if isLessTicksThan(case_data["master"], case_data["develop"]):
                emit("develop_down")
            elif isLessTicksThan(case_data["develop"], case_data["master"]):
                emit("develop_up")
            else:
                emit("develop_steady")

            if isLessTicksThan(case_data["develop"], case_data["factory"]):
                emit("factory_down")
            elif isLessTicksThan(case_data["factory"], case_data["develop"]):
                emit("factory_up")
            else:
                emit("factory_steady")

        with open(construct_rst, "w") as construct_file:
            construct_file.write(
                """\
.. title: Construct %s
.. tags: %s
.. date: 2013/08/15 08:15:17

.. contents::
"""
                % (construct_name, ",".join(tags or ["untagged"]))
            )

            construct_file.write(
                """
Performance Diagrams
====================

"""
            )
            for python_version in python_versions:
                key = python_version, construct_name

                if key in graphs:
                    construct_file.write(graphs[key])

            construct_filename = os.path.join(getSourcesDir(), construct_name + ".py")

            case_1_file = StringIO()
            case_2_file = StringIO()

            inside = False
            case = 0

            for line in open(construct_filename):
                if not inside or case == 1:
                    case_1_file.write(line)
                else:
                    case_1_file.write("\n")

                if "# construct_alternative" in line:
                    case = 2

                if not inside or case == 2:
                    case_2_file.write(line)
                else:
                    case_2_file.write("\n")

                if "# construct_begin" in line:
                    inside = True
                    case = 1
                elif "# construct_end" in line:
                    inside = False
                    case = 1

            case_1 = case_1_file.getvalue()
            case_1_file.close()

            case_2 = case_2_file.getvalue()
            case_2_file.close()

            construct_file.write(
                """
Source Code with Construct
==========================

.. code-block:: python

%s
"""
                % (
                    "\n".join(
                        ("    " + line) if line else ""
                        for line in case_1.split("\n")[19:]
                    )
                )
            )
            construct_file.write(
                """
Source Code without Construct
=============================

.. code-block:: python

%s
"""
                % (
                    "\n".join(
                        ("    " + line) if line else ""
                        for line in case_2.split("\n")[19:]
                    )
                )
            )

            code_diff = difflib.HtmlDiff().make_table(
                case_1.split("\n"), case_2.split("\n"), "Construct", "Baseline", True
            )

            construct_file.write(
                """
Context Diff of Source Code
===========================

.. raw:: html

    <style type="text/css">
        table.diff {font-family:Courier; border:medium;}
        .diff_header {background-color:#e0e0e0}
        td.diff_header {text-align:right}
        .diff_next {background-color:#c0c0c0}
        .diff_chg {background-color:#ffff77}
        .diff_sub {background-color:#ffaaaa}
        .diff_add {background-color:#aaffaa}
    </style>

%s
"""
                % (
                    "\n".join(
                        ("    " + line) if line else ""
                        for line in code_diff.split("\n")
                    )
                )
            )
            diff_filename = os.path.join(
                data_dir, python_version, "factory", construct_name + ".html"
            )

            if os.path.exists(diff_filename):

                generated_diff = open(diff_filename).read()

                construct_file.write(
                    """
Context Diff of Generated Code
==============================

.. raw:: html

    <style type="text/css">
        table.diff {font-family:Courier; border:medium;}
        .diff_header {background-color:#e0e0e0}
        td.diff_header {text-align:right}
        .diff_next {background-color:#c0c0c0}
        .diff_add {background-color:#aaffaa}
        .diff_chg {background-color:#ffff77}
        .diff_sub {background-color:#ffaaaa}
    </style>

%s
"""
                    % (
                        "\n".join(
                            ("    " + line) if line else ""
                            for line in generated_diff.split("\n")
                        )
                    )
                )

    index_dir = os.path.join(home_dir, "index")
    makedirs(index_dir)

    with open(os.path.join(index_dir, "index.rst"), "w") as index_file:
        index_file.write(
            """\
.. title: Welcome to Nuitka Speedcenter
.. slug: index

This is a list of basic constructs and performance comparisons of Nuitka with
CPython for each. Bear in mind, that for some operations large gains are
feasible by being avoided, but that this about costs for them in case they
cannot.

All of these tests aim to avoid SSA and whole level program optimization.

The following Python construct test cases exist so far:

"""
        )
        for construct_name in sorted(construct_names):
            index_file.write(
                """\
* `%s </constructs/construct-%s.html>`_
"""
                % (construct_name, construct_name.lower())
            )

        index_file.write(
            """
Also coming are optimization tests, demonstrating the removal or simplication
of executed code."""
        )


def getPythonVersion(python):
    version_output = subprocess.check_output(
        (
            python,
            "-c",
            """\
import sys, os;\
print(".".join(str(s) for s in list(sys.version_info)[:3]));\
print(("x86_64" if "AMD64" in sys.version else "x86") if os.name=="nt" else os.uname()[4]);\
""",
        ),
        stderr=subprocess.STDOUT,
    )

    python_version = version_output.split(b"\n")[0].strip()
    python_arch = version_output.split(b"\n")[1].strip()

    if sys.version.startswith("3"):
        python_arch = python_arch.decode()
        python_version = python_version.decode()

    return python_version


def getCommitIdFromName(name):
    from git import Repo

    repo = Repo(os.path.join(git_dir, "Nuitka.git"))

    return getattr(repo.heads, name).commit


def _takeNumbers(name, python, major, filename):
    case_dir = os.path.join(getDataDir(), major, name)
    makedirs(case_dir)
    data_filename = os.path.join(case_dir, filename.replace(".py", ".data"))

    command = [
        python,
        os.path.join(
            getNuitkaWorktreeDir("factory"), "bin/measure-construct-performance"
        ),
        "--nuitka",
        os.path.join(getNuitkaWorktreeDir(name), "bin/nuitka"),
        "--cpython",
        "no",
        "--code-diff",
        os.path.abspath(data_filename.replace(".data", ".html")),
        os.path.join(getTestCasesDir(), filename),
    ]

    process = subprocess.Popen(
        args=command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout_runner, stderr_runner = process.communicate()
    exit_runner = process.returncode

    assert exit_runner == 0, stderr_runner
    open(data_filename, "wb").write(stdout_runner)


def _readNumbers(name, major, filename):
    data_filename = os.path.join(
        getDataDir(), major, name, filename.replace(".py", ".data")
    )

    readDataFile(data_filename)


def _validate(values, test_case_hash, commit):
    if values is None:
        return None
    if values["TEST_CASE_HASH"] != test_case_hash or values["NUITKA_COMMIT"] != commit:
        return None

    return values


def getTestCasesDir():
    return os.path.join(getNuitkaWorktreeDir("factory"), "tests/benchmarks/constructs")


def _updateNumbers(python):
    python_version = getPythonVersion(python)
    major = ".".join(python_version.split(".")[:2])

    print("Working with", major)

    nuitka_factory_commit = getCommitIdFromName("factory")
    nuitka_develop_commit = getCommitIdFromName("develop")
    nuitka_master_commit = getCommitIdFromName("master")

    cases_dir = getTestCasesDir()

    for filename in sorted(os.listdir(cases_dir)):
        if filename == "InplaceOperationInstanceStringAdd.py":
            continue

        fullpath = os.path.join(cases_dir, filename)

        if not filename.endswith(".py"):
            continue
        if filename.startswith("run_"):
            continue
        if not os.path.isfile(fullpath):
            continue

        if python_version.startswith("3") and filename.endswith("_27.py"):
            continue

        print("Consider:", filename)
        sys.stdout.flush()

        needs_cpython = False

        test_case_hash = hashlib.md5(open(fullpath, "rb").read()).hexdigest()

        cpython_filename = os.path.join(
            getDataDir(), major, "cpython", filename.replace(".py", ".data")
        )

        if os.path.exists(cpython_filename):
            old_values = readDataFile(cpython_filename)

            if (
                old_values["TEST_CASE_HASH"] != test_case_hash
                or old_values["PYTHON"] != python_version
            ):
                needs_cpython = True
        else:
            needs_cpython = True

        factory_values = _readNumbers("factory", major, filename)
        factory_values = _validate(
            factory_values, test_case_hash, nuitka_factory_commit
        )

        develop_values = _readNumbers("develop", major, filename)
        develop_values = _validate(
            develop_values, test_case_hash, nuitka_develop_commit
        )

        master_values = _readNumbers("master", major, filename)
        master_values = _validate(master_values, test_case_hash, nuitka_master_commit)

        if needs_cpython:
            print("CPython ... ")
            makedirs(os.path.dirname(cpython_filename))

            command = [
                python,
                os.path.join(
                    getNuitkaWorktreeDir("factory"), "bin/measure-construct-performance"
                ),
                fullpath,
                "--copy-source-to",
                getSourcesDir(),
            ]

            process = subprocess.Popen(
                args=command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout_runner, stderr_runner = process.communicate()
            exit_runner = process.returncode

            assert exit_runner == 0, stderr_runner

            open(cpython_filename, "wb").write(stdout_runner)

        if factory_values is None:
            print("Nuitka factory ... ")
            _takeNumbers("factory", python, major, filename)

        if develop_values is None:
            print("Nuitka develop ... ")
            _takeNumbers("develop", python, major, filename)

        if master_values is None:
            print("Nuitka master ... ")
            _takeNumbers("master", python, major, filename)

    version_data_dir = os.path.join(getDataDir(), major)

    for branch_name in sorted(os.listdir(version_data_dir)):
        branch_path = os.path.join(version_data_dir, branch_name)

        if not os.path.isdir(branch_path):
            continue

        for filename in sorted(os.listdir(branch_path)):

            fullpath = os.path.join(branch_path, filename)

            if filename.endswith((".data", ".html")):
                case_name = filename[:-5] + ".py"

                case_filename = os.path.join(cases_dir, case_name)
                if not os.path.exists(case_filename):
                    print("Removing obsolete:", fullpath)
                    os.unlink(fullpath)

            else:
                assert False


def updateNumbers():
    print("Updating numbers:")
    _updateNumbers("python2.7")
    _updateNumbers("python3.5")


parser = OptionParser()

parser.add_option(
    "--update-nuitka",
    action="store_true",
    dest="nuitka",
    default=False,
    help="""\
When given, the download page is updated. Default %default.""",
)

parser.add_option(
    "--update-numbers",
    action="store_true",
    dest="numbers",
    default=False,
    help="""\
When given, the numbers are updated. Default %default.""",
)

parser.add_option(
    "--update-graphs",
    action="store_true",
    dest="graph",
    default=False,
    help="""\
When given, the site is built. Default %default.""",
)

parser.add_option(
    "--build-site",
    action="store_true",
    dest="build",
    default=False,
    help="""\
When given, the site is built. Default %default.""",
)

parser.add_option(
    "--deploy-site",
    action="store_true",
    dest="deploy",
    default=False,
    help="""\
When given, the site is deployed. Default %default.""",
)

parser.add_option(
    "--no-push",
    action="store_true",
    dest="no_push",
    default=False,
    help="""\
When given, push changes to repo. Default %default.""",
)

parser.add_option(
    "--update-all",
    action="store_true",
    dest="all",
    default=False,
    help="""\
When given, all is updated. Default %default.""",
)

options, positional_args = parser.parse_args()

assert not positional_args, positional_args

if options.all:
    options.nuitka = True
    options.numbers = True
    options.graph = True
    options.build = True

    if not options.no_push:
        options.deploy = True

# TODO: Make this an option too.
if not os.path.isdir("doc/images"):
    fetchDocs()

if options.nuitka:
    updateNuitkaSoftware()

if options.numbers:
    updateNumbers()

if options.graph:
    updateConstructGraphs()

if options.build or options.deploy:
    if os.path.isdir("cache"):
        shutil.rmtree("cache")


def runNikolaCommand(command):
    print("Starting nikola command:", command)
    assert 0 == os.system("nikola " + command)
    print("Succeeded nikola command:", command)


if options.build:
    runNikolaCommand("build")

    os.unlink("output/rss.xml")

if options.deploy:
    runNikolaCommand("deploy")
