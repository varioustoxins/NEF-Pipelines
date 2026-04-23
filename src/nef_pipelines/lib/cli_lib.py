"""
CLI utility functions for command-line interface parsing and processing.

*TODO* double character escapes need to be supported to avoid over complication and custom separators
*TODO* support for custom separators needs to be withdrawn

This module provides parsing and validation for several CLI constructs used throughout NEF pipelines:

1. Residue Range Syntax - A:10..20, A+B:10, etc.
   - Numeric, string, negative residues
   - Open-ended ranges
   - Multiple chains with +
   - Custom separators

2. Chain Offset Syntax - A:10-20+5 for cloning with offsets
   - Range with positive/negative offsets
   - Overlap detection

3. Frame/Loop/Tag Selection - frame.loop.tag format
   - Hierarchical NEF data selection
   - Wildcard support

4. Range Number Pairs - Low-level 10..20 parsing
   - String residues, negative numbers
   - Open-ended ranges

5. Selector Lists - +nef, -custom for include/exclude patterns
   - Namespace filtering with +/- prefixes
   - Escape sequences (,,→, ++→+)
   - Inversion support

6. Separator Conflict Detection - Validates separators don't conflict with data
   - Checks chain codes, sequence codes
   - Suggests available alternatives

7. Validation and Utilities - Range validation against actual data
   - Expansion, formatting functions
"""

from __future__ import annotations

import re
from enum import Enum, Flag, auto
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Union

import pyparsing as pp
from pynmrstar import Entry, Saveframe
from pyparsing import ParserElement, ParseResults, StringEnd

from nef_pipelines.lib.sequence_lib import sequence_from_entry
from nef_pipelines.lib.structures import (
    BadFrameLoopTagSyntaxException,
    ChainOffsetSyntaxParsingError,
    FrameLoopAndTagSelectors,
    RangeOffset,
    ResiduePair,
    ResidueRange,
    ResidueRangeParsingException,
)
from nef_pipelines.lib.util import NEWLINE, is_int, parse_comma_separated_options

SELECT_ALL_FRAME_CATEGORIES_AND_TAGS = "*.*:*"


class SelectorAction(Enum):
    """Actions for selector operations."""

    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"


class AllNamespacesSentinel:
    """Sentinel object representing 'all namespaces' in selector operations.

    Using a unique sentinel object instead of a string like "ALL" prevents
    any possible conflict with an actual namespace named "ALL" or "*".
    """

    def __repr__(self):
        return "ALL_NAMESPACES"

    def __str__(self):
        return "ALL_NAMESPACES"


# Singleton sentinel for "all namespaces" selector
ALL_NAMESPACES = AllNamespacesSentinel()


# separators that can be used in star files [. and _ can't be separators]
# basically non-numeric and alphabetic ascii
POSSIBLE_SEPARATORS = r'[](),;:"&<>/\{}`~!@#$%?+=|^-*'

# info on range formats
# residue range number parsing default separator [..]
# so we have <RangeNumberPair>
#  1 -> RangeNumberPair(1, 1)                 # closed range from 1 (int) to 1 (int)
# -1 -> RangeNumberPair(-1, -1)               # closed range from -1 (int) to -1 (int)
# -1..10 -> RangeNumberPair(-1, 10)           # closed range from -1 (int) to 10 (int)
#  1..-10 -> RangeNumberPair(1, -10)          # closed range from 1 (int) to -10 (int) which is empty
# -15..-10 -> RangeNumberPair(-15, -10)       # closed range from -15 (int) to -10 (int)
#  1.. -> RangeNumberPair(1, None)            # open range from 1 (int) to end
# -1.. -> RangeNumberPair(-1, None)           # open range from -1 (int) to end
# --1..--1 -> RangeNumberPair('--1', '--1')   # closed range single residue '--1' (str)
# --1..--2 -> RangeNumberPair('--1', '--2')   # closed range but no legal as you can't specify ranges between
#                                               '--1' (str) to '--2' (str)
# all closed ranges that parse to strings have to have the
# --1 -> RangeNumberPair('--1', '--1')        # closed range single residue '--1'  (str)
# ..-1 RangeNumberPair(None, -1)              # open range from start to -1
# ..10 RangeNumberPair(None, 10)              # open range from start to 10

# any other number separator [-, + not allowed always, : only allowed if it's not used elsewhere .. residue range number
# is part of a residue range and : can still be used as a separator there, but we won't allow +, - or .. to keep things
# simple]
# lets take =  as range separator
# .. -> RangeNumberPair('..', '..')           # closed single residue range from '..' to '..'
# ..= -> RangeNumberPair('..', None)          # can be parsed but is not a meaningful range as is range,
# but can be treated as RangeNumber('..', '..') via post processing
# =.. -> RangeNumberPair(None, '..')          # can be parsed but is not a meaningful range as is range,
#                                             # but can be treated as RangeNumber('..', '..') via post processing
# ..=.. -> RangeNumberPair('..', '..')        # closed single residue range from '..' to '..'

# we can also have
# <RangeNumberPairList> =  <RangeNumberPair>[+<RangeNumberPair...]> ->
#                          [RangeNumberPair] | [RangeNumberPair, RangeNumberPair,...]
# <ChainCode> =  <string>
# <ChainCodeList> = <ChainCode>[+<ChainCode>...]
# <ResidueRange> = [<ChainCodeList>][<ChainCodeSeparator>][<RangeNumberPairList>]
# <ChainCodeSeparator> = <StrNoSigns>
# <StrNoSigns> = <a string but no + no - and no <ChainCodeSeparator>>

RANGE_FORMAT = "<CHAIN> | :<START-RESIDUE>[..<END-RESIDUE>] | <CHAIN>:<START-RESIDUE>[..<END-RESIDUE>]"

# Frame/loop/tag selector separators
FRAME_TAG_SEPARATOR = ":"
FRAME_LOOP_SEPARATOR = "."
TAG_LIST_SEPARATOR = ","

# Placeholders for escape sequence processing in parse_frame_loop_and_tags
_FRAME_LOOP_AND_TAG_PLACEHOLDERS = {
    "::": "\x00COLON\x00",
    "..": "\x00DOT\x00",
    ",,": "\x00COMMA\x00",
    "\\\\": "\x00BACKSLASH\x00",
    "++": "\x00PLUS\x00",
    "--": "\x00MINUS\x00",
}
_REVERSED_FRAME_LOOP_AND_TAG_PLACEHOLDERS = {
    placeholder: sep[0] for sep, placeholder in _FRAME_LOOP_AND_TAG_PLACEHOLDERS.items()
}


class DetectedSeparatorConflicts(Flag):
    """Flags indicating if different separators are required for unambiguous parsing."""

    OK = 0
    CHAIN_SEPARATOR_IN_CHAIN_CODES = auto()
    RANGE_SEPARATOR_IN_CHAIN_CODES = auto()
    CHAIN_SEPARATOR_IN_SEQUENCE_CODES = auto()
    RANGE_SEPARATOR_IN_SEQUENCE_CODES = auto()


# TODO i would like single returns
def parse_range_number_pair(
    range_part: str, range_separator: str = ".."
) -> ResiduePair:
    """
    Parse a range number pair "10..20", "-5..-1", "10", "-10" into a RangeNumberPair object.

    Returns:
        RangeNumberPair with start_residue and end_residue fields
    """
    range_part = range_part.strip()

    # Handle cases with no separator (single residue becomes closed range)
    if range_separator not in range_part:
        # Single residue: convert to closed range (start == end)
        if is_int(range_part):
            residue_val = int(range_part)
            return ResiduePair(start_residue=residue_val, end_residue=residue_val)
        else:
            # String residue: treat as closed range of that string value
            return ResiduePair(start_residue=range_part, end_residue=range_part)

    # Handle cases with separator - much simpler with .. separator
    start_str, end_str = range_part.split(range_separator, 1)
    start_str = start_str.strip()
    end_str = end_str.strip()

    # Handle empty start (like "..10")
    if not start_str:
        if is_int(end_str):
            return ResiduePair(start_residue=None, end_residue=int(end_str))
        else:
            return ResiduePair(start_residue=None, end_residue=end_str)

    # Handle empty end (like "10..")
    if not end_str:
        if is_int(start_str):
            return ResiduePair(start_residue=int(start_str), end_residue=None)
        else:
            return ResiduePair(start_residue=start_str, end_residue=None)

    # Handle both start and end present
    start_residue = int(start_str) if is_int(start_str) else start_str
    end_residue = int(end_str) if is_int(end_str) else end_str

    return ResiduePair(start_residue=start_residue, end_residue=end_residue)


