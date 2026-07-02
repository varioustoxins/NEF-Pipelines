import csv
import io
from collections import Counter
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import clevercsv
from clevercsv.dialect import SimpleDialect
from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import UNUSED, loop_reorder_columns, loop_row_dict_iter
from nef_pipelines.lib.structures import NEFColumnsException
from nef_pipelines.lib.util import (
    escape_spaces_with_underscore,
    find_index_of_first_unescaped,
    read_utf8_file,
    unescape_backslashes,
    warn,
)
from nef_pipelines.tools.columns.columns_structures import (
    DefaultValueSpecification,
    ExtractFormat,
    FileValueSpecification,
    InsertInstruction,
    InsertPlacement,
    LiteralsValueSpecification,
    NEFColumnsFileColumnNotFoundException,
    NEFColumnsFileIOException,
    NEFColumnsFileNotFoundException,
    NEFColumnsLoopColumnNotFoundException,
    RangeFromValueSpec,
    RangeValueSpec,
    RepeatValueSpec,
    TabularFormatResult,
    ValueSpec,
)

_DEFAULT_FILL = UNUSED


def detect_tabular_format(
    lines: Sequence[str],
    consistency: float = 0.9,
) -> Union[TabularFormatResult, SimpleDialect]:
    """
    Detect the format of tabular data.

    Assumes `lines` contains only data lines — no comments, no blank
    lines, no header row with a mismatched column count. Strip those
    upstream.

    Returns:
    - TabularFormatResult.RAGGED_WHITESPACE for space-aligned columnar data
    - TabularFormatResult.CLEVERCSV_AUTO to use clevercsv.DictReader without a dialect
    - a clevercsv.Dialect for proper delimited data
    - TabularFormatResult.UNKNOWN_OR_MESSY on failure

    Parameters
    ----------
    lines
        Data lines to inspect. Trailing newlines are tolerated.
    consistency
        Fraction of lines that must share the same column count for
        whitespace splitting to count as a "grid". 0.9 = 90%.
    """

    cleaned = _validate_and_clean_lines(lines)

    ragged_result = _check_ragged_whitespace(cleaned, consistency)
    if ragged_result:
        return ragged_result

    return _detect_csv_with_clevercsv(cleaned)


def _validate_and_clean_lines(raw_lines: Sequence[str]) -> List[str]:
    """Validate input and normalise lines by stripping whitespace and removing blanks."""
    if not raw_lines:
        raise NEFColumnsException("No lines provided")
    cleaned = [line.rstrip("\r\n") for line in raw_lines if line.strip()]
    if not cleaned:
        raise NEFColumnsException("No non-blank lines provided")
    return cleaned


def _check_ragged_whitespace(
    clean_lines: List[str], min_consistency: float
) -> Optional[TabularFormatResult]:
    """Check if lines form a ragged whitespace grid. Returns TabularFormatResult.RAGGED_WHITESPACE or None."""
    if len(clean_lines) < 2:
        return None

    ws_counts = [len(line.split()) for line in clean_lines]
    tab_counts = [len(line.split("\t")) for line in clean_lines]

    def dominant(counts: list[int]) -> tuple[int, float]:
        mode, count = Counter(counts).most_common(1)[0]
        return mode, count / len(counts)

    ws_mode, ws_frac = dominant(ws_counts)
    tab_mode, tab_frac = dominant(tab_counts)

    header_ws_count = ws_counts[0]
    data_ws_counts = ws_counts[1:]
    max_data_ws = max(data_ws_counts) if data_ws_counts else 0

    if header_ws_count > max_data_ws and max_data_ws == 1:
        return None

    ws_grid = ws_frac >= min_consistency and ws_mode > 1
    tab_grid = tab_frac >= min_consistency and tab_mode > 1

    if ws_grid and not tab_grid:
        return TabularFormatResult.RAGGED_WHITESPACE
    return None


def _detect_csv_with_clevercsv(
    clean_lines: List[str],
) -> Union[TabularFormatResult, SimpleDialect]:
    """Use CleverCSV to detect delimiter, with special handling for space delimiters."""
    text = "\n".join(clean_lines) + "\n"
    try:
        dialect = clevercsv.Sniffer().sniff(text)
        if dialect and dialect.delimiter == " ":
            data_counts = [len(line.split()) for line in clean_lines[1:]]
            if data_counts and max(data_counts) == 1:
                return TabularFormatResult.CLEVERCSV_AUTO
            return TabularFormatResult.RAGGED_WHITESPACE
        return dialect
    except (clevercsv.exceptions.Error, csv.Error):
        return TabularFormatResult.UNKNOWN_OR_MESSY


