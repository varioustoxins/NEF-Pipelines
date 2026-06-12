from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple

import typer
from click import Context
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib.cli_lib import (
    SELECT_ALL_FRAME_CATEGORIES_AND_TAGS,
    expand_default_frame_loop_and_tag_wildcards,
    parse_frame_loop_and_tags,
    print_output_or_exit_error,
    selection_to_frame_loops_and_tags,
)
from nef_pipelines.lib.namespace_lib import (
    collect_namespaces_from_frames,
    filter_frame_loops_and_tags_by_namespace,
    filter_namespaces,
)
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.structures import FrameLoopsAndTags
from nef_pipelines.lib.util import STDIN, exit_error, warn
from nef_pipelines.tools.frames import frames_app

DEFAULT_ROW_COUNT = 10


@dataclass
class _FrameDisplayFlags:
    showing_frame_tags: bool
    showing_loop_data: bool
    showing_loop_placeholder: bool
    is_complete_frame: bool
    add_frame_markers: bool


class DisplayMode(Enum):
    """Display mode for loop rows."""

    ALL = "all"
    HEAD = "head"
    MIDDLE = "middle"
    TAIL = "tail"


@dataclass
class DisplayOptions:
    """Formatting options for display output."""

    display_modes: List[Any] = field(default_factory=list)
    count: int = 10
    exact: bool = False
    no_comments: bool = False


@frames_app.command()
def display(
    context: Context,
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="read NEF data from a file instead of stdin",
    ),
    exact: bool = typer.Option(
        False,
        "-e",
        "--exact",
        help="use exact matching in frame loop and tag selectors (no wildcards)",
    ),
    out: Optional[str] = typer.Option(
        "@auto",
        "--out",
        help="""\
            output destinations:
            - `@auto` [default] - If stdout is a terminal, write displayed saveframes to stdout (entry suppressed).
              If stdout is a pipe/stream, write entry to stdout and displayed saveframes to stderr.

            - `-`, `@out` - Write displayed saveframes to stdout, don't output the entry.

            - `@err` - Write displayed saveframes to stderr, write entry to stdout.

            - `<filename>` - Write displayed saveframes to file, write entry to stdout.


            Use backslash to escape @ (e.g., \\@file).
            """,
    ),
    # TODO: Support explicit index ranges for AI-friendly row selection
    #       e.g., --rows 1-5,10-15 or --rows 0,5,10,15
    #       This would complement --head/--middle/--tail with precise control
    head: bool = typer.Option(
        False,
        "--head",
        help=f"""\
            show first N rows of loops (use with --count, default is {DEFAULT_ROW_COUNT});
            additive with --middle and --tail
        """,
    ),
    middle: bool = typer.Option(
        False,
        "--middle",
        help=f"""\
            show middle N rows of loops (use with --count, default is {DEFAULT_ROW_COUNT});
            additive with --tail and --head
        """,
    ),
    tail: bool = typer.Option(
        False,
        "--tail",
        help=f"""\
            show last N rows of loops (use with --count, default is {DEFAULT_ROW_COUNT});
            additive with --head and --middle
        """,
    ),
    count: int = typer.Option(
        DEFAULT_ROW_COUNT,
        "--count",
        help="number of rows to display with --head, --middle, or --tail",
    ),
    no_comments: bool = typer.Option(
        False,
        "--no-comments",
        help="suppress comments (frame headers, ellipsis, etc.)",
    ),
    namespace_selectors: Optional[List[str]] = typer.Option(
        None,
        "--namespace",
        help="filter frames by namespace (+nef to include, -ccpn to exclude etc)",
    ),
    no_initial_namespace_selection: bool = typer.Option(
        False,
        "--no-initial-namespace-selection",
        help="start with empty namespace selection instead of all",
    ),
    selectors: Optional[List[str]] = typer.Argument(
        None,
        help="selectors for what to display in the format frame.loop:tag1,tag2 (wildcards supported)",
    ),
    force: bool = typer.Option(False, "--force", help="overwrite existing files"),
):
    """\
    - display selected loops/frames with specified tags only

    Namespace filtering allows including/excluding frames by namespace prefix:
    - +nef includes only nef frames
    - -ccpn excludes ccpn frames
    - --no-initial-namespace-selection starts with empty set instead of all

    ```bash
    Examples:

        # show the heads of chemical shift frames
        nef frames display file.nef "shift.chemical_shift:*" --head --count 5

        # show contents of frames not in the nef namespace
        nef frames display file.nef --namespace -nef

        # display the frame tags from all non ccpn frames
        nef frames display file.nef "*:*" --namespace -ccpn

        # display all frame tags for frames tags and loops in the nef namespace only
        nef frames display file.nef "shift:*" --namespace +nef --no-initial-namespace-selection
    ```
    """

    # Handle polymorphic first arg (file vs selector)
    input, selectors = _parse_polymorphic_entry_inputs(input, selectors)

    # TODO [future] we really want a version that also displays help first...
    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Parse selectors OUTSIDE pipe (follows CLAUDE.md pattern)
    parsed_selectors = _parse_selectors(selectors)

    display_modes = _extract_display_modes(head, middle, tail)

    # Create display options (refactoring item 1)
    display_options = DisplayOptions(
        display_modes=display_modes,
        count=count,
        exact=exact,
        no_comments=no_comments,
    )

    # TODO [future] move to namespace_lib and add tests
    namespaces = _parse_and_select_namespaces(
        entry, namespace_selectors, no_initial_namespace_selection
    )

    matched_items = selection_to_frame_loops_and_tags(
        entry,
        parsed_selectors,
        exact=exact,
    )
    if namespaces is not None:
        matched_items = filter_frame_loops_and_tags_by_namespace(
            matched_items, namespaces
        )

    # Call pipe function (business logic)
    entry, output_dict = pipe(
        entry,
        matched_items,
        display_options,
    )

    print_output_or_exit_error(entry, out, output_dict, force)


