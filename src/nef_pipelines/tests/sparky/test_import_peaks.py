import typer

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_frame,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.sparky.importers.peaks import peaks

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


     1   1   A   16   DG   H3'   A   16   DG   H8    4.905   .   8.01    .   .   .   7150000.0    .
     2   2   A   16   DG   H4'   A   16   DG   H8    4.439   .   8.013   .   .   .   5420000.0    .
     3   3   A   17   DT   H6    A   16   DG   H8    7.205   .   8.004   .   .   .   1680000.0    .
     4   4   A   17   DT   H7    A   16   DG   H8    1.459   .   8.008   .   .   .   20900000.0   .
     5   5   A   17   DT   H2"   A   17   DT   H1'   2.509   .   5.84    .   .   .   46800000.0   .

stop_
"""

DATA_SEQUENCE = read_test_data("sparky_manual_basic_sequence.nef", __file__)


def test_basic():

    path = path_in_test_data(__file__, "sparky_manual_basic.peaks")

    result = run_and_report(app, ["--molecule-type", "dna", path], input=DATA_SEQUENCE)

    loop = isolate_loop(
        result.stdout, "nef_nmr_spectrum_sparky_sparky_manual_basic", "nef_peak"
    )

    assert_lines_match(EXPECTED, str(loop))


def test_basic_no_sequence():

    path = path_in_test_data(__file__, "sparky_manual_basic.peaks")

    result = run_and_report(app, ["--molecule-type", "dna", path])

    loop = isolate_loop(
        result.stdout, "nef_nmr_spectrum_sparky_sparky_manual_basic", "nef_peak"
    )

    assert_lines_match(EXPECTED, str(loop))


def test_basic_no_sequence_requires_sequence():

    path = path_in_test_data(__file__, "sparky_manual_full_no_sequence.peaks")

    result = run_and_report(app, [path], input=DATA_SEQUENCE)

    loop = isolate_loop(
        result.stdout,
        "nef_nmr_spectrum_sparky_sparky_manual_full_no_sequence",
        "nef_peak",
    )

    assert_lines_match(EXPECTED, str(loop))


def test_full():

    path = path_in_test_data(__file__, "sparky_manual_full.peaks")

    result = run_and_report(app, ["--molecule-type", "dna", path])

    loop = isolate_loop(
        result.stdout, "nef_nmr_spectrum_sparky_sparky_manual_full", "nef_peak"
    )

    assert_lines_match(EXPECTED, str(loop))


EXPECTED_FULL_COMMENT = """ # noqa: E501
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
  _nef_peak.ccpn_comment

     1   1   A   16   DG   H3'   A   16   DG   H8    4.905   .   8.01    .   .   .   7150000.0    .   'this is a comment'
     2   2   A   16   DG   H4'   A   16   DG   H8    4.439   .   8.013   .   .   .   5420000.0    .   .
     3   3   A   17   DT   H6    A   16   DG   H8    7.205   .   8.004   .   .   .   1680000.0    .   'so is this as well'
     4   4   A   17   DT   H7    A   16   DG   H8    1.459   .   8.008   .   .   .   20900000.0   .   .
     5   5   A   17   DT   H2"   A   17   DT   H1'   2.509   .   5.84    .   .   .   46800000.0   .   .
stop_
""".replace(
    NOQA_E501, ""
)


def test_full_comment():

    path = path_in_test_data(__file__, "sparky_manual_full_comment.peaks")

    result = run_and_report(app, ["--molecule-type", "dna", path])

    loop = isolate_loop(
        result.stdout, "nef_nmr_spectrum_sparky_sparky_manual_full_comment", "nef_peak"
    )

    assert_lines_match(EXPECTED_FULL_COMMENT, str(loop))


def test_missing_isotopes():
    path = path_in_test_data(__file__, "CONCACX.txt")

    result = run_and_report(
        app,
        [
            path,
        ],
        expected_exit_code=1,
    )

    assert "the isotopes are not defined" in result.stdout
    assert "[1, 2, 3, 4]" in result.stdout


EXPECTED_SPECTRUM_CONCACX = open(
    path_in_test_data(__file__, "CONCACX_expected_spectrum.txt")
).read()


def test_give_isotopes_when_bad():
    path = path_in_test_data(__file__, "CONCACX.txt")

    result = run_and_report(
        app,
        [
            "--nuclei",
            "13C,15N,13C,13C",
            path,
        ],
    )

    spectrum_frame = isolate_frame(result.stdout, "nef_nmr_spectrum_sparky_CONCACX")

    assert_lines_match(EXPECTED_SPECTRUM_CONCACX, spectrum_frame)
