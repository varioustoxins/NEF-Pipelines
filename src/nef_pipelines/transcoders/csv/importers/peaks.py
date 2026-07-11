import string
from pathlib import Path
from textwrap import dedent
from typing import Dict, List

import typer
from ordered_set import OrderedSet
from pynmrstar import Entry

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
    sequence_to_residue_name_lookup,
    unknown_residues_to_warning,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    NewPeak,
    PipeOutput,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.tabular_data_lib import (
    ENCODING,
    HELP_FOR_FORMATS,
    CsvLikeFormats,
    CsvParseError,
    _parse_csv_rows_from_text,
)
from nef_pipelines.lib.util import (
    STDIN,
    chunks,
    exit_error,
    flatten,
    parse_comma_separated_options,
    warn,
)
from nef_pipelines.transcoders.csv import import_app

app = typer.Typer()

HELP_FOR_FRAME_NAME = "name for the frame, note white spaces will be replace by _"

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

DEFAULT_ATOMS_HELP = (
    "the atoms to use if atoms names aren't defined in the file "
    "This option can be used multiple twice to define the atoms or you can use a "
    "comma separated list"
)

DEFAULT_NUCLEI_HELP = (
    "nuclei to use for each dimension if not defined they are guessed from the assignments"
    "or an error is reported"
)


class CSVPeakListException(Exception):
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
    """- import peak lists from one or more CSV files into NEF spectrum frames"""
    default_atoms = parse_comma_separated_options(default_atoms)

    csv_format = csv_format.upper()

    entry = read_or_create_entry_exit_error_on_bad_file(entry_input)

    try:
        result = pipe(
            entry,
            default_chain_code,
            default_atoms,
            csv_file,
            csv_file_encoding,
            csv_format,
            dimension_nuclei,
            spectrometer_frequency,
        )

    except (CsvParseError, IncompatibleDimensionTypesException) as e:
        exit_error(str(e))

    for warning in result.warnings:
        warn(warning)

    print(result.entry)


def pipe(
    entry: Entry,
    chain_code: str,
    atoms: List[str],
    csv_file: Path,
    csv_file_encoding: str,
    csv_format: CsvLikeFormats,
    input_dimensions: List[str],
    spectrometer_frequency,
) -> PipeOutput:
    """Import peak lists from CSV into NEF entry.

    Returns:
        PipeOutput with modified entry and any warnings about unknown residues
    """
    # Get sequence if available (used to look up missing residue names)

    try:
        sequence = sequence_from_entry(entry)
        lookup = sequence_to_residue_name_lookup(sequence)
    except Exception:
        lookup = {}

    encoding = {"encoding": csv_file_encoding}

    file_shifts, warnings = _parse_csv(
        csv_file, encoding, chain_code, atoms, csv_file, csv_format, lookup
    )

    dimensions = _guess_dimensions_if_not_defined_or_throw(
        file_shifts, input_dimensions
    )

    dimensions = [{"axis_code": dimension} for dimension in dimensions]

    frame = peaks_to_frame(file_shifts, dimensions, spectrometer_frequency)

    add_frames_to_entry(entry, [frame])

    return PipeOutput(entry=entry, warnings=warnings)


def _guess_isotopes_from_peaks(peaks: List[NewPeak]) -> Dict[int, set]:
    """Analyze peaks to guess isotope codes for each dimension from atom types."""
    guessed_dimensions = {}

    for peak in peaks:
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

    return guessed_dimensions


def _validate_and_fill_dimensions(
    guessed_dimensions: Dict[int, set], results_by_dimension: Dict[int, str]
):
    """Validate guessed dimensions and fill in results, raise if ambiguous."""
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


def _build_dimension_list(results_by_dimension: Dict[int, str]) -> List[str]:
    """Build ordered list of dimensions from results dictionary."""
    max_dimension = max(results_by_dimension.keys())
    return [results_by_dimension[i] for i in range(max_dimension + 1)]


def _guess_dimensions_if_not_defined_or_throw(
    peaks: List[NewPeak], input_dimensions: List[str]
) -> List[str]:
    """Guess dimension isotopes from peak data if not explicitly provided."""
    results_by_dimension = {
        i: dimension for i, dimension in enumerate(input_dimensions)
    }

    guessed_dimensions = _guess_isotopes_from_peaks(peaks)
    _validate_and_fill_dimensions(guessed_dimensions, results_by_dimension)
    return _build_dimension_list(results_by_dimension)


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


def _process_header_row(row: List[str], file_name: str) -> Dict[str, int]:
    """Process header row and return column_offsets mapping."""
    header_row = [elem.lower().replace(" ", "_") for elem in row]
    _exit_if_headers_dont_look_right(row, 1, header_row, file_name)

    headers = [*BASIC_HEADERS, *OPTIONAL_HEADERS]
    column_offsets = {}
    for header in headers:
        if header in header_row:
            column_offsets[header] = header_row.index(header)

    return column_offsets


