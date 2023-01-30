from textwrap import dedent

import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.pales.exporters.rdcs import rdcs

runner = CliRunner()
app = typer.Typer()
app.command()(rdcs)

NEF_STREAM = open(path_in_test_data(__file__, "pales_test_1.nef")).read()
NEF_STREAM_DISORDERED = open(path_in_test_data(__file__, "pales_test_2.nef")).read()
NEF_STREAM_SEGIDS = open(path_in_test_data(__file__, "pales_test_segids.nef")).read()


# noinspection PyUnusedLocal
def test_rdcs(clear_cache):

    result = run_and_report(app, [], input=NEF_STREAM)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\

        VARS    RESID_I  RESNAME_I  ATOMNAME_I  RESID_J  RESNAME_J  ATOMNAME_J  D      DD     W
        FORMAT  %5d      %6s        %6s         %5d      %6s        %6s         %9.3f  %9.3f  %.2f
                3        GLY        HN          22       GLY        N           3.1    0.4    1.0
                2        TRP        HN          21       TRP        N          -5.2    0.33   1.0

    """
    EXPECTED = dedent(EXPECTED)

    assert_lines_match(EXPECTED, result.stdout)


# noinspection PyUnusedLocal
def test_rdcs_disordered(clear_cache):

    result = run_and_report(app, [], input=NEF_STREAM_DISORDERED)

    assert result.exit_code == 0

    EXPECTED = """\

        VARS    RESID_I  RESNAME_I  ATOMNAME_I  RESID_J  RESNAME_J  ATOMNAME_J  D      DD     W
        FORMAT  %5d      %6s        %6s         %5d      %6s        %6s         %9.3f  %9.3f  %.2f
                3        GLY        HN          22       GLY        N           3.1    0.4    1.0
                2        TRP        HN          21       TRP        N          -5.2    0.33   1.0

    """

    assert_lines_match(EXPECTED, result.stdout)


def test_rdcs_segid(clear_cache):

    result = run_and_report(app, ["--segids"], input=NEF_STREAM_SEGIDS)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\

        VARS    SEGNAME_I RESID_I  RESNAME_I  ATOMNAME_I  SEGNAME_J RESID_J  RESNAME_J  ATOMNAME_J  D      DD     W
        FORMAT  %4s       %5d      %6s        %6s         %4s       %5d      %6s        %6s         %9.3f  %9.3f  %.2f
                AAAA      3        GLY        HN          AAAA      22       GLY        N           3.1    0.4    1.0
                AAAA      2        TRP        HN          AAAA      21       TRP        N          -5.2    0.33   1.0

    """
    EXPECTED = dedent(EXPECTED)

    assert_lines_match(EXPECTED, result.stdout)
