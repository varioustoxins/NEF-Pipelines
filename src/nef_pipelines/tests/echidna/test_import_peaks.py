import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.echidna.importers.peaks import peaks

app = typer.Typer()
app.command()(peaks)


EXPECTED = """
loop_
   _nef_peak.index
   _nef_peak.peak_id
   _nef_peak.chain_code_1
   _nef_peak.sequence_code_1
   _nef_peak.residue_name_1
   _nef_peak.atom_name_1
   _nef_peak.chain_code_2
   _nef_peak.sequence_code_2
   _nef_peak.residue_name_2
   _nef_peak.atom_name_2
   _nef_peak.position_1
   _nef_peak.position_uncertainty_1
   _nef_peak.position_2
   _nef_peak.position_uncertainty_2
   _nef_peak.height
   _nef_peak.height_uncertainty
   _nef_peak.volume
   _nef_peak.volume_uncertainty
   _nef_peak.ccpn_figure_of_merit
   _nef_peak.ccpn_comment

  1    1    A   10   ALA   N   A   10   ALA   H   122.836   .   7.826   .   .   .   .   .   6.03818   'large violation!'
  2    2    A   11   ALA   N   A   11   ALA   H   118.678   .   8.063   .   .   .   .   .   6.36477   'large violation!'
  3    3    A   12   ALA   N   A   12   ALA   H   119.301   .   7.842   .   .   .   .   .   4.6192    'large violation!'
  4    4    A   13   ALA   N   A   13   ALA   H   122.946   .   8.232   .   .   .   .   .   3.63582   'large violation!'
  5    5    A   14   ALA   N   A   14   ALA   H   120.475   .   8.948   .   .   .   .   .   3.07293   .
  6    6    A   15   ALA   N   A   15   ALA   H   118.138   .   8.798   .   .   .   .   .   2.89933   .
  7    7    A   16   ALA   N   A   16   ALA   H   120.784   .   8.035   .   .   .   .   .   3.00885   .
stop_
"""

EXPECTED_TENSOR = """
save_np_tensor_frame_echidna_peaks
   _np_tensor_frame.sf_category          np_tensor_frame
   _np_tensor_frame.sf_framecode         np_tensor_frame_echidna_peaks
   _np_tensor_frame.restraint_origin     measured
   _np_tensor_frame.ccpn_format          angles_euler
   _np_tensor_frame.restraint_magnitude  -3012.1
   _np_tensor_frame.restraint_rhomicity  -1797.8
   _np_tensor_frame.ccpn_phi             80.68
   _np_tensor_frame.ccpn_psi             164.6
   _np_tensor_frame.ccpn_theta           128.22
save_
"""

EXPECTED_POSITION = """
save_np_atom_position_echidna_peaks
   _np_atom_position.sf_category   np_atom_position
   _np_atom_position.sf_framecode  np_atom_position_echidna_peaks
   _np_atom_position.x             80.68
   _np_atom_position.y             17.426
   _np_atom_position.z             7.735

save_


"""


def test_basic():

    path = path_in_test_data(__file__, "echidna_peaks.txt")

    data_sequence = read_test_data("echidna_sequence.nef", __file__)

    result = run_and_report(app, [path], input=data_sequence)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_echidna_peaks", "nef_peak")

    assert_lines_match(EXPECTED, str(loop))

    frame = isolate_frame(result.stdout, "nef_nmr_spectrum_echidna_peaks")

    frame = " ".join(frame.split())
    assert (
        "_nef_nmr_spectrum.ccpn_comment 'NOTE: merits with values > 3.63582 are flagged as large violations"
        in frame
    )
    assert (
        "_nef_nmr_spectrum.np_tensor_frame_name np_tensor_frame_echidna_peaks" in frame
    )
    assert (
        "_nef_nmr_spectrum.np_atom_position_name np_atom_position_echidna_peaks"
        in frame
    )

    tensor_frame = isolate_frame(result.stdout, "np_tensor_frame_echidna_peaks")

    assert_lines_match(tensor_frame, EXPECTED_TENSOR)

    position_frame = isolate_frame(result.stdout, "np_atom_position_echidna_peaks")

    assert_lines_match(position_frame, EXPECTED_POSITION)
