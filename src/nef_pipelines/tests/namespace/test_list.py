import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.namespace.list import list as list_cmd

runner = CliRunner()
app = typer.Typer()
app.command()(list_cmd)

INPUT_NAMESPACE_TEST = read_test_data("namespace_test.nef", __file__)

# Expected complete outputs for basic mode
EXPECTED_ALL_NAMESPACES = """\
aria
custom
nef
test
"""

EXPECTED_NEF_AND_CUSTOM = """\
custom
nef
"""

EXPECTED_ARIA_CUSTOM_AND_TEST = """\
aria
custom
test
"""

EXPECTED_ONLY_NEF = """\
nef
"""

EXPECTED_ONLY_CUSTOM = """\
custom
"""

EXPECTED_EMPTY = ""

# Expected strings for checking specific content in verbose mode or NEF output
EXPECTED_TAG_MYNEF_SEQUENCE = "_mynef_sequence"
EXPECTED_TAG_NEF_CHEMICAL_SHIFT = "_nef_chemical_shift"
EXPECTED_FRAME_CUSTOM_DATA = "custom_data_frame"

# Expected complete outputs for verbose mode
EXPECTED_VERBOSE_ALL = """\
Namespace    Level    Category             Frame                      Loop            Program       Use  # noqa: E501
-----------  -------  -------------------  -------------------------  --------------  ------------  ---------------------
aria         frame    distance_restraints  aria_distance_restraints                   Aria          Structure calculation
aria         loop     distance_restraints  aria_distance_restraints   restraint       Aria          Structure calculation
custom       frame    data_frame           custom_data_frame                          ?             ?
custom       loop     data_frame           custom_data_frame          values          ?             ?
nef          frame    molecular_system     nef_molecular_system                       NEF Standard  Data Exchange
nef          loop     molecular_system     nef_molecular_system       sequence        NEF Standard  Data Exchange
nef          frame    chemical_shift_list  nef_chemical_shift_list_1                  NEF Standard  Data Exchange
nef          loop     chemical_shift_list  nef_chemical_shift_list_1  chemical_shift  NEF Standard  Data Exchange
test         frame    experiment           test_experiment                            ?             ?
test         loop     experiment           test_experiment            measurements    ?             ?
""".replace(
    "# noqa: E501", ""
)

EXPECTED_VERBOSE_NEF_ONLY = """\
Namespace    Level    Category             Frame                      Loop            Program       Use
-----------  -------  -------------------  -------------------------  --------------  ------------  -------------
nef          frame    molecular_system     nef_molecular_system                       NEF Standard  Data Exchange
nef          loop     molecular_system     nef_molecular_system       sequence        NEF Standard  Data Exchange
nef          frame    chemical_shift_list  nef_chemical_shift_list_1                  NEF Standard  Data Exchange
nef          loop     chemical_shift_list  nef_chemical_shift_list_1  chemical_shift  NEF Standard  Data Exchange
"""


def test_list_basic_mode_all_namespaces():
    """Test basic mode lists all namespaces as ordered set."""

    result = run_and_report(app, [], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ALL_NAMESPACES, result.stdout)


def test_list_basic_mode_include_specific():
    """Test basic mode with explicit include selectors."""

    result = run_and_report(app, ["+nef", "+custom"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_NEF_AND_CUSTOM, result.stdout)


def test_list_basic_mode_exclude():
    """Test basic mode with exclude selector."""

    result = run_and_report(app, ["--", "-nef"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_mixed_include_exclude():
    """Test basic mode with mixed include and exclude."""

    result = run_and_report(
        app, ["--", "+nef", "+custom", "-nef"], input=INPUT_NAMESPACE_TEST
    )

    assert_lines_match(EXPECTED_ONLY_CUSTOM, result.stdout)


def test_list_basic_mode_wildcard():
    """Test basic mode with wildcard pattern."""

    result = run_and_report(app, ["+n*"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ONLY_NEF, result.stdout)


def test_list_basic_mode_wildcard_exclude():
    """Test basic mode with wildcard exclude pattern."""

    result = run_and_report(app, ["--", "-n*"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_invert():
    """Test basic mode with --invert flag."""

    result = run_and_report(app, ["--invert", "nef"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_comma_separated():
    """Test basic mode with comma-separated selectors."""

    result = run_and_report(app, ["nef,custom"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_NEF_AND_CUSTOM, result.stdout)


def test_list_verbose_mode():
    """Test verbose mode shows detailed table with all namespaces."""

    result = run_and_report(app, ["--verbose"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_ALL, result.stdout)


def test_list_verbose_mode_shows_registered_namespace_info():
    """Test verbose mode shows program and use info for registered namespaces."""

    result = run_and_report(app, ["--verbose"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_ALL, result.stdout)


def test_list_verbose_mode_shows_unknown_for_unregistered():
    """Test verbose mode shows [Unknown] for unregistered namespaces."""

    result = run_and_report(app, ["--verbose"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_ALL, result.stdout)


def test_list_verbose_mode_shows_levels():
    """Test verbose mode shows different level types (frame and loop)."""

    result = run_and_report(app, ["--verbose"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_ALL, result.stdout)


def test_list_verbose_mode_filtered():
    """Test verbose mode with namespace filtering shows only nef namespace."""

    result = run_and_report(app, ["--verbose", "+nef"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_NEF_ONLY, result.stdout)


def test_list_empty_result():
    """Test listing with selector that matches nothing."""

    result = run_and_report(app, ["+nonexistent"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_EMPTY, result.stdout)


def test_list_with_frame_selection():
    """Test listing with frame selection."""

    result = run_and_report(
        app,
        ["--frames", "nef_molecular_system"],
        input=INPUT_NAMESPACE_TEST,
    )

    assert_lines_match(EXPECTED_ONLY_NEF, result.stdout)


def test_list_escaped_plus_prefix():
    """Test escaped ++ for literal + in namespace."""

    result = run_and_report(app, ["++test"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_EMPTY, result.stdout)


def test_list_escaped_minus_prefix():
    """Test escaped -- for literal - in namespace."""

    result = run_and_report(app, ["--", "--test"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_EMPTY, result.stdout)
