import string
import sys
from itertools import zip_longest
from pathlib import Path
from textwrap import dedent
from typing import Dict, List

import typer
from fyeah import f

from nef_pipelines.lib.isotope_lib import ATOM_TO_ISOTOPE
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_1_3,
    MoleculeTypes,
    chain_code_iter,
    residues_to_residue_name_lookup,
    sequence_from_entry,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    NewPeak,
    PeakFitMethod,
    Residue,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_float,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.sparky import import_app
from nef_pipelines.transcoders.sparky.importers.shifts import (
    _exit_if_chain_codes_and_file_name_dont_match,
)


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
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A]",
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
        help="if set don't validate the peaks agains the inpuy sequence if provided",
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
):
    """convert sparky peaks file <SPARKY-PEAKS>.txt to NEF [alpha]"""

    chain_codes = parse_comma_separated_options(chain_codes)

    if not chain_codes:
        chain_codes = ["A"]

    # make this a library function
    _exit_if_chain_codes_and_file_name_dont_match(chain_codes, file_names)

    entry = read_or_create_entry_exit_error_on_bad_file(input)

    sequence = sequence_from_entry(entry) if not no_validate else None

    nuclei = parse_comma_separated_options(nuclei)

    entry = pipe(
        entry,
        frame_name,
        file_names,
        chain_codes,
        sequence,
        input_dimensions=nuclei,
        spectrometer_frequency=spectrometer_frequency,
        molecule_type=molecule_type,
    )

    print(entry)


def pipe(
    entry,
    frame_name,
    file_names,
    chain_codes,
    sequence,
    input_dimensions,
    spectrometer_frequency,
    molecule_type=MoleculeTypes.PROTEIN,
):

    sparky_frames = []

    for file_name, chain_code in zip(file_names, chain_code_iter(chain_codes)):

        try:
            with open(file_name, "r") as fp:
                lines = fp.readlines()
        except IOError as e:
            msg = f"""
                    while reading sparky peaks file {file_name} there was an error reading the file
                    the error was: {e}
                """
            exit_error(msg, e)

        sparky_peaks = _parse_peaks(
            lines,
            file_name=file_name,
            molecule_type=molecule_type,
            chain_code=chain_code,
            sequence=sequence,
        )

        dimensions = _guess_dimensions_if_not_defined_or_throw(
            sparky_peaks, input_dimensions
        )

        dimensions = [{"axis_code": dimension} for dimension in dimensions]

        frame = peaks_to_frame(sparky_peaks, dimensions, spectrometer_frequency)

        file_name = Path(file_name).stem  # used in f method...

        frame.name = f(frame_name)

        sparky_frames.append(frame)

    return add_frames_to_entry(entry, sparky_frames)


def parse_header_to_columns(header_line: str, file_name) -> Dict[str, int]:
    headings_to_columns = {}
    headings = header_line.split()

    if "Data" in headings:
        headings.remove("Data")

    while ("(hz)") in headings:
        headings.remove("(hz)")

    for i, heading in enumerate(headings):
        if heading in "Assignment Height Volume".split():
            headings_to_columns[heading] = i
            continue

        if heading.startswith("w") or heading.startswith("lw"):
            headings_to_columns[heading] = i
            continue

        # TODO add a warning function in the library
        msg = f"""
            WARNING: unexpected heading {heading} in the file {file_name}...
                     this heading will be ignored, please send the heading and first
                     few lines of this file to the developers of NEF-Pipelines if you
                     believe this is a valid sparky peaks file
        """

        print(msg, file=sys.stderr)

    assignment_column = headings_to_columns["Assignment"]
    if assignment_column != 0:
        msg = f"""
            The file {file_name} doesn't look like a sparky file the Assignment column should be the first column
            i got {assignment_column}
            header was
            {header_line}
        """
        exit(msg)

    return headings_to_columns


def _exit_error_if_shift_not_float(shifts, line_info):
    for i, shift in enumerate(shifts, start=1):
        if not is_float(shift):
            msg = f"""
                file {line_info.file_name} does not look like a sparky file
                for shift w{i} at line {line_info.line_no} with the value {shift} couldn't be converted to a float
                the full line was:
                {line_info.line}
            """
            exit_error(msg)