def _validate_separators(chain_separator: str, range_separator: str) -> None:
    """Validate that chain and range separators are different."""
    if chain_separator == range_separator:
        msg = f"""
            Chain separator: {chain_separator} and range separator: {range_separator}
            cannot be identical
        """
        raise ResidueRangeParsingException(dedent(msg).strip())


def _parse_residue_ranges_with_pyparsing(
    spec: str, chain_separator: str, range_separator: str
) -> List[ResidueRange]:
    """
    Parse range specification using pyparsing for clean, robust parsing.

    Args:
        spec: Range specification to parse
        chain_separator: Character that separates chain from residue
        range_separator: Character sequence that separates start from end residue

    Returns:
        List of ResidueRange objects
    """

    # With .. separator, we don't need separate strict/relaxed grammars
    grammar = _build_unified_grammar(chain_separator, range_separator)

    try:
        parsed = grammar.parseString(spec, parseAll=True)
        return _convert_structured_parse_results(parsed.asList(), chain_separator, spec)
    except pp.ParseException as e:
        raise ResidueRangeParsingException(f"Failed to parse '{spec}': {str(e)}")


def _build_unified_grammar(chain_separator: str, range_separator: str):
    """
    Build unified pyparsing grammar for .. separator.

    With .. separator, there's no ambiguity so we don't need separate strict/relaxed modes.
    """

    # Basic elements - try integer first, then fall back to string
    # Pattern for integers (positive or negative)
    integer = pp.Regex(r"[+-]?\d+").setParseAction(lambda t: int(t[0]))

    # Pattern for non-integer residues (anything that's not just digits/signs)
    # Exclude the range separator and chain separator from residue names
    excluded_in_residue = re.escape(range_separator + chain_separator + "+") + r"\s,"
    string_residue = pp.Regex(f"[^{excluded_in_residue}]+")

    # Try integer first, then string residue
    residue = integer | string_residue

    # Chain names exclude +, whitespace, comma, and chain separator
    # With .. separator, chain names can freely contain - without ambiguity
    excluded_chars = re.escape("+" + chain_separator) + r"\s,"
    chain_name = pp.Regex(f"[^{excluded_chars}]+")

    # Separators
    chain_sep = pp.Literal(chain_separator).suppress()
    range_sep = pp.Literal(range_separator)
    plus_sep = pp.Literal("+").suppress()

    # Helper function to create range patterns
    def _create_range_patterns(residue_expr, parse_single_action=None):
        """Create closed/open range and single residue patterns for a given residue expression."""
        if parse_single_action is None:

            def parse_single_action(t):
                return ("single", t[0])

        closed = (residue_expr + range_sep + residue_expr).setParseAction(
            lambda t: ("range", t[0], t[2])
        )
        open_end = (residue_expr + range_sep + pp.StringEnd()).setParseAction(
            lambda t: ("range", t[0], None)
        )
        open_start = (range_sep + residue_expr).setParseAction(
            lambda t: ("range", None, t[1])
        )
        single = residue_expr.copy().setParseAction(parse_single_action)

        return closed | open_end | open_start | single

    # Residue patterns - much simpler with .. separator
    residue_pattern = _create_range_patterns(residue)
    residue_list = residue_pattern + pp.ZeroOrMore(plus_sep + residue_pattern)
    chain_list = chain_name + pp.ZeroOrMore(plus_sep + chain_name)

    # Define numeric-only residue patterns for bare number parsing
    numeric_residue = integer  # Only pure integers
    numeric_residue_pattern = _create_range_patterns(
        numeric_residue, lambda t: ("single", int(t[0]))
    )
    numeric_residue_list = numeric_residue_pattern + pp.ZeroOrMore(
        plus_sep + numeric_residue_pattern
    )

    # All possible patterns (order matters - most specific first)
    all_chains_with_residues = chain_sep + residue_list  # :10..20 or :10+20
    specific_chains_with_residues = (
        chain_list + chain_sep + residue_list
    )  # A:10..20 or A+B:10..20
    chains_with_empty_residues = chain_list + chain_sep  # A: (entire chain)
    numeric_residues_only = numeric_residue_list  # 10..20 or 10+20 (bare numbers only)
    chains_only = chain_list  # A or A+B (includes non-numeric strings)

    # Put numeric patterns before chain patterns to ensure numeric strings are parsed as residues
    return (
        all_chains_with_residues
        | specific_chains_with_residues
        | chains_with_empty_residues
        | numeric_residues_only
        | chains_only
    )


def _convert_structured_parse_results(
    tokens: List, chain_separator: str, original_spec: str
) -> List[ResidueRange]:
    """
    Convert structured pyparsing tokens to ResidueRange objects.

    Args:
        tokens: List of structured parsed tokens
        chain_separator: Character that separates chain from residue
        original_spec: Original specification string for context

    Returns:
        List of ResidueRange objects
    """
    ranges = []

    # Separate chain names from residue patterns
    chain_names = []
    residue_patterns = []

    for token in tokens:
        if isinstance(token, str):
            # This is a chain name
            chain_names.append(token)
        elif isinstance(token, tuple):
            # This is a structured residue pattern
            residue_patterns.append(token)

    # Determine the pattern type based on original spec
    if original_spec.startswith(chain_separator):
        # All chains pattern: :10..20 or :10+20
        chain_names = [None]  # Apply to all chains

    elif chain_separator in original_spec:
        # Chain-specific pattern: A:10..20 or A+B:10..20
        if not chain_names:
            # Extract from original spec if not found in tokens
            chain_part = original_spec.split(chain_separator)[0]
            chain_names = [name.strip() for name in chain_part.split("+")]

    elif not chain_names and residue_patterns:
        # No chain separator - residues for all chains
        chain_names = [None]  # Apply to all chains

    elif not residue_patterns:
        # Only chain names, no residue patterns (entire chains)
        # Chain names are already extracted
        pass

    # Create ranges
    if residue_patterns:
        # We have residue patterns to process
        for chain_name in chain_names:
            for pattern in residue_patterns:
                if pattern[0] == "range":
                    _, start, end = pattern
                    # Unwrap nested tuples from action functions
                    start_val = _unwrap_value(start)
                    end_val = _unwrap_value(end) if end is not None else None
                    ranges.append(ResidueRange(chain_name, start_val, end_val))
                elif pattern[0] == "single":
                    _, residue = pattern
                    # Unwrap nested tuples from action functions
                    residue_val = _unwrap_value(residue)

                    # With .. separator, single residues always become closed ranges (start == end)
                    # Open ranges use explicit patterns like "1.." or "..10"
                    ranges.append(ResidueRange(chain_name, residue_val, residue_val))
    else:
        # Only chain names (entire chains)
        for chain_name in chain_names:
            ranges.append(ResidueRange(chain_name, None, None))

    return ranges


def _unwrap_value(value):
    """Unwrap nested tuples from pyparsing action functions to get the actual value."""
    if isinstance(value, tuple) and len(value) >= 2 and value[0] == "single":
        return value[1]
    elif isinstance(value, tuple) and len(value) >= 2 and value[0] == "range":
        # This shouldn't happen for individual values, but handle it
        return value[1]
    else:
        return value


def _validate_plus_operator_syntax(spec: str, i: int, all_specs: List[str]) -> None:
    """
    Validate that plus operator syntax is correctly formed.

    Args:
        spec: Range specification to validate
        i: Specification number for error messages
        all_specs: All specifications for error context

    Raises:
        ResidueRangeParsingError: If malformed plus operator syntax is detected
    """
    # Check for double plus (empty chain or range)
    if "++" in spec:
        if ":" in spec:
            # This is likely a residue range with empty range: A:10-20++40-60
            msg = f"""
                Empty residue range in range combination in specification {i}: '{spec}'
                Expected format with range combinations: CHAIN:RANGE+RANGE (e.g., 'A:10..20+40..60')
                All specs were: {' '.join(all_specs)}
            """
        else:
            # This is likely a chain combination with empty chain: A++B
            msg = f"""
                Empty chain code in chain combination in specification {i}: '{spec}'
                Expected format with chain combinations: CHAIN+CHAIN (e.g., 'A+B')
                All specs were: {' '.join(all_specs)}
            """
        raise ResidueRangeParsingException(dedent(msg).strip())

    # Check for plus followed immediately by chain separator (empty chain before colon)
    if "+:" in spec:
        msg = f"""
            Empty chain code in chain combination in specification {i}: '{spec}'
            Expected format with chain combinations: CHAIN+CHAIN:RESIDUES (e.g., 'A+B:10..20')
            All specs were: {' '.join(all_specs)}
        """
        raise ResidueRangeParsingException(dedent(msg).strip())


