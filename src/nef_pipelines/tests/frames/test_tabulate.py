import pytest
import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.tabulate import tabulate

runner = CliRunner()
app = typer.Typer()
app.command()(tabulate)


EXPECTED_BASIC = """
          nef_sequence
          ------------

      index  chain_code      sequence_code  residue_name    linking
         1            A             10               GLU    start
         2            A             11               TYR    middle
         3            A             12               ALA    middle
         4            A             13               GLN    middle
         5            A             14               PRO    middle
         6            A             15               ARG    middle
         7            A             16               LEU    middle
         8            A             17               ARG    middle
         9            A             18               LEU    middle
        10            A             19               GLY    middle
        11            A             20               PHE    middle
        12            A             21               GLU    middle
        13            A             22               ASP    end

    """

# noinspection PyUnusedLocal


def test_frame_basic():

    path = path_in_test_data(__file__, "tailin_seq_short.nef")

    result = run_and_report(app, ["--in", path])

    assert_lines_match(EXPECTED_BASIC, result.stdout)


def test_frame_selection():

    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(app, ["--in", path, "nef_molecular_system"])

    assert "nef_sequence" in result.stdout
    assert "nef_chemical_shift_list_default" not in result.stdout


def test_frame_and_loop_selection_text():

    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(
        app, ["--in", path, "nef_nmr_Spectrum_simnoe.nef_spectrum_Dimension"]
    )

    assert "nef_molecular_system" not in result.stdout
    assert "nef_spectrum_dimension" in result.stdout
    assert "nef_peak" not in result.stdout


def test_frame_and_loop_selection_index():

    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(app, ["--in", path, "nef_nmr_spectrum_simnoe.3"])

    assert "nef_molecular_system" not in result.stdout
    assert "nef_spectrum_dimension" not in result.stdout
    assert "nef_peak" in result.stdout


def test_frame_and_loop_selection_text_exact():

    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(
        app, ["--in", path, "nef_nmr_spectrum_simnoe.nef_spectrum_dimension", "--exact"]
    )

    assert "nef_molecular_system" not in result.stdout
    assert "nef_spectrum_dimension" in result.stdout
    assert "nef_peak" not in result.stdout


EXPECTED_SPECTRUM_DIMENSIONS_DIM_ONLY = """
    nef_spectrum_dimension
    ----------------------

    dimension-id
               1
               2
               3
    """

EXPECTED_DIMENSION_ID_SPECTRAL_WIDTH = """
    nef_spectrum_dimension
    ----------------------
      dimension-id    spectral-width
                 1          11.0113
                 2          11.06
                 3          81.8927
    """

EXPECTED_EXCLUDE_DIMENSION_ID_SPECTRAL_WIDTH = """
    nef_spectrum_dimension
    ----------------------
      axis-unit    axis-code      spectrometer-frequency    folding    absolute-peak-positions
      ppm          1H                            800.133    circular   true
      ppm          1H                            800.133    circular   true
      ppm          15N                            81.076    circular   true

    """
EXPECTED_DATA_ALL = """  # noqa: E501
    nef_spectrum_dimension
    ----------------------
      dimension-id  axis-unit    axis-code      spectrometer-frequency    spectral-width  folding    absolute-peak-positions
                 1  ppm          1H                            800.133           11.0113  circular   true
                 2  ppm          1H                            800.133           11.06    circular   true
                 3  ppm          15N                            81.076           81.8927  circular   true
    """.replace(
    NOQA_E501, ""
)

EXPECTED_DATA_LOOKUP = {
    "EXPECTED_DATA_EMPTY": "",
    "EXPECTED_SPECTRUM_DIMENSIONS_DIM_ONLY": EXPECTED_SPECTRUM_DIMENSIONS_DIM_ONLY,
    "EXPECTED_DIMENSION_ID_SPECTRAL_WIDTH": EXPECTED_DIMENSION_ID_SPECTRAL_WIDTH,
    "EXPECTED_EXCLUDE_DIMENSION_ID_SPECTRAL_WIDTH": EXPECTED_EXCLUDE_DIMENSION_ID_SPECTRAL_WIDTH,
    "EXPECTED_DATA_ALL": EXPECTED_DATA_ALL,
}


@pytest.mark.parametrize(
    "column_selections,expected_lookup",
    [
        ("-", "EXPECTED_DATA_EMPTY"),
        ("-*", "EXPECTED_DATA_EMPTY"),
        ("-,+dim", "EXPECTED_SPECTRUM_DIMENSIONS_DIM_ONLY"),
        ("-,dimension_id,spectral_width", "EXPECTED_DIMENSION_ID_SPECTRAL_WIDTH"),
        (
            "-dimension_id,-spectral_width",
            "EXPECTED_EXCLUDE_DIMENSION_ID_SPECTRAL_WIDTH",
        ),
        ("+", "EXPECTED_DATA_ALL"),
        ("+dimension_id,+spectral_width", "EXPECTED_DATA_ALL"),
    ],
)
def test_exclude_columns(column_selections, expected_lookup):

    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(
        app,
        [
            "--in",
            path,
            "--abbreviate",
            "--select-columns",
            column_selections,
            "nef_nmr_spectrum_simnoe.nef_spectrum_dimension",
        ],
    )

    assert_lines_match(EXPECTED_DATA_LOOKUP[expected_lookup], result.stdout)


def test_full():
    path = path_in_test_data(__file__, "ubiquitin_short_unassign_single_chain.nef")

    result = run_and_report(
        app, ["--in", path, "nef_nmr_spectrum_simnoe.nef_spectrum_dimension", "--full"]
    )

    assert "value_first_point" in result.stdout


def test_no_header():
    path = path_in_test_data(
        __file__,
        "tailin_seq_short.nef",
    )

    result = run_and_report(app, ["--in", path, "--no-title"])

    assert_lines_match("\n".join(EXPECTED_BASIC.split("\n")[3:]), result.stdout)


EXPECTED_CSV = """
index,chain_code,sequence_code,residue_name,linking
1,A,10,GLU,start
2,A,11,TYR,middle
3,A,12,ALA,middle
4,A,13,GLN,middle
5,A,14,PRO,middle
6,A,15,ARG,middle
7,A,16,LEU,middle
8,A,17,ARG,middle
9,A,18,LEU,middle
10,A,19,GLY,middle
11,A,20,PHE,middle
12,A,21,GLU,middle
13,A,22,ASP,end
"""


def test_csv():
    path = path_in_test_data(
        __file__,
        "tailin_seq_short.nef",
    )

    result = run_and_report(app, ["--in", path, "--no-title", "--format", "csv"])

    assert_lines_match(EXPECTED_CSV, result.stdout)
