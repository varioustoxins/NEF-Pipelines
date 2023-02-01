import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.mars.exporters.shifts import shifts

app = typer.Typer()
app.command()(shifts)


def test_export_shifts_nef5_short():
    stream = open(path_in_test_data(__file__, "sec5_short.neff")).read()

    result = run_and_report(app, ["-"], input=stream)

    EXPECTED = """\
              H      N        CA      CA-1    CB      CB-1
        PR_1  8.594  133.252  61.159  59.291  33.274  37.309
        PR_2  8.928  131.397  -       -       -       -
        PR_3  9.671  130.698  60.735  62.418  39.792  69.744
        PR_4  8.185  128.894  53.744  54.679  43.207  34.050
        PR_5  8.548  128.09   56.292  65.574  32.964  69.899
    """

    assert_lines_match(EXPECTED, result.stdout)
