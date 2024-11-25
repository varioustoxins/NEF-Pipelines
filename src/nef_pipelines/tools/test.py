import os
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
    # native_tracebacks: bool = typer.Option(False, '-n', '--native-tracebacks', help='use standard python tracebacks'),
    targets: List[str] = typer.Argument(None, help=TARGET_HELP),
):
    """- run the test suite"""

    from pytest import main

    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent

    root_path = str(dir_path.parent / "nef_pipelines" / "tests")

    os.chdir(Path(root_path).absolute())

    tests = _find_pytest_commands(root_path, targets)

    if not targets or (targets and len(tests) != 0):
        command = ["-vvv", "--full-trace", *tests]

        if not warnings:
            command = ["--disable-warnings", *command]
        # if native_tracebacks:
        #     command = ['--tb=native', *command]
        main(command)


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
