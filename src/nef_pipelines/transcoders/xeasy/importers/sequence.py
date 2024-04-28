from pathlib import Path
from typing import List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import read_or_create_entry_exit_error_on_bad_file
from nef_pipelines.lib.sequence_lib import sequence_to_nef_frame
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import STDIN, parse_comma_separated_options
from nef_pipelines.transcoders.xeasy import import_app
from nef_pipelines.transcoders.xeasy.xeasy_lib import parse_sequence

app = typer.Typer()

NO_CHAIN_START_HELP = """don't include the start chain link type on a chain for the first residue [linkage will be
                            middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call
                            this option multiple times to set chain starts for multiple chains"""
NO_CHAIN_END_HELP = """don't include the end chain link type on a chain for the last residue [linkage will be
                        middle] for the named chains. Either use a comma joined list of chains [e.g. A,B] or call this
                        option multiple times to set chain ends for multiple chains"""


@import_app.command()
def sequence(
    entry_name: str = typer.Option("xeasy", help="a name for the entry if required"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    no_chain_starts: List[str] = typer.Option(
        [], "--no-chain-start", help=NO_CHAIN_START_HELP
    ),
    no_chain_ends: List[str] = typer.Option(
        [], "--no-chain-end", help=NO_CHAIN_END_HELP
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="the file to read", metavar="<XEASY-SEQUENCE-FILE.seq>"
    ),
):
    """- convert xeasy sequences to nef"""

    no_chain_starts = parse_comma_separated_options(no_chain_starts)
    if not no_chain_starts:
        no_chain_starts = [False]

    no_chain_ends = parse_comma_separated_options(no_chain_ends)
    if no_chain_ends:
        no_chain_ends = [False]

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name)

    entry = pipe(entry, no_chain_starts, no_chain_ends, file_names)

    print(entry)


def pipe(
    entry: Entry,
    no_chain_starts: List[bool],
    no_chain_ends: List[bool],
    file_names: List[Path],
):

    xeasy_sequences = set()

    for file_name in file_names:

        xeasy_sequences.update(_read_sequence(file_name))

    xeasy_sequences = sorted(xeasy_sequences)

    xeasy_frame = sequence_to_nef_frame(xeasy_sequences, no_chain_starts, no_chain_ends)

    entry.add_saveframe(xeasy_frame)

    return entry


def _read_sequence(file_name: Path) -> List[SequenceResidue]:

    with file_name.open() as fh:
        lines = fh.readlines()

    return parse_sequence(lines)
