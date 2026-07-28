"""CSV reading utilities for NEF-Pipelines.

Public API:
    Enums & Constants:
        - CsvLikeFormats: CSV, TSV, SSV, AUTO
        - HELP_FOR_FORMATS: Help text for format option
        - ENCODING: UTF-8 with BOM support

    Loading:
        - read_csv(): Main CSV reading function with normalization
        - parse_csv_text(): Parse CSV text without file I/O
        - parse_csv_as_dicts(): Parse CSV text and return dicts

    Exceptions:
        - CsvParseError: Raised on CSV validation errors
        - TabularDataError: Base exception for tabular data operations
        - ColumnNotFoundError: Raised when column not found

    Utilities:
        - get_column_or_default(): Extract column with fallback
        - build_column_offsets(): Map column names to indices
        - extract_column_from_text(): Extract single column from text
        - detect_tabular_format(): Detect format of tabular text
"""

import csv
import io
from enum import auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import clevercsv
from clevercsv.dialect import SimpleDialect
from strenum import LowercaseStrEnum, StrEnum

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.util import escape_spaces_with_underscore

# Constants
ENCODING = "utf-8-sig"

HELP_FOR_FORMATS = """\
    CSV like formats that can be read [CSV: comma separated variables, TSV tab separated variables,
    SSV space separated variables, AUTO read file and guess format from contents]
"""

