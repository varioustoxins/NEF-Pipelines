import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_frame,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.csv.importers.peaks import peaks

app = typer.Typer()
app.command()(peaks)


# noinspection PyUnusedLocal
def test_short_csv():

    csv_path = path_in_test_data(__file__, "ubi_hsqc_short.csv")

    result = run_and_report(app, [csv_path])

    EXPECTED = """\
        save_nef_nmr_spectrum_peaks
           _nef_nmr_spectrum.sf_category                nef_nmr_spectrum
           _nef_nmr_spectrum.sf_framecode               nef_nmr_spectrum_peaks
           _nef_nmr_spectrum.num_dimensions             2
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

             1   ppm   15N   60.833    8.668   123.614   none   true   false
             2   ppm   1H    600.123   1.078   9.349     none   true   true

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

             1   1   A   2   GLN   N   A   2   GLN   H   123.22   .   8.9    .   .   .   .   .
             2   2   A   3   ILE   N   A   3   ILE   H   115.34   .   8.32   .   .   .   .   .
             3   3   A   4   PHE   N   A   4   PHE   H   118.11   .   8.61   .   .   .   .   .
             4   4   A   5   VAL   N   A   5   VAL   H   121.0    .   9.3    .   .   .   .   .

           stop_

        save_

    """

    result = isolate_frame(result.stdout, "nef_nmr_spectrum_peaks")

    assert_lines_match(EXPECTED, result)
