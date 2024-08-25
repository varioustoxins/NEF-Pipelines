import typer

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.xeasy.importers.peaks import peaks

app = typer.Typer()
app.command()(peaks)


EXPECTED = """
save_nef_nmr_spectrum_xeasy_basic                                  # noqa: E501
   _nef_nmr_spectrum.sf_category                nef_nmr_spectrum
   _nef_nmr_spectrum.sf_framecode               nef_nmr_spectrum_xeasy_basic
   _nef_nmr_spectrum.num_dimensions             3
   _nef_nmr_spectrum.chemical_shift_list        .
   _nef_nmr_spectrum.experiment_classification  .
   _nef_nmr_spectrum.experiment_type            .

   loop_
      _nef_spectrum_dimension.dimension_id
      _nef_spectrum_dimension.axis_unit
      _nef_spectrum_dimension.axis_code
      _nef_spectrum_dimension.spectrometer_frequency
      _nef_spectrum_dimension.spectral_width
      _nef_spectrum_dimension.value_first_point
      _nef_spectrum_dimension.folding
      _nef_spectrum_dimension.absolute_peak_positions
      _nef_spectrum_dimension.is_acquisition

     1   ppm   1H    600.123   0.001   8.732     none   true   false
     2   ppm   1H    600.123   4.984   8.950     none   true   false
     3   ppm   15N   60.833    0.023   115.276   none   true   true

   stop_

   loop_
      _nef_spectrum_dimension_transfer.dimension_1
      _nef_spectrum_dimension_transfer.dimension_2
      _nef_spectrum_dimension_transfer.transfer_type
      _nef_spectrum_dimension_transfer.is_indirect

     1   2   onebond   false
     2   3   onebond   false

   stop_

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
      _nef_peak.chain_code_3
      _nef_peak.sequence_code_3
      _nef_peak.residue_name_3
      _nef_peak.atom_name_3
      _nef_peak.position_1
      _nef_peak.position_uncertainty_1
      _nef_peak.position_2
      _nef_peak.position_uncertainty_2
      _nef_peak.position_3
      _nef_peak.position_uncertainty_3
      _nef_peak.height
      _nef_peak.height_uncertainty
      _nef_peak.volume
      _nef_peak.volume_uncertainty
      _nef_peak.ccpn_comment

     1   1   A   2   MET   H   A   3   ARG   H     A   4   GLN   N   8.731   .   8.723   .   115.265   .   .   .   5.5   0.0   'MAP    403'
     2   2   .   .   .     .   .   .   .     .     .   .   .     .   8.731   .   4.61    .   115.275   .   .   .   5.5   0.0   .
     3   3   A   5   THR   H   A   6   MET   HA2   A   7   LEU   N   8.732   .   4.192   .   115.254   .   .   .   5.5   0.0   'MAP    404'
     4   3   A   5   THR   H   A   6   MET   HA3   A   7   LEU   N   8.732   .   4.192   .   115.254   .   .   .   5.5   0.0   'MAP    405'

   stop_

save_
""".replace(
    NOQA_E501, ""
)


def test_basic():

    data_sequence = read_test_data("basic_sequence.nef", __file__)
    peaks_path = path_in_test_data(__file__, "basic.peaks")

    result = run_and_report(app, [peaks_path], input=data_sequence)

    loop = isolate_frame(result.stdout, "nef_nmr_spectrum_xeasy_basic")

    assert_lines_match(EXPECTED, str(loop))
