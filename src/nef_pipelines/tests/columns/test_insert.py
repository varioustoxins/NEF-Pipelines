from pathlib import Path

import pytest
import typer
from pynmrstar import Entry

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    isolate_loop,
    path_in_test_data,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.columns.columns_structures import (
    ColumnSpecification,
    FileValueSpecification,
    HeadingsInferredAdvisory,
    InsertInstruction,
    InsertPlacement,
)
from nef_pipelines.tools.columns.insert import insert, pipe

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


# two_columns.csv has a heading row, so selecting by position requires saying so: --skip 1
# discards the headings and --use-column-headings off then reads what remains positionally
POSITIONAL_ON_HEADED_FILE = ["--use-column-headings", "off", "--skip", "1"]

FILE_REF_BY_COL_CASES = [
    ("named-col", [], "uncertainty=@{path}:uncertainty", EXPECTED_UNCERTAINTY_APPENDED),
    (
        "first-by-index",
        POSITIONAL_ON_HEADED_FILE,
        "source=@{path}:1",
        EXPECTED_SOURCE_APPENDED,
    ),
    (
        "second-by-index",
        POSITIONAL_ON_HEADED_FILE,
        "uncertainty=@{path}:2",
        EXPECTED_UNCERTAINTY_APPENDED,
    ),
    ("bare-index-auto-names", [], "@{path}:2", EXPECTED_UNCERTAINTY_APPENDED),
]


@pytest.mark.parametrize(
    "test_id, extra_args, col_spec, expected",
    FILE_REF_BY_COL_CASES,
    ids=[case[0] for case in FILE_REF_BY_COL_CASES],
)
def test_insert_file_ref_by_col(test_id, extra_args, col_spec, expected):
    csv_path = path_in_test_data(__file__, "two_columns.csv")
    spec = col_spec.format(path=csv_path)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", *extra_args, spec],
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


# --- column heading detection and the --use-column-headings override ---

HEADERLESS_SHIFTS = """\
1   G   C1'   91.38
2   G   C2'   75.10
3   G   C3'   74.98
"""

HEADED_SHIFTS = """\
index,residue,atom,shift
1,G,C1',91.38
2,G,C2',75.10
3,G,C3',74.98
"""

EXPECTED_HEADERLESS_ALL_ROWS = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.shift

        A   2   GLN   N   123.22   91.38
        A   2   GLN   H   8.90     75.10
        .   .   .     .   .        74.98

    stop_
"""

EXPECTED_HEADED_BY_NAME = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.shift

        A   2   GLN   N   123.22   91.38
        A   2   GLN   H   8.90     75.10
        .   .   .     .   .        74.98

    stop_
"""

EXPECTED_RULE_1_WARNING = (
    "are by number, so it is being read as having no heading row; "
    "use --use-column-headings on if the first row is headings"
)

EXPECTED_INFERRED_HEADINGS_ERROR = (
    "[the first row was read as column headings (inferred)]"
)

EXPECTED_NO_HEADING_NAMED_1 = (
    "column '1' not found in {path}; available columns are: index, residue, atom, shift "
    "[the first row was read as column headings]"
)

EXPECTED_NO_COLUMN_NAMED_ATOM = (
    "column 'atom' not found in {path}; available columns are indexed as 1..4 "
    "[the file was read as having no column headings]"
)


def _unwrapped(text: str) -> str:
    """Collapse whitespace so an assertion is not broken by where a message happens to wrap."""
    return " ".join(text.split())


def _write(tmp_path, name, text):
    """Write a data file for a test and return its path as a string."""
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_headerless_file_keeps_its_first_row(tmp_path):
    """Rule 1: all references by number means no heading row, so no data row is consumed.

    The first row here starts with a number, which is what data rows in such files look like,
    so the inference is almost certainly right and is not reported.
    """
    data = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"shift=@{data}:4"],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_HEADERLESS_ALL_ROWS, loop_text)
    assert result.stderr == ""


def test_positional_inference_is_reported_when_first_row_looks_like_headings(tmp_path):
    """A first row of nothing but text is the tell that the file may really have headings."""
    data = _write(tmp_path, "headed.csv", HEADED_SHIFTS)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"shift=@{data}:4"],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    assert EXPECTED_RULE_1_WARNING in _unwrapped(result.stderr)


def test_headerless_inference_warning_is_silenced_by_the_flag(tmp_path):
    """Stating the shape of the file removes the advisory warning but not the behaviour."""
    data = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "off",
            f"shift=@{data}:4",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_HEADERLESS_ALL_ROWS, loop_text)
    assert result.stderr == ""