def _make_detected_dialect(delim: str, quote: str, escape):
    """Create a csv.Dialect subclass with the given delimiter, quotechar, and escapechar."""
    return type(
        "DetectedDialect",
        (csv.Dialect,),
        {
            "delimiter": delim,
            "quotechar": quote if quote else '"',
            "escapechar": escape,
            "doublequote": True,
            "skipinitialspace": False,
            "lineterminator": "\n",
            "quoting": csv.QUOTE_MINIMAL,
        },
    )


def _resolve_tag(
    ref: Union[int, str], tags: List[str], loop_category: Optional[str] = None
) -> str:
    """Resolve a column reference: 1-based integer index → tag name, else return as-is."""
    if isinstance(ref, int):
        idx = ref
    else:
        try:
            idx = int(ref)
        except ValueError:
            return ref
    if 1 <= idx <= len(tags):
        return tags[idx - 1]
    if loop_category is not None:
        raise NEFColumnsLoopColumnNotFoundException(idx, loop_category, len(tags))
    raise NEFColumnsException(
        f"column index {idx} out of range (loop has {len(tags)} columns, indices are 1-based)"
    )


def _resolve_file_col_name(
    col_name: str, headers: List[str], path: Optional[Path] = None
) -> str:
    """Resolve a file-column reference to a normalised header name.

    Integer tokens use 1-based indexing (1 = first column).
    Non-integer tokens are normalised via _norm_col and returned as-is.
    """
    try:
        idx = int(col_name)
    except ValueError:
        return escape_spaces_with_underscore(col_name)
    if 1 <= idx <= len(headers):
        return headers[idx - 1]
    raise NEFColumnsFileColumnNotFoundException(
        idx, str(path) if path else "<unknown>", headers
    )


def _apply_skip_and_comment(raw_text: str, skip: int, comment: str) -> str:
    """Strip comment lines and skip leading non-empty rows; return remaining text."""
    if comment:
        raw_text = "\n".join(
            line
            for line in raw_text.splitlines()
            if not line.strip().startswith(comment)
        )
    non_empty = [line.rstrip() for line in raw_text.splitlines() if line.strip()]
    return "\n".join(non_empty[skip:])


_MAX_RAGGED_WARNINGS = 3


def _parse_ragged_whitespace(lines: List[str], col_name: str, path: Path) -> List[str]:
    """Extract one column from space-aligned tabular text (header on line 0)."""
    if not lines:
        return []
    headers = [escape_spaces_with_underscore(h) for h in lines[0].split()]
    rows = []
    overwide = []
    for line_index, line in enumerate(lines[1:], start=2):
        fields = line.split()
        if len(fields) > len(headers):
            overwide.append(
                f"  line {line_index}: {len(fields)} fields but only {len(headers)} headers"
            )
        row = dict(zip(headers, fields))
        for h in headers[len(fields) :]:
            row[h] = UNUSED
        rows.append(row)
    if overwide:
        examples = "\n".join(overwide[:_MAX_RAGGED_WARNINGS])
        total = len(overwide)
        suffix = (
            f"\n  ... and {total - _MAX_RAGGED_WARNINGS} more"
            if total > _MAX_RAGGED_WARNINGS
            else ""
        )
        warn(
            f"in {path}, {total} row(s) have more fields than headers; extra fields ignored:\n{examples}{suffix}"
        )
    norm_col = escape_spaces_with_underscore(col_name)
    if not rows or norm_col not in rows[0]:
        raise NEFColumnsFileColumnNotFoundException(col_name, str(path), headers)
    return [row[norm_col] for row in rows]


def _parse_csv_rows(
    remaining: str, format_result: Union[TabularFormatResult, SimpleDialect]
) -> List[dict]:
    """Parse delimited rows from `remaining` using the detected format."""
    if format_result == TabularFormatResult.CLEVERCSV_AUTO:
        reader = clevercsv.DictReader(io.StringIO(remaining))
    elif format_result == TabularFormatResult.UNKNOWN_OR_MESSY:
        reader = csv.DictReader(io.StringIO(remaining))
    else:
        reader = clevercsv.DictReader(io.StringIO(remaining), dialect=format_result)
    return list(reader)


