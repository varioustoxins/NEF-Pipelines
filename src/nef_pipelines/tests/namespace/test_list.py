import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.namespace.list import list_namespaces as list_cmd

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
Namespace    Level         Frame                      Category             Loop            Tag                Program       Use  # noqa: E501
-----------  ------------  -------------------------  -------------------  --------------  -----------------  ------------  ---------------------
nef          frame         nef_molecular_system       molecular_system                                        NEF Standard  Data Exchange
nef           frame-tag    nef_molecular_system       molecular_system                     sf_category        NEF Standard  Data Exchange
nef           frame-tag    nef_molecular_system       molecular_system                     sf_framecode       NEF Standard  Data Exchange
nef           loop         nef_molecular_system       molecular_system     sequence                           NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        index              NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        chain_code         NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        sequence_code      NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        residue_name       NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        linking            NEF Standard  Data Exchange
nef          frame         nef_chemical_shift_list_1  chemical_shift_list                                     NEF Standard  Data Exchange
nef           frame-tag    nef_chemical_shift_list_1  chemical_shift_list                  sf_category        NEF Standard  Data Exchange
nef           frame-tag    nef_chemical_shift_list_1  chemical_shift_list                  sf_framecode       NEF Standard  Data Exchange
nef           loop         nef_chemical_shift_list_1  chemical_shift_list  chemical_shift                     NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  index              NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  chain_code         NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  sequence_code      NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  residue_name       NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  atom_name          NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  value              NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  value_uncertainty  NEF Standard  Data Exchange
custom       frame         custom_data_frame          data_frame                                              ?             ?
custom        frame-tag    custom_data_frame          data_frame                           sf_category        ?             ?
custom        frame-tag    custom_data_frame          data_frame                           sf_framecode       ?             ?
custom        frame-tag    custom_data_frame          data_frame                           note               ?             ?
custom        frame-tag    custom_data_frame          data_frame                           info               ?             ?
custom        loop         custom_data_frame          data_frame           values                             ?             ?
custom         column-tag  custom_data_frame          data_frame           values          index              ?             ?
custom         column-tag  custom_data_frame          data_frame           values          chain_code         ?             ?
custom         column-tag  custom_data_frame          data_frame           values          sequence_code      ?             ?
custom         column-tag  custom_data_frame          data_frame           values          data               ?             ?
custom         column-tag  custom_data_frame          data_frame           values          comment            ?             ?
test         frame         test_experiment            experiment                                              ?             ?
test          frame-tag    test_experiment            experiment                           sf_category        ?             ?
test          frame-tag    test_experiment            experiment                           sf_framecode       ?             ?
test          frame-tag    test_experiment            experiment                           description        ?             ?
test          frame-tag    test_experiment            experiment                           author             ?             ?
test          loop         test_experiment            experiment           measurements                       ?             ?
test           column-tag  test_experiment            experiment           measurements    index              ?             ?
test           column-tag  test_experiment            experiment           measurements    chain_code         ?             ?
test           column-tag  test_experiment            experiment           measurements    sequence_code      ?             ?
test           column-tag  test_experiment            experiment           measurements    value              ?             ?
test           column-tag  test_experiment            experiment           measurements    error              ?             ?
aria         frame         aria_distance_restraints   distance_restraints                                     Aria          Structure calculation
aria          frame-tag    aria_distance_restraints   distance_restraints                  sf_category        Aria          Structure calculation
aria          frame-tag    aria_distance_restraints   distance_restraints                  sf_framecode       Aria          Structure calculation
aria          loop         aria_distance_restraints   distance_restraints  restraint                          Aria          Structure calculation
aria           column-tag  aria_distance_restraints   distance_restraints  restraint       index              Aria          Structure calculation
aria           column-tag  aria_distance_restraints   distance_restraints  restraint       atom_1             Aria          Structure calculation
aria           column-tag  aria_distance_restraints   distance_restraints  restraint       atom_2             Aria          Structure calculation
aria           column-tag  aria_distance_restraints   distance_restraints  restraint       distance           Aria          Structure calculation
aria           column-tag  aria_distance_restraints   distance_restraints  restraint       error              Aria          Structure calculation
""".replace(
    "# noqa: E501", ""
)

EXPECTED_VERBOSE_NEF_ONLY = """\
Namespace    Level         Frame                      Category             Loop            Tag                Program       Use # noqa: E501
-----------  ------------  -------------------------  -------------------  --------------  -----------------  ------------  -------------
nef          frame         nef_molecular_system       molecular_system                                        NEF Standard  Data Exchange
nef           frame-tag    nef_molecular_system       molecular_system                     sf_category        NEF Standard  Data Exchange
nef           frame-tag    nef_molecular_system       molecular_system                     sf_framecode       NEF Standard  Data Exchange
nef           loop         nef_molecular_system       molecular_system     sequence                           NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        index              NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        chain_code         NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        sequence_code      NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        residue_name       NEF Standard  Data Exchange
nef            column-tag  nef_molecular_system       molecular_system     sequence        linking            NEF Standard  Data Exchange
nef          frame         nef_chemical_shift_list_1  chemical_shift_list                                     NEF Standard  Data Exchange
nef           frame-tag    nef_chemical_shift_list_1  chemical_shift_list                  sf_category        NEF Standard  Data Exchange
nef           frame-tag    nef_chemical_shift_list_1  chemical_shift_list                  sf_framecode       NEF Standard  Data Exchange
nef           loop         nef_chemical_shift_list_1  chemical_shift_list  chemical_shift                     NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  index              NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  chain_code         NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  sequence_code      NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  residue_name       NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  atom_name          NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  value              NEF Standard  Data Exchange
nef            column-tag  nef_chemical_shift_list_1  chemical_shift_list  chemical_shift  value_uncertainty  NEF Standard  Data Exchange
""".replace(
    "# noqa: E501", ""
)


def test_list_basic_mode_all_namespaces():
    """Test basic mode lists all namespaces as ordered set."""

    result = run_and_report(app, [], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ALL_NAMESPACES, result.stdout)


def test_list_basic_mode_include_specific():
    """Test basic mode with explicit include selectors."""

    result = run_and_report(app, ["-", "+nef", "+custom"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_NEF_AND_CUSTOM, result.stdout)


def test_list_basic_mode_exclude():
    """Test basic mode with exclude selector."""

    result = run_and_report(app, ["--", "+", "-nef"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_mixed_include_exclude():
    """Test basic mode with mixed include and exclude."""

    result = run_and_report(
        app, ["--", "-", "+nef", "+custom", "-nef"], input=INPUT_NAMESPACE_TEST
    )

    assert_lines_match(EXPECTED_ONLY_CUSTOM, result.stdout)


def test_list_basic_mode_wildcard():
    """Test basic mode with wildcard pattern."""

    result = run_and_report(app, ["-", "+n*"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ONLY_NEF, result.stdout)


def test_list_basic_mode_wildcard_exclude():
    """Test basic mode with wildcard exclude pattern."""

    result = run_and_report(app, ["--", "-n*"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_invert():
    """Test basic mode with --no-initial-selection flag."""

    result = run_and_report(
        app,
        ["--no-initial-selection", "aria", "custom", "test"],
        input=INPUT_NAMESPACE_TEST,
    )

    assert_lines_match(EXPECTED_ARIA_CUSTOM_AND_TEST, result.stdout)


def test_list_basic_mode_comma_separated():
    """Test basic mode with comma-separated selectors."""

    result = run_and_report(app, ["--", "-", "nef,custom"], input=INPUT_NAMESPACE_TEST)

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

    result = run_and_report(app, ["--verbose", "-", "+nef"], input=INPUT_NAMESPACE_TEST)

    assert_lines_match(EXPECTED_VERBOSE_NEF_ONLY, result.stdout)


def test_list_empty_result():
    """Test listing with selector that matches nothing."""

    result = run_and_report(app, ["-", "+nonexistent"], input=INPUT_NAMESPACE_TEST)

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
    """Test escaped \\+ for literal + in namespace."""

    result = run_and_report(
        app, ["--use-escapes", "-", r"\+test"], input=INPUT_NAMESPACE_TEST
    )

    assert_lines_match(EXPECTED_EMPTY, result.stdout)


def test_list_escaped_minus_prefix():
    """Test escaped \\- for literal - in namespace."""

    result = run_and_report(
        app, ["--use-escapes", "--", "-", r"\-test"], input=INPUT_NAMESPACE_TEST
    )

    assert_lines_match(EXPECTED_EMPTY, result.stdout)
