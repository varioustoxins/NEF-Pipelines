"""Tests for shifts offset command with isotope-based syntax."""

import pytest
import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.shifts.offset import offset

EXIT_ERROR = 1

app = typer.Typer()
app.command()(offset)


def test_offset_element_type_matching():
    """Test element-type matching: C+1.0 affects all carbon atoms."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "C+1.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    175.0   .   C   13
      A   1   ALA   CA   51.0    .   C   13
      A   1   ALA   CB   41.0    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    120.0   .   N   15
      A   2   GLY   C    174.0   .   C   13
      A   2   GLY   CA   46.0    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    110.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_isotope_specific_matching():
    """Test isotope-specific matching: 13C+0.5 affects only 13C atoms."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "13C+0.5"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    174.5   .   C   13
      A   1   ALA   CA   50.5    .   C   13
      A   1   ALA   CB   40.5    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    120.0   .   N   15
      A   2   GLY   C    173.5   .   C   13
      A   2   GLY   CA   45.5    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    110.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_accumulation_behavior():
    """Test element-type and isotope-specific specs accumulate."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "C+1.0,13C+2.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    177.0   .   C   13
      A   1   ALA   CA   53.0    .   C   13
      A   1   ALA   CB   43.0    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    120.0   .   N   15
      A   2   GLY   C    176.0   .   C   13
      A   2   GLY   CA   48.0    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    110.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_multiple_isotopes():
    """Test multiple isotope-specific offsets in one command."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "13C+0.5,15N-0.3,1H+0.1"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    174.5   .   C   13
      A   1   ALA   CA   50.5    .   C   13
      A   1   ALA   CB   40.5    .   C   13
      A   1   ALA   H    8.6     .   H   1
      A   1   ALA   N    119.7   .   N   15
      A   2   GLY   C    173.5   .   C   13
      A   2   GLY   CA   45.5    .   C   13
      A   2   GLY   H    8.1     .   H   1
      A   2   GLY   N    109.7   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_space_separated_specs():
    """Test multiple specs as separate arguments (space-separated)."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "13C+0.5", "15N-0.3"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    174.5   .   C   13
      A   1   ALA   CA   50.5    .   C   13
      A   1   ALA   CB   40.5    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    119.7   .   N   15
      A   2   GLY   C    173.5   .   C   13
      A   2   GLY   CA   45.5    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    109.7   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_wildcard_patterns():
    """Test wildcard patterns: HA* matches HA, HA2, HA3 but not H."""
    test_file = path_in_test_data(__file__, "wildcard_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "HA*+1.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_wildcards", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   H     8.5     .   H   1
      A   1   ALA   HA    5.2     .   H   1
      A   1   ALA   N     120.0   .   N   15
      A   2   GLY   H     8.0     .   H   1
      A   2   GLY   HA2   4.9     .   H   1
      A   2   GLY   HA3   4.8     .   H   1
      A   2   GLY   N     110.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_negative_values():
    """Test negative offset values."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "N-10.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    174.0   .   C   13
      A   1   ALA   CA   50.0    .   C   13
      A   1   ALA   CB   40.0    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    110.0   .   N   15
      A   2   GLY   C    173.0   .   C   13
      A   2   GLY   CA   45.0    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    100.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


TEST_CASES_ERROR_HANDLING = [
    (
        "missing-plus-minus",
        ["C1.0"],
        "must be atom_pattern+value or atom_pattern-value",
    ),
    ("missing-value", ["C+"], "is not a number"),
    ("non-numeric-value", ["C+abc"], "is not a number"),
    ("missing-pattern", ["+1.0"], "must be atom_pattern+value or atom_pattern-value"),
]


@pytest.mark.parametrize(
    "test_id, spec, expected_error", TEST_CASES_ERROR_HANDLING, ids=lambda x: x[0]
)
def test_offset_error_cases(test_id, spec, expected_error):
    """Test error handling for invalid offset specs."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(
        app, ["--in", test_file] + spec, expected_exit_code=EXIT_ERROR
    )

    assert expected_error in result.stdout


def test_offset_no_specs_passthrough():
    """Test warning and passthrough when no offset specs provided."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, ""], merge_stderr=False)

    # File should pass through unchanged
    entry = Entry.from_string(result.stdout)
    frame = entry.get_saveframe_by_name("nef_chemical_shift_list_test")
    loop = frame.get_loop("nef_chemical_shift")

    # Check first carbon value is unchanged (174.0)
    c_value = float(loop.data[0][4])
    assert c_value == 174.0

    EXPECTED_WARNING = (
        "WARNING: no offset specs provided - file will pass through unchanged"
    )
    assert EXPECTED_WARNING in result.stderr


