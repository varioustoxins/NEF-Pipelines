from pathlib import Path

import pytest
import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.insert import insert

EXIT_ERROR = 1

app = typer.Typer()
app.command()(insert)

NEF_WITH_SHIFT_LOOP = read_test_data("nef_with_shift_loop.nef", __file__)

NEF_WITH_EMPTY_FRAME = """\
data_test

    save_nef_chemical_shift_list_myshifts
       _nef_chemical_shift_list.sf_category  nef_chemical_shift_list
       _nef_chemical_shift_list.sf_framecode nef_chemical_shift_list_myshifts

    save_
"""


# --- constants used by test_insert (defined here because parametrize evals at import time) ---

EXPECTED_BEFORE_ATOM = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.new_col
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value

        A   2   GLN   .   N   123.22
        A   2   GLN   .   H   8.90

    stop_
"""

EXPECTED_AFTER_VALUE = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.new_col

        A   2   GLN   N   123.22   .
        A   2   GLN   H   8.90     .

    stop_
"""

EXPECTED_AT_REPLACES_INDEX_THREE = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.new_col
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value

        A   2   .   N   123.22
        A   2   .   H   8.90

    stop_
"""

EXPECTED_INLINE_VALUES = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.new_col

        A   2   GLN   N   123.22   0.1
        A   2   GLN   H   8.90     0.05

    stop_
"""

EXPECTED_APPENDED_WITH_DEFAULT = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.new_col

        A   2   GLN   N   123.22   .
        A   2   GLN   H   8.90     .

    stop_
"""

EXPECTED_UNCERTAINTY_APPENDED = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.uncertainty

        A   2   GLN   N   123.22   0.1
        A   2   GLN   H   8.90     0.05

    stop_
"""

EXPECTED_TWO_COLUMNS_APPENDED = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.flag
        _nef_chemical_shift.uncertainty

        A   2   GLN   N   123.22   ok   0.1
        A   2   GLN   H   8.90     ok   0.05

    stop_
"""

EXPECTED_FORCE_OVERWRITE = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value

        A   2   GLN   N   999.99
        A   2   GLN   H   888.88

    stop_
"""

EXPECTED_SHARED_VALUE_SPEC = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.flag
        _nef_chemical_shift.confidence

        A   2   GLN   N   123.22   ok   ok
        A   2   GLN   H   8.90     ok   ok

    stop_
"""


INSERT_TEST_CASES = [
    (
        "before-anchor",
        ["--selector", "myshifts.chemical_shift", "new_col", "--before", "atom_name"],
        EXPECTED_BEFORE_ATOM,
    ),
    (
        "after-anchor",
        ["--selector", "myshifts.chemical_shift", "new_col", "--after", "value"],
        EXPECTED_AFTER_VALUE,
    ),
    (
        "at-by-index",
        ["--selector", "myshifts.chemical_shift", "new_col", "--at", "3"],
        EXPECTED_AT_REPLACES_INDEX_THREE,
    ),
    (
        "at-by-name",
        ["--selector", "myshifts.chemical_shift", "new_col", "--at", "residue_name"],
        EXPECTED_AT_REPLACES_INDEX_THREE,
    ),
    (
        "inline-values",
        [
            "--selector",
            "myshifts.chemical_shift",
            "new_col=0.1,0.05",
            "--after",
            "value",
        ],
        EXPECTED_INLINE_VALUES,
    ),
    (
        "append-default",
        ["--selector", "myshifts.chemical_shift", "new_col"],
        EXPECTED_APPENDED_WITH_DEFAULT,
    ),
    (
        "append-comma-values",
        ["--selector", "myshifts.chemical_shift", "uncertainty=0.1,0.05"],
        EXPECTED_UNCERTAINTY_APPENDED,
    ),
    (
        "two-columns",
        ["--selector", "myshifts.chemical_shift", "flag=ok,ok", "uncertainty=0.1,0.05"],
        EXPECTED_TWO_COLUMNS_APPENDED,
    ),
    (
        "force-overwrite",
        ["--selector", "myshifts.chemical_shift", "--force", "value=999.99,888.88"],
        EXPECTED_FORCE_OVERWRITE,
    ),
    (
        "shared-value-spec",
        ["--selector", "myshifts.chemical_shift", "flag,confidence=ok*"],
        EXPECTED_SHARED_VALUE_SPEC,
    ),
]


@pytest.mark.parametrize(
    "test_id, args, expected", INSERT_TEST_CASES, ids=lambda x: x[0]
)
def test_insert(test_id, args, expected):
    result = run_and_report(app, ["--in", "-", *args], input=NEF_WITH_SHIFT_LOOP)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


@pytest.mark.parametrize(
    "args, expected_substrings",
    [
        (
            [
                "--selector",
                "myshifts.chemical_shift",
                "new_col",
                "--before",
                "nonexistent",
            ],
            ["nonexistent"],
        ),
        (
            ["--selector", "myshifts.chemical_shift", "value=999.99,888.88"],
            ["already exists"],
        ),
        (
            ["--selector", "myshifts.chemical_shift", "value", "--after", "atom_name"],
            ["already exists"],
        ),
    ],
    ids=["unknown-anchor", "duplicate-without-force", "clone-existing-is-error"],
)
def test_insert_error(args, expected_substrings):
    result = run_and_report(
        app,
        ["--in", "-", *args],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    for s in expected_substrings:
        assert s in result.stdout


EXPECTED_REPEAT_COLUMN = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.flag

        A   2   GLN   N   123.22   yes
        A   2   GLN   H   8.90     yes

    stop_
"""