def pipe(
    entry: Entry,
    frames_loops_and_tags: List[FrameLoopsAndTags],
    display_options: DisplayOptions,
) -> Tuple[Optional[Entry], Dict[str, str]]:
    """\
    Worker function that formats already-matched frames/loops for display.

    Args:
        entry: Input NEF entry
        frames_loops_and_tags: One FrameLoopsAndTags per matched frame
        display_options: DisplayOptions containing display_modes, count, exact, no_comments

    Returns:
        (entry_to_stream, output_dict)
    """
    display_lines = []

    target_frames = {item.frame.name: item for item in frames_loops_and_tags}

    if target_frames:
        prev_frame_was_collapsed = False
        for frame in entry.frame_list:
            if frame.name in target_frames:
                if prev_frame_was_collapsed and display_lines:
                    display_lines.append("")
                prev_frame_was_collapsed = False

                selected_frame = target_frames[frame.name]

                flags = _compute_frame_display_flags(selected_frame, display_options)

                frame_open_lines = _format_frame_open(selected_frame.frame.name, flags)
                frame_tag_lines = _process_frame_tags(
                    selected_frame, display_options, flags
                )
                loop_lines = _process_loops(selected_frame, display_options, flags)
                frame_close_lines = _format_frame_close(flags)

                lines = [
                    *frame_open_lines,
                    *frame_tag_lines,
                    *loop_lines,
                    *frame_close_lines,
                ]

                display_lines.extend(_indent_frame_content(lines))
            else:
                hints = _format_collapsed_frame_hint(
                    frame.name, display_options.no_comments
                )
                display_lines.extend(hints)
                if hints:
                    prev_frame_was_collapsed = True

    return entry, {"-": "\n".join(display_lines)}


def _process_loops(
    selected_frame: FrameLoopsAndTags,
    display_options: DisplayOptions,
    flags: _FrameDisplayFlags,
) -> List[str]:
    lines: List[str] = []
    for loop in selected_frame.loops:
        _process_loop_or_placeholder(
            lines,
            loop,
            selected_frame.loop_tags.get(loop.category, []),
            display_options,
        )
    if not display_options.no_comments and not flags.is_complete_frame:
        _append_collapsed_loop_hints(lines, selected_frame)
    return lines


