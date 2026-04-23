from pathlib import Path
from typing import Annotated, List, Optional, Set, Tuple
from warnings import warn

import typer
from pynmrstar import Entry, Saveframe
from tabulate import tabulate

from nef_pipelines.lib.namespace_lib import (
    REGISTERED_NAMESPACES,
    collect_namespaces_from_frames,
    filter_namespaces,
    get_namespace,
    if_separator_conflicts_get_message,
)
from nef_pipelines.lib.nef_lib import (
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.structures import EntryPart
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.namespace import namespace_app

# TODO [future] add output via | less --header -R --header=2 and the opportunity to remove colouring --no-colour?
# TODO [future] add line numbers
# TODO [future] more colour, textual
# TODO [future] select by object type [tags, loops, etc] use selectors
# TODO [future] output option
# TODO [future] colour namespace parts in frame names etc
# TODO [future] bold namespaces


# raised if , found in a namespace and use_separator_escapes not specified
class NamespaceSeparatorConflict(Exception):
    pass


# Display names for EntryPart enum values in verbose output.
# @ is used as a placeholder for a leading space (tabulate would strip real spaces);
# _replace_indent_markers_in_level_column() swaps them back after table generation.
ENTRY_PART_DISPLAY = {
    EntryPart.Saveframe: "frame",
    EntryPart.FrameTag: "@frame-tag",
    EntryPart.Loop: "@loop",
    EntryPart.LoopTag: "@@column-tag",
}


@namespace_app.command(name="list")
def list_namespaces(
    namespace_selectors: Annotated[
        Optional[List[str]],
        typer.Argument(
            metavar="<NAMESPACES>",
            help="""\
                Optional namespace patterns for filtering (supports wildcards).
                Prefix with + to include (default), - or ! to exclude.
                Escape: \\+namespace for literal +namespace, \\-namespace for literal -namespace  and \\, to
                escape ,s. \\\\ escapes to a single \\ (requires --use-escapes).
                Can be comma-separated (e.g., nef,custom) or repeated arguments.
                Note: Use -- before selectors starting with - or use ! instead to avoid argument parsing problems
                      to avoid option parsing (e.g., nef namespace list -- -nef or nef namespaces list !nef).
                """,
            show_default=False,
        ),
    ] = None,
    input_path: Annotated[
        Path,
        typer.Option(
            "-i",
            "--in",
            metavar="NEF-FILE",
            help="where to read NEF data from either a file or stdin '-'",
        ),
    ] = Path("-"),
    frame_selectors: Annotated[
        List[str],
        typer.Option(
            "-f",
            "--frames",
            metavar="<FRAME-SELECTOR>",
            help="""\
                Limit to specific frames by name or category (supports wildcards).
                Note: the option -s/--selector-type allows you to choose which selection type to use.
                [default: all frames]
                """,
            show_default=False,
        ),
    ] = None,
    selector_type: Annotated[
        SelectionType,
        typer.Option(
            "-s",
            "--selector",
            help=f"""\
                control how to select frames, can be one of: {SELECTORS_LOWER}.
                Any will match on names first and then if there is no match attempt to match on category
                """,
        ),
    ] = SelectionType.ANY,
    verbose: Annotated[
        bool,
        typer.Option(
            "-v",
            "--verbose",
            help="show detailed table format with frame, loop, level, program, and use columns",
        ),
    ] = False,
    no_initial_selection: Annotated[
        bool,
        typer.Option(
            "--no-initial-selection",
            help="start with empty namespace selection instead of all",
        ),
    ] = False,
    # TODO [future] there should be a --out option...
    use_separator_escapes: Annotated[
        bool,
        typer.Option(
            "--use-escapes",
            help="allow escape sequences in names (,, for comma). Required if separator found in names",
        ),
    ] = False,
):
    """- list namespaces in selected frames [use --verbose for details]"""

    namespace_selectors: List[str] = namespace_selectors or []
    frame_selectors_list: List[str] = frame_selectors or []

    input_path, namespace_selectors = _parse_file_from_args(
        input_path, namespace_selectors
    )

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    frames = select_frames(entry, frame_selectors_list, selector_type)

    namespaces_to_show: Set[str] = _select_namespaces_or_exit_error_if_missing_escapes(
        frames, namespace_selectors, use_separator_escapes, no_initial_selection
    )

    _, result = pipe(entry, frames, namespaces_to_show, verbose)

    print(result)


def pipe(
    entry: Entry,
    frames: List[Saveframe],
    namespaces_to_show: Set[str],
    verbose: bool,
) -> Tuple[Entry, str]:
    """
    List namespaces from selected frames.

    Args:
        entry: Input NEF entry (passed through unchanged)
        frames: Saveframes to collect namespace data from
        namespaces_to_show: Pre-filtered set of namespaces to display
        verbose: If True, return detailed table; if False, return simple list

    Returns:
        (entry, text) — entry is passed through unchanged; text is the namespace list or table
    """

    namespace_data = collect_namespaces_from_frames(frames)

    if verbose:
        text = _generate_verbose_table(frames, namespace_data, namespaces_to_show)
    else:
        text = _generate_basic_list(namespaces_to_show)

    return entry, text


def _raise_if_separator_conflicts_with_namespace(
    all_namespaces: Set[str],
    namespace_selectors: List[str],
    use_separator_escapes: bool,
):
    # Check for separator conflicts in namespace names
    if namespace_selectors:
        conflict_info = if_separator_conflicts_get_message(
            [*all_namespaces], [",", "+", "-", "*"], use_separator_escapes
        )
        if conflict_info:
            conflicting_names, found_separators, escape_sequences = conflict_info

            # Format separator list
            sep_list = ", ".join(f"'{s}'" for s in found_separators)

            # Format conflicting names
            names_list = ", ".join(f"'{n}'" for n in conflicting_names)
            remaining = len(all_namespaces) - len(conflicting_names)
            if remaining > 0:
                names_list += f" ... and {remaining} more"

            # Format escape sequences
            escape_list = ", ".join(
                f"'{esc}' for '{sep}'" for sep, esc in escape_sequences
            )

            msg = f"""\
                The separator character(s) {sep_list} found in names: {names_list}

                Use --use-escapes to enable escape sequences: {escape_list}
                """

            raise NamespaceSeparatorConflict(msg)


def _parse_file_from_args(
    input_path: Path, namespace_selectors: List[str]
) -> Tuple[Path, List[str]]:
    """If the first positional arg is a file, treat it as the input file."""
    if namespace_selectors and Path(namespace_selectors[0]).is_file():
        if input_path != STDIN:
            exit_error(
                f"two inputs specified: --in {input_path} and {namespace_selectors[0]}, please choose only one"
            )
        input_path = Path(namespace_selectors[0])
        namespace_selectors = namespace_selectors[1:]
    return input_path, namespace_selectors


def _select_namespaces_or_exit_error_if_missing_escapes(
    frames: List[Saveframe],
    namespace_selectors: List[str],
    use_separator_escapes: bool,
    no_initial_selection: bool,
) -> Set[str]:
    """Apply selector filtering to a set of namespace names, with conflict checking and warnings."""

    all_namespaces = set(collect_namespaces_from_frames(frames).keys())

    try:
        _raise_if_separator_conflicts_with_namespace(
            all_namespaces, namespace_selectors, use_separator_escapes
        )
    except NamespaceSeparatorConflict as e:
        exit_error(
            f"a separator namespace conflict [{e}] was detected:  selectors{', '.join(namespace_selectors)}"
        )
    namespaces_to_show = filter_namespaces(
        all_namespaces, namespace_selectors, use_separator_escapes, no_initial_selection
    )
    if len(namespaces_to_show) == 0:
        warn(f"no namespaces selected by {namespace_selectors}")
    return namespaces_to_show


def _generate_basic_list(namespaces: set) -> str:
    """
    Generate basic namespace list (ordered).

    Args:
        namespaces: Set of namespace strings

    Returns:
        String with one namespace per line, sorted
    """

    result = ""
    if namespaces:
        result = sorted(namespaces)

    result = "\n".join(result)
    return result


def _replace_indent_markers_in_level_column(table: str) -> str:
    """
    Replace @ indent markers in the Level column with spaces.

    tabulate strips leading spaces from cell values, so ENTRY_PART_DISPLAY uses @ as a
    placeholder for a leading space. This function locates the Level column from the
    header/separator lines and swaps @ back to spaces only within that column.
    """
    lines = table.splitlines()
    if len(lines) < 2:
        return table

    header_line = lines[0]
    separator_line = lines[1]

    level_pos = header_line.find("Level")
    if level_pos == -1:
        return table

    # Find the dash group in the separator that contains level_pos
    col_start = col_end = None
    i = 0
    while i < len(separator_line):
        if separator_line[i] == "-":
            start = i
            while i < len(separator_line) and separator_line[i] == "-":
                i += 1
            if start <= level_pos < i:
                col_start, col_end = start, i
                break
        else:
            i += 1

    if col_start is None:
        return table

    result_lines = lines[:2]
    for line in lines[2:]:
        if len(line) > col_start:
            segment = line[col_start:col_end]
            segment = segment.replace("@@", "  ").replace("@", " ")
            line = line[:col_start] + segment + line[col_end:]
        result_lines.append(line)

    return "\n".join(result_lines)


def _build_row(
    namespace: str,
    entry_part: EntryPart,
    frame_name: str,
    frame_category: str,
    namespaces_to_show: Set[str],
    loop_category: str = None,
    tag: str = None,
) -> List:
    """Return a table row for one entry-part, or an empty list if filtered out."""
    if namespace not in namespaces_to_show:
        return []

    program, use = REGISTERED_NAMESPACES.get(namespace, ("?", "?"))
    level_type = ENTRY_PART_DISPLAY[entry_part]

    display_frame_category = frame_category
    if display_frame_category.startswith(f"{namespace}_"):
        display_frame_category = display_frame_category[len(namespace) + 1 :]

    loop_value = ""
    if entry_part in (EntryPart.Loop, EntryPart.LoopTag) and loop_category:
        loop_cat = loop_category.lstrip("_")
        if loop_cat.startswith(f"{namespace}_"):
            loop_cat = loop_cat[len(namespace) + 1 :]
        loop_value = loop_cat

    tag_value = ""
    if entry_part in (EntryPart.FrameTag, EntryPart.LoopTag) and tag:
        tag_display = tag.lstrip("_")
        if "." in tag_display:
            tag_display = tag_display.split(".", 1)[1]
        if namespace and tag_display.startswith(f"{namespace}_"):
            tag_display = tag_display[len(namespace) + 1 :]
        tag_value = tag_display

    return [
        namespace,
        level_type,
        frame_name,
        display_frame_category,
        loop_value,
        tag_value,
        program,
        use,
    ]


def _collect_rows(
    frames: List[Saveframe], namespaces_to_show: Set[str]
) -> Tuple[List[List], bool]:
    """Scan frames in file order and return (rows, has_loops)."""
    rows = []
    has_loops = False

    for frame in frames:
        frame_namespace = get_namespace(frame, EntryPart.Saveframe)

        row = _build_row(
            frame_namespace,
            EntryPart.Saveframe,
            frame.name,
            frame.category,
            namespaces_to_show,
        )
        if row:
            rows.append(row)

        for tag_name, _tag_value in frame.tag_iterator():
            tag_namespace = get_namespace(tag_name, EntryPart.FrameTag, frame_namespace)
            row = _build_row(
                tag_namespace,
                EntryPart.FrameTag,
                frame.name,
                frame.category,
                namespaces_to_show,
                tag=tag_name,
            )
            if row:
                rows.append(row)

        for loop in frame.loops:
            loop_namespace = get_namespace(loop, EntryPart.Loop, frame_namespace)
            row = _build_row(
                loop_namespace,
                EntryPart.Loop,
                frame.name,
                frame.category,
                namespaces_to_show,
                loop.category,
            )
            if row:
                has_loops = True
                rows.append(row)

            for tag_name in loop.tags:
                tag_namespace = get_namespace(
                    tag_name, EntryPart.LoopTag, loop_namespace
                )
                row = _build_row(
                    tag_namespace,
                    EntryPart.LoopTag,
                    frame.name,
                    frame.category,
                    namespaces_to_show,
                    loop.category,
                    tag_name,
                )
                if row:
                    has_loops = True
                    rows.append(row)

    return rows, has_loops


def _generate_verbose_table(
    frames: List[Saveframe], namespace_data: dict, namespaces_to_show: Set[str]
) -> str:
    """Generate verbose table showing namespace details in file order."""

    rows, has_loops = _collect_rows(frames, namespaces_to_show)

    result = ""
    if rows:
        if has_loops:
            headers = [
                "Namespace",
                "Level",
                "Frame",
                "Category",
                "Loop",
                "Tag",
                "Program",
                "Use",
            ]
            result = tabulate(rows, headers=headers, tablefmt="simple")
        else:
            rows_without_loop = [row[:4] + row[6:] for row in rows]
            headers = ["Namespace", "Level", "Frame", "Category", "Program", "Use"]
            result = tabulate(rows_without_loop, headers=headers, tablefmt="simple")

        result = _replace_indent_markers_in_level_column(result)
        result = _colorize_namespace_column(result, namespace_data)
        result = _stripe_alternate_rows(result)

    return result


def _colorize_namespace_column(table: str, namespace_data: dict) -> str:
    """
    Apply distinct foreground colours to each namespace in the Namespace column.

    Assigns a colour to each namespace based on file order and applies it to the
    namespace text in the first column of each data row.
    """
    import sys

    if not sys.stdout.isatty():
        return table

    # Colour palette - bright, distinct colours
    COLOURS = [
        "\033[38;5;33m",  # bright blue
        "\033[38;5;35m",  # bright green
        "\033[38;5;214m",  # orange
        "\033[38;5;13m",  # bright magenta
        "\033[38;5;51m",  # bright cyan
        "\033[38;5;11m",  # bright yellow
        "\033[38;5;9m",  # bright red
        "\033[38;5;213m",  # pink
    ]
    _RESET_FG = "\033[39m"  # Reset foreground only, preserve background

    # Assign colours to namespaces in file order
    namespace_colors = {}
    for idx, namespace in enumerate(namespace_data.keys()):
        namespace_colors[namespace] = COLOURS[idx % len(COLOURS)]

    lines = table.splitlines()
    if len(lines) < 3:
        return table

    header_line = lines[0]
    separator_line = lines[1]

    # Find where the Namespace column ends (first separator boundary)
    sep_end = separator_line.find(" ")
    if sep_end == -1:
        sep_end = len(separator_line)

    result_lines = [header_line, separator_line]
    for line in lines[2:]:
        # Extract the namespace value from the first column
        namespace_value = line[:sep_end].strip()
        if namespace_value in namespace_colors:
            color = namespace_colors[namespace_value]
            # Replace the namespace text with coloured version
            colored_namespace = color + namespace_value + _RESET_FG
            # Pad to maintain alignment
            padding = " " * (sep_end - len(namespace_value))
            line = colored_namespace + padding + line[sep_end:]
        result_lines.append(line)

    return "\n".join(result_lines)


def _stripe_alternate_rows(table: str) -> str:
    """
    Apply alternating very-light-grey ANSI background to every other data row.

    Header and separator lines (first two lines) are left unstyled.
    Only applied when stdout is a TTY so piped/redirected output stays clean.
    """
    import sys

    if not sys.stdout.isatty():
        return table

    _GREY_BG = "\033[48;2;230;230;230m"
    _RESET = "\033[0m"

    lines = table.splitlines()
    result_lines = lines[:2]  # header + separator untouched
    for idx, line in enumerate(lines[2:]):
        if idx % 2 == 1:
            line = _GREY_BG + line + _RESET
        result_lines.append(line)
    return "\n".join(result_lines)
