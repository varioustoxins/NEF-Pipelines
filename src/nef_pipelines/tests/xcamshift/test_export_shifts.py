import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xcamshift.exporters.shifts import shifts

runner = CliRunner()
app = typer.Typer()
app.command()(shifts)

EXPECTED = """\
assign  (  segid  AAAA  and  resid  1  and  resn  ALA  and  name  N    )  115.740
assign  (  segid  AAAA  and  resid  1  and  resn  ALA  and  name  C    )  181.080
assign  (  segid  AAAA  and  resid  1  and  resn  ALA  and  name  CA   )   53.270
assign  (  segid  AAAA  and  resid  1  and  resn  ALA  and  name  CB   )   20.340
assign  (  segid  AAAA  and  resid  1  and  resn  ALA  and  name  HA   )    5.320
assign  (  segid  AAAA  and  resid  2  and  resn  GLY  and  name  HN   )    7.310
assign  (  segid  AAAA  and  resid  2  and  resn  GLY  and  name  N    )  117.940
assign  (  segid  AAAA  and  resid  2  and  resn  GLY  and  name  C    )  176.920
assign  (  segid  AAAA  and  resid  2  and  resn  GLY  and  name  CA   )   46.770
assign  (  segid  AAAA  and  resid  2  and  resn  GLY  and  name  HA2  )    4.890
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  HN   )    8.820
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  N    )  116.850
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  C    )  172.980
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  CA   )   71.710
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  CB   )   33.150
assign  (  segid  AAAA  and  resid  3  and  resn  VAL  and  name  HA   )    5.020
"""


# noinspection PyUnusedLocal
def test_3ab():

    input = read_test_data("test_agv.neff", __file__)
    result = run_and_report(app, ["-"], input=input)

    assert_lines_match(EXPECTED, result.stdout)
