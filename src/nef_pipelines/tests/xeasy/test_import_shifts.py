import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xeasy.importers.shifts import shifts

SHIFTS_XEASY = "nef_chemical_shift_list_xeasy"

app = typer.Typer()
app.command()(shifts)

EXPECTED = """\
save_nef_chemical_shift_list_xeasy
   _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
   _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_xeasy
   loop_
      _nef_chemical_shift.chain_code
      _nef_chemical_shift.sequence_code
      _nef_chemical_shift.residue_name
      _nef_chemical_shift.atom_name
      _nef_chemical_shift.value
      _nef_chemical_shift.value_uncertainty
      _nef_chemical_shift.element
      _nef_chemical_shift.isotope_number
     A   1   HIS   N     112.794   0.010   .   .
     A   1   HIS   HE1   7.955     0.010   .   .
     A   2   MET   N     113.996   0.000   .   .
     A   2   MET   QE    3.778     0.010   .   .
     A   2   MET   CE    27.054    0.010   .   .
     A   3   ARG   HD2   3.133     0.000   .   .
     A   3   ARG   HD3   3.134     0.000   .   .
     A   3   ARG   HE    4.378     0.010   .   .
   stop_
save_

"""


def test_ppm_out_short():

    STREAM = read_test_data("basic_sequence.nef", __file__)

    path = path_in_test_data(__file__, "basic_shifts.prot")

    result = run_and_report(app, [path], input=STREAM)

    shifts_result = isolate_frame(result.stdout, SHIFTS_XEASY)

    assert_lines_match(EXPECTED, shifts_result)
