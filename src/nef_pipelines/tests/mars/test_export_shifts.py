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


def test_export_shifts_pete_co():

    stream = open(path_in_test_data(__file__, "short_co.neff")).read()

    result = run_and_report(app, ["-"], input=stream)

    EXPECTED = """\
                   H        N  CA      CA-1    CB-1    CO       CO-1
        PR_1  11.671  136.682  -       -       -       -        -
        PR_2  10.946  131.689  -       -       -       -        -
        PR_3  10.266  112.518  46.281  63.862  32.984  176.722  178.726
        PR_4   9.632  104.529  46.465  -       -       173.390  175.767

    """

    assert_lines_match(EXPECTED, result.stdout)
