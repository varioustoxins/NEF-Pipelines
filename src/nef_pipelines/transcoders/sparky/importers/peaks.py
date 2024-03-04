import string
from itertools import zip_longest
from pathlib import Path
from textwrap import dedent
from typing import List

import typer
from fyeah import f

from nef_pipelines.lib.isotope_lib import ATOM_TO_ISOTOPE
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.sequence_lib import MoleculeTypes, sequence_from_entry
from nef_pipelines.lib.structures import NewPeak
from nef_pipelines.lib.translation_lib import translate_new_peak
from nef_pipelines.lib.util import STDIN, exit_error, parse_comma_separated_options
from nef_pipelines.transcoders.sparky import import_app
from nef_pipelines.transcoders.sparky.importers.shifts import (
    _exit_if_number_chain_codes_and_file_names_dont_match,
)
from nef_pipelines.transcoders.sparky.sparky_lib import parse_peaks


# TODO: this needs to be moved to a library
class SparkyPeakListException(Exception):
    pass


class IncompatibleDimensionTypesException(SparkyPeakListException):
    pass


app = typer.Typer()

DEFAULT_NUCLEI_HELP = (
    "nuclei to use for each dimension, if not defined they are guessed from the assignments"
    "or an error is reported"
)


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def peaks(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A] "
        "one per file. If only one chain code is supplied it applies to all files",
        metavar="<CHAIN-CODES>",
    ),
    frame_name: str = typer.Option(
        "sparky_{file_name}",
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
        ..., help="input files of type peaks.txt", metavar="<SPARKY-peaks>.txt"
    ),
    nuclei: List[str] = typer.Option([], help=DEFAULT_NUCLEI_HELP),
    default_chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain-code",
        help="default chain code to use if none is provided in the file",
    ),
    molecule_type: MoleculeTypes = typer.Option(
        MoleculeTypes.PROTEIN, help="the type of molecule"
    ),
    no_validate: bool = typer.Option(
        False,
        help="if set don't validate the peaks against the input sequence if provided",
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
):
    """convert sparky peaks file <SPARKY-PEAKS>.txt to NEF"""

    chain_codes = parse_comma_separated_options(chain_codes)

    if not chain_codes:
        chain_codes = ["A"]

    if len(chain_codes) == 1 and len(file_names) > 1:
        chain_codes = chain_codes * len(file_names)

    # make this a library function
    _exit_if_number_chain_codes_and_file_names_dont_match(chain_codes, file_names)

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    sequence = sequence_from_entry(entry) if not no_validate else None

    nuclei = parse_comma_separated_options(nuclei)

    file_names_and_lines = {}
    for file_name, chain_code in zip_longest(file_names, chain_codes, fillvalue=None):

        if file_name is None:
            continue

        if chain_code is None:
            chain_code = chain_codes[-1]

        try:
            with open(file_name, "r") as fp:
                lines = fp.readlines()
        except IOError as e:
            msg = f"""
                    while reading sparky peaks file {file_name} there was an error reading the file
                    the error was: {e}
                """
            exit_error(msg, e)

        file_names_and_lines[file_name] = lines

    entry = pipe(
        entry,
        frame_name,
        file_names_and_lines,
        chain_code,
        sequence,
        input_dimensions=nuclei,
        spectrometer_frequency=spectrometer_frequency,
        molecule_type=molecule_type,
    )

    print(entry)


def pipe(
    entry,
    frame_code_template,
    file_names_and_lines,
    chain_code,
    sequence,
    input_dimensions,
    spectrometer_frequency,
    molecule_type=MoleculeTypes.PROTEIN,
):

    sparky_frames = []

    for file_name, lines in file_names_and_lines.items():

        sparky_peaks = parse_peaks(
            lines,
            file_name=file_name,
            molecule_type=molecule_type,
            chain_code=chain_code,
            sequence=sequence,
        )

        sparky_peaks = [translate_new_peak(peak) for peak in sparky_peaks]

        dimensions = _guess_dimensions_if_not_defined_or_throw(
            sparky_peaks, input_dimensions
        )

        dimensions = [{"axis_code": dimension} for dimension in dimensions]

        file_name = Path(file_name).stem  # used in f method...

        frame_code = f(frame_code_template)

        frame = peaks_to_frame(
            sparky_peaks, dimensions, spectrometer_frequency, frame_code=frame_code
        )

        sparky_frames.append(frame)

    return add_frames_to_entry(entry, sparky_frames)


def _guess_dimensions_if_not_defined_or_throw(
    peaks: List[NewPeak], input_dimensions: List[str]
) -> List[str]:
    results_by_dimension = {
        i: dimension for i, dimension in enumerate(input_dimensions)
    }

    guessed_dimensions = {}

    for peak_number, peak in enumerate(peaks, start=1):

        for dimension_index, shift in enumerate(peak.shifts):
            atom_name = shift.atom.atom_name

            if len(atom_name) == 0:
                atom_name = None

            atom_type = None
            if atom_name != UNUSED and atom_name is not None:
                atom_type = atom_name.strip()[0]

            if atom_type is not None and atom_type.lower() not in string.ascii_letters:
                atom_type = None

            guessed_dimension_isotopes = guessed_dimensions.setdefault(
                dimension_index, set()
            )
            if atom_type and atom_type in ATOM_TO_ISOTOPE:
                isotope_code = ATOM_TO_ISOTOPE[atom_type]
                guessed_dimension_isotopes.add(isotope_code)
            else:
                guessed_dimension_isotopes.add(UNUSED)

    for guessed_dimension_index in guessed_dimensions:
        if guessed_dimension_index not in results_by_dimension:

            guessed_dimension = guessed_dimensions[guessed_dimension_index]
            if len(guessed_dimension) > 1 and UNUSED in guessed_dimension:
                guessed_dimension.remove(UNUSED)

            if len(guessed_dimensions[guessed_dimension_index]) > 1:

                _raise_multiple_guessed_isotopes(
                    guessed_dimensions, guessed_dimension_index
                )

    for dimension_index in guessed_dimensions:
        if dimension_index not in results_by_dimension:
            results_by_dimension[dimension_index] = list(
                guessed_dimensions[dimension_index]
            )[0]

    max_dimension = max(results_by_dimension.keys())

    result = []
    for i in range(max_dimension + 1):
        result.append(results_by_dimension[i])

    return result


def _raise_multiple_guessed_isotopes(guessed_dimensions, guessed_dimension_index):
    dim_info = []
    for dimension_index in sorted(guessed_dimensions).keys():
        dim_data = f"{dimension_index}: {' '.join(guessed_dimensions.values())}"
        dim_info.append(dim_data)
    msg = f"""\
                    no isotope provided for dimension {guessed_dimension_index + 1} and multiple possibilities
                    found in atom names, please use explicit isotope codes using dimension-nuclei

                    deduced codes for dimensions:


                """
    msg = dedent(msg)
    msg += dim_info
    raise IncompatibleDimensionTypesException(msg)
