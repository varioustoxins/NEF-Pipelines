import pytest
import typer
from pynmrstar import Entry

from nef_pipelines.lib.structures import FrameLoopAndTagSelectors
from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.columns_structures import (
    NEFColumnsReorderDuplicateColumnsException,
)
from nef_pipelines.tools.columns.reorder import pipe, reorder

EXIT_ERROR = 1

app = typer.Typer()
app.command()(reorder)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

# Shared by multiple tests
EXPECTED_ATOM_FIRST = """\
    loop_
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.value
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name

      N   123.22   A   2   GLN
      H   8.90     A   2   GLN

    stop_
"""


def test_rearrange_custom_order_with_star():
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "atom_name",
            "value",
            "*",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_ATOM_FIRST, loop_text)


def test_rearrange_star_only_preserves_order():
    EXPECTED_UNCHANGED = """\
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

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "*",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_UNCHANGED, loop_text)


def test_rearrange_alphabetical_policy():
    EXPECTED_ALPHABETICAL = """\
    loop_
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.value

      N   A   GLN   2   123.22
      H   A   GLN   2   8.90

    stop_
    """

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--policy",
            "alphabetical",
            "--selector",
            "myshifts.chemical_shift",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_ALPHABETICAL, loop_text)


def test_rearrange_unknown_column_errors():
    EXPECTED_ERROR_UNKNOWN_COLUMN = (
        "ERROR [in: reorder]: columns not found in loop nef_chemical_shift: nonexistent; "
        + "available columns: chain_code, sequence_code, residue_name, atom_name, value [entry 'test']"
        + "\n\n"
        + "exiting...\n"
    )

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "nonexistent",
            "*",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
        merge_stderr=False,
    )

    # Errors go to stderr via exit_error
    assert_lines_match(EXPECTED_ERROR_UNKNOWN_COLUMN, result.stderr)


def test_reorder_without_selector_syntax():
    """Test using frame.loop:col1,col2 syntax without --selector"""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "myshifts.chemical_shift:atom_name,value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    # Should have atom_name, value first, then rest (implicit *)
    assert_lines_match(EXPECTED_ATOM_FIRST, loop_text)


def test_reorder_implicit_star():
    """Test that * is implicitly added at end if not present"""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "atom_name",
            "value",  # No explicit *
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    # Should have atom_name, value first, then rest (implicit *)
    assert_lines_match(EXPECTED_ATOM_FIRST, loop_text)


def test_cli_warns_on_duplicate_columns():
    """Test that CLI warns and deduplicates when columns are repeated"""
    EXPECTED_WARNING = "WARNING: Ignoring subsequent duplicate column order requests: 'atom_name' is repeated\n"

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "atom_name",
            "value",
            "atom_name",  # Duplicate
            "*",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )

    # Should have warned to stderr
    assert result.stderr == EXPECTED_WARNING

    # Result should be correct (duplicates removed)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_ATOM_FIRST, loop_text)


def test_cli_warns_on_duplicate_star():
    """Test that CLI warns and deduplicates when * is repeated"""
    EXPECTED_WARNING = "WARNING: Ignoring subsequent duplicate column order requests: '*' is repeated\n"

    EXPECTED_ATOM_THEN_REST = """\
    loop_
       _nef_chemical_shift.atom_name
       _nef_chemical_shift.chain_code
       _nef_chemical_shift.sequence_code
       _nef_chemical_shift.residue_name
       _nef_chemical_shift.value

      N   A   2   GLN   123.22
      H   A   2   GLN   8.90

    stop_
    """

    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "atom_name",
            "*",
            "value",
            "*",  # Duplicate * - will be removed, leaving: atom_name, *, value
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )

    # Should have warned to stderr
    assert result.stderr == EXPECTED_WARNING

    # After dedup: ["atom_name", "*", "value"]
    # * expands to all remaining (chain_code, sequence_code, residue_name)
    # So order is: atom_name, chain_code, sequence_code, residue_name, value
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_ATOM_THEN_REST, loop_text)


def test_pipe_errors_on_duplicate_columns():
    """Test that calling pipe() directly with duplicates raises NEFColumnsReorderDuplicateColumnsException"""
    entry = Entry.from_string(NEF_WITH_SHIFT_LOOP)

    # Call pipe() with duplicate columns
    frame_loop_tags = FrameLoopAndTagSelectors(
        frame_name="nef_chemical_shift_list_myshifts",
        loop_name="nef_chemical_shift",
        loop_tags=["atom_name", "value", "atom_name"],  # Duplicate
    )

    with pytest.raises(
        NEFColumnsReorderDuplicateColumnsException, match="duplicate columns.*atom_name"
    ):
        pipe(entry, frame_loop_tags)


def test_pipe_errors_on_duplicate_star():
    """Test that calling pipe() directly with duplicate * raises NEFColumnsReorderDuplicateColumnsException"""
    entry = Entry.from_string(NEF_WITH_SHIFT_LOOP)

    # Call pipe() with duplicate *
    frame_loop_tags = FrameLoopAndTagSelectors(
        frame_name="nef_chemical_shift_list_myshifts",
        loop_name="nef_chemical_shift",
        loop_tags=["atom_name", "*", "value", "*"],  # Duplicate *
    )

    with pytest.raises(
        NEFColumnsReorderDuplicateColumnsException, match="duplicate columns.*\\*"
    ):
        pipe(entry, frame_loop_tags)


def test_pipe_implicit_star_prevents_data_loss():
    """Test that calling pipe() directly without * doesn't delete columns"""
    from pynmrstar import Entry

    from nef_pipelines.lib.structures import FrameLoopAndTagSelectors
    from nef_pipelines.tools.columns.reorder import pipe

    entry = Entry.from_string(NEF_WITH_SHIFT_LOOP)

    # Call pipe() directly without * in loop_tags
    frame_loop_tags = FrameLoopAndTagSelectors(
        frame_name="nef_chemical_shift_list_myshifts",
        loop_name="nef_chemical_shift",
        loop_tags=["atom_name", "value"],  # * - should be auto-added at th ened
    )

    result_entry = pipe(entry, frame_loop_tags)
    loop_text = isolate_loop(
        str(result_entry), "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )

    # All columns should still be present (implicit * added)
    assert_lines_match(EXPECTED_ATOM_FIRST, loop_text)
