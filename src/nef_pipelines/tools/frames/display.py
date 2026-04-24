import sys
from collections import OrderedDict
from enum import Enum
from fnmatch import fnmatchcase
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, List, Optional, Tuple, Union

import typer
from click import Context
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib.cli_lib import (
    SELECT_ALL_FRAME_CATEGORIES_AND_TAGS,
    parse_frame_loop_and_tags,
)
from nef_pipelines.lib.namespace_lib import (
    collect_namespaces_from_frames,
    filter_namespaces,
    get_namespace,
)
from nef_pipelines.lib.nef_lib import (
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
    select_loops_by_category,
)
from nef_pipelines.lib.structures import (
    DisplayOptions,
    EntryPart,
    FrameLoopAndTagSelectors,
    FramesLoopAndTags,
)
from nef_pipelines.lib.util import STDIN, exit_error, warn
from nef_pipelines.tools.frames import frames_app

DEFAULT_ROW_COUNT = 10


class DisplayMode(Enum):
    """Display mode for loop rows."""

    ALL = "all"
    HEAD = "head"
    MIDDLE = "middle"
    TAIL = "tail"


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
    tags_only: bool = typer.Option(
        False,
        "--tags-only",
        help="show only tag-value pairs, not loop data",
    ),
    loops_only: bool = typer.Option(
        False,
        "--loops-only",
        help="show only loop data, not saveframe tags",
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
    no_initial_selection: bool = typer.Option(
        False,
        "--no-initial-selection",
        help="start with empty namespace selection instead of all",
    ),
    selectors: Optional[List[str]] = typer.Argument(
        None,
        help="selectors for what to display in the format frame.loop:tag1,tag2 (wildcards supported)",
    ),
    # TODO [Future] exact!
    force: bool = typer.Option(False, "--force", help="overwrite existing files"),
):
    """\
    - display selected loops/frames with specified tags only

    Namespace filtering allows including/excluding frames by namespace prefix:
    - +nef includes only nef frames
    - -ccpn excludes ccpn frames
    - --no-initial-selection starts with empty set instead of all

    ```bash
    Examples:

        # show the heads of chemical shift frames
        nef frames display file.nef "shift.chemical_shift:*" --head --count 5

        # show contents of frames not in the nef namespace
        nef frames display file.nef --namespace -nef

        # display the frame tags from all non ccpn frames
        nef frames display file.nef "*:*" --namespace -ccpn

        # display all frame tags for frames tags and loops in the nef namespace only
        nef frames display file.nef "shift:*" --namespace +nef --no-initial-selection
    ```
    """

    # Handle polymorphic first arg (file vs selector)
    input, selectors = _parse_polymorphic_entry_inputs(input, selectors)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    # Parse selectors OUTSIDE pipe (follows CLAUDE.md pattern)
    parsed_selectors = _parse_selectors(selectors)

    display_modes = _extract_display_modes(head, middle, tail)

    # Create display options (refactoring item 1)
    display_options = DisplayOptions(
        display_modes=display_modes,
        count=count,
        exact=exact,
        tags_only=tags_only,
        loops_only=loops_only,
        no_comments=no_comments,
    )

    # TODO [Future] move to namespace_lib
    namespaces = _parse_and_select_namespaces(
        entry, namespace_selectors, no_initial_selection
    )

    # Match selectors to actual frames/loops BEFORE calling pipe (refactoring item 3)
    matched_items = _match_selectors_to_frames_and_loops(
        entry,
        parsed_selectors,
        exact,
        namespaces,
    )

    # Merge matched items for the same frame+loop (combining tags from multiple selectors)
    matched_items = _merge_matched_items(matched_items)

    # Call pipe function (business logic)
    entry, output_dict = pipe(
        entry,
        matched_items,
        display_options,
    )

    # Handle output based on --out option and --force
    print_entry = _print_output_or_exit_error(out, output_dict, force)
    if print_entry:
        print(entry)


