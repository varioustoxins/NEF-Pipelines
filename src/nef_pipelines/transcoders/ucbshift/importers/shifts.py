from enum import auto
from pathlib import Path
from typing import List

import typer
from strenum import LowercaseStrEnum

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import get_chain_code_iter
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import ShiftList
from nef_pipelines.lib.util import STDIN, parse_comma_separated_options
from nef_pipelines.transcoders.ucbshift import import_app
from nef_pipelines.transcoders.ucbshift.ucbshift_lib import parse_ucbshift_shifts

# TODO what about full side chain predictions in UCBshift 2.0?
# TODO what about clashes in multiple files


class PredictionType(LowercaseStrEnum):
    X = auto()
    Y = auto()
    COMBINED = auto()


@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A]",
        metavar="<CHAIN-CODES>",
    ),
    prediction_type: PredictionType = typer.Option(
        PredictionType.COMBINED,
        "--prediction-type",
        help="which UCBShift prediction columns to use (x, y, or combined)",
    ),
    frame_name: str = typer.Option(
        "ucbshift", "-f", "--frame-name", help="a name for the frame"
    ),
    input_path: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type UCBShift CSV", metavar="<UCBShift-shifts>.csv"
    ),
):
    """convert shifts from UCBShift CSV file to NEF α"""

    chain_codes = parse_comma_separated_options(chain_codes)

    entry = read_entry_from_file_or_stdin_or_exit_error(input_path)

    entry = pipe(entry, chain_codes, frame_name, file_names, prediction_type)

    print(entry)


def pipe(entry, chain_codes, entry_name, file_names, prediction_type):

    ucbshift_frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name, "r") as csvfile:

            ucbshift_shifts = parse_ucbshift_shifts(
                csvfile, chain_code, file_name, prediction_type
            )

            shift_list = ShiftList(shifts=ucbshift_shifts)
            frame = shifts_to_nef_frame(shift_list, entry_name)

            ucbshift_frames.append(frame)

    return add_frames_to_entry(entry, ucbshift_frames)