def test_quiet_suppresses_the_warning_but_not_the_behaviour(tmp_path):
    """--quiet hides advisory warnings while leaving the inference itself untouched."""
    data = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--quiet",
            f"shift=@{data}:4",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_HEADERLESS_ALL_ROWS, loop_text)
    assert result.stderr == ""


def test_headings_on_reads_a_named_column(tmp_path):
    """With headings on a name resolves against the heading row, which is not data."""
    data = _write(tmp_path, "headed.csv", HEADED_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "on",
            f"shift=@{data}:shift",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_HEADED_BY_NAME, loop_text)
    assert result.stderr == ""


def test_headings_on_treats_a_number_as_a_name(tmp_path):
    """With headings on ':1' means the column headed '1', so it fails when there is none."""
    data = _write(tmp_path, "headed.csv", HEADED_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "on",
            f"shift=@{data}:1",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert EXPECTED_NO_HEADING_NAMED_1.format(path=data) in result.stdout


def test_headings_off_cannot_look_a_column_up_by_name(tmp_path):
    """With headings off there are no names to match, so a named reference fails."""
    data = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "off",
            f"shift=@{data}:atom",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert EXPECTED_NO_COLUMN_NAMED_ATOM.format(path=data) in result.stdout


EXPECTED_MIXED_SHAPES_IN_ONE_COMMAND = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.raw
        _nef_chemical_shift.named

        A   2   GLN   N   123.22   91.38   91.38
        A   2   GLN   H   8.90     75.10   75.10
        .   .   .     .   .        74.98   74.98

    stop_
"""


def test_column_headings_mode_changes_within_one_command(tmp_path):
    """The flag is positional, so each file is read with the mode in force where it appears."""
    headerless = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    headed = _write(tmp_path, "headed.csv", HEADED_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "off",
            f"raw=@{headerless}:4",
            "--use-column-headings",
            "on",
            f"named=@{headed}:shift",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_MIXED_SHAPES_IN_ONE_COMMAND, loop_text)
    assert result.stderr == ""


def test_column_headings_can_return_to_auto(tmp_path):
    """auto restores inference for later references, so its warning reappears."""
    stated = _write(tmp_path, "stated.csv", HEADED_SHIFTS)
    inferred = _write(tmp_path, "inferred.csv", HEADED_SHIFTS)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--use-column-headings",
            "on",
            f"named=@{stated}:shift",
            "--use-column-headings",
            "auto",
            f"raw=@{inferred}:4",
        ],
        input=NEF_WITH_SHIFT_LOOP,
        merge_stderr=False,
    )
    assert EXPECTED_RULE_1_WARNING in _unwrapped(result.stderr)
    assert "inferred.csv" in _unwrapped(result.stderr)
    assert "stated.csv" not in _unwrapped(result.stderr)


def test_pipe_returns_warnings_and_prints_nothing(tmp_path, capsys):
    """The pipe is silent by contract: advisory warnings come back for the caller to report."""
    data = _write(tmp_path, "headed.csv", HEADED_SHIFTS)
    entry = Entry.from_string(NEF_WITH_SHIFT_LOOP)
    loop = entry.get_saveframe_by_name("nef_chemical_shift_list_myshifts").get_loop(
        "nef_chemical_shift"
    )

    instruction = InsertInstruction(
        ColumnSpecification("shift", FileValueSpecification(Path(data), "4")),
        InsertPlacement.APPEND,
        None,
        loop,
    )

    result = pipe(entry, [instruction])

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""

    EXPECTED = [HeadingsInferredAdvisory(Path(data), has_header=False, is_mixed=False)]
    assert result.items == EXPECTED


# --- positional file settings: comment prefixes, skipping and bare file references ---

TWO_PREFIX_FILE_A = """\
# hash comment
value
1.0
2.0
"""

TWO_PREFIX_FILE_B = """\
! bang comment
score
10
20
"""

EXPECTED_TWO_PREFIXES = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.a
        _nef_chemical_shift.b

        A   2   GLN   N   123.22   1.0   10
        A   2   GLN   H   8.90     2.0   20

    stop_
"""


def test_two_files_with_different_comment_prefixes(tmp_path):
    """Each file is filtered with the comment prefixes in force where its reference appears."""
    file_a = _write(tmp_path, "a.csv", TWO_PREFIX_FILE_A)
    file_b = _write(tmp_path, "b.csv", TWO_PREFIX_FILE_B)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--comment",
            "#",
            f"a=@{file_a}:value",
            "--clear-comments",
            "--comment",
            "!",
            f"b=@{file_b}:score",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_TWO_PREFIXES, loop_text)