# TODO too long needs to be split into hogh level functions
def pipe(
    entry: Entry,
    frames_loops_and_tags: List[FramesLoopAndTags],
    display_options: DisplayOptions,
) -> Tuple[Optional[Entry], Dict[str, str]]:
    """\
    Worker function that formats already-matched frames/loops for display.

    This function focuses solely on formatting - all matching is done before calling pipe().

    Args:
        entry: Input NEF entry
        frames_loops_and_tags: List of already-matched frames/loops with their tags
        display_options: DisplayOptions containing display_modes, count, exact, tags_only, loops_only, no_comments

    Returns:
        (entry_to_stream, output_dict)
        - entry_to_stream: Entry to stream to stdout (or None)
        - output_dict: Dict mapping filename -> display output text
    """
    # Format each matched item
    display_lines = []

    for item in frames_loops_and_tags:
        lines = []

        # Determine what content will be shown
        showing_frame_tags = item.frame_tags and not display_options.loops_only
        showing_loop_data = item.loop is not None and not display_options.tags_only

        # Only add frame comments if showing actual content (not just placeholder)
        add_frame_comments = not display_options.no_comments and (
            showing_frame_tags or showing_loop_data
        )

        # 1. Frame start comment
        if add_frame_comments:
            lines.extend(_format_frame_start_comment(item.frame.name))

        # 2. Frame tags (if present and not suppressed)
        if showing_frame_tags:
            lines.extend(_format_frame_tags(item.frame, item.frame_tags))

        # 3. Loop data or placeholder (if present)
        _prcoess_loopdata_or_placeholder(lines, item, display_options)

        # 4. Frame end comment
        if add_frame_comments:
            lines.append("")
            lines.extend(_format_frame_end_comment())

        display_lines.extend(lines)

    output_text = "\n".join(display_lines)
    output_dict = {"-": output_text}

    return entry, output_dict


def _prcoess_loopdata_or_placeholder(
    lines: list[Any], item: FramesLoopAndTags, display_options: DisplayOptions
):

    showing_loop_data = item.loop is not None and not display_options.tags_only
    showing_loop_placeholder = item.loop is not None and display_options.tags_only

    if showing_loop_placeholder:
        # Placeholder for tags_only mode (no frame comments)
        lines.append(f"# loop not shown: {item.loop.category}")
    elif showing_loop_data:
        # Get display modes
        display_modes = (
            display_options.display_modes
            if display_options.display_modes
            else [DisplayMode.ALL]
        )

        # Calculate which rows to show
        indices = _calculate_display_indices(
            len(item.loop.data), display_modes, display_options.count
        )

        # Format loop structure
        loop_lines = _format_loop_data(item.loop, item.loop_tags, indices)

        # Insert ellipsis for gaps
        if not display_options.no_comments and len(indices) < len(item.loop.data):
            loop_lines = _insert_ellipsis_comments(
                loop_lines, indices, len(item.loop.data)
            )

        # Add to output
        loop_text = "\n".join(loop_lines)
        dedented = dedent(loop_text)
        lines.extend(dedented.split("\n"))


def _match_frame_tags(
    frame: Saveframe,
    selector: FrameLoopAndTagSelectors,
    exact: bool,
    selected_namespaces: set[str],
) -> Optional[FramesLoopAndTags]:
    """Match frame tags for a frame-only selector."""
    if selector.frame_tags:
        # Match specific frame tags
        frame_tag_names = [tag[0] for tag in frame.tag_iterator()]
        matched_frame_tags = _select_tags(
            frame_tag_names, selector.frame_tags, exact, selected_namespaces
        )
        if matched_frame_tags:
            # Filter matched tags by namespace
            matched_frame_tags = _filter_tags_by_namespace(
                matched_frame_tags, frame, selected_namespaces, EntryPart.FrameTag
            )
            if matched_frame_tags:
                return FramesLoopAndTags(
                    frame=frame, loop=None, frame_tags=matched_frame_tags, loop_tags=[]
                )
    else:
        # Match entire frame (all tags) - filter by namespace
        frame_tag_names = [tag[0] for tag in frame.tag_iterator()]
        if selector.frame_tags == ["*"]:
            # Filter all tags by namespace
            filtered_tags = _filter_tags_by_namespace(
                frame_tag_names, frame, selected_namespaces, EntryPart.FrameTag
            )
            if filtered_tags:
                return FramesLoopAndTags(
                    frame=frame, loop=None, frame_tags=filtered_tags, loop_tags=[]
                )
        else:
            # No tags specified
            return FramesLoopAndTags(
                frame=frame, loop=None, frame_tags=[], loop_tags=[]
            )
    return None


