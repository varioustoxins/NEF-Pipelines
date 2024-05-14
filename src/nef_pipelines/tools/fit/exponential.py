from enum import auto
from pathlib import Path
from typing import Dict, List, Tuple

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry, Saveframe
from strenum import StrEnum

from nef_pipelines.lib.nef_lib import (
    SelectionType,
    read_entry_from_file_or_stdin_or_exit_error,
    select_frames,
)
from nef_pipelines.lib.shift_lib import IntensityMeasurementType
from nef_pipelines.lib.util import exit_error, parse_comma_separated_options
from nef_pipelines.tools.fit import fit_app

streamfitter_install_failure = None
try:
    from streamfitter.fitter import ErrorPropogation, fitter

    stream_fitter = fitter

except ImportError as e:
    streamfitter_intall_failure = e

    # this is partial copy of the enum to avoid errors
    class ErrorPropogation(StrEnum):
        PROPOGATION = "error stream fitter package not installed"
        ERROR_STREAM_FITTER_NOT_INSTALLED = auto()

    stream_fitter = None


@fit_app.command()
def exponential(
    input: Path = typer.Option(
        None,
        "-i",
        "--in",
        metavar="NEF-FILE",
        help="read NEF data from a file instead of stdin",
    ),
    error_method: ErrorPropogation = typer.Option(
        ErrorPropogation.PROPOGATION,
        "-e",
        "--error-method",
        help="error propogation method",
    ),
    cycles: int = typer.Option(
        1000,
        "-c",
        "--cycles",
        help="number of cycles for error propogation",
    ),
    noise_level: float = typer.Option(
        None,
        "-n",
        "--noise-level",
        help="noise level to use instead of value from replicates",
    ),
    seed: int = typer.Option(
        42, "-s", "--seed", help="seed for random number generator"
    ),
    data_type: IntensityMeasurementType = typer.Option(
        IntensityMeasurementType.HEIGHT, "-d", "--data-type", help="data type to fit"
    ),
    frames_selectors: List[str] = typer.Argument(None, help="select frames to fit"),
):
    """- fit a data series to an exponential decay with error propogation"""

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    frame_selectors = parse_comma_separated_options(frames_selectors)

    _exit_if_no_frame_selectors(frame_selectors)

    series_frames = _select_relaxation_series_or_exit(entry, frames_selectors)

    _exit_if_no_series_frames_selected(series_frames, frame_selectors)

    entry = pipe(
        entry, series_frames, error_method, cycles, noise_level, data_type, seed
    )

    print(entry)


# TODO:  there is some duplication here!
def _select_relaxation_series_or_exit(
    entry: Entry, frame_selectors: List[str]
) -> Tuple:
    relaxation_frames = select_frames(entry, "nef_series_list", SelectionType.CATEGORY)
    series_frames_and_ids = OrderedSet(
        [
            (spectrum_frame.name, id(spectrum_frame))
            for spectrum_frame in relaxation_frames
        ]
    )

    named_frames = []
    for frame_selector in frame_selectors:
        named_frames.extend(select_frames(entry, frame_selector, SelectionType.NAME))

    named_frames_and_ids = OrderedSet(
        [(named_frame.name, id(named_frame)) for named_frame in named_frames]
    )

    selected_frames_and_ids = series_frames_and_ids.intersection(named_frames_and_ids)

    return [
        entry.get_saveframe_by_name(frame_name)
        for frame_name, _ in selected_frames_and_ids
    ]


def _exit_if_no_series_frames_selected(active_relaxation_frames, frame_selectors):
    if not active_relaxation_frames:
        msg = f"""
            no series frames selected by the selectors
            {" ".join(frame_selectors)}
        """
        exit_error(msg)


def _exit_if_no_frame_selectors(frame_selectors):
    if len(frame_selectors) == 0:
        msg = "you must select some frames!"
        exit_error(msg)

    return None


def pipe(
    entry: Entry,
    series_frames: List[Saveframe],
    error_method: ErrorPropogation,
    cycles: int,
    noise_level,
    data_type: IntensityMeasurementType,
    seed: int,
) -> Dict:

    if stream_fitter is None:
        msg = f"""
                error the package streamfitter is not installed or is not importing properly
                the error was {streamfitter_intall_failure}
            """

        exit_error(msg)

    return stream_fitter(
        entry, series_frames, error_method, cycles, noise_level, data_type, seed
    )