EXPECTED_RANGE_COLUMN = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.index

        A   2   GLN   N   123.22   1
        A   2   GLN   H   8.90     2

    stop_
"""

EXPECTED_PADDED_COLUMN = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.flag

        A   2   GLN   N   123.22   ok
        A   2   GLN   H   8.90     .

    stop_
"""


@pytest.mark.parametrize(
    "col_spec, expected",
    [
        ("flag=yes*2", EXPECTED_REPEAT_COLUMN),
        ("flag=yes*", EXPECTED_REPEAT_COLUMN),
        ("index=1..2", EXPECTED_RANGE_COLUMN),
        ("index=1..", EXPECTED_RANGE_COLUMN),
        ("flag=ok", EXPECTED_PADDED_COLUMN),
    ],
    ids=["repeat-n", "repeat-fill", "range", "range-from", "padded"],
)
def test_insert_value_spec_variants(col_spec, expected):
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", col_spec],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


def test_insert_auto_creates_loop():
    EXPECTED = """\
        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.value

            A   1.5

        stop_
    """
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.nef_chemical_shift",
            "chain_code=A",
            "value=1.5",
        ],
        input=NEF_WITH_EMPTY_FRAME,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED, loop_text)


# --- comment / skip filter tests (use pre-existing test-data files) ---


@pytest.mark.parametrize(
    "extra_args, csv_name",
    [
        (["--comment", "#"], "values_with_comments.csv"),
        (["--skip", "1"], "values_with_skip.csv"),
    ],
    ids=["comment-filter", "skip-rows"],
)
def test_insert_file_ref_filter(extra_args, csv_name):
    csv_path = path_in_test_data(__file__, csv_name)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            *extra_args,
            f"uncertainty=@{csv_path}:uncertainty",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_UNCERTAINTY_APPENDED, loop_text)


# --- file-ref tests: unique CSV content ---


def test_insert_with_file_values():
    EXPECTED = """\
        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.sequence_code
            _nef_chemical_shift.residue_name
            _nef_chemical_shift.new_col
            _nef_chemical_shift.atom_name
            _nef_chemical_shift.value

            A   2   GLN   0.1    N   123.22
            A   2   GLN   0.05   H   8.90

        stop_
    """
    csv_path = path_in_test_data(__file__, "source_weight.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            f"new_col=@{csv_path}:weight",
            "--before",
            "atom_name",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED, loop_text)