def _check_duplicate_chains(
    ranges: List[ResidueRange],
    new_range: ResidueRange,
    i: int,
    spec: str,
    all_specs: List[str],
) -> None:
    """Check for duplicate chain codes when no_combine is enabled."""
    for existing_range in ranges:
        if existing_range.chain_code == new_range.chain_code:
            chain_code = new_range.chain_code
            msg = f"""
                Duplicate chain '{chain_code}' specified in ranges option for residue range specification {i} : {spec}
                Each chain can only be specified once
                All specs were: {' '.join(all_specs)}
            """
            raise ResidueRangeParsingException(dedent(msg).strip())


def parse_residue_ranges(
    range_specs: Union[None, List[str]],
    chain_separator: str = ":",
    range_separator: str = "..",
    no_combine: bool = False,
) -> List[ResidueRange]:
    """
    Parse range specifications in multiple formats with + operator support.

    Supported patterns:
    - <CHAIN> - entire chain (e.g., 'A', 'B', 'chain-name')
    - <RESIDUE> - single residue in all chains (e.g., '5', '-10')
    - <START-RESIDUE>{range_sep}<END-RESIDUE> - residue range in all chains (e.g., '5..10', '-5..10')
    - <CHAIN>{chain_sep}<START-RESIDUE>[{range_sep}<END-RESIDUE>] - residues in specific chain (e.g., 'A:5..10', 'B:5')
    - <CHAIN>+<CHAIN>[+...] - multiple chains (e.g., 'A+B', 'A+B+C')
    - <CHAIN>+<CHAIN>{chain_sep}<RESIDUES> - residues in multiple chains (e.g., 'A+B:10..20')
    - <CHAIN>{chain_sep}<RESIDUES>+<RESIDUES>[+...] - multiple residue ranges in chain (e.g., 'A:10..20+40..60')
    - {chain_sep}<START-RESIDUE>[{range_sep}<END-RESIDUE>] - residues in all chains (e.g., ':1..10', ':5', ':-5')
    - Open ranges: '1..', '..10', 'A:1..', 'A:..10'

    Args:
        range_specs: List of range specifications
        chain_separator: Character that separates chain from residue (default: ':')
        range_separator: Character sequence that separates start from end residue (default: '..')
        no_combine: If True, skip combining overlapping/adjacent ranges (default: False)

    Returns:
        List of ResidueRange objects
    """
    _validate_separators(chain_separator, range_separator)

    ranges = []
    all_specs = parse_comma_separated_options(range_specs or [])

    for i, spec in enumerate(all_specs, start=1):
        spec = spec.strip()
        if not spec:
            continue

        # Check for specific malformed plus operator patterns first
        _validate_plus_operator_syntax(spec, i, all_specs)

        # Check for empty range specifications
        if spec == chain_separator:
            msg = f"""
                Empty range specification [{i}] in: '{spec}'
                All specs were: {' '.join(all_specs)}
                Expected format: {RANGE_FORMAT}
            """
            raise ResidueRangeParsingException(dedent(msg).strip())
        # Parse using pyparsing only
        try:
            parsed_ranges = _parse_residue_ranges_with_pyparsing(
                spec, chain_separator, range_separator
            )

            # In no_combine mode, check for duplicate chains across different specifications only
            # The + operator within a single spec should be allowed to create multiple ranges for the same chain
            for residue_range in parsed_ranges:
                if no_combine:
                    # Only check for duplicates if this range has a single chain (not from + operator expansion)
                    # If the spec created multiple ranges, they're from + operator and should be allowed
                    if (
                        len(parsed_ranges) == 1
                    ):  # Single range from this spec, check for duplicates
                        _check_duplicate_chains(
                            ranges, residue_range, i, spec, all_specs
                        )
                ranges.append(residue_range)

        except Exception as e:
            # Handle specific exception types
            if isinstance(e, ResidueRangeParsingException):
                # Re-raise ResidueRangeParsingErrors (like duplicate chain) without modification
                raise e

            # Default error message
            msg = f"""
                Failed to parse range specification {i}: '{spec}'
                Error: {str(e)}
                Expected format: {RANGE_FORMAT}
                All specs were: {' '.join(all_specs)}
            """
            raise ResidueRangeParsingException(dedent(msg).strip())

    # Combine overlapping and adjacent ranges unless disabled
    if not no_combine:
        ranges = combine_residue_ranges(ranges)

    return ranges


def combine_residue_ranges(ranges: List[ResidueRange]) -> List[ResidueRange]:
    """
    Combine overlapping and adjacent residue ranges for the same chain.

    This function takes a list of ResidueRange objects and merges ranges that:
    - Are for the same chain
    - Are overlapping (e.g., A:1-5 and A:3-8 become A:1-8)
    - Are adjacent (e.g., A:1-5 and A:6-10 become A:1-10)

    Args:
        ranges: List of ResidueRange objects to combine

    Returns:
        List of combined ResidueRange objects, sorted by chain_code and start_residue
    """
    if not ranges:
        return []

    # Group ranges by chain_code
    chain_ranges = {}
    for range_obj in ranges:
        chain_code = range_obj.chain_code
        if chain_code not in chain_ranges:
            chain_ranges[chain_code] = []
        chain_ranges[chain_code].append(range_obj)

    combined_ranges = []

    for chain_code, chain_range_list in chain_ranges.items():
        # Skip ranges that represent entire chains (both start and end are None)
        entire_chain_ranges = [
            r
            for r in chain_range_list
            if r.start_residue is None and r.end_residue is None
        ]
        residue_ranges = [
            r
            for r in chain_range_list
            if not (r.start_residue is None and r.end_residue is None)
        ]

        # If there's an entire chain range, it subsumes all other ranges for this chain
        if entire_chain_ranges:
            combined_ranges.append(ResidueRange(chain_code, None, None))
            continue

        if not residue_ranges:
            continue

        # Sort ranges by start_residue (handle None values and mixed types)
        def sort_key(r):
            # Open-ended ranges (start_residue is None) go first
            if r.start_residue is None:
                return 0, float("-inf")
            # Numeric residues come before string residues
            if isinstance(r.start_residue, int):
                return 1, r.start_residue
            else:
                return 2, str(r.start_residue)

        sorted_ranges = sorted(residue_ranges, key=sort_key)

        # Merge overlapping and adjacent ranges
        merged = []
        current = sorted_ranges[0]

        for next_range in sorted_ranges[1:]:
            # Handle cases where current or next range has None values
            current_start = current.start_residue
            current_end = current.end_residue
            next_start = next_range.start_residue
            next_end = next_range.end_residue

            # Skip ranges with None start_residue in the middle (shouldn't happen after sorting)
            if next_start is None:
                continue

            # Check if ranges can be merged (overlapping or adjacent)
            can_merge = False

            if current_end is None:
                # Current range is open-ended (goes to end of chain), so it subsumes any later range
                can_merge = True
            elif next_start is not None:
                # Only try to merge if both residues are the same type (both int or both str)
                # Calculate effective end for comparison
                effective_current_end = (
                    current_end if current_end is not None else current_start
                )
                if (
                    effective_current_end is not None
                    and isinstance(effective_current_end, type(next_start))
                    and isinstance(effective_current_end, int)
                    and next_start  # Only merge numeric ranges
                    <= effective_current_end + 1
                ):
                    can_merge = True

            if can_merge:
                # Merge the ranges
                new_start = current_start if current_start is not None else next_start

                # Calculate new end
                if current_end is None or next_end is None:
                    new_end = None  # Open-ended
                else:
                    new_end = max(current_end, next_end)

                current = ResidueRange(chain_code, new_start, new_end)
            else:
                # Cannot merge, add current to results and start new range
                merged.append(current)
                current = next_range

        # Add the last range
        merged.append(current)
        combined_ranges.extend(merged)

    # Sort final result by chain_code, then by start_residue
    def final_sort_key(r):
        chain_key = r.chain_code if r.chain_code is not None else ""
        # Handle mixed types in start_residue
        if r.start_residue is None:
            start_key = (0, float("-inf"))
        elif isinstance(r.start_residue, int):
            start_key = (1, r.start_residue)
        else:
            start_key = (2, str(r.start_residue))
        return chain_key, start_key

    return sorted(combined_ranges, key=final_sort_key)


