import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.tabulate import tabulate

runner = CliRunner()
app = typer.Typer()
app.command()(tabulate)


# noinspection PyUnusedLocal
def test_frame_basic(clear_cache):

    path = path_in_test_data(__file__, "tailin_seq_short.nef")

    result = run_and_report(app, ["--pipe", path])

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\
      ind   chain       seq   resn     link
         1  A             10  GLU      start
         2  A             11  TYR      middle
         3  A             12  ALA      middle
         4  A             13  GLN      middle
         5  A             14  PRO      middle
         6  A             15  ARG      middle
         7  A             16  LEU      middle
         8  A             17  ARG      middle
         9  A             18  LEU      middle
        10  A             19  GLY      middle
        11  A             20  PHE      middle
        12  A             21  GLU      middle
        13  A             22  ASP      end

    """

    assert_lines_match(EXPECTED, result.stdout)
