import string
from pathlib import Path

import pytest

from nef_pipelines.lib.util import (
    STDOUT,
    exit_if_file_has_bytes_and_no_force,
    fnmatch_one_of,
    strip_characters_left,
    strip_characters_right,
)


@pytest.mark.parametrize(
    "input, expected",
    [
        ("", ("", "")),
        ("AAAA", ("", "AAAA")),
        ("123AAAA", ("123", "AAAA")),
    ],
)
def test_strip_characters_left(input, expected):

    result = strip_characters_left(input, string.digits)

    assert result == expected


@pytest.mark.parametrize(
    "input, expected",
    [
        ("", ("", "")),
        ("AAAA", ("AAAA", "")),
        ("AAAA123", ("AAAA", "123")),
    ],
)
def test_strip_characters_right(input, expected):

    result = strip_characters_right(input, string.digits)
    assert result == expected


@pytest.mark.parametrize(
    "target, patterns,  result",
    [
        ("a", "a b a".split(), True),
        ("a", "d e f".split(), False),
        ("abc", "a*c e f".split(), True),
        ("abc", "abc e f".split(), True),
    ],
)
def test_fnmatch_one_of(target, patterns, result):
    assert fnmatch_one_of(target, patterns) == result


@pytest.mark.parametrize(
    "file_name, force, only_touch, is_exception_raised",
    [
        (STDOUT, False, None, False),
        (STDOUT, True, None, False),
        ("test.txt", True, True, False),
        ("test.txt", False, True, False),
        ("test.txt", True, False, False),
        ("test.txt", False, False, True),
        (None, True, None, False),
        (None, False, None, False),
    ],
)
def test_exit_if_file_has_bytes_and_no_force(
    file_name, force, only_touch, is_exception_raised, tmpdir
):

    if file_name == STDOUT:
        path = STDOUT
    elif file_name:
        path = Path(tmpdir) / file_name
    else:
        path = Path(tmpdir) / "non_existent.txt"

    if file_name and path != STDOUT:
        if only_touch:
            path.touch()
        else:
            with path.open("w") as f:
                f.write("test")

    exception_raised = False
    try:
        exit_if_file_has_bytes_and_no_force(path, force)
    except SystemExit:
        exception_raised = True

    assert exception_raised == is_exception_raised