EXPECTED_CLEAR_COMMENTS_KEEPS_HASH_LINE = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.a

        A   2   GLN   N   123.22   value
        A   2   GLN   H   8.90     1.0
        .   .   .     .   .        2.0

    stop_
"""


def test_clear_comments_alone_stops_all_comment_filtering(tmp_path):
    """--clear-comments removes every prefix, so a '#' line becomes ordinary content."""
    file_a = _write(tmp_path, "a.csv", TWO_PREFIX_FILE_A)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--comment",
            "#",
            "--clear-comments",
            f"a=@{file_a}:#_hash_comment",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_CLEAR_COMMENTS_KEEPS_HASH_LINE, loop_text)


SKIP_TAIL_FILE = """\
value
1.0
2.0
TRAILER
"""

EXPECTED_SKIP_TAIL = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.a

        A   2   GLN   N   123.22   1.0
        A   2   GLN   H   8.90     2.0

    stop_
"""


def test_skip_tail_drops_trailing_rows(tmp_path):
    """--skip-tail removes rows from the end after comment filtering."""
    data = _write(tmp_path, "trailing.csv", SKIP_TAIL_FILE)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            "--skip-tail",
            "1",
            f"a=@{data}:value",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_SKIP_TAIL, loop_text)


BARE_REF_FILE = """\
# a comment
weight
1.5
2.5
"""

EXPECTED_BARE_REF_HEADING_FROM_COMMENT = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.#_a_comment

        A   2   GLN   N   123.22   weight
        A   2   GLN   H   8.90     1.5
        .   .   .     .   .        2.5

    stop_
"""

EXPECTED_BARE_REF_HEADING_FROM_WEIGHT = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.weight

        A   2   GLN   N   123.22   1.5
        A   2   GLN   H   8.90     2.5

    stop_
"""

BARE_REF_CASES = [
    ("no-settings", [], EXPECTED_BARE_REF_HEADING_FROM_COMMENT),
    ("skip-one", ["--skip", "1"], EXPECTED_BARE_REF_HEADING_FROM_WEIGHT),
    ("comment-hash", ["--comment", "#"], EXPECTED_BARE_REF_HEADING_FROM_WEIGHT),
]


@pytest.mark.parametrize(
    "test_id, extra_args, expected",
    BARE_REF_CASES,
    ids=[case[0] for case in BARE_REF_CASES],
)
def test_bare_file_ref_takes_headings_from_the_settings_in_force(
    tmp_path, test_id, extra_args, expected
):
    """A bare @file names its columns from the first row the current settings expose."""
    data = _write(tmp_path, "bare.csv", BARE_REF_FILE)
    result = run_and_report(
        app,
        [
            "--in",
            "-",
            "--selector",
            "myshifts.chemical_shift",
            *extra_args,
            f"@{data}",
        ],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(expected, loop_text)


def test_inferred_heading_mode_is_reported_as_inferred(tmp_path):
    """A failed lookup says how the file was read, and that the mode was a guess."""
    data = _write(tmp_path, "headerless.txt", HEADERLESS_SHIFTS)
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", f"shift=@{data}:atom"],
        input=NEF_WITH_SHIFT_LOOP,
        expected_exit_code=EXIT_ERROR,
    )
    assert EXPECTED_INFERRED_HEADINGS_ERROR in result.stdout


EXPECTED_LOOP_EXTENDED_BY_SEVERAL_ROWS = """\
    loop_
        _nef_chemical_shift.chain_code
        _nef_chemical_shift.sequence_code
        _nef_chemical_shift.residue_name
        _nef_chemical_shift.atom_name
        _nef_chemical_shift.value
        _nef_chemical_shift.extra

        A   2   GLN   N   123.22   a
        A   2   GLN   H   8.90     b
        .   .   .     .   .        c
        .   .   .     .   .        d

    stop_
"""


def test_column_longer_than_loop_extends_it_by_several_rows():
    """Padded rows must be independent lists, not one row aliased into every position."""
    result = run_and_report(
        app,
        ["--in", "-", "--selector", "myshifts.chemical_shift", "extra=a,b,c,d"],
        input=NEF_WITH_SHIFT_LOOP,
    )
    loop_text = isolate_loop(
        result.stdout, "nef_chemical_shift_list_myshifts", "nef_chemical_shift"
    )
    assert_lines_match(EXPECTED_LOOP_EXTENDED_BY_SEVERAL_ROWS, loop_text)
