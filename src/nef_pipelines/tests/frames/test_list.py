from pathlib import Path

import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.list import list

app = typer.Typer()
app.command()(list)


# noinspection PyUnusedLocal
def test_frame_basic():

    path = path_in_test_data(__file__, "frames.nef")
    result = run_and_report(app, ["--in", path])

    EXPECTED = """\
        entry test

        nef_nmr_meta_data  nef_molecular_system
    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_frame_file_first():

    path = path_in_test_data(__file__, "frames.nef")

    result = run_and_report(app, [path])

    EXPECTED = """\
        entry test

        nef_nmr_meta_data  nef_molecular_system
    """

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_frame_file_first_and_select():

    path = path_in_test_data(__file__, "frames.nef")
    result = run_and_report(app, [path, "meta_data"])

    EXPECTED = """\
        entry test

        nef_nmr_meta_data
    """

    assert_lines_match(EXPECTED, result.stdout)


def test_frame_no_file():

    path = Path("NO_SUCH_FILE")
    run_and_report(app, [path], expected_exit_code=1)


def test_frame_basic_verbose():

    path = path_in_test_data(__file__, "frames.nef")
    result = run_and_report(app, ["--in", path, "--verbose"])

    EXPECTED_VERBOSE = """
        entry test
            lines: 48 frames: 2 checksum: d6235a487cbdb33cb1ed5d2f5f3f2635 [md5]
        1. nef_nmr_meta_data
            category: nef_nmr_meta_data
            loops: 1 [lengths: 19]
            loop names: nef_program_script
            is nef frame: True
        2. nef_molecular_system
            category: nef_molecular_system
            loops: 1 [lengths: 13]
            loop names: nef_sequence
            is nef frame: True

    """

    assert_lines_match(EXPECTED_VERBOSE, result.stdout)