def _combine_range_number_pairs(ranges: List[ResiduePair]) -> List[ResiduePair]:
    """
    Combine overlapping and adjacent range number pairs.

    This function takes a list of RangeNumberPair objects and merges ranges that:
    - Are overlapping (e.g., 1-5 and 3-8 become 1-8)
    - Are adjacent (e.g., 1-5 and 6-10 become 1-10)

    Args:
        ranges: List of RangeNumberPair objects to combine

    Returns:
        List of combined RangeNumberPair objects, sorted by start_residue
    """
    if not ranges:
        return []

    # Convert string residue numbers to integers for comparison, keeping track of original types
    numeric_ranges = []
    for range_obj in ranges:
        try:
            start_num = (
                int(range_obj.start_residue)
                if range_obj.start_residue is not None
                else None
            )
            end_num = (
                int(range_obj.end_residue)
                if range_obj.end_residue is not None
                else None
            )
            numeric_ranges.append((start_num, end_num, range_obj))
        except (ValueError, TypeError):
            # If we can't convert to numbers, treat as separate ranges that can't be combined
            numeric_ranges.append((None, None, range_obj))

    # Separate ranges that couldn't be converted to numbers - they won't be combined
    unconvertible_ranges = [
        original
        for start_num, end_num, original in numeric_ranges
        if start_num is None and original.start_residue is not None
    ]

    # Work with convertible ranges
    convertible_ranges = [
        (start_num, end_num, original)
        for start_num, end_num, original in numeric_ranges
        if not (start_num is None and original.start_residue is not None)
    ]

    if not convertible_ranges:
        return list(ranges)  # Return original ranges if none can be converted

    # Sort ranges by start_residue (handle None values)
    def sort_key(range_tuple):
        sort_key_start_num, sort_key_end_num, original = range_tuple
        # Open-ended ranges (start_residue is None) go first
        if sort_key_start_num is None:
            return float("-inf")
        return sort_key_start_num

    sorted_ranges = sorted(convertible_ranges, key=sort_key)

    # Merge overlapping and adjacent ranges
    merged = []
    if sorted_ranges:
        current_start, current_end, current_original = sorted_ranges[0]

        for next_start, next_end, next_original in sorted_ranges[1:]:
            # Skip ranges with None start_residue in the middle (shouldn't happen after sorting)
            if next_start is None:
                continue

            # Check if ranges can be merged (overlapping or adjacent)
            can_merge = False

            if current_end is None:
                # Current range is open-ended (from start to end), so it subsumes any later range
                can_merge = True
            elif next_start is not None:
                # Calculate effective end for comparison
                effective_current_end = (
                    current_end if current_end is not None else current_start
                )
                if (
                    effective_current_end is not None
                    and next_start <= effective_current_end + 1
                ):
                    can_merge = True

            if can_merge:
                # Merge the ranges
                new_start = current_start if current_start is not None else next_start

                # Calculate new end
                if current_end is None or next_end is None:
                    new_end = None  # Open-ended
                else:
                    new_end = max(current_end, next_end)

                current_start, current_end = new_start, new_end
            else:
                # Cannot merge, add current to results and start new range
                merged.append(ResiduePair(current_start, current_end))
                current_start, current_end = next_start, next_end

        # Add the last range
        merged.append(ResiduePair(current_start, current_end))

    # Add back the unconvertible ranges
    result = merged + [
        ResiduePair(r.start_residue, r.end_residue) for r in unconvertible_ranges
    ]

    # Sort final result by start_residue
    def final_sort_key(r):
        try:
            start_key = (
                int(r.start_residue) if r.start_residue is not None else float("-inf")
            )
        except (ValueError, TypeError):
            # Non-numeric ranges go to the end
            start_key = float("inf")
        return start_key

    return sorted(result, key=final_sort_key)


def parse_range_number_pairs(
    range_specs: List[str], range_separator: str = "..", no_combine: bool = False
) -> List[ResiduePair]:
    """
    Parse multiple range number pair specifications into RangeNumberPair objects.

    This function takes a list of range specifications and parses each one using
    parse_range_number_pair, then optionally combines overlapping and adjacent ranges.

    Args:
        range_specs: List of range specifications (e.g., ["1..5", "10", "15..20"])
        range_separator: Character sequence used to separate start and end residues (default: "..")
        no_combine: If True, disable combining of overlapping/adjacent ranges (default: False)

    Returns:
        List of RangeNumberPair objects, optionally combined and sorted

    Examples:
        parse_range_number_pairs(["1..5", "3..8"]) -> [RangeNumberPair(1, 8)]
        parse_range_number_pairs(["1..5", "3..8"], no_combine=True) -> [RangeNumberPair(1, 5), RangeNumberPair(3, 8)]
    """
    if not range_specs:
        return []

    ranges = []
    for range_spec in range_specs:
        range_spec = range_spec.strip()
        if not range_spec:
            continue

        # Parse individual range specification
        range_pair = parse_range_number_pair(range_spec, range_separator)
        ranges.append(range_pair)

    # Combine overlapping and adjacent ranges unless disabled
    if not no_combine:
        ranges = _combine_range_number_pairs(ranges)

    return ranges


def analyze_nef_entry_for_separator_conflicts(
    entry: Entry, chain_separator: str = ":", range_separator: str = "-"
) -> DetectedSeparatorConflicts:
    """
    Analyze a NEF Entry to determine if current separators conflict with data values.

    Scans all chain_codes and sequence_codes in the Entry to identify potential conflicts:
    - Chain codes containing the chain separator (like "A:B" when chain_separator is ":")
    - Chain codes containing the range separator (like "A-B" when range_separator is "-")
    - Sequence codes containing the chain separator (like "5:6" when chain_separator is ":")
    - Sequence codes containing the range separator (like "5-6" when range_separator is "-")

    Args:
        entry: NEF Entry to analyze
        chain_separator: Character that separates chain from residue (default: ":")
        range_separator: Character that separates start from end residue (default: "-")

    Returns:
        SeparatorConflictRequirement flags indicating what conflicts were found
    """
    result = DetectedSeparatorConflicts.OK

    chain_codes = set()
    sequence_codes = set()

    # Extract chain codes and sequence codes from all relevant loops
    for frame in entry.frame_list:
        for loop in frame:
            if not loop.tags:
                continue

            # Find chain_code and sequence_code tags (including indexed ones like chain_code_1)
            chain_indices = []
            sequence_indices = []

            for i, tag in enumerate(loop.tags):
                if tag == "chain_code" or tag.startswith("chain_code_"):
                    chain_indices.append(i)
                elif tag == "sequence_code" or tag.startswith("sequence_code_"):
                    sequence_indices.append(i)

            # Extract values from data rows
            for row in loop.data:
                for idx in chain_indices:
                    if idx < len(row) and row[idx] not in [".", "?", ""]:
                        chain_codes.add(row[idx])

                for idx in sequence_indices:
                    if idx < len(row) and row[idx] not in [".", "?", ""]:
                        sequence_codes.add(row[idx])

    # Check for separator conflicts in chain codes
    for chain_code in chain_codes:
        if chain_separator in chain_code:
            result |= DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_CHAIN_CODES
        if range_separator in chain_code:
            result |= DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_CHAIN_CODES

    # Check for separator conflicts in sequence codes
    for sequence_code in sequence_codes:
        sequence_code_str = str(sequence_code)
        if chain_separator in sequence_code_str:
            result |= DetectedSeparatorConflicts.CHAIN_SEPARATOR_IN_SEQUENCE_CODES
        if range_separator in sequence_code_str:
            result |= DetectedSeparatorConflicts.RANGE_SEPARATOR_IN_SEQUENCE_CODES

    return result


