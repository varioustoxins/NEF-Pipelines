import sys
from argparse import Namespace
from contextlib import contextmanager
from io import StringIO
from pathlib import Path

import pytest

# from pandas import DataFrame
from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import (  # dataframe_to_loop,; loop_to_dataframe,; NEF_CATEGORY_ATTR,
    UNUSED,
    BadNefFileException,
    create_entry_from_stdin,
    loop_row_dict_iter,
    loop_row_namespace_iter,
    read_entry_from_stdin_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
    select_frames_by_name,
    select_loops_by_category,
)
from nef_pipelines.lib.structures import SaveframeNameParts
from nef_pipelines.lib.test_lib import assert_lines_match, path_in_test_data
from nef_pipelines.lib.util import STDIN
from nef_pipelines.main import EXIT_ERROR

ITER_TEST_DATA = """\
    loop_
        _test.col_1
        _test.col_2
        _test.col_3

        a 2 4.5
        b 3 5.6

    stop_

"""

LOOPS_TWO_CATEGORIES = """\
data_test
    save_test_frame
        _test.sf_category test
        loop_
            _nef_chemical_shift.col_1
            .
        stop_
        loop_
            _nef_distance_restraint.col_1
            .
        stop_
    save_
"""

LOOPS_THREE_CATEGORIES = """\
data_test
    save_test_frame
        _test.sf_category test
        loop_
            _nef_chemical_shift.col_1
            .
        stop_
        loop_
            _nef_distance_restraint.col_1
            .
        stop_
        loop_
            _nef_rdc_restraint.col_1
            .
        stop_
    save_
"""

LOOPS_NUMBERED_LISTS = """\
data_test
    save_test_frame
        _test.sf_category test
        loop_
            _nef_chemical_shift_list_1.col_1
            .
        stop_
        loop_
            _nef_chemical_shift_list_2.col_1
            .
        stop_
        loop_
            _nef_chemical_shift_list_3.col_1
            .
        stop_
    save_
"""

LOOPS_TWO_NUMBERED_LISTS_PLUS_DISTANCE = """\
data_test
    save_test_frame
        _test.sf_category test
        loop_
            _nef_chemical_shift_list_1.col_1
            .
        stop_
        loop_
            _nef_chemical_shift_list_2.col_1
            .
        stop_
        loop_
            _nef_distance_restraint.col_1
            .
        stop_
    save_
"""

# def test_nef_to_pandas():
#
#     TEST_DATA_NEF = """
#         loop_
#           _test_loop.tag_1 _test_loop.tag_2
#           1                 2
#           3                 .
#         stop_
#     """
#
#     loop = Loop.from_string(TEST_DATA_NEF, convert_data_types=True)
#     result = loop_to_dataframe(loop)
#
#     EXPECTED_DATA_FRAME = DataFrame()
#     EXPECTED_DATA_FRAME["tag_1"] = ["1", "3"]
#     EXPECTED_DATA_FRAME["tag_2"] = ["2", "."]
#
#     assert result.equals(EXPECTED_DATA_FRAME)
#
#
# def test_pandas_to_nef():
#
#     TEST_DATA_NEF = """
#         loop_
#           _test_loop.tag_1 _test_loop.tag_2
#           1                 2
#           3                 .
#         stop_
#     """
#
#     EXPECTED_NEF = Loop.from_string(TEST_DATA_NEF)
#
#     data_frame = DataFrame()
#     data_frame["tag_1"] = ["1", "3"]
#     data_frame["tag_2"] = ["2", "."]
#
#     result = dataframe_to_loop(data_frame, category="test_loop")
#
#     assert result == EXPECTED_NEF


# def test_nef_category():
#
#     TEST_DATA_NEF = """
#         loop_
#           _test_loop.tag_1 _test_loop.tag_2
#           1                 2
#           3                 .
#         stop_
#     """
#
#     loop = Loop.from_string(TEST_DATA_NEF, convert_data_types=True)
#     frame = loop_to_dataframe(loop)
#
#     assert frame.attrs[NEF_CATEGORY_ATTR] == "test_loop"
#
#     new_loop = dataframe_to_loop(frame)
#
#     # note pynmrstar includes the leading _ in the category, I don't...!
#     assert new_loop.category == "_test_loop"
#
#     new_loop_2 = dataframe_to_loop(frame, category="wibble")
#     # note pynmrstar includes the leading _ in the category, I don't...!
#     assert new_loop_2.category == "_wibble"