def _match_loop_tags(
    frame: Saveframe,
    selector: FrameLoopAndTagSelectors,
    exact: bool,
    selected_namespaces: set[str],
) -> List[FramesLoopAndTags]:
    """Match loop tags for a loop selector."""
    results = []
    loop_patterns = [selector.loop_name]
    matching_loops = select_loops_by_category(frame.loops, loop_patterns, exact=exact)

    for loop in matching_loops:
        # Match loop tags
        if selector.loop_tags:
            matched_loop_tags = _select_tags(
                loop.tags, selector.loop_tags, exact, selected_namespaces, loop.category
            )
            if matched_loop_tags:
                # Filter matched loop tags by namespace
                matched_loop_tags = _filter_tags_by_namespace(
                    matched_loop_tags, loop, selected_namespaces, EntryPart.LoopTag
                )
                if matched_loop_tags:
                    results.append(
                        FramesLoopAndTags(
                            frame=frame,
                            loop=loop,
                            frame_tags=[],
                            loop_tags=matched_loop_tags,
                        )
                    )

    return results


def _match_selectors_to_frames_and_loops(
    entry: Entry,
    selectors: List[FrameLoopAndTagSelectors],
    exact: bool,
    selected_namespaces: set[str],
) -> List[FramesLoopAndTags]:
    """
    Match selectors to actual frames and loops in the entry.

    This function separates parsing/matching from formatting logic by doing all
    selector matching upfront and returning structured match results.

    Args:
        entry: Input NEF entry
        selectors: List of parsed FrameLoopAndTags selectors
        exact: Whether to use exact matching (no wildcards)
        selected_namespaces: Set of namespaces to include

    Returns:
        List of MatchedFrameLoopAndTags objects, each containing:
        - frame: The matched Saveframe
        - loop: The matched Loop (or None for frame-only matches)
        - frame_tags: List of matched frame tag names
        - loop_tags: List of matched loop tag names
    """
    matched_items = []

    for selector in selectors:
        # Match frames based on frame_name pattern
        frame_patterns = [selector.frame_name]
        matching_frames = select_frames(
            entry, frame_patterns, selector_type=SelectionType.ANY
        )

        # Process each matching frame
        for frame in entry.frame_list:
            if frame not in matching_frames:
                continue

            # Note: We don't filter frames by namespace here because we want to allow
            # selecting tags from frames even if the frame's namespace doesn't match.
            # For example, selecting ccpn tags from nef frames.
            # Tag-level namespace filtering happens in _filter_tags_by_namespace.

            # Determine what to match based on selector type
            if selector.loop_name is None:
                # Frame-only selector (no loop)
                result = _match_frame_tags(frame, selector, exact, selected_namespaces)
                if result:
                    matched_items.append(result)
            else:
                # Loop selector - match loops within this frame
                matched_items.extend(
                    _match_loop_tags(frame, selector, exact, selected_namespaces)
                )

    return matched_items


def _filter_tags_by_namespace(
    tag_names: List[str],
    parent: Union[Saveframe, Loop],
    selected_namespaces: set[str],
    tag_type: EntryPart,
) -> List[str]:
    """
    Filter tags by namespace using get_namespace.

    Args:
        tag_names: List of tag names to filter
        parent: Parent frame or loop for namespace inheritance
        selected_namespaces: Set of selected namespaces
        tag_type: EntryPart.FrameTag or EntryPart.LoopTag

    Returns:
        List of tags that match the selected namespaces
    """
    if not selected_namespaces:
        return tag_names

    filtered = []
    for tag_name in tag_names:
        tag_namespace = get_namespace(tag_name, tag_type, parent_namespace=parent)
        if tag_namespace in selected_namespaces:
            filtered.append(tag_name)

    return filtered


