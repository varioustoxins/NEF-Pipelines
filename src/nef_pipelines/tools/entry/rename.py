import sys
from pathlib import Path

import typer

from nef_pipelines.lib.nef_lib import read_entry_from_stdin_or_exit
from nef_pipelines.tools.entry import entry_app


# noinspection PyUnusedLocal
@entry_app.command()
def rename(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    name: str = typer.Argument(
        None,
        help="the new name for the entry",
    ),
):
    """- rename the current entry"""

    entry = read_entry_from_stdin_or_exit()

    if name is not None:
        entry.entry_id = name

    if not sys.stdout.isatty():
        print(entry)
