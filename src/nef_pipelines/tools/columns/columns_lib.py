from dataclasses import replace
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from pynmrstar import Entry, Loop

from nef_pipelines.lib.nef_lib import UNUSED, loop_reorder_columns, loop_row_dict_iter
from nef_pipelines.lib.structures import PipeOutput
from nef_pipelines.lib.tabular_data_lib import (
    ColumnNotFoundError,
    CsvLikeFormats,
    TabularDataError,
    _apply_skip_and_comment,
    _parse_csv_rows_from_text,
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
    is_int,
    read_utf8_sig_file,
    unescape_backslashes,
    warn,
)
from nef_pipelines.tools.columns.columns_structures import (
    ColumnHeadings,
    CommentInstruction,
    DefaultValueSpecification,
    ExtractFormat,
    FileSettings,
    FileValueSpecification,
    HeadingsInferredAdvisory,
    InsertInstruction,
    InsertPlacement,
    Instruction,
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
    ResolvedFileValueSpecification,
    SkipInstruction,
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


def _headings_note(mode: ColumnHeadings, has_header: bool) -> str:
    """State how the file was read, for a column-not-found message.

    This is a statement of fact only. Naming the option that would change it is the command
    line's business, not the pipeline's, so no option names appear here.

    Args:
        mode: The heading mode asked for, possibly AUTO
        has_header: The mode actually used once any inference was applied

    Returns:
        Text to show in brackets after the list of available columns
    """
    if has_header:
        used = "the first row was read as column headings"
    else:
        used = "the file was read as having no column headings"

    inferred = " (inferred)" if mode == ColumnHeadings.AUTO else ""

    return f"{used}{inferred}"


# TODO this should be in general utils...
def _read_file_or_raise(path: Path) -> str:
    """Read a file's text, raising the columns-specific exceptions for missing or unreadable files.

    Args:
        path: Path to read

    Returns:
        The file's decoded text

    Raises:
        NEFColumnsFileNotFoundException: If the path does not exist
        NEFColumnsFileIOException: If the file cannot be read or decoded
    """
    if not path.exists():
        raise NEFColumnsFileNotFoundException(str(path))

    try:
        result = read_utf8_sig_file(path.resolve())
    except (OSError, PermissionError, UnicodeDecodeError) as e:
        raise NEFColumnsFileIOException(str(path), "read", e)

    return result


# TODO may need callers to be reworked to just use tabular_data_lib
def _read_column_from_file(
    path: Path,
    col_name: Optional[str],
    format: ExtractFormat = ExtractFormat.CSV,
    skip: int = 0,
    comment: Union[str, List[str]] = "",
    skip_tail: int = 0,
) -> List[str]:
    """Read a single column (or all non-header lines) from a CSV or whitespace-aligned file.

    Raises NEFColumnsException if the file is not found or the column is absent.
    """
    file_content = _read_file_or_raise(path)

    # Extract column from text (no double file read)
    return extract_column_from_text(
        file_content, col_name, format, skip, comment, skip_tail, path
    )


# TODO may need callers to be reworked to just use tabular_data_lib
def extract_column_from_text(
    text: str,
    col_name: Optional[str],
    format: ExtractFormat = ExtractFormat.CSV,
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
        col_name: Column name or index to extract (ignored for SIMPLE format)
        format: Format type (CSV or SIMPLE)
        skip: Rows to skip after header
        comment: Prefix(es) for comment lines to ignore (string or list)
        skip_tail: Number of trailing rows to skip from the end
        source_path: Optional path for error messages
        has_header: If True the first remaining row names the columns; if False the columns are
            named '1', '2', ... by position and every row is treated as data
        headings_note: Optional note appended in brackets to a column-not-found message,
            explaining how the heading mode was arrived at; see :func:`_headings_note`

    Returns:
        List of values from the specified column

    Raises:
        NEFColumnsException if the column is not found
    """
    # Handle SIMPLE format - return all lines without column extraction
    if format == ExtractFormat.SIMPLE:
        import io

        from nef_pipelines.lib.tabular_data_lib import _apply_skip_and_comment

        remaining, _, _ = _apply_skip_and_comment(text, skip, comment, skip_tail)
        lines = [line.rstrip() for line in io.StringIO(remaining) if line.strip()]
        return lines

    # CSV format - use generic column extraction
    try:
        result = _generic_extract_column_from_text(
            text,
            col_name,
            CsvLikeFormats.AUTO,
            skip,
            comment,
            skip_tail,
            source_path,
            has_header,
            headings_note,
        )
        return result
    except ColumnNotFoundError as e:
        # Re-raise as NEFColumns exception, preserving the diagnostic text which already
        # names the out-of-range index and the available column specifications
        raise NEFColumnsException(str(e)) from e
    except TabularDataError as e:
        # Re-raise as NEFColumns exception
        if source_path:
            raise NEFColumnsFileIOException(str(source_path), "parse", e) from e
        raise NEFColumnsException(str(e)) from e


# TODO this should be in the nef lib or something???
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


def _resolve_values(
    value_spec: ValueSpec,
    n_rows: int,
    default: str,
    file_settings: FileSettings = FileSettings(),
) -> List[str]:
    if isinstance(value_spec, DefaultValueSpecification):
        result = [default] * n_rows
    elif isinstance(value_spec, ResolvedFileValueSpecification):
        result = list(value_spec.values)
    elif isinstance(value_spec, FileValueSpecification):
        result = _read_column_from_file(
            value_spec.path,
            value_spec.col,
            format=value_spec.format,
            skip=file_settings.skip,
            comment=list(file_settings.comment),
            skip_tail=file_settings.skip_tail,
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
    loop: Loop,
    col_name: str,
    value_spec: ValueSpec,
    default: str,
    file_settings: FileSettings = FileSettings(),
) -> None:
    """Replace all values in an existing column in place."""
    rows = list(loop_row_dict_iter(loop, convert=False))
    values = _resolve_values(value_spec, len(rows), default, file_settings)

    # Warn about row count mismatches when using file value specs
    if isinstance(value_spec, (FileValueSpecification, ResolvedFileValueSpecification)):
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

        if (
            isinstance(
                value_spec, (FileValueSpecification, ResolvedFileValueSpecification)
            )
            and "," in col_name
        ):
            raise NEFColumnsException(
                f"insert takes one column per file reference, "
                f"got multiple columns '{col_name}'"
            )

        if col_name in loop.tags:
            _force_replace_column(
                loop, col_name, value_spec, default, instr.file_settings
            )
        else:
            values = _resolve_values(
                value_spec, len(loop.data), default, instr.file_settings
            )
            index = _resolve_insert_index(loop, instr.keyword, instr.position_anchor)
            if instr.keyword == InsertPlacement.AT:
                loop.tags.pop(index)
                for row in loop.data:
                    row.pop(index)

            if len(values) < len(loop.data):
                values = values + [default] * (len(loop.data) - len(values))
            elif len(values) > len(loop.data) and loop.data:
                # each padded row must be its own list; multiplying a list of lists would
                # alias one row into every position and corrupt the loop on insertion
                loop.data.extend(
                    [default] * len(loop.tags)
                    for _ in range(len(values) - len(loop.data))
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


def _is_numeric_column_reference(col: Optional[str]) -> bool:
    """Return True if a file column reference is a 1-based positional index rather than a name."""

    return is_int(col) if col is not None else False


def _detect_header_behaviour(columns: List[Optional[str]]) -> Tuple[bool, bool]:
    """Decide whether a batch of file column references implies a header row.

    A batch that refers to its columns purely by position cannot have consumed a header row,
    so the first row is data. Any reference by name requires a header row to resolve against.

    Args:
        columns: The column references making up one batch

    Returns:
        (has_header, is_mixed) - is_mixed is True when the batch mixes positional and named
        references, which is ambiguous; such a batch is treated as having a header
    """
    numeric = [col for col in columns if _is_numeric_column_reference(col)]
    named = [col for col in columns if not _is_numeric_column_reference(col)]

    has_header = bool(named) or not numeric
    is_mixed = bool(named) and bool(numeric)

    return has_header, is_mixed


def _assign_batch_header_behaviour(
    instructions: List[Tuple[InsertInstruction, FileSettings]],
) -> Tuple[Dict[int, bool], List[str]]:
    """Group consecutive file references by (path, settings) and decide header handling per batch.

    A batch ends when the next file-backed instruction targets a different path or carries
    different file settings; instructions that do not read from a file never break a batch.
    Detection is per batch rather than per file so the same file may be read with a header
    under one set of settings and without one under another.

    Note that bare '@file' references are expanded to named columns before this point, so they
    always fall into the header-requiring case.

    Args:
        instructions: File-backed instructions in command-line order, with their settings

    Returns:
        (has_header_by_instruction_id, advisories, positional_inferences); the last is the
        (path, settings) of each batch inferred to be positional, which the caller checks
        against the file itself before deciding whether the inference is worth reporting
    """
    batches: List[List[Tuple[InsertInstruction, FileSettings]]] = []
    previous_key = None
    for instruction, settings in instructions:
        key = (instruction.column_spec.value_spec.path, settings)
        if key != previous_key:
            batches.append([])
            previous_key = key
        batches[-1].append((instruction, settings))

    has_header_by_instruction_id: Dict[int, bool] = {}
    advisories: List[HeadingsInferredAdvisory] = []
    positional_inferences: List[Tuple[Path, FileSettings]] = []
    for batch in batches:
        path = batch[0][0].column_spec.value_spec.path
        settings = batch[0][1]
        requested = settings.use_column_headings

        if requested != ColumnHeadings.AUTO:
            # the user has stated the shape of the file, so there is nothing to infer or warn about
            has_header = requested == ColumnHeadings.ON
        else:
            columns = [
                instruction.column_spec.value_spec.col for instruction, _ in batch
            ]
            has_header, is_mixed = _detect_header_behaviour(columns)

            if is_mixed:
                advisories.append(HeadingsInferredAdvisory(path, has_header, is_mixed))
            elif not has_header:
                # only worth reporting if the file turns out to look like it has headings,
                # which cannot be known until it is read - see apply_column_instructions
                positional_inferences.append((path, settings))

        for instruction, _ in batch:
            has_header_by_instruction_id[id(instruction)] = has_header

    return has_header_by_instruction_id, advisories, positional_inferences


def _first_row_looks_like_headings(text: str) -> bool:
    """Return True if every field of the first row is non-numeric text.

    Numeric column headings are common enough that inferring a file to be headerless is
    usually right and not worth reporting. A first row made entirely of text is the tell that
    the inference may be wrong, because data rows in these files almost always carry a number.

    Args:
        text: The file text after comment removal and skipping

    Returns:
        True if the first row is entirely non-numeric and so looks like a heading row
    """
    rows = _parse_csv_rows_from_text(text, CsvLikeFormats.AUTO)
    if not rows or not rows[0]:
        return False

    for field in rows[0]:
        field = field.strip()
        if not field:
            return False
        try:
            float(field)
        except ValueError:
            continue
        return False

    return True


def _resolve_file_backed_instruction(
    instruction: InsertInstruction,
    raw_files: Dict[Path, str],
    filtered_files: Dict[Tuple[Path, FileSettings], str],
    has_header: bool = True,
) -> InsertInstruction:
    """Resolve a file-backed instruction's column into literal values.

    Reads the file through the two-level cache using the file settings carried on the
    instruction, then returns an equivalent instruction whose value specification is a
    LiteralsValueSpecification. This keeps all placement, padding and clash handling in
    the single application path in :func:`_apply_instructions`.

    Args:
        instruction: The instruction to resolve
        raw_files: Cache of path → raw file text, read from disk at most once per path
        filtered_files: Cache of (path, settings) → text after comment removal and skipping
        has_header: Whether this instruction's batch treats the first row as column headings

    Returns:
        The instruction with its file value specification replaced by literal values
    """
    value_spec = instruction.column_spec.value_spec
    path = value_spec.path
    settings = instruction.file_settings

    if path not in raw_files:
        raw_files[path] = _read_file_or_raise(path)

    cache_key = (path, settings)
    if cache_key not in filtered_files:
        filtered_files[cache_key], _, _ = _apply_skip_and_comment(
            raw_files[path],
            skip=settings.skip,
            comment=list(settings.comment),
            skip_tail=settings.skip_tail,
        )

    values = extract_column_from_text(
        filtered_files[cache_key],
        value_spec.col,
        format=value_spec.format,
        source_path=path,
        has_header=has_header,
        headings_note=_headings_note(settings.use_column_headings, has_header),
    )

    resolved_spec = replace(
        instruction.column_spec,
        value_spec=ResolvedFileValueSpecification(path, values),
    )
    return replace(instruction, column_spec=resolved_spec)


def apply_column_instructions(
    entry: Entry,
    instructions: List[Instruction],
) -> PipeOutput:
    """Apply a mixed list of Comment/Skip/Insert instructions to an entry.

    Comment and Skip instructions update the running file-reading state; Insert
    instructions are resolved against that state. File-backed columns are read through a
    two-level cache — raw text is read from disk once per path, and parsed results are
    cached per (path, settings) so re-reading a file under changed settings never returns
    to disk.

    Resolved instructions are then applied by the shared placement machinery, so file
    columns, literals and ranges all follow the same insertion, padding and column-clash
    rules.

    This function never prints and phrases nothing. Findings are returned as typed items for
    the caller to render with a message building function, or discard.

    Args:
        entry: NEF entry to modify in place
        instructions: Mixed list of CommentInstruction, SkipInstruction and InsertInstruction

    Returns:
        PipeOutput carrying the modified entry and any advisories raised while reading files
    """
    comment: List[str] = []
    skip = 0
    skip_tail = 0

    raw_files: Dict[Path, str] = {}
    filtered_files: Dict[Tuple[Path, FileSettings], str] = {}

    # First pass: settle the file settings in force for each instruction
    settled: List[InsertInstruction] = []
    for instruction in instructions:
        if isinstance(instruction, CommentInstruction):
            comment = list(instruction.prefixes)
        elif isinstance(instruction, SkipInstruction):
            skip = instruction.skip
            skip_tail = instruction.skip_tail
        elif isinstance(instruction, InsertInstruction):
            if instruction.file_settings == FileSettings():
                instruction = replace(
                    instruction,
                    file_settings=FileSettings(tuple(comment), skip, skip_tail),
                )
            settled.append(instruction)

    # Second pass: decide header handling for each batch of consecutive file references
    file_backed = [
        (instruction, instruction.file_settings)
        for instruction in settled
        if isinstance(instruction.column_spec.value_spec, FileValueSpecification)
    ]
    (
        has_header_by_instruction_id,
        advisories,
        positional_inferences,
    ) = _assign_batch_header_behaviour(file_backed)

    # Third pass: read the file columns and apply everything through the shared machinery
    resolved: List[InsertInstruction] = []
    for instruction in settled:
        if isinstance(instruction.column_spec.value_spec, FileValueSpecification):
            instruction = _resolve_file_backed_instruction(
                instruction,
                raw_files,
                filtered_files,
                has_header_by_instruction_id[id(instruction)],
            )
        resolved.append(instruction)

    # a positional inference is only reported once the file shows it may have been wrong
    for path, settings in positional_inferences:
        text = filtered_files.get((path, settings))
        if text is not None and _first_row_looks_like_headings(text):
            advisories.append(
                HeadingsInferredAdvisory(path, has_header=False, is_mixed=False)
            )

    _apply_instructions_by_loop(_group_instructions_by_loop(resolved))

    return PipeOutput(entry=entry, items=advisories)