def _merge_matched_items(
    matched_items: List[FramesLoopAndTags],
) -> List[FramesLoopAndTags]:
    """
    Merge matched items that refer to the same frame+loop.

    When multiple selectors target the same frame+loop with different tags,
    combine them into a single matched item with all tags.

    Args:
        matched_items: List of matched items (may have duplicates for same frame+loop)

    Returns:
        List of merged matched items (one per unique frame+loop combination)
    """
    grouped = OrderedDict()

    for item in matched_items:
        # Use (frame.name, loop.category if loop else None) as key
        key = (item.frame.name, item.loop.category if item.loop else None)

        if key not in grouped:
            grouped[key] = {
                "frame": item.frame,
                "loop": item.loop,
                "frame_tags": [],
                "loop_tags": [],
            }

        # Accumulate tags (preserving order, avoiding duplicates)
        for tag in item.frame_tags:
            if tag not in grouped[key]["frame_tags"]:
                grouped[key]["frame_tags"].append(tag)

        for tag in item.loop_tags:
            if tag not in grouped[key]["loop_tags"]:
                grouped[key]["loop_tags"].append(tag)

    # Convert back to MatchedFrameLoopAndTags objects
    merged = []
    for key, data in grouped.items():
        merged.append(
            FramesLoopAndTags(
                frame=data["frame"],
                loop=data["loop"],
                frame_tags=data["frame_tags"],
                loop_tags=data["loop_tags"],
            )
        )

    return merged


# ============================
# ATOMIC FORMATTING FUNCTIONS
# ============================


def _format_frame_start_comment(frame_name: str) -> List[str]:
    """Generate frame start comment.

    Returns:
        ["# save_{frame_name}", ""]
    """
    return [f"# save_{frame_name}", ""]


