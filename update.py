#!/usr/bin/env python3.9

from __future__ import print_function

import datetime
import hashlib
import os
import shutil
import subprocess
import sys
from io import StringIO
from optparse import OptionParser

import appdirs
from collections import defaultdict

from orderedsets import OrderedSet

work_trees_to_look_at = "main", "develop", "factory"

cache_dir = appdirs.user_cache_dir("Nuitka-Speedcenter", None)
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
git_dir = os.path.join(cache_dir, "git")
if not os.path.exists(git_dir):
    os.makedirs(git_dir)
clone_dir = os.path.join(git_dir, "Nuitka.git")


def executeCommand(command):
    print("Execute: ", command)

    assert 0 == os.system(command)


def getNuitkaWorkTreeDir(work_tree):
    return os.path.join(git_dir, work_tree)


def makedirs(path, mode=0o755):
    if not os.path.isdir(path):
        os.makedirs(path, mode)


def updateNuitkaSoftware():
    if not os.path.exists(clone_dir):
        makedirs(git_dir)

        executeCommand(
            "cd '%s'; git clone --bare --mirror https://github.com/Nuitka/Nuitka.git"
            % git_dir
        )
    else:
        executeCommand("cd '%s'; git fetch -p -u" % clone_dir)

    for work_tree in work_trees_to_look_at:
        work_tree_dir = getNuitkaWorkTreeDir(work_tree)

        if not os.path.exists(work_tree_dir):
            executeCommand(
                "cd '%s'; git worktree add '%s' '%s'"
                % (clone_dir, work_tree_dir, work_tree)
            )
        else:
            executeCommand(
                "cd '%s'; git reset --hard '%s'" % (work_tree_dir, work_tree)
            )


