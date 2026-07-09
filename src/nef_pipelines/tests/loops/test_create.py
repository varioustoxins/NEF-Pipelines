import pytest
import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.frames.create import create as frames_create
from nef_pipelines.tools.loops.create import create

EXIT_ERROR = 1

app = typer.Typer()
app.command()(create)

frames_app = typer.Typer()
frames_app.command()(frames_create)


def _make_entry_with_frame(category: str, name: str) -> str:
    result = run_and_report(frames_app, [category, name])
    return result.stdout


def test_create_empty_loop():
    EXPECTED_SHIFT_LOOP = """\
        loop_
           _nef_chemical_shift.chain_code
           _nef_chemical_shift.sequence_code
           _nef_chemical_shift.residue_name
           _nef_chemical_shift.atom_name
           _nef_chemical_shift.value

        stop_
    """

    nef_input = _make_entry_with_frame("nef_chemical_shift_list", "myshifts")

    result = run_and_report(
        app,
        [
            "nef_chemical_shift_list_myshifts.nef_chemical_shift:chain_code,sequence_code,residue_name,atom_name,value"
        ],
        input=nef_input,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_create_no_columns_adds_placeholder_and_warns():
    EXPECTED_PLACEHOLDER_WARNING = (
        "WARNING: no columns specified for 'nef_chemical_shift_list_myshifts.nef_chemical_shift'; "
        + "adding placeholder column 'place_holder'"
    )
    EXPECTED_PLACEHOLDER_LOOP = """\
        loop_
           _nef_chemical_shift.place_holder

        stop_
    """

    nef_input = _make_entry_with_frame("nef_chemical_shift_list", "myshifts")

    result = run_and_report(
        app,
        ["nef_chemical_shift_list_myshifts.nef_chemical_shift"],
        input=nef_input,
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_PLACEHOLDER_WARNING, result.stderr)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_PLACEHOLDER_LOOP, loop_text)


ERROR_CASES = [
    (
        "loop_already_exists",
        ["nef_chemical_shift_list_1.nef_chemical_shift:chain_code"],
        """\
            ERROR [in: create]: 1 loop already exist:

            loop 'nef_chemical_shift' already exists with columns: index, chain_code, sequence_code, """
        + """residue_name, atom_name, value, value_uncertainty

            exiting...
        """,
    ),
    (
        "no_frame_match",
        ["NONEXISTENT.nef_chemical_shift:chain_code"],
        """\
            ERROR [in: create]: no frames matched by NONEXISTENT.nef_chemical_shift:chain_code

            exiting...
        """,
    ),
    (
        "selector_without_loop_name",
        ["nef_chemical_shift_list_1"],
        """\
            ERROR [in: create]: frame and loop name must be separated by '.' in \
            'nef_chemical_shift_list_1'

            exiting...
        """,
    ),
]


@pytest.mark.parametrize(
    "test_id, args, expected_error", ERROR_CASES, ids=lambda x: x[0]
)
def test_create_errors(test_id, args, expected_error):
    """Test various error conditions in loop creation."""
    nef_input = read_test_data("simple_shifts.nef", __file__)

    result = run_and_report(
        app,
        args,
        input=nef_input,
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(expected_error, result.stdout)


def test_create_with_force_replaces_existing_loop():
    """--force allows replacing an existing loop with warning."""
    EXPECTED_WARNING_REPLACING_LOOP = (
        "WARNING: replacing existing loop 'nef_chemical_shift' with columns: index, chain_code, "
        + "sequence_code, residue_name, atom_name, value, value_uncertainty"
    )
    EXPECTED_LOOP_AFTER_FORCE_REPLACE = """\
        loop_
           _nef_chemical_shift.new_column

          A

        stop_
    """

    nef_input = read_test_data("simple_shifts.nef", __file__)

    result = run_and_report(
        app,
        ["--force", "nef_chemical_shift_list_1.nef_chemical_shift:new_column=A"],
        input=nef_input,
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_WARNING_REPLACING_LOOP, result.stderr)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_1", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_LOOP_AFTER_FORCE_REPLACE, loop_text)


def test_create_invalid_selector_errors():
    """Invalid selector syntax should produce clear error."""
    EXPECTED_ERROR_INVALID_SELECTOR = """\
        ERROR [in: create]: invalid selector syntax in 'invalid:::selector:chain_code'

        exiting..."""

    nef_input = _make_entry_with_frame("nef_chemical_shift_list", "myshifts")

    result = run_and_report(
        app,
        ["invalid:::selector:chain_code"],
        input=nef_input,
        expected_exit_code=EXIT_ERROR,
    )

    assert_lines_match(EXPECTED_ERROR_INVALID_SELECTOR, result.stdout)
