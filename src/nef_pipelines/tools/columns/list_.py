from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer
from pynmrstar import Entry
from tabulate import tabulate

from nef_pipelines.lib.cli_lib import print_output_or_exit_error
from nef_pipelines.lib.nef_lib import read_entry_from_file_or_stdin_or_exit_error
from nef_pipelines.lib.structures import FrameLoopsAndTags
from nef_pipelines.lib.util import (
    STDIN,
    is_stdout_tty,
    strings_to_table_terminal_sensitive,
)
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _parse_frame_loop_and_tag_selectors_or_exit_error,
)
from nef_pipelines.tools.columns.columns_lib import _filter_tags


@columns_app.command("list")
def list_(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    out: Optional[str] = typer.Option(
        "@auto",
        "--out",
        help="""\
            output destinations:
            - `@auto` [default] - If stdout is a terminal, write display to stdout (entry suppressed).
              If stdout is a pipe/stream, write entry to stdout and display to stderr.

            - `-`, `@out` - Write display to stdout, don't output the entry.

            - `@err` - Write display to stderr, write entry to stdout.

            - `<filename>` - Write display to file, write entry to stdout.

            Use backslash to escape @ (e.g., \\@file).
            """,
    ),
    selectors: List[str] = typer.Argument(
        ...,
        help="frame.loop or frame.loop:tag selectors",
    ),
    force: bool = typer.Option(False, "--force", help="overwrite existing files"),
) -> None:
    """- list column names in loops; selectors: frame.loop or frame.loop:pattern (wildcards and indices supported)"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    selections = _parse_frame_loop_and_tag_selectors_or_exit_error(entry, selectors)
    entry, output_dict = pipe(entry, selections)
    print_output_or_exit_error(entry, out, output_dict, force)


def pipe(
    entry: Entry, selections: List[FrameLoopsAndTags]
) -> Tuple[Entry, Dict[str, str]]:
    """Generate column list display output.

    Returns:
        (entry, output_dict) where output_dict["-"] contains the formatted display text
    """
    output_lines = []
    is_tty = is_stdout_tty()

    for item in selections:
        for loop in item.loops:
            loop_tags = item.loop_tags.get(loop.category, [])
            tags = _filter_tags(loop.tags, loop_tags, loop.category)
            loop_id = f"{item.frame.name}.{loop.category.lstrip('_')}"
            if is_tty:
                prefix = f"{loop_id}: "
                used = len(prefix)
                table = strings_to_table_terminal_sensitive(tags, used_width=used)
                output_lines.append(prefix + tabulate(table, tablefmt="plain"))
            else:
                output_lines.append(f"{loop_id}: {', '.join(tags)}")

    return entry, {"-": "\n".join(output_lines)}
