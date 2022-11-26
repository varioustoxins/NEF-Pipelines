import pytest
from typer.testing import CliRunner

from lib.test_lib import assert_lines_match, path_in_test_data, run_and_report

runner = CliRunner()


PALES_TEMPLATE = ["pales", "export", "template"]
SEQUENCE_STREAM = open(
    path_in_test_data(__file__, "tailin_seq_short.nef", local=True)
).read()


@pytest.fixture
def using_pales():
    # register the module under test
    import transcoders.pales  # noqa: F401


# noinspection PyUnusedLocal
def test_template(typer_app, using_pales, monkeypatch, clear_cache):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    result = run_and_report(typer_app, PALES_TEMPLATE, input=SEQUENCE_STREAM)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    # note: sequence starts at residue 10 so residue 10 has an amine not an amide and isn't in the tremplate...
    EXPECTED = """\
        REMARK NEF CHAIN A
        REMARK NEF START RESIDUE 10

        DATA SEQUENCE EYAQPRLRLG FED

        VARS    RESID_I  RESNAME_I  ATOMNAME_I  RESID_J  RESNAME_J  ATOMNAME_J  D      DD     W
        FORMAT  %5d      %6s        %6s         %5d      %6s        %6s         %9.3f  %9.3f  %.2f
                11       TYR        HN          11       TYR        N           0.0    0.0    1.0
                12       ALA        HN          12       ALA        N           0.0    0.0    1.0
                13       GLN        HN          13       GLN        N           0.0    0.0    1.0
                15       ARG        HN          15       ARG        N           0.0    0.0    1.0
                16       LEU        HN          16       LEU        N           0.0    0.0    1.0
                17       ARG        HN          17       ARG        N           0.0    0.0    1.0
                18       LEU        HN          18       LEU        N           0.0    0.0    1.0
                19       GLY        HN          19       GLY        N           0.0    0.0    1.0
                20       PHE        HN          20       PHE        N           0.0    0.0    1.0
                21       GLU        HN          21       GLU        N           0.0    0.0    1.0
                22       ASP        HN          22       ASP        N           0.0    0.0    1.0
    """

    assert_lines_match(EXPECTED, result.stdout)
