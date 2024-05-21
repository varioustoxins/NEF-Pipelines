import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrpipe.importers.peaks import peaks

HEADER = read_test_data("test_header_entry.txt", __file__)

METADATA_NMRPIPE = "nef_nmr_meta_data"


app = typer.Typer()
app.command()(peaks)


# noinspection PyUnusedLocal
def test_peaks():
    EXPECTED = read_test_data("gb3_assigned_trunc_expected.tab", __file__)

    path = path_in_test_data(__file__, "gb3_assigned_trunc.tab")
    result = run_and_report(app, [path], input=HEADER)

    peaks_result = isolate_frame(result.stdout, "nef_nmr_spectrum_gb3_assigned_trunc")

    assert_lines_match(EXPECTED, peaks_result)
