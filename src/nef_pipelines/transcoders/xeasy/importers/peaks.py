from pathlib import Path
from typing import List

import typer
from fyeah import f

from nef_pipelines.lib.nef_lib import (
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.sequence_lib import (
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.util import STDIN
from nef_pipelines.transcoders.sparky.importers.peaks import (
    _guess_dimensions_if_not_defined_or_throw,
)
from nef_pipelines.transcoders.xeasy import import_app
from nef_pipelines.transcoders.xeasy.xeasy_lib import parse_peaks


# TODO: this needs to be moved to a library
class XeasyPeakListException(Exception):
    pass


class IncompatibleDimensionTypesException(XeasyPeakListException):
    pass


app = typer.Typer()

DEFAULT_NUCLEI_HELP = (
    "nuclei to use for each dimension, if not defined they are guessed from the assignments"
    "or an error is reported"
)


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    frame_name: str = typer.Option(
        "xeasy_{file_name}",
        "-f",
        "--frame-name",
        help="a templated name for the frame {file_name} will be replaced by input filename",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--in",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type peaks.txt", metavar="<XEASY-peaks>.peaks"
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
):
    """convert xeasy peaks file <XEASY-PEAKS>.peaks to NEF"""

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    sequence = sequence_from_entry_or_exit(entry)

    entry = pipe(
        entry,
        frame_name,
        file_names,
        sequence,
        spectrometer_frequency=spectrometer_frequency,
    )

    print(entry)


def pipe(
    entry,
    frame_name,
    file_names,
    sequence,
    spectrometer_frequency,
):

    xeasy_frames = []

    residue_type_lookup = sequence_to_residue_name_lookup(sequence)
    for file_name in file_names:

        with file_name.open() as fh:
            lines = fh.readlines()

        spectrum_type, dimension_info, peaks = parse_peaks(
            lines, file_name, residue_type_lookup
        )

        dimensions = _guess_dimensions_if_not_defined_or_throw(peaks, dimension_info)

        dimensions = [{"axis_code": dimension.axis_code} for dimension in dimensions]

        file_name = Path(file_name).stem  # used in f method...

        frame_name = f(frame_name)

        frame = peaks_to_frame(
            peaks, dimensions, spectrometer_frequency, frame_code=frame_name
        )

        xeasy_frames.append(frame)

    return add_frames_to_entry(entry, xeasy_frames)
