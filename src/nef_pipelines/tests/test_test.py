from nef_pipelines.lib.test_lib import select_matching_tests

TEST_NAMES = [
    "tests/nmrpipe/test_gdb.py::test_bad_data_format",
    "tests/nmrpipe/test_gdb.py::test_bad_format",
    "tests/nmrview/test_tcl.py::test_basic_word",
    "tests/nmrview/test_tcl.py::test_quoted_word",
]


def test_test_match_specific():

    EXPECTED_NAMES = [
        "tests/nmrpipe/test_gdb.py::test_bad_data_format",
        "tests/nmrview/test_tcl.py::test_basic_word",
    ]

    result = select_matching_tests(TEST_NAMES, EXPECTED_NAMES)

    assert result == EXPECTED_NAMES


def test_test_match_stared_path():

    EXPECTED_NAMES = [
        "tests/nmrview/test_tcl.py::test_basic_word",
    ]

    args = ["*nmrview*::test_basic_word"]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_test_match_stared_name():
    args = ["tests/nmrview/test_tcl.py::*"]

    EXPECTED_NAMES = [
        "tests/nmrview/test_tcl.py::test_basic_word",
        "tests/nmrview/test_tcl.py::test_quoted_word",
    ]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_just_name():
    args = ["test_basic_word"]

    EXPECTED_NAMES = [
        "tests/nmrview/test_tcl.py::test_basic_word",
    ]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_star():
    args = ["*"]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == TEST_NAMES


def test_test_match_truncated_path():

    EXPECTED_NAMES = [
        "tests/nmrpipe/test_gdb.py::test_bad_data_format",
        "tests/nmrpipe/test_gdb.py::test_bad_format",
    ]

    args = ["nmrpipe/test_gdb.py::*"]
    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_no_path():
    args = ["::test_bad_format"]

    EXPECTED_NAMES = [
        "tests/nmrpipe/test_gdb.py::test_bad_format",
    ]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_no_name():
    args = ["tests/nmrpipe/test_gdb.py::"]

    EXPECTED_NAMES = [
        "tests/nmrpipe/test_gdb.py::test_bad_data_format",
        "tests/nmrpipe/test_gdb.py::test_bad_format",
    ]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES


def test_bare_separator():

    args = ["::"]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == TEST_NAMES


def test_bare_filename():

    args = ["test_gdb.py::"]

    EXPECTED_NAMES = [
        "tests/nmrpipe/test_gdb.py::test_bad_data_format",
        "tests/nmrpipe/test_gdb.py::test_bad_format",
    ]

    result = select_matching_tests(TEST_NAMES, args)

    assert result == EXPECTED_NAMES
