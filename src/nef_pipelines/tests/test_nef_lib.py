import sys
from argparse import Namespace
from contextlib import contextmanager
from io import StringIO

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
)
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
    lines = open(path).read()

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

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        Namespace(col_1="a", col_2=2, col_3=4.5),
        Namespace(col_1="b", col_2=3, col_3=5.6),
    ]

    result = [row for row in loop_row_namespace_iter(loop)]

    assert result == EXPECTED


def test_loop_row_namespace_iter_no_convert():

    loop = Loop.from_string(ITER_TEST_DATA)

    EXPECTED = [
        Namespace(col_1="a", col_2="2", col_3="4.5"),
        Namespace(col_1="b", col_2="3", col_3="5.6"),
    ]

    result = [row for row in loop_row_namespace_iter(loop, convert=False)]

    assert result == EXPECTED


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
