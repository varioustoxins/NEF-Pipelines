import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.sparky.importers.shifts import shifts

SHIFTS_SPARKY = "nef_chemical_shift_list_sparky"

app = typer.Typer()
app.command()(shifts)

EXPECTED = """\
save_nef_chemical_shift_list_sparky
    _nef_chemical_shift_list.sf_category   nef_chemical_shift_list
    _nef_chemical_shift_list.sf_framecode  nef_chemical_shift_list_sparky


    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.value_uncertainty
        _nef_chemical_shift.element
        _nef_chemical_shift.isotope_number

        A   236   PRO   C      176.443   .   C   13
        A   236   PRO   CA     62.822    .   C   13
        A   236   PRO   CB     32.269    .   C   13
        A   236   PRO   CD     49.668    .   C   13
        A   236   PRO   CG     27.035    .   C   13
        A   236   PRO   HA     4.438     .   H   1
        A   236   PRO   HB2    1.918     .   H   1
        A   236   PRO   HB3    2.271     .   H   1
        A   236   PRO   HD2    3.541     .   H   1
        A   236   PRO   HG2    1.967     .   H   1
        A   237   ALA   C      177.765   .   C   13
        A   237   ALA   CA     52.387    .   C   13
        A   237   ALA   CB     19.145    .   C   13
        A   237   ALA   HN     8.549     .   H   1
        A   237   ALA   HA     4.277     .   H   1
        A   237   ALA   N      124.638   .   N   15
        A   237   ALA   QB     1.357     .   H   1
        A   238   MET   C      175.895   .   C   13
        A   238   MET   CA     55.484    .   C   13
        A   238   MET   CB     32.904    .   C   13
        A   238   MET   CG     31.928    .   C   13
        A   238   MET   HN     8.379     .   H   1
        A   238   MET   HA     4.412     .   H   1
        A   238   MET   HB2    1.956     .   H   1
        A   238   MET   HB3    2.018     .   H   1
        A   238   MET   HG2    2.505     .   H   1
        A   238   MET   HG3    2.565     .   H   1
        A   238   MET   N      119.821   .   N   15
    stop_
save_
"""


def test_ppm_out_short():

    STREAM = read_test_data("P3a_L273R_sequence_short.neff", __file__)

    path = path_in_test_data(__file__, "test_shifts_P3a_L273R_shifts_short.txt")

    result = run_and_report(app, [path], input=STREAM)

    shifts_result = isolate_frame(result.stdout, SHIFTS_SPARKY)

    assert_lines_match(EXPECTED, shifts_result)
