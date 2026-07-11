from pathlib import Path
from textwrap import dedent
from typing import List, Tuple

import typer
from pynmrstar import Entry, Loop, Saveframe

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
    unknown_residues_to_warning,
)
from nef_pipelines.lib.structures import (
    AtomLabel,
    PipeOutput,
    RdcRestraint,
    SequenceResidue,
)
from nef_pipelines.lib.tabular_data_lib import (
    COLUMN_SEPARATORS_MAY_HAVE_CHANGED,
    ENCODING,
    HELP_FOR_FORMATS,
    CsvLikeFormats,
    CsvParseError,
    _parse_csv_rows_from_text,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_float,
    is_int,
    parse_comma_separated_options,
    warn,
)
from nef_pipelines.transcoders.csv import import_app

app = typer.Typer()


def _validate_type(value, expected_type, error_msg, row, row_number, file_name):
    """Validate value can be converted to expected type, raise CsvParseError if not."""
    validators = {int: is_int, float: is_float}
    type_names = {int: "integer", float: "float"}

    validator = validators[expected_type]
    type_name = type_names[expected_type]

    if not validator(value):
        msg = f"""\
            invalid type {type_name} at line {row_number} in file {file_name} for the value {value}
            {error_msg}
            {', '.join(row)} [{COLUMN_SEPARATORS_MAY_HAVE_CHANGED}]
        """
        raise CsvParseError(msg)


HELP_FOR_FRAME_NAME = "name for the frame, note white spaces will be replace by _"

CHAIN_CODE = "chain_code"
SEQUENCE_CODE = "sequence_code"
ATOM = "atom"
VALUE = "value"
VALUE_UNCERTAINTY = "value_uncertainty"

CHAIN_CODE_1 = f"{CHAIN_CODE}_1"
CHAIN_CODE_2 = f"{CHAIN_CODE}_2"
CHAINS_1_2 = f"{CHAIN_CODE_1} {CHAIN_CODE_2}"
SEQUENCE_CODE_1 = f"{SEQUENCE_CODE}_1"
SEQUENCE_CODE_2 = f"{SEQUENCE_CODE}_2"
SEQUENCE_CODE_1_2 = f"{SEQUENCE_CODE_1} {SEQUENCE_CODE_2}"
ATOM_1 = f"{ATOM}_1"
ATOM_2 = f"{ATOM}_2"
ATOMS_1_2 = f"{ATOM_1} {ATOM_2}"

REQUIRED_HEADERS_SHORT = f"{SEQUENCE_CODE} {VALUE}".split()
REQUIRED_HEADERS_LONG = f"{CHAINS_1_2} {SEQUENCE_CODE_1_2} {ATOMS_1_2} {VALUE}".split()


DEFAULT_ATOMS_HELP = (
    "the atoms to use if atoms aren't defined in the file, there should be two. "
    "This option can be used mutiple twice to define the atoms or you can use a "
    "comma separated list"
)


@import_app.command(no_args_is_help=True)
def rdcs(
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
    verbose: bool = typer.Option(False, help="report verbose information"),
    default_atoms: List[str] = typer.Option(
        [], "-a", "--atoms", help=DEFAULT_ATOMS_HELP
    ),
    default_chain_code: str = typer.Option(
        "A",
        "-c",
        "--chain-code",
        help="default chain code to use if none is provided in the file",
    ),
    csv_file: Path = typer.Argument(None, metavar="<CSV-FILE>"),
):
    """- import RDC restraints from one or more CSV files into NEF RDC restraint list frames"""
    default_atoms = parse_comma_separated_options(default_atoms)

    if not default_atoms:
        default_atoms = ("H", "N")

    csv_format = csv_format.upper()

    entry = read_entry_from_file_or_stdin_or_exit_error(entry_input)

    try:
        result = pipe(
            entry,
            default_chain_code,
            default_atoms,
            csv_file,
            csv_file_encoding,
            csv_format,
        )

    except CsvParseError as e:
        exit_error(str(e))

    for warning in result.warnings:
        warn(warning)

    print(result.entry)


def pipe(
    entry: Entry,
    chain_code: str,
    atoms: Tuple[str, str],
    csv_file: Path,
    csv_file_encoding: str,
    csv_format: CsvLikeFormats,
) -> PipeOutput:
    """Import RDC restraints from CSV file into NEF entry.

    Args:
        entry: NEF entry to add RDC restraints to
        chain_code: Default chain code if not specified in CSV
        atoms: Tuple of two atom names for the RDC pair
        csv_file: Path to CSV file
        csv_file_encoding: Character encoding of the CSV file
        csv_format: CSV format (CSV, TSV, SSV, or AUTO)

    Returns:
        PipeOutput with modified entry and any warnings about unknown residues
    """
    sequence = sequence_from_entry_or_exit(entry)

    lookup = sequence_to_residue_name_lookup(sequence)

    encoding = {"encoding": csv_file_encoding}
    file_rdcs, warnings = _parse_csv(
        csv_file, encoding, chain_code, atoms, lookup, csv_file, csv_format
    )

    frame = _rdcs_to_frame(file_rdcs)

    add_frames_to_entry(entry, [frame])

    return PipeOutput(entry=entry, warnings=warnings)