def _read_column_from_file(
    path: Path,
    col_name: Optional[str],
    format: ExtractFormat = ExtractFormat.CSV,
    skip: int = 0,
    comment: str = "",
) -> List[str]:
    """Read a single column (or all non-header lines) from a CSV or whitespace-aligned file.

    Raises NEFColumnsException if the file is not found or the column is absent.
    """
    if not path.exists():
        raise NEFColumnsFileNotFoundException(str(path))

    try:
        file_content = read_utf8_file(path.resolve())
    except (OSError, PermissionError, UnicodeDecodeError) as e:
        raise NEFColumnsFileIOException(str(path), "read", e)

    remaining = _apply_skip_and_comment(file_content, skip, comment)

    if format == ExtractFormat.SIMPLE or (
        format == ExtractFormat.CSV and col_name is None
    ):
        lines = [line.rstrip() for line in io.StringIO(remaining) if line.strip()]
        if format == ExtractFormat.CSV and col_name is None:
            lines = lines[1:]
        result = lines
    else:
        lines = remaining.splitlines()
        headers_for_resolve = _csv_column_names(path, skip=skip, comment=comment)
        col_name = _resolve_file_col_name(col_name, headers_for_resolve, path)
        try:
            format_result = detect_tabular_format(lines)
        except NEFColumnsException as e:
            raise NEFColumnsFileIOException(str(path), "parse", e)

        if format_result == TabularFormatResult.RAGGED_WHITESPACE:
            result = _parse_ragged_whitespace(lines, col_name, path)
        else:
            rows = _parse_csv_rows(remaining, format_result)
            if not rows:
                result = []
            else:
                rows = [
                    {escape_spaces_with_underscore(k): v for k, v in row.items()}
                    for row in rows
                ]
                norm_col = escape_spaces_with_underscore(col_name)
                if norm_col not in rows[0]:
                    available = list(rows[0].keys())
                    raise NEFColumnsFileColumnNotFoundException(
                        col_name, str(path), available
                    )
                result = [row[norm_col] for row in rows]

    return result


def _csv_column_names(path: Path, skip: int = 0, comment: str = "") -> List[str]:
    """Return normalised column names from the header row of a CSV file."""
    if not path.exists():
        raise NEFColumnsFileNotFoundException(str(path))

    try:
        file_content = read_utf8_file(path.resolve())
    except (OSError, PermissionError, UnicodeDecodeError) as e:
        raise NEFColumnsFileIOException(str(path), "read", e)

    remaining = _apply_skip_and_comment(file_content, skip, comment)
    if not remaining.strip():
        return []

    # Detect format and extract header
    lines = remaining.splitlines()
    if not lines:
        return []

    format_result = detect_tabular_format(lines)

    if format_result == TabularFormatResult.RAGGED_WHITESPACE:
        # Space-separated - use str.split()
        return [escape_spaces_with_underscore(h) for h in lines[0].split()]
    elif format_result == TabularFormatResult.CLEVERCSV_AUTO:
        # Use clevercsv without a dialect for auto-detection
        reader = clevercsv.reader(io.StringIO(remaining))
        for row in reader:
            return [escape_spaces_with_underscore(h.strip()) for h in row if h.strip()]
    elif format_result == TabularFormatResult.UNKNOWN_OR_MESSY:
        # Fall back to standard csv.reader
        reader = csv.reader(io.StringIO(remaining))
        for row in reader:
            return [escape_spaces_with_underscore(h.strip()) for h in row if h.strip()]
    else:
        # Use clevercsv with detected dialect
        reader = clevercsv.reader(io.StringIO(remaining), dialect=format_result)
        for row in reader:
            return [escape_spaces_with_underscore(h.strip()) for h in row if h.strip()]
    return []


def _rebuild_loop(frame, loop: Loop, new_tags: List[str], rows: List[dict]) -> Loop:
    """Swap a loop in its frame: remove old, build new with new_tags and rows via pynmrstar API."""
    category = loop.category
    new_loop = Loop.from_scratch(category.lstrip("_"))
    for tag in new_tags:
        new_loop.add_tag(tag)
    if rows:
        new_loop.add_data(rows)
    frame.remove_loop(category)
    frame.add_loop(new_loop)
    return new_loop


