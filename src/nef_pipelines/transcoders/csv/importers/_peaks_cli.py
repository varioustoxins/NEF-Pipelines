import csv
import re
import string
from enum import auto
from io import TextIOWrapper
from pathlib import Path
from textwrap import dedent
from typing import Dict, List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry
from strenum import StrEnum
from tabulate import tabulate

from nef_pipelines.lib.isotope_lib import ATOM_TO_ISOTOPE
from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.peak_lib import peaks_to_frame
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    sequence_from_entry,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    NewPeak,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    flatten,
    get_display_file_name,
    is_float,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.csv import import_app

app = typer.Typer()

HELP_FOR_FRAME_NAME = "name for the frame, note white spaces will be replace by _"
HELP_FOR_FORMATS = """\
    CSV like formats that can be read [CSV: comma separated variables, TSV tab separated variables,
    SSV space separated variables, AUTO read file and guess format from contents]
"""


class CsvLikeFormats(StrEnum):
    CSV = auto()
    TSV = auto()
    SSV = auto()
    AUTO = auto()
    csv = auto()
    tsv = auto()
    ssv = auto()
    auto = auto()


INDEX = "index"
PEAK_ID = "peak_id"

CHAIN_CODE_STUB = "chain_code_"
SEQUENCE_CODE_STUB_ = "sequence_code_"
RESIDUE_NAME_STUB = "residue_name_"
ATOM_NAME_STUB = "atom_name_"
ATOM_CODES = flatten(
    [
        f"{CHAIN_CODE_STUB}{i} {SEQUENCE_CODE_STUB_}{i} {RESIDUE_NAME_STUB}{i} {ATOM_NAME_STUB}{i}".split()
        for i in range(1, 16)
    ]
)
POSITION_STUB = "position_"
POSITION_UNCERTAINTY_STUB = "position_uncertainty_"
POSITION_CODES = [f"{POSITION_STUB}{i}".split() for i in range(1, 16)]
POSITION_UNCERTAINTY_CODES = [
    f"{POSITION_UNCERTAINTY_STUB}{i}".split() for i in range(1, 16)
]
VOLUME = "volume"
VOLUME_UNCERTAINTY = "volume_uncertainty"
HEIGHT = "height"
HEIGHT_UNCERTAINTY = "height_uncertainty"

BASIC_HEADERS = flatten([PEAK_ID, *ATOM_CODES, *POSITION_CODES])
OPTIONAL_HEADERS = [
    VOLUME,
    VOLUME_UNCERTAINTY,
    HEIGHT,
    HEIGHT_UNCERTAINTY,
    *POSITION_UNCERTAINTY_CODES,
]
REQUIRED_HEADERS = [PEAK_ID, *ATOM_CODES[:4], *POSITION_CODES[0]]

COLUMN_SEPARATORS_MAY_HAVE_CHANGED = (
    "note: column separators shown here may different to those in the original file..."
)
DEFAULT_ATOMS_HELP = (
    "the atoms to use if atoms names aren't defined in the file "
    "This option can be used multiple twice to define the atoms or you can use a "
    "comma separated list"
)

DEFAULT_NUCLEI_HELP = (
    "nuclei to use for each dimension if not defined they are guessed from the assigments"
    "or an error is reported"
)


class CSVPeakListException(Exception):
    pass


class BadSequenceException(CSVPeakListException):
    pass


class BadDimensionException(CSVPeakListException):
    pass


class IncompatibleDimensionTypesException(CSVPeakListException):
    pass


@import_app.command(no_args_is_help=True)
def peaks(
    entry_input: Path = typer.Option(
        STDIN,
        metavar="<INPUT>",
        help="file to read NEF data from [stdin = -]",
    ),
    csv_format: CsvLikeFormats = typer.Option(
        CsvLikeFormats.AUTO, "-f", "--format", help=HELP_FOR_FORMATS
    ),
    csv_file_encoding: str = typer.Option(
        "utf-8-sig", "-e", "--encoding", help="encoding for the csv file"
    ),
    default_atoms: List[str] = typer.Option(
        [], "-a", "--atoms", help=DEFAULT_ATOMS_HELP
    ),
    dimension_nuclei: List[str] = typer.Option([], help=DEFAULT_NUCLEI_HELP),
    default_chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain-code",
        help="default chain code to use if none is provided in the file",
    ),
    spectrometer_frequency: float = typer.Option(
        600.123456789, help="spectrometer frequency in MHz"
    ),
    csv_file: Path = typer.Argument(None, metavar="<CSV-FILE>"),
):
    default_atoms = parse_comma_separated_options(default_atoms)

    csv_format = csv_format.upper()

    entry = read_or_create_entry_exit_error_on_bad_file(entry_input)

    try:
        pipe(
            entry,
            default_chain_code,
            default_atoms,
            csv_file,
            csv_file_encoding,
            csv_format,
            dimension_nuclei,
            spectrometer_frequency,
        )
    except BadSequenceException as e:

        sequence_table = _tabulate_sequence(entry)
        _exit_bad_sequence(e, entry_input, sequence_table)

    except BadDimensionException as e:
        msg = f"peak list dimensions were not usable because {e}"
        exit_error(msg)

    except CSVPeakListException as e:
        exit_error(str(e))

    print(entry)


