import shutil
import tempfile
from pathlib import Path

import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.csv.importers.loop import loop

EXIT_ERROR = 1

app = typer.Typer()
app.command()(loop)

ENTRY_WITH_SHIFT_FRAME = Path(
    path_in_test_data(__file__, "entry_with_shift_frame.nef")
).read_text()


EXPECTED_SHIFT_LOOP = """\
    loop_
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.value_uncertainty

      A   2   GLN   N   123.22   0.1
      A   2   GLN   H   8.90     0.05
      A   3   ILE   N   115.34   0.1
      A   3   ILE   H   8.32     0.05

    stop_
"""

EXPECTED_ERROR_NOT_FOUND = """\
    ERROR [in: loop]: the frame nef_chemical_shift_list_NONEXISTENT was not found in the entry nef

    you may need to create it first using: nef frames create

    exiting...
"""

EXPECTED_ERROR_TRIPLETS = """\
    ERROR [in: loop]: for the command-line frame policy arguments must be triplets of framecode loop-category and path

    i got 2 argument(s), the last unpaired argument was: nef_chemical_shift

    exiting...
"""

EXPECTED_ERROR_COMMENT_WITHOUT_COMMENT = """\
    ERROR [in: loop]: the comment frame policy requires --comment to be specified
    (the comment character may not be # in all files)

    exiting...
"""


def test_loop_import_command_line_policy():
    csv_path = path_in_test_data(__file__, "shifts_with_chain.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "nef_chemical_shift_list_myshifts",
            "nef_chemical_shift",
            csv_path,
        ],
        input=nef_input,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_missing_frame_errors():
    csv_path = path_in_test_data(__file__, "shifts_with_chain.csv")

    result = run_and_report(
        app,
        [
            "nef_chemical_shift_list_NONEXISTENT",
            "nef_chemical_shift",
            csv_path,
        ],
        expected_exit_code=EXIT_ERROR,
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_ERROR_NOT_FOUND, result.stderr)


def test_loop_import_file_name_policy():

    csv_path = path_in_test_data(__file__, "shifts_with_chain.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    with tempfile.TemporaryDirectory() as tmp_dir:
        dest = (
            Path(tmp_dir) / "nef_chemical_shift_list_myshifts__nef_chemical_shift.csv"
        )
        shutil.copy(csv_path, dest)

        result = run_and_report(
            app,
            ["--in", "-", "--frame-policy", "file-name", str(dest)],
            input=nef_input,
        )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_odd_triplet_args_errors():

    result = run_and_report(
        app,
        ["nef_chemical_shift_list_myshifts", "nef_chemical_shift"],
        expected_exit_code=EXIT_ERROR,
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_ERROR_TRIPLETS, result.stderr)


def test_loop_import_with_comment_filter():
    csv_path = path_in_test_data(__file__, "shifts_with_chain_and_comments.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--comment",
            "#",
            "nef_chemical_shift_list_myshifts",
            "nef_chemical_shift",
            csv_path,
        ],
        input=nef_input,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_header_policy():
    """Test HEADER policy where first line contains framecode,loop_category."""
    csv_path = path_in_test_data(__file__, "shifts_with_header_policy.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    result = run_and_report(
        app,
        ["--in", "-", "--frame-policy", "header", csv_path],
        input=nef_input,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_header_policy_with_skip():
    """Test HEADER policy with --skip: framecode,loop_category comes AFTER skipped rows."""
    csv_path = path_in_test_data(__file__, "shifts_with_header_policy_and_skip.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    result = run_and_report(
        app,
        ["--in", "-", "--frame-policy", "header", "--skip", "1", csv_path],
        input=nef_input,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_comment_policy():
    """Test COMMENT policy where framename: and loop: are in comment lines."""
    csv_path = path_in_test_data(__file__, "shifts_with_comment_policy.csv")
    nef_input = ENTRY_WITH_SHIFT_FRAME

    result = run_and_report(
        app,
        ["--in", "-", "--frame-policy", "comment", "--comment", "#", csv_path],
        input=nef_input,
        merge_stderr=False,
    )

    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SHIFT_LOOP, loop_text)


def test_loop_import_comment_policy_requires_comment():
    """Test that COMMENT policy errors without --comment specified."""
    csv_path = path_in_test_data(__file__, "shifts_with_comment_policy.csv")

    result = run_and_report(
        app,
        ["--frame-policy", "comment", csv_path],
        expected_exit_code=EXIT_ERROR,
        merge_stderr=False,
    )

    assert_lines_match(EXPECTED_ERROR_COMMENT_WITHOUT_COMMENT, result.stderr)


def test_loop_import_with_normalized_headers_warns():
    """Test that column headers with spaces are normalized with a warning."""
    csv_path = path_in_test_data(__file__, "shifts_with_spaces.csv")

    result = run_and_report(
        app,
        [
            "--frame-policy",
            "command-line",
            "nef_chemical_shift_list_myshifts",
            "nef_chemical_shift",
            csv_path,
        ],
        input=ENTRY_WITH_SHIFT_FRAME,
        merge_stderr=False,
    )

    EXPECTED_WARNINGS = """\
        WARNING: normalized column header 'chain code' → 'chain_code'
        WARNING: normalized column header 'sequence code' → 'sequence_code'
        WARNING: normalized column header 'residue name' → 'residue_name'
        WARNING: normalized column header 'atom name' → 'atom_name'
        WARNING: normalized column header 'value uncertainty' → 'value_uncertainty'
    """

    assert_lines_match(EXPECTED_WARNINGS, result.stderr)

    loop_result = isolate_loop(
        result.stdout,
        "nef_chemical_shift_list_myshifts",
        "nef_chemical_shift",
    )

    EXPECTED_LOOP = """\
        loop_
           _nef_chemical_shift.chain_code
           _nef_chemical_shift.sequence_code
           _nef_chemical_shift.residue_name
           _nef_chemical_shift.atom_name
           _nef_chemical_shift.value
           _nef_chemical_shift.value_uncertainty

          A   2   GLN   N   123.22   0.1
          A   2   GLN   H   8.90     0.05

        stop_
    """

    assert_lines_match(EXPECTED_LOOP, loop_result)