def test_insert_file_ref_infers_col_name_from_left():
    EXPECTED = """\
        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.sequence_code
            _nef_chemical_shift.residue_name
            _nef_chemical_shift.atom_name
            _nef_chemical_shift.value
            _nef_chemical_shift.weight

            A   2   GLN   N   123.22   0.1
            A   2   GLN   H   8.90     0.05

        stop_
    """
    csv_path = path_in_test_data(__file__, "weight_source.csv")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"weight=@{csv_path}"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED, loop_text)


def test_insert_bare_file_ref_auto_names_col():
    """@file:col without a name= prefix auto-names the NEF column from the CSV columns."""
    EXPECTED = """\
        loop_
            _nef_chemical_shift.chain_code
            _nef_chemical_shift.sequence_code
            _nef_chemical_shift.residue_name
            _nef_chemical_shift.atom_name
            _nef_chemical_shift.value
            _nef_chemical_shift.Shift_(ppm)

            A   2   GLN   N   123.22   1.5
            A   2   GLN   H   8.90     2.5

        stop_
    """
    csv_path = path_in_test_data(__file__, "shift_ppm.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            f"@{csv_path}:Shift (ppm)",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED, loop_text)


def test_insert_multi_file_refs():
    """@path1:col,@path2:col in a single arg pulls columns from two separate files."""
    file1 = path_in_test_data(__file__, "flag.csv")
    file2 = path_in_test_data(__file__, "uncertainty.csv")
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            f"@{file1}:flag,@{file2}:uncertainty",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_TWO_COLUMNS_APPENDED, loop_text)


# --- bare file-ref tests: flag,uncertainty CSV ---


@pytest.mark.parametrize(
    "col_spec, expected",
    [
        ("@{path}", EXPECTED_TWO_COLUMNS_APPENDED),
        ("@{path}:flag,uncertainty", EXPECTED_TWO_COLUMNS_APPENDED),
        ("@{path}:1,uncertainty", EXPECTED_TWO_COLUMNS_APPENDED),
    ],
    ids=["all-columns", "named-multi-col", "mixed-index-and-name"],
)
def test_insert_bare_file_ref(col_spec, expected):
    csv_path = path_in_test_data(__file__, "loop_import.csv")
    spec = col_spec.format(path=csv_path)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", spec],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


# --- column-index selection tests: source,uncertainty CSV ---

EXPECTED_SOURCE_APPENDED = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.source

    A   2   GLN   N   123.22   foo
    A   2   GLN   H   8.90     bar

stop_
"""


@pytest.mark.parametrize(
    "col_spec, expected",
    [
        ("uncertainty=@{path}:uncertainty", EXPECTED_UNCERTAINTY_APPENDED),
        ("source=@{path}:1", EXPECTED_SOURCE_APPENDED),
        ("uncertainty=@{path}:2", EXPECTED_UNCERTAINTY_APPENDED),
        ("@{path}:2", EXPECTED_UNCERTAINTY_APPENDED),
    ],
    ids=["named-col", "first-by-index", "second-by-index", "bare-index-auto-names"],
)
def test_insert_file_ref_by_col(col_spec, expected):
    csv_path = path_in_test_data(__file__, "two_columns.csv")
    spec = col_spec.format(path=csv_path)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", spec],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


@pytest.mark.parametrize(
    "col_spec, expected_in_error",
    [
        ("col=@{path}:99", "column index 99 out of range"),
        ("col=@{path}:0", "column index 0 out of range"),
    ],
    ids=["out-of-range", "zero-index"],
)
def test_insert_file_ref_index_error(col_spec, expected_in_error):
    csv_path = path_in_test_data(__file__, "two_columns.csv")
    spec = col_spec.format(path=csv_path)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", spec],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )

    assert expected_in_error in result.stdout
    assert "1-based" in result.stdout
    assert "column specifications:" in result.stdout


# --- loop-level file import ---


@pytest.mark.parametrize(
    "args_template",
    [
        ["nef_chemical_shift_list_myshifts.nef_chemical_shift=@{path}"],
        ["--selector", "myshifts", "nef_chemical_shift:=@{path}"],
    ],
    ids=["fully-qualified", "with-selector"],
)
def test_insert_loop_file_import(args_template):
    """frame.loop=@file and loop:=@file bulk-import all CSV columns into the loop."""
    csv_path = path_in_test_data(__file__, "loop_import.csv")
    args = [a.format(path=csv_path) for a in args_template]
    result = run_and_report(app, ["--in", "-", *args], input=NEF_WITH_SHIFT_LOOP)
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_TWO_COLUMNS_APPENDED, loop_text)


EXPECTED_FORCE_REPLACE = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value

    A   2   GLN   N   999.99
    A   2   GLN   H   888.88

stop_
"""