def test_create_entry_from_empty_stdin(mocker):

    mocker.patch("sys.stdin", StringIO())
    result = create_entry_from_stdin()
    assert result is None


def test_create_entry_from_bad_stdin(mocker):
    mocker.patch("sys.stdin", StringIO("wibble"))

    with pytest.raises(BadNefFileException):
        result = create_entry_from_stdin()
        assert result is None


def test_create_entry_from_stdin(mocker):
    INPUT = """
        data_test
    """
    mocker.patch("sys.stdin", StringIO(INPUT))

    result = create_entry_from_stdin()

    assert result == Entry.from_scratch("test")


def test_read_or_create_entry_exit_error_on_bad_file_empty_stdin(mocker):
    mocker.patch("sys.stdin", StringIO())
    result = read_or_create_entry_exit_error_on_bad_file(STDIN)
    assert result == Entry.from_scratch("nef")


def test_read_or_create_entry_exit_error_on_bad_file_exception(mocker, tmp_path):
    mocker.patch("sys.exit")
    read_or_create_entry_exit_error_on_bad_file(tmp_path / "doesnt_exists.neff")

    sys.exit.assert_called_once_with(EXIT_ERROR)


def test_read_or_create_entry_exit_error_on_bad_file_bad_stdin(mocker):
    mocker.patch("sys.stdin", StringIO("wibble"))
    mocker.patch("sys.exit")

    read_or_create_entry_exit_error_on_bad_file(STDIN)

    sys.exit.assert_called_once_with(EXIT_ERROR)


def test_read_or_create_entry_exit_error_on_bad_file(mocker):
    INPUT = """
        data_test
    """
    mocker.patch("sys.stdin", StringIO(INPUT))

    result = create_entry_from_stdin()

    assert result == Entry.from_scratch("test")


def test_select_frames():
    TEST_DATA = """\
    data_test
        save_test_frame_1
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_


        save_test_frame_2
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_

        save_test_frame_13
            _test.sf_category test
            loop_
                _test.col_1
                .
            stop_
        save_

    """

    test = Entry.from_string(TEST_DATA)

    frames = select_frames_by_name(test, "test_frame_1")

    assert len(frames) == 1
    assert frames[0].name == "test_frame_1"

    frames = select_frames_by_name(test, ["test_frame_13"])

    assert len(frames) == 1
    assert frames[0].name == "test_frame_13"

    frames = select_frames_by_name(test, "frame_")
    assert len(frames) == 3
    names = sorted([frame.name for frame in frames])
    assert names == ["test_frame_1", "test_frame_13", "test_frame_2"]

    frames = select_frames_by_name(test, ["frame_1"], exact=False)

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ["test_frame_1", "test_frame_13"]

    frames = select_frames_by_name(test, ["*frame_1*"])

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ["test_frame_1", "test_frame_13"]

    frames = select_frames_by_name(test, ["frame_[1]"])

    assert len(frames) == 2
    names = sorted([frame.name for frame in frames])
    assert names == ["test_frame_1", "test_frame_13"]

    frames = select_frames_by_name(test, ["frame_[2]"])

    assert len(frames) == 1
    assert frames[0].name == "test_frame_2"


@contextmanager
def replace_stdin(target: str):
    """The provided input should be the text the user inputs. It support multiple lines for multiple inputs"""
    orig = sys.stdin
    sys.stdin = StringIO(target)
    yield
    sys.stdin = orig


def test_read_entry_stdin_or_exit_empty_stdin():
    with replace_stdin(""):
        with pytest.raises(SystemExit) as pytest_wrapped_e:
            read_entry_from_stdin_or_exit()

    assert pytest_wrapped_e.type == SystemExit
    assert pytest_wrapped_e.value.code == 1


