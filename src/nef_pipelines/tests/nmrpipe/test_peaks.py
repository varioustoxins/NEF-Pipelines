import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrpipe.importers.peaks import peaks

HEADER = open(path_in_test_data(__file__, "test_header_entry.txt")).read()

PEAKS_NMRPIPE = "nef_nmr_spectrum_nmrpipe"
METADATA_NMRPIPE = "nef_nmr_meta_data"


app = typer.Typer()
app.command()(peaks)


# noinspection PyUnusedLocal
def test_peaks():
    EXPECTED = open(
        path_in_test_data(__file__, "gb3_assigned_trunc_expected.tab")
    ).read()

    path = path_in_test_data(__file__, "gb3_assigned_trunc.tab")
    result = run_and_report(app, [path], input=HEADER)

    assert result.exit_code == 0
    peaks_result = isolate_frame(result.stdout, "%s" % PEAKS_NMRPIPE)

    assert_lines_match(EXPECTED, peaks_result)
