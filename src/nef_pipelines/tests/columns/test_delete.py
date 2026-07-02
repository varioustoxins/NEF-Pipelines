import pytest
import typer

from nef_pipelines.lib.test_lib import assert_lines_match, isolate_loop, run_and_report
from nef_pipelines.tools.columns.delete import delete

EXIT_SUCCESS = 0

EXIT_ERROR = 1

app = typer.Typer()
app.command()(delete)

NEF_WITH_SHIFT_LOOP = """\
data_test

    save_nef_chemical_shift_list_myshifts
       _nef_chemical_shift_list.sf_category  nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode nef_chemical_shift_list_myshifts

       loop_
          _nef_chemical_shift.chain_code
          _nef_chemical_shift.sequence_code
          _nef_chemical_shift.residue_name
          _nef_chemical_shift.atom_name
          _nef_chemical_shift.value
          _nef_chemical_shift.value_uncertainty

         A  2  GLN  N  123.22  0.1
         A  2  GLN  H  8.90    0.05

       stop_

    save_
"""

EXPECTED_AFTER_DELETE_UNCERTAINTY = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_RESIDUE_NAME_AND_UNCERTAINTY = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   N   123.22
      A   2   H   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_VALUE_WILDCARD = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name

      A   2   GLN   N
      A   2   GLN   H

    stop_
"""

EXPECTED_AFTER_DELETE_VALUE_UNCERTAINTY = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   123.22
      A   2   GLN   H   8.90

    stop_
"""

# Standard deletion tests: NEF_WITH_SHIFT_LOOP input, check loop output
STANDARD_DELETE_CASES = [
    (
        "single_column",
        ["--in", "-", "myshifts.chemical_shift:value_uncertainty"],
        EXPECTED_AFTER_DELETE_UNCERTAINTY,
    ),
    (
        "prefixed_wildcard",
        ["--in", "-", "myshifts.chemical_shift:*_uncertainty"],
        EXPECTED_AFTER_DELETE_UNCERTAINTY,
    ),
    (
        "comma_separated",
        ["--in", "-", "myshifts.chemical_shift:residue_name,value_uncertainty"],
        EXPECTED_AFTER_DELETE_RESIDUE_NAME_AND_UNCERTAINTY,
    ),
    (
        "multiple_selector_args",
        [
            "--in",
            "-",
            "myshifts.chemical_shift:residue_name",
            "myshifts.chemical_shift:value_uncertainty",
        ],
        EXPECTED_AFTER_DELETE_RESIDUE_NAME_AND_UNCERTAINTY,
    ),
    (
        "wildcard_pattern",
        ["--in", "-", "myshifts.chemical_shift:value"],
        EXPECTED_AFTER_DELETE_VALUE_WILDCARD,
    ),
    (
        "suffixed_wildcard",
        ["--in", "-", "myshifts.chemical_shift:value_*"],
        EXPECTED_AFTER_DELETE_VALUE_UNCERTAINTY,
    ),
]


@pytest.mark.parametrize(
    "test_id, args, expected", STANDARD_DELETE_CASES, ids=lambda x: x[0]
)
def test_delete_columns_standard(test_id, args, expected):
    """Test column deletion with standard NEF input and loop output validation."""
    result = run_and_report(app, args, input=NEF_WITH_SHIFT_LOOP)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


def test_delete_with_escaped_wildcard():
    """Test escaped wildcard matches literal asterisk, not as wildcard pattern."""
    EXPECTED = """\
        loop_
           _nef_chemical_shift.chain_code
           _nef_chemical_shift.sequence_code
           _nef_chemical_shift.residue_name
           _nef_chemical_shift.atom_name
           _nef_chemical_shift.value
           _nef_chemical_shift.test_other_column

          A   2   GLN   N   123.22   0.1
          A   2   GLN   H   8.90     0.05

        stop_
    """

    nef_with_special = NEF_WITH_SHIFT_LOOP.replace(
        "_nef_chemical_shift.value_uncertainty",
        "_nef_chemical_shift.test*column",
    )
    nef_with_special = nef_with_special.replace(
        "   A  2  GLN  N  123.22  0.1",
        "   A  2  GLN  N  123.22  delete_me  0.1",
    )
    nef_with_special = nef_with_special.replace(
        "   A  2  GLN  H  8.90    0.05",
        "   A  2  GLN  H  8.90    delete_me  0.05",
    )
    nef_with_special = nef_with_special.replace(
        "_nef_chemical_shift.test*column",
        "_nef_chemical_shift.test*column\n          _nef_chemical_shift.test_other_column",
    )

    result = run_and_report(
        app,
        ["--in", "-", r"myshifts.chemical_shift:test\*column"],
        input=nef_with_special,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED, loop_text)


# Warning and error tests: check stdout directly
WARNING_ERROR_CASES = [
    (
        "unknown_column_warns",
        ["--in", "-", "myshifts.chemical_shift:nonexistent"],
        "no columns matching ['nonexistent'] found in loop chemical_shift",
        EXIT_SUCCESS,
    ),
    (
        "invalid_selector_shows_ordinal",
        ["--in", "-", "myshifts.chemical_shift:value", "invalid:::syntax"],
        "invalid selector syntax for the 2nd selector: invalid:::syntax",
        EXIT_ERROR,
    ),
]


@pytest.mark.parametrize(
    "test_id, args, expected, exit_code", WARNING_ERROR_CASES, ids=lambda x: x[0]
)
def test_delete_warnings_and_errors(test_id, args, expected, exit_code):
    """Test warnings and errors in column deletion."""
    result = run_and_report(
        app, args, input=NEF_WITH_SHIFT_LOOP, expected_exit_code=exit_code
    )
    assert_lines_match(expected, result.stdout)