@pytest.mark.skip(reason="not currently working and deprecated")
def test_read_entry_stdin_or_exit():

    EXPECTED = """\
    data_new

    save_nef_nmr_meta_data
       _nef_nmr_meta_data.sf_category      nef_nmr_meta_data
       _nef_nmr_meta_data.sf_framecode     nef_nmr_meta_data
       _nef_nmr_meta_data.format_name      nmr_exchange_format
       _nef_nmr_meta_data.format_version   1.1
       _nef_nmr_meta_data.program_name     NEFPipelines
       _nef_nmr_meta_data.program_version  0.0.1
       _nef_nmr_meta_data.script_name      header.py
       _nef_nmr_meta_data.creation_date    2021-06-19T21:13:32.548158
       _nef_nmr_meta_data.uuid             NEFPipelines-2021-06-19T21:13:32.548158-0485797022

       loop_
          _nef_run_history.run_number
          _nef_run_history.program_name
          _nef_run_history.program_version
          _nef_run_history.script_name
          _nef_run_history.uuid

          1 NEFPipelines 1.1 header.py NEFPipelines-2021-06-19T21:13:32.548158-0485797022

       stop_

    save_

    """
    path = path_in_test_data(__file__, "header.nef")
    lines = Path(path).read_text()

    with replace_stdin(lines):
        entry = read_entry_from_stdin_or_exit()

    assert_lines_match(str(entry), EXPECTED)


def test_loop_row_dict_iter():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"col_1": "a", "col_2": 2, "col_3": 4.5},
        {"col_1": "b", "col_2": 3, "col_3": 5.6},
    ]

    result = [row for row in loop_row_dict_iter(loop)]

    assert result == EXPECTED


def test_loop_row_dict_iter_no_convert():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"col_1": "a", "col_2": "2", "col_3": "4.5"},
        {"col_1": "b", "col_2": "3", "col_3": "5.6"},
    ]

    result = [row for row in loop_row_dict_iter(loop, convert=False)]

    assert result == EXPECTED


def test_row_dict_iter_update():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"col_1": "a", "col_2": "2_updated", "col_3": "4.5"},
        {"col_1": "b", "col_2": "3_updated", "col_3": "5.6"},
    ]

    for row in loop_row_dict_iter(loop, convert=False):
        for tag in row:
            if tag == "col_2":
                row[tag] = f"{row[tag]}_updated"

    result = [row for row in loop_row_dict_iter(loop, convert=False)]

    assert result == EXPECTED


def test_row_dict_iter_update_convert():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"col_1": "a", "col_2": "3", "col_3": "5.5"},
        {"col_1": "b", "col_2": "4", "col_3": "6.6"},
    ]

    for row in loop_row_dict_iter(loop, convert=True):
        for tag in row:
            if tag in ["col_2", "col_3"]:
                row[tag] = row[tag] + 1

    result = [row for row in loop_row_dict_iter(loop, convert=False)]

    assert result == EXPECTED


def test_row_dict_iter_delete():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"col_1": "a", "col_2": UNUSED, "col_3": "4.5"},
        {"col_1": "b", "col_2": UNUSED, "col_3": "5.6"},
    ]

    for row in loop_row_dict_iter(loop, convert=True):
        for tag in row:
            if tag == "col_2":
                del row[tag]

    result = [row for row in loop_row_dict_iter(loop, convert=False)]

    assert result == EXPECTED


def test_loop_row_namespace_iter():
    """Test loop_row_namespace_iter returns RowNamespace objects with correct attribute access and type conversion."""

    loop = Loop.from_string(ITER_TEST_DATA)

    result = list(loop_row_namespace_iter(loop))

    assert len(result) == 2
    # Check values and types are converted correctly
    assert (result[0].col_1, result[0].col_2, result[0].col_3) == ("a", 2, 4.5)
    assert [type(result[0].col_1), type(result[0].col_2), type(result[0].col_3)] == [
        str,
        int,
        float,
    ]
    assert (result[1].col_1, result[1].col_2, result[1].col_3) == ("b", 3, 5.6)
    assert [type(result[1].col_1), type(result[1].col_2), type(result[1].col_3)] == [
        str,
        int,
        float,
    ]


