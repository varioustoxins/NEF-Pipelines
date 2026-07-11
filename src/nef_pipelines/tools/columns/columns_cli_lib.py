import getopt
import sys
import textwrap
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import click
from pynmrstar import Entry, Loop

from nef_pipelines.lib.cli_lib import (
    BadFrameLoopTagSyntaxException,
    parse_frame_loop_and_tags,
)
from nef_pipelines.lib.nef_lib import (
    SelectionType,
    select_frames,
    select_loops_by_category,
)
from nef_pipelines.lib.structures import FrameLoopAndTagSelectors, FrameLoopsAndTags
from nef_pipelines.lib.tabular_data_lib import CsvLikeFormats, parse_csv_text
from nef_pipelines.lib.util import (
    escape_spaces_with_underscore,
    exit_error,
    read_utf8_sig_file,
    to_ordinal,
)
from nef_pipelines.tools.columns.columns_lib import _resolve_file_col_name
from nef_pipelines.tools.columns.columns_structures import (
    ColumnPlacement,
    ColumnSpecification,
    DefaultValueSpecification,
    ExtractFormat,
    FileValueSpecification,
    InsertInstruction,
    InsertPlacement,
    LiteralsValueSpecification,
    NEFColumnsDuplicateLoopException,
    NEFColumnsRenameParseException,
    NEFColumnsReplaceInvalidFormatException,
    NEFInsertCLILoopNotDefinedException,
    OrderedArguments,
    RangeFromValueSpec,
    RangeValueSpec,
    RepeatValueSpec,
    ValueSpec,
)

# Selector Parsing Functions


def _build_frame_loop_and_tag_selector_error_message(
    selector_str: str, index: int, exception: BadFrameLoopTagSyntaxException
) -> str:
    """Build a formatted error message for invalid selector syntax."""

    msg = (
        f"invalid selector syntax for the {to_ordinal(index + 1)} selector: "
        f"{selector_str}"
    )
    return msg


def _parse_selected_loops_or_raise(
    entry: Entry, selectors: List[str]
) -> List[FrameLoopsAndTags]:
    """Parse selectors and return one FrameLoopsAndTags per matched (frame, loop) pair.

    Raises BadFrameLoopTagSyntaxException if selector syntax is invalid.
    Each item has exactly one loop; loop_tags holds the raw patterns keyed by category.
    Callers filter via _filter_tags. frame_tags is always empty.
    """
    result = []
    for selector_str in selectors:
        sel = parse_frame_loop_and_tags(selector_str)

        if sel.loop_name is None:
            continue

        frames = select_frames(entry, [sel.frame_name], SelectionType.ANY)
        for frame in frames:
            loops = select_loops_by_category(
                frame.loops, [sel.loop_name] if sel.loop_name else []
            )
            for loop in loops:
                result.append(
                    FrameLoopsAndTags(
                        frame=frame,
                        loops=[loop],
                        loop_tags={loop.category: sel.loop_tags},
                    )
                )
    return result


def _parse_frame_loop_and_tag_selectors_or_exit_error(
    entry: Entry, selectors: List[str]
) -> List[FrameLoopsAndTags]:
    """Parse selectors into FrameLoopsAndTags, exits on invalid syntax.

    This is a convenience wrapper around _parse_selected_loops_or_raise that
    provides user-friendly error messages when selector syntax is invalid.
    """
    try:
        return _parse_selected_loops_or_raise(entry, selectors)
    except BadFrameLoopTagSyntaxException as e:
        for index, selector_str in enumerate(selectors):
            try:
                parse_frame_loop_and_tags(selector_str)
            except BadFrameLoopTagSyntaxException:
                exit_error(
                    _build_frame_loop_and_tag_selector_error_message(
                        selector_str, index, e
                    )
                )
        raise


# CLI Argument Parsing Functions


def parse_value_spec(spec: Optional[str]) -> ValueSpec:
    """Parse a value specification string into a ValueSpec dataclass."""
    if spec is None:
        result: ValueSpec = DefaultValueSpecification()
    elif spec.startswith("@"):
        path, _, col = spec[1:].partition(":")
        result = FileValueSpecification(path=Path(path), col=col or None)
    elif "*" in spec:
        val, _, count_str = spec.partition("*")
        if count_str == "":
            result = RepeatValueSpec(value=val, count=None)
        else:
            try:
                count = int(count_str)
                result = (
                    RepeatValueSpec(value=val, count=count)
                    if count >= 0
                    else LiteralsValueSpecification(values=spec.split(","))
                )
            except ValueError:
                result = LiteralsValueSpecification(values=spec.split(","))
    elif ".." in spec:
        start_str, _, end_str = spec.partition("..")
        try:
            start = int(start_str)
            result = (
                RangeFromValueSpec(start=start)
                if end_str == ""
                else RangeValueSpec(start=start, end=int(end_str))
            )
        except ValueError:
            result = LiteralsValueSpecification(values=spec.split(","))
    else:
        result = LiteralsValueSpecification(values=spec.split(","))
    return result