def parse_chain_offset_syntax(
    args: List[str], chain_separator: str = ":", range_separator: str = ".."
) -> List[RangeOffset]:
    """
    Parse chain offset syntax using pyparsing.

    Supports syntax like:
    - A:+5 (chain A, offset +5)
    - A:10..20+3 (chain A, residues 10-20, offset +3)
    - A+B+C:50..60+5:90..102-3 (chains A,B,C with multiple range offsets)

    Args:
        args: List of argument strings to parse
        chain_separator: Character separating chain groups from range/offset specs
        range_separator: Character sequence separating start/end residues in ranges

    Returns:
        List[RangeOffset]: Parsed range offset objects

    Raises:
        ChainOffsetSyntaxParsingError: If parsing fails
    """
    if not args:
        return []

    # Join all arguments and split by commas to handle comma-separated input
    all_args = " ".join(args)
    if "," in all_args:
        parts = [part.strip() for part in all_args.split(",") if part.strip()]
    else:
        parts = args

    try:
        # Build the pyparsing grammar
        grammar = _build_chain_offset_grammar(chain_separator, range_separator)

        results = []
        for part in parts:
            part = part.strip()
            if not part:
                continue

            try:
                tokens = grammar.parseString(part, parseAll=True)
                range_offsets = _convert_chain_offset_tokens(tokens)
                results.extend(range_offsets)
            except pp.ParseException as e:
                # Provide specific error messages based on the input pattern

                if part.endswith(":"):
                    raise ChainOffsetSyntaxParsingError(
                        f"Empty range/offset specification in operation '{part}'"
                    )
                elif ":" not in part:
                    raise ChainOffsetSyntaxParsingError(
                        f"Missing ':' separator in operation '{part}'"
                    )
                elif part.startswith(":"):
                    raise ChainOffsetSyntaxParsingError(
                        f"Empty chain group in operation '{part}'"
                    )
                elif ".." in part and part.count("..") > 1:

                    raise ChainOffsetSyntaxParsingError(
                        f"""\
                           Failed to parse range in operation '{part}': invalid range format
                           with multiple consecutive separators
                        """
                    )
                elif ":" in part:
                    range_part = part.split(":", 1)[
                        1
                    ]  # Get everything after the first ':'

                    # Check if range part contains letters mixed with digits (like 1A, 5A)
                    if re.search(r"\d+[A-Za-z]", range_part) or re.search(
                        r"[A-Za-z]+\d", range_part
                    ):
                        raise ChainOffsetSyntaxParsingError(
                            f"Failed to parse range in operation '{part}': residue ranges must be integers, not strings"
                        )

                    # Check if no offset is present (no + or - in the range part)
                    elif not any(c in range_part for c in "+-"):
                        raise ChainOffsetSyntaxParsingError(
                            f"No valid offset found in operation '{part}'"
                        )

                    # Check if offset contains letters (like +abc)
                    elif any(
                        c.isalpha()
                        for c in range_part.split("+")[-1] + range_part.split("-")[-1]
                        if c
                    ):
                        raise ChainOffsetSyntaxParsingError(
                            f"No valid offset found in operation '{part}': offset must be a signed integer"
                        )

                # Fallback for any other parsing errors
                raise ChainOffsetSyntaxParsingError(
                    f"Invalid chain offset syntax: '{part}' - {str(e)}"
                )

        return results

    except Exception as e:
        if isinstance(e, ChainOffsetSyntaxParsingError):
            raise
        raise ChainOffsetSyntaxParsingError(
            f"Error parsing chain offset syntax: {str(e)}"
        )


def _build_chain_offset_grammar(chain_separator: str, range_separator: str):
    """
    Build pyparsing grammar for chain offset syntax.

    Args:
        chain_separator: Character separating chain groups from range/offset specs
        range_separator: Character sequence separating start/end residues

    Returns:
        pyparsing grammar for chain offset syntax
    """
    # Define basic tokens
    integer = pp.Regex(r"[+-]?\d+").setParseAction(lambda t: int(t[0]))
    signed_integer = pp.Regex(r"[+-]\d+").setParseAction(lambda t: int(t[0]))

    # Chain names - avoid chain separator and +
    import re

    forbidden_chars = re.escape(chain_separator + "+")
    chain_name = pp.Regex(f"[^{forbidden_chars}\\s,]+")

    # Chain group: A or A+B+C
    chain_group = chain_name + pp.ZeroOrMore(pp.Suppress("+") + chain_name)

    # Range patterns with offset
    range_sep = pp.Literal(range_separator)

    # Full range + offset: "10..20+3"
    full_range_offset = (
        integer + range_sep + integer + signed_integer.copy()
    ).setParseAction(lambda t: ("range_offset", t[0], t[2], int(t[3])))

    # Open start range + offset: "..20+3"
    open_start_offset = (range_sep + integer + signed_integer.copy()).setParseAction(
        lambda t: ("range_offset", None, t[1], int(t[2]))
    )

    # Open end range + offset: "10..+3"
    open_end_offset = (integer + range_sep + signed_integer.copy()).setParseAction(
        lambda t: ("range_offset", t[0], None, int(t[2]))
    )

    # Single residue + offset: "15+1"
    single_residue_offset = (integer + signed_integer.copy()).setParseAction(
        lambda t: ("range_offset", t[0], t[0], int(t[1]))
    )

    # Just offset: "+2"
    just_offset = signed_integer.copy().setParseAction(
        lambda t: ("range_offset", None, None, int(t[0]))
    )

    # Try patterns in order of specificity
    range_offset_spec = (
        full_range_offset
        | open_start_offset
        | open_end_offset
        | single_residue_offset
        | just_offset
    )

    # Full specification: A+B+C:range_offset[:range_offset]*
    full_spec = (
        chain_group.setResultsName("chains")
        + pp.Suppress(chain_separator)
        + range_offset_spec
        + pp.ZeroOrMore(pp.Suppress(chain_separator) + range_offset_spec)
    )

    return full_spec


def _convert_chain_offset_tokens(tokens) -> List[RangeOffset]:
    """
    Convert parsed tokens to RangeOffset objects.

    Args:
        tokens: Parsed tokens from pyparsing

    Returns:
        List[RangeOffset]: Converted range offset objects
    """
    results = []

    # Extract chain names from the named result
    chain_names = []
    range_offset_specs = []

    # Parse tokens structure
    for token in tokens:
        if isinstance(token, str):
            chain_names.append(token)
        elif (
            isinstance(token, tuple) and len(token) >= 4 and token[0] == "range_offset"
        ):
            range_offset_specs.append(token)

    # If no range offset specs found, this is an error in parsing
    if not range_offset_specs:
        # Fallback: try to find all range_offset tuples in flattened token list
        def find_range_offsets(tokens_list):
            offsets = []
            for item in tokens_list:
                if (
                    isinstance(item, tuple)
                    and len(item) >= 4
                    and item[0] == "range_offset"
                ):
                    offsets.append(item)
                elif isinstance(item, (list, tuple)):
                    offsets.extend(find_range_offsets(item))
            return offsets

        range_offset_specs = find_range_offsets(tokens)

    # Create RangeOffset objects for each chain and each range spec
    for chain_code in chain_names:
        for spec in range_offset_specs:
            if len(spec) >= 4:
                _, start_residue, end_residue, offset = spec[:4]
                results.append(
                    RangeOffset(chain_code, start_residue, end_residue, offset)
                )

    return results


def _validate_and_convert_integer(value_str: str) -> int:
    """
    Validate that a string represents an integer and convert it.
    This enforces the requirement that residue ranges must be integers.
    """
    try:
        return int(value_str)
    except ValueError:
        raise ChainOffsetSyntaxParsingError(
            f"Residue ranges must be integers, got: '{value_str}'"
        )


def _calculate_actual_bounds(range_offsets: List[RangeOffset]) -> dict:
    """
    Calculate actual bounds for each chain from all range offsets to avoid using infinity.

    Args:
        range_offsets: List of RangeOffset objects

    Returns:
        dict: Dictionary mapping chain_code to (min_residue, max_residue) bounds
    """
    chain_bounds = {}

    for range_offset in range_offsets:
        chain_code = range_offset.chain_code
        if chain_code not in chain_bounds:
            chain_bounds[chain_code] = {"min_values": [], "max_values": []}

        # Collect actual numeric bounds from defined ranges
        if range_offset.start_residue is not None:
            chain_bounds[chain_code]["min_values"].append(range_offset.start_residue)
        if range_offset.end_residue is not None:
            chain_bounds[chain_code]["max_values"].append(range_offset.end_residue)

    # Calculate final bounds for each chain
    result = {}
    for chain_code, bounds_data in chain_bounds.items():
        min_values = bounds_data["min_values"]
        max_values = bounds_data["max_values"]

        # Use actual minimum and maximum, with reasonable defaults
        min_bound = min(min_values) - 1 if min_values else -100
        max_bound = max(max_values) + 1 if max_values else 1000

        result[chain_code] = (min_bound, max_bound)

    return result