def _exit_bad_sequence(e, entry_input, sequence_table=None):
    msg = (
        f"{dedent(str(e))}\n"
        f"the source of the residue sequence was: {get_display_file_name(entry_input)}\n\n"
    )
    if not sequence_table:
        msg += "note: if you would like to see a complete input sequence use the verbose option"
    else:
        msg += "sequence was:\n\n"
        msg += sequence_table

    exit_error(msg)


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


def pipe(
    entry: Entry,
    chain_code: str,
    atoms: List[str],
    csv_file: Path,
    csv_file_encoding: str,
    csv_format: CsvLikeFormats,
    input_dimensions: List[str],
    spectrometer_frequency,
) -> Entry:
    encoding = {"encoding": csv_file_encoding}

    file_shifts = _parse_csv(
        csv_file, encoding, chain_code, atoms, csv_file, csv_format
    )

    dimensions = _guess_dimensions_if_not_defined_or_throw(
        file_shifts, input_dimensions
    )

    dimensions = [{"axis_code": dimension} for dimension in dimensions]

    frame = peaks_to_frame(file_shifts, dimensions, spectrometer_frequency)

    add_frames_to_entry(entry, [frame])

    return entry


def _parse_csv(
    csv_file: Path,
    encoding: Dict[str, str],
    default_chain_code: str,
    atoms: List[str],
    file_name: str,
    csv_format: str,
) -> List[NewPeak]:
    column_offsets = {}
    headers = [*BASIC_HEADERS, *OPTIONAL_HEADERS]

    peaks = []
    with open(csv_file, **encoding) as csv_fp:

        peak_reader = _get_csv_reader_for_format(csv_format, csv_fp, encoding)

        for i, row in enumerate(peak_reader):
            row = [elem.strip() for elem in row]

            line_info = LineInfo(file_name, i + 1, ", ".join(row))
            if i == 0:
                header_row = [elem.lower() for elem in row]

                _exit_if_headers_dont_look_right(row, i + 1, header_row, file_name)

                for header in headers:
                    if header in header_row:
                        column_offsets[header] = header_row.index(header)

            else:
                shifts = []
                for column_index in range(1, 16):
                    chain_code_header = f"chain_code_{column_index}"
                    if chain_code_header in column_offsets:
                        chain_code = row[column_offsets[chain_code_header]]
                    else:
                        chain_code = default_chain_code

                    sequence_code_header = f"sequence_code_{column_index}"
                    sequence_code = None
                    if sequence_code_header in column_offsets:
                        sequence_code = row[column_offsets[sequence_code_header]]

                    if not sequence_code:
                        continue

                    residue_name = extract_column_or_unused(
                        row, f"residue_name_{column_index}", column_offsets
                    )

                    atom_name = extract_column_or_unused(
                        row, f"atom_name_{column_index}", column_offsets
                    )

                    # TODO this is a required column note if its missing!
                    position = extract_column_or_unused(
                        row, f"position_{column_index}", column_offsets
                    )
                    exit_if_value_is_unused(
                        position, f"position_{column_index}", line_info
                    )
                    position = float(position)

                    position_uncertainty = extract_column_or_unused(
                        row, f"position_uncertainty_{column_index}", column_offsets
                    )
                    if position_uncertainty != UNUSED:
                        position_uncertainty = float(position_uncertainty)

                    sequence_residue = SequenceResidue(
                        chain_code, sequence_code, residue_name
                    )
                    atom_label = AtomLabel(sequence_residue, atom_name)
                    shift = ShiftData(atom_label, position, position_uncertainty)
                    shifts.append(shift)

                peak = NewPeak(shifts)
                peaks.append(peak)
    return peaks


