import csv
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry

from nef_pipelines.lib.cli_lib import print_output_or_exit_error
from nef_pipelines.lib.nef_lib import (
    loop_row_dict_iter,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.structures import FrameLoopsAndTags
from nef_pipelines.lib.util import STDIN, exit_error
from nef_pipelines.tools.columns import columns_app
from nef_pipelines.tools.columns.columns_cli_lib import (
    _parse_frame_loop_and_tag_selectors_or_exit_error,
)
from nef_pipelines.tools.columns.columns_lib import _filter_tags


@columns_app.command()
def extract(
    input: Path = typer.Option(
        STDIN,
        "--in",
        metavar="|PIPE|",
        help="read NEF data from a file or stdin",
    ),
    output: str = typer.Option(
        ...,
        "--out",
        "-o",
        help="file to write extracted column values to",
    ),
    force: bool = typer.Option(False, "--force", help="overwrite existing files"),
    # TODO [future] could add an iterleaved target option so we can output to several files!
    selectors: List[str] = typer.Argument(
        ...,
        help="frame.loop:col selectors for columns to extract",
    ),
) -> None:
    """- extract selected column values from a loop to a file; selectors: frame.loop:col_1,col_2..."""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)
    selections = _parse_frame_loop_and_tag_selectors_or_exit_error(entry, selectors)
    entry, output_dict = pipe(entry, selections)
    print_output_or_exit_error(entry, output, output_dict, force)


def pipe(
    entry: Entry,
    selections: List[FrameLoopsAndTags],
) -> Tuple[Entry, Dict[str, str]]:
    """Extract column data and format as CSV or simple text.

    Returns:
        (entry, output_dict) where output_dict["-"] contains the formatted data
    """
    col_data: Dict[str, List[str]] = {}

    for item in selections:
        for loop in item.loops:
            loop_tags = item.loop_tags.get(loop.category, [])
            tags = _filter_tags(loop.tags, loop_tags, loop.category)
            rows = list(loop_row_dict_iter(loop, convert=False))
            for tag in tags:
                col_data[tag] = [str(row[tag]) for row in rows]

    if not col_data:
        exit_error("no columns matched the given selectors")

    formatted_data = _format_columns(col_data)
    return entry, {"-": formatted_data}


def _format_columns(
    col_data: Dict[str, List[str]],
) -> str:
    """Format column data as CSV or simple text."""
    output = StringIO()

    writer = csv.writer(output)
    writer.writerow(list(col_data.keys()))
    for values in zip(*col_data.values()):
        writer.writerow(list(values))

    return output.getvalue()