def generateConstructGraph(
    name,
    python_version,
    graph_data,
):
    cpython_value = graph_data["cpython"]
    nuitka_main_value = graph_data["main"]
    nuitka_develop_value = graph_data["develop"]
    nuitka_factory_value = graph_data["factory"]

    graph_title = "Construct %s" % name

    graph_values = [
        cpython_value,
        nuitka_main_value,
        nuitka_develop_value,
        nuitka_factory_value,
    ]

    graph_x_labels = [
        "CPython %s" % python_version,
        "Nuitka (main)",
        "Nuitka (develop)",
        "Nuitka (factory)",
    ]

    # Also return the rest for pygal plug-in:
    return """
.. chart:: Bar
    :title: '%(graph_title)s'
    :x_labels: %(graph_x_labels)s

    'Ticks', %(graph_values)s
    """ % {
        "graph_title": graph_title,
        "graph_x_labels": repr(graph_x_labels),
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
            "curl -s https://nuitka.net/gitweb/?p=Nuitka.git;a=blob_plain;f=%s;hb=refs/heads/factory"
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

    return sorted(
        [
            python_version
            for python_version in sorted(os.listdir(data_dir))
            if python_version != "construct-sources"
        ],
        key=lambda python_version: tuple(int(x) for x in python_version.split(".")),
        reverse=True,
    )


def readDataFile(filename):
    values = {}

    if os.path.exists(filename):
        # There was a bug, where Scons output was done even if used --quiet.
        code = "".join(
            line for line in open(filename, "r") if "Nuitka-Scons:" not in line
        )

        try:
            exec(code, values)
        except ValueError:
            return None

        del values["__builtins__"]
        return values
    else:
        return None


def makeTag(python_version, case_data, version1, version2):
    python_version_prefix = python_version.replace(".", "")
    key = (python_version_prefix, version2, version1)

    assert version1 in case_data, (version1, case_data)
    assert version2 in case_data, (version2, case_data)
    if isLessTicksThan(case_data[version2], case_data[version1]):
        return "%s_%s_down_vs_%s" % key
    elif isLessTicksThan(case_data[version1], case_data[version2]):
        return "%s_%s_up_vs_%s" % key
    else:
        return "%s_%s_steady_vs_%s" % key


def getConstructGraphData():
    data_dir = getDataDir()

    graph_data = {}

    python_versions = getPythonVersions()

    construct_names = set()

    tags = defaultdict(OrderedSet)

    for python_version in python_versions:
        main_data_dir = os.path.join(data_dir, python_version, "main")

        develop_data_dir = os.path.join(data_dir, python_version, "develop")

        factory_data_dir = os.path.join(data_dir, python_version, "factory")

        cpython_data_dir = os.path.join(data_dir, python_version, "cpython")

        for entry in sorted(os.listdir(main_data_dir)):
            if not entry.endswith(".data"):
                continue

            construct_name = entry.split(".")[0]
            construct_names.add(construct_name)

            cpython_values = readDataFile(os.path.join(cpython_data_dir, entry))

            factory_values = readDataFile(os.path.join(factory_data_dir, entry))

            develop_values = readDataFile(os.path.join(develop_data_dir, entry))

            main_values = readDataFile(os.path.join(main_data_dir, entry))

            graph_data[python_version, construct_name] = dict(
                cpython=cpython_values["CPYTHON_CONSTRUCT"],
                main=main_values["NUITKA_CONSTRUCT"],
                develop=develop_values["NUITKA_CONSTRUCT"],
                factory=factory_values["NUITKA_CONSTRUCT"],
            )

            tags[construct_name].add(
                makeTag(
                    python_version=python_version,
                    case_data=graph_data[python_version, construct_name],
                    version1="main",
                    version2="develop",
                )
            )
            tags[construct_name].add(
                makeTag(
                    python_version=python_version,
                    case_data=graph_data[python_version, construct_name],
                    version1="develop",
                    version2="factory",
                ),
            )

    return python_versions, construct_names, graph_data, tags


def isLessTicksThan(value1, value2):
    if abs(value1 - value2) / float(value1) < 0.001:
        return False

    if abs(value1 - value2) < 1000:
        return False

    return value1 < value2


# Check noise detection correctness
assert isLessTicksThan(102528524, 77178450) is False
assert isLessTicksThan(77178450, 102528524) is True
assert isLessTicksThan(99858, 99542) is False
assert isLessTicksThan(99542, 99858) is False


def updateConstructGraphs():
    python_versions, construct_names, graph_data, tags = getConstructGraphData()

    home_dir = getHomeDir()

    graphs = {}

    for python_version in python_versions:
        for construct_name in construct_names:
            if (python_version, construct_name) in graph_data:
                graphs[python_version, construct_name] = generateConstructGraph(
                    name=construct_name,
                    python_version=python_version,
                    graph_data=graph_data[python_version, construct_name],
                )

    for construct_name in sorted(construct_names):
        construct_tags = tags[construct_name]

        construct_rst = os.path.join(
            home_dir, "constructs", "construct-%s.rst" % construct_name
        )

        makedirs(os.path.dirname(construct_rst))

        for python_version in python_versions:
            key = python_version, construct_name

            if key not in graph_data:
                continue

        with open(construct_rst, "w") as construct_file:
            construct_file.write(
                """\
.. title: Construct %s
.. tags: %s
.. date: %s

.. contents::
"""
                % (
                    construct_name,
                    ",".join(construct_tags or ["untagged"]),
                    datetime.datetime.now().strftime("%m/%d/%Y, %H:%M:%S"),
                )
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
Also coming are optimization tests, demonstrating the removal or simplification
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
            getNuitkaWorkTreeDir("factory"), "bin/measure-construct-performance"
        ),
        "--nuitka",
        os.path.join(getNuitkaWorkTreeDir(name), "bin/nuitka"),
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

    return readDataFile(data_filename)


def _validate(values, test_case_hash, commit):
    if values is None:
        return None
    if (
        values.get("TEST_CASE_HASH") != test_case_hash
        or values.get("NUITKA_COMMIT") != commit.hexsha
    ):
        return None

    return values


def getTestCasesDir():
    return os.path.join(getNuitkaWorkTreeDir("factory"), "tests/benchmarks/constructs")


def _updateNumbers(python):
    python_version = getPythonVersion(python)
    major = ".".join(python_version.split(".")[:2])

    print("Working with", major)

    nuitka_factory_commit = getCommitIdFromName("factory")
    nuitka_develop_commit = getCommitIdFromName("develop")
    nuitka_main_commit = getCommitIdFromName("main")

    cases_dir = getTestCasesDir()

    for filename in sorted(os.listdir(cases_dir)):
        # TODO: Is this still valid?
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

        if major in ("2.6", "2.7", "3.4") and filename.endswith("35.py"):
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

        main_values = _readNumbers("main", major, filename)
        main_values = _validate(main_values, test_case_hash, nuitka_main_commit)

        if needs_cpython:
            print("CPython ... ")
            makedirs(os.path.dirname(cpython_filename))

            command = [
                python,
                os.path.join(
                    getNuitkaWorkTreeDir("factory"), "bin/measure-construct-performance"
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

        if main_values is None:
            print("Nuitka main ... ")
            _takeNumbers("main", python, major, filename)

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

    _updateNumbers("python3.10")
    _updateNumbers("python3.11")
    _updateNumbers("python3.12")
    #    _updateNumbers("python3.8")
    _updateNumbers("python2.7")


def reportNumbers():
    print("Report of numbers:")

    python_versions, construct_names, graph_data, tags = getConstructGraphData()

    data = []

    for construct_name, tag_set in tags.items():
        for tag in tag_set:
            if "steady" in tag:
                continue

            python_version = tag.split("_")[0]
            python_version = python_version[0] + "." + python_version[1:]

            if python_version == "2.7":
                continue

            if not tag.startswith("312_factory"):
                continue

            factory = graph_data[python_version, construct_name]["factory"]
            develop = graph_data[python_version, construct_name]["develop"]
            main = graph_data[python_version, construct_name]["main"]

            data.append((construct_name, tag, python_version, main, develop, factory, ((factory/develop) * 100)))

    data.sort(key = lambda d:d[6])

    for line in data:
        construct_name, tag, python_version, main, develop, factory, percent = line

        print(construct_name, tag, python_version, main, develop, factory, "%.2f" % percent)



def main():
    parser = OptionParser()

    parser.add_option(
        "--update-nuitka",
        action="store_true",
        dest="nuitka",
        default=False,
        help="""\
When given, the Nuitka repo is updated. Default %default.""",
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
        "--show-numbers",
        action="store_true",
        dest="show",
        default=False,
        help="""\
When given, report the interesting numbers in text report. Default %default.""",
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
        options.show = True
        options.graph = True
        options.build = True
        options.deploy = True

    # TODO: Make this an option too.
    if not os.path.isdir("doc/images"):
        fetchDocs()

    if options.nuitka:
        updateNuitkaSoftware()

    if options.numbers:
        updateNumbers()

    if options.show:
        reportNumbers()

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

    if options.deploy:
        runNikolaCommand("deploy")


if __name__ == "__main__":
    print("Running with %s" % sys.executable)
    os.environ["PATH"] = (
        os.path.dirname(sys.executable) + os.pathsep + os.environ["PATH"]
    )

    main()
