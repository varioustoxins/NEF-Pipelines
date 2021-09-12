
from argparse import Namespace
from typing import Iterable, List

from lib.sequence_lib import sequence_to_nef_frame, chain_code_iter
from lib.typer_utils import get_args

from pathlib import Path

from lib.structures import SequenceResidue
from lib.util import exit_error, process_stream_and_add_frames


from transcoders.nmrview import import_app
import typer

from transcoders.nmrview.nmrview_lib import read_sequence

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command()
def sequence(
    chain_codes: str = typer.Option('A', '--chains', help='chain codes as a list of names separated by dots',
                                    metavar='<CHAIN-CODES>'),
    no_chain_start: bool = typer.Option(False, '--no-chain-start/',
                                        help="don't include a start of chain link type for the first residue"),
    no_chain_end: bool = typer.Option(False, '--no-chain-end/',
                                      help="don't include an end of chain link type for the last residue"),
    entry_name: str = typer.Option('nmrview', help='a name for the entry'),
    pipe: Path = typer.Option(None, metavar='|PIPE|',
                              help='pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]'),
    file_names: List[Path] = typer.Argument(..., help='input files of type nmrview.seq', metavar='<SEQ-FILE>')
):
    """convert nmrview sequence file <nmrview>.seq files to NEF"""
    try:
        args = get_args()

        process_sequence(args)
    except Exception as e:
        exit_error(f"reading sequence failed because {e}")


def process_sequence(args: Namespace):
    nmrview_frames = []

    for file_name, chain_code in zip(args.file_names, chain_code_iter(args.chain_codes)):
        with open(file_name, 'r') as lines:
            nmrview_sequence = read_sequence(lines, chain_code=chain_code)

            frame = sequence_to_nef_frame(nmrview_sequence, args.entry_name)

            nmrview_frames.append(frame)

    entry = process_stream_and_add_frames(nmrview_frames, args)

    print(entry)


if __name__ == '__main__':

    typer.run(sequence)
