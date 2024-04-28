import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xplor.exporters.rdcs import rdcs

runner = CliRunner()
app = typer.Typer()
app.command()(rdcs)

EXPECTED = """\
! restraints from frame nef_rdc_restraint_list_rdcs in nef entry xplor

assign  (  resn   ANI   and  name   OO  )
        (  resn   ANI   and  name   Z   )
        (  resn   ANI   and  name   X   )
        (  resn   ANI   and  name   Y   )
        (  segid  AAAA  and  resid  1   and  resname  ALA  and  name  HA    )
        (  segid  AAAA  and  resid  1   and  resname  ALA  and name   HN    )    1.300   1.000
assign  (  resn   ANI   and  name   OO  )
        (  resn   ANI   and  name   Z   )
        (  resn   ANI   and  name   X   )
        (  resn   ANI   and  name   Y   )
        (  segid  AAAA  and  resid  1   and  resname  ALA  and  name  HB    )
        (  segid  AAAA  and  resid  1   and  resname  ALA  and  name  HN    )    4.600   1.000
assign  (  resn   ANI   and  name   OO  )
        (  resn   ANI   and  name   Z   )
        (  resn   ANI   and  name   X   )
        (  resn   ANI   and  name   Y   )
        (  segid  AAAA  and  resid  2   and  resname  ALA  and  name  HG3#  )
        (  segid  AAAA  and  resid  2   and  resname  ALA  and  name  HN    )    2.400   1.000
assign  (  resn   ANI   and  name   OO  )
        (  resn   ANI   and  name   Z   )
        (  resn   ANI   and  name   X   )
        (  resn   ANI   and  name   Y   )
        (  segid  AAAA  and  resid  3   and  resname  ALA  and  name  HA    )
        (  segid  AAAA  and  resid  3   and  resname  ALA  and  name  HN    )    6.700   1.000

"""


# noinspection PyUnusedLocal
def test_3ab():

    with open(path_in_test_data(__file__, "3a_ab_rdcs.neff")) as fh:
        input = fh.read()

    result = run_and_report(app, [], input=input)

    assert_lines_match(EXPECTED, result.stdout)
