import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import (
    assert_frame_category_exists,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.globals import globals_

app = typer.Typer()
app.command()(globals_)


def test_null():

    result = run_and_report(app, [])

    assert result.stdout.strip() == ""


def test_basic():
    data = read_test_data(
        "header.nef",
        __file__,
    )

    result = run_and_report(app, ["--verbose"], input=data)

    entry = Entry.from_string(result.stdout)

    assert_frame_category_exists(entry, "nefpls_globals")

    globals_frames = entry.get_saveframes_by_category("nefpls_globals")

    globals_frame = globals_frames[0]
    assert globals_frame.get_tag("_nefpls_globals.verbose")[0] == "True"
    assert globals_frame.get_tag("_nefpls_globals.force")[0] == "False"
    assert "global options" in globals_frame.get_tag("_nefpls_globals.info")[0]


def test_passthru():
    data = read_test_data(
        "header.nef",
        __file__,
    )

    result = run_and_report(app, [], input=data)

    entry = Entry.from_string(result.stdout)

    assert_frame_category_exists(entry, "nefpls_globals")