def detect_overlapping_range_offsets(range_offsets: List[RangeOffset]) -> List[tuple]:
    """
    Detect overlapping RangeOffset objects that would map residues to the same final residue numbers.

    Two RangeOffset objects overlap if they have overlapping source residue ranges within the same
    chain and their target ranges (after applying offsets) overlap.

    Args:
        range_offsets: List of RangeOffset objects to check for overlaps

    Returns:
        List[tuple]: List of tuples (range_offset1, range_offset2, conflict_info) where each tuple
                    represents a pair of overlapping range offsets and conflict information
    """
    if not range_offsets:
        return []

    # Calculate actual bounds for each chain to avoid using infinity
    actual_bounds = _calculate_actual_bounds(range_offsets)

    overlaps = []

    # Compare each pair of range offsets
    for i in range(len(range_offsets)):
        for j in range(i + 1, len(range_offsets)):
            range1 = range_offsets[i]
            range2 = range_offsets[j]

            # Check if they affect the same chain
            if range1.chain_code != range2.chain_code:
                continue

            # Get the effective residue ranges for each offset
            chain_bound = actual_bounds[range1.chain_code]
            source_range1 = _get_effective_residue_range(range1, chain_bound)
            source_range2 = _get_effective_residue_range(range2, chain_bound)

            # Calculate target ranges after applying offsets
            target_range1 = _apply_offset_to_range(source_range1, range1.offset)
            target_range2 = _apply_offset_to_range(source_range2, range2.offset)

            # Check if target ranges overlap (this is what matters for conflicts)
            if _ranges_overlap(target_range1, target_range2):
                # Find the specific overlapping residues
                overlap_info = _calculate_overlap_details(
                    range1,
                    source_range1,
                    target_range1,
                    range2,
                    source_range2,
                    target_range2,
                )
                overlaps.append((range1, range2, overlap_info))

    return overlaps


def _get_effective_residue_range(
    range_offset: RangeOffset, chain_bounds: tuple
) -> tuple:
    """
    Get the effective residue range for a RangeOffset using actual bounds instead of infinity.

    Args:
        range_offset: RangeOffset object
        chain_bounds: tuple (min_bound, max_bound) for the chain

    Returns:
        tuple: (start_residue, end_residue) with concrete values
    """
    start = range_offset.start_residue
    end = range_offset.end_residue
    min_bound, max_bound = chain_bounds

    # Handle whole chain (both None) - use actual bounds
    if start is None and end is None:
        return min_bound, max_bound

    # Handle open-ended start (None, end)
    if start is None:
        return min_bound, end

    # Handle open-ended end (start, None)
    if end is None:
        return start, max_bound

    # Handle single residue (start == end)
    if start == end:
        return start, start

    # Handle ranges
    return start, end


def _ranges_overlap(range1: tuple, range2: tuple) -> bool:
    """
    Check if two residue ranges overlap using concrete bounds.

    Args:
        range1: tuple (start, end) for first range (concrete values)
        range2: tuple (start, end) for second range (concrete values)

    Returns:
        bool: True if ranges overlap
    """
    start1, end1 = range1
    start2, end2 = range2

    # With concrete bounds, we can do simple integer comparison
    # Ranges [a,b] and [c,d] overlap if max(a,c) <= min(b,d)
    return max(start1, start2) <= min(end1, end2)


def _apply_offset_to_range(source_range: tuple, offset: int) -> tuple:
    """
    Apply an offset to a residue range.

    Args:
        source_range: tuple (start, end) for source range
        offset: integer offset to apply

    Returns:
        tuple: (start + offset, end + offset) with None values preserved
    """
    start, end = source_range

    if start is None and end is None:
        return None, None  # Entire chain remains entire chain

    new_start = start + offset if start is not None else None
    new_end = end + offset if end is not None else None

    return new_start, new_end


def _calculate_overlap_details(
    range1: RangeOffset,
    source_range1: tuple,
    target_range1: tuple,
    range2: RangeOffset,
    source_range2: tuple,
    target_range2: tuple,
) -> dict:
    """
    Calculate detailed information about the overlap between two range offsets.

    Args:
        range1: First RangeOffset object
        source_range1: Source range for first offset
        target_range1: Target range for first offset
        range2: Second RangeOffset object
        source_range2: Source range for second offset
        target_range2: Target range for second offset

    Returns:
        dict: Detailed overlap information
    """
    return {
        "chain_code": range1.chain_code,
        "source_overlap": _find_range_intersection(source_range1, source_range2),
        "target_overlap": _find_range_intersection(target_range1, target_range2),
        "range1_source": source_range1,
        "range1_target": target_range1,
        "range1_offset": range1.offset,
        "range2_source": source_range2,
        "range2_target": target_range2,
        "range2_offset": range2.offset,
    }


def _find_range_intersection(range1: tuple, range2: tuple) -> Optional[tuple]:
    """
    Find the intersection of two ranges using concrete bounds.

    Args:
        range1: tuple (start, end) for first range
        range2: tuple (start, end) for second range

    Returns:
        tuple: (start, end) of intersection, or None if no intersection
    """
    start1, end1 = range1
    start2, end2 = range2

    # For intersection calculation with concrete bounds, we need to handle None values
    # by using very large/small concrete values instead of infinity

    # Use concrete extreme values instead of infinity
    min_bound = -100000  # Very small concrete value
    max_bound = 100000  # Very large concrete value

    # Replace None values with concrete bounds for calculation
    calc_start1 = start1 if start1 is not None else min_bound
    calc_end1 = end1 if end1 is not None else max_bound
    calc_start2 = start2 if start2 is not None else min_bound
    calc_end2 = end2 if end2 is not None else max_bound

    # Calculate intersection using concrete values
    intersection_start = max(calc_start1, calc_start2)
    intersection_end = min(calc_end1, calc_end2)

    # Check if intersection is valid
    if intersection_start > intersection_end:
        return None

    # Convert back to None for open-ended ranges if needed
    result_start = intersection_start if intersection_start != min_bound else None
    result_end = intersection_end if intersection_end != max_bound else None

    # Handle edge case where both original ranges had None values
    if start1 is None and start2 is None:
        result_start = None
    if end1 is None and end2 is None:
        result_end = None

    return result_start, result_end


def parse_frame_loop_and_tags(
    frame_spec: str,
    use_escapes: bool = False,
) -> FrameLoopAndTagSelectors:
    """\
    Parse a frame/loop/tag selector specification.

    The selector uses dot and colon to specify selection level:

        NO DOT (frame level):
            name        → entire saveframe (all tags + all loops)
            name:tag    → saveframe tag (metadata like sf_category)
            :tag        → saveframe tag in all frames

        HAS DOT (loop level):
            name.loop       → entire loop (all columns)
            name.loop:tag   → loop column
            .loop:tag       → loop column in all frames
            .:tag           → loop column in all loops/frames

    Empty parts default to wildcard (*):
        .loop == *.loop    (empty before dot)
        name. == name.*    (empty after dot)
        :tag == *:tag      (empty before colon)

    Args:
        frame_spec: Selector string
        use_escapes: Enable escape sequences (default False). When True, doubled separators become literals.

    Returns:
        FrameLoopAndTags with:
            - frame_name: Frame selector pattern (never None, default "*")
            - loop_name: None (frame tags only), "*" (all loops), or "name" (specific loop)
            - frame_tags: Saveframe-level tags (empty if loop-level selector)
            - loop_tags: Loop column tags (empty if frame-level selector)

    Examples:
        parse_frame_loop_and_tags("shift:sf_category")
        → FrameLoopAndTags(frame_name="shift", loop_name=None,
                           frame_tags=["sf_category"], loop_tags=[])

        parse_frame_loop_and_tags("shift.chemical_shift:atom_name")
        → FrameLoopAndTags(frame_name="shift", loop_name="chemical_shift",
                           frame_tags=[], loop_tags=["atom_name"])

        parse_frame_loop_and_tags(":sf_category")
        → FrameLoopAndTags(frame_name="*", loop_name=None,
                           frame_tags=["sf_category"], loop_tags=[])

    Escape Sequences (use_escapes=True):
        When use_escapes=True, doubled separators become literal characters in identifiers:
        - :: → literal :
        - .. → literal .
        - ,, → literal ,

        Examples:
            parse_frame_loop_and_tags("frame::name:tag", use_escapes=True)
            → FrameLoopAndTags(frame_name="frame:name", frame_tags=["tag"], ...)

            parse_frame_loop_and_tags("frame.loop..2:tag", use_escapes=True)
            → FrameLoopAndTags(frame_name="frame", loop_name="loop.2", ...)

            parse_frame_loop_and_tags("frame:tag1,,2,tag3", use_escapes=True)
            → FrameLoopAndTags(..., frame_tags=["tag1,2", "tag3"])
    """

    # Save original spec before processing
    original_spec = frame_spec

    # Pre-process for escape sequences
    frame_spec = _insert_frame_loop_tag_placeholders(frame_spec, use_escapes)

    grammar = _build_frame_loop_tag_grammar(use_escapes)

    parser_result = _parse_spec_with_grammar(
        frame_spec, grammar, original_spec, use_escapes
    )

    result = _build_frame_loop_selectors(frame_spec, parser_result)

    # Post-process to restore escaped characters
    result = _remove_frame_loop_tag_place_holders(result, use_escapes)

    return result


