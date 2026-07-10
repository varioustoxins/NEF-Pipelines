import csv
import io
from collections import defaultdict
from enum import auto
from textwrap import dedent

import clevercsv
from strenum import StrEnum

from nef_pipelines.tools.columns.columns_lib import (
    TabularFormatResult,
    detect_tabular_format,
)


class CsvLikeFormats(StrEnum):
    """CSV-like formats supported for reading."""

    CSV = auto()
    TSV = auto()
    SSV = auto()
    AUTO = auto()
    csv = auto()
    tsv = auto()
    ssv = auto()
    auto = auto()


class CsvParseError(Exception):
    """Raised when CSV parsing fails due to validation errors."""

    pass


HELP_FOR_FORMATS = """\
    CSV like formats that can be read [CSV: comma separated variables, TSV tab separated variables,
    SSV space separated variables, AUTO read file and guess format from contents]
"""

COLUMN_SEPARATORS_MAY_HAVE_CHANGED = (
    "note: column separators shown here may different to those in the original file..."
)


def _get_csv_reader_for_format(csv_format, csv_fp, encoding):
    """Return a csv.reader configured for the given format."""
    if csv_format == CsvLikeFormats.AUTO:
        content = csv_fp.read()
        lines = content.splitlines()

        if not lines:
            return iter([])

        format_result = detect_tabular_format(lines)

        if format_result == TabularFormatResult.RAGGED_WHITESPACE:
            normalized_lines = []
            for line in lines:
                fields = line.split()
                normalized_lines.append("\t".join(fields))
            normalized = "\n".join(normalized_lines)
            reader = csv.reader(io.StringIO(normalized), delimiter="\t")
        elif format_result == TabularFormatResult.CLEVERCSV_AUTO:
            reader = clevercsv.reader(io.StringIO(content))
        elif format_result == TabularFormatResult.UNKNOWN_OR_MESSY:
            reader = csv.reader(io.StringIO(content))
        else:
            reader = clevercsv.reader(io.StringIO(content), dialect=format_result)
    elif csv_format == CsvLikeFormats.TSV:
        reader = csv.reader(csv_fp, delimiter="\t")
    elif csv_format == CsvLikeFormats.CSV:
        reader = csv.reader(csv_fp)
    elif csv_format == CsvLikeFormats.SSV:
        reader = csv.reader(csv_fp, delimiter=" ", skipinitialspace=True)
    else:
        reader = csv.reader(csv_fp, delimiter=" ", skipinitialspace=True)
    return reader


def _format_missing_residues_section(unknown_residues):
    """Format missing residues grouped by chain with overflow handling.

    Returns:
        Formatted string showing missing residues (max 20 per chain, 10 per line)
    """
    missing_by_chain = defaultdict(list)
    for chain, seq in sorted(unknown_residues):
        missing_by_chain[chain].append(seq)

    MAX_PER_CHAIN = 20
    RES_PER_LINE = 10
    missing_residue_lines = []
    total_overflow = 0

    for chain in sorted(missing_by_chain.keys()):
        missing_residue_lines.append(f"\nchain {chain}")
        residues = missing_by_chain[chain]
        shown = residues[:MAX_PER_CHAIN]
        overflow = len(residues) - MAX_PER_CHAIN

        if overflow > 0:
            total_overflow += overflow

        for i in range(0, len(shown), RES_PER_LINE):
            line_residues = shown[i : i + RES_PER_LINE]
            formatted = "  " + "  ".join(f"{seq:>4}" for seq in line_residues)
            missing_residue_lines.append(formatted)

        if overflow > 0:
            missing_residue_lines.append(f"  ... and {overflow} more")

    if total_overflow > 0:
        missing_residue_lines.append(
            f"\n[total of {total_overflow} more residues not shown above]"
        )

    return "\n".join(missing_residue_lines)


def _format_sequence_section(lookup):
    """Format sequence grouped by chain for display.

    Returns:
        Tuple of (formatted_string, num_chains)
    """
    sequence_chains = defaultdict(list)
    for (chain, seq), res_name in sorted(lookup.items()):
        sequence_chains[chain].append((seq, res_name))

    RES_PER_LINE = 10
    sequence_lines = []

    for chain in sorted(sequence_chains.keys()):
        sequence_lines.append(f"\nchain {chain}")
        residues = sequence_chains[chain]

        for i in range(0, len(residues), RES_PER_LINE):
            line_residues = residues[i : i + RES_PER_LINE]
            formatted = ["  "]
            for seq, res_name in line_residues:
                formatted.append(f"{seq:>4} {res_name:<3}")
            sequence_lines.append(" ".join(formatted))

    return "\n".join(sequence_lines), len(sequence_chains)


def _unknown_residues_to_warning(unknown_residues, lookup):
    """Format unknown residues as warning message.

    Args:
        unknown_residues: Set of (chain_code, sequence_code) tuples for residues not found
        lookup: Sequence lookup dictionary to show available residues

    Returns:
        Warning string, or empty string if no unknown residues
    """
    if not unknown_residues:
        return ""

    missing_section = _format_missing_residues_section(unknown_residues)
    sequence_section, num_chains = _format_sequence_section(lookup)

    sequence_header = "The Sequence was:" if num_chains == 1 else "The Sequences were:"

    warning_msg = f"""
        The following residues were not found in the input sequence
        and have been imported with residue_name set to '.' (UNUSED):

        The missing residues were:
        {missing_section}

        {sequence_header}
        {sequence_section}
    """

    return dedent(warning_msg).strip()
