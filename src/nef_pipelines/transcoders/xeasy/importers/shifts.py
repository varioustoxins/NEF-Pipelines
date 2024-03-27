from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import ShiftList
from nef_pipelines.lib.util import STDIN
from nef_pipelines.transcoders.xeasy import import_app
from nef_pipelines.transcoders.xeasy.xeasy_lib import parse_shifts

app = typer.Typer()


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    frame_name: str = typer.Option(
        "xeasy", "-f", "--frame-name", help="a name for the frame"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type nmrview.out", metavar="<NMRVIEW-shifts>.out"
    ),
):
    """convert xeasy [flya] shift file <sparky-shifts>.txt to NEF"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    sequence = sequence_from_entry_or_exit(entry)

    pipe(entry, sequence, frame_name, file_names)


def pipe(entry, sequence, entry_name, file_names):

    xeasy_frames = []

    for file_name in file_names:

        with open(file_name) as lines:

            chain_seqid_to_type = sequence_to_residue_name_lookup(sequence)

            xeasy_shifts = parse_shifts(lines, file_name, chain_seqid_to_type)

            shift_list = ShiftList(xeasy_shifts)

            frame = shifts_to_nef_frame(shift_list, entry_name)

            xeasy_frames.append(frame)

    entry = add_frames_to_entry(entry, xeasy_frames)

    print(entry)