COLUMN_SEPARATORS_MAY_HAVE_CHANGED = (
    "note: column separators shown here may different to those in the original file..."
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


class TabularFormatResult(LowercaseStrEnum):
    """Format detection results for tabular data files."""

    RAGGED_WHITESPACE = auto()
    CLEVERCSV_AUTO = auto()
    UNKNOWN_OR_MESSY = auto()


class CsvParseError(Exception):
    """Raised when CSV parsing fails due to validation errors."""

    pass


class TabularDataError(Exception):
    """Base exception for tabular data operations."""

    pass


class ColumnNotFoundError(TabularDataError):
    """Raised when a requested column is not found in tabular data."""

    pass


def get_column_or_default(
    row: List[str],
    tags: List[str],
    column_name: str,
    default: str = UNUSED,
) -> str:
    """Extract column value from row with fallback to default.

    Args:
        row: Data row (list of string values)
        tags: Column names from header
        column_name: Name of column to extract
        default: Value to return if column absent or empty

    Returns:
        Column value if present and non-empty, otherwise default
    """
    try:
        idx = tags.index(column_name)
        value = row[idx] if idx < len(row) else default
        return value if value and value.strip() else default
    except ValueError:
        return default


def build_column_offsets(tags: List[str]) -> Dict[str, int]:
    """Build mapping of column names to their indices.

    Args:
        tags: Column names from header

    Returns:
        Dictionary mapping column name → index position
    """
    return {tag: i for i, tag in enumerate(tags)}


def read_csv(
    csv_file: Path,
    csv_format: CsvLikeFormats = CsvLikeFormats.AUTO,
    skip: int = 0,
    comment: Union[str, List[str]] = "",
    header_skip: int = 0,
    tail_skip: int = 0,
) -> Tuple[List[str], List[List[str]], List[str]]:
    """Read CSV file and return (tags, data_rows, warnings).

    Args:
        csv_file: Path to CSV file
        csv_format: Format type (CSV, TSV, SSV, or AUTO for detection)
        skip: Number of header rows to skip after column headers
        comment: Prefix(es) for comment lines to ignore (string or list)
        header_skip: Number of rows to skip before reading column headers
        tail_skip: Number of trailing rows to skip from the end

    Returns:
        (column_tags, data_rows, warnings)
        - column_tags: Normalized column names (spaces → underscores)
        - data_rows: List of data rows (each row is list of strings)
        - warnings: List of warning messages (header normalization, etc.)

    Raises:
        CsvParseError: If CSV file is empty or cannot be read
    """
    try:
        text = csv_file.read_text(encoding=ENCODING)
    except (OSError, PermissionError, UnicodeDecodeError) as e:
        raise CsvParseError(f"failed to read {csv_file}: {e}") from e

    return parse_csv_text(
        text, csv_format, skip, comment, header_skip, tail_skip, source_path=csv_file
    )


def parse_csv_text(
    text: str,
    csv_format: CsvLikeFormats = CsvLikeFormats.AUTO,
    skip: int = 0,
    comment: Union[str, List[str]] = "",
    header_skip: int = 0,
    skip_tail: int = 0,
    source_path: Optional[Path] = None,
    has_header: bool = True,
) -> Tuple[List[str], List[List[str]], List[str]]:
    """Parse CSV text and return (tags, data_rows, warnings).

    Args:
        text: CSV text content
        csv_format: Format type (CSV, TSV, SSV, or AUTO for detection)
        skip: Number of header rows to skip after column headers
        comment: Prefix(es) for comment lines to ignore (string or list)
        header_skip: Number of rows to skip before reading column headers
        skip_tail: Number of trailing rows to skip from the end
        source_path: Optional path for error messages
        has_header: If True the first remaining row names the columns; if False the columns are
            named '1', '2', ... by position and every row is treated as data

    Returns:
        (column_tags, data_rows, warnings)
        - column_tags: Normalized column names (spaces → underscores)
        - data_rows: List of data rows (each row is list of strings)
        - warnings: List of warning messages (header normalization, etc.)

    Raises:
        CsvParseError: If CSV text is empty after filtering
    """
    # Apply header_skip first (skip rows BEFORE reading headers)
    filtered_text, _, _ = _apply_skip_and_comment(
        text, skip=header_skip, comment=comment, skip_tail=0
    )

    # Parse CSV rows from filtered text
    rows = _parse_csv_rows_from_text(filtered_text, csv_format)

    if not rows:
        source = f" in {source_path}" if source_path else ""
        raise CsvParseError(f"CSV is empty after filtering{source}")

    warnings = []
    if has_header:
        # Extract header row
        header_row = rows[0]
        original_tags = [tag.strip() for tag in header_row]

        # Normalize tags (spaces → underscores) and collect warnings
        normalized_tags = [escape_spaces_with_underscore(tag) for tag in original_tags]
        for orig, norm in zip(original_tags, normalized_tags):
            if orig != norm:
                warnings.append(f"normalized column header '{orig}' → '{norm}'")

        # Extract data rows (skip header + additional skip rows)
        data_start = 1 + skip
    else:
        # No header row: synthesise 1-based positional names and treat every row as data
        normalized_tags = [str(i + 1) for i in range(len(rows[0]))]
        data_start = skip

    data_rows = rows[data_start:]

    # Apply skip_tail to remove trailing rows
    if skip_tail > 0 and len(data_rows) > skip_tail:
        data_rows = data_rows[:-skip_tail]

    return normalized_tags, data_rows, warnings


def parse_csv_as_dicts(
    text: str,
    csv_format: CsvLikeFormats = CsvLikeFormats.AUTO,
    skip: int = 0,
    comment: Union[str, List[str]] = "",
    header_skip: int = 0,
    skip_tail: int = 0,
    source_path: Optional[Path] = None,
    has_header: bool = True,
) -> Tuple[List[Dict[str, str]], List[str], List[str]]:
    """Parse CSV text and return list of dicts (one per row).

    Args:
        text: CSV text content
        csv_format: Format type (CSV, TSV, SSV, or AUTO for detection)
        skip: Number of header rows to skip after column headers
        comment: Prefix(es) for comment lines to ignore (string or list)
        header_skip: Number of rows to skip before reading column headers
        skip_tail: Number of trailing rows to skip from the end
        source_path: Optional path for error messages
        has_header: If True the first remaining row names the columns; if False the columns are
            named '1', '2', ... by position and every row is treated as data

    Returns:
        (dict_rows, tags, warnings)
        - dict_rows: List of dicts (keys = normalized column names)
        - tags: Normalized column names
        - warnings: List of warning messages

    Raises:
        CsvParseError: If CSV text is empty after filtering
    """
    tags, list_rows, warnings = parse_csv_text(
        text, csv_format, skip, comment, header_skip, skip_tail, source_path, has_header
    )

    # Convert list rows to dicts
    dict_rows = [dict(zip(tags, row)) for row in list_rows]

    return dict_rows, tags, warnings


def detect_tabular_format(
    lines: List[str],
) -> Union[TabularFormatResult, SimpleDialect]:
    """Detect format of tabular text from lines.

    Uses heuristics to classify as:
    - RAGGED_WHITESPACE: Fixed-width-like spacing
    - CLEVERCSV_AUTO: Let clevercsv auto-detect
    - UNKNOWN_OR_MESSY: Fallback to standard csv.reader
    - SimpleDialect: Detected delimiter/quoting

    Args:
        lines: Lines of text to analyze

    Returns:
        TabularFormatResult enum or SimpleDialect for proper delimited data
    """
    if not lines:
        return TabularFormatResult.UNKNOWN_OR_MESSY

    # Join lines into text for clevercsv detection
    text = "\n".join(lines)

    # Check field counts first (before clevercsv)
    field_counts = [len(line.split()) for line in lines if line.strip()]
    all_same_count = field_counts and len(set(field_counts)) == 1

    # Check if it looks like whitespace-delimited data
    has_commas = any("," in line for line in lines)
    has_tabs = any("\t" in line for line in lines)
    has_multiple_spaces = any("  " in line for line in lines if line.strip())

    # Try clevercsv detector
    try:
        dialect = clevercsv.Sniffer().sniff(text)
        if dialect and hasattr(dialect, "delimiter"):
            # If space delimiter detected, validate field consistency
            # OR accept as ragged whitespace if no other delimiters
            if dialect.delimiter == " ":
                if (
                    not all_same_count
                    and not has_commas
                    and not has_tabs
                    and has_multiple_spaces
                ):
                    # Ragged whitespace - varying field counts OK
                    return TabularFormatResult.RAGGED_WHITESPACE
                elif not all_same_count:
                    # Inconsistent and not ragged whitespace
                    return TabularFormatResult.UNKNOWN_OR_MESSY
            return dialect
    except (clevercsv.Error, Exception):
        pass

    # Check for ragged whitespace (whitespace-aligned)
    # If no commas/tabs and has multiple spaces, treat as ragged whitespace
    if not has_commas and not has_tabs and has_multiple_spaces:
        return TabularFormatResult.RAGGED_WHITESPACE

    # Default: let clevercsv try auto-detection
    return TabularFormatResult.CLEVERCSV_AUTO


def _parse_csv_rows_from_text(text: str, csv_format: CsvLikeFormats) -> List[List[str]]:
    """Parse CSV text into rows using specified format.

    Internal helper - returns raw rows without header normalization.

    Args:
        text: CSV text to parse
        csv_format: Format type (CSV, TSV, SSV, or AUTO)

    Returns:
        List of rows (each row is a list of strings)
    """
    if csv_format == CsvLikeFormats.AUTO:
        lines = text.splitlines()
        format_result = detect_tabular_format(lines)

        # Check if detected dialect is space-based (needs normalization like RAGGED_WHITESPACE)
        is_space_dialect = (
            hasattr(format_result, "delimiter") and format_result.delimiter == " "
        )

        if format_result == TabularFormatResult.RAGGED_WHITESPACE or is_space_dialect:
            # Split each line on whitespace, join with tabs
            # This collapses multiple spaces and handles space-based dialects correctly
            normalized_lines = [
                "\t".join(line.split()) for line in lines if line.strip()
            ]
            text = "\n".join(normalized_lines)
            reader = csv.reader(io.StringIO(text), delimiter="\t")
        elif format_result == TabularFormatResult.CLEVERCSV_AUTO:
            reader = clevercsv.reader(io.StringIO(text))
        elif format_result == TabularFormatResult.UNKNOWN_OR_MESSY:
            reader = csv.reader(io.StringIO(text))
        else:
            reader = clevercsv.reader(io.StringIO(text), dialect=format_result)
    elif csv_format == CsvLikeFormats.TSV:
        reader = csv.reader(io.StringIO(text), delimiter="\t")
    elif csv_format == CsvLikeFormats.CSV:
        reader = csv.reader(io.StringIO(text))
    elif csv_format == CsvLikeFormats.SSV:
        reader = csv.reader(io.StringIO(text), delimiter=" ", skipinitialspace=True)
    else:
        reader = csv.reader(io.StringIO(text), delimiter=" ", skipinitialspace=True)

    return list(reader)


def _apply_skip_and_comment(
    raw_text: str,
    skip: int,
    comment: Union[str, List[str]],
    skip_tail: int = 0,
) -> Tuple[str, int, int]:
    """Strip comment lines, skip leading/trailing rows, and return filtered text with line counts.

    Args:
        raw_text: Input text
        skip: Number of leading non-empty rows to skip
        comment: Comment prefix(es) to filter (string or list)
        skip_tail: Number of trailing non-empty rows to skip

    Returns:
        Tuple of (filtered_text, num_comment_lines_removed, num_blank_lines_removed)
    """
    original_lines = raw_text.splitlines()
    num_blank = sum(1 for line in original_lines if not line.strip())

    # Normalize comment to list
    if isinstance(comment, str):
        comment_prefixes = [comment] if comment else []
    else:
        comment_prefixes = comment if comment else []

    if comment_prefixes:
        filtered_lines = []
        num_comment = 0
        for line in original_lines:
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in comment_prefixes):
                num_comment += 1
            else:
                filtered_lines.append(line)
    else:
        filtered_lines = original_lines
        num_comment = 0

    # Get non-empty lines
    non_empty = [line.rstrip() for line in filtered_lines if line.strip()]

    # Apply skip and skip_tail
    if skip_tail > 0:
        result_lines = non_empty[skip:-skip_tail]
    else:
        result_lines = non_empty[skip:]

    return "\n".join(result_lines), num_comment, num_blank