def test_offset_mixed_element_and_isotope():
    """Test realistic scenario with both element-type and isotope-specific offsets accumulating."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(
        app, ["--in", test_file, "C+0.07,13C+0.05,15N-0.44,1H+0.02"]
    )

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    174.12   .   C   13
      A   1   ALA   CA   50.12    .   C   13
      A   1   ALA   CB   40.12    .   C   13
      A   1   ALA   H    8.52     .   H   1
      A   1   ALA   N    119.56   .   N   15
      A   2   GLY   C    173.12   .   C   13
      A   2   GLY   CA   45.12    .   C   13
      A   2   GLY   H    8.02     .   H   1
      A   2   GLY   N    109.56   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_duplicate_patterns_accumulate():
    """Test that duplicate patterns accumulate and trigger a warning."""
    test_file = path_in_test_data(__file__, "simple_shifts.nef")

    result = run_and_report(app, ["--in", test_file, "C+1.0,C+2.0"], merge_stderr=False)

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_test", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    177.0   .   C   13
      A   1   ALA   CA   53.0    .   C   13
      A   1   ALA   CB   43.0    .   C   13
      A   1   ALA   H    8.5     .   H   1
      A   1   ALA   N    120.0   .   N   15
      A   2   GLY   C    176.0   .   C   13
      A   2   GLY   CA   48.0    .   C   13
      A   2   GLY   H    8.0     .   H   1
      A   2   GLY   N    110.0   .   N   15

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)

    EXPECTED_WARNING = "WARNING: duplicate pattern 'C' - offsets will be accumulated"
    assert EXPECTED_WARNING in result.stderr


def test_offset_element_pattern_no_isotope_column():
    """Test element extraction from atom name when element column missing."""
    test_file = path_in_test_data(__file__, "no_isotope_column.nef")

    result = run_and_report(app, ["--in", test_file, "C+1.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_no_isotope", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element

      A   1   ALA   C    175.0   .   C
      A   1   ALA   CA   51.0    .   C
      A   1   ALA   N    120.0   .   N

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_fallback_isotope_pattern_no_column():
    """Test isotope-specific pattern falls back to element matching when isotope column missing."""
    test_file = path_in_test_data(__file__, "no_isotope_column.nef")

    result = run_and_report(app, ["--in", test_file, "13C+1.0"], merge_stderr=False)

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_no_isotope", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element

      A   1   ALA   C    175.0   .   C
      A   1   ALA   CA   51.0    .   C
      A   1   ALA   N    120.0   .   N

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)

    EXPECTED_WARNING = (
        "WARNING: frame 'nef_chemical_shift_list_no_isotope': isotope_number column missing - "
        + "isotope-specific patterns will not match"
    )
    assert EXPECTED_WARNING in result.stderr


def test_offset_isotope_only_atom_names():
    """Test offsetting when atom names are just element symbols (C, N, H) using isotope codes."""
    test_file = path_in_test_data(__file__, "isotope_only.nef")

    result = run_and_report(app, ["--in", test_file, "13C+5.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_isotope", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    179.0   .   C   13
      A   1   ALA   C    185.0   .   C   13
      A   1   ALA   N    120.0   .   N   15
      A   1   ALA   H    8.5     .   H   1

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)


def test_offset_element_extraction_no_element_column():
    """Test element extraction from atom names when element column missing."""
    test_file = path_in_test_data(__file__, "no_element_column.nef")

    result = run_and_report(app, ["--in", test_file, "C+2.0"], merge_stderr=False)

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_no_element", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty

      A   1   ALA   C    176.0   .
      A   1   ALA   CA   52.0    .
      A   1   ALA   N    120.0   .

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)

    EXPECTED_WARNING = (
        "WARNING: frame 'nef_chemical_shift_list_no_element': element column missing - "
        + "extracting elements from atom names"
    )
    assert EXPECTED_WARNING in result.stderr


def test_offset_element_pattern_with_isotope_atoms():
    """Test element-type pattern (C) matches all carbons regardless of specific isotope."""
    test_file = path_in_test_data(__file__, "isotope_only.nef")

    result = run_and_report(app, ["--in", test_file, "C+10.0"])

    loop_str = isolate_loop(
        result.stdout, "nef_chemical_shift_list_isotope", "nef_chemical_shift"
    )

    EXPECTED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty
       _nef_chemical_shift.element
       _nef_chemical_shift.isotope_number

      A   1   ALA   C    184.0   .   C   13
      A   1   ALA   C    190.0   .   C   13
      A   1   ALA   N    120.0   .   N   15
      A   1   ALA   H    8.5     .   H   1

    stop_
    """

    assert_lines_match(EXPECTED, loop_str)