def _process_frame_tags(
    selected_frame: FrameLoopsAndTags,
    display_options: DisplayOptions,
    flags: _FrameDisplayFlags,
) -> List[str]:
    lines: List[str] = []
    if flags.showing_frame_tags:
        lines.extend(
            _format_frame_tags(selected_frame.frame, selected_frame.frame_tags)
        )
        if not display_options.no_comments and _is_partial_frame_tags(selected_frame):
            lines.append("   # more frame tags...")
    elif flags.showing_loop_data and not display_options.no_comments:
        lines.append("# frame tags ...")
        lines.append("")
    return lines


def _compute_frame_display_flags(
    item: FrameLoopsAndTags, display_options: DisplayOptions
) -> _FrameDisplayFlags:
    no_loops = not item.loops
    has_loops = bool(item.loops)

    # A loop is "fully expanded" when either all columns are selected (loop_tags equals
    # the full tag list) or no column filter was applied at all (loop_tags is empty —
    # bare loop, command shows everything).
    all_loops_fully_expanded = has_loops and all(
        not item.loop_tags.get(lp.category, [])
        or set(item.loop_tags.get(lp.category, [])) == set(lp.tags)
        for lp in item.loops
    )

    # After wildcard expansion, bare-frame selectors produce a non-empty frame_tags list
    # (design doc §3), so this cleanly separates frame-tag selections from loop-only ones.
    has_frame_tag_selection = bool(item.frame_tags)

    # Show frame tags when: no loops present (frame-tag only selection), OR every loop is
    # fully expanded and frame tags were selected (whole-frame or explicit tag selection).
    should_show_frame_tags = no_loops or (
        all_loops_fully_expanded and has_frame_tag_selection
    )

    showing_frame_tags = should_show_frame_tags
    showing_loop_data = has_loops
    showing_loop_placeholder = (
        False  # No longer used (was for removed --tags-only flag)
    )

    # Complete frame: all tags shown, all loops present, all columns shown — use raw
    # save_/save_ markers instead of commented # save_ markers.
    is_complete_frame = _is_complete_frame_selection(
        item, showing_frame_tags, showing_loop_data
    )
    add_frame_markers = not display_options.no_comments and (
        showing_frame_tags or showing_loop_data
    )

    return _FrameDisplayFlags(
        showing_frame_tags=showing_frame_tags,
        showing_loop_data=showing_loop_data,
        showing_loop_placeholder=showing_loop_placeholder,
        is_complete_frame=is_complete_frame,
        add_frame_markers=add_frame_markers,
    )


def _process_loop_or_placeholder(
    lines: list[Any],
    loop: Loop,
    loop_tags: List[str],
    display_options: DisplayOptions,
) -> None:
    display_modes = (
        display_options.display_modes
        if display_options.display_modes
        else [DisplayMode.ALL]
    )
    indices = _calculate_display_indices(
        len(loop.data), display_modes, display_options.count
    )
    loop_lines = _format_loop_data(loop, loop_tags, indices)

    # Add "# more columns..." if showing partial columns
    if not display_options.no_comments and _is_partial_loop_columns(loop, loop_tags):
        loop_lines = _insert_more_columns_comment(loop_lines)

    if not display_options.no_comments and len(indices) < len(loop.data):
        loop_lines = _insert_ellipsis_comments(loop_lines, indices, len(loop.data))

    loop_text = "\n".join(loop_lines)
    lines.extend(dedent(loop_text).split("\n"))


# ============================
# ATOMIC FORMATTING FUNCTIONS
# ============================


def _get_collapsed_loops(item: FrameLoopsAndTags) -> List[str]:
    """Get list of loop categories in frame but not selected.

    Args:
        item: FrameLoopsAndTags for one frame

    Returns:
        List of collapsed loop categories
    """
    frame_loop_categories = {loop.category for loop in item.frame.loops}
    selected_loop_categories = {loop.category for loop in item.loops}
    collapsed = frame_loop_categories - selected_loop_categories
    return sorted(collapsed)


