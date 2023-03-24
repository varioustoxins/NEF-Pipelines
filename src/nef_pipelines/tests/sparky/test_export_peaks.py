import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.sparky.exporters.peaks import peaks

SHIFTS_SPARKY = "nef_chemical_shift_list_sparky"

app = typer.Typer()
app.command()(peaks)

EXPECTED = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Height  Volume

  PR_36N-H       120.519  6.169        9       1
  PR_66N-H       104.406  6.180       10       2
  PR_65N-H       104.408  6.517       11       3
  PR_67N-H       103.504  7.048       12       4

************************************************************************************

"""


def test_ppm_out_short():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(app, ["--file-name-template", "-"], input=STREAM)

    assert_lines_match(EXPECTED, result.stdout)


EXPECTED_SUPPRESS_ASSIGNMENT = """\
****************************** nef_nmr_spectrum_peaks ******************************

       w1       w2      Height  Volume

  120.519  6.169        9       1
  104.406  6.180       10       2
  104.408  6.517       11       3
  103.504  7.048       12       4
************************************************************************************

"""


def test_ppm_out_short_suppress_assigment():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app,
        ["--file-name-template", "-", "--suppress-column", "assignment"],
        input=STREAM,
    )

    assert_lines_match(EXPECTED_SUPPRESS_ASSIGNMENT, result.stdout)


EXPECTED_NO_HEIGHT = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2        Volume

  PR_36N-H       120.519  6.169          1
  PR_66N-H       104.406  6.180          2
  PR_65N-H       104.408  6.517          3
  PR_67N-H       103.504  7.048          4

************************************************************************************

"""


def test_ppm_out_short_no_height():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--suppress-column", "height"], input=STREAM
    )

    assert_lines_match(EXPECTED_NO_HEIGHT, result.stdout)


EXPECTED_NO_VOLUME = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Height

  PR_36N-H       120.519  6.169        9
  PR_66N-H       104.406  6.180       10
  PR_65N-H       104.408  6.517       11
  PR_67N-H       103.504  7.048       12

************************************************************************************

"""


def test_ppm_out_short_no_volume():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--suppress-column", "volume"], input=STREAM
    )

    assert_lines_match(EXPECTED_NO_VOLUME, result.stdout)


EXPECTED_NO_HEIGHT_OR_VOLUME = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2

  PR_36N-H       120.519  6.169
  PR_66N-H       104.406  6.180
  PR_65N-H       104.408  6.517
  PR_67N-H       103.504  7.048

************************************************************************************

"""


def test_ppm_out_short_no_height_or_volume():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app,
        [
            "--file-name-template",
            "-",
            "--suppress-column",
            "volume",
            "--suppress-column",
            "height",
        ],
        input=STREAM,
    )

    assert_lines_match(EXPECTED_NO_HEIGHT_OR_VOLUME, result.stdout)


def test_ppm_out_short_no_height_or_volume_with_data():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app,
        [
            "--file-name-template",
            "-",
            "--suppress-column",
            "volume,height",
            "--add-data",
        ],
        input=STREAM,
    )

    assert_lines_match(EXPECTED_NO_HEIGHT_OR_VOLUME, result.stdout)


EXPECTED_DIFFERENT_RESIDUES = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment         w1       w2      Height  Volume

PR_67H-PR_68HA   7.856   4.049           3       1
PR_66H-HA        7.406   4.180          10       5

************************************************************************************

"""


def test_ppm_out_short_different_residues():

    STREAM = open(
        path_in_test_data(__file__, "ubi_peaks_short_different_residues.neff")
    ).read()

    result = run_and_report(app, ["--file-name-template", "-"], input=STREAM)

    assert_lines_match(EXPECTED_DIFFERENT_RESIDUES, result.stdout)


EXPECTED_CHAINS = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment         w1       w2      Height  Volume

A.G66H-HA        7.806   4.280          12       7
A.G66H-A.G67HA   7.906   4.380          14       9

************************************************************************************
"""


def test_ppm_out_short_chains():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short_chains.neff")).read()

    result = run_and_report(app, ["--file-name-template", "-"], input=STREAM)

    assert_lines_match(EXPECTED_CHAINS, result.stdout)


EXPECTED_NO_CHAINS = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment         w1       w2      Height  Volume

G66H-HA         7.806    4.280          12       7
G66H-G67HA      7.906    4.380          14       9

************************************************************************************
"""


def test_ppm_out_short_no_chains():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short_chains.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--no-chains"], input=STREAM
    )

    assert_lines_match(EXPECTED_NO_CHAINS, result.stdout)


EXPECTED_WITH_DATA = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Data  Height  Volume

  PR_36N-H       120.519  6.169              9       1
  PR_66N-H       104.406  6.180             10       2
  PR_65N-H       104.408  6.517             11       3
  PR_67N-H       103.504  7.048             12       4

************************************************************************************

"""


