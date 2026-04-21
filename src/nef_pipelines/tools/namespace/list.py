from __future__ import annotations

from pathlib import Path
from typing import Annotated, List

import typer
from tabulate import tabulate

from nef_pipelines.lib.namespace_lib import (
    REGISTERED_NAMESPACES,
    collect_namespaces_from_frames,
    filter_namespaces,
    if_separator_conflicts_get_message,
)
from nef_pipelines.lib.nef_lib import (
    SELECTORS_LOWER,
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.util import exit_error
from nef_pipelines.tools.namespace import namespace_app

#TODO [future] add output via | less --header -R --header=2 and the opportunity to remove colouring --no-colour?
#TODO [future] add line numbers
#TODO [future] more colour, textual
#TODO [future] select by object type [tags, loops, etc] use selectors
#TODO [future] output option
#TODO [future] colour namespace parts in frame names etc
#TODO [future] bold namespaces


# raised if , found in a namespace and use_separator_escapes not specified
class NamepaceSeparatorConflict(Exception):
    pass


@namespace_app.command()
def list(
    namespace_selectors: Annotated[
        List[str],
        typer.Argument(
            metavar="<NAMESPACE-SELECTOR>",
            help="""\
                Optional namespace patterns for filtering (supports wildcards).
                Prefix with + to include (default), - to exclude.
                Escape: ++namespace for literal +namespace, --namespace for literal -namespace.
                Can be comma-separated (e.g., nef,custom) or repeated arguments.
                """,
            show_default=False,
        ),
    ] = None,
    input: Annotated[
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
    invert: Annotated[
        bool,
        typer.Option(
            "--invert",
            help="invert namespace selection (exclude matched, include unmatched)",
        ),
    ] = False,
    use_separator_escapes: Annotated[
        bool,
        typer.Option(
            "--use-separator-escapes",
            help="allow escape sequences in names (,, for comma). Required if separator found in names",
        ),
    ] = False,
):
    """- list namespaces in selected frames [use --verbose for details]"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frames = select_frames(entry, frame_selectors, selector_type)

    try:
        result = pipe(
            frames,
            namespace_selectors,
            verbose,
            invert,
            use_separator_escapes,
        )
    except NamepaceSeparatorConflict:
        exit_error("the separator conflict anmespace conflict")

    print(result)


def pipe(
    frames: List,
    namespace_selectors: List[str],
    verbose: bool,
    invert: bool,
    use_separator_escapes: bool,
) -> str:
    """
    List namespaces from selected frames.

    Args:
        frames: List of NEF saveframes to process
        namespace_selectors: Optional namespace patterns with +/- prefixes
        verbose: If True, return detailed table; if False, return simple list
        invert: If True, invert namespace selection logic
        use_separator_escapes: If True, process escape sequences

    Returns:
        String containing namespace list or table
    """

    # Collect all namespaces from frames
    namespace_data = collect_namespaces_from_frames(frames)
    all_namespaces = set(namespace_data.keys())

    _raise_if_separator_conflicts_with_namespace(
        all_namespaces, namespace_selectors, use_separator_escapes
    )

    namespaces_to_show = filter_namespaces(
        all_namespaces, namespace_selectors, use_separator_escapes, invert
    )

    # Generate output
    if verbose:
        return _generate_verbose_table(namespace_data, namespaces_to_show)
    else:
        return _generate_basic_list(namespaces_to_show)


def _raise_if_separator_conflicts_with_namespace(
    all_namespaces: set[str],
    namespace_selectors: list[str],
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

                Use --use-separator-escapes to enable escape sequences: {escape_list}
                """

            raise NamepaceSeparatorConflict(msg)


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


def _generate_verbose_table(namespace_data: dict, namespaces_to_show: set) -> str:
    """
    Generate verbose table showing namespace details.

    Args:
        namespace_data: Dict mapping namespace → list of (frame_name, frame_category, loop_category, level_type) tuples
        namespaces_to_show: Set of namespaces to include in table

    Returns:
        Formatted table string
    """

    # Build table rows and track if we have any loops
    rows = []
    has_loops = False
    for namespace in sorted(namespaces_to_show):
        if namespace not in namespace_data:
            continue

        # Get program and use info from registered namespaces
        if namespace in REGISTERED_NAMESPACES:
            program, use = REGISTERED_NAMESPACES[namespace]
        else:
            program, use = "?", "?"

        # Add rows for each occurrence
        for frame_name, frame_category, loop_category, level_type in namespace_data[
            namespace
        ]:
            # Track if we have any loop entries
            if level_type == "loop":
                has_loops = True

            # Remove namespace prefix from frame category
            display_frame_category = frame_category
            if display_frame_category.startswith(f"{namespace}_"):
                display_frame_category = display_frame_category[len(namespace) + 1 :]

            # For loops, extract loop category (strip leading _ and namespace prefix)
            loop_value = ""
            if level_type == "loop" and loop_category:
                loop_cat = loop_category.lstrip("_")
                if loop_cat.startswith(f"{namespace}_"):
                    loop_cat = loop_cat[len(namespace) + 1 :]
                loop_value = loop_cat

            rows.append(
                [
                    namespace,
                    level_type,
                    display_frame_category,
                    frame_name,
                    loop_value,
                    program,
                    use,
                ]
            )

    # Generate table
    result = ""
    if rows:
        # Elide Loop column if there are no loops
        if has_loops:
            headers = [
                "Namespace",
                "Level",
                "Category",
                "Frame",
                "Loop",
                "Program",
                "Use",
            ]
            result = tabulate(rows, headers=headers, tablefmt="simple")
        else:
            # Remove Loop column (index 4)
            rows_without_loop = [row[:4] + row[5:] for row in rows]
            headers = ["Namespace", "Level", "Category", "Frame", "Program", "Use"]
            result = tabulate(rows_without_loop, headers=headers, tablefmt="simple")

    return result
