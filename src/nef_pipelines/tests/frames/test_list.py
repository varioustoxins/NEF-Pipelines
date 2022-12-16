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
