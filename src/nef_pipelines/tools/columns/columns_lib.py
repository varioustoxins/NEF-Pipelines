from fnmatch import fnmatchcase
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import UNUSED, loop_reorder_columns, loop_row_dict_iter
from nef_pipelines.lib.tabular_data_lib import (
    ColumnNotFoundError,
    CsvLikeFormats,
    TabularDataError,
)
from nef_pipelines.lib.tabular_data_lib import (
    _resolve_file_col_name as _generic_resolve_file_col_name,
)
from nef_pipelines.lib.tabular_data_lib import (
    extract_column_from_text as _generic_extract_column_from_text,
)
from nef_pipelines.lib.util import (
    escape_for_fnmatch,
    find_index_of_first_unescaped,
    read_utf8_sig_file,
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
    NEFColumnsColumnNotFoundInFileException,
    NEFColumnsColumnNotFoundInLoopException,
    NEFColumnsException,
    NEFColumnsFileIOException,
    NEFColumnsFileNotFoundException,
    NEFColumnsTagCategoryMismatchException,
    RangeFromValueSpec,
    RangeValueSpec,
    RepeatValueSpec,
    ValueSpec,
)

_DEFAULT_FILL = UNUSED


# TODO may need callers to be reworked to just use tabular_data_lib
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
        raise NEFColumnsColumnNotFoundInLoopException(idx, loop_category, len(tags))
    raise NEFColumnsException(
        f"column index {idx} out of range (loop has {len(tags)} columns, indices are 1-based)"
    )


# TODO may need callers to be reworked to just use tabular_data_lib
def _resolve_file_col_name(
    col_name: str, headers: List[str], path: Optional[Path] = None
) -> str:
    """Resolve a file-column reference to a normalised header name.

    Wrapper around tabular_data_lib version that throws NEFColumns exceptions.
    """
    try:
        return _generic_resolve_file_col_name(col_name, headers, path)
    except ColumnNotFoundError:
        # Re-raise as NEFColumns exception for API compatibility
        try:
            idx = int(col_name)
            raise NEFColumnsColumnNotFoundInFileException(
                idx, str(path) if path else "<unknown>", headers
            )
        except ValueError:
            # col_name is not an integer
            raise NEFColumnsColumnNotFoundInFileException(
                col_name, str(path) if path else "<unknown>", headers
            )


# TODO may need callers to be reworked to just use tabular_data_lib
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
        file_content = read_utf8_sig_file(path.resolve())
    except (OSError, PermissionError, UnicodeDecodeError) as e:
        raise NEFColumnsFileIOException(str(path), "read", e)

    # Extract column from text (no double file read)
    return extract_column_from_text(file_content, col_name, format, skip, comment, path)


# TODO may need callers to be reworked to just use tabular_data_lib
def extract_column_from_text(
    text: str,
    col_name: Optional[str],
    format: ExtractFormat = ExtractFormat.CSV,
    skip: int = 0,
    comment: str = "",
    source_path: Optional[Path] = None,
) -> List[str]:
    """Extract a single column from CSV or whitespace-aligned text.

    Args:
        text: File content as string
        col_name: Column name or index to extract (ignored for SIMPLE format)
        format: Format type (CSV or SIMPLE)
        skip: Rows to skip after header
        comment: Comment prefix to filter
        source_path: Optional path for error messages

    Returns:
        List of values from the specified column

    Raises:
        NEFColumnsException if the column is not found
    """
    # Handle SIMPLE format - return all lines without column extraction
    if format == ExtractFormat.SIMPLE:
        import io

        from nef_pipelines.lib.tabular_data_lib import _apply_skip_and_comment

        remaining = _apply_skip_and_comment(text, skip, comment)
        lines = [line.rstrip() for line in io.StringIO(remaining) if line.strip()]
        return lines

    # CSV format - use generic column extraction
    try:
        result = _generic_extract_column_from_text(
            text, col_name, CsvLikeFormats.AUTO, skip, comment, source_path
        )
        return result
    except ColumnNotFoundError as e:
        # Re-raise as NEFColumns exception
        raise NEFColumnsException(str(e)) from e
    except TabularDataError as e:
        # Re-raise as NEFColumns exception
        if source_path:
            raise NEFColumnsFileIOException(str(source_path), "parse", e) from e
        raise NEFColumnsException(str(e)) from e


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
                    raise NEFColumnsColumnNotFoundInLoopException(
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

        if has_wildcard:
            pattern = unescaped
        else:
            pattern = f"*{escape_for_fnmatch(unescaped)}*"

        result.extend(t for t in tags if fnmatchcase(t, pattern))

    return result


def _resolve_values(value_spec: ValueSpec, n_rows: int, default: str) -> List[str]:
    if isinstance(value_spec, DefaultValueSpecification):
        result = [default] * n_rows
    elif isinstance(value_spec, FileValueSpecification):
        result = _read_column_from_file(
            value_spec.path,
            value_spec.col,
            format=value_spec.format,
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

    # Warn about row count mismatches when using file value specs
    if isinstance(value_spec, FileValueSpecification):
        file_rows = "row" if len(values) == 1 else "rows"
        loop_rows = "row" if len(rows) == 1 else "rows"
        if len(values) < len(rows):
            warn(
                f"file {value_spec.path} has {len(values)} {file_rows}, "
                f"loop has {len(rows)} {loop_rows} - filling remaining with '.'"
            )
        elif len(values) > len(rows):
            warn(
                f"file {value_spec.path} has {len(values)} {file_rows}, "
                f"loop has {len(rows)} {loop_rows} - extending loop with '.' in other columns"
            )

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
            raise NEFColumnsColumnNotFoundInLoopException(
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