def _is_partial_frame_tags(item: FrameLoopsAndTags) -> bool:
    """Check if showing some but not all frame tags.

    Args:
        item: FrameLoopsAndTags for one frame

    Returns:
        True if partial tag selection
    """
    if not item.frame_tags:
        return False  # No frame-tag selection — not a partial display

    # Count total tags in frame ([all names] == total → complete, not partial)
    total_tags = sum(1 for _ in item.frame.tag_iterator())
    selected_count = len(item.frame_tags)

    return selected_count < total_tags


def _is_partial_loop_columns(loop: Loop, loop_tags: List[str]) -> bool:
    """Check if showing some but not all columns in a loop.

    Args:
        loop: The loop
        loop_tags: Selected columns ([] means all; full column list also means all;
            a strict subset means partial)

    Returns:
        True if partial column selection
    """
    if not loop_tags:
        return False  # Bare loop — showing all columns

    return len(loop_tags) < len(loop.tags)


def _is_complete_frame_selection(
    item: FrameLoopsAndTags, showing_frame_tags: bool, showing_loop_data: bool
) -> bool:
    """Determine if we're showing a complete frame (all tags, all loops, all columns).

    Complete frame means:
    - All frame tags are being SHOWN (the full frame-tag set is selected)
    - All loops from frame are present
    - All columns in each loop are shown ([] = bare loop, or the full column set)

    Args:
        item: FrameLoopsAndTags for one frame
        showing_frame_tags: True if frame tags are being displayed
        showing_loop_data: True if loop data is being displayed

    Returns:
        True if showing complete frame, False if partial selection
    """
    # If not showing frame tags, it's not a complete frame
    if not showing_frame_tags:
        return False

    # If not showing loops, it's not a complete frame
    if not showing_loop_data:
        return False

    # Check if all loops from the frame are present
    frame_loop_categories = {loop.category for loop in item.frame.loops}
    selected_loop_categories = {loop.category for loop in item.loops}
    all_loops_present = frame_loop_categories == selected_loop_categories

    # Each loop shows all columns when bare ([]) or its full column set is selected
    all_columns_selected = all(
        not item.loop_tags.get(loop.category, [])
        or set(item.loop_tags.get(loop.category, [])) == set(loop.tags)
        for loop in item.loops
    )

    # Frame tags complete when the full frame-tag set is selected. Reached only while
    # showing_frame_tags, so item.frame_tags is non-empty here ([] would mean collapsed).
    all_frame_tag_names = {tag for tag, _ in item.frame.tag_iterator()}
    frame_tags_complete = set(item.frame_tags) == all_frame_tag_names

    return frame_tags_complete and all_loops_present and all_columns_selected


def _format_frame_start_comment(frame_name: str) -> List[str]:
    """Generate frame start comment (commented save marker for partial selections).

    Returns:
        ["# save_{frame_name}", ""]
    """
    return [f"# save_{frame_name}", ""]


def _format_frame_end_comment() -> List[str]:
    """Generate frame end comment (commented save marker for partial selections).

    Returns:
        ["", "# save_", ""]
    """
    return ["", "# save_", ""]


def _format_frame_start_marker(frame_name: str) -> List[str]:
    """Generate frame start marker (uncommented for complete frames).

    Returns:
        ["save_{frame_name}", ""]
    """
    return [f"save_{frame_name}", ""]


def _format_frame_end_marker() -> List[str]:
    """Generate frame end marker (uncommented for complete frames).

    Returns:
        ["", "save_", ""]
    """
    return ["", "save_", ""]


def _format_collapsed_frame_hint(frame_name: str, no_comments: bool) -> List[str]:
    if no_comments:
        return []
    return [f"# frame {frame_name} ..."]


def _format_frame_open(frame_name: str, flags: _FrameDisplayFlags) -> List[str]:
    if not flags.add_frame_markers:
        return []
    if flags.is_complete_frame:
        return _format_frame_start_marker(frame_name)
    return _format_frame_start_comment(frame_name)


