#TODO add support for DATA FIRST_RESID

# noinspection PyUnusedLocal
from argparse import Namespace
from pathlib import Path
from typing import List, Iterable

import typer
from icecream import ic

from lib.sequence_lib import chain_code_iter, sequence_3let_to_sequence_residues, sequence_to_nef_frame, offset_chain_residues
from lib.structures import SequenceResidue
from lib.typer_utils import get_args
from lib.util import exit_error, process_stream_and_add_frames
from transcoders.nmrpipe.nmrpipe_lib import read_db_file_records, gdb_to_3let_sequence
from transcoders.nmrpipe import import_app
from lib.util import cached_file_stream

app = typer.Typer()

# noinspection PyUnusedLocal
@import_app.command()
def sequence(
    chain_codes: str = typer.Option('A', '--chains', help='chain codes as a list of names spearated by dots',
                                   metavar='<CHAIN-CODES>'),
    no_chain_start: bool = typer.Option(False, '--no-chain-start/',
                                        help="don't include a start of chain link type for the first residue"),
    no_chain_end: bool = typer.Option(False, '--no-chain-end/',
                                      help="don't include an end of chain link type for the last residue"),
    entry_name: str = typer.Option('nmrpipe', help='a name for the entry'),
    pipe: Path = typer.Option(None, metavar='|PIPE|',
                              help='pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]'),
    start: int = typer.Option(1, metavar='offset', help='residue number to start the sequence at'),
    file_names: List[Path] = typer.Argument(..., help='input files of type nmrview.seq', metavar='<SEQ-FILE>')
):
    """convert nmrview sequence file <nmrview>.seq files to NEF"""
    try:
        args = get_args()

        process_sequence(args)
    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)


def process_sequence(args: Namespace):
    nmrpipe_frames = []

    for file_name, chain_code in zip(args.file_names, chain_code_iter(args.chain_codes)):
        # cached_file_stream
        with cached_file_stream(file_name) as lines:

            nmrpipe_sequence = read_sequence(lines, chain_code=chain_code, sequence_file_name=file_name, start=args.start)

            frame = sequence_to_nef_frame(nmrpipe_sequence, args.entry_name)

            nmrpipe_frames.append(frame)

    entry = process_stream_and_add_frames(nmrpipe_frames, args)

    print(entry)


def read_sequence(sequence_lines: Iterable[str], chain_code: str = 'A', sequence_file_name: str = 'unknown',
                  start: int = 1) -> List[SequenceResidue]:

    gdb_file = read_db_file_records(sequence_lines, sequence_file_name)

    sequence_3let = gdb_to_3let_sequence(gdb_file)

    sequence_residues =  sequence_3let_to_sequence_residues(sequence_3let, chain_code=chain_code)

    sequence_residues = offset_chain_residues(sequence_residues, {chain_code: start-1})

    return sequence_residues


if __name__ == '__main__':

    typer.run(sequence)