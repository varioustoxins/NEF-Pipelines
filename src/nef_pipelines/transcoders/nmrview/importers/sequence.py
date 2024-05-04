from argparse import Namespace
from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.sequence_lib import get_chain_code_iter, sequence_to_nef_frame
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    parse_comma_separated_options,
    process_stream_and_add_frames,
)
from nef_pipelines.transcoders.nmrview import import_app
from nef_pipelines.transcoders.nmrview.nmrview_lib import read_sequence

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def sequence(
    chain_codes: str = typer.Option(
        "A",
        "--chains",
        help="chain codes, can be called multiple times and or be a comma separated list [no spaces!]",
        metavar="<CHAIN-CODES>",
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
    entry_name: str = typer.Option("nmrview", help="a name for the entry"),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        help="pipe to read NEF data from other than stdin",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type nmrview.seq", metavar="<SEQ-FILE>"
    ),
):
    """convert nmrview sequence file <nmrview>.seq files to NEF"""
    try:
        args = get_args()

        process_sequence(args)
    except Exception as e:
        exit_error(f"reading sequence failed because {e}")


def process_sequence(args: Namespace):
    nmrview_frames = []

    chain_codes = parse_comma_separated_options(args.chain_codes)
    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(args.file_names, chain_code_iter):
        with open(file_name, "r") as lines:
            nmrview_sequence = read_sequence(lines, chain_code=chain_code)

            frame = sequence_to_nef_frame(nmrview_sequence, args.entry_name)

            nmrview_frames.append(frame)

    entry = process_stream_and_add_frames(nmrview_frames, args)

    print(entry)


if __name__ == "__main__":

    typer.run(sequence)