def _format_frame_close(flags: _FrameDisplayFlags) -> List[str]:
    if not flags.add_frame_markers:
        return []
    if flags.is_complete_frame:
        return ["", *_format_frame_end_marker()]
    return ["", *_format_frame_end_comment()]


def _append_collapsed_loop_hints(lines: List[str], item: FrameLoopsAndTags) -> None:
    """Append placeholder comments for loops that exist but weren't selected."""
    collapsed_loops = _get_collapsed_loops(item)
    for loop_category in collapsed_loops:
        lines.append(f"# loop {loop_category.lstrip('_')} ...")
    if collapsed_loops:
        lines.append("")


def _indent_frame_content(lines: List[str]) -> List[str]:
    """
    Add 4-space base indentation to frame content, normalizing loop content to 8 spaces.

    Frame markers (save_..., # save_) remain unindented.
    Loop keywords (loop_, stop_) get 4 spaces.
    Loop content (columns starting with _, data rows) get 8 spaces total.
    Other content gets 4 spaces.

    Args:
        lines: List of formatted frame lines

    Returns:
        List with proper indentation
    """
    result = []
    in_loop = False

    for line in lines:
        stripped = line.strip()

        # Don't indent empty lines or frame markers
        if not line or line.startswith("save_") or line.startswith("# save"):
            result.append(line)
            continue

        # Track loop boundaries
        if stripped == "loop_":
            in_loop = True
            result.append("    " + stripped)
        elif stripped == "stop_":
            in_loop = False
            result.append("    " + stripped)
        elif in_loop:
            # Loop content: columns (start with _) and data rows get 8 spaces
            result.append("        " + stripped)
        else:
            # Other content (frame tags, comments) gets 4 spaces - use stripped to normalize
            result.append("    " + stripped)

    return result


def _format_frame_tags(frame: Saveframe, selected_tags: List[str]) -> List[str]:
    """Format frame tags by building a filtered saveframe copy and using pynmrstar str()."""
    selected_pairs = [
        (name, val)
        for name, val in frame.tag_iterator()
        if name in selected_tags or not selected_tags
    ]
    if not selected_pairs:
        return []

    temp = Saveframe.from_scratch(frame.name, frame.tag_prefix)
    for name, value in selected_pairs:
        temp.add_tag(name, value if value != "" else None)

    frame_lines = str(temp).split("\n")

    # Strip save_ header (first line) and save_ footer
    result = []
    for line in frame_lines[1:]:
        if line.strip() == "save_":
            break
        result.append(line)
    return result