def column_spec_from_str(
    token: str,
    skip: int = 0,
    comment: str = "",
    format: Optional["ExtractFormat"] = None,
) -> ColumnSpecification:
    """Parse 'col_name' or 'col_name=value_spec' into a ColumnSpec."""

    parts = token.split("=", 1)
    col_name = parts[0]
    value_spec = parse_value_spec(parts[1] if len(parts) == 2 else None)
    if isinstance(value_spec, FileValueSpecification):
        col = col_name if value_spec.col is None else value_spec.col
        value_spec = FileValueSpecification(
            path=value_spec.path,
            col=col,
            skip=skip,
            comment=comment,
            format=format if format is not None else ExtractFormat.CSV,
        )
    return ColumnSpecification(col_name=col_name, value_spec=value_spec)


def _has_assignment(s: str) -> bool:
    """Return True if `s` contains an unescaped '=' character."""
    i = 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            i += 2
        elif s[i] == "=":
            return True
        else:
            i += 1
    return False


def _find_assignment_boundaries(s: str) -> List[int]:
    """Return positions of commas that precede an identifier= boundary."""
    boundaries = []
    n = len(s)
    i = 0
    while i < n:
        if s[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if s[i] == ",":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            if j > i + 1 and j < n and s[j] == "=":
                boundaries.append(i)
        i += 1
    return boundaries


def _split_bare_tags(s: str) -> List[str]:
    """Split a bare (no-assignment) tag string at comma boundaries.

    Commas inside an @file reference token are not boundaries unless followed by '@'.
    """
    parts: List[str] = []
    current: List[str] = []
    in_at_ref = False
    chars = list(s)
    n = len(chars)
    i = 0
    while i < n:
        ch = chars[i]
        if ch == "@" and not current:
            in_at_ref = True
            current.append(ch)
        elif ch == "," and in_at_ref and i + 1 < n and chars[i + 1] == "@":
            if current:
                parts.append("".join(current))
            current = []
            in_at_ref = False
        elif ch == "," and not in_at_ref:
            if current:
                parts.append("".join(current))
            current = []
        else:
            current.append(ch)
        i += 1
    if current:
        parts.append("".join(current))
    return [p for p in parts if p]


def _split_on_column_specification_on_assignment_boundaries(tags_raw: str) -> List[str]:
    """Split a column spec string at identifier= boundaries.

    For strings containing '=', splits at commas followed by an identifier
    immediately before '=', enabling multi-value specs to coexist with multiple
    column specs: 'col1=a,b,c,col2=d,e' → ['col1=a,b,c', 'col2=d,e'].
    A string with no '=' is treated as a comma-separated list of bare tag names.
    A single col=val spec with no further identifier= boundary is returned as-is.
    Backslash-escaped '=' signs (\\=) are not treated as boundaries.
    """
    if not tags_raw:
        return []

    if not _has_assignment(tags_raw):
        return _split_bare_tags(tags_raw)

    boundaries = _find_assignment_boundaries(tags_raw)
    if not boundaries:
        return [tags_raw]

    segments = []
    prev = 0
    for b in boundaries:
        segments.append(tags_raw[prev:b])
        prev = b + 1
    segments.append(tags_raw[prev:])
    segments = [p for p in segments if p]

    expanded = []
    for i, seg in enumerate(segments):
        if "=" not in seg and i + 1 < len(segments) and "=" in segments[i + 1]:
            _, _, spec = segments[i + 1].partition("=")
            for bare_tag in seg.split(","):
                bare_tag = bare_tag.strip()
                if bare_tag:
                    expanded.append(f"{bare_tag}={spec}")
        else:
            expanded.append(seg)
    return [p for p in expanded if p]


def _peel_selector_prefix(token: str) -> Tuple[str, str]:
    """Peel off an optional 'frame.loop:' prefix from a column spec token.

    Returns (prefix_with_colon, remainder). A selector prefix is identified by
    '.' appearing before ':' and before any '=' in the token. File references
    (tokens starting with '@') are never treated as frame.loop selectors.
    Returns ('', token) if no valid selector prefix is found.

    Also normalises two loop-level file-import shorthands into the canonical
    'frame.loop:@file' form accepted by the rest of the pipeline:
      frame.loop=@file  →  ('frame.loop:', '@file')   dot before =, no colon before =
      loop:=@file       →  ('', 'loop:@file')          colon immediately before =
    """
    if token.startswith("@"):
        return "", token
    dot = token.find(".")
    colon = token.find(":")
    eq = token.find("=")

    has_prefix = dot != -1 and colon != -1 and dot < colon and (eq == -1 or dot < eq)

    if has_prefix:
        return token[: colon + 1], token[colon + 1 :]

    if (
        dot != -1
        and eq != -1
        and dot < eq
        and (colon == -1 or colon > eq)
        and eq + 1 < len(token)
        and token[eq + 1] == "@"
    ):
        return token[:eq] + ":", token[eq + 1 :]

    if (
        colon != -1
        and eq != -1
        and colon == eq - 1
        and eq + 1 < len(token)
        and token[eq + 1] == "@"
    ):
        return "", token[: colon + 1] + token[eq + 1 :]

    # Recognize bare "frame.loop" (dot but no colon/eq) as empty-loop selector
    # Used by loops create to allow "frame.loop" meaning "create empty loop"
    if dot != -1 and colon == -1 and eq == -1:
        return token + ":", ""

    return "", token


_FLAG_NAME_TO_PLACEMENT: Dict[str, InsertPlacement] = {
    "before": InsertPlacement.BEFORE,
    "after": InsertPlacement.AFTER,
    "at": InsertPlacement.AT,
}


def _get_argv() -> List[str]:
    return sys.argv[1:]


def _trim_command_prefix(argv: List[str], ctx) -> List[str]:
    """Drop leading subcommand-name tokens (e.g. 'columns', 'insert') so getopt sees only
    the insert-level args. In CliRunner tests the mocked argv has no command names → no-op.
    """
    cmd_path: List[str] = []
    c = ctx
    while c is not None:
        if c.info_name:
            cmd_path.insert(0, c.info_name)
        c = c.parent
    idx = 0
    for name in cmd_path:
        for i in range(idx, len(argv)):
            if argv[i] == name:
                idx = i + 1
                break
    return argv[idx:]


def _build_getopt_strings(ctx) -> Tuple[str, List[str]]:
    """Build gnu_getopt short/long strings from the live context params."""
    short_opts, long_opts = "", []
    for param in ctx.command.params:
        if isinstance(param, click.Option):
            requires_arg = not param.is_flag
            for opt in param.opts:
                if opt.startswith("--"):
                    long_opts.append(opt[2:] + ("=" if requires_arg else ""))
                elif opt.startswith("-"):
                    short_opts += opt[1:] + (":" if requires_arg else "")
    return short_opts, long_opts


def _placement_token_map(ctx) -> Dict[str, str]:
    """Map every spelling of the placement flags to the param's variable name, derived
    from the live context. Placement params are identified by name membership in
    _FLAG_NAME_TO_PLACEMENT (the one semantic table); their spellings (--before, -b, ...)
    come from param.opts so they are never hardcoded.

    (Identifying by `param.callback is track_order` is avoided: Typer may wrap the callback,
    so callback identity is not reliable; param.name is stable.)
    """
    return {
        opt: param.name
        for param in ctx.command.params
        if isinstance(param, click.Option) and param.name in _FLAG_NAME_TO_PLACEMENT
        for opt in param.opts
    }


def track_order(ctx, param, value):
    """Typer option callback that records the interleaved order of placement flags and col
    specs. Builds the ordered structure once, on the first callback call (regardless of value,
    so no-flag invocations build it too). Subsequent calls just return value — the ordering is
    fully captured in ctx.obj["sequence"]."""
    if ctx.obj is None:
        ctx.obj = {}

    if "sequence" not in ctx.obj:
        argv = _trim_command_prefix(_get_argv(), ctx)
        short_opts, long_opts = _build_getopt_strings(ctx)
        placement_tokens = _placement_token_map(
            ctx
        )  # token -> param.name (e.g. "before")
        try:
            opts, positionals = getopt.gnu_getopt(argv, short_opts, long_opts)
        except getopt.GetoptError:
            opts, positionals = [], []  # Click is the real validator; don't hard-exit

        # unify by searching argv for each item's position
        items: List[OrderedArguments] = []
        used = set()
        for flag, val in opts:
            if flag in placement_tokens:
                for i, tok in enumerate(argv):
                    # match every form getopt accepts: '--before x', '--before=x', '-b x', '-bx'
                    space_form = (
                        tok == flag and i + 1 < len(argv) and argv[i + 1] == val
                    )
                    long_equals_form = flag.startswith("--") and tok == f"{flag}={val}"
                    short_attached_form = (
                        not flag.startswith("--") and tok == f"{flag}{val}"
                    )
                    if i not in used and (
                        space_form or long_equals_form or short_attached_form
                    ):
                        items.append(
                            OrderedArguments(i, "flag", placement_tokens[flag], val)
                        )
                        used.add(i)
                        if space_form:
                            used.add(i + 1)  # also reserve the separate anchor token
                        break
        for col in positionals:
            for i, tok in enumerate(argv):
                if i not in used and tok == col:
                    items.append(OrderedArguments(i, "col", None, col))
                    used.add(i)
                    break

        # the one ordered structure: flags + col specs interleaved, in argv order
        ctx.obj["sequence"] = sorted(items, key=lambda e: e.offset)

    return value


_FrameLoopGroups = Dict[str, List[ColumnPlacement]]
_ResolvedLoopColumnSpecificationPairs = List[Tuple[Loop, List[ColumnPlacement]]]


def _split_col_spec(token: str) -> Tuple[str, Optional[str]]:
    """Split 'col_name=value_spec' into (col_name, value_spec_or_None)."""
    parts = token.split("=", 1)
    return parts[0], parts[1] if len(parts) == 2 else None


def _split_frame_loop_prefix(col_spec: str) -> Tuple[Optional[str], str]:
    """Extract an embedded 'frame.loop:' prefix from col_spec.

    Returns (frame_loop, bare_spec) when a prefix is found, or (None, col_spec) otherwise.
    File references (starting with '@') never carry an embedded prefix.
    """
    if col_spec.startswith("@"):
        result = None, col_spec
    else:
        dot = col_spec.find(".")
        colon = col_spec.find(":")
        eq = col_spec.find("=")
        if dot != -1 and colon != -1 and dot < colon and (eq == -1 or dot < eq):
            result = col_spec[:colon], col_spec[colon + 1 :]
        else:
            result = None, col_spec
    return result


def _merge_selector_and_prefix(
    selector: Optional[str],
    frame_loop: Optional[str],
    bare_spec: str,
    original_col_spec: str,
) -> Tuple[str, str]:
    """Combine selector with extracted prefix to produce (frame_loop_str, bare_col_spec)."""
    if frame_loop is not None:
        return frame_loop, bare_spec
    if original_col_spec.startswith("@"):
        if selector is None:
            raise NEFInsertCLILoopNotDefinedException(original_col_spec, None, True)
        if "." not in selector:
            raise NEFInsertCLILoopNotDefinedException(original_col_spec, selector, True)
        return selector, original_col_spec
    if selector is None:
        # Before raising generic error, check for syntax errors (better error message)
        # Try parsing as frame.loop - if it fails with syntax error, let that propagate
        try:
            parse_frame_loop_and_tags(original_col_spec)
        except BadFrameLoopTagSyntaxException:
            raise  # Let syntax errors propagate with specific message
        raise NEFInsertCLILoopNotDefinedException(original_col_spec, None, False)
    if "." not in selector:
        colon = bare_spec.find(":")
        eq = bare_spec.find("=")
        if colon == -1 or (eq != -1 and colon > eq):
            raise NEFInsertCLILoopNotDefinedException(
                original_col_spec, selector, False
            )
        return f"{selector}.{bare_spec[:colon]}", bare_spec[colon + 1 :]
    return selector, bare_spec


def _resolve_col_spec_selector(
    selector: Optional[str], col_spec: str
) -> Tuple[str, str]:
    """Resolve a (possibly partial) selector against a col_spec string.

    Returns (frame_loop_str, bare_col_spec) where frame_loop_str is a complete
    'frame.loop' string suitable for parse_frame_loop_and_tags.

    selector may be:
    - None         : col_spec must be fully qualified 'frame.loop:col_specs'
    - 'frame'      : col_spec must supply 'loop:col_specs'
    - 'frame.loop' : col_spec is just 'col_specs'

    An embedded 'frame.loop:' prefix in col_spec always takes precedence over selector.
    File references (col_spec starting with '@') are never treated as frame.loop selectors.
    """
    frame_loop, bare_spec = _split_frame_loop_prefix(col_spec)
    return _merge_selector_and_prefix(selector, frame_loop, bare_spec, col_spec)


def _parse_position_anchor(anchor_str: Optional[str]) -> Optional[Union[int, str]]:
    """Convert a raw CLI anchor string to int if possible, else keep as str."""
    if anchor_str is None:
        return None
    try:
        return int(anchor_str)
    except ValueError:
        return anchor_str


def _expand_bare_file_refs(
    instructions: List[ColumnPlacement],
    skip: int = 0,
    comment: str = "",
) -> List[ColumnPlacement]:
    """Expand bare file-reference col specs into named col=@file:col instructions.

    Forms handled:

    @path              → one instruction per column in the CSV header (all columns)
    @path:col          → auto-names the NEF column from the normalised CSV column name
    @path:col1,col2    → multiple specific columns, each separately auto-named

    Raises NEFColumnsException (from columns_lib) if the file is not found or a column name/index is invalid.
    """
    result = []
    for instruction in instructions:
        col_name, value_spec = _split_col_spec(instruction.col_spec)
        if not col_name.startswith("@"):
            result.append(instruction)
        else:
            file_part, _, csv_cols = col_name[1:].partition(":")
            path = Path(file_part)
            if csv_cols:
                raw_cols = [c.strip() for c in csv_cols.split(",") if c.strip()]
                # Get column names from CSV file using csv_lib
                text = read_utf8_sig_file(path)
                headers, _, _ = parse_csv_text(
                    text, CsvLikeFormats.AUTO, skip, comment, source_path=path
                )
                cols = [_resolve_file_col_name(c, headers, path) for c in raw_cols]
            else:
                # Get all column names from CSV file
                text = read_utf8_sig_file(path)
                cols, _, _ = parse_csv_text(
                    text, CsvLikeFormats.AUTO, skip, comment, source_path=path
                )
            for c in cols:
                nef_col = escape_spaces_with_underscore(c)
                result.append(
                    ColumnPlacement(
                        f"{nef_col}=@{file_part}:{c}",
                        instruction.placement,
                        instruction.anchor,
                    )
                )
    return result


def _parse_ordered_col_instructions(
    ctx,
    ctx_args: List[str],
) -> List[ColumnPlacement]:
    """Build (col_spec, placement, anchor) instructions from the ordered argv structure.

    Walks ctx.obj["sequence"] (a List[OrderedArg] built by track_order, in argv order).
    Col specs accumulate as pending; a placement flag binds every pending col to that
    placement; any cols left over at the end default to APPEND. An embedded 'frame.loop:'
    prefix is peeled off each col-spec token and re-attached to every col spec it expands to.

    ctx_args is retained for error-message context in the caller; ordering comes entirely
    from ctx.obj["sequence"].

    If no sequence exists (no position flags), builds a simple sequence from ctx_args with
    all specs treated as cols (all get APPEND placement).
    """
    sequence = (ctx.obj or {}).get("sequence", []) if ctx else []

    # Fallback for commands without position flags (e.g., loops create)
    if not sequence and ctx_args:
        sequence = [
            OrderedArguments(i, "col", None, arg) for i, arg in enumerate(ctx_args)
        ]

    pending: List[str] = []
    instructions: List[ColumnPlacement] = []
    for arg in sequence:
        if arg.kind == "col":
            prefix, col_specs = _peel_selector_prefix(arg.value)
            split_specs = _split_on_column_specification_on_assignment_boundaries(
                col_specs
            )
            if split_specs:
                for col_spec in split_specs:
                    pending.append(prefix + col_spec)
            elif prefix:
                # Has frame.loop: prefix but no column specs (empty remainder after colon)
                # Keep the colon to maintain frame.loop: format for empty loops
                pending.append(prefix)
        else:  # flag
            for col in pending:
                instructions.append(
                    ColumnPlacement(col, _FLAG_NAME_TO_PLACEMENT[arg.name], arg.value)
                )
            pending = []
    for col in pending:
        instructions.append(ColumnPlacement(col, InsertPlacement.APPEND, None))
    return instructions


def _group_column_specifications_by_loop_or_raise(
    raw_loops_and_column_specifications: List[ColumnPlacement],
    selector: Optional[str],
) -> _FrameLoopGroups:
    column_specifications_grouped_by_frame_loop: _FrameLoopGroups = {}
    for instruction in raw_loops_and_column_specifications:
        frame_loop, bare_column = _resolve_col_spec_selector(
            selector, instruction.col_spec
        )
        column_specifications_grouped_by_frame_loop.setdefault(frame_loop, []).append(
            ColumnPlacement(bare_column, instruction.placement, instruction.anchor)
        )
    return column_specifications_grouped_by_frame_loop


def _resolve_frame_loop_strings_to_loops_or_raise(
    entry: Entry,
    column_specifications_grouped_by_frame_loop: _FrameLoopGroups,
    exact: bool = False,
) -> _ResolvedLoopColumnSpecificationPairs:
    resolved: _ResolvedLoopColumnSpecificationPairs = []
    for frame_loop_str, group in column_specifications_grouped_by_frame_loop.items():

        sel = parse_frame_loop_and_tags(frame_loop_str)

        for frame in select_frames(
            entry, [sel.frame_name], SelectionType.ANY, exact=exact
        ):
            loops = select_loops_by_category(
                frame.loops, [sel.loop_name] if sel.loop_name else []
            )
            if not loops and sel.loop_name:
                new_loop = Loop.from_scratch(sel.loop_name)
                try:
                    frame.add_loop(new_loop)
                except ValueError:

                    raise NEFColumnsDuplicateLoopException(sel.loop_name, frame.name)
                loops = [new_loop]
            for loop in loops:
                resolved.append((loop, group))
    return resolved


def _build_column_instructions(
    resolved_loop_column_specification_pairs: _ResolvedLoopColumnSpecificationPairs,
    skip: int = 0,
    comment: str = "",
    format: Optional["ExtractFormat"] = None,
) -> List[InsertInstruction]:
    column_instructions: List[InsertInstruction] = []
    for loop, group in resolved_loop_column_specification_pairs:
        for instruction in _expand_bare_file_refs(group, skip=skip, comment=comment):
            column_instructions.append(
                InsertInstruction(
                    column_spec_from_str(
                        instruction.col_spec, skip=skip, comment=comment, format=format
                    ),
                    instruction.placement,
                    _parse_position_anchor(instruction.anchor),
                    loop,
                )
            )
    return column_instructions


def _build_missing_loop_error_message(e: NEFInsertCLILoopNotDefinedException):
    if e.is_file_ref:
        if e.selector is None:
            msg = f"""
                    the column specification '{e.col_spec}' imports from a file but no target loop was specified;
                    either prefix it with '<frame>.<loop>:' or use --selector <frame>.<loop>
                """
            msg = textwrap.dedent(msg).strip()
        else:
            msg = f"""
                    the column specification '{e.col_spec}' imports from a file but the --selector '{e.selector}'
                    names only a frame; supply a '<frame>.<loop>' selector to define the target loop
                """
            msg = textwrap.dedent(msg).strip()
    else:
        if e.selector is None:
            msg = f"""
                    the column specification '{e.col_spec}' has no '<frame>.<loop>:' prefix and no --selector was given;
                    either prefix it with '<frame>.<loop>:<column-specification>' or define the target loops with
                    --selector <frame>.<loop>
                """
            msg = textwrap.dedent(msg).strip()
        else:
            msg = f"""
                    the column specification  '{e.col_spec}' has no loop name and ths selector --selector '{e.selector}'
                    only names  a frame; either prefix the column specification with '<loop>:<col-specificagtion>'
                    or define the loop with --selector <frame>.<loop>
                """
            msg = textwrap.dedent(msg).strip()

    return msg


# Rename Argument Parsing Functions


def _build_rename_parse_error_message(
    e: NEFColumnsRenameParseException,
    entry: Optional[Entry] = None,
    input_file: Optional[Path] = None,
) -> str:
    """Format rename parse exception into user-friendly message with context."""
    from nef_pipelines.lib.util import STDIN

    # Build error-specific message
    if e.error_type == "empty_tag":
        msg = f"tag name is empty in rename spec '{e.arg}'"
    elif e.error_type == "empty_new_name":
        msg = f"new name is empty in rename spec '{e.arg}'"
    elif e.error_type == "unpaired_tag":
        msg = f"unpaired tag '{e.arg}' - tags must come in pairs"
    elif e.error_type == "missing_selector":
        msg = f"bare tag '{e.arg}' requires --selector to be specified"
    else:
        msg = f"invalid rename specification: {e.arg}"

    # Add context if available
    context_parts = []
    if entry:
        context_parts.append(f"entry '{entry.entry_id}'")
    if input_file and input_file != STDIN:
        context_parts.append(f"file '{input_file}'")

    if context_parts:
        msg = f"{msg} [{', '.join(context_parts)}]"

    return msg


def _parse_rename_arguments_or_raise(
    arguments: List[str], selector: str = None
) -> List[Tuple[FrameLoopAndTagSelectors, str]]:
    """Parse rename arguments into (FrameLoopAndTagSelectors, new_name) pairs.

    Supports: frame.loop:tag=new, frame.loop:tag new, tag=new, tag new

    Raises:
        NEFColumnsRenameParseException: if arguments are malformed
    """
    pairs = []
    i = 0

    while i < len(arguments):
        if "=" in arguments[i]:
            parsed_selector, new_name = _parse_rename_equals_format(
                arguments[i], selector
            )
            pairs.append((parsed_selector, new_name))
            i += 1
        else:
            parsed_selector, new_name = _parse_rename_bare_pair(arguments, i, selector)
            pairs.append((parsed_selector, new_name))
            i += 2

    return pairs


def _parse_rename_equals_format(
    arg: str, selector: str
) -> Tuple[FrameLoopAndTagSelectors, str]:
    """Parse 'tag=new' or 'frame.loop:tag=new' format.

    Raises:
        NEFColumnsRenameParseException: if tag or new name is empty
    """
    tag_part, _, new_name = arg.partition("=")

    if not tag_part:
        raise NEFColumnsRenameParseException("empty_tag", arg, selector)
    if not new_name:
        raise NEFColumnsRenameParseException("empty_new_name", arg, selector)

    parsed_selector = _build_rename_selector_structure(tag_part, selector)
    return parsed_selector, new_name.strip()


def _parse_rename_bare_pair(
    arguments: List[str], index: int, selector: str
) -> Tuple[FrameLoopAndTagSelectors, str]:
    """Parse 'tag new' or 'frame.loop:tag new' bare pair format.

    Raises:
        NEFColumnsRenameParseException: if tag is unpaired
    """
    arg = arguments[index]

    if index + 1 >= len(arguments):
        raise NEFColumnsRenameParseException("unpaired_tag", arg, selector, index)

    next_arg = arguments[index + 1]
    if "=" in next_arg:
        raise NEFColumnsRenameParseException("unpaired_tag", arg, selector, index)

    parsed_selector = _build_rename_selector_structure(arg, selector)
    return parsed_selector, next_arg.strip()


def _build_rename_selector_structure(
    tag_part: str, selector: str
) -> FrameLoopAndTagSelectors:
    """Build FrameLoopAndTagSelectors directly from tag and optional --selector.

    Raises:
        NEFColumnsRenameParseException: if bare tag provided without --selector
    """
    from nef_pipelines.lib.structures import FrameLoopAndTagSelectors

    has_frame_loop = ":" in tag_part or "." in tag_part

    if has_frame_loop:
        # Parse full selector: frame.loop:tag
        return parse_frame_loop_and_tags(tag_part)

    # Bare tag - combine with --selector
    if not selector:
        raise NEFColumnsRenameParseException("missing_selector", tag_part, selector)

    # Parse selector to get frame and loop, then add tag
    base_selector = parse_frame_loop_and_tags(selector)
    return FrameLoopAndTagSelectors(
        frame_name=base_selector.frame_name,
        loop_name=base_selector.loop_name,
        frame_tags=[],
        loop_tags=[tag_part],
    )


# ===== REORDER PARSING =====


def _parse_reorder_arguments_or_raise(
    selector: Optional[str],
    column_order: List[str],
    policy: str,
) -> FrameLoopAndTagSelectors:
    """Parse reorder arguments into FrameLoopAndTagSelectors with new column order.

    Returns FrameLoopAndTagSelectors where loop_tags specifies the new order.
    Columns not in loop_tags stay at end in current order.

    Raises:
        NEFColumnsReorderMissingSelectorException: no selector and no frame.loop: prefix
        NEFColumnsReorderInvalidPolicyException: invalid policy value
        NEFColumnsReorderDuplicateColumnsException: duplicate columns in specification
    """
    from nef_pipelines.lib.structures import FrameLoopAndTagSelectors
    from nef_pipelines.tools.columns.columns_structures import (
        NEFColumnsReorderDuplicateColumnsException,
        NEFColumnsReorderInvalidPolicyException,
        NEFColumnsReorderMissingSelectorException,
    )

    # Validate policy
    from nef_pipelines.tools.columns.reorder import ColumnOrderPolicy

    valid_policies = [p.value for p in ColumnOrderPolicy]
    if policy not in valid_policies:
        raise NEFColumnsReorderInvalidPolicyException(policy, valid_policies)

    # If no --selector, first arg should be frame.loop:cols
    if selector is None:
        if not column_order:
            raise NEFColumnsReorderMissingSelectorException(None)
        first_arg = column_order[0]
        if ":" in first_arg:
            selector, _, cols = first_arg.partition(":")
            if cols:
                column_order = cols.split(",") + column_order[1:]
            else:
                column_order = column_order[1:]
        else:
            raise NEFColumnsReorderMissingSelectorException(first_arg)

    # Check for duplicates (excluding *)
    non_star_cols = [c for c in column_order if c != "*"]
    seen = set()
    duplicates = [c for c in non_star_cols if c in seen or seen.add(c)]
    if duplicates:
        raise NEFColumnsReorderDuplicateColumnsException(
            list(dict.fromkeys(duplicates)), selector
        )

    # Parse selector and return structure with column order in loop_tags
    parsed_selector = parse_frame_loop_and_tags(selector)
    return FrameLoopAndTagSelectors(
        frame_name=parsed_selector.frame_name,
        loop_name=parsed_selector.loop_name,
        frame_tags=[],
        loop_tags=column_order,
    )


def _parse_reorder_arguments_or_exit_error(
    selector: Optional[str],
    column_order: List[str],
    policy: str,
    entry: Entry,
    input_file: Path,
) -> FrameLoopAndTagSelectors:
    """Wrapper that formats exceptions and exits."""
    from nef_pipelines.lib.structures import NEFPipelinesException
    from nef_pipelines.lib.util import exit_error
    from nef_pipelines.tools.columns.columns_structures import (
        NEFColumnsReorderMissingSelectorException,
    )

    try:
        return _parse_reorder_arguments_or_raise(selector, column_order, policy)
    except NEFColumnsReorderMissingSelectorException as e:
        # Add helpful context for missing selector
        msg = str(e)
        msg += "\n\nLoop selector must specify both saveframe and loop."
        msg += "\nExamples:"
        msg += "\n  --selector myshifts.chemical_shift atom_name value"
        msg += "\n  myshifts.chemical_shift:atom_name,value"
        msg = _format_exception_with_context(
            NEFPipelinesException(msg), entry, input_file
        )
        exit_error(msg)
    except NEFPipelinesException as e:
        msg = _format_exception_with_context(e, entry, input_file)
        exit_error(msg)


# ===== REPLACE PARSING =====


def _parse_replace_arguments_or_raise(
    selector: Optional[str],
    replacements: List[str],
    entry: Entry,
    format: "ExtractFormat",
) -> List[InsertInstruction]:
    """Parse replace arguments into InsertInstructions.

    Replace is just insert with @file:col specifications and --at placement.
    Directly builds InsertInstructions without roundtrip string parsing.

    TODO: Currently only supports paired format (frame.loop:col @file) and @file value specs.
          Should support insert syntax: frame.loop:col=@file, frame.loop:col=1..10, etc.
          Imbalanced argument sets (odd number of args) are not allowed in paired format.

    Raises:
        NEFColumnsReplaceInvalidFormatException: invalid argument format
    """

    if len(replacements) % 2 != 0:
        raise NEFColumnsReplaceInvalidFormatException(
            f"{len(replacements)} arguments",
            "selector @file:col or col @file:col (must be pairs)",
        )

    instructions = []
    for i in range(0, len(replacements), 2):
        selector_arg = replacements[i]
        file_arg = replacements[i + 1]

        if not file_arg.startswith("@"):
            raise NEFColumnsReplaceInvalidFormatException(
                file_arg, "file reference must start with '@'"
            )

        # Parse selector to get frame, loop, and column
        parsed_selector = parse_frame_loop_and_tags(selector_arg)
        if not parsed_selector.loop_tags or len(parsed_selector.loop_tags) != 1:
            raise NEFColumnsReplaceInvalidFormatException(
                selector_arg,
                "each selector must specify exactly one column",
            )

        col_name = parsed_selector.loop_tags[0]

        # Parse file reference: @file:col or @file
        remainder = file_arg[1:]
        file_part, _, file_col_part = remainder.partition(":")
        file_path = Path(file_part)
        file_col = file_col_part if file_col_part else col_name

        # Find the target loop
        frames = select_frames(entry, [parsed_selector.frame_name], SelectionType.ANY)
        for frame in frames:
            loops = select_loops_by_category(
                frame.loops,
                [parsed_selector.loop_name] if parsed_selector.loop_name else [],
            )
            for loop in loops:
                # Build InsertInstruction directly
                value_spec = FileValueSpecification(
                    path=file_path,
                    col=file_col,
                    format=format,
                )
                col_spec = ColumnSpecification(
                    col_name=col_name,
                    value_spec=value_spec,
                )
                instructions.append(
                    InsertInstruction(
                        column_spec=col_spec,
                        keyword=InsertPlacement.AT,
                        position_anchor=col_name,
                        loop=loop,
                    )
                )

    return instructions


def _parse_replace_arguments_or_exit_error(
    selector: Optional[str],
    replacements: List[str],
    entry: Entry,
    input_file: Path,
    format: "ExtractFormat",
) -> List[InsertInstruction]:
    """Wrapper that formats exceptions and exits."""
    from nef_pipelines.lib.structures import NEFPipelinesException
    from nef_pipelines.lib.util import exit_error

    try:
        return _parse_replace_arguments_or_raise(selector, replacements, entry, format)
    except NEFPipelinesException as e:
        msg = _format_exception_with_context(e, entry, input_file)
        exit_error(msg)


# ===== SHARED UTILITIES =====


def _format_exception_with_context(
    e: Exception,
    entry: Optional[Entry] = None,
    input_file: Optional[Path] = None,
) -> str:
    """Format any NEFPipelinesException with entry/file context.

    Uses exception's __str__() for base message, adds context.
    Each exception class defines its own __str__() with specific fields.
    """
    from nef_pipelines.lib.util import STDIN

    msg = str(e)

    context_parts = []
    if entry:
        context_parts.append(f"entry '{entry.entry_id}'")
    if input_file and input_file != STDIN:
        context_parts.append(f"file '{input_file}'")

    if context_parts:
        msg = f"{msg} [{', '.join(context_parts)}]"

    return msg
