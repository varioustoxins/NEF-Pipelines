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
def test_shifts_single_chain():

    EXPECTED = """\
        save_nef_chemical_shift_list_ucbshift
           _nef_chemical_shift_list.sf_category      nef_chemical_shift_list
           _nef_chemical_shift_list.sf_framecode     nef_chemical_shift_list_ucbshift

           loop_
              _nef_chemical_shift.chain_code
              _nef_chemical_shift.sequence_code
              _nef_chemical_shift.residue_name
              _nef_chemical_shift.atom_name
              _nef_chemical_shift.value
              _nef_chemical_shift.value_uncertainty
              _nef_chemical_shift.element
              _nef_chemical_shift.isotope_number

              A   1   MET   H    8.432     .   H   1
              A   1   MET   HA   4.207     .   H   1
              A   1   MET   C    170.727   .   C   13
              A   1   MET   CA   54.512    .   C   13
              A   1   MET   CB   33.104    .   C   13
              A   1   MET   N    120.882   .   N   15
              A   2   GLN   H    8.928     .   H   1
              A   2   GLN   HA   4.984     .   H   1
              A   2   GLN   C    175.83    .   C   13
              A   2   GLN   CA   54.92     .   C   13
              A   2   GLN   CB   30.66     .   C   13
              A   2   GLN   N    123.822   .   N   15
              A   3   ILE   H    8.347     .   H   1
              A   3   ILE   HA   4.258     .   H   1
              A   3   ILE   C    171.982   .   C   13
              A   3   ILE   CA   59.497    .   C   13
              A   3   ILE   CB   42.071    .   C   13
              A   3   ILE   N    116.238   .   N   15

           stop_

        save_
    """

    sequence_file = path_in_test_data(__file__, "test_sequence.nef")
    ucbshift_file = path_in_test_data(__file__, "test_shifts.csv")

    result = run_and_report(
        app, ["shifts", "-i", sequence_file, ucbshift_file], expected_exit_code=0
    )

    ucbshift_frame = isolate_frame(result.stdout, "nef_chemical_shift_list_ucbshift")

    assert_lines_match(EXPECTED, ucbshift_frame)
