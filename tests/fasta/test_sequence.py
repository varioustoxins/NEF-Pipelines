import pytest
from typer.testing import CliRunner

from lib.test_lib import assert_lines_match, isolate_frame, path_in_test_data

MOLECULAR_SYSTEM = "nef_molecular_system"
FASTA_IMPORT_SEQUENCE = ["fasta", "import", "sequence"]

runner = CliRunner()


@pytest.fixture
def using_fasta():
    # register the module under test
    import transcoders.fasta  # noqa: F401


EXPECTED_3AA = """\
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

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3aa(typer_app, using_fasta, clear_cache, monkeypatch):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    path = path_in_test_data(__file__, "3aa.fasta", local=True)
    result = runner.invoke(typer_app, [*FASTA_IMPORT_SEQUENCE, path])

    print(result.stdout)

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)


EXPECTED_3A_AB = """\
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

     1   A    1   ALA   start    .   .
     2   A    2   ALA   middle   .   .
     3   A    3   ALA   end      .   .
     4   B    1   ALA   start    .   .
     5   B    2   ALA   middle   .   .
     6   B    3   ALA   end      .   .

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3aa_x2(typer_app, using_fasta, clear_cache, monkeypatch):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = runner.invoke(typer_app, [*FASTA_IMPORT_SEQUENCE, path])

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB, mol_sys_result)


EXPECTED_3A_AB_B_start_11 = """\
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

     1   A    1   ALA   start    .   .
     2   A    2   ALA   middle   .   .
     3   A    3   ALA   end      .   .
     4   B   11   ALA   start    .   .
     5   B   12   ALA   middle   .   .
     6   B   13   ALA   end      .   .

   stop_

save_"""


# noinspection PyUnusedLocal
def test_3aa_x2_off_10_b(typer_app, using_fasta, clear_cache, monkeypatch):

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = runner.invoke(
        typer_app, [*FASTA_IMPORT_SEQUENCE, "--starts", "1,11", path]
    )

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB_B_start_11, mol_sys_result)
