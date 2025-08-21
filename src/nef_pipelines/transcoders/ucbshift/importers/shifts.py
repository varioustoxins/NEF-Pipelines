from pathlib import Path
from typing import List

import typer

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import get_chain_code_iter
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import ShiftList
from nef_pipelines.lib.util import (
    STDIN,
    expand_template_or_exit_error,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.ucbshift import import_app
from nef_pipelines.transcoders.ucbshift.ucbshift_lib import (
    PredictionType,
    parse_ucbshift_shifts,
)

# TODO what about full side chain predictions in UCBshift 2.0?


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
        "{file_name}_{shift_type}",
        "-f",
        "--frame-name",
        help="a template for the frame name. Supports {file_name} and {shift_type} variables",
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

    entry = read_or_create_entry_exit_error_on_bad_file(input_path, "ucbshift")

    entry = pipe(entry, chain_codes, frame_name, file_names, prediction_type)

    print(entry)


def pipe(entry, chain_codes, frame_name_template, file_names, prediction_type):

    frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name, "r") as csvfile:

            file_shifts = parse_ucbshift_shifts(
                csvfile, chain_code, file_name, prediction_type
            )

            # Create frame name from template using this specific file name
            file_name_stem = Path(file_name).stem

            shift_type = _get_prediction_type(prediction_type)

            frame_name = _get_frame_name(
                frame_name_template, file_name_stem, shift_type
            )

            # Create a frame for this file's shifts
            shift_list = ShiftList(file_shifts)
            frame = shifts_to_nef_frame(shift_list, frame_name)
            frames.append(frame)

    return add_frames_to_entry(entry, frames)


def _get_frame_name(frame_name_template, file_name, shift_type):
    """Apply template substitution with error handling for invalid variables"""
    return expand_template_or_exit_error(
        frame_name_template, file_name=file_name, shift_type=shift_type
    )


def _get_prediction_type(prediction_type):
    # Determine shift type name
    if prediction_type == PredictionType.X:
        shift_type = "x"
    elif prediction_type == PredictionType.Y:
        shift_type = "y"
    else:
        shift_type = "ucbshift"
    return shift_type