def _rdcs_to_frame(rdcs: List[RdcRestraint], frame_code="rdcs"):
    RDC_FRAME_CATEGORY = "nef_rdc_restraint_list"
    RDC_LOOP_CATEGORY = "nef_rdc_restraint"

    frame_code = f"{RDC_FRAME_CATEGORY}_{frame_code}"

    frame = Saveframe.from_scratch(frame_code, RDC_FRAME_CATEGORY)

    frame_tags = (
        "restraint_origin",
        "tensor_magnitude",
        "tensor_rhombicity",
        "tensor_chain_code",
        "tensor_sequence_code",
        "tensor_residue_name",
    )

    frame.add_tag("sf_category", RDC_FRAME_CATEGORY)
    frame.add_tag("sf_framecode", frame_code)

    for tag in frame_tags:
        frame.add_tag(tag, ".")

    loop = Loop.from_scratch()
    frame.add_loop(loop)

    loop_tags = (
        "index",
        "restraint_id",
        "restraint_combination_id",
        "chain_code_1",
        "sequence_code_1",
        "residue_name_1",
        "atom_name_1",
        "chain_code_2",
        "sequence_code_2",
        "residue_name_2",
        "atom_name_2",
        "weight",
        "target_value",
        "target_value_uncertainty",
        "lower_linear_limit",
        "lower_limit",
        "upper_limit",
        "upper_linear_limit",
        "scale",
        "distance_dependent",
    )

    loop.set_category(RDC_LOOP_CATEGORY)
    loop.add_tag(loop_tags)

    for index, rdc in enumerate(rdcs):
        data = {
            "index": index,
            "restraint_id": index,
            "chain_code_1": rdc.atom_1.residue.chain_code,
            "sequence_code_1": rdc.atom_1.residue.sequence_code,
            "residue_name_1": rdc.atom_1.residue.residue_name,
            "atom_name_1": rdc.atom_1.atom_name,
            "chain_code_2": rdc.atom_2.residue.chain_code,
            "sequence_code_2": rdc.atom_2.residue.sequence_code,
            "residue_name_2": rdc.atom_2.residue.residue_name,
            "atom_name_2": rdc.atom_2.atom_name,
            "weight": 1.0,
            "target_value": rdc.value,
            "target_value_uncertainty": rdc.value_uncertainty,
            "scale": 1.0,
        }
        loop.add_data([data])

    return frame


def _process_header_row(row, row_number, file_name):
    """Process header row and return column offsets dict."""
    header_row = [elem.lower().replace(" ", "_") for elem in row]
    _exit_if_headers_dont_look_right(row, row_number, header_row, file_name)

    headers = [
        CHAIN_CODE,
        *REQUIRED_HEADERS_SHORT,
        *REQUIRED_HEADERS_LONG,
        VALUE_UNCERTAINTY,
    ]

    column_offsets = {}
    for header in headers:
        if header in header_row:
            column_offsets[header] = header_row.index(header)

    return column_offsets


def _extract_chain_codes(row, column_offsets, default_chain_code):
    """Extract chain codes from row, using defaults if not in file."""
    if CHAIN_CODE_1 in column_offsets and CHAIN_CODE_2 in column_offsets:
        chain_code_1 = row[column_offsets[CHAIN_CODE_1]]
        chain_code_2 = row[column_offsets[CHAIN_CODE_2]]
    else:
        chain_code_1 = default_chain_code
        chain_code_2 = default_chain_code

    return chain_code_1, chain_code_2


def _extract_and_validate_sequence_codes(row, column_offsets, row_number, file_name):
    """Extract and validate sequence codes are integers."""
    if SEQUENCE_CODE_1 in column_offsets and SEQUENCE_CODE_2 in column_offsets:
        sequence_code_1 = row[column_offsets[SEQUENCE_CODE_1]]
        sequence_code_2 = row[column_offsets[SEQUENCE_CODE_2]]
    else:
        sequence_code_1 = row[column_offsets[SEQUENCE_CODE]]
        sequence_code_2 = row[column_offsets[SEQUENCE_CODE]]

    if SEQUENCE_CODE in column_offsets:
        base_msg = f"for this converter to work the {SEQUENCE_CODE} must be an integer"
    else:
        base_msg = "for this converter to work the the sequence codes must be integers"

    _validate_type(
        sequence_code_1,
        int,
        base_msg + f", {SEQUENCE_CODE_1} wasn't",
        row,
        row_number,
        file_name,
    )
    _validate_type(
        sequence_code_2,
        int,
        base_msg + f", {SEQUENCE_CODE_2} wasn't",
        row,
        row_number,
        file_name,
    )

    return int(sequence_code_1), int(sequence_code_2)