def _remove_frame_loop_tag_place_holders(
    result: FrameLoopAndTagSelectors, use_escapes: bool
) -> FrameLoopAndTagSelectors:
    if use_escapes:
        frame_name = result.frame_name
        loop_name = result.loop_name
        frame_tags = result.frame_tags
        loop_tags = result.loop_tags

        # Restore placeholders to literal separators
        for placeholder, char in _REVERSED_FRAME_LOOP_AND_TAG_PLACEHOLDERS.items():
            frame_name = frame_name.replace(placeholder, char)
            if loop_name and loop_name != "*":
                loop_name = loop_name.replace(placeholder, char)
            frame_tags = [tag.replace(placeholder, char) for tag in frame_tags]
            loop_tags = [tag.replace(placeholder, char) for tag in loop_tags]

        result = FrameLoopAndTagSelectors(frame_name, loop_name, frame_tags, loop_tags)
    return result


def _build_frame_loop_selectors(
    frame_spec, result: ParseResults
) -> FrameLoopAndTagSelectors:
    # Indices into ParseResults for the frame.loop:tags grammar
    FRAME_IDX = 0
    LOOP_IDX = 1
    FRAME_TAGS_IDX = 1
    LOOP_TAGS_IDX = 2

    def extract_tags_from_result(result: ParseResults, start_index: int) -> List[str]:
        """Extract and strip tags from parse results, defaulting to ["*"] if no tags present."""
        return (
            [tag.strip() for tag in result[start_index:]]
            if len(result) > start_index
            else ["*"]
        )

    # Parse results based on whether we have tags and/or explicit loop
    has_tag_separator = FRAME_TAG_SEPARATOR in frame_spec
    has_loop_separator = FRAME_LOOP_SEPARATOR in frame_spec

    # Set defaults
    frame_name = result[FRAME_IDX]
    loop_name = None
    frame_tags = []
    loop_tags = []

    if has_loop_separator and has_tag_separator:
        # frame.loop:tags → loop columns
        loop_name = result[LOOP_IDX]
        loop_tags = extract_tags_from_result(result, LOOP_TAGS_IDX)
    elif has_loop_separator:
        # frame.loop → entire loop
        loop_name = result[LOOP_IDX]
        loop_tags = ["*"]
    elif has_tag_separator:
        # frame:tags → frame tags ONLY (not loop columns)
        frame_tags = extract_tags_from_result(result, FRAME_TAGS_IDX)
    else:
        # frame → entire frame (all tags + all loops)
        loop_name = "*"
        frame_tags = ["*"]
        loop_tags = ["*"]

    return FrameLoopAndTagSelectors(frame_name, loop_name, frame_tags, loop_tags)


def _detect_escape_sequences(spec: str) -> str:
    """\
    Detect which escape sequences are present in the spec.

    Returns:
        Empty string if no escapes found, otherwise a descriptive message about the escape sequences
    """
    found_escapes = [
        seq for seq in _FRAME_LOOP_AND_TAG_PLACEHOLDERS.keys() if seq in spec
    ]
    if not found_escapes:
        return ""

    # Build message describing the escape sequences
    if len(found_escapes) == 1:
        seq = found_escapes[0]
        char = seq[0]
        result = f"I found {seq} which looks like an escape sequence for {char} when --use-escapes is active"
    else:
        # Multiple escapes: "I found ::, .. and ,, which look like escape sequences for
        # :, . and , when --use-escapes is active"
        chars = [seq[0] for seq in found_escapes]

        # Format escape sequences list
        if len(found_escapes) == 2:
            escapes_str = f"{found_escapes[0]} and {found_escapes[1]}"
            chars_str = f"{chars[0]} and {chars[1]}"
        else:
            escapes_str = ", ".join(found_escapes[:-1]) + f" and {found_escapes[-1]}"
            chars_str = ", ".join(chars[:-1]) + f" and {chars[-1]}"

        result = f"I found {escapes_str} which look like escape sequences for {chars_str} when --use-escapes is active"

    return result


def _insert_frame_loop_tag_placeholders(
    frame_spec: str | Any, use_escapes: bool
) -> Any:
    if use_escapes:
        for seq, placeholder in _FRAME_LOOP_AND_TAG_PLACEHOLDERS.items():
            frame_spec = frame_spec.replace(seq, placeholder)
    return frame_spec


def _parse_spec_with_grammar(
    frame_spec: str,
    grammar: ParserElement | StringEnd,
    original_spec: str,
    use_escapes: bool,
) -> ParseResults:
    try:
        result = grammar.parseString(frame_spec)
    except pp.ParseException as e:
        # Check for common error cases
        if frame_spec.count(FRAME_TAG_SEPARATOR) > 1:
            count = frame_spec.count(FRAME_TAG_SEPARATOR)
            reason = f"you have too many {FRAME_TAG_SEPARATOR} separators [{count}], you should have 1"
            if use_escapes:
                msg = f". To use a literal '{FRAME_TAG_SEPARATOR}' character, escape it as '{FRAME_TAG_SEPARATOR * 2}'"
                reason += msg
            else:
                # Check if escape sequences are present
                escape_msg = _detect_escape_sequences(original_spec)
                if escape_msg:
                    reason += f". Did you forget --use-escapes? ({escape_msg})"
        elif FRAME_TAG_SEPARATOR in frame_spec:
            # Check if tags are empty (after the separator)
            tags_part = frame_spec.split(FRAME_TAG_SEPARATOR, 1)[1]
            if not tags_part.strip():
                reason = f"tags cannot be empty after '{FRAME_TAG_SEPARATOR}'"
            else:
                reason = f"invalid syntax: {str(e)}"
        else:
            reason = f"invalid syntax: {str(e)}"

        # Check for escape sequences when use_escapes is False
        if not use_escapes:
            escape_msg = _detect_escape_sequences(original_spec)
            if escape_msg and "Did you forget --use-escapes?" not in reason:
                reason += f". Did you forget --use-escapes? ({escape_msg})"

        raise BadFrameLoopTagSyntaxException(original_spec, reason)
    return result


def _build_frame_loop_tag_grammar(use_escapes: bool) -> ParserElement | StringEnd:
    # Build pyparsing grammar
    frame_tag_sep = pp.Literal(FRAME_TAG_SEPARATOR).suppress()
    frame_loop_sep = pp.Literal(FRAME_LOOP_SEPARATOR)
    tag_sep = pp.Literal(TAG_LIST_SEPARATOR).suppress()

    # Frame and loop identifiers (anything except the special separators)
    # When using escapes, allow placeholder characters (null bytes from escape processing)
    forbidden_chars = FRAME_TAG_SEPARATOR + FRAME_LOOP_SEPARATOR + TAG_LIST_SEPARATOR
    if use_escapes:
        # Allow any character including placeholders (null bytes from escape processing)
        identifier = pp.CharsNotIn(forbidden_chars)
    else:
        identifier = pp.Word(pp.printables, excludeChars=forbidden_chars)

    # Tag names (anything except separators, with optional whitespace)
    tag_name = pp.Combine(
        pp.Optional(pp.White()) + identifier + pp.Optional(pp.White())
    )
    tag_list = tag_name + pp.ZeroOrMore(tag_sep + tag_name)

    # Frame.Loop patterns
    frame_loop_explicit = (
        pp.Optional(identifier, default="*")
        + frame_loop_sep.suppress()
        + pp.Optional(identifier, default="*")
    )
    frame_only = pp.Optional(identifier, default="*")

    frame_loop_part = frame_loop_explicit | frame_only

    # Complete grammar: frame[.loop][:tag1,tag2,...] (tags optional)
    grammar = frame_loop_part + pp.Optional(frame_tag_sep + tag_list) + pp.StringEnd()
    return grammar