def _format_frame_end_comment() -> List[str]:
    """Generate frame end comment.

    Returns:
        ["", "# save_", ""]
    """
    return ["", "# save_", ""]


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
        selected_tags: List of tag names to include
        indices_to_include: Row indices to include

    Returns:
        List of lines containing loop structure: ["loop_", "   _tag1", ..., "   value1", ..., "stop_"]
    """
    tag_indices = [loop.tags.index(tag) for tag in selected_tags]

    # Build new loop with selected tags using pynmrstar
    new_loop = Loop.from_scratch(loop.category)

    # Add selected tags
    for tag in selected_tags:
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

    # Find data row section
    tag_end_idx = None
    stop_idx = None
    for i, line in enumerate(loop_lines):
        if (
            line.strip()
            and not line.strip().startswith("_")
            and not line.strip().startswith("loop_")
            and tag_end_idx is None
        ):
            tag_end_idx = i
        if line.strip().startswith("stop_"):
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
) -> set[str]:
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


def _apply_namespace_filtering(
    entry: Entry,
    selected_namespaces: set[str],
    loops_only: bool,
) -> Entry:
    """Apply frame-level namespace filtering if needed."""
    if not loops_only:
        # Collect all namespaces to check if filtering is needed
        namespace_dict = collect_namespaces_from_frames(entry.frame_list)
        all_namespaces = set(namespace_dict.keys())

        # Validate that selected namespaces exist (defensive check)
        invalid_namespaces = selected_namespaces - all_namespaces
        if invalid_namespaces:
            raise ValueError(
                f"Invalid namespaces: {', '.join(sorted(invalid_namespaces))}. "
                f"Available: {', '.join(sorted(all_namespaces))}"
            )

        # Only filter if selected_namespaces is a subset (meaning some were excluded)
        if selected_namespaces != all_namespaces:
            return _filter_entry_by_selected_namespaces(entry, selected_namespaces)

    return entry


# TODO this should be a utilty function
def _print_output_or_exit_error(
    out: Optional[str], output_dict: Dict[str, str], force: bool
) -> bool:
    print_entry = False
    if out is None or out == "@auto":
        # Auto-detect behavior: TTY → display to stdout (no entry), Pipe → display to stderr + entry to stdout
        if sys.stdout.isatty():
            # Terminal: display to stdout only, don't print entry
            if "-" in output_dict:
                print(output_dict["-"], end="")
        else:
            # Pipe: display to stderr, entry to stdout
            if "-" in output_dict:
                print(output_dict["-"], end="", file=sys.stderr)
                print_entry = True
    elif out in ("-", "@out"):
        # Force display-only: display to stdout, no entry output (even in pipe mode)
        if "-" in output_dict:
            print(output_dict["-"], end="")
    elif out == "@err":
        # Force pipe mode: display to stderr, entry to stdout (even in terminal)
        if "-" in output_dict:
            print(output_dict["-"], end="", file=sys.stderr)
        print_entry = True
    else:
        # Write display to file, stream entry to stdout
        if Path(out).exists() and not force:
            msg = f"file {out} already exists, run with --force to overwrite"
            exit_error(msg)
        with open(out, "w") as f:
            if out in output_dict:
                f.write(output_dict[out])
            elif "-" in output_dict:
                f.write(output_dict["-"])

        # Stream entry to stdout
        print_entry = True
    return print_entry


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

    parsed_selectors = []
    for selector in selectors:
        parsed_selectors.append(parse_frame_loop_and_tags(selector))
    return parsed_selectors


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


def _should_include_tag_by_selected_namespaces(
    tag_name: str,
    parent_frame_or_loop: Union[Saveframe, Loop, str],
    selected_namespaces: set[str],
    is_loop_tag: bool = False,
) -> bool:
    """\
    Check if a tag should be included based on selected namespaces.

    Uses proper namespace determination from namespace_lib which handles tag inheritance.

    Args:
        tag_name: Tag name to check
        parent_frame_or_loop: Parent saveframe, loop object, or namespace string
        selected_namespaces: Set of selected namespaces (pre-parsed)
        is_loop_tag: True if checking a loop tag, False for frame tag

    Returns:
        True if tag should be included, False otherwise
    """
    # Determine tag's namespace using proper namespace_lib function
    entry_part = EntryPart.LoopTag if is_loop_tag else EntryPart.FrameTag
    tag_namespace = get_namespace(tag_name, entry_part, parent_frame_or_loop)

    return tag_namespace in selected_namespaces


def _filter_entry_by_selected_namespaces(
    entry: Entry, selected_namespaces: set[str]
) -> Entry:
    """\
    Filter entry frames by selected namespaces with hierarchical logic.

    Logic: Don't filter out a frame if it contains children in the target namespace.
    - Frame is included if its namespace is in selected_namespaces OR
    - Frame has children whose namespace is in selected_namespaces

    Args:
        entry: Input NEF entry
        selected_namespaces: Set of namespaces to include (pre-parsed)

    Returns:
        New entry with only frames matching namespace criteria
    """
    # Create new entry with filtered frames
    filtered_entry = Entry.from_scratch(entry.entry_id)

    for frame in entry.frame_list:
        frame_ns = get_namespace(frame, EntryPart.Saveframe)

        # Collect all child namespaces
        child_namespaces = set()
        for tag_name, _ in frame.tag_iterator():
            tag_ns = get_namespace(tag_name, EntryPart.FrameTag, frame_ns)
            child_namespaces.add(tag_ns)

        for loop in frame.loops:
            loop_ns = get_namespace(loop, EntryPart.Loop)
            child_namespaces.add(loop_ns)

            for tag in loop.tags:
                tag_ns = get_namespace(tag, EntryPart.LoopTag, loop_ns)
                child_namespaces.add(tag_ns)

        # Include frame if:
        # - Frame namespace is in selected set, OR
        # - Any child namespace is in selected set (hierarchical logic)
        frame_matches = frame_ns in selected_namespaces
        children_match = bool(child_namespaces & selected_namespaces)

        if frame_matches or children_match:
            filtered_entry.add_saveframe(frame)

    return filtered_entry


def _select_tags(
    available_tags,
    tag_patterns,
    exact,
    selected_namespaces: set[str] = None,
    loop_category=None,
):
    """\
    Select tags matching patterns, preserving order.

    Note: Uses fnmatch directly as no cli_lib utility exists for tag selection.

    Args:
        available_tags: List of available tag names (short names without category)
        tag_patterns: List of patterns to match
        exact: Whether to use exact matching
        selected_namespaces: Set of selected namespaces for filtering (optional)
        loop_category: Loop category for constructing full tag names for namespace checking

    Returns:
        list: Ordered list of matching tags
    """

    selected = set()

    for pattern in tag_patterns:
        # Auto-wildcard unless exact
        match_pattern = pattern if exact else f"*{pattern}*"
        for tag in available_tags:
            if fnmatchcase(tag, match_pattern):
                selected.add(tag)

    # Filter by namespace if specified
    if selected_namespaces is not None and loop_category:
        # Get loop namespace for tag inheritance
        loop_ns = get_namespace(loop_category, EntryPart.Loop)

        filtered = set()
        for tag in selected:
            # Use proper namespace determination for loop tags
            if _should_include_tag_by_selected_namespaces(
                tag, loop_ns, selected_namespaces, is_loop_tag=True
            ):
                filtered.add(tag)
        selected = filtered

    # Preserve file order
    return [tag for tag in available_tags if tag in selected]