def _resolve_file_col_name(
    col_name: str,
    headers: List[str],
    path: Optional[Path] = None,
    allow_positional: bool = True,
) -> str:
    """Resolve a file-column reference to a normalised header name.

    Integer tokens use 1-based indexing (1 = first column) when positional references are
    allowed. When they are not - because the file's first row names its columns - an integer
    token is a name like any other, so ':1' means the column headed '1'.

    Non-integer tokens are normalised via escape_spaces_with_underscore and returned as-is.

    Args:
        col_name: Column name or 1-based index
        headers: List of header names
        path: Optional path for error messages
        allow_positional: Whether an integer token selects by position; False when the file is
            being read with column headings, where every reference is a name

    Returns:
        Normalized header name

    Raises:
        ColumnNotFoundError: If column index is out of range
    """
    if not allow_positional:
        return escape_spaces_with_underscore(col_name)

    try:
        idx = int(col_name)
        if 1 <= idx <= len(headers):
            result = headers[idx - 1]
        else:
            source = str(path) if path else "<unknown>"
            column_specs = ", ".join(f"{i+1}={h}" for i, h in enumerate(headers))
            raise ColumnNotFoundError(
                f"column index {idx} out of range (1-based indices are 1-{len(headers)}) in {source}\n"
                f"column specifications: {column_specs}"
            )
    except ValueError:
        result = escape_spaces_with_underscore(col_name)

    return result


