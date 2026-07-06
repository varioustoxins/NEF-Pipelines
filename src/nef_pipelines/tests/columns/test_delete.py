import pytest
import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.delete import delete

EXIT_SUCCESS = 0

EXIT_ERROR = 1

app = typer.Typer()
app.command()(delete)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

EXPECTED_AFTER_DELETE_ATOM_NAME = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.value

      A   2   GLN   123.22
      A   2   GLN   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_NAME_WILDCARD = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.value

      A   2   123.22
      A   2   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_CHAIN_AND_ATOM = """\
    loop_
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.value

      2   GLN   123.22
      2   GLN   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_CODE_WILDCARD = """\
    loop_
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      GLN   N   123.22
      GLN   H   8.90

    stop_
"""

EXPECTED_AFTER_DELETE_RESIDUE_NAME = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   N   123.22
      A   2   H   8.90

    stop_
"""

# Standard deletion tests: NEF_WITH_SHIFT_LOOP input, check loop output
STANDARD_DELETE_CASES = [
    (
        "single_column",
        ["--in", "-", "myshifts.chemical_shift:atom_name"],
        EXPECTED_AFTER_DELETE_ATOM_NAME,
    ),
    (
        "prefixed_wildcard",
        ["--in", "-", "myshifts.chemical_shift:*_name"],
        EXPECTED_AFTER_DELETE_NAME_WILDCARD,
    ),
    (
        "comma_separated",
        ["--in", "-", "myshifts.chemical_shift:chain_code,atom_name"],
        EXPECTED_AFTER_DELETE_CHAIN_AND_ATOM,
    ),
    (
        "multiple_selector_args",
        [
            "--in",
            "-",
            "myshifts.chemical_shift:chain_code",
            "myshifts.chemical_shift:atom_name",
        ],
        EXPECTED_AFTER_DELETE_CHAIN_AND_ATOM,
    ),
    (
        "wildcard_pattern",
        ["--in", "-", "myshifts.chemical_shift:*_code"],
        EXPECTED_AFTER_DELETE_CODE_WILDCARD,
    ),
    (
        "suffixed_wildcard",
        ["--in", "-", "myshifts.chemical_shift:residue_*"],
        EXPECTED_AFTER_DELETE_RESIDUE_NAME,
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

          A   2   GLN   N   123.22   kept
          A   2   GLN   H   8.90     kept

        stop_
    """

    nef_with_special = NEF_WITH_SHIFT_LOOP.replace(
        "     A  2  GLN  N  123.22",
        "     A  2  GLN  N  123.22  delete_me  kept",
    )
    nef_with_special = nef_with_special.replace(
        "     A  2  GLN  H  8.90",
        "     A  2  GLN  H  8.90  delete_me  kept",
    )
    nef_with_special = nef_with_special.replace(
        "      _nef_chemical_shift.value",
        """
            _nef_chemical_shift.value\n      _nef_chemical_shift.test*column
            _nef_chemical_shift.test_other_column
        """,
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
        "WARNING: no columns matching ['nonexistent'] found in loop nef_chemical_shift",
        EXIT_SUCCESS,
        True,
    ),
    (
        "invalid_selector_shows_ordinal",
        ["--in", "-", "myshifts.chemical_shift:value", "invalid:::syntax"],
        """\
            ERROR [in: delete]: invalid selector syntax for the 2nd selector: invalid:::syntax

            exiting...""",
        EXIT_ERROR,
        False,
    ),
]


@pytest.mark.parametrize(
    "test_id, args, expected, exit_code, check_stderr",
    WARNING_ERROR_CASES,
    ids=[c[0] for c in WARNING_ERROR_CASES],
)
def test_delete_warnings_and_errors(test_id, args, expected, exit_code, check_stderr):
    """Test warnings and errors in column deletion."""
    result = run_and_report(
        app,
        args,
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=exit_code,
        merge_stderr=not check_stderr,
    )
    output = result.stderr if check_stderr else result.stdout
    assert_lines_match(expected, output)
