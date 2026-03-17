from re import escape

import pytest
from pynmrstar import Entry, Loop, Saveframe

# noinspection PyProtectedMember
from nef_pipelines.lib.cli_lib import (
    RANGE_FORMAT,
    ChainOffsetSyntaxParsingError,
    DetectedSeparatorConflicts,
    RangeOffset,
    _combine_range_number_pairs,
    _get_available_separators,
    _validate_separators_are_unique_or_get_message,
    analyze_nef_entry_for_separator_conflicts,
    combine_residue_ranges,
    detect_overlapping_range_offsets,
    expand_residue_range,
    format_residue_range,
    parse_chain_offset_syntax,
    parse_frame_loop_and_tags,
    parse_range_number_pairs,
    parse_residue_ranges,
    validate_residue_ranges_in_system,
)
from nef_pipelines.lib.structures import (
    ResiduePair,
    ResidueRange,
    ResidueRangeParsingException,
)
from nef_pipelines.lib.test_lib import assert_lines_match


def test_parse_residue_ranges_basic():
    """Test parsing basic residue range specifications."""
    ranges = parse_residue_ranges(["A:1..10", "B:5..15"])

    assert ranges == [ResidueRange("A", 1, 10), ResidueRange("B", 5, 15)]


def test_parse_residue_ranges_comma_separated():
    """Test parsing comma-separated range specifications."""
    ranges = parse_residue_ranges(["A:1..5,B:10..20"])

    assert ranges == [ResidueRange("A", 1, 5), ResidueRange("B", 10, 20)]


def test_parse_residue_ranges_empty():
    """Test parsing empty or None input."""
    ranges = parse_residue_ranges(None)
    assert len(ranges) == 0

    ranges = parse_residue_ranges([])
    assert len(ranges) == 0


def test_parse_residue_ranges_validation():
    """Test parsing validation."""
    ranges = parse_residue_ranges(["A:5..10"])
    assert ranges[0] == ResidueRange("A", 5, 10)


def test_parse_residue_ranges_optional_chain():
    """Test parsing ranges with optional chain (applies to all chains)."""
    ranges = parse_residue_ranges([":10..20"])

    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 10, 20)


def test_parse_residue_ranges_optional_end():
    """Test parsing ranges with optional end residue."""
    ranges = parse_residue_ranges(["A:10", "B:5..15"])

    assert ranges == [ResidueRange("A", 10, 10), ResidueRange("B", 5, 15)]


def test_parse_residue_ranges_no_colon():
    """Test parsing range without colon (applies to all chains)."""
    ranges = parse_residue_ranges(["10..20"])

    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 10, 20)


def test_parse_residue_ranges_negative_numbers():
    """Test negative start residue (open-ended)"""
    ranges = parse_residue_ranges([":-5.."])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -5, None)

    # Test negative start with positive end
    ranges = parse_residue_ranges([":-5..10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -5, 10)

    # Test negative start with negative end
    ranges = parse_residue_ranges([":-10..-5"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -10, -5)


def test_parse_residue_ranges_negative_chain_codes():
    """Test that non-numeric strings with dashes are treated as chain codes"""
    ranges = parse_residue_ranges(["-B", "-X1", "-chain"])

    assert ranges == [
        ResidueRange("-B", None, None),
        ResidueRange("-X1", None, None),
        ResidueRange("-chain", None, None),
    ]


def test_parse_residue_ranges_simplified_parsing():
    """Test single negative number - treated as residue range"""
    ranges = parse_residue_ranges(["-5"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -5, -5)  # Treated as residue

    # Test multiple numbers
    ranges = parse_residue_ranges(["-5", "-23"])
    assert ranges == [
        ResidueRange(None, -23, -23),  # Single residue -23
        ResidueRange(None, -5, -5),  # Single residue -5
    ]

    # Test positive numbers - treated as single residue ranges
    pos_ranges = parse_residue_ranges(["5"])
    assert len(pos_ranges) == 1
    assert pos_ranges[0] == ResidueRange(None, 5, 5)  # Single residue


def test_parse_residue_ranges_bare_chain_codes():
    """Test parsing bare chain codes (entire chains)."""
    ranges = parse_residue_ranges(["A", "B"])

    assert ranges == [ResidueRange("A", None, None), ResidueRange("B", None, None)]


def test_parse_residue_ranges_mixed_formats():
    """Test parsing mixed chain codes and ranges."""
    ranges = parse_residue_ranges(["A", "B:5..15", ":10"])

    assert ranges == [
        ResidueRange(None, 10, 10),  # Residue 10 in all chains (sorted first)
        ResidueRange("A", None, None),  # Entire chain A
        ResidueRange("B", 5, 15),  # Range in chain B
    ]


def test_parse_residue_ranges_chain_codes_with_dashes():
    """Test parsing chain codes that contain dashes and complex names."""
    ranges = parse_residue_ranges(["A-1", "chain-B", "my-complex-chain", "-A-B-C"])

    assert ranges == [
        ResidueRange("-A-B-C", None, None),
        ResidueRange("A-1", None, None),
        ResidueRange("chain-B", None, None),
        ResidueRange("my-complex-chain", None, None),
    ]


# Test invalid format cases that should raise ResidueRangeParsingError
EXPECTED_EMPTY_RANGE_MSG = """
    Empty range specification [1] in: ':'
    All specs were: :
    Expected format: <CHAIN> | :<START-RESIDUE>[..<END-RESIDUE>] | <CHAIN>:<START-RESIDUE>[..<END-RESIDUE>]
"""

ESCAPED_RANGE_SPEC = escape(RANGE_FORMAT)

# These constants are no longer needed since string residues are now valid

EXPECTED_DUPLICATE_CHAIN_MSG = """
    Duplicate chain 'A' specified in ranges option for residue range specification 2 : A:10..15
    Each chain can only be specified once
    All specs were: A:1..5 A:10..15
"""


def test_parse_residue_ranges_error_cases():
    """Test error handling in range parsing."""

    # Test empty range specification
    with pytest.raises(ResidueRangeParsingException) as exc_info:
        parse_residue_ranges([":"])  # Empty range spec

    assert_lines_match(EXPECTED_EMPTY_RANGE_MSG, str(exc_info.value))

    # Test duplicate chain in no_combine mode
    with pytest.raises(ResidueRangeParsingException) as exc_info:
        parse_residue_ranges(["A:1..5", "A:10..15"], no_combine=True)  # Duplicate chain

    assert_lines_match(EXPECTED_DUPLICATE_CHAIN_MSG, str(exc_info.value))

    # Test that string residues are now valid (these used to be errors)
    # A:abc..10 should be valid (string start residue)
    ranges = parse_residue_ranges(["A:abc..10"])
    assert ranges == [ResidueRange("A", "abc", 10)]

    # A:10..xyz should be valid (string end residue)
    ranges = parse_residue_ranges(["A:10..xyz"])
    assert ranges == [ResidueRange("A", 10, "xyz")]


def test_parse_residue_ranges_custom_separators():
    """Test parsing ranges with custom separators."""
    # Test with @ as chain separator and ~ as range separator
    ranges = parse_residue_ranges(
        ["A", "B@5~15", "@10"], chain_separator="@", range_separator="~"
    )

    assert len(ranges) == 3
    assert ranges == [
        ResidueRange(None, 10, 10),  # Residue 10 in all chains (sorted first)
        ResidueRange("A", None, None),  # Entire chain A
        ResidueRange("B", 5, 15),  # Range in chain B
    ]

    # Test range with custom separator (separate test to avoid duplicate chain_code=None)
    ranges2 = parse_residue_ranges(["10~20"], chain_separator="@", range_separator="~")
    assert len(ranges2) == 1
    assert ranges2 == [
        ResidueRange(None, 10, 20),
    ]  # Range 10-20 in all chains


def test_parse_residue_ranges_custom_separators_with_dashes():
    """Test custom separators allow dashes in chain codes."""
    # With custom separators, dashes in chain codes should work fine
    ranges = parse_residue_ranges(
        ["A-1", "B-2@5~15", "@-5"], chain_separator="@", range_separator="~"
    )

    assert len(ranges) == 3
    assert ranges == [
        ResidueRange(None, -5, -5),  # Negative residue (all chains, sorted first)
        ResidueRange("A-1", None, None),  # Chain with dash
        ResidueRange("B-2", 5, 15),  # Chain with dash and range
    ]


def test_parse_residue_ranges_separator_validation():
    """Test that identical separators are rejected."""

    expected_msg = r"Chain separator: : and range separator: :\ncannot be identical"
    with pytest.raises(ResidueRangeParsingException, match=expected_msg):
        parse_residue_ranges(["A:5"], chain_separator=":", range_separator=":")


def test_analyze_nef_entry_for_separator_conflicts_no_conflicts():
    """Test separator conflict analysis with no conflicts."""
    test_nef = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A   1   ALA   start    .   .
         2   B   2   VAL   middle   .   .

       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result == DetectedSeparatorConflicts.OK


def test_analyze_nef_entry_for_separator_conflicts_chain_separator_in_chain_codes():
    """Test separator conflict analysis with chain separator in chain codes."""
    test_nef = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A:1   1   ALA   start    .   .
         2   B     2   VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result & DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_CHAIN_CODES


def test_analyze_nef_entry_for_separator_conflicts_range_separator_in_chain_codes():
    """Test separator conflict analysis with range separator in chain codes."""
    test_nef = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A-1   1   ALA   start    .   .
         2   B     2   VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result & DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_CHAIN_CODES


def test_analyze_nef_entry_for_separator_conflicts_chain_separator_in_sequence_codes():
    """Test separator conflict analysis with chain separator in sequence codes."""
    test_nef = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A   1:2   ALA   start    .   .
         2   B   2     VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result & DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_SEQUENCE_CODES


def test_analyze_nef_entry_for_separator_conflicts_range_separator_in_sequence_codes():
    """Test separator conflict analysis with range separator in sequence codes."""
    test_nef = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A   1-2   ALA   start    .   .
         2   B   2     VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result & DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_SEQUENCE_CODES


def test_analyze_nef_entry_for_separator_conflicts_custom_separators():
    """Test separator conflict analysis with custom separators."""
    # First test with data that's OK with standard separators
    test_nef_custom = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A@1   1     ALA   start    .   .
         2   B     2~3   VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef_custom)

    # Test with standard separators - should be OK
    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result == DetectedSeparatorConflicts.OK

    # Test with custom separators that conflict
    result = analyze_nef_entry_for_separator_conflicts(
        entry, chain_separator="@", range_separator="~"
    )
    assert result & DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_CHAIN_CODES
    assert result & DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_SEQUENCE_CODES


def test_analyze_nef_entry_for_separator_conflicts_multiple_conflicts():
    """Test separator conflict analysis with multiple types of conflicts."""
    test_nef_multiple = """
    data_test_entry

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system
       _nef_molecular_system.sf_framecode  nef_molecular_system

       loop_
          _nef_sequence.index
          _nef_sequence.chain_code
          _nef_sequence.sequence_code
          _nef_sequence.residue_name
          _nef_sequence.linking
          _nef_sequence.residue_variant
          _nef_sequence.cis_peptide

         1   A:B   1-2   ALA   start    .   .
         2   C-D   3:4   VAL   middle   .   .
       stop_

    save_
    """

    entry = Entry.from_string(test_nef_multiple)

    result = analyze_nef_entry_for_separator_conflicts(entry)
    assert result & DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_CHAIN_CODES
    assert result & DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_CHAIN_CODES
    assert result & DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_SEQUENCE_CODES
    assert result & DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_SEQUENCE_CODES


def test_combine_residue_ranges_empty():
    """Test combining empty list of ranges."""
    result = combine_residue_ranges([])
    assert result == []


def test_combine_residue_ranges_single_range():
    """Test combining single range (no combination needed)."""
    ranges = [ResidueRange("A", 1, 5)]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 5)]


def test_combine_residue_ranges_overlapping():
    """Test combining overlapping ranges."""
    ranges = [ResidueRange("A", 1, 5), ResidueRange("A", 3, 8)]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 8)]


