import os

from textwrap import dedent
from typing import List

import typer
from pathlib import Path

from lib.test_lib import select_matching_tests, run_and_read_pytest
from lib.util import exit_error
from nef_app import app


def _find_pytest_commands(root_path, targets):
    if not targets:
        targets = '*'

    stdout, stderr = run_and_read_pytest(['--collect-only', '-q', root_path])

    _exit_if_stderr(stderr)

    tests = stdout.split('\n')[:-3]

    return select_matching_tests(tests, targets)


def _exit_if_stderr(stderr):
    if stderr.strip():
        msg = \
            '''
               couldn't collect tests because of an error
               
               ----------------------- pytest errors -----------------------
               {stderr}
               ----------------------- pytest errors -----------------------
            '''
        msg = dedent(msg)
        msg = f'{msg}'
        exit_error(msg)


TARGET_HELP = \
    '''
    targets are selected as path::name, globs can be used, 
    missing paths and names are replaced by * eg path:: is equivalent to path::*
    '''
TARGET_HELP = dedent(TARGET_HELP)

@app.command()
def test(
        targets: List[str] = typer.Argument(None, help=TARGET_HELP)
):
    """-  run the test suite"""

    from pytest import main

    dir_path = Path(os.path.dirname(os.path.realpath(__file__))).parent / 'tests'

    root_path = f'{str(dir_path.parent / "tests")}'

    tests = _find_pytest_commands(root_path, targets)

    if not targets or (targets and len(tests) != 0):
        main(['-vvv', *tests])