def test_loop_row_namespace_iter_no_convert():
    """Test loop_row_namespace_iter with convert=False returns string values without type conversion."""

    loop = Loop.from_string(ITER_TEST_DATA)

    result = list(loop_row_namespace_iter(loop, convert=False))

    assert len(result) == 2
    # Check all values remain as strings when convert=False
    assert (result[0].col_1, result[0].col_2, result[0].col_3) == ("a", "2", "4.5")
    assert [type(result[0].col_1), type(result[0].col_2), type(result[0].col_3)] == [
        str,
        str,
        str,
    ]
    assert (result[1].col_1, result[1].col_2, result[1].col_3) == ("b", "3", "5.6")
    assert [type(result[1].col_1), type(result[1].col_2), type(result[1].col_3)] == [
        str,
        str,
        str,
    ]


def test_loop_row_namespace_iter_mutability_basic():
    """Test that RowNamespace allows modifying loop data through attribute assignment."""

    loop = Loop.from_string(ITER_TEST_DATA)

    for row in loop_row_namespace_iter(loop):
        if row.col_1 == "a":
            row.col_2 = 999
            row.col_3 = 888.8

    # Values are converted to strings on write (pynmrstar stores everything as strings)
    assert loop.data[0] == ["a", "999", "888.8"]
    assert [type(datum) for datum in loop.data[0]] == [str, str, str]

    # Second row unchanged
    assert loop.data[1] == ["b", "3", "5.6"]
    assert [type(datum) for datum in loop.data[1]] == [str, str, str]


def test_loop_row_namespace_write_converts_to_string():
    """Test that all values are converted to strings on write."""
    TEST_DATA = """\
    loop_
        _test.name
        _test.int_val
        _test.float_val
        _test.bool_val

        A . . .
    stop_
    """

    loop = Loop.from_string(TEST_DATA)
    rows = list(loop_row_namespace_iter(loop))

    # Assign different types - all get converted to strings
    rows[0].int_val = 42
    rows[0].float_val = 3.14
    rows[0].bool_val = True

    # Everything is stored as strings (pynmrstar behavior)
    assert loop.data[0] == ["A", "42", "3.14", "True"]
    assert [type(datum) for datum in loop.data[0]] == [str, str, str, str]


def test_loop_row_namespace_read_converts_from_string():
    """Test that values are converted to appropriate types on READ, not write."""
    TEST_DATA = """\
    loop_
        _test.name
        _test.value

        A 10
    stop_
    """

    loop = Loop.from_string(TEST_DATA)
    rows = list(loop_row_namespace_iter(loop))

    # Assign float - gets stored as string
    rows[0].value = 3.14159

    # Stored as string in loop.data
    assert loop.data[0] == ["A", "3.14159"]
    assert [type(datum) for datum in loop.data[0]] == [str, str]

    # But when we READ it back via iterator, it's converted to float
    rows_after = list(loop_row_namespace_iter(loop))
    assert rows_after[0].value == 3.14159
    assert type(rows_after[0].value) is float


def test_loop_row_namespace_iter_mutability_invalid_attribute():
    """Test that RowNamespace raises AttributeError with detailed context when trying to set invalid attributes."""

    loop = Loop.from_string(ITER_TEST_DATA)
    rows = list(loop_row_namespace_iter(loop))

    with pytest.raises(
        AttributeError,
        match=r"Cannot set 'invalid_column' on row 0 in loop '_test'.*Available tags: col_1, col_2, col_3",
    ):
        rows[0].invalid_column = 123