def extract_column_or_unused(row, residue_name_header, column_offsets):
    if residue_name_header in column_offsets:
        residue_name = row[column_offsets[residue_name_header]]
    else:
        residue_name = UNUSED
    return residue_name


def exit_if_value_is_unused(value, header, line_info):
    name = header.rstrip(string.digits).rstrip("_")
    if value == UNUSED:
        msg = f"""\
            at line {line_info.line_no} in file {line_info.file_name} for column {header}
            all atom names in the peak must have a {name} [. is not permissible] i got {value}
            line was: {line_info.line}
            note: columns separators may not be the same as in your file
        """
        exit_error(msg)


def _exit_if_headers_dont_look_right(row: List[str], row_number, header_row, file_name):

    row_set = set(row)
    row_set -= {
        INDEX,
    }
    if not set(REQUIRED_HEADERS).issubset(set(row)):
        msg = f"""
            in the file {file_name} at the first row the headers for the file don't look right,
            as a minimum you should have

            {' '.join(REQUIRED_HEADERS)}

            the following were missing from the first row

            {' '.join(set(REQUIRED_HEADERS) - set(row))}

            which has the following headings

            {' '.join(row)}

        """
        exit_error(msg)

    remaining_headings = OrderedSet(row)
    remaining_headings -= {INDEX, PEAK_ID}

    for required_peak_info, required_shift_info in zip(
        chunks(ATOM_CODES, 4), POSITION_CODES
    ):

        if not set(required_peak_info).issubset(row_set) and not set(
            required_shift_info
        ).issubset(required_shift_info):
            remaining_headings -= set(required_peak_info)
            remaining_headings -= set(required_shift_info)
            msg = f"""
                in the file {file_name} at the first row not all of the headers that must be seen together are present
                it is expected that the following headers should be seen together

                {' '.join(required_peak_info)}

                and

                {' '.join(required_shift_info)}

                the remaining headings are



                {' '.join(remaining_headings)}

            """
            exit_error(msg)
        else:
            remaining_headings -= required_peak_info
            remaining_headings -= required_shift_info


def _exit_error_if_value_not_type(value, type, value_msg, row, row_number, file_name):
    TYPES = {int: (is_int, "integer"), float: (is_float, "float")}

    converter, type_name = TYPES[type]

    if not converter(value):
        msg = f"""\
            at line {row_number} in file {file_name} for the value {value}
            {value_msg}
            {', '.join(row)} [{COLUMN_SEPARATORS_MAY_HAVE_CHANGED}]
        """
        exit_error(msg)


def _get_csv_reader_for_format(csv_format, csv_fp, encoding):
    if csv_format == CsvLikeFormats.AUTO:
        dialect = csv.Sniffer().sniff(csv_fp.read(1024))
        csv_fp.seek(0)
        rdc_reader = csv.reader(csv_fp, dialect)
    elif csv_format == CsvLikeFormats.TSV:
        rdc_reader = csv.reader(csv_fp, delimiter="\t")
    elif csv_format == CsvLikeFormats.CSV:
        rdc_reader = csv.reader(csv_fp)
    else:
        lines = []
        for line in csv_fp:
            line = re.sub(r"\s+", "\t", line)
            lines.append(line.strip())
        lines = "\n".join(lines)
        csv_fp = TextIOWrapper(lines, encoding)
        rdc_reader = csv.reader(csv_fp, delimiter="\t")
    return rdc_reader


def _lookup_residue_name_or_exit(chain_code, sequence_code, lookup):
    residue_name = get_residue_name_from_lookup(chain_code, sequence_code, lookup)
    if residue_name == UNUSED:
        msg = f"""
                            There is no residue with chain {chain_code} and sequence code {sequence_code} in the input
                            sequence so I can't find a residue name for this residue
                        """
        raise BadSequenceException(msg)

    return residue_name


def _tabulate_sequence(entry: Entry) -> None:
    sequence = sequence_from_entry(entry)
    table = []
    for residue in sequence:
        row = [residue.chain_code, residue.sequence_code, residue.residue_name]
        table.append(row)

    if not table:
        result = "NO SEQUENCE..!"
    else:
        headers = "chain_code sequence_code residue_name".split()
        headers = [header.replace("_", " ") for header in headers]
        result = tabulate(table, headers=headers)

    return result
