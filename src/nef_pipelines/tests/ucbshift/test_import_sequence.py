from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.ucbshift import import_app

runner = CliRunner()
app = import_app


# noinspection PyUnusedLocal
def test_sequence_single_chain():

    EXPECTED = """\
        save_nef_molecular_system
           _nef_molecular_system.sf_category      nef_molecular_system
           _nef_molecular_system.sf_framecode     nef_molecular_system

           loop_
              _nef_sequence.index
              _nef_sequence.chain_code
              _nef_sequence.sequence_code
              _nef_sequence.residue_name
              _nef_sequence.linking
              _nef_sequence.residue_variant
              _nef_sequence.cis_peptide

               1   A   1   MET   start    .   .
               2   A   2   GLN   middle   .   .
               3   A   3   ILE   end      .   .

           stop_

        save_
    """

    ucbshift_file = path_in_test_data(__file__, "test_shifts.csv")

    result = run_and_report(app, ["sequence", ucbshift_file], expected_exit_code=0)

    molecular_system_frame = isolate_frame(result.stdout, "nef_molecular_system")

    assert_lines_match(EXPECTED, molecular_system_frame)


# noinspection PyUnusedLocal
def test_sequence_with_chain_code():

    EXPECTED = """\
        save_nef_molecular_system
           _nef_molecular_system.sf_category      nef_molecular_system
           _nef_molecular_system.sf_framecode     nef_molecular_system

           loop_
              _nef_sequence.index
              _nef_sequence.chain_code
              _nef_sequence.sequence_code
              _nef_sequence.residue_name
              _nef_sequence.linking
              _nef_sequence.residue_variant
              _nef_sequence.cis_peptide

               1   B   1   MET   start    .   .
               2   B   2   GLN   middle   .   .
               3   B   3   ILE   end      .   .

           stop_

        save_
    """

    ucbshift_file = path_in_test_data(__file__, "test_shifts.csv")

    result = run_and_report(
        app, ["sequence", "--chain-code", "B", ucbshift_file], expected_exit_code=0
    )

    molecular_system_frame = isolate_frame(result.stdout, "nef_molecular_system")

    assert_lines_match(EXPECTED, molecular_system_frame)