def test_loop_row_namespace_iter_writethrough():
    """Test that reading and writing through RowNamespace is consistent with direct loop access."""

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        Namespace(col_1="a", col_2="2", col_3="4.5"),
        Namespace(col_1="b", col_2="3", col_3="5.6"),
    ]

    rows = list(loop_row_namespace_iter(loop))

    # Verify initial values match expected (with type conversion)
    assert rows[0].col_1 == EXPECTED[0].col_1
    assert rows[0].col_2 == int(EXPECTED[0].col_2)
    assert rows[0].col_3 == float(EXPECTED[0].col_3)
    assert rows[1].col_1 == EXPECTED[1].col_1
    assert rows[1].col_2 == int(EXPECTED[1].col_2)
    assert rows[1].col_3 == float(EXPECTED[1].col_3)

    # Now modify values
    rows[0].col_2 = 777
    rows[1].col_3 = 111.1

    # Verify changes propagated to loop data - all stored as strings
    assert loop.data[0] == ["a", "777", "4.5"]
    assert [type(datum) for datum in loop.data[0]] == [str, str, str]
    assert loop.data[1] == ["b", "3", "111.1"]
    assert [type(datum) for datum in loop.data[1]] == [str, str, str]

    # Verify re-reading shows modified values with correct types (converted on read)
    rows_after = list(loop_row_namespace_iter(loop))
    assert rows_after[0].col_1 == "a"
    assert rows_after[0].col_2 == 777
    assert rows_after[0].col_3 == 4.5
    assert rows_after[1].col_1 == "b"
    assert rows_after[1].col_2 == 3
    assert rows_after[1].col_3 == 111.1


@pytest.mark.skip(reason="not currently working")
def test_loop_row_dict_iter_attributes():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"a": "a", "b": "2", "c": "4.5"},
        {"a": "b", "b": "3", "c": "5.6"},
    ]

    for i, row in enumerate(loop_row_dict_iter(loop, convert=False)):
        assert row.col_1 == EXPECTED[i]["a"]
        assert row.col_2 == EXPECTED[i]["b"]
        assert row.col_3 == EXPECTED[i]["c"]


@pytest.mark.skip(reason="not currently working")
def test_loop_row_dict_iter_attributes_update():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        {"a": "a_b", "b": "3", "c": "5.5"},
        {"a": "b_b", "b": "4", "c": "6.6"},
    ]

    for row in loop_row_dict_iter(loop, convert=True):
        row.col_1 += "_b"
        row.col_2 += 1
        row.col_3 += 1

    for i, row in enumerate(loop_row_namespace_iter(loop, convert=False)):
        assert str(row.col_1) == EXPECTED[i]["a"]
        assert str(row.col_2) == EXPECTED[i]["b"]
        assert str(row.col_3) == EXPECTED[i]["c"]


def test_select_loops_by_category_empty_patterns():
    """Test select_loops_by_category with empty pattern list returns all loops."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, [])

    assert len(result) == 2


def test_select_loops_by_category_single_match():
    """Test select_loops_by_category with single pattern matching one loop."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["chemical_shift"])

    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift"


def test_select_loops_by_category_multiple_patterns():
    """Test select_loops_by_category with multiple patterns."""
    entry = Entry.from_string(LOOPS_THREE_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["chemical", "distance"])

    assert len(result) == 2
    categories = sorted([loop.category for loop in result])
    assert categories == ["_nef_chemical_shift", "_nef_distance_restraint"]


def test_select_loops_by_category_no_matches():
    """Test select_loops_by_category with pattern matching no loops."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["dihedral"])

    assert len(result) == 0


def test_select_loops_by_category_exact_flag_false():
    """Test select_loops_by_category with exact=False adds automatic wildcards."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["shift"], exact=False)

    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift"


