import string

import pytest

from nef_pipelines.lib.util import strip_characters_left
from nef_pipelines.transcoders.sparky.sparky_lib import parse_single_assignment


def test_strip_characters_left_empty():

    test = ""

    stripped, remaining = strip_characters_left(test, string.digits)

    assert stripped == ""
    assert remaining == ""


def test_strip_characters_left_partial():

    test = "123abc"

    stripped, remaining = strip_characters_left(test, string.digits)

    assert stripped == "123"
    assert remaining == "abc"


def test_strip_characters_left_all():

    test = "123456"

    stripped, remaining = strip_characters_left(test, string.digits)

    assert stripped == "123456"
    assert remaining == ""


@pytest.mark.parametrize(
    """input,expected_residue_name, expected_residue_number, expected_atom_name, previous_residue_name,
       previous_residue_number""",
    [
        ("10N", "", "10", "N", None, None),
        ("HN", "", "", "HN", None, None),
        ("?", "", "", "", None, None),
        ("T17H7", "T", "17", "H7", None, None),
        ("?N", "", "", "N", None, None),
        ("G16H8", "G", "16", "H8", None, None),
        ('T17H2"', "T", "17", 'H2"', None, None),
        ("H1'", "", "", "H1'", None, None),
        ("10N", "", "10", "N", "A", "11"),
        ("HN", "A", "11", "HN", "A", "11"),
        ("?", "", "", "", "A", "11"),
        ("T17H7", "T", "17", "H7", "A", "11"),
        ("?N", "A", "11", "N", "A", "11"),
        ("G16H8", "G", "16", "H8", "A", "11"),
        ('T17H2"', "T", "17", 'H2"', "A", "11"),
        ("H1'", "A", "11", "H1'", "A", "11"),
        ("N25CA", "N", "25", "CA", None, None),
    ],
)
def test_split_assignment(
    input,
    expected_residue_name,
    expected_residue_number,
    expected_atom_name,
    previous_residue_name,
    previous_residue_number,
):
    if previous_residue_number or previous_residue_name:
        residue_number, residue_name, atom_name = parse_single_assignment(
            input,
            previous_residue_name=previous_residue_name,
            previous_residue_number=previous_residue_number,
        )
    else:
        residue_number, residue_name, atom_name = parse_single_assignment(input)

    assert residue_name == expected_residue_name
    assert residue_number == expected_residue_number
    assert atom_name == expected_atom_name