def test_combine_residue_ranges_adjacent():
    """Test combining adjacent ranges."""
    ranges = [ResidueRange("A", 1, 5), ResidueRange("A", 6, 10)]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 10)]


def test_combine_residue_ranges_separate():
    """Test that separate ranges are not combined."""
    ranges = [ResidueRange("A", 1, 5), ResidueRange("A", 8, 10)]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 5), ResidueRange("A", 8, 10)]


def test_combine_residue_ranges_multiple_chains():
    """Test combining ranges across different chains."""
    ranges = [
        ResidueRange("A", 1, 5),
        ResidueRange("A", 3, 8),
        ResidueRange("B", 1, 3),
        ResidueRange("B", 5, 7),
    ]
    result = combine_residue_ranges(ranges)
    assert result == [
        ResidueRange("A", 1, 8),
        ResidueRange("B", 1, 3),
        ResidueRange("B", 5, 7),
    ]


def test_combine_residue_ranges_entire_chain_subsumes():
    """Test that entire chain range subsumes all other ranges for that chain."""
    ranges = [
        ResidueRange("A", 1, 5),
        ResidueRange("A", None, None),  # Entire chain A
        ResidueRange("A", 10, 15),
    ]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", None, None)]


def test_combine_residue_ranges_open_ended():
    """Test combining ranges with open ends."""
    ranges = [ResidueRange("A", 1, 5), ResidueRange("A", 3, None)]  # From 3 to end
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, None)]


def test_combine_residue_ranges_all_chains():
    """Test combining ranges that apply to all chains."""
    ranges = [
        ResidueRange(None, 1, 5),  # All chains
        ResidueRange(None, 3, 8),  # All chains
    ]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange(None, 1, 8)]


EXPECTED_COMPLEX_RESULT = [
    ResidueRange("A", 1, 3),
    ResidueRange("A", 5, 10),
    ResidueRange("A", 12, 15),
    ResidueRange("B", 2, 4),
    ResidueRange("B", 6, 8),
]


def test_combine_residue_ranges_complex_scenario():
    """Test complex scenario with multiple overlapping and adjacent ranges."""
    ranges = [
        ResidueRange("A", 1, 3),
        ResidueRange("A", 5, 7),
        ResidueRange("A", 6, 10),
        ResidueRange("A", 12, 15),
        ResidueRange("B", 2, 4),
        ResidueRange("B", 6, 8),
    ]
    result = combine_residue_ranges(ranges)
    assert result == EXPECTED_COMPLEX_RESULT


def test_combine_residue_ranges_single_residue():
    """Test combining single residue ranges."""
    ranges = [ResidueRange("A", 1, 1), ResidueRange("A", 2, 2), ResidueRange("A", 4, 4)]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 2), ResidueRange("A", 4, 4)]


def test_combine_residue_ranges_unsorted_input():
    """Test that function handles unsorted input correctly."""
    ranges = [
        ResidueRange("A", 10, 15),
        ResidueRange("A", 1, 5),
        ResidueRange("A", 3, 8),
    ]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 8), ResidueRange("A", 10, 15)]


def test_combine_residue_ranges_negative_residues():
    """Test combining ranges with negative residue numbers."""
    ranges = [
        ResidueRange("A", -5, -1),
        ResidueRange("A", -3, 2),
        ResidueRange("A", 5, 10),
    ]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", -5, 2), ResidueRange("A", 5, 10)]


def test_combine_residue_ranges_edge_case_touching():
    """Test ranges that exactly touch at boundaries."""
    ranges = [
        ResidueRange("A", 1, 5),
        ResidueRange("A", 6, 10),  # Exactly adjacent
        ResidueRange("A", 11, 15),  # Also adjacent to previous
    ]
    result = combine_residue_ranges(ranges)
    assert result == [ResidueRange("A", 1, 15)]


EXPECTED_COMBINED_RANGES = [ResidueRange("A", 1, 8), ResidueRange("B", 10, 20)]


def test_parse_residue_ranges_combines_by_default():
    """Test that parse_residue_ranges combines overlapping/adjacent ranges by default."""
    ranges = parse_residue_ranges(["A:1..5", "A:3..8", "B:10..15", "B:16..20"])

    assert ranges == EXPECTED_COMBINED_RANGES


EXPECTED_UNCOMBINED_RANGES = [
    ResidueRange("A", 1, 5),
    ResidueRange("B", 10, 15),
    ResidueRange("C", 3, 8),
]


def test_parse_residue_ranges_no_combine_disabled():
    """Test that parse_residue_ranges can skip combining when no_combine=True."""
    # Use ranges that don't overlap chains to avoid duplicate chain error
    ranges = parse_residue_ranges(["A:1..5", "B:10..15", "C:3..8"], no_combine=True)

    assert ranges == EXPECTED_UNCOMBINED_RANGES


EXPECTED_COMPLEX_COMBINED_RANGES = [
    ResidueRange("A", 1, 3),
    ResidueRange("A", 5, 10),
    ResidueRange("B", None, None),  # Entire chain B
    ResidueRange("C", 1, 5),
    ResidueRange("C", 8, 10),
]


def test_parse_residue_ranges_complex_combining():
    """Test complex combining scenarios in parse_residue_ranges."""
    ranges = parse_residue_ranges(
        [
            "A:1..3",
            "A:5..7",
            "A:6..10",  # A:5..7 and A:6..10 should combine to A:5..10
            "B",
            "B:20..25",  # B (entire chain) should subsume B:20..25
            "C:1..5",
            "C:8..10",  # C ranges should remain separate
        ]
    )

    assert ranges == EXPECTED_COMPLEX_COMBINED_RANGES


