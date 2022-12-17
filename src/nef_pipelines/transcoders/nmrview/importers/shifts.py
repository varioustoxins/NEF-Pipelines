from argparse import Namespace
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from pynmrstar import Entry, Saveframe

from nef_pipelines.lib.sequence_lib import chain_code_iter
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import SequenceResidue
from nef_pipelines.lib.typer_utils import get_args
from nef_pipelines.lib.util import (
    cached_file_stream,
    exit_error,
    get_pipe_file_text_or_exit,
    process_stream_and_add_frames,
)
from nef_pipelines.transcoders.nmrview import import_app
from nef_pipelines.transcoders.nmrview.nmrview_lib import parse_shifts, read_sequence

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: str = typer.Option(
        "A",
        "--chains",
        help="chain codes as a list of names spearated by dots",
        metavar="<CHAIN-CODES>",
    ),
    entry_name: str = typer.Option("nmrview", help="a name for the entry"),
    pipe: Path = typer.Option(
        None,
        metavar="|PIPE|",
        help="pipe to read NEF data from, for testing [overrides stdin !use stdin instead!]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type nmrview.out", metavar="<NMRVIEW-shifts>.out"
    ),
):
    """convert nmrview shift file <nmrview-shifts>.out to NEF"""

    try:
        args = get_args()

        process_shifts(args)
    except Exception as e:
        exit_error(f"reading sequence failed because {e}", e)


#
#
def process_shifts(args: Namespace):
    nmrview_frames = []

    for file_name, chain_code in zip(
        args.file_names, chain_code_iter(args.chain_codes)
    ):

        with cached_file_stream(file_name) as lines:

            sequence = _get_sequence_or_exit(args)

            chain_seqid_to_type = _sequence_to_residue_type_lookup(sequence)

            nmrview_shifts = parse_shifts(
                lines, chain_seqid_to_type, chain_code=chain_code, file_name=file_name
            )

            frame = shifts_to_nef_frame(nmrview_shifts, args.entry_name)

            nmrview_frames.append(frame)

    entry = process_stream_and_add_frames(nmrview_frames, args)

    print(entry)


def sequence_from_frames(frames: Saveframe) -> List[SequenceResidue]:

    residues = []
    for frame in frames:
        for loop in frame:
            chain_code_index = loop.tag_index("chain_code")
            sequence_code_index = loop.tag_index("sequence_code")
            residue_name_index = loop.tag_index("residue_name")

            for line in loop:
                chain_code = line[chain_code_index]
                sequence_code = int(line[sequence_code_index])
                residue_name = line[residue_name_index]
                residue = SequenceResidue(chain_code, sequence_code, residue_name)
                residues.append(residue)

    return residues


# TODO this should be replaced by a library function from nef or sequence utils...
# also need ro report what file we are trying to read shifts from
def _get_sequence_or_exit(args):
    sequence_file = None
    if "sequence" in args:
        sequence_file = args.sequence

    sequence = None
    if not sequence_file:
        try:
            lines = get_pipe_file_text_or_exit(args)

            entry = Entry.from_string(lines)
            frames = entry.get_saveframes_by_category("nef_molecular_system")
            sequence = sequence_from_frames(frames)

        except Exception as e:
            exit_error(f"failed to read sequence from input stream because {e}", e)

    else:
        with open(sequence_file, "r") as lines:
            sequence = read_sequence(lines, chain_code=args.chain_code)
    return sequence


def _sequence_to_residue_type_lookup(
    sequence: List[SequenceResidue],
) -> Dict[Tuple[str, int], str]:
    result: Dict[Tuple[str, int], str] = {}
    for residue in sequence:
        result[residue.chain_code, residue.sequence_code] = residue.residue_name
    return result


if __name__ == "__main__":

    typer.run(shifts)