def _filter_tags(
    tags: List[str], patterns: List[str], loop_category: Optional[str] = None
) -> List[str]:
    """Filter tags by index or fnmatch patterns with escape support; empty patterns = all tags.

    Pattern types:
    1. Integer indices: "1", "2", "3" (1-based column positions)
    2. Plain names: "value" → "*value*" (substring match, backward compatible)
    3. Explicit wildcards: Full fnmatch pattern control

    Wildcard patterns (fnmatch syntax):
    - * : matches any characters         "atom_*" → atom_name, atom_id
    - ? : matches single character       "valu?" → value (not values)
    - [seq] : matches any char in seq    "atom_[NH]" → atom_N, atom_H
    - [!seq] : matches char not in seq   "[!_]*" → columns not starting with _

    Pattern examples:
    - "atom_*"      : prefix match (atom_name, atom_id)
    - "*_value"     : suffix match (shift_value, error_value)
    - "*name*"      : substring match (atom_name, chain_name)
    - "value"       : auto-wrapped as "*value*" (substring)
    - "atom_[NH]*"  : atom_N*, atom_H* columns

    Escape sequences:
    - "\\*"  : literal asterisk     "file\\*.txt" → "file*.txt" (no wildcard)
    - "\\?"  : literal question     "what\\?" → "what?" (no wildcard)
    - "\\\\" : literal backslash    "path\\\\name" → "path\\name"

    Args:
        tags: List of tag names to filter
        patterns: List of patterns (indices or fnmatch patterns)

    Returns:
        List of matching tags
    """
    if not patterns:
        return list(tags)

    result: List[str] = []
    for p in patterns:
        # Try integer index first (1-based)
        try:
            idx = int(p)
            if 1 <= idx <= len(tags):
                result.append(tags[idx - 1])
            else:
                if loop_category is not None:
                    raise NEFColumnsLoopColumnNotFoundException(
                        idx, loop_category, len(tags)
                    )
                raise NEFColumnsException(
                    f"column index {idx} out of range ({len(tags)} columns, indices are 1-based)"
                )
            continue
        except ValueError:
            pass

        # Check if pattern contains unescaped wildcards
        has_wildcard = (
            find_index_of_first_unescaped(p, "*") is not None
            or find_index_of_first_unescaped(p, "?") is not None
        )

        # Unescape the pattern
        unescaped = unescape_backslashes(p)

        # If no wildcards in original, wrap for substring matching (backward compatibility)
        pattern = unescaped if has_wildcard else f"*{unescaped}*"

        result.extend(t for t in tags if fnmatchcase(t, pattern))

    return result


def _resolve_values(value_spec: ValueSpec, n_rows: int, default: str) -> List[str]:
    if isinstance(value_spec, DefaultValueSpecification):
        result = [default] * n_rows
    elif isinstance(value_spec, FileValueSpecification):
        result = _read_column_from_file(
            value_spec.path,
            value_spec.col,
            skip=value_spec.skip,
            comment=value_spec.comment,
        )
    elif isinstance(value_spec, RepeatValueSpec):
        count = n_rows if value_spec.count is None else value_spec.count
        result = [value_spec.value] * count
    elif isinstance(value_spec, RangeValueSpec):
        s, e = value_spec.start, value_spec.end
        step = 1 if e >= s else -1
        result = [str(i) for i in range(s, e + step, step)]
    elif isinstance(value_spec, RangeFromValueSpec):
        result = [str(i) for i in range(value_spec.start, value_spec.start + n_rows)]
    elif isinstance(value_spec, LiteralsValueSpecification):
        result = list(value_spec.values)
    else:
        raise NEFColumnsException(
            f"unhandled ValueSpec type: {type(value_spec).__name__}"
        )
    return result


def _insert_column_into_loop(
    loop: Loop, idx: int, col_name: str, values: List[str]
) -> None:
    """Insert a column at position idx into a loop.

    Uses the public add_tag() API to append the new tag, then loop_reorder_columns
    to move it into the requested position. Row data is appended via the public
    loop.data attribute before reordering.
    """
    current_tags = list(loop.tags)
    try:
        loop.add_tag(col_name)
    except ValueError as e:
        # PyNMRStar raises ValueError if tag has a category that doesn't match the loop
        if "different categories" in str(e):
            from nef_pipelines.tools.columns.columns_exceptions import (
                NEFColumnsTagCategoryMismatchException,
            )

            # Extract category from tag if present (format: category.tag_name)
            if "." in col_name:
                tag_category = col_name.split(".", 1)[0]
                if not tag_category.startswith("_"):
                    tag_category = "_" + tag_category
            else:
                tag_category = "(none)"
            raise NEFColumnsTagCategoryMismatchException(
                col_name, tag_category, loop.category
            )
        raise
    if loop.data:
        for row, v in zip(loop.data, values):
            row.append(v)
        new_order = current_tags[:idx] + [col_name] + current_tags[idx:]
        loop_reorder_columns(loop, new_order)
    elif values:
        loop.add_data([{col_name: v} for v in values])