def test_select_loops_by_category_exact_flag_true():
    """Test select_loops_by_category with exact=True requires exact category match."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    # "shift" doesn't match exactly "nef_chemical_shift" (without leading _)
    result = select_loops_by_category(loops, ["shift"], exact=True)
    assert len(result) == 0

    # Exact match required (pattern without leading underscore)
    result = select_loops_by_category(loops, ["nef_chemical_shift"], exact=True)
    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift"


def test_select_loops_by_category_wildcard_patterns():
    """Test select_loops_by_category with explicit wildcard patterns."""
    entry = Entry.from_string(LOOPS_TWO_NUMBERED_LISTS_PLUS_DISTANCE)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    # Partial match with automatic wildcards
    result = select_loops_by_category(loops, ["shift_list_1"])
    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift_list_1"

    # Explicit wildcard pattern
    result = select_loops_by_category(loops, ["*shift_list*"])
    assert len(result) == 2
    categories = sorted([loop.category for loop in result])
    assert categories == [
        "_nef_chemical_shift_list_1",
        "_nef_chemical_shift_list_2",
    ]


def test_select_loops_by_category_internal_wildcards():
    """Test select_loops_by_category with explicit internal wildcards like A*B."""
    entry = Entry.from_string(LOOPS_THREE_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    # Pattern with internal wildcard
    result = select_loops_by_category(loops, ["nef_*_shift"])
    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift"

    # Another pattern with internal wildcard
    result = select_loops_by_category(loops, ["nef_*_restraint"])
    assert len(result) == 2
    categories = sorted([loop.category for loop in result])
    assert categories == ["_nef_distance_restraint", "_nef_rdc_restraint"]

    # Multiple wildcards
    result = select_loops_by_category(loops, ["nef_*_*"])
    assert len(result) == 3


def test_select_loops_by_category_bracket_patterns():
    """Test select_loops_by_category with bracket patterns for character sets."""
    entry = Entry.from_string(LOOPS_NUMBERED_LISTS)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["list_[12]"])

    assert len(result) == 2
    categories = sorted([loop.category for loop in result])
    assert categories == [
        "_nef_chemical_shift_list_1",
        "_nef_chemical_shift_list_2",
    ]


def test_select_loops_by_category_deduplication():
    """Test select_loops_by_category deduplicates matches from multiple patterns."""
    entry = Entry.from_string(LOOPS_TWO_CATEGORIES)
    frame = entry.get_saveframe_by_name("test_frame")
    loops = frame.loops

    result = select_loops_by_category(loops, ["chemical", "shift", "nef_chemical"])

    assert len(result) == 1
    assert result[0].category == "_nef_chemical_shift"


@pytest.mark.parametrize(
    "full_name,category,expected",
    [
        # Singleton frame (no identity, no counter)
        (
            "nef_molecular_system",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", None, None),
        ),
        # Frame with identity only
        (
            "nef_molecular_system_protein_A",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "protein_A", None),
        ),
        # Frame with counter only (no identity before counter)
        ("ccpn_data`1`", "ccpn_data", SaveframeNameParts("ccpn", "data", None, "1")),
        # Frame with both identity and counter
        (
            "nef_molecular_system_protein_A`1`",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "protein_A", "1"),
        ),
        # Edge case: multiple underscores in identity
        (
            "nef_distance_restraint_list_long_range_1",
            "nef_distance_restraint_list",
            SaveframeNameParts("nef", "distance_restraint_list", "long_range_1", None),
        ),
        # Edge case: no namespace prefix possible (null namespace)
        ("nef", "nef", SaveframeNameParts("", "nef", None, None)),
        # Edge case: empty backticks (malformed counter)
        (
            "nef_molecular_system_protein_A``",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "protein_A``", None),
        ),
        # Edge case: multiple counters (only first is used)
        (
            "nef_molecular_system_protein_A`1`2`",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "protein_A`1", "2"),
        ),
        # Edge case: backtick in identity (before counter)
        (
            "nef_molecular_system_protein`A`1`",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "protein`A", "1"),
        ),
        # Edge case: backtick in identity (before counter)
        (
            "nef_molecular_system_proteinA``1`",
            "nef_molecular_system",
            SaveframeNameParts("nef", "molecular_system", "proteinA`", "1"),
        ),
        # Data inconsistency: category not a prefix of full_name
        (
            "nef_molecular_system",
            "ccpn_data",
            SaveframeNameParts("ccpn", "data", "ular_system", None),
        ),
    ],
)
def test_parse_frame_name(full_name, category, expected):
    """\
    Test parse_frame_name with various frame name patterns.
    """
    from nef_pipelines.lib.nef_lib import parse_frame_name

    parsed = parse_frame_name((full_name, category))

    assert parsed == expected


def test_parse_frame_name_with_saveframe():
    """\
    Test parse_frame_name can accept a Saveframe object.
    """
    from pynmrstar import Saveframe

    from nef_pipelines.lib.nef_lib import parse_frame_name

    frame = Saveframe.from_scratch("nef_molecular_system_protein_A")
    frame.category = "nef_molecular_system"

    parsed = parse_frame_name(frame)
    expected = SaveframeNameParts("nef", "molecular_system", "protein_A", None)

    assert parsed == expected