# Tests for combine_range_number_pairs function
def test_combine_range_number_pairs_empty():
    """Test combining empty list of range number pairs."""
    result = _combine_range_number_pairs([])
    assert result == []


def test_combine_range_number_pairs_single_range():
    """Test combining single range number pair."""
    ranges = [ResiduePair(1, 5)]
    result = _combine_range_number_pairs(ranges)
    assert result == [ResiduePair(1, 5)]


EXPECTED_OVERLAPPING = [ResiduePair(1, 8)]


def test_combine_range_number_pairs_overlapping():
    """Test combining overlapping range number pairs."""
    ranges = [ResiduePair(1, 5), ResiduePair(3, 8)]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_OVERLAPPING


EXPECTED_ADJACENT = [ResiduePair(1, 10)]


def test_combine_range_number_pairs_adjacent():
    """Test combining adjacent range number pairs."""
    ranges = [ResiduePair(1, 5), ResiduePair(6, 10)]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_ADJACENT


EXPECTED_SEPARATE = [ResiduePair(1, 5), ResiduePair(10, 15)]


def test_combine_range_number_pairs_separate():
    """Test that separate range number pairs remain separate."""
    ranges = [ResiduePair(1, 5), ResiduePair(10, 15)]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_SEPARATE


EXPECTED_OPEN_ENDED = [ResiduePair(1, None)]


