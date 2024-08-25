import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.mars.importers.peaks import peaks

app = typer.Typer()
app.command()(peaks)

NOQUA_E501 = "# noqa E501"
EXPECTED_HNCA = """
# noqa E501
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
    _nef_peak.ccpn_figure_of_merit


    1   1   A   1   MET   CA   A   2   GLN   N   A   2   GLN   H   54.608   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    2   2   A   2   GLN   CA   A   2   GLN   N   A   2   GLN   H   55.215   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    3   3   A   2   GLN   CA   A   3   ILE   N   A   3   ILE   H   55.057   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
    4   4   A   3   ILE   CA   A   3   ILE   N   A   3   ILE   H   59.616   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
    5   5   A   3   ILE   CA   A   4   PHE   N   A   4   PHE   H   59.599   .   118.73    .   8.614   .   .   .   .   .      merit=H   1.0
    6   6   A   4   PHE   CA   A   4   PHE   N   A   4   PHE   H   55.138   .   118.73    .   8.614   .   .   .   .   .      merit=H   1.0
    7   7   A   4   PHE   CA   A   5   VAL   N   A   5   VAL   H   55.142   .   121.424   .   9.307   .   .   .   .   .      merit=H   1.0
    8   8   A   5   VAL   CA   A   5   VAL   N   A   5   VAL   H   60.412   .   121.424   .   9.307   .   .   .   .   .      merit=H   1.0

stop_
""".replace(
    NOQUA_E501, ""
)

EXPECTED_HNcoCA = """
# noqa E501
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
    _nef_peak.ccpn_figure_of_merit


    1   1   A   1   MET   CA   A   2   GLN   N   A   2   GLN   H   54.608   .   122.899   .   8.907   .   .   .   .   .     merit=M   0.75
    2   2   A   2   GLN   CA   A   3   ILE   N   A   3   ILE   H   55.057   .   115.127   .   8.318   .   .   .   .   .     merit=M   0.75
    3   3   A   3   ILE   CA   A   4   PHE   N   A   4   PHE   H   59.599   .   118.73    .   8.614   .   .   .   .   .     merit=H   1.0
    4   4   A   4   PHE   CA   A   5   VAL   N   A   5   VAL   H   55.142   .   121.424   .   9.307   .   .   .   .   .     merit=H   1.0
stop_
""".replace(
    NOQUA_E501, ""
)


EXPECTED_all = """
# noqa E501
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
    _nef_peak.ccpn_figure_of_merit


    1   1   A   1   MET   CA   A   2   GLN   N   A   2   GLN   H   54.608   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    2   2   A   1   MET   CB   A   2   GLN   N   A   2   GLN   H   33.279   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    3   3   A   2   GLN   CA   A   2   GLN   N   A   2   GLN   H   55.215   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    4   4   A   2   GLN   CB   A   2   GLN   N   A   2   GLN   H   30.606   .   122.899   .   8.907   .   .   .   .   .      merit=M   0.75
    5   5   A   2   GLN   CA   A   3   ILE   N   A   3   ILE   H   55.057   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
    6   6   A   2   GLN   CB   A   3   ILE   N   A   3   ILE   H   30.582   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
    7   7   A   3   ILE   CA   A   3   ILE   N   A   3   ILE   H   59.616   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
    8   8   A   3   ILE   CB   A   3   ILE   N   A   3   ILE   H   42.025   .   115.127   .   8.318   .   .   .   .   .      merit=M   0.75
stop_
""".replace(
    NOQUA_E501, ""
)


def test_import_peaks():

    sequence_stream = read_test_data("ubi_seq.nef", __file__)

    filenames = "sparky_all.out sparky_CA-1.out sparky_CA.out".split()

    paths = [path_in_test_data(__file__, filename) for filename in filenames]
    result = run_and_report(app, paths, input=sequence_stream)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_mars_HNCA", "nef_peak")
    assert_lines_match(EXPECTED_HNCA, loop)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_mars_HNcoCA", "nef_peak")
    assert_lines_match(EXPECTED_HNcoCA, loop)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_mars_sparky_all", "nef_peak")
    assert_lines_match(EXPECTED_all, loop)
