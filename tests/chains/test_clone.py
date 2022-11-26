import pytest
from typer.testing import CliRunner

from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

runner = CliRunner()

CLONE_CHAIN = ["chains", "clone"]


@pytest.fixture
def using_clone():
    # register the module under test
    import tools.chains.clone  # noqa: F401


# noinspection PyUnusedLocal
def test_clone_basic(typer_app, using_clone, clear_cache, monkeypatch):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    INPUT = open(path_in_test_data(__file__, "3aa.nef")).read()

    result = runner.invoke(typer_app, [*CLONE_CHAIN, "A", "2"], input=INPUT)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\
            save_nef_molecular_system
               _nef_molecular_system.sf_category   nef_molecular_system
               _nef_molecular_system.sf_framecode  nef_molecular_system

               loop_
                  _nef_sequence.index
                  _nef_sequence.chain_code
                  _nef_sequence.sequence_code
                  _nef_sequence.residue_name
                  _nef_sequence.linking
                  _nef_sequence.residue_variant
                  _nef_sequence.cis_peptide

                 1   A   1   ALA   start    .   .
                 2   A   2   ALA   middle   .   .
                 3   A   3   ALA   end      .   .
                 4   B   1   ALA   start    .   .
                 5   B   2   ALA   middle   .   .
                 6   B   3   ALA   end      .   .
                 7   C   1   ALA   start    .   .
                 8   C   2   ALA   middle   .   .
                 9   C   3   ALA   end      .   .

               stop_

            save_
    """

    assert_lines_match(EXPECTED, isolate_frame(result.stdout, "nef_molecular_system"))


# noinspection PyUnusedLocal
def test_bad_count(typer_app, using_clone, clear_cache, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    INPUT = open(path_in_test_data(__file__, "3aa.nef")).read()

    result = runner.invoke(typer_app, [*CLONE_CHAIN, "A", "0"], input=INPUT)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 1

    assert "clone count must be > 0" in result.stdout


# noinspection PyUnusedLocal
def test_bad_target(typer_app, using_clone, clear_cache, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    INPUT = open(path_in_test_data(__file__, "3aa.nef")).read()

    result = runner.invoke(typer_app, [*CLONE_CHAIN, "B", "1"], input=INPUT)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 1

    assert "couldn't find target chain B" in result.stdout


# noinspection PyUnusedLocal
def test_custom_chains(typer_app, using_clone, clear_cache, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    INPUT = open(path_in_test_data(__file__, "3aa.nef")).read()

    result = runner.invoke(
        typer_app, [*CLONE_CHAIN, "A", "2", "--chains", "D,E"], input=INPUT
    )

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\
            save_nef_molecular_system
               _nef_molecular_system.sf_category   nef_molecular_system
               _nef_molecular_system.sf_framecode  nef_molecular_system

               loop_
                  _nef_sequence.index
                  _nef_sequence.chain_code
                  _nef_sequence.sequence_code
                  _nef_sequence.residue_name
                  _nef_sequence.linking
                  _nef_sequence.residue_variant
                  _nef_sequence.cis_peptide

                 1   A   1   ALA   start    .   .
                 2   A   2   ALA   middle   .   .
                 3   A   3   ALA   end      .   .
                 4   D   1   ALA   start    .   .
                 5   D   2   ALA   middle   .   .
                 6   D   3   ALA   end      .   .
                 7   E   1   ALA   start    .   .
                 8   E   2   ALA   middle   .   .
                 9   E   3   ALA   end      .   .

               stop_

            save_
    """

    assert_lines_match(EXPECTED, isolate_frame(result.stdout, "nef_molecular_system"))


# noinspection PyUnusedLocal
def test_clone_chain_clash(typer_app, using_clone, clear_cache, monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    INPUT = open(path_in_test_data(__file__, "3aa_x3.nef")).read()

    result = runner.invoke(typer_app, [*CLONE_CHAIN, "A", "2"], input=INPUT)

    if result.exit_code != 0:
        print("INFO: stdout from failed read:\n", result.stdout)

    assert result.exit_code == 0

    EXPECTED = """\
            save_nef_molecular_system
               _nef_molecular_system.sf_category   nef_molecular_system
               _nef_molecular_system.sf_framecode  nef_molecular_system

               loop_
                  _nef_sequence.index
                  _nef_sequence.chain_code
                  _nef_sequence.sequence_code
                  _nef_sequence.residue_name
                  _nef_sequence.linking
                  _nef_sequence.residue_variant
                  _nef_sequence.cis_peptide

                 1    A   1   ALA   start    .   .
                 2    A   2   ALA   middle   .   .
                 3    A   3   ALA   end      .   .
                 4    B   1   ALA   start    .   .
                 5    B   2   ALA   middle   .   .
                 6    B   3   ALA   end      .   .
                 7    C   1   ALA   start    .   .
                 8    C   2   ALA   middle   .   .
                 9    C   3   ALA   end      .   .
                 10   D   1   ALA   start    .   .
                 11   D   2   ALA   middle   .   .
                 12   D   3   ALA   end      .   .
                 13   E   1   ALA   start    .   .
                 14   E   2   ALA   middle   .   .
                 15   E   3   ALA   end      .   .

               stop_

            save_
    """

    assert_lines_match(EXPECTED, isolate_frame(result.stdout, "nef_molecular_system"))
