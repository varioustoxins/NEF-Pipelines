import os
import sys
from pathlib import Path
from textwrap import dedent
from typing import List

import typer

from nef_pipelines.lib.test_lib import run_and_read_pytest, select_matching_tests
from nef_pipelines.lib.util import exit_error
from nef_pipelines.nef_app import app

TARGET_HELP = """
    targets are selected as path::name, globs can be used,
    missing paths and names are replaced by * eg path:: is equivalent to path::*
    note: filenames do not require a trailing .py
    """
TARGET_HELP = dedent(TARGET_HELP)


@app.command(rich_help_panel="Housekeeping")
def test(
    warnings: bool = typer.Option(
        False, "-w", "--warnings", help="include all warnings"
    ),
    verbose: int = typer.Option(
        0,
        "-v",
        "--verbose",
        count=True,
        help="increase verbosity: -v (normal), -vv (verbose), -vvv (very verbose)",
    ),
    show_capture: bool = typer.Option(
        False, "-s", "--show-capture", help="show print statements and captured output"
    ),
    exit_first: bool = typer.Option(
        False, "-x", "--exitfirst", help="exit on first test failure"
    ),
    keyword: str = typer.Option(
        None, "-k", "--keyword", help="only run tests matching given expression"
    ),
    traceback: str = typer.Option(
        "long",
        "--tb",
        "--traceback",
        help="traceback style: auto, long, short, line, native, no",
    ),
    pdb: bool = typer.Option(False, "--pdb", help="drop into debugger on failures"),
    markers: str = typer.Option(
        None, "-m", "--markers", help="only run tests matching given mark expression"
    ),
    quiet: bool = typer.Option(
        False, "-q", "--quiet", help="decrease verbosity (quiet mode)"
    ),
    targets: List[str] = typer.Argument(None, help=TARGET_HELP),
):
    """- run the test suite"""

    from pytest import main

    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent

    root_path = str(dir_path.parent / "nef_pipelines" / "tests")

    os.chdir(Path(root_path).absolute())

    tests = _find_pytest_commands(root_path, targets)

    if not targets or (targets and len(tests) != 0):
        # Build verbosity flags
        if quiet:
            verbosity_flags = ["-q"]
        elif verbose == 0:
            # default no verbosity
            verbosity_flags = []
        else:
            verbosity_flags = [f"-{'v' * verbose}"]

        command = [*verbosity_flags, "--full-trace", *tests]

        # Only disable warnings if explicitly requested (no --warnings flag)
        # This allows Python warnings (like pyparsing) to be captured by pytest
        if not warnings:
            command = ["--disable-warnings", *command]

        if show_capture:
            command.append("-s")

        if exit_first:
            command.append("-x")

        if keyword:
            command.extend(["-k", keyword])

        if traceback != "long":
            command.append(f"--tb={traceback}")

        if pdb:
            command.append("--pdb")

        if markers:
            command.extend(["-m", markers])

        try:
            exit_code = main(command)
        except Exception as e:
            print(f"\nERROR: pytest failed to start:\n{e}", file=sys.stderr)
            sys.stderr.flush()
            sys.exit(1)

        sys.stderr.flush()
        sys.stdout.flush()
        sys.exit(exit_code)


def _find_pytest_root(root_path):

    stdout = _run_pytest_and_exit_error(["--fixtures", root_path])

    result = None

    for line in stdout.split("\n"):

        if line.startswith("rootdir:"):
            spaced_fields = line.split()
            fields = []

            for field in spaced_fields:
                fields.extend(field.split(","))
            result = fields[1]
            break

    return result


def _find_pytest_commands(root_path, targets):
    if not targets:
        targets = "*"

    stdout = _run_pytest_and_exit_error(["--collect-only", "-qq", root_path])

    pytest_root = _find_pytest_root(root_path)

    if not pytest_root:
        exit_error(f"couldn't find pytest root directory starting from: {root_path}")

    tests = stdout.split("\n")[:-3]

    result = [
        Path(pytest_root) / test_path
        for test_path in select_matching_tests(tests, targets)
    ]

    return result


def _run_pytest_and_exit_error(commands):
    ret_code, stdout, stderr = run_and_read_pytest(commands)

    if ret_code != 0:
        msg = f"""
        running pytest failed:

        return code: {ret_code}
        __________________________________________________________________stdout_______________________________________________________________
        {stdout}
        _______________________________________________________________________________________________________________________________________
        __________________________________________________________________stderr_______________________________________________________________
        {stderr}
        _______________________________________________________________________________________________________________________________________
        """

        exit_error(msg)

    return stdout


def _exit_if_stderr(stderr):
    if stderr.strip():
        _exit_pytest_error(stderr)


def _exit_pytest_error(output):
    msg = f"""
               couldn't collect tests because of an error

               ----------------------- pytest errors -----------------------
               {output}
               ----------------------- pytest errors -----------------------
            """
    msg = dedent(msg)
    msg = f"{msg}"
    exit_error(msg)
