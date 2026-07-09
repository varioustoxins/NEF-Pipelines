import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.replace import replace

EXIT_ERROR = 1

app = typer.Typer()
app.command()(replace)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

EXPECTED_REPLACED = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   9.99
      A   2   GLN   H   8.88

    stop_
"""

EXPECTED_ERROR_ODD_ARGS = (
    "ERROR [in: replace]: invalid replace format '1 arguments'; expected: "
    + "selector @file:col or col @file:col (must be pairs) [entry 'test']\n"
    + "\n"
    + "exiting..."
)

EXPECTED_PADDED_LOOP = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value

      A   2   GLN   N   9.99
      A   2   GLN   H   .

    stop_
"""


def test_replace_from_csv():
    csv_path = path_in_test_data(__file__, "replace_values.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift:value",
            f"@{csv_path}",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_REPLACED, loop_text)


def test_replace_from_multicolumn_csv_reads_named_column():
    csv_path = path_in_test_data(__file__, "replace_multicolumn.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift:value",
            f"@{csv_path}",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_REPLACED, loop_text)


def test_replace_from_simple_file():
    txt_path = path_in_test_data(__file__, "replace_simple.txt")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--format",
            "simple",
            "myshifts.chemical_shift:value",
            f"@{txt_path}",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_REPLACED, loop_text)


def test_replace_with_explicit_file_column_name():
    csv_path = path_in_test_data(__file__, "replace_custom_column.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift:value",
            f"@{csv_path}:replacement_col",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_REPLACED, loop_text)


def test_replace_odd_args_errors():
    result = run_and_report(
        app,
        ["--in", "-", "myshifts.chemical_shift:value"],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert_lines_match(EXPECTED_ERROR_ODD_ARGS, result.stdout)


def test_replace_row_count_mismatch_warns():
    """Test that row count mismatch produces a warning but succeeds with padding."""
    csv_path = path_in_test_data(__file__, "replace_short.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift:value",
            f"@{csv_path}",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=0,  # Should succeed, not error
        merge_stderr=False,  # Keep stderr separate from stdout
    )

    # Verify complete warning message in stderr - test COMPLETE output
    assert (
        f"WARNING: file {csv_path} has 1 row, loop has 2 rows - filling remaining with '.'\n"
        == result.stderr
    )

    # Verify complete loop structure with padding
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_PADDED_LOOP, loop_text)