EXPECTED_COLUMN_GROWS_LOOP = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.new_col

    A   2   GLN   N   123.22   111.11
    A   2   GLN   H   8.90     222.22
    .   .   .     .   .        333.33

stop_
"""


def test_force_replace_column():
    """--force required to replace an existing column."""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--force",
            "value=999.99,888.88",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_FORCE_REPLACE, loop_text)


def test_column_extends_loop():
    """More values than rows extends the loop; missing cells filled with '.'."""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "new_col=111.11,222.22,333.33",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_COLUMN_GROWS_LOOP, loop_text)


EXPECTED_RAGGED_WHITESPACE_FILL = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.c

    A   2   GLN   N   123.22   3
    A   2   GLN   H   8.90     .

stop_
"""


def test_ragged_whitespace_fills_missing_cells():
    """A short row in a whitespace-delimited file produces '.' for the missing field."""
    wsp_path = path_in_test_data(__file__, "ragged_whitespace.txt")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"c=@{wsp_path}:c"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_RAGGED_WHITESPACE_FILL, loop_text)


EXPECTED_CHAINED_FLAGS = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.col_a
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.col_b

    A   2   GLN   ok   N   123.22   0.1
    A   2   GLN   ok   H   8.90     0.05

stop_
"""


def test_chained_position_flags():
    """Multiple position flags in one command (col_a --before atom_name col_b --after value) work correctly."""
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "col_a=ok,ok",
            "--before",
            "atom_name",
            "col_b=0.1,0.05",
            "--after",
            "value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_CHAINED_FLAGS, loop_text)


EXPECTED_REVERSE_RANGE = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.countdown

    A   2   GLN   N   123.22   10
    A   2   GLN   H   8.90     9

stop_
"""


def test_reverse_range():
    """Reverse range (10..9) generates descending values."""
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", "countdown=10..9"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_REVERSE_RANGE, loop_text)


EXPECTED_HEADER_ONLY_CSV_FILLS_WITH_DOTS = """\
loop_
    _nef_chemical_shift.chain_code
    _nef_chemical_shift.sequence_code
    _nef_chemical_shift.residue_name
    _nef_chemical_shift.atom_name
    _nef_chemical_shift.value
    _nef_chemical_shift.col

    A   2   GLN   N   123.22   .
    A   2   GLN   H   8.90     .

stop_
"""


def test_header_only_csv_graceful_handling():
    """Header-only CSV files are handled gracefully by inserting missing values (.)."""
    csv_path = path_in_test_data(__file__, "header_only.csv")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"col=@{csv_path}"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_HEADER_ONLY_CSV_FILLS_WITH_DOTS, loop_text)


def test_empty_csv_error():
    """Empty CSV file produces clear error message with file path."""
    csv_path = path_in_test_data(__file__, "empty.csv")
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"col=@{csv_path}"],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert "failed to parse file" in result.stdout
    assert "empty.csv" in result.stdout
    assert "No lines provided" in result.stdout


def test_missing_csv_file_error():
    """Missing CSV file produces clear error message."""
    csv_path = Path(__file__).parent / "test_data" / "does_not_exist.csv"
    assert not csv_path.exists(), f"Test integrity: {csv_path} must not exist"
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"col=@{csv_path}"],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert "file not found" in result.stdout
