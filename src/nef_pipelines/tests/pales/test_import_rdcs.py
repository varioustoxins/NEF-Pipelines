import pytest
import typer
from pynmrstar import Entry
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.pales.importers.rdcs import rdcs

runner = CliRunner()
app = typer.Typer()
app.command()(rdcs)


# noinspection PyUnusedLocal
@pytest.mark.parametrize(
    "test_name",
    [
        "anA",
        "ssiaA",
        "ssiaF",
        "anDC_short",
        "dadrFixed_short",
        "dadrOnlyFixed_short",
        "saupePred_short",
        "ssiaB_short",
        "ssiaC_short",
        "ssia_short",
        "svd_short",
        "1AKI_pales_short",
    ],
)
def test_rdcs(test_name):

    test_data_path = path_in_test_data(
        __file__,
        f"{test_name}.tbl",
    )
    expected_data = read_test_data(f"{test_name}.nef", __file__)

    result = run_and_report(
        app,
        [
            test_data_path,
        ],
    )

    expected_entry = Entry.from_string(expected_data)

    for frame in expected_entry:
        test_frame = isolate_frame(result.stdout, frame.name)
        # TODO we should be able to compare the frames and loops logically and directly without going to strings
        assert_lines_match(str(frame), test_frame)