def _extract_and_validate_values(row, column_offsets, row_number, file_name):
    """Extract and validate RDC value and optional uncertainty."""
    value = row[column_offsets[VALUE]]
    _validate_type(
        value,
        float,
        f"{VALUE}s must be floats but the input wasn't",
        row,
        row_number,
        file_name,
    )
    value = float(value)

    if VALUE_UNCERTAINTY in column_offsets:
        value_uncertainty = row[column_offsets[VALUE_UNCERTAINTY]]
        _validate_type(
            value_uncertainty,
            float,
            f"{VALUE_UNCERTAINTY} must be floats but the input wasn't",
            row,
            row_number,
            file_name,
        )
        value_uncertainty = float(value_uncertainty)
    else:
        value_uncertainty = UNUSED

    return value, value_uncertainty


def _build_rdc_from_row(
    chain_code_1,
    chain_code_2,
    sequence_code_1,
    sequence_code_2,
    residue_name_1,
    residue_name_2,
    row,
    column_offsets,
    atoms,
    value,
    value_uncertainty,
    weight,
):
    """Build RDC restraint from validated row data."""
    residue_1 = SequenceResidue(chain_code_1, sequence_code_1, residue_name_1)
    residue_2 = SequenceResidue(chain_code_2, sequence_code_2, residue_name_2)

    if ATOM_1 in column_offsets and ATOM_2 in column_offsets:
        atom_1 = AtomLabel(residue_1, row[column_offsets[ATOM_1]])
        atom_2 = AtomLabel(residue_2, row[column_offsets[ATOM_2]])
    else:
        atom_1 = AtomLabel(residue_1, atoms[0])
        atom_2 = AtomLabel(residue_2, atoms[1])

    return RdcRestraint(atom_1, atom_2, value, value_uncertainty, weight=weight)


def _parse_csv(
    csv_file, encoding, default_chain_code, atoms, lookup, file_name, csv_format
):
    """Parse CSV file and extract RDC restraints.

    Returns:
        Tuple of (rdc_list, warnings_list)
    """
    data = []
    unknown_residues = set()
    weight = 1.0
    column_offsets = None

    # Read file and parse as text
    text = csv_file.read_text(encoding=ENCODING)
    rows = _parse_csv_rows_from_text(text, csv_format)

    for i, row in enumerate(rows):
        if i == 0:
            column_offsets = _process_header_row(row, i + 1, file_name)
        else:
            # Extract and validate row data
            chain_code_1, chain_code_2 = _extract_chain_codes(
                row, column_offsets, default_chain_code
            )
            sequence_code_1, sequence_code_2 = _extract_and_validate_sequence_codes(
                row, column_offsets, i + 1, file_name
            )
            value, value_uncertainty = _extract_and_validate_values(
                row, column_offsets, i + 1, file_name
            )

            # Lookup residue names, track unknown residues
            residue_name_1 = get_residue_name_from_lookup(
                chain_code_1, sequence_code_1, lookup
            )
            if residue_name_1 == UNUSED:
                unknown_residues.add((chain_code_1, sequence_code_1))

            residue_name_2 = get_residue_name_from_lookup(
                chain_code_2, sequence_code_2, lookup
            )
            if residue_name_2 == UNUSED:
                unknown_residues.add((chain_code_2, sequence_code_2))

            # Build RDC restraint
            rdc = _build_rdc_from_row(
                chain_code_1,
                chain_code_2,
                sequence_code_1,
                sequence_code_2,
                residue_name_1,
                residue_name_2,
                row,
                column_offsets,
                atoms,
                value,
                value_uncertainty,
                weight,
            )
            data.append(rdc)

    warning = unknown_residues_to_warning(unknown_residues, lookup)
    warnings = [warning] if warning else []
    return data, warnings


def _exit_if_headers_dont_look_right(row: List[str], row_number, header_row, file_name):

    if "value_uncertainty" in row:
        row = list(row)
        row.remove("value_uncertainty")

    ok = False
    if len(row) == len(REQUIRED_HEADERS_SHORT):
        if len(header_row) < len(REQUIRED_HEADERS_SHORT) and len(
            set(header_row).intersection(set(REQUIRED_HEADERS_SHORT))
        ) != len(REQUIRED_HEADERS_SHORT):
            msg = f"""\
                the column headers don't look right they should include {', '.join(REQUIRED_HEADERS_SHORT)}
                i have {', '.join(header_row)} at line {row_number} value of line was
                {', '.join(row)} [{COLUMN_SEPARATORS_MAY_HAVE_CHANGED}]
                in file {file_name}
            """
            msg = dedent(msg)
            raise CsvParseError(msg)
        else:
            ok = True

    if (
        not ok
        and len(row) == len(REQUIRED_HEADERS_LONG)
        and len(set(header_row).intersection(set(REQUIRED_HEADERS_LONG)))
        != len(REQUIRED_HEADERS_LONG)
    ):
        msg = f"""\
            the column headers don't look right they should include {', '.join(REQUIRED_HEADERS_LONG)}
            i have {', '.join(header_row)} at line {row_number} value of line was
            {', '.join(row)} [{COLUMN_SEPARATORS_MAY_HAVE_CHANGED}]
            in file {file_name}
        """
        msg = dedent(msg)

        raise CsvParseError(msg)
