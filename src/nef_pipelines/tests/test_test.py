# TODO we could also do with a test to check the separation of stdout and stderr by run_and_report

from nef_pipelines.lib.test_lib import run_and_report, select_matching_tests

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


def test_py_file_without_separator():
    """Test that test_file.py (without ::) matches all tests in that file."""
    # Use stable dummy test files instead of production tests
    test_names = [
        "tests/meta_tests/test_data/dummy_test_simple.py::test_dummy_pass_1",
        "tests/meta_tests/test_data/dummy_test_simple.py::test_dummy_pass_2",
        "tests/meta_tests/test_data/dummy_test_another.py::test_another_1",
    ]

    args = ["dummy_test_simple.py"]

    expected_names = [
        "tests/meta_tests/test_data/dummy_test_simple.py::test_dummy_pass_1",
        "tests/meta_tests/test_data/dummy_test_simple.py::test_dummy_pass_2",
    ]

    result = select_matching_tests(test_names, args)

    assert result == expected_names


def test_run_and_report_displays_stderr_on_exit_code_mismatch():
    """Test that run_and_report displays complete diagnostics when exit code doesn't match expected."""
    from contextlib import redirect_stdout
    from io import StringIO

    from meta_tests.test_data.failing_app import app

    captured_output = StringIO()

    with redirect_stdout(captured_output):
        # This should trigger assertion error and print diagnostics
        # Expected exit code 0 but actual will be 1, so diagnostics will be displayed
        try:
            run_and_report(app, [], expected_exit_code=0, merge_stderr=False)
        except AssertionError:
            pass  # Expected when exit codes don't match

    output = captured_output.getvalue()

    # Verify output contains complete diagnostic stanza
    EXPECTED_DIAGNOSTIC_SECTIONS = [
        "---------------------------------------- -stdout- ----------------------------------------",
        "This is stdout output",
        "---------------------------------------- -stderr- ----------------------------------------",
        "This is stderr output",
        "---------------------------------------- exception ----------------------------------------",
        "raise typer.Exit(1)",
        "---------------------------------------- --------- ----------------------------------------",
    ]

    # Verify all sections are present in correct order
    last_pos = -1
    for section in EXPECTED_DIAGNOSTIC_SECTIONS:
        pos = output.find(section, last_pos + 1)
        assert pos > last_pos, f"Section '{section}' missing or out of order"
        last_pos = pos

    # Verify output ends with footer
    assert output.rstrip().endswith(EXPECTED_DIAGNOSTIC_SECTIONS[-1])