def parse_frame_loop_selector(pattern: str, separator: str = ".") -> Tuple[str, str]:
    """Parse a frame.loop pattern into frame and loop selectors.

    Handles cases:
    - 'frame.loop' → ('frame', 'loop')
    - 'frame' → ('frame', '*')
    - '.loop' → ('*', 'loop')
    - 'frame.' → ('frame', '*')
    - '.' → ('*', '*')
    - '' → ('*', '*')

    Args:
        pattern: Pattern string in frame.loop format
        separator: Separator between frame and loop (default '.')

    Returns:
        Tuple of (frame_selector, loop_selector)
    """
    if not pattern or pattern == separator:
        return "*", "*"

    if separator not in pattern:
        return pattern, "*"

    frame_part, loop_part = pattern.split(separator, 1)
    frame_selector = frame_part if frame_part else "*"
    loop_selector = loop_part if loop_part else "*"
    return frame_selector, loop_selector


def _get_available_separators(
    entry_or_frames: Union[Entry, List[Saveframe]], separators: List[str]
) -> List[str]:
    """Get list of available separators from POSSIBLE_SEPARATORS that aren't in use.

    Args:
        entry_or_frames: NEF entry or list of frames to check
        separators: names and values of separators

    Returns:
        List of available separators
    """

    frame_list = (
        entry_or_frames.frame_list
        if isinstance(entry_or_frames, Entry)
        else entry_or_frames
    )

    # Collect all text from entry
    all_text_parts = []
    for frame in frame_list:
        # note a frame_name implicitly contains it's category so no need for both...
        all_text_parts.append(frame.name)
        for loop in frame.loops:
            all_text_parts.append(loop.category)
            all_text_parts.extend(loop.tags)

    all_text_characters = set("".join(all_text_parts))

    # Find separators that aren't in use
    used_separators = set(separators)
    available = set(POSSIBLE_SEPARATORS) - used_separators - all_text_characters

    return sorted(available)


def _validate_separators_are_unique_or_get_message(
    separators: Dict[str, str]
) -> Optional[str]:
    """Validate that input parsing separators are different from each other.

    Args:
       separators: Dictionary of separator names and separator values

    Returns:
        Error message if conflicts found, None otherwise
    """
    conflicts = []

    # Get all separator name-value pairs as a list
    separator_items = list(separators.items())

    # Compare each separator with all others that come after it
    for i, (name1, sep1) in enumerate(separator_items):
        for name2, sep2 in separator_items[i + 1 :]:
            if sep1 == sep2:
                conflicts.append(f"'{name1}' and '{name2}' both use '{sep1}'")

    msg = None
    if conflicts:
        msg = f"""\
            There are separator conflict: the following separators cannot be identical:
                {f',{NEWLINE}'.join(conflicts)}
            Please use different separators.
        """

    return msg


def format_residue_range(residue_range: ResidueRange) -> str:
    """Format a ResidueRange object as a human-readable string (e.g. A:10..20).

    Args:
        residue_range: ResidueRange to format

    Returns:
        Formatted residue range string
    """
    chain = residue_range.chain_code or "*"
    start = residue_range.start_residue
    end = residue_range.end_residue

    if start == end:
        return f"{chain}:{start}"
    elif start is None:
        return f"{chain}:..{end}"
    elif end is None:
        return f"{chain}:{start}.."
    else:
        return f"{chain}:{start}..{end}"


def expand_residue_range(residue_range: ResidueRange) -> List[int]:
    """Expand a residue range into a list of integer sequence codes.

    Only works for closed integer ranges (e.g. 10..20). For open-ended or string ranges,
    returns an empty list as they cannot be fully expanded.

    Args:
        residue_range: ResidueRange object to expand

    Returns:
        List of integers within the range, or empty list if unexpandable
    """
    start = residue_range.start_residue
    end = residue_range.end_residue

    if start is None or end is None:
        return []

    if not is_int(start) or not is_int(end):
        return []

    return list(range(int(start), int(end) + 1))


def validate_residue_ranges_in_system(
    entry: Entry,
    residue_ranges: List[ResidueRange],
) -> List[ResidueRange]:
    """Identify residue ranges that are not present in the entry's molecular system.

    Checks only closed integer ranges that can be expanded.

    Args:
        entry: NEF entry containing the molecular system
        residue_ranges: List of ResidueRange objects to validate

    Returns:
        List of ResidueRange objects not found in the molecular system
    """
    sequence = sequence_from_entry(entry)
    if not sequence:
        return []

    system_residues = {(res.chain_code, res.sequence_code) for res in sequence}

    ranges_not_found = []

    for residue_range in residue_ranges:
        chain_code = residue_range.chain_code
        if chain_code is None:
            continue

        expanded = expand_residue_range(residue_range)
        if not expanded:
            continue

        range_found = False
        for res_code in expanded:
            if (chain_code, res_code) in system_residues:
                range_found = True
                break

        if not range_found:
            ranges_not_found.append(residue_range)

    return ranges_not_found


def parse_selector_lists(
    selectors: List[str], use_escapes: bool = False, no_initial_selection: bool = False
) -> List[Tuple[SelectorAction, Union[str, AllNamespacesSentinel]]]:
    r"""
    Parse a set of selectors with inclusion/exclusion prefixes and optional escape sequences.
    The implimentation assumes that you have everything selected and want a set of operations that
    act on thsi initial selection. This includes the falg no_initial_selection which, when True,
    adds an action to clear the selection list.

    The no_initial_selection flag controls the initial state:
    - no_initial_selection=False (normal): Start empty
    - no_initial_selection=True (empty): Start with all

    Args:
        selectors: List of patterns (may include +/-/! prefixes)
        use_escapes: If True, process escape sequences (\, → ,)

    Returns:
        List of tuples (action, pattern) where:
        - action is SelectorAction.INCLUDE or SelectorAction.EXCLUDE
        - pattern is ALL_NAMESPACES sentinel or namespace_name string
        - When no_initial_selection=True, prepends (EXCLUDE, ALL_NAMESPACES) to start with all

    Examples:
        ['nef'] → [(INCLUDE, 'nef')]  # start empty, add nef
        no_initial_selection=True, ['nef'] → [(EXCLUDE, ALL_NAMESPACES), (INCLUDE, 'nef')]  # start none, add nef
        ['+nef', '-custom'] → [(INCLUDE, 'nef'), (EXCLUDE, 'custom')]
        ['-'] → [(EXCLUDE, ALL_NAMESPACES)]  # clear all
        no_initial_selection=True, ['+nef'] → [(EXCLUDE, ALL_NAMESPACES), (INCLUDE, 'nef')]
    """

    result = []

    if no_initial_selection:
        result.append((SelectorAction.EXCLUDE, ALL_NAMESPACES))

    for selector_str in selectors:
        # Step 1: Tokenize into (was_first_char_escaped, content)
        chunks = []
        current_chunk = []
        escaped = False
        first_char_escaped = False
        is_first_in_chunk = True

        for char in selector_str:
            if use_escapes and not escaped and char == "\\":
                escaped = True
                continue

            if not escaped and char == ",":
                # Finalize the current item before the comma
                chunks.append((first_char_escaped, "".join(current_chunk)))
                # Reset for next item
                current_chunk = []
                is_first_in_chunk = True
                first_char_escaped = False
            else:
                if is_first_in_chunk:
                    first_char_escaped = escaped
                    is_first_in_chunk = False

                current_chunk.append(char)
                escaped = False

        # Add the final item in the string
        chunks.append((first_char_escaped, "".join(current_chunk)))

        # Step 2: Resolve Actions
        for was_escaped, item in chunks:
            if not item:
                continue

            # A prefix is ONLY a prefix if it wasn't escaped
            if not was_escaped:
                if item == "+":
                    result.append((SelectorAction.INCLUDE, ALL_NAMESPACES))
                    continue
                if item == "-" or item == "!":
                    result.append((SelectorAction.EXCLUDE, ALL_NAMESPACES))
                    continue
                if item.startswith("+"):
                    result.append((SelectorAction.INCLUDE, item[1:]))
                    continue
                if item.startswith("-") or item.startswith("!"):
                    result.append((SelectorAction.EXCLUDE, item[1:]))
                    continue

            # If escaped OR no prefix: it's a bare name (always INCLUDE)
            result.append((SelectorAction.INCLUDE, item))

    return result
