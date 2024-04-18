import typer
from pytest import fixture

from nef_pipelines.lib.test_lib import (
    NOQA_E501,
    assert_lines_match,
    isolate_loop,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.unassign import unassign

EXIT_ERROR = 1

app = typer.Typer()
app.command()(unassign)

EXPECTED_BASIC_SHIFT_LIST = """
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.value_uncertainty
    _nef_chemical_shift.element
    _nef_chemical_shift.isotope_number

    @-     @1     .    C     174.078751  .               C  13
    @-     @1     .    H       8.507345  0.0031493880    H   1
    @-     @1-1   .    C     175.947447  0.08720577414   C  13
    @-     @1-1   .    CA     56.689055  0.0499432144    C  13
    @-     @2     .    C      17.078751  .               C  13
    @-     @2     .    H      18.507345  0.0031493880    H   1
    @-     @2     .    N      23.365410  0.1052522259    N  15
    @-     @2-1   .    C      75.947447  0.08720577414   C  13
    @-     @2-1   .    CA      6.689055  0.0499432144    C  13
    @-     @2-1   .    CB      1.543048  0.1003766534    C  13
    @-     @3     .    C       7.090786  .               C  13
    @-     @3     .    N      12.714456  0.1199761464    N  15
    @-     @3-1   .    C      78.121295  0.3397487528    C  13
    @-     @3-1   .    CB      6.570846  0.0514681685    C  13
    @-     @4     .    H      88.111256  0.0019229051    H   1
    @-     @4     .    N     112.453575  0.0925289285    N  15
    @-     @4-1   .    C     167.261980  0.0133395288    C  13
    @-     @4-1   .    CB    116.427729  0.1141368283    C  13
stop_
"""

EXPECTED_BASIC_SPECTRUM = """
loop_                                          # noqa: E501
    _nef_peak.index
    _nef_peak.peak_id
    _nef_peak.volume
    _nef_peak.volume_uncertainty
    _nef_peak.height
    _nef_peak.height_uncertainty
    _nef_peak.position_1
    _nef_peak.position_uncertainty_1
    _nef_peak.position_2
    _nef_peak.position_uncertainty_2
    _nef_peak.position_3
    _nef_peak.position_uncertainty_3
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

    1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   @-   @5   .   HE1   @-   @4   .   HN   @-   @5   .   N
    2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .    .    .   .     .    .    .   .    .    .    .   .
    3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   @-   @3   .   HE1   @-   @4   .   HA   .    .    .   .

stop_
""".replace(
    NOQA_E501, ""
)


@fixture
def INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN():
    return read_test_data("ubiquitin_short_unassign_single_chain.nef", __file__)


# noinspection PyUnusedLocal
def test_unassign_basic(INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN):

    result = run_and_report(app, [], input=INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN)

    loop = isolate_loop(
        result.stdout, "nef_chemical_shift_list_default", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_BASIC_SHIFT_LIST, loop)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_simnoe", "nef_peak")
    assert_lines_match(EXPECTED_BASIC_SPECTRUM, loop)


EXPECTED_FULL_SHIFT_LIST = """
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.value_uncertainty
        _nef_chemical_shift.element
        _nef_chemical_shift.isotope_number

        @-     @1     .     .    174.078751  .               C  13
        @-     @1     .     .      8.507345  0.0031493880    H   1
        @-     @1-1   .     .    175.947447  0.08720577414   C  13
        @-     @1-1   .     .     56.689055  0.0499432144    C  13
        @-     @2     .     .     17.078751  .               C  13
        @-     @2     .     .     18.507345  0.0031493880    H   1
        @-     @2     .     .     23.365410  0.1052522259    N  15
        @-     @2-1   .     .     75.947447  0.08720577414   C  13
        @-     @2-1   .     .      6.689055  0.0499432144    C  13
        @-     @2-1   .     .      1.543048  0.1003766534    C  13
        @-     @3     .     .      7.090786  .               C  13
        @-     @3     .     .     12.714456  0.1199761464    N  15
        @-     @3-1   .     .     78.121295  0.3397487528    C  13
        @-     @3-1   .     .      6.570846  0.0514681685    C  13
        @-     @4     .     .     88.111256  0.0019229051    H   1
        @-     @4     .     .    112.453575  0.0925289285    N  15
        @-     @4-1   .     .    167.261980  0.0133395288    C  13
        @-     @4-1   .     .    116.427729  0.1141368283    C  13
    stop_
    """

EXPECTED_FULL_SPECTRUM = """
    loop_                                          # noqa: E501
        _nef_peak.index
        _nef_peak.peak_id
        _nef_peak.volume
        _nef_peak.volume_uncertainty
        _nef_peak.height
        _nef_peak.height_uncertainty
        _nef_peak.position_1
        _nef_peak.position_uncertainty_1
        _nef_peak.position_2
        _nef_peak.position_uncertainty_2
        _nef_peak.position_3
        _nef_peak.position_uncertainty_3
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

        1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   @-   @5   .   .     @-   @4   .   .     @-   @5   .   .
        2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .    .    .   .     .    .    .   .     .    .    .   .
        3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   @-   @3   .   .     @-   @4   .   .     .    .    .   .

    stop_
""".replace(
    NOQA_E501, ""
)


def test_unassign_all(INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN):

    result = run_and_report(
        app, ["--targets", "all"], input=INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN
    )

    loop = isolate_loop(
        result.stdout, "nef_chemical_shift_list_default", "nef_chemical_shift"
    )
    assert_lines_match(loop, EXPECTED_FULL_SHIFT_LIST)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_simnoe", "nef_peak")
    assert_lines_match(EXPECTED_FULL_SPECTRUM, loop)


EXPECTED_UNUSED_SHIFT_LIST = """
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.value_uncertainty
        _nef_chemical_shift.element
        _nef_chemical_shift.isotope_number

        .     .     .     .    174.078751  .               C  13
        .     .     .     .      8.507345  0.0031493880    H   1
        .     .     .     .    175.947447  0.08720577414   C  13
        .     .     .     .     56.689055  0.0499432144    C  13
        .     .     .     .     17.078751  .               C  13
        .     .     .     .     18.507345  0.0031493880    H   1
        .     .     .     .     23.365410  0.1052522259    N  15
        .     .     .     .     75.947447  0.08720577414   C  13
        .     .     .     .      6.689055  0.0499432144    C  13
        .     .     .     .      1.543048  0.1003766534    C  13
        .     .     .     .      7.090786  .               C  13
        .     .     .     .     12.714456  0.1199761464    N  15
        .     .     .     .     78.121295  0.3397487528    C  13
        .     .     .     .      6.570846  0.0514681685    C  13
        .     .     .     .     88.111256  0.0019229051    H   1
        .     .     .     .    112.453575  0.0925289285    N  15
        .     .     .     .    167.261980  0.0133395288    C  13
        .     .     .     .    116.427729  0.1141368283    C  13
    stop_
    """

EXPECTED_UNUSED_SPECTRUM = """
    loop_                                          # noqa: E501
        _nef_peak.index
        _nef_peak.peak_id
        _nef_peak.volume
        _nef_peak.volume_uncertainty
        _nef_peak.height
        _nef_peak.height_uncertainty
        _nef_peak.position_1
        _nef_peak.position_uncertainty_1
        _nef_peak.position_2
        _nef_peak.position_uncertainty_2
        _nef_peak.position_3
        _nef_peak.position_uncertainty_3
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

        1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   .   .   .   .   .   .   .   .   .   .   .   .
        2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .   .   .   .   .   .   .   .   .   .   .   .
        3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   .   .   .   .   .   .   .   .   .   .   .   .

    stop_
""".replace(
    NOQA_E501, ""
)


def test_unassign_complete(INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN):

    result = run_and_report(
        app,
        ["--targets", "all", "--sequence-mode", "unused"],
        input=INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN,
    )

    loop = isolate_loop(
        result.stdout, "nef_chemical_shift_list_default", "nef_chemical_shift"
    )
    assert_lines_match(loop, EXPECTED_UNUSED_SHIFT_LIST)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_simnoe", "nef_peak")
    assert_lines_match(EXPECTED_UNUSED_SPECTRUM, loop)


EXPECTED_ORDERED_SHIFT_LIST = """
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.value_uncertainty
        _nef_chemical_shift.element
        _nef_chemical_shift.isotope_number

        @-     @1     .    C     174.078751  .               C  13
        @-     @1     .    H       8.507345  0.0031493880    H   1
        @-     @1-1   .    C     175.947447  0.08720577414   C  13
        @-     @1-1   .    CA     56.689055  0.0499432144    C  13
        @-     @2     .    C      17.078751  .               C  13
        @-     @2     .    H      18.507345  0.0031493880    H   1
        @-     @2     .    N      23.365410  0.1052522259    N  15
        @-     @2-1   .    C      75.947447  0.08720577414   C  13
        @-     @2-1   .    CA      6.689055  0.0499432144    C  13
        @-     @2-1   .    CB      1.543048  0.1003766534    C  13
        @-     @4     .    C       7.090786  .               C  13
        @-     @4     .    N      12.714456  0.1199761464    N  15
        @-     @4-1   .    C      78.121295  0.3397487528    C  13
        @-     @4-1   .    CB      6.570846  0.0514681685    C  13
        @-     @5     .    H      88.111256  0.0019229051    H   1
        @-     @5     .    N     112.453575  0.0925289285    N  15
        @-     @5-1   .    C     167.261980  0.0133395288    C  13
        @-     @5-1   .    CB    116.427729  0.1141368283    C  13
    stop_
    """

EXPECTED_ORDERED_SPECTRUM = """
    loop_                                               # noqa: E501
        _nef_peak.index
        _nef_peak.peak_id
        _nef_peak.volume
        _nef_peak.volume_uncertainty
        _nef_peak.height
        _nef_peak.height_uncertainty
        _nef_peak.position_1
        _nef_peak.position_uncertainty_1
        _nef_peak.position_2
        _nef_peak.position_uncertainty_2
        _nef_peak.position_3
        _nef_peak.position_uncertainty_3
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

        1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   @-   @3   .   HE1   @-   @5   .   HN   @-   @3   .   N
        2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .    .    .   .     .    .    .   .    .    .    .   .
        3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   @-   @4   .   HE1   @-   @5   .   HA   .    .    .   .

    stop_
""".replace(
    NOQA_E501, ""
)


def test_unassign_ordered(INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN):

    result = run_and_report(
        app,
        ["--sequence-mode", "ordered"],
        input=INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN,
    )

    loop = isolate_loop(
        result.stdout, "nef_chemical_shift_list_default", "nef_chemical_shift"
    )
    assert_lines_match(loop, EXPECTED_ORDERED_SHIFT_LIST)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_simnoe", "nef_peak")
    assert_lines_match(EXPECTED_ORDERED_SPECTRUM, loop)


EXPECTED_PRESERVED_SHIFT_LIST = """
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.value_uncertainty
        _nef_chemical_shift.element
        _nef_chemical_shift.isotope_number

        @-     @PR_1     .    C     174.078751  .               C  13
        @-     @PR_1     .    H       8.507345  0.0031493880    H   1
        @-     @PR_1-1   .    C     175.947447  0.08720577414   C  13
        @-     @PR_1-1   .    CA     56.689055  0.0499432144    C  13
        @-     @PR_2     .    C      17.078751  .               C  13
        @-     @PR_2     .    H      18.507345  0.0031493880    H   1
        @-     @PR_2     .    N      23.365410  0.1052522259    N  15
        @-     @PR_2-1   .    C      75.947447  0.08720577414   C  13
        @-     @PR_2-1   .    CA      6.689055  0.0499432144    C  13
        @-     @PR_2-1   .    CB      1.543048  0.1003766534    C  13
        @-     @2     .    C       7.090786  .               C  13
        @-     @2     .    N      12.714456  0.1199761464    N  15
        @-     @2-1   .    C      78.121295  0.3397487528    C  13
        @-     @2-1   .    CB      6.570846  0.0514681685    C  13
        @-     @3     .    H      88.111256  0.0019229051    H   1
        @-     @3     .    N     112.453575  0.0925289285    N  15
        @-     @3-1   .    C     167.261980  0.0133395288    C  13
        @-     @3-1   .    CB    116.427729  0.1141368283    C  13
    stop_
    """

EXPECTED_PRESERVED_SPECTRUM = """
    loop_                                          # noqa: E501
        _nef_peak.index
        _nef_peak.peak_id
        _nef_peak.volume
        _nef_peak.volume_uncertainty
        _nef_peak.height
        _nef_peak.height_uncertainty
        _nef_peak.position_1
        _nef_peak.position_uncertainty_1
        _nef_peak.position_2
        _nef_peak.position_uncertainty_2
        _nef_peak.position_3
        _nef_peak.position_uncertainty_3
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

        1   0   0.38    .   0.38    .   10.405   .   8.796   .   132.49   .   @-   @1   .   HE1   @-   @3   .   HN   @-   @1   .   N
        2   1   1.298   .   1.298   .   10.408   .   7.139   .   132.49   .   .    .    .   .     .    .    .   .    .    .    .   .
        3   3   0.319   .   0.319   .   10.408   .   5.542   .   132.49   .   @-   @2   .   HE1   @-   @3   .   HA   .    .    .   .

    stop_
""".replace(
    NOQA_E501, ""
)


def test_unassign_preserve(INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN):
    result = run_and_report(
        app,
        ["--sequence-mode", "preserve"],
        input=INPUT_UBI_SHORT_UNASSIGNED_SINGLE_CHAIN,
    )

    loop = isolate_loop(
        result.stdout, "nef_chemical_shift_list_default", "nef_chemical_shift"
    )
    assert_lines_match(loop, EXPECTED_PRESERVED_SHIFT_LIST)

    loop = isolate_loop(result.stdout, "nef_nmr_spectrum_simnoe", "nef_peak")
    assert_lines_match(EXPECTED_PRESERVED_SPECTRUM, loop)
