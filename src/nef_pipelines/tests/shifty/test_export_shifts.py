import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.shifty.exporters.shifts import shifts

runner = CliRunner()
app = typer.Typer()
app.command()(shifts)

EXPECTED = """\
#NUM  AA     HA     HN      N15      CA      CB       CO
1     A   5.320  0.000  115.740  53.270  20.340  181.080
2     G   0.000  7.310  117.940  46.770   0.000  176.920
3     V   5.020  8.820  116.850  71.710  33.150  172.980
"""


# noinspection PyUnusedLocal
def test_3ab(clear_cache):

    input = open(path_in_test_data(__file__, "test_agv.neff")).read()
    result = run_and_report(app, ["-"], input=input)

    assert_lines_match(EXPECTED, result.stdout)