def _calculate_display_indices(
    total_rows: int, display_modes: List[DisplayMode], count: int
) -> List[int]:
    """Calculate which row indices to include based on display modes.

    Args:
        total_rows: Total number of rows in the loop
        display_modes: List of display modes (HEAD, MIDDLE, TAIL, ALL)
        count: Number of rows for HEAD/MIDDLE/TAIL modes

    Returns:
        Sorted list of row indices to display
    """
    # Collect row indices from all display modes (additive)
    if DisplayMode.ALL in display_modes or total_rows <= count:
        # Show all rows if ALL mode or data is smaller than count
        indices_to_include = set(range(total_rows))
    else:
        indices_to_include = set()
        for mode in display_modes:
            if mode == DisplayMode.HEAD:
                indices_to_include.update(range(min(count, total_rows)))
            elif mode == DisplayMode.MIDDLE:
                start = max(0, (total_rows - count) // 2)
                end = min(total_rows, start + count)
                indices_to_include.update(range(start, end))
            elif mode == DisplayMode.TAIL:
                indices_to_include.update(range(max(0, total_rows - count), total_rows))

    # Convert to sorted list for ordered display
    return sorted(indices_to_include)


def _format_loop_data(
    loop: Loop, selected_tags: List[str], indices_to_include: List[int]
) -> List[str]:
    """Format loop data using pynmrstar (no comments).

    Args:
        loop: The loop to format
        selected_tags: List of tag names to include (empty list = all tags)
        indices_to_include: Row indices to include

    Returns:
        List of lines containing loop structure: ["loop_", "   _tag1", ..., "   value1", ..., "stop_"]
    """
    # If no tags specified, use all tags
    tags_to_show = selected_tags if selected_tags else loop.tags
    tag_indices = [loop.tags.index(tag) for tag in tags_to_show]

    # Build new loop with selected tags using pynmrstar
    new_loop = Loop.from_scratch(loop.category)

    # Add selected tags
    for tag in tags_to_show:
        new_loop.add_tag(tag)

    # Add data rows (only selected columns)
    for idx in indices_to_include:
        row = loop.data[idx]
        values = [row[i] for i in tag_indices]
        new_loop.add_data(values)

    # Create temporary saveframe and format using pynmrstar
    temp_frame = Saveframe.from_scratch("temp", loop.category)
    temp_frame.add_loop(new_loop)

    # Get formatted string and extract loop portion
    frame_str = str(temp_frame)

    # Extract just the loop (skip saveframe header/footer)
    frame_lines = frame_str.split("\n")
    in_loop = False
    loop_lines = []
    for line in frame_lines:
        if line.strip().startswith("loop_"):
            in_loop = True
        if in_loop:
            loop_lines.append(line)
            if line.strip().startswith("stop_"):
                break

    return loop_lines


def _insert_more_columns_comment(loop_lines: List[str]) -> List[str]:
    """Insert '# more columns...' comment in loop header after tag list.

    TODO: [future] Show column count: "# ... 5 more columns ..." instead of "# more columns..."
          Optionally show first and last omitted column names: "# ... 5 more columns (atom_id through merit) ..."

    Args:
        loop_lines: Loop lines from pynmrstar formatting

    Returns:
        Modified loop lines with comment inserted
    """
    result = []
    in_tags = False
    tags_done = False

    for line in loop_lines:
        stripped = line.strip()

        # Detect loop start
        if stripped.startswith("loop_"):
            in_tags = True
            result.append(line)
            continue

        # If in tags section and line starts with underscore, it's a tag
        if in_tags and stripped.startswith("_"):
            result.append(line)
            continue

        # First non-tag line after tags - insert comment before it
        if in_tags and not stripped.startswith("_") and not tags_done:
            result.append("   # more columns...")
            tags_done = True

        result.append(line)

    return result


def _insert_ellipsis_comments(
    loop_lines: List[str], indices_to_include: List[int], total_rows: int
) -> List[str]:
    """Insert ellipsis comments for omitted rows.

    Args:
        loop_lines: Loop lines from _format_loop_data()
        indices_to_include: Row indices that were included
        total_rows: Total number of rows in original loop

    Returns:
        Modified loop_lines with ellipsis comments inserted
    """

    def _add_ellipsis_insertion(
        insertions: List[Tuple[int, str]], position: int, gap_size: int
    ) -> None:
        """Add ellipsis comment lines to insertions list for a gap of given size."""
        insertions.append((position, ""))
        insertions.append((position, f" # ... {gap_size} rows omitted ..."))
        insertions.append((position, ""))

    # Find data row section and stop_
    # tag_end_idx = first non-empty, non-tag, non-loop_, non-comment line (actual data starts here)
    tag_end_idx = None
    stop_idx = None
    for i, line in enumerate(loop_lines):
        stripped = line.strip()
        if (
            stripped
            and not stripped.startswith("_")
            and not stripped.startswith("loop_")
            and not stripped.startswith("#")
            and tag_end_idx is None
        ):
            tag_end_idx = i
        if stripped.startswith("stop_"):
            stop_idx = i
            break

    if tag_end_idx is None or stop_idx is None:
        return loop_lines

    # Insert ellipsis for gaps
    insertions = []  # List of (position, text) to insert
    output_idx = 0
    prev_orig_idx = -1

    # Check if rows omitted at the beginning
    if indices_to_include[0] > 0:
        gap_size = indices_to_include[0]
        _add_ellipsis_insertion(insertions, tag_end_idx, gap_size)

    for orig_idx in indices_to_include:
        if prev_orig_idx >= 0 and orig_idx > prev_orig_idx + 1:
            # There's a gap in the middle
            gap_size = orig_idx - prev_orig_idx - 1
            insert_pos = tag_end_idx + output_idx
            _add_ellipsis_insertion(insertions, insert_pos, gap_size)

        output_idx += 1
        prev_orig_idx = orig_idx

    # Check if rows omitted at the end
    if indices_to_include[-1] < total_rows - 1:
        gap_size = total_rows - indices_to_include[-1] - 1
        insert_pos = tag_end_idx + output_idx
        _add_ellipsis_insertion(insertions, insert_pos, gap_size)

    # Insert ellipsis in reverse order to maintain indices
    for pos, text in reversed(insertions):
        loop_lines.insert(pos, text)

    return loop_lines


# ======================
# ORCHESTRATOR FUNCTION
# ======================


def _parse_and_select_namespaces(
    entry: Entry, namespaces: Optional[List[str]], no_initial_selection: bool
) -> Optional[set[str]]:
    if not namespaces and not no_initial_selection:
        return None  # No filtering requested

    # Parse namespace selectors OUTSIDE pipe (refactoring item 2)
    # Collect actual namespaces from entry
    namespace_dict = collect_namespaces_from_frames(entry.frame_list)
    all_namespaces = set(namespace_dict.keys())

    # Select from actual namespaces using selectors
    selected_namespaces = _parse_namespace_selectors(
        entry, namespaces, no_initial_selection
    )

    # Validate that selected namespaces exist in entry
    invalid_namespaces = selected_namespaces - all_namespaces
    if invalid_namespaces:
        available = ", ".join(sorted(all_namespaces)) if all_namespaces else "none"
        warn(
            f"Namespace selectors {', '.join(namespaces)} didn't select any valid namespaces. "
            f"Invalid: {', '.join(sorted(invalid_namespaces))}. "
            f"Available namespaces are: {available}"
        )
    return selected_namespaces


# TODO this should be a utility function
def _parse_polymorphic_entry_inputs(
    input: Path, selectors: Optional[List[str]]
) -> Tuple[Path, Optional[List[str]]]:
    if selectors and len(selectors) > 0 and Path(selectors[0]).is_file():
        if input != STDIN:
            msg = "you specified two inputs --input {input} and {putative_file} please choose only one!"
            exit_error(msg)
        else:
            input = selectors[0]
            selectors = selectors[1:]
    return input, selectors


def _extract_display_modes(head: bool, middle: bool, tail: bool) -> List[Any]:
    # Collect display modes (additive)
    display_modes = []
    if head:
        display_modes.append(DisplayMode.HEAD)
    if middle:
        display_modes.append(DisplayMode.MIDDLE)
    if tail:
        display_modes.append(DisplayMode.TAIL)
    if not display_modes:
        display_modes = [DisplayMode.ALL]
    return display_modes


def _parse_selectors(selectors: Optional[List[str]]) -> List[Any]:

    if not selectors:
        selectors = [SELECT_ALL_FRAME_CATEGORIES_AND_TAGS]  # Default

    return [
        expand_default_frame_loop_and_tag_wildcards(parse_frame_loop_and_tags(selector))
        for selector in selectors
    ]


def _parse_namespace_selectors(
    entry: Entry, namespace: Optional[List[str]], no_initial_selection: bool
) -> set[str]:
    """
    Parse namespace selectors and return the set of selected namespaces.

    Args:
        entry: Input NEF entry
        namespace: List of namespace selectors (+nef, -ccpn, etc.) or None
        no_initial_selection: If True, start with empty set instead of all namespaces

    Returns:
        Set of selected namespace strings
    """
    if not namespace:
        # No filtering - return all namespaces
        namespace_dict = collect_namespaces_from_frames(entry.frame_list)
        return set(namespace_dict.keys())

    # Collect all namespaces from the entry
    namespace_dict = collect_namespaces_from_frames(entry.frame_list)
    all_namespaces = set(namespace_dict.keys())

    # Apply filtering using filter_namespaces
    selected = filter_namespaces(
        all_namespaces,
        namespace,
        use_separator_escapes=False,
        no_initial_selection=no_initial_selection,
    )

    return selected
