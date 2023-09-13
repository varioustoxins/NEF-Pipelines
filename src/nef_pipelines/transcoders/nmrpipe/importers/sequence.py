# TODO add support for DATA FIRST_RESID
# noinspection PyUnusedLocal
from pathlib import Path
from typing import Iterable, List

import typer
from pynmrstar import Entry

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_file_or_exit,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    get_chain_starts,
    offset_chain_residues,
    sequence_to_nef_frame,
)
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.util import exit_error
from nef_pipelines.transcoders.nmrpipe import import_app
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import (
    gdb_to_sequence,
    read_db_file_records,
)

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command()
def sequence(
    chain_code: str = typer.Option(
        "A",
        "--chains",
        help="the chain code to use",
        metavar="<CHAIN-CODE>",
    ),
    no_chain_start: bool = typer.Option(
        False,
        "--no-chain-start",
        help="don't include a start of chain link type for the first residue",
    ),
    no_chain_end: bool = typer.Option(
        False,
        "--no-chain-end",
        help="don't include an end of chain link type for the last residue",
    ),
    entry_name: str = typer.Option(
        "nmrpipe", help="a name for the entry if its created from new"
    ),
    input: Path = typer.Option(
        None,
        "-i",
        "--input",
        metavar="|INPUT|",
        help="input to read NEF data from",
    ),
    start: int = typer.Option(
        None, metavar="<START>", help="residue number to start the sequence at"
    ),
    file_name: Path = typer.Argument(
        ..., help="input files of type <NMRPIPE>.tab", metavar="<NMRPIPE-FILE>"
    ),
):
    """read a sequence from an NMRPipe file <NMPRPIPE-FILE>.tab into NEF a file"""

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name=entry_name)

    lines = read_file_or_exit(file_name)

    entry = pipe(
        entry, lines, chain_code, no_chain_start, no_chain_end, start, file_name
    )

    print(entry)


def pipe(
    entry: Entry,
    lines: List[str],
    chain_code: str,
    no_chain_start: bool,
    no_chain_end: bool,
    start: int,
    file_name: str,
):
    try:

        nmrpipe_sequence = read_sequence(
            lines,
            chain_code=chain_code,
            sequence_file_name=file_name,
            start=start,
        )

        no_chain_start_list = (
            [
                chain_code,
            ]
            if no_chain_start is True
            else []
        )
        no_chain_end_list = (
            [
                chain_code,
            ]
            if no_chain_end is True
            else []
        )

        frame = sequence_to_nef_frame(
            nmrpipe_sequence,
            no_chain_start=no_chain_start_list,
            no_chain_end=no_chain_end_list,
        )

        entry = add_frames_to_entry(
            entry,
            [
                frame,
            ],
        )

    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)

    return entry


def read_sequence(
    sequence_lines: Iterable[str],
    chain_code: str = "A",
    sequence_file_name: str = "unknown",
    start: int = None,
) -> List[SequenceResidue]:

    gdb_file = read_db_file_records(sequence_lines, sequence_file_name)

    sequence = gdb_to_sequence(gdb_file, chain_code)

    if sequence and start is not None:
        nmrpipe_chain_start = get_chain_starts(sequence)[chain_code]

        offset = start - nmrpipe_chain_start
        sequence = offset_chain_residues(sequence, {chain_code: offset})

    return sequence


if __name__ == "__main__":

    typer.run(sequence)
