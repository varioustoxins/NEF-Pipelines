import string

import pytest

from nef_pipelines.lib.util import strip_characters_left, strip_characters_right


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