def test_combine_range_number_pairs_open_ended():
    """Test combining range number pairs with open-ended ranges."""
    ranges = [
        ResiduePair(1, None),  # Open-ended from 1
        ResiduePair(5, 10),  # This should be subsumed
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_OPEN_ENDED


EXPECTED_OPEN_ENDED_MULTIPLE = [
    ResiduePair(5, None)  # All combine to open-ended from 5
]


def test_combine_range_number_pairs_open_ended_multiple():
    """Test combining multiple open-ended ranges."""
    ranges = [
        ResiduePair(5, None),  # Open-ended from 5
        ResiduePair(6, None),  # Open-ended from 6 (subsumed by 5-)
        ResiduePair(8, None),  # Open-ended from 8 (subsumed by 5-)
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_OPEN_ENDED_MULTIPLE


EXPECTED_SINGLE = [
    ResiduePair(5, 6),  # 5 and 6 combine to range 5-6
    ResiduePair(8, 8),  # 8 remains separate
]


def test_combine_range_number_pairs_single_residue():
    """Test combining single residue ranges (where start == end)."""
    ranges = [
        ResiduePair(5, 5),  # Single residue 5
        ResiduePair(6, 6),  # Single residue 6 (adjacent)
        ResiduePair(8, 8),  # Single residue 8 (separate)
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_SINGLE


EXPECTED_UNSORTED = [
    ResiduePair(1, 8),  # 1-5 and 4-8 combined
    ResiduePair(10, 15),  # Separate
]


def test_combine_range_number_pairs_unsorted_input():
    """Test combining unsorted range number pairs."""
    ranges = [
        ResiduePair(10, 15),
        ResiduePair(1, 5),
        ResiduePair(4, 8),  # Overlaps with 1-5
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_UNSORTED


EXPECTED_NEGATIVE = [ResiduePair(-5, 2)]


def test_combine_range_number_pairs_negative_residues():
    """Test combining range number pairs with negative residue numbers."""
    ranges = [ResiduePair(-5, -1), ResiduePair(-3, 2)]  # Overlaps with -5 to -1
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_NEGATIVE


EXPECTED_STRING = [
    ResiduePair(10, 15),  # Numeric range comes first
    ResiduePair("1A", "5A"),  # String ranges at end, unchanged
    ResiduePair("3B", "8B"),
]


def test_combine_range_number_pairs_string_residues():
    """Test combining range number pairs with string residue numbers that can't be converted."""
    ranges = [
        ResiduePair("1A", "5A"),
        ResiduePair("3B", "8B"),  # Different from 1A-5A, won't combine
        ResiduePair(10, 15),  # Numeric range
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_STRING


EXPECTED_MIXED = [
    ResiduePair(1, 8),  # 1-5 and 3-8 combined
    ResiduePair(10, 20),  # "10"-"15" and "12"-"20" combined
]


def test_combine_range_number_pairs_mixed_numeric_string():
    """Test combining range number pairs with mixed numeric and string types."""
    ranges = [
        ResiduePair(1, 5),
        ResiduePair("10", "15"),  # String numbers that can be converted
        ResiduePair(3, 8),  # Overlaps with 1-5
        ResiduePair("12", "20"),  # Overlaps with 10-15
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_MIXED


EXPECTED_TOUCHING = [
    ResiduePair(1, 6),  # 1-3 and 4-6 combined
    ResiduePair(8, 10),  # Separate
]


def test_combine_range_number_pairs_edge_case_touching():
    """Test edge case where ranges touch exactly."""
    ranges = [
        ResiduePair(1, 3),
        ResiduePair(4, 6),  # Touches 1-3 (3+1=4)
        ResiduePair(8, 10),  # Separate from 4-6
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_TOUCHING


EXPECTED_COMPLEX = [
    ResiduePair(1, 8),  # 1-3, 2-5, 6-8 all combined
    ResiduePair(10, 15),  # 10-12 and 11-15 combined
    ResiduePair(20, None),  # Open-ended from 20
]


def test_combine_range_number_pairs_complex_scenario():
    """Test complex scenario with multiple overlapping and adjacent ranges."""
    ranges = [
        ResiduePair(1, 3),
        ResiduePair(2, 5),  # Overlaps with 1-3
        ResiduePair(6, 8),  # Adjacent to combined 1-5
        ResiduePair(10, 12),  # Separate
        ResiduePair(11, 15),  # Overlaps with 10-12
        ResiduePair(20, None),  # Open-ended from 20
    ]
    result = _combine_range_number_pairs(ranges)
    assert result == EXPECTED_COMPLEX


# ==================== Plus Operator Tests ====================

EXPECTED_CHAINS = [
    ResidueRange("A", None, None),  # Entire chain A
    ResidueRange("B", None, None),  # Entire chain B
]


def test_parse_residue_ranges_plus_multiple_chains():
    """Test parsing multiple chains with + operator: A+B."""
    ranges = parse_residue_ranges(["A+B"])

    assert ranges == EXPECTED_CHAINS


EXPECTED_THREE_CHAINS = [
    ResidueRange("A", None, None),  # Entire chain A
    ResidueRange("B", None, None),  # Entire chain B
    ResidueRange("C", None, None),  # Entire chain C
]


def test_parse_residue_ranges_plus_three_chains():
    """Test parsing three chains with + operator: A+B+C."""
    ranges = parse_residue_ranges(["A+B+C"])

    assert ranges == EXPECTED_THREE_CHAINS


EXPECTED_CHAINS_RESIDUES = [
    ResidueRange("A", 20, 40),  # Chain A residues 20-40
    ResidueRange("B", 20, 40),  # Chain B residues 20-40
]


def test_parse_residue_ranges_plus_chains_with_residues():
    """Test parsing multiple chains with residue ranges: A+B:20..40."""
    ranges = parse_residue_ranges(["A+B:20..40"])

    assert ranges == EXPECTED_CHAINS_RESIDUES


EXPECTED_MULTIPLE_RANGES = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("A", 40, 60),  # Chain A residues 40-60
]


def test_parse_residue_ranges_plus_multiple_residue_ranges():
    """Test parsing multiple residue ranges in one chain: A:10..20+40..60."""
    ranges = parse_residue_ranges(["A:10..20+40..60"])

    assert ranges == EXPECTED_MULTIPLE_RANGES


EXPECTED_THREE_RANGES = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("A", 40, 60),  # Chain A residues 40-60
    ResidueRange("A", 80, 100),  # Chain A residues 80-100
]


def test_parse_residue_ranges_plus_multiple_ranges_three_parts():
    """Test parsing three residue ranges in one chain: A:10..20+40..60+80..100."""
    ranges = parse_residue_ranges(["A:10..20+40..60+80..100"])

    assert ranges == EXPECTED_THREE_RANGES


EXPECTED_SINGLE_RESIDUES = [
    ResidueRange("A", 10, 10),  # Chain A residue 10 (single residue becomes range)
    ResidueRange("A", 20, 20),  # Chain A residue 20
    ResidueRange("A", 30, 30),  # Chain A residue 30
]


def test_parse_residue_ranges_plus_single_residues():
    """Test parsing multiple single residues: A:10+20+30."""
    ranges = parse_residue_ranges(["A:10+20+30"])

    assert ranges == EXPECTED_SINGLE_RESIDUES


EXPECTED_MIXED_RANGES_SINGLES = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("A", 30, 30),  # Chain A residue 30
    ResidueRange("A", 40, 50),  # Chain A residues 40-50
]


def test_parse_residue_ranges_plus_mixed_ranges_and_singles():
    """Test parsing mixed ranges and single residues: A:10..20+30+40..50."""
    ranges = parse_residue_ranges(["A:10..20+30+40..50"])

    assert ranges == EXPECTED_MIXED_RANGES_SINGLES


EXPECTED_COMPLEX_NAMES = [
    ResidueRange("chain-A", None, None),  # Entire chain with complex name
    ResidueRange("chain-B", None, None),  # Entire chain with complex name
]


def test_parse_residue_ranges_plus_complex_chain_names():
    """Test parsing complex chain names with + operator: chain-A+chain-B."""
    ranges = parse_residue_ranges(["chain-A+chain-B"])

    assert ranges == EXPECTED_COMPLEX_NAMES


EXPECTED_COMBINED_REGULAR = [
    ResidueRange("A", 20, 40),  # Chain A residues 20-40 (from A+B:20..40)
    ResidueRange("B", 20, 40),  # Chain B residues 20-40 (from A+B:20..40)
    ResidueRange("C", 50, 60),  # Chain C residues 50-60 (regular syntax)
]


def test_parse_residue_ranges_plus_combined_with_regular():
    """Test parsing + operator combined with regular syntax."""
    ranges = parse_residue_ranges(["A+B:20..40", "C:50..60"])

    assert ranges == EXPECTED_COMBINED_REGULAR


EXPECTED_CUSTOM_SEPS = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("B", 10, 20),  # Chain B residues 10-20
]


def test_parse_residue_ranges_plus_with_custom_separators():
    """Test parsing + operator with custom separators."""
    ranges = parse_residue_ranges(
        ["A+B@10~20"], chain_separator="@", range_separator="~"
    )

    assert ranges == EXPECTED_CUSTOM_SEPS


EXPECTED_PLUS_NEGATIVE = [
    ResidueRange("A", -10, -5),  # Chain A residues -10 to -5
    ResidueRange("A", 5, 10),  # Chain A residues 5 to 10
]


def test_parse_residue_ranges_plus_negative_residues():
    """Test parsing + operator with negative residue numbers."""
    ranges = parse_residue_ranges(["A:-10..-5+5..10"])

    assert ranges == EXPECTED_PLUS_NEGATIVE


EXPECTED_PLUS_OPEN_ENDED = [
    ResidueRange("A", 10, 10),  # Chain A residue 10 (single residue)
    ResidueRange("A", 20, None),  # Chain A from residue 20 to end
]


def test_parse_residue_ranges_plus_open_ended_ranges():
    """Test parsing + operator with open-ended ranges."""
    ranges = parse_residue_ranges(["A:10+20.."])

    assert ranges == EXPECTED_PLUS_OPEN_ENDED


EXPECTED_EMPTY_CHAIN_ERROR = """
Empty chain code in chain combination in specification 1: 'A++B'
Expected format with chain combinations: CHAIN+CHAIN (e.g., 'A+B')
All specs were: A++B
"""


def test_parse_residue_ranges_plus_error_empty_chain():
    """Test error handling for empty chain codes in + combinations."""
    with pytest.raises(ResidueRangeParsingException) as exc_info:
        parse_residue_ranges(["A++B"])

    assert_lines_match(EXPECTED_EMPTY_CHAIN_ERROR, str(exc_info.value))


EXPECTED_EMPTY_RESIDUE_RANGE_ERROR = """
Empty residue range in range combination in specification 1: 'A:10..20++40..60'
Expected format with range combinations: CHAIN:RANGE+RANGE (e.g., 'A:10..20+40..60')
All specs were: A:10..20++40..60
"""


def test_parse_residue_ranges_plus_error_empty_residue_range():
    """Test error handling for empty residue ranges in + combinations."""
    with pytest.raises(ResidueRangeParsingException) as exc_info:
        parse_residue_ranges(["A:10..20++40..60"])

    assert_lines_match(EXPECTED_EMPTY_RESIDUE_RANGE_ERROR, str(exc_info.value))


EXPECTED_EMPTY_CHAIN_WITH_RESIDUES_ERROR = """
Empty chain code in chain combination in specification 1: 'A+:10..20'
Expected format with chain combinations: CHAIN+CHAIN:RESIDUES (e.g., 'A+B:10..20')
All specs were: A+:10..20
"""


def test_parse_residue_ranges_plus_error_empty_chain_with_residues():
    """Test error handling for empty chain codes with residue ranges."""
    with pytest.raises(ResidueRangeParsingException) as exc_info:
        parse_residue_ranges(["A+:10..20"])

    assert_lines_match(EXPECTED_EMPTY_CHAIN_WITH_RESIDUES_ERROR, str(exc_info.value))


EXPECTED_PLUS_NO_COMBINE = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("A", 15, 25),  # Chain A residues 15-25 (separate, not combined)
]


def test_parse_residue_ranges_plus_no_combine_mode():
    """Test + operator with no_combine=True to prevent range merging but allow + operator combinations."""
    # The + operator creates multiple ranges for the same chain within a single specification,
    # which should be allowed even in no_combine mode (no_combine prevents merging overlapping ranges,
    # but + operator creates intentionally separate ranges)
    ranges = parse_residue_ranges(["A:10..20+15..25"], no_combine=True)

    assert ranges == EXPECTED_PLUS_NO_COMBINE

    # This should fail because we have duplicate chain specifications across different arguments
    import pytest

    from nef_pipelines.lib.structures import ResidueRangeParsingException

    with pytest.raises(ResidueRangeParsingException):
        parse_residue_ranges(["A:10..20", "A:15..25"], no_combine=True)


EXPECTED_SIMPLIFIED = [
    ResidueRange("A", 10, 20),  # Chain A residues 10-20
    ResidueRange("B", 10, 20),  # Chain B residues 10-20
]


def test_parse_residue_ranges_plus_simplified_mode():
    """Test + operator with simplified parsing."""
    ranges = parse_residue_ranges(["A+B:10..20"])

    assert ranges == EXPECTED_SIMPLIFIED


EXPECTED_PLUS_COMBINING = [
    ResidueRange("A", 10, 25)  # Combined into single range 10-25
]


def test_parse_residue_ranges_plus_combining_behavior():
    """Test that + operator works correctly with range combining."""
    ranges = parse_residue_ranges(
        ["A:10..20+15..25"]
    )  # Overlapping ranges should combine

    assert ranges == EXPECTED_PLUS_COMBINING


# Tests for parse_range_number_pairs function
def test_parse_range_number_pairs_empty():
    """Test parsing empty list of range number pairs."""
    result = parse_range_number_pairs([])
    assert result == []


EXPECTED_BASIC = [ResiduePair(1, 5), ResiduePair(10, 15)]


def test_parse_range_number_pairs_basic():
    """Test basic parsing of range number pairs."""
    result = parse_range_number_pairs(["1..5", "10..15"])
    assert result == EXPECTED_BASIC


EXPECTED_PAIRS_COMBINED = [
    ResiduePair(1, 8),  # 1..5 and 3..8 combined
    ResiduePair(10, 15),  # 10..15 separate
]


def test_parse_range_number_pairs_combines_by_default():
    """Test that ranges are combined by default."""
    result = parse_range_number_pairs(["1..5", "3..8", "10..15"])
    assert result == EXPECTED_PAIRS_COMBINED


EXPECTED_PAIRS_NO_COMBINE = [
    ResiduePair(1, 5),  # With no_combine, individual ranges are preserved
    ResiduePair(3, 8),
]


def test_parse_range_number_pairs_no_combine_disabled():
    """Test that no_combine=True prevents combining."""
    result = parse_range_number_pairs(["1..5", "3..8"], no_combine=True)
    assert result == EXPECTED_PAIRS_NO_COMBINE


EXPECTED_PAIRS_SINGLE = [
    ResiduePair(5, 5),  # Single residue 5
    ResiduePair(10, 10),  # Single residue 10
]


def test_parse_range_number_pairs_single_residues():
    """Test parsing single residue specifications."""
    result = parse_range_number_pairs(["5", "10"])
    # Single residues become closed ranges (start == end)
    assert result == EXPECTED_PAIRS_SINGLE


EXPECTED_PAIRS_CUSTOM = [ResiduePair(1, 5), ResiduePair(10, 15)]


def test_parse_range_number_pairs_custom_separator():
    """Test parsing with custom range separator."""
    result = parse_range_number_pairs(["1_5", "10_15"], range_separator="_")
    assert result == EXPECTED_PAIRS_CUSTOM


EXPECTED_PAIRS_WHITESPACE = [ResiduePair(1, 5), ResiduePair(10, 15)]


def test_parse_range_number_pairs_with_whitespace():
    """Test parsing with whitespace in specifications."""
    result = parse_range_number_pairs([" 1..5 ", "  10..15  "])
    assert result == EXPECTED_PAIRS_WHITESPACE


EXPECTED_PAIRS_COMPLEX_COMBINED = [
    ResiduePair(1, 3),
    ResiduePair(5, 10),  # 5..7 and 6..10 combined
    ResiduePair(20, 20),  # Single residue 20 (closed range)
    ResiduePair(25, 30),  # Range 25..30 (separate)
]


def test_parse_range_number_pairs_complex_combining():
    """Test complex combining scenarios in parse_range_number_pairs."""
    result = parse_range_number_pairs(
        [
            "1..3",
            "5..7",
            "6..10",  # 5..7 and 6..10 should combine to 5..10
            "20",
            "25..30",  # 20 and 25..30 should remain separate
        ]
    )
    assert result == EXPECTED_PAIRS_COMPLEX_COMBINED


EXPECTED_PAIRS_NEGATIVE = [
    ResiduePair(-10, -10),  # Single negative residue
    ResiduePair(-5, -1),  # Negative range
    ResiduePair(5, 10),  # Positive range
]


def test_parse_range_number_pairs_negative_numbers():
    """Test parsing negative numbers with .. separator."""
    result = parse_range_number_pairs(["-5..-1", "-10", "5..10"])
    assert result == EXPECTED_PAIRS_NEGATIVE


EXPECTED_PAIRS_OPEN = [
    ResiduePair(1, None),  # Open range from 1 to end
    ResiduePair(None, 10),  # Open range from start to 10
    ResiduePair(-5, None),  # Open range from -5 to end
]


def test_parse_range_number_pairs_open_ranges():
    """Test parsing open-ended ranges with .. separator."""
    result = parse_range_number_pairs(["1..", "..10", "-5.."], no_combine=True)
    assert result == EXPECTED_PAIRS_OPEN


EXPECTED_PAIRS_STRING = [
    ResiduePair("A1", "A1"),  # String residue 'A1'
    ResiduePair("B2", "B5"),  # String range 'B2'..'B5'
    ResiduePair("--1", "--1"),  # String residue '--1'
]


def test_parse_range_number_pairs_string_residues():
    """Test parsing string residues with .. separator."""
    result = parse_range_number_pairs(["A1", "B2..B5", "--1"])
    assert result == EXPECTED_PAIRS_STRING


def test_parse_residue_ranges_single_residue():
    """Test parsing single residue specifications (explicit start and end)."""
    # Test B:10..10 - single residue 10 in chain B (explicit start and end)
    ranges = parse_residue_ranges(["B:10..10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange("B", 10, 10)

    # Test 10..10 - single residue 10 in all chains (explicit start and end)
    ranges = parse_residue_ranges(["10..10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 10, 10)

    # Test mixed single and range
    ranges = parse_residue_ranges(["10..10", "B:10..20"])
    assert len(ranges) == 2
    assert ranges[0] == ResidueRange(None, 10, 10)
    assert ranges[1] == ResidueRange("B", 10, 20)


def test_parse_residue_ranges_from_start_to_end():
    """Test parsing ranges from start residue to end of chain."""
    # Test A:5 - chain A only residue 5 (single residue)
    ranges = parse_residue_ranges(["A:5"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange("A", 5, 5)  # Now single residue

    # Test A:5.. - chain A from residue 5 to end (open-ended)
    ranges = parse_residue_ranges(["A:5.."])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange("A", 5, None)

    # Test :15 - all chains only residue 15 (single residue)
    ranges = parse_residue_ranges([":15"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 15, 15)  # Now single residue on all chains

    # Test 10 - all chains residue 10 (single residue, no colon)
    ranges = parse_residue_ranges(["10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 10, 10)


def test_parse_residue_ranges_empty_ranges():
    """Test parsing residue ranges that result in empty ranges (start > end)."""
    # Test basic empty range
    ranges = parse_residue_ranges(["20..10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 20, 10)

    # Test chain-specific empty range
    ranges = parse_residue_ranges(["A:15..5"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange("A", 15, 5)

    # Test negative empty range
    ranges = parse_residue_ranges([":-5..-10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -5, -10)

    # Test mixed positive to negative (empty range)
    ranges = parse_residue_ranges([":5..-2"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, 5, -2)

    # Test negative range parsed correctly
    ranges = parse_residue_ranges(["-5..-10"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange(None, -5, -10)

    # Test multiple empty ranges
    ranges = parse_residue_ranges(["A:10..5", "B:20..15"])
    assert len(ranges) == 2
    assert ranges[0] == ResidueRange("A", 10, 5)
    assert ranges[1] == ResidueRange("B", 20, 15)


def test_parse_residue_ranges_whole_chain():
    """Test that A: is valid and means entire chain A."""
    ranges = parse_residue_ranges(["A:"])
    assert len(ranges) == 1
    assert ranges[0] == ResidueRange("A", None, None)  # Entire chain A


# ==================== Chain Offset Syntax Tests ====================


def test_parse_chain_offset_syntax_empty():
    """Test parsing empty list returns empty result."""
    result = parse_chain_offset_syntax([])
    assert result == []


EXPECTED_WHOLE_CHAIN_OFFSET = [
    RangeOffset(chain_code="A", start_residue=None, end_residue=None, offset=2)
]


def test_parse_chain_offset_syntax_whole_chain():
    """Test parsing whole chain offset: A:+2"""
    result = parse_chain_offset_syntax(["A:+2"])
    assert result == EXPECTED_WHOLE_CHAIN_OFFSET


EXPECTED_RANGE_OFFSET = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=4)
]


def test_parse_chain_offset_syntax_range():
    """Test parsing range offset: A:10..20+4"""
    result = parse_chain_offset_syntax(["A:10..20+4"])
    assert result == EXPECTED_RANGE_OFFSET


EXPECTED_MULTI_CHAIN = [
    RangeOffset(chain_code="A", start_residue=None, end_residue=None, offset=2),
    RangeOffset(chain_code="B", start_residue=None, end_residue=None, offset=2),
    RangeOffset(chain_code="C", start_residue=None, end_residue=None, offset=2),
]


def test_parse_chain_offset_syntax_multiple_chains():
    """Test parsing multiple chains: A+B+C:+2"""
    result = parse_chain_offset_syntax(["A+B+C:+2"])
    assert result == EXPECTED_MULTI_CHAIN


EXPECTED_NEGATIVE_OFFSET = [
    RangeOffset(chain_code="A", start_residue=None, end_residue=None, offset=-5),
    RangeOffset(chain_code="B", start_residue=None, end_residue=None, offset=-5),
    RangeOffset(chain_code="C", start_residue=None, end_residue=None, offset=-5),
]


def test_parse_chain_offset_syntax_negative_offset():
    """Test parsing negative offset: A+B+C:-5"""
    result = parse_chain_offset_syntax(["A+B+C:-5"])
    assert result == EXPECTED_NEGATIVE_OFFSET


EXPECTED_COMMA_SEPARATED = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=3),
    RangeOffset(chain_code="B", start_residue=40, end_residue=50, offset=5),
]


def test_parse_chain_offset_syntax_comma_separated():
    """Test parsing comma separated operations: A:10..20+3,B:40..50+5"""
    result = parse_chain_offset_syntax(["A:10..20+3,B:40..50+5"])
    assert result == EXPECTED_COMMA_SEPARATED


EXPECTED_CHAIN_OFFSET_MULTIPLE_RANGES = [
    RangeOffset(chain_code="A", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="A", start_residue=90, end_residue=102, offset=-3),
    RangeOffset(chain_code="B", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="B", start_residue=90, end_residue=102, offset=-3),
    RangeOffset(chain_code="C", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="C", start_residue=90, end_residue=102, offset=-3),
]


def test_parse_chain_offset_syntax_multiple_ranges():
    """Test parsing multiple ranges for same chains: A+B+C:50..60+5:90..102-3"""
    result = parse_chain_offset_syntax(["A+B+C:50..60+5:90..102-3"])
    assert result == EXPECTED_CHAIN_OFFSET_MULTIPLE_RANGES


EXPECTED_COMPLEX_MIXED = [
    RangeOffset(chain_code="A", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="B", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="C", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="C", start_residue=90, end_residue=102, offset=-3),
    RangeOffset(chain_code="D", start_residue=90, end_residue=102, offset=-3),
    RangeOffset(chain_code="E", start_residue=90, end_residue=102, offset=-3),
]


def test_parse_chain_offset_syntax_complex_mixed():
    """Test parsing complex mixed operations: A+B+C:50..60+5,C+D+E:90..102-3"""
    result = parse_chain_offset_syntax(["A+B+C:50..60+5,C+D+E:90..102-3"])
    assert result == EXPECTED_COMPLEX_MIXED


EXPECTED_SINGLE_RESIDUE = [
    RangeOffset(chain_code="A", start_residue=15, end_residue=15, offset=1)
]


def test_parse_chain_offset_syntax_single_residue():
    """Test parsing single residue offset: A:15+1"""
    result = parse_chain_offset_syntax(["A:15+1"])
    assert result == EXPECTED_SINGLE_RESIDUE


EXPECTED_OPEN_ENDED_START = [
    RangeOffset(chain_code="A", start_residue=None, end_residue=20, offset=2)
]


def test_parse_chain_offset_syntax_open_ended_start():
    """Test parsing open-ended from start: A:..20+2"""
    result = parse_chain_offset_syntax(["A:..20+2"])
    assert result == EXPECTED_OPEN_ENDED_START


EXPECTED_OPEN_ENDED_END = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=None, offset=3)
]


def test_parse_chain_offset_syntax_open_ended_end():
    """Test parsing open-ended to end: A:10..+3"""
    result = parse_chain_offset_syntax(["A:10..+3"])
    assert result == EXPECTED_OPEN_ENDED_END


def test_parse_chain_offset_syntax_error_string_residues():
    """Test error handling for string residues: A:1A..5A+2"""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="Failed to parse range"):
        parse_chain_offset_syntax(["A:1A..5A+2"])


EXPECTED_NEGATIVE_RESIDUES = [
    RangeOffset(chain_code="A", start_residue=-5, end_residue=-1, offset=10)
]


def test_parse_chain_offset_syntax_negative_residues():
    """Test parsing negative residues: A:-5..-1+10"""
    result = parse_chain_offset_syntax(["A:-5..-1+10"])
    assert result == EXPECTED_NEGATIVE_RESIDUES


EXPECTED_MULTIPLE_ARGS = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=3),
    RangeOffset(chain_code="B", start_residue=40, end_residue=50, offset=5),
]


def test_parse_chain_offset_syntax_multiple_args():
    """Test parsing multiple arguments: ['A:10..20+3', 'B:40..50+5']"""
    result = parse_chain_offset_syntax(["A:10..20+3", "B:40..50+5"])
    assert result == EXPECTED_MULTIPLE_ARGS


EXPECTED_WHITESPACE_HANDLING = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=3),
    RangeOffset(chain_code="B", start_residue=40, end_residue=50, offset=5),
]


def test_parse_chain_offset_syntax_whitespace():
    """Test parsing with whitespace: ' A:10..20+3 , B:40..50+5 '"""
    result = parse_chain_offset_syntax([" A:10..20+3 , B:40..50+5 "])
    assert result == EXPECTED_WHITESPACE_HANDLING


def test_parse_chain_offset_syntax_error_missing_colon():
    """Test error handling for missing colon separator."""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="Missing ':' separator"):
        parse_chain_offset_syntax(["A+2"])


def test_parse_chain_offset_syntax_error_empty_chain():
    """Test error handling for empty chain group."""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="Empty chain group"):
        parse_chain_offset_syntax([":+2"])


def test_parse_chain_offset_syntax_error_no_offset():
    """Test error handling for missing offset."""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="No valid offset found"):
        parse_chain_offset_syntax(["A:10..20"])


def test_parse_chain_offset_syntax_error_invalid_range():
    """Test error handling for invalid range format."""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="Failed to parse range"):
        parse_chain_offset_syntax(["A:10..20..30+5"])


def test_parse_chain_offset_syntax_error_empty_range_spec():
    """Test error handling for empty range specification."""
    with pytest.raises(
        ChainOffsetSyntaxParsingError, match="Empty range/offset specification"
    ):
        parse_chain_offset_syntax(["A:"])


def test_parse_chain_offset_syntax_error_invalid_offset():
    """Test error handling for invalid offset format."""
    with pytest.raises(ChainOffsetSyntaxParsingError, match="No valid offset found"):
        parse_chain_offset_syntax(["A:10..20+abc"])


EXPECTED_ZERO_OFFSET = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=0)
]


def test_parse_chain_offset_syntax_zero_offset():
    """Test parsing zero offset: A:10..20+0"""
    result = parse_chain_offset_syntax(["A:10..20+0"])
    assert result == EXPECTED_ZERO_OFFSET


EXPECTED_LARGE_OFFSET = [
    RangeOffset(chain_code="A", start_residue=1, end_residue=5, offset=1000)
]


def test_parse_chain_offset_syntax_large_offset():
    """Test parsing large offset: A:1..5+1000"""
    result = parse_chain_offset_syntax(["A:1..5+1000"])
    assert result == EXPECTED_LARGE_OFFSET


EXPECTED_CHAIN_NAMES_WITH_NUMBERS = [
    RangeOffset(chain_code="A1", start_residue=None, end_residue=None, offset=5),
    RangeOffset(chain_code="B2", start_residue=None, end_residue=None, offset=5),
    RangeOffset(chain_code="C3", start_residue=None, end_residue=None, offset=5),
]


def test_parse_chain_offset_syntax_chain_names_with_numbers():
    """Test parsing chain names with numbers: A1+B2+C3:+5"""
    result = parse_chain_offset_syntax(["A1+B2+C3:+5"])
    assert result == EXPECTED_CHAIN_NAMES_WITH_NUMBERS


EXPECTED_COMPLEX_CHAIN_NAMES = [
    RangeOffset(chain_code="CHAIN_A", start_residue=10, end_residue=20, offset=3),
    RangeOffset(chain_code="CHAIN_B", start_residue=10, end_residue=20, offset=3),
]


def test_parse_chain_offset_syntax_complex_chain_names():
    """Test parsing complex chain names: CHAIN_A+CHAIN_B:10..20+3"""
    result = parse_chain_offset_syntax(["CHAIN_A+CHAIN_B:10..20+3"])
    assert result == EXPECTED_COMPLEX_CHAIN_NAMES


EXPECTED_VERY_COMPLEX = [
    RangeOffset(chain_code="A", start_residue=None, end_residue=None, offset=1),
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=2),
    RangeOffset(chain_code="A", start_residue=30, end_residue=40, offset=-1),
    RangeOffset(chain_code="B", start_residue=50, end_residue=60, offset=5),
    RangeOffset(chain_code="C", start_residue=50, end_residue=60, offset=5),
]


def test_parse_chain_offset_syntax_very_complex():
    """Test parsing very complex specification: A:+1:10..20+2:30..40-1,B+C:50..60+5"""
    result = parse_chain_offset_syntax(["A:+1:10..20+2:30..40-1,B+C:50..60+5"])
    assert result == EXPECTED_VERY_COMPLEX


EXPECTED_SAME_RESIDUE_RANGE = [
    RangeOffset(chain_code="A", start_residue=20, end_residue=20, offset=4),
    RangeOffset(chain_code="A", start_residue=50, end_residue=45, offset=10),
]


def test_parse_chain_offset_syntax_same_residue_range():
    """Test parsing same start/end residue and reverse range: A:20..20+4:50..45+10"""
    result = parse_chain_offset_syntax(["A:20..20+4:50..45+10"])
    assert result == EXPECTED_SAME_RESIDUE_RANGE


EXPECTED_ALTERNATIVE_SEPARATORS = [
    RangeOffset(chain_code="A", start_residue=10, end_residue=20, offset=3),
    RangeOffset(chain_code="B", start_residue=40, end_residue=50, offset=5),
]


def test_parse_chain_offset_syntax_alternative_separators():
    """Test parsing with alternative separators: A@10_20+3,B@40_50+5"""
    result = parse_chain_offset_syntax(
        ["A@10_20+3,B@40_50+5"], chain_separator="@", range_separator="_"
    )
    assert result == EXPECTED_ALTERNATIVE_SEPARATORS


EXPECTED_COMPLEX_SEPARATORS = [
    RangeOffset(chain_code="CH:A", start_residue=None, end_residue=None, offset=2),
    RangeOffset(chain_code="CH:A", start_residue=10, end_residue=20, offset=5),
    RangeOffset(chain_code="CH:B", start_residue=None, end_residue=None, offset=2),
    RangeOffset(chain_code="CH:B", start_residue=10, end_residue=20, offset=5),
]


def test_parse_chain_offset_syntax_colon_in_chain_name():
    """Test parsing with colon in chain name using alternative separator: CH:A+CH:B@+2@10_20+5"""
    result = parse_chain_offset_syntax(
        ["CH:A+CH:B@+2@10_20+5"], chain_separator="@", range_separator="_"
    )
    assert result == EXPECTED_COMPLEX_SEPARATORS


# ==================================================================================
# Tests for detect_overlapping_range_offsets functionality
# ==================================================================================


def test_detect_overlapping_range_offsets_empty():
    """Test overlap detection with empty list returns empty result."""
    result = detect_overlapping_range_offsets([])
    assert result == []


def test_detect_overlapping_range_offsets_no_overlaps():
    """Test overlap detection with non-overlapping ranges."""
    range_offsets = [
        RangeOffset("A", 1, 10, 0),  # A:1-10 -> 1-10
        RangeOffset("A", 20, 30, 0),  # A:20-30 -> 20-30
        RangeOffset("B", 1, 10, 0),  # B:1-10 -> 1-10 (different chain)
    ]
    result = detect_overlapping_range_offsets(range_offsets)
    assert result == []


def test_detect_overlapping_range_offsets_simple_overlap():
    """Test overlap detection with simple overlapping ranges."""
    range_offsets = [
        RangeOffset("A", 1, 10, 5),  # A:1-10 -> 6-15
        RangeOffset("A", 8, 15, 0),  # A:8-15 -> 8-15 (overlap at 8-15)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]
    assert range1.chain_code == "A"
    assert range2.chain_code == "A"
    assert conflict_info["chain_code"] == "A"


def test_detect_overlapping_range_offsets_whole_chain_overlap():
    """Test overlap detection with whole chain operations."""
    range_offsets = [
        RangeOffset("A", None, None, 5),  # Whole chain A +5
        RangeOffset(
            "A", 10, 20, 0
        ),  # A:10-20 +0 -> will overlap with shifted whole chain
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]
    assert conflict_info["chain_code"] == "A"


def test_detect_overlapping_range_offsets_different_chains_no_overlap():
    """Test that ranges on different chains don't overlap."""
    range_offsets = [
        RangeOffset("A", 1, 10, 10),  # A:1-10 -> 11-20
        RangeOffset(
            "B", 1, 10, 10
        ),  # B:1-10 -> 11-20 (same target range but different chain)
    ]
    result = detect_overlapping_range_offsets(range_offsets)
    assert result == []


def test_detect_overlapping_range_offsets_adjacent_ranges_no_overlap():
    """Test that adjacent ranges don't count as overlapping."""
    range_offsets = [
        RangeOffset("A", 1, 10, 0),  # A:1-10 -> 1-10
        RangeOffset("A", 11, 20, 0),  # A:11-20 -> 11-20 (adjacent, no overlap)
    ]
    result = detect_overlapping_range_offsets(range_offsets)
    assert result == []


def test_detect_overlapping_range_offsets_touching_ranges_overlap():
    """Test that touching ranges (same residue number) do overlap."""
    range_offsets = [
        RangeOffset("A", 1, 10, 0),  # A:1-10 -> 1-10
        RangeOffset("A", 10, 20, 0),  # A:10-20 -> 10-20 (overlap at residue 10)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]
    assert conflict_info["target_overlap"] == (10, 10)  # Overlap at residue 10


def test_detect_overlapping_range_offsets_open_ended_ranges():
    """Test overlap detection with open-ended ranges."""
    range_offsets = [
        RangeOffset("A", 10, None, 0),  # A:10.. -> 10 to end
        RangeOffset("A", 15, 25, 0),  # A:15-25 -> 15-25 (overlaps with open range)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]
    assert conflict_info["chain_code"] == "A"


def test_detect_overlapping_range_offsets_multiple_overlaps():
    """Test overlap detection with multiple overlapping pairs."""
    range_offsets = [
        RangeOffset("A", 1, 10, 0),  # A:1-10 -> 1-10
        RangeOffset("A", 5, 15, 0),  # A:5-15 -> 5-15 (overlaps with first)
        RangeOffset("A", 12, 20, 0),  # A:12-20 -> 12-20 (overlaps with second)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    # Should detect 2 overlapping pairs: (1st, 2nd) and (2nd, 3rd)
    assert len(result) == 2

    # Check that all detected overlaps are for chain A
    for range1, range2, conflict_info in result:
        assert conflict_info["chain_code"] == "A"


def test_detect_overlapping_range_offsets_offset_creates_overlap():
    """Test overlap detection where offsets create overlaps."""
    range_offsets = [
        RangeOffset("A", 1, 5, 10),  # A:1-5 +10 -> 11-15
        RangeOffset("A", 10, 15, 0),  # A:10-15 +0 -> 10-15 (overlaps at 11-15)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]

    # Verify the target overlap calculation
    target_overlap = conflict_info["target_overlap"]
    assert target_overlap == (11, 15)  # The overlapping target range


def test_detect_overlapping_range_offsets_negative_offsets():
    """Test overlap detection with negative offsets."""
    range_offsets = [
        RangeOffset("A", 20, 30, -10),  # A:20-30 -10 -> 10-20
        RangeOffset("A", 15, 25, -5),  # A:15-25 -5 -> 10-20 (same target range)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]

    # Both should map to the same target range 10-20
    target_overlap = conflict_info["target_overlap"]
    assert target_overlap == (10, 20)


def test_detect_overlapping_range_offsets_single_residue_overlap():
    """Test overlap detection with single residue ranges."""
    range_offsets = [
        RangeOffset("A", 10, 10, 5),  # A:10 +5 -> 15
        RangeOffset("A", 15, 15, 0),  # A:15 +0 -> 15 (same target residue)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]

    target_overlap = conflict_info["target_overlap"]
    assert target_overlap == (15, 15)  # Single residue overlap


def test_detect_overlapping_range_offsets_complex_scenario():
    """Test overlap detection in a complex scenario with multiple chains and ranges."""
    range_offsets = [
        # Chain A operations
        RangeOffset("A", 1, 10, 0),  # A:1-10 -> 1-10
        RangeOffset("A", 20, 30, -15),  # A:20-30 -15 -> 5-15 (overlaps with first)
        RangeOffset("A", 40, 50, 0),  # A:40-50 -> 40-50 (no overlap)
        # Chain B operations
        RangeOffset("B", 1, 10, 0),  # B:1-10 -> 1-10 (different chain, no overlap)
        RangeOffset("B", 5, 15, 0),  # B:5-15 -> 5-15 (overlaps with B:1-10)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    # Should detect 2 overlaps: A:1-10 vs A:5-15, and B:1-10 vs B:5-15
    assert len(result) == 2

    # Check that we have overlaps for both chains
    chains_with_overlaps = {
        conflict_info["chain_code"] for _, _, conflict_info in result
    }
    assert chains_with_overlaps == {"A", "B"}


def test_detect_overlapping_range_offsets_conflict_info_details():
    """Test that conflict info contains all expected details."""
    range_offsets = [
        RangeOffset("A", 1, 10, 5),  # A:1-10 +5 -> 6-15
        RangeOffset("A", 8, 15, 0),  # A:8-15 +0 -> 8-15 (overlap at 8-15)
    ]
    result = detect_overlapping_range_offsets(range_offsets)

    assert len(result) == 1
    range1, range2, conflict_info = result[0]

    # Check all expected keys in conflict_info
    expected_keys = {
        "chain_code",
        "source_overlap",
        "target_overlap",
        "range1_source",
        "range1_target",
        "range1_offset",
        "range2_source",
        "range2_target",
        "range2_offset",
    }
    assert set(conflict_info.keys()) == expected_keys

    # Check specific values
    assert conflict_info["chain_code"] == "A"
    assert conflict_info["range1_offset"] == 5
    assert conflict_info["range2_offset"] == 0
    assert conflict_info["target_overlap"] == (8, 15)


def test_get_available_separators_basic():
    """Test finding available separators when no conflicts exist."""
    test_nef = """
    data_test_entry

    save_test_frame
       _test_frame.sf_category   test_category

       loop_
          _loop.tag1
          _loop.tag2
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    # Use some common separators
    current_separators = [":", ","]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[]();"&<>/\{}`~!@#$%?+=|^-*'))
    assert result == expected


def test_get_available_separators_with_frame_name_conflicts():
    """Test that separators in frame names are excluded."""
    test_nef = """
    data_test_entry

    save_test-frame:special,chars
       _test-frame:special,chars.sf_category   category

    save_
    """

    entry = Entry.from_string(test_nef)

    current_separators = [";"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[]()"&<>/\{}`~!@#$%?+=|^*'))
    assert result == expected


def test_get_available_separators_with_loop_category_conflicts():
    """Test that separators in loop categories are excluded."""
    test_nef = """
    data_test_entry

    save_frame
       _frame.sf_category   category

       loop_
          _test;loop|category.tag
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    current_separators = [":"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[](),"&<>/\{}`~!@#$%?+=^-*'))
    assert result == expected


def test_get_available_separators_with_tag_conflicts():
    """Test that separators in tag names are excluded."""
    test_nef = """
    data_test_entry

    save_frame
       _frame.sf_category   category

       loop_
          _loop.tag&name
          _loop.tag#value
          _loop.tag@test
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    current_separators = [":"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[](),;"<>/\{}`~!$%?+=|^-*'))
    assert result == expected


def test_get_available_separators_multiple_frames():
    """Test checking separators across multiple frames."""
    test_nef = """
    data_test_entry

    save_frame1-name
       _frame1-name.sf_category   category1

       loop_
          _loop1.tag_a
          _loop1.tag_b
       stop_

    save_

    save_frame2:name
       _frame2:name.sf_category   category2

       loop_
          _loop2.tag_x
          _loop2.tag_y
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    current_separators = [",", ";"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[]()"&<>/\{}`~!@#$%?+=|^*'))
    assert result == expected


def test_get_available_separators_accepts_frame_list():
    """Test that function accepts list of frames instead of Entry."""
    frame1 = Saveframe.from_scratch("frame1", "category1")
    loop1 = Loop.from_scratch("loop1")
    loop1.add_tag(["tag_a"])
    frame1.add_loop(loop1)

    frame2 = Saveframe.from_scratch("frame2", "category2")
    loop2 = Loop.from_scratch("loop2")
    loop2.add_tag(["tag_b"])
    frame2.add_loop(loop2)

    frames = [frame1, frame2]
    current_separators = [":"]

    result = _get_available_separators(frames, current_separators)

    expected = list(sorted(r'[](),;"&<>/\{}`~!@#$%?+=|^-*'))
    assert result == expected


def test_get_available_separators_empty_entry():
    """Test with empty entry (no frames)."""
    test_nef = """
    data_test_entry
    """

    entry = Entry.from_string(test_nef)
    current_separators = [":"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[](),;"&<>/\{}`~!@#$%?+=|^-*'))
    assert result == expected


def test_get_available_separators_no_current_separators():
    """Test with no current separators."""
    test_nef = """
    data_test_entry

    save_frame-test
       _frame-test.sf_category   category

       loop_
          _loop.tag_a
       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    current_separators = []

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted(r'[](),;:"&<>/\{}`~!@#$%?+=|^*'))
    assert result == expected


def test_get_available_separators_many_used():
    """Test when many separators are used in the entry."""
    # Note: This test uses Entry.from_scratch() because it needs to create
    # an entry with special characters that would not be valid in NEF text format
    entry = Entry.from_scratch("test_entry")
    # Use a frame name with many special characters (note: _ and . removed from tests)
    frame = Saveframe.from_scratch("frame[](),.;:&<>", "category")
    loop = Loop.from_scratch("loop")
    loop.add_tag(["tag/\\{}`~!@#$%"])
    frame.add_loop(loop)
    entry.add_saveframe(frame)

    current_separators = ["?", "+"]

    result = _get_available_separators(entry, current_separators)

    expected = list(sorted('"=|^-*'))
    assert result == expected


def test_validate_split_separators_no_conflicts():
    """Test that validation passes when all separators are different."""
    separators = {"frame-tag": ":", "frame-loop": ".", "tag-list": ","}

    result = _validate_separators_are_unique_or_get_message(separators)

    assert result is None


def test_validate_split_separators_multiple_conflicts():
    """Test detection of multiple separate conflicts."""
    separators = {"sep1": ":", "sep2": ":", "sep3": ",", "sep4": ","}

    result = _validate_separators_are_unique_or_get_message(separators)

    expected = """\
        There are separator conflict: the following separators cannot be identical:
            'sep1' and 'sep2' both use ':',
            'sep3' and 'sep4' both use ','
        Please use different separators.
    """

    assert_lines_match(expected, result)


def test_validate_split_separators_empty():
    """Test that empty separator dict passes."""
    separators = {}

    result = _validate_separators_are_unique_or_get_message(separators)

    assert result is None


# Tests for parse_frame_loop_and_tags (ported from test_split.py)


def test_parse_frame_loop_and_tags_custom_separators():
    """Test parsing with custom separators."""
    result = parse_frame_loop_and_tags(
        "my_frame/loop_cat|tag1,tag2", frame_tag_separator="|", frame_loop_separator="/"
    )

    assert result.frame_name == "my_frame"
    assert result.loop_name == "loop_cat"
    assert result.tags == ["tag1", "tag2"]


def test_parse_frame_loop_and_tags_explicit_frame_loop():
    """Test explicit frame.loop:tags format."""
    result = parse_frame_loop_and_tags(
        "nef_rdc_restraint_list.nef_rdc_restraint:chain_code_1"
    )

    assert result.frame_name == "nef_rdc_restraint_list"
    assert result.loop_name == "nef_rdc_restraint"
    assert result.tags == ["chain_code_1"]


def test_parse_frame_loop_and_tags_frame_only():
    """Test frame:tags format (auto-detect loop)."""
    result = parse_frame_loop_and_tags("my_frame:tag1,tag2,tag3")

    assert result.frame_name == "my_frame"
    assert result.loop_name == "*"
    assert result.tags == ["tag1", "tag2", "tag3"]


def test_parse_frame_loop_and_tags_loop_wildcard():
    """Test .loop:tags format (any frame)."""
    result = parse_frame_loop_and_tags(".rdc:atom_name_1,atom_name_2")

    assert result.frame_name == "*"
    assert result.loop_name == "rdc"
    assert result.tags == ["atom_name_1", "atom_name_2"]


def test_parse_frame_loop_and_tags_frame_wildcard():
    """Test frame.:tags format (any loop in frame)."""
    result = parse_frame_loop_and_tags("dipolar.:tag1")

    assert result.frame_name == "dipolar"
    assert result.loop_name == "*"
    assert result.tags == ["tag1"]


def test_parse_frame_loop_and_tags_missing_separator_error():
    """Test error when frame tag separator is missing."""
    try:
        parse_frame_loop_and_tags("nef_rdc_restraint_list.nef_rdc_restraint")
        assert False, "Expected BadFrameLoopTagSyntaxException"
    except Exception as e:
        assert "you don't have a frame tag separator [:]" in str(e)
        assert "nef_rdc_restraint_list.nef_rdc_restraint" in str(e)


def test_parse_frame_loop_and_tags_too_many_separators_error():
    """Test error when too many frame tag separators."""
    try:
        parse_frame_loop_and_tags("frame:loop:tag1")
        assert False, "Expected BadFrameLoopTagSyntaxException"
    except Exception as e:
        assert "you have too many [2] separators [:], you should have 1" in str(e)


def test_parse_frame_loop_and_tags_empty_tags_error():
    """Test error when tags are empty."""
    try:
        parse_frame_loop_and_tags("frame.loop:")
        assert False, "Expected BadFrameLoopTagSyntaxException"
    except Exception as e:
        assert "tags are required after ':'" in str(e)


def test_parse_frame_loop_and_tags_whitespace_handling():
    """Test that whitespace in tags is stripped."""
    result = parse_frame_loop_and_tags("frame:tag1 , tag2 ,tag3")

    assert result.tags == ["tag1", "tag2", "tag3"]


def test_parse_residue_ranges_multiple_in_chain():
    """Test parsing multiple residue ranges in a single chain using +."""
    ranges = parse_residue_ranges(["A:1..10+20..30"])

    # These will be combined by default by combine_residue_ranges unless they are non-adjacent
    # 1..10 and 20..30 are not adjacent, so they should remain separate
    assert len(ranges) == 2
    assert ranges[0] == ResidueRange("A", 1, 10)
    assert ranges[1] == ResidueRange("A", 20, 30)


def test_parse_residue_ranges_multiple_chains_single_range():
    """Test parsing multiple chains with a single residue range using +."""
    ranges = parse_residue_ranges(["A+B:1..10"])

    assert len(ranges) == 2
    assert ranges[0] == ResidueRange("A", 1, 10)
    assert ranges[1] == ResidueRange("B", 1, 10)


def test_format_residue_range():
    assert format_residue_range(ResidueRange("A", 10, 20)) == "A:10..20"
    assert format_residue_range(ResidueRange(None, 10, 20)) == "*:10..20"
    assert format_residue_range(ResidueRange("A", 10, 10)) == "A:10"
    assert format_residue_range(ResidueRange("A", None, 10)) == "A:..10"
    assert format_residue_range(ResidueRange("A", 10, None)) == "A:10.."


def test_expand_residue_range():
    assert expand_residue_range(ResidueRange("A", 10, 12)) == [10, 11, 12]
    assert expand_residue_range(ResidueRange("A", 10, 10)) == [10]
    assert expand_residue_range(ResidueRange("A", 12, 10)) == []
    assert expand_residue_range(ResidueRange("A", None, 10)) == []
    assert expand_residue_range(ResidueRange("A", "10A", "10B")) == []


def test_validate_residue_ranges_in_system():
    test_nef = """
    data_test

    save_nef_molecular_system
       _nef_molecular_system.sf_category   nef_molecular_system

       loop_
          _nef_molecular_system_loop.chain_code
          _nef_molecular_system_loop.sequence_code
          _nef_molecular_system_loop.residue_variant
          _nef_molecular_system_loop.residue_name

         A   10   .   ALA
         A   11   .   ALA

       stop_

    save_
    """

    entry = Entry.from_string(test_nef)

    ranges = [
        ResidueRange("A", 10, 11),  # Found
        ResidueRange("A", 12, 13),  # Not found
        ResidueRange("B", 10, 11),  # Not found (wrong chain)
    ]

    missing = validate_residue_ranges_in_system(entry, ranges)
    assert len(missing) == 2
    assert missing[0] == ResidueRange("A", 12, 13)
    assert missing[1] == ResidueRange("B", 10, 11)
