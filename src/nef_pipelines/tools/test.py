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


# TODO add verbosity control
# TODO add flag to enable warnings


@app.command()
def test(
    warnings: bool = typer.Option(
        False, "-w", "--warnings", help="include all warnings"
    ),
    targets: List[str] = typer.Argument(None, help=TARGET_HELP),
):
    """-  run the test suite"""

    from pytest import main

    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent

    root_path = str(dir_path.parent / "..")

    os.chdir(Path(root_path).absolute())

    tests = _find_pytest_commands(root_path, targets)

    if not targets or (targets and len(tests) != 0):
        command = ["-vvv", "--full-trace", *tests]

        if not warnings:
            command = ["--disable-warnings", *command]
        main(command)


def _find_pytest_commands(root_path, targets):
    if not targets:
        targets = "*"

    ret_code, stdout, stderr = run_and_read_pytest(["--collect-only", "-qq", root_path])

    print(stdout)

    if ret_code != 0:
        output = f"""
        return code: {ret_code}
        __________________________________________________________________stdout_______________________________________________________________
        {stdout}
        _______________________________________________________________________________________________________________________________________
        __________________________________________________________________stderr_______________________________________________________________
        {stderr}
        _______________________________________________________________________________________________________________________________________
        """
        print(output, file=sys.stderr)
        _exit_if_stderr(stdout)

    tests = stdout.split("\n")[:-3]

    return [
        Path.cwd() / test_path for test_path in select_matching_tests(tests, targets)
    ]


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