def _extract_shift_from_row(
    row: List[str],
    column_index: int,
    column_offsets: Dict[str, int],
    default_chain_code: str,
    lookup: Dict,
    unknown_residues: set,
    line_info: LineInfo,
):
    """Extract shift data for a single dimension from a row.

    Returns:
        ShiftData object or None if dimension has no data
    """
    sequence_code_header = f"sequence_code_{column_index}"
    sequence_code = None
    if sequence_code_header in column_offsets:
        sequence_code = row[column_offsets[sequence_code_header]]

    if not sequence_code:
        shift = None
    else:
        chain_code_header = f"chain_code_{column_index}"
        if chain_code_header in column_offsets:
            chain_code = row[column_offsets[chain_code_header]]
        else:
            chain_code = default_chain_code

        residue_name = extract_column_or_unused(
            row, f"residue_name_{column_index}", column_offsets
        )

        # Look up residue name from sequence if not provided in CSV
        if residue_name == UNUSED or not residue_name:
            residue_name = get_residue_name_from_lookup(
                chain_code, sequence_code, lookup
            )
            if residue_name == UNUSED:
                # sequence_code is a string from CSV, convert to int for set
                unknown_residues.add((chain_code, int(sequence_code)))

        atom_name = extract_column_or_unused(
            row, f"atom_name_{column_index}", column_offsets
        )

        position = extract_column_or_unused(
            row, f"position_{column_index}", column_offsets
        )
        _validate_required_column(position, f"position_{column_index}", line_info)
        position = float(position)

        position_uncertainty = extract_column_or_unused(
            row, f"position_uncertainty_{column_index}", column_offsets
        )
        if position_uncertainty != UNUSED:
            position_uncertainty = float(position_uncertainty)

        sequence_residue = SequenceResidue(chain_code, sequence_code, residue_name)
        atom_label = AtomLabel(sequence_residue, atom_name)
        shift = ShiftData(atom_label, position, position_uncertainty)

    return shift


def _parse_csv(
    csv_file: Path,
    encoding: Dict[str, str],
    default_chain_code: str,
    atoms: List[str],
    file_name: str,
    csv_format: str,
    lookup: Dict,
):
    """Parse CSV file and return peaks with warnings for unknown residues.

    Returns:
        Tuple of (peaks, warnings) where warnings is a list of warning strings
    """
    peaks = []
    unknown_residues = set()
    column_offsets = {}

    # Read file and parse as text
    text = csv_file.read_text(encoding=ENCODING)
    rows = _parse_csv_rows_from_text(text, csv_format)

    for i, row in enumerate(rows):
        row = [elem.strip() for elem in row]
        line_info = LineInfo(file_name, i + 1, ", ".join(row))

        if i == 0:
            column_offsets = _process_header_row(row, file_name)
        else:
            shifts = []
            for column_index in range(1, 16):
                shift = _extract_shift_from_row(
                    row,
                    column_index,
                    column_offsets,
                    default_chain_code,
                    lookup,
                    unknown_residues,
                    line_info,
                )
                if shift:
                    shifts.append(shift)

            peak = NewPeak(shifts)
            peaks.append(peak)

    warning = unknown_residues_to_warning(unknown_residues, lookup)
    warnings = [warning] if warning else []
    return peaks, warnings


def extract_column_or_unused(row, residue_name_header, column_offsets):
    if residue_name_header in column_offsets:
        residue_name = row[column_offsets[residue_name_header]]
    else:
        residue_name = UNUSED
    return residue_name


def _validate_required_column(value, header, line_info):
    """Validate that required column has a value, raise CsvParseError if missing."""
    name = header.rstrip(string.digits).rstrip("_")
    if value == UNUSED:
        msg = f"""\
            at line {line_info.line_no} in file {line_info.file_name} for column {header}
            all peaks must have a {name} [. is not permissible] i got {value}
            line was: {line_info.line}
            note: columns separatorsshown here may not be the same as in your file
        """
        msg = dedent(msg)
        raise CsvParseError(msg)


def _validate_required_headers(row: List[str], file_name: str):
    """Validate minimum required headers are present."""
    if not set(REQUIRED_HEADERS).issubset(set(row)):
        missing = set(REQUIRED_HEADERS) - set(row)
        msg = f"""\
            in the file {file_name} at the first row the headers for the file don't look right,
            as a minimum you should have

            {' '.join(REQUIRED_HEADERS)}

            the following were missing from the first row

            {' '.join(missing)}

            which has the following headings

            {' '.join(row)}
        """
        msg = dedent(msg)
        raise CsvParseError(msg)


def _validate_grouped_headers(row: List[str], row_set: set, file_name: str):
    """Validate that grouped headers (peak_info and shift_info) appear together."""
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
            msg = f"""\
                in the file {file_name} at the first row not all of the headers that must be seen together are present
                it is expected that the following headers should be seen together

                {' '.join(required_peak_info)}

                and

                {' '.join(required_shift_info)}

                the remaining headings are

                {' '.join(remaining_headings)}
            """
            msg = dedent(msg)
            raise CsvParseError(msg)
        else:
            remaining_headings -= required_peak_info
            remaining_headings -= required_shift_info


def _exit_if_headers_dont_look_right(row: List[str], row_number, header_row, file_name):
    """Validate CSV headers, raise CsvParseError if invalid."""
    _validate_required_headers(row, file_name)

    row_set = set(row)
    row_set -= {INDEX}
    _validate_grouped_headers(row, row_set, file_name)