def test_ppm_out_short_with_data():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--add-data"], input=STREAM
    )

    assert_lines_match(EXPECTED_WITH_DATA, result.stdout)


EXPECTED_FULL_ASSIGNMENTS = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Height  Volume

  PR_36N-PR_36H  120.519  6.169        9       1
  PR_66N-PR_66H  104.406  6.180       10       2
  PR_65N-PR_65H  104.408  6.517       11       3
  PR_67N-PR_67H  103.504  7.048       12       4

************************************************************************************

"""


def test_ppm_out_short_full_assignments():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--full-assignments"], input=STREAM
    )

    assert_lines_match(EXPECTED_FULL_ASSIGNMENTS, result.stdout)


EXPECTED_NO_ASSIGNMENTS = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1     w2   Height  Volume

       ?-?  120.519  6.169        9       1
       ?-?  104.406  6.180       10       2
       ?-?  104.408  6.517       11       3
       ?-?  103.504  7.048       12       4

************************************************************************************

"""


def test_ppm_out_short_discard_assignments():

    STREAM = open(path_in_test_data(__file__, "ubi_peaks_short.neff")).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--discard-assignments"], input=STREAM
    )

    assert_lines_match(EXPECTED_NO_ASSIGNMENTS, result.stdout)


EXPECTED_WITH_FULL_ASSIGNMENTS = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Height  Volume

  A.A36N-H    120.519  6.169           9       1
  A.G66N-H    104.406  6.180          10       2
  A.L65N-H    104.408  6.517          11       3
  A.V67N-H    103.504  7.048          12       4

************************************************************************************


"""


def test_ppm_out_short_with_full_assignments():

    STREAM = open(
        path_in_test_data(__file__, "peaks_short_with_assignments.neff")
    ).read()

    result = run_and_report(app, ["--file-name-template", "-"], input=STREAM)

    assert_lines_match(EXPECTED_WITH_FULL_ASSIGNMENTS, result.stdout)


EXPECTED_WITH_DIFFERENT_CHAIN_SEPARATOR = """\

****************************** nef_nmr_spectrum_peaks ******************************

Assignment       w1       w2      Height  Volume

  A_A36N-H    120.519  6.169           9       1
  A_G66N-H    104.406  6.180          10       2
  A_L65N-H    104.408  6.517          11       3
  A_V67N-H    103.504  7.048          12       4

************************************************************************************

"""


def test_ppm_out_short_with_different_chain_separator():

    STREAM = open(
        path_in_test_data(__file__, "peaks_short_with_assignments.neff")
    ).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--chain-separator", "_"], input=STREAM
    )

    assert_lines_match(EXPECTED_WITH_DIFFERENT_CHAIN_SEPARATOR, result.stdout)


EXPECTED_3D_m1 = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment                     w1       w2       w3      Height  Volume

  PR_36N-H-CA               120.519  6.169    56.120          9       1
  PR_36N-PR_36H-PR_36CAm1   104.406  6.180    52.670         10       2
  PR_65N-H-CA               104.408  6.517    53.150         11       3
  PR_65N-PR_65H-PR_65CAm1   103.504  7.048    52.130         12       4

************************************************************************************


"""


def test_ppm_out_short_3d_m1():

    STREAM = open(
        path_in_test_data(__file__, "ubi_peaks_short_i_minus_one.neff")
    ).read()

    result = run_and_report(
        app,
        [
            "--file-name-template",
            "-",
        ],
        input=STREAM,
    )

    assert_lines_match(EXPECTED_3D_m1, result.stdout)


EXPECTED_3D_m1_no_negatives = """\
****************************** nef_nmr_spectrum_peaks ******************************

Assignment                      w1      w2       w3     Height  Volume

  PR_36N-H-CA               120.519  6.169   56.120          9       1
  PR_36N-PR_36H-?CA         104.406  6.180   52.670         10       2
  PR_65N-H-CA               104.408  6.517   53.150         11       3
  PR_65N-PR_65H-?CA         103.504  7.048   52.130         12       4

************************************************************************************


"""


def test_ppm_out_short_3d_m1_no_negatives():

    STREAM = open(
        path_in_test_data(__file__, "ubi_peaks_short_i_minus_one.neff")
    ).read()

    result = run_and_report(
        app, ["--file-name-template", "-", "--no-negative-residues"], input=STREAM
    )

    assert_lines_match(EXPECTED_3D_m1_no_negatives, result.stdout)


def test_ppm_out_short_overlapped_chains():

    STREAM = open(
        path_in_test_data(__file__, "ubi_peaks_short_overlapping_chains.neff")
    ).read()

    result = run_and_report(app, ["--no-chains"], input=STREAM, expected_exit_code=1)

    assert "ignore chains" in result.stdout
    assert " A " in result.stdout
    assert " B " in result.stdout
    assert "66" in result.stdout
    assert "36" in result.stdout
