import string
from fnmatch import translate as fnmatch_translate
from pathlib import Path

import pytest

from nef_pipelines.lib.util import (
    STDOUT,
    exit_if_file_has_bytes_and_no_force,
    find_substring_with_wildcard,
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


@pytest.mark.parametrize(
    "text,pattern,expected,description",
    [
        # Literal matches
        # chain_code
        # ^    ^
        # 0123456789
        ("chain_code", "chain", (0, 5), "literal substring match"),
        # Case sensitivity
        # Chain_Code
        # ^    ^
        # 0123456789
        ("Chain_Code", "Chain", (0, 5), "case-sensitive match (upper)"),
        ("Chain_Code", "chain", None, "case-sensitive no match (lower)"),
        # Wildcard patterns with asterisk
        # nef_chemical_shift
        #              ^    ^  13,18
        #     ^             ^  4, 18
        # 0123456789012345678
        ("nef_chemical_shift", "*shift*", (13, 18), "asterisk wildcards around word"),
        (
            "nef_chemical_shift",
            "*shift",
            (13, 18),
            "asterisk wildcards at front of word",
        ),
        ("nef_chemical_shift", "shift*", (13, 18), "asterisk wildcards at end of word"),
        ("nef_chemical_shift", "*chem*shift*", (4, 18), "multiple asterisks in middle"),
        # nef_molecular_system
        # 01234567890123456789
        #     ^            ^  4, 17
        ("nef_molecular_system", "mol*sys", (4, 17), "asterisk between chars"),
        # Wildcard patterns with question mark
        # chain_code
        # ^    ^  0, 6
        #  ^    ^ 1, 6
        # 0123456789
        ("chain_code", "ch?in", (0, 5), "question mark in middle"),
        ("chain_code", "?h?in", (0, 5), "multiple question marks"),
        ("chain_code", "?h?in", (0, 5), "question marks start and end"),
        ("chain_code", "h?in?", (1, 6), "question marks at end"),  # matches 'hain_'
        # Mixed wildcards
        # chain_code_name
        # 0123456789012345
        #       ^   ^  6, 10
        ("chain_code_name", "*c?de*", (6, 10), "mixed asterisk and question mark"),
        # Patterns with newlines (tests DOTALL mode)
        # chain\ncode
        # ^         ^  0, 10
        # 01234567890
        ("chain\ncode", "chain?code", (0, 10), "question mark matches newline"),
        # nef\chemical\shift
        #    n        n
        # ^           ^  0, 12
        # 01234567890123456789
        (
            "nef\nchemical\nshift",
            "*chemical*",
            (4, 12),
            "asterisk with newlines in text",
        ),  # matches 'chemical'
        # Bare wildcards
        # chain_code
        # ^         ^  0, 10
        # 0123456789
        ("chain_code", "*", (0, 10), "bare asterisk matches entire string"),
        # A
        # ^^  0, 1
        # 0
        ("A", "?", (0, 1), "bare question mark matches single character"),
        # chain_code
        # ^^  0, 1
        # 0123456789
        (
            "chain_code",
            "?",
            (0, 1),
            "bare question mark matches first character in substring search",
        ),
    ],
)
def test_find_substring_with_wildcard(text, pattern, expected, description):
    """Test find_substring_with_wildcard with various patterns.

    Args:
        text: The text to search in
        pattern: The pattern to search for (may contain wildcards)
        expected: Expected result tuple (start, end) or None
        description: Description of what this test case checks
    """
    result = find_substring_with_wildcard(text, pattern)
    assert result == expected, f"Failed: {description}"


@pytest.mark.parametrize(
    "pattern,expected_pattern,description",
    [
        # Patterns without wildcards - just get wrapped in (?s:...)
        ("chain", r"(?s:chain)\Z", "literal string no wildcards"),
        # Patterns with leading wildcards
        ("*chain", r"(?s:.*chain)\Z", "leading asterisk"),
        ("?chain", r"(?s:.chain)\Z", "leading question mark"),
        # Patterns with trailing wildcards
        ("chain*", r"(?s:chain.*)\Z", "trailing asterisk"),
        ("chain?", r"(?s:chain.)\Z", "trailing question mark"),
        # Patterns with both leading and trailing wildcards
        ("*chain*", r"(?s:(?=(?P<g0>.*?chain))(?P=g0).*)\Z", "both asterisk wildcards"),
        ("?chain?", r"(?s:.chain.)\Z", "both question marks"),
        # Patterns with wildcards in middle
        ("ch*in", r"(?s:ch.*in)\Z", "asterisk in middle"),
        ("ch?in", r"(?s:ch.in)\Z", "question mark in middle"),
        # Single wildcards
        ("*", r"(?s:.*)\Z", "single asterisk"),
        ("?", r"(?s:.)\Z", "single question mark"),
    ],
)
def test_fnmatch_translate_output(pattern, expected_pattern, description):
    """Test to verify exact output of fnmatch_translate.

    This is a regression test that documents the exact behavior of fnmatch_translate
    across Python versions. If fnmatch_translate changes its output format, these
    tests will catch it.

    The function find_substring_with_wildcard() depends on these specific patterns:
    - Wrapping in (?s:...) for DOTALL mode
    - Adding \\Z anchor at the end (but NOT \\A at the start)
    - Converting * to .* and ? to .
    - Using named groups (?P<gN>...) ONLY for patterns with both leading AND trailing
      ASTERISKS (e.g., "*chain*" → "(?=(?P<gN>.*?chain))(?P=gN).*" where N is a number)
    - Question marks on both ends do NOT create named groups (e.g., "?chain?" → ".chain.")
    - Group numbers vary based on fnmatch's internal counter state

    Args:
        pattern: The fnmatch pattern to translate
        expected_pattern: Regex pattern to match against the output (allows for variable group numbers)
        description: Description of the pattern
    """
    import re

    result = fnmatch_translate(pattern)

    # Normalize group numbers: fnmatch uses an internal counter that varies
    # Replace all group numbers (g0, g1, g20, etc.) with g0 for consistent comparison
    normalized_result = re.sub(r"\?P<g\d+>", "?P<g0>", result)
    normalized_result = re.sub(r"\?P=g\d+", "?P=g0", normalized_result)

    assert normalized_result == expected_pattern, (
        f"{description}: fnmatch_translate output changed!\n"
        f"  Pattern:  {pattern!r}\n"
        f"  Expected: {expected_pattern!r}\n"
        f"  Got:      {result!r}\n"
        f"  Normalized: {normalized_result!r}"
    )
