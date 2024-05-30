import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.simulate.peaks import peaks

runner = CliRunner()
app = typer.Typer()
app.command()(peaks)

EXPECTED = """ # noqa: E501
save_nef_nmr_spectrum_synthetic_N_HSQC
   _nef_nmr_spectrum.sf_category                nef_nmr_spectrum
   _nef_nmr_spectrum.sf_framecode               nef_nmr_spectrum_synthetic_N_HSQC
   _nef_nmr_spectrum.num_dimensions             2
   _nef_nmr_spectrum.chemical_shift_list        .
   _nef_nmr_spectrum.experiment_classification  H[N]
   _nef_nmr_spectrum.experiment_type            '15N HSQC/HMQC'

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

     1   ppm   15N   60.833    24.487   125.828   none   true   false
     2   ppm   1H    600.123   0.606    8.535     none   true   true

   stop_

   loop_
      _nef_spectrum_dimension_transfer.dimension_1
      _nef_spectrum_dimension_transfer.dimension_2
      _nef_spectrum_dimension_transfer.transfer_type
      _nef_spectrum_dimension_transfer.is_indirect

     1   2   onebond   false

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
      _nef_peak.position_1
      _nef_peak.position_uncertainty_1
      _nef_peak.position_2
      _nef_peak.position_uncertainty_2
      _nef_peak.height
      _nef_peak.height_uncertainty
      _nef_peak.volume
      _nef_peak.volume_uncertainty

     0   0   '#18'   @19   .     N   '#18'   @19   .     H   123.3654109   0.1052522259   8.507345563   0.003149388014   1000000   .   1000000   .
     1   1   @-      @9    .     N   @-      @9    .     H   124.7144569   0.1199761464   7.956588347   0.0027175082     1000000   .   1000000   .
     2   2   A       10    Ala   N   A       10    Ala   H   102.4535755   0.0925289285   8.11125646    0.0019229051     1000000   .   1000000   .

   stop_

save_
""".replace(
    NOQA_E501, ""
)


INPUT_UBI_SHORT_NEF = read_test_data("ubiquitin_short.nef", __file__)


# noinspection PyUnusedLocal
def test_ubi_short():

    result = run_and_report(app, [], input=INPUT_UBI_SHORT_NEF)

    new_peaks_frame = isolate_frame(result.stdout, "nef_nmr_spectrum_synthetic_N_HSQC")
    assert_lines_match(EXPECTED, new_peaks_frame)


def test_ubi_short_different_frame_name():
    result = run_and_report(
        app, ["--name-template", "wibble_{spectrum}"], input=INPUT_UBI_SHORT_NEF
    )

    isolate_frame(result.stdout, "nef_nmr_spectrum_wibble_N_HSQC")


def test_ubi_short_different_spectrometer_frequency():
    result = run_and_report(
        app, ["--spectrometer-frequency", "800"], input=INPUT_UBI_SHORT_NEF
    )

    EXPECTED_800 = EXPECTED.replace("60.833", "81.095")
    EXPECTED_800 = EXPECTED_800.replace("600.123", "800.000")
    new_peaks_frame = isolate_frame(result.stdout, "nef_nmr_spectrum_synthetic_N_HSQC")
    assert_lines_match(EXPECTED_800, new_peaks_frame)


EXPECTED_HNCA = """ # noqa: E501
save_nef_nmr_spectrum_synthetic_HNCA
   _nef_nmr_spectrum.sf_category                nef_nmr_spectrum
   _nef_nmr_spectrum.sf_framecode               nef_nmr_spectrum_synthetic_HNCA
   _nef_nmr_spectrum.num_dimensions             3
   _nef_nmr_spectrum.chemical_shift_list        .
   _nef_nmr_spectrum.experiment_classification  H[N[CA]]
   _nef_nmr_spectrum.experiment_type            HNCA

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

     1   ppm   13C   150.933   9.523    61.581    none   true   false
     2   ppm   15N   60.833    24.487   125.828   none   true   false
     3   ppm   1H    600.123   0.606    8.535     none   true   true

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

     0   0   '#18'   @19     .     CA   '#18'   @19   .     N   '#18'   @19   .     H   55.19626104   .              123.3654109   0.1052522259   8.507345563   0.003149388014   1000000   .   1000000   .
     1   1   '#18'   @19-1   .     CA   '#18'   @19   .     N   '#18'   @19   .     H   56.6890552    0.0499432144   123.3654109   0.1052522259   8.507345563   0.003149388014   1000000   .   1000000   .
     2   2   @-      @9      .     CA   @-      @9    .     N   @-      @9    .     H   57.45044906   .              124.7144569   0.1199761464   7.956588347   0.0027175082     1000000   .   1000000   .
     3   3   @-      @9-1    .     CA   @-      @9    .     N   @-      @9    .     H   61.14832291   0.0266869088   124.7144569   0.1199761464   7.956588347   0.0027175082     1000000   .   1000000   .
     4   4   A       9       Ala   CA   A       10    Ala   N   A       10    Ala   H   52.49098528   0              102.4535755   0.0925289285   8.11125646    0.0019229051     1000000   .   1000000   .

   stop_

save_

""".replace(
    NOQA_E501, ""
)


def test_ubi_short_triple():

    result = run_and_report(app, ["HNCA"], input=INPUT_UBI_SHORT_NEF)

    print(result.stdout)
    new_peaks_frame = isolate_frame(result.stdout, "nef_nmr_spectrum_synthetic_HNCA")
    assert_lines_match(EXPECTED_HNCA, new_peaks_frame)