def extract_column_from_text(
    text: str,
    col_name: Optional[str],
    csv_format: CsvLikeFormats = CsvLikeFormats.AUTO,
    skip: int = 0,
    comment: Union[str, List[str]] = "",
    skip_tail: int = 0,
    source_path: Optional[Path] = None,
    has_header: bool = True,
    headings_note: Optional[str] = None,
) -> List[str]:
    """Extract a single column from CSV or whitespace-aligned text.

    Args:
        text: File content as string
        col_name: Column name or index to extract (None = all lines after header)
        csv_format: Format type (CSV, TSV, SSV, or AUTO for detection)
        skip: Rows to skip after header
        comment: Prefix(es) for comment lines to ignore (string or list)
        skip_tail: Number of trailing rows to skip from the end
        source_path: Optional path for error messages
        has_header: If True the first remaining row names the columns; if False the columns are
            named '1', '2', ... by position and every row is treated as data
        headings_note: Optional caller-supplied note appended in brackets to a column-not-found
            message, used to explain how the heading mode was arrived at

    Returns:
        List of values from the specified column

    Raises:
        TabularDataError: If column not found or parsing fails
        ColumnNotFoundError: If specified column not found
    """
    remaining, _, _ = _apply_skip_and_comment(text, skip, comment, skip_tail)

    # Special case: col_name=None means return all non-header lines
    if col_name is None:
        lines = [line.rstrip() for line in io.StringIO(remaining) if line.strip()]
        result = lines if not has_header else lines[1:]
    else:
        # Parse using specified format (or AUTO-detect)
        try:
            dict_rows, tags, _ = parse_csv_as_dicts(
                remaining,
                csv_format,
                skip=0,
                comment="",
                source_path=source_path,
                has_header=has_header,
            )
        except CsvParseError as e:
            # Re-raise parse errors as TabularDataError for consistency
            if "empty after filtering" in str(e):
                raise TabularDataError("No lines provided") from e
            raise TabularDataError(str(e)) from e

        if not dict_rows:
            result = []
        else:
            # Resolve column name; with headings in force every reference is a name
            resolved_col = _resolve_file_col_name(
                col_name, tags, source_path, allow_positional=not has_header
            )

            # Extract column values
            normalised_column = escape_spaces_with_underscore(resolved_col)
            if normalised_column not in dict_rows[0]:
                available = list(dict_rows[0].keys())
                source = str(source_path) if source_path else "<unknown>"
                if has_header:
                    detail = f"available columns are: {', '.join(available)}"
                else:
                    detail = f"available columns are indexed as 1..{len(available)}"
                note = f" [{headings_note}]" if headings_note else ""
                raise ColumnNotFoundError(
                    f"column '{col_name}' not found in {source}; {detail}{note}"
                )

            result = [row.get(normalised_column, UNUSED) for row in dict_rows]

    return result
