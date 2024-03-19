from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.transcoders.nmrpipe.importers.sequence import pipe as nmrpipe_pipe
from nef_pipelines.transcoders.talos import import_app

app = typer.Typer()


@import_app.command()
def sequence(
    chain_code: str = typer.Option(
        "A",
        "--chain",
        help="chain codes for the new chain",
        metavar="<CHAIN-CODE>",
    ),
    no_chain_start: bool = typer.Option(
        False,
        "--no-chain-start/",
        help="don't include a start of chain link type for the first residue",
    ),
    no_chain_end: bool = typer.Option(
        False,
        "--no-chain-end/",
        help="don't include an end of chain link type for the last residue",
    ),
    entry_name: str = typer.Option("talos", help="a name for the entry"),
    input: Path = typer.Option(
        None,
        "-i",
        "--input",
        metavar="|INPUT|",
        help="file to read NEF data from [- is stdin; defaults is stdin]",
    ),
    file_name: Path = typer.Argument(
        ..., help="input files of type <TALOS-FILE>.pred", metavar="<PRED-FILE>"
    ),
):
    """-  convert sequence from a talos pred file to NEF"""

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name=entry_name)

    lines = read_file_or_exit(file_name)

    entry = pipe(entry, lines, chain_code, no_chain_start, no_chain_end, file_name)

    print(entry)


def pipe(
    entry: Entry,
    lines: List[str],
    chain_code: str,
    no_chain_start: bool,
    no_chain_end: bool,
    file_name: Path,
):

    return nmrpipe_pipe(
        entry, lines, chain_code, no_chain_start, no_chain_end, 1, file_name
    )