def _parse_peaks(lines, file_name, molecule_type, chain_code, sequence):

    peaks = []

    in_data = False

    dimension_count = None

    for line_number, line in enumerate(lines, start=1):

        line = line.strip()

        line_info = LineInfo(file_name, line_number, line)

        if len(line) == 0:
            continue

        if line.startswith("#"):
            continue

        if line.strip()[: len("Assignment")] == "Assignment":
            if in_data:
                _exit_error_header_in_data(line_info)

            column_headers_to_indices = parse_header_to_columns(line, file_name)

            dimension_count = _count_dimensions(column_headers_to_indices)

            _exit_error_no_dimensions(dimension_count, line_info)

            in_data = True

            continue
        else:
            if not in_data:
                _exit_error_data_but_no_header(line_info)

            fields = line.split()

            column_count = len(fields)
            if column_count < (dimension_count + 1):
                _exit_error_not_enough_columns_in_data_row(
                    dimension_count, column_count, line_info
                )
            values = {}
            for column, index in column_headers_to_indices.items():
                if index < len(fields):
                    values[column] = fields[index]
                else:
                    values[column] = UNUSED

            assignmnents_column = column_headers_to_indices["Assignment"]
            raw_assignment = fields[assignmnents_column]

            assignments = _process_assignments(
                raw_assignment, chain_code, sequence, molecule_type, line_info
            )

            shifts = [
                fields[column_headers_to_indices[f"w{index}"]]
                for index in range(1, dimension_count + 1)
            ]

            converted_shifts = []
            for shift in shifts:
                shift = float(shift) if is_float(shift) else shift
                converted_shifts.append(shift)

            _exit_error_if_shift_not_float(shifts, line_info)

            shifts = converted_shifts

            peak_fit_method = None
            volume = None
            if "Volume" in column_headers_to_indices:

                volume_index = column_headers_to_indices["Volume"]

                volume = float(fields[volume_index])

                line_fit_index = volume_index + 1
                if line_fit_index < len(fields):
                    if fields[line_fit_index] == "ga":
                        peak_fit_method = PeakFitMethod.GAUSSIAN
                        fields.remove("ga")

            height = (
                float(fields[column_headers_to_indices["Height"]])
                if "Height" in column_headers_to_indices
                else None
            )

            comment_fields = []
            line_widths = []
            for dimension in range(1, dimension_count + 1):
                line_width_column = f"lw{dimension}"
                if line_width_column in column_headers_to_indices:
                    line_width_column_index = column_headers_to_indices[
                        line_width_column
                    ]
                    if line_width_column_index < len(fields):
                        possible_line_width = fields[line_width_column_index]
                        if is_float(possible_line_width):
                            line_widths.append(float(possible_line_width))
                        else:
                            comment_fields.append(possible_line_width)
                            line_widths.append(None)
                    else:
                        line_widths.append(None)

            shift_data = [
                ShiftData(atom=atom, value=value, line_width=line_width)
                for atom, value, line_width in zip_longest(
                    assignments, shifts, line_widths, fillvalue=None
                )
            ]

            max_column = max(column_headers_to_indices.values())
            if len(fields) > max_column:
                comment_fields = [*comment_fields, *fields[max_column + 1 :]]

            comment = " ".join(comment_fields)

            peak = NewPeak(
                shifts=shift_data,
                peak_fit_method=peak_fit_method,
                height=height,
                volume=volume,
                comment=comment,
            )

            peaks.append(peak)

    return peaks


def _exit_error_data_but_no_header(line_info):
    msg = f"""
                    the file {line_info.file_name} doesn't look like a sparky file at line {line_info.line_no}
                    there appears to be a data line but no header was detected a head should look like
                    Assignment w1 w2 ... etc
                    the current line data is
                    {line_info.line}
                """
    exit_error(msg)