def _force_replace_column(
    loop: Loop, col_name: str, value_spec: ValueSpec, default: str
) -> None:
    """Replace all values in an existing column in place."""
    rows = list(loop_row_dict_iter(loop, convert=False))
    values = _resolve_values(value_spec, len(rows), default)
    if len(values) < len(rows):
        values = values + [default] * (len(rows) - len(values))
    elif len(values) > len(rows):
        default_row = {tag: default for tag in loop.tags}
        rows = rows + [dict(default_row) for _ in range(len(values) - len(rows))]
    loop.clear_data()
    loop.add_data([{**row, col_name: str(v)} for row, v in zip(rows, values)])


def _resolve_insert_index(
    loop: Loop,
    keyword: InsertPlacement,
    position_anchor: Optional[Union[int, str]],
) -> int:
    """Resolve a placement keyword to a 0-based insertion index."""
    if keyword in (InsertPlacement.BEFORE, InsertPlacement.AFTER, InsertPlacement.AT):
        category = loop.category.lstrip("_")
        resolved_anchor = _resolve_tag(position_anchor, loop.tags, category)
        if resolved_anchor not in loop.tags:
            raise NEFColumnsLoopColumnNotFoundException(
                position_anchor, category, len(loop.tags)
            )
        idx = loop.tags.index(resolved_anchor)
        if keyword == InsertPlacement.AFTER:
            return idx + 1
        return idx
    return len(loop.tags)


def _apply_instructions(
    loop: Loop,
    instructions: List[InsertInstruction],
    default: str,
) -> None:
    """Apply a list of fully-resolved InsertInstruction objects to a loop.

    Existing columns are silently overwritten; name-clash preflight is the caller's responsibility.
    """
    for instr in instructions:
        col_name = instr.column_spec.col_name
        value_spec = instr.column_spec.value_spec

        if isinstance(value_spec, FileValueSpecification) and "," in col_name:
            raise NEFColumnsException(
                f"insert takes one column per file reference, "
                f"got multiple columns '{col_name}'"
            )

        if col_name in loop.tags:
            _force_replace_column(loop, col_name, value_spec, default)
        else:
            values = _resolve_values(value_spec, len(loop.data), default)
            index = _resolve_insert_index(loop, instr.keyword, instr.position_anchor)
            if instr.keyword == InsertPlacement.AT:
                loop.tags.pop(index)
                for row in loop.data:
                    row.pop(index)

            if len(values) < len(loop.data):
                values = values + [default] * (len(loop.data) - len(values))
            elif len(values) > len(loop.data) and loop.data:
                loop.data.extend(
                    [[default] * len(loop.tags)] * (len(values) - len(loop.data))
                )

            _insert_column_into_loop(loop, index, col_name, [str(v) for v in values])


def _apply_instructions_by_loop(
    by_loop: Dict[int, Tuple[Loop, List[InsertInstruction]]]
) -> None:
    for loop, group in by_loop.values():
        _apply_instructions(loop, group, _DEFAULT_FILL)


def _group_instructions_by_loop(
    column_instructions: List[InsertInstruction],
) -> Dict[int, Tuple[Loop, List[InsertInstruction]]]:
    by_loop: Dict[int, Tuple[Loop, List[InsertInstruction]]] = {}
    for column_instruction in column_instructions:
        key = id(column_instruction.loop)
        if key not in by_loop:
            by_loop[key] = (column_instruction.loop, [])
        by_loop[key][1].append(column_instruction)
    return by_loop


def apply_column_instructions(
    entry: Entry, column_instructions: List[InsertInstruction]
) -> Entry:
    """Apply fully-resolved column instructions to an entry and return it."""
    instructions_by_loop = _group_instructions_by_loop(column_instructions)
    _apply_instructions_by_loop(instructions_by_loop)
    return entry
