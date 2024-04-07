import typer
from typer.testing import CliRunner

from nef_pipelines.lib.nef_lib import NEF_MOLECULAR_SYSTEM
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.fasta.importers.sequence import sequence

runner = CliRunner()
app = typer.Typer()
app.command()(sequence)


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
def test_3aa():

    path = path_in_test_data(__file__, "3aa.fasta")
    result = run_and_report(app, [path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3AA, mol_sys_result)


def test_3aa_spaces():

    path = path_in_test_data(__file__, "3aa_spaces.fasta")
    result = run_and_report(app, [path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

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
def test_3aa_x2():

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = run_and_report(app, [path])

    assert result.exit_code == 0

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

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
def test_3aa_x2_off_10_b():

    path = path_in_test_data(__file__, "3aa_x2.fasta")
    result = run_and_report(app, ["--starts", "1,11", path])

    mol_sys_result = isolate_frame(result.stdout, "%s" % NEF_MOLECULAR_SYSTEM)

    assert_lines_match(EXPECTED_3A_AB_B_start_11, mol_sys_result)