def _exit_error_not_enough_columns_in_data_row(
    dimension_count, column_count, line_info
):
    msg = f"""
            In sparky peaks file {line_info.file_name} at line {line_info.line_no}
            there were was not enough data [expected {1+ dimension_count} columns
            (Assignment + shifts * {dimension_count})]
            the line was:
            {line_info.line}
        """
    exit_error(msg)


def _exit_error_no_dimensions(dimension_count, line_info):
    if dimension_count < 1:
        msg = f"""
                    sparky peak file {line_info.file_name} doesn't appear to have enough columns [minimum 1]
                    at line {line_info.line_no}
                    the header was:
                    {line_info.line}
                """
        sys.exit(msg)


def _count_dimensions(column_headers_to_indices):
    dimension_count = 0
    for name in [f"w{i}" for i in range(1, 20)]:
        if name in column_headers_to_indices:
            dimension_count += 1
        else:
            break
    return dimension_count


def _exit_error_header_in_data(line_info):
    msg = f"""
        bad sparky peak file {line_info.file_name} at line no {line_info.line_number} there appears to be a
        second header...
        the line was:
        {line_info.line}
                """
    exit_error(msg)


# TODO this doesn't cope with abbreviated names
def _process_assignments(
    assignments, chain_code, sequence: List[SequenceResidue], molecule_type, line_info
):

    residue_name_lookup = residues_to_residue_name_lookup(sequence)

    residue_name_translations = TRANSLATIONS_1_3[molecule_type]

    fields = assignments.split("-")

    assignments = []
    last_sequence_code = None
    last_residue_name = None
    for field in fields:

        if len(field) == 1 and field == "?":
            assignment = AtomLabel(
                atom_name=UNUSED, residue=Residue("@-", UNUSED, UNUSED)
            )
            assignments.append(assignment)
        else:

            without_first_letters = field.lstrip(string.ascii_letters)

            first_letters = field[: -len(without_first_letters)]

            if len(first_letters) == 0 and without_first_letters[0] == "?":
                first_letters = "?"
                without_first_letters = without_first_letters[1:]

            without_numbers = without_first_letters.lstrip(string.digits)
            without_numbers = without_numbers.lstrip("\"'")

            numbers = without_first_letters[: -len(without_numbers)]

            if (
                without_numbers != ""
                and len(numbers) == 0
                and without_numbers[0] == "?"
            ):
                numbers = "?"
                without_numbers = without_numbers[1:]

            if without_numbers == "":
                residue_name = last_residue_name
            elif len(first_letters) == 0 or first_letters == "?":
                residue_name = UNUSED
            else:
                residue_name = first_letters

            if without_numbers == "":
                sequence_code = last_sequence_code
            elif len(numbers) == 0 or numbers == "?":
                sequence_code = UNUSED
            else:
                sequence_code = numbers

            if without_numbers == "":
                atom_name = f"{first_letters}{without_first_letters}"
            elif len(without_numbers) == 0 or without_numbers == "?":
                atom_name = UNUSED
            else:
                atom_name = without_numbers

            if residue_name_translations is not None:
                if residue_name in residue_name_translations:
                    translated_residue_name = residue_name_translations[residue_name]
                else:
                    msg = f"""
                        The residue name {residue_name} is not defined for the molecule type {molecule_type} for the
                        assignment {assignment} at line {line_info.line_no} in file {line_info.file_name} the line was
                        {line_info.line}
                    """
                    exit_error(msg)

            if sequence and ((chain_code, sequence_code) not in residue_name_lookup):
                msg = f"""
                    the chain code {chain_code} and sequence_code {sequence} from
                    line {line_info.line_no} in file {line_info.file_name} were not found
                    in the input sequence, the full line was

                    {line_info.line}

                    if you wish to input the peaks without validating against the input sequence use the
                    --no-validate option of sparky import peaks
                """
                exit_error(msg)

            assignment = AtomLabel(
                atom_name=atom_name,
                residue=Residue(chain_code, sequence_code, translated_residue_name),
            )

            assignments.append(assignment)

        last_sequence_code = sequence_code
        last_residue_name = residue_name

    return assignments


# TODO: this needs to be moved to a library
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
