import csv
import re
from enum import auto
from io import TextIOWrapper
from pathlib import Path
from textwrap import dedent
from typing import List, Tuple

import typer
from pynmrstar import Entry, Loop, Saveframe
from strenum import StrEnum
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    get_residue_name_from_lookup,
    sequence_from_entry,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
)
from nef_pipelines.lib.structures import AtomLabel, RdcRestraint, SequenceResidue
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
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


COLUMN_SEPARATORS_MAY_HAVE_CHANGED = (
    "note: column separators shown here may different to those in the original file..."
)
DEFAULT_ATOMS_HELP = (
    "the atoms to use if atoms aren't defined in the file, there should be two. "
    "This option can be used mutiple twice to define the atoms or you can use a "
    "comma separated list"
)


class BadSequenceException(Exception):
    pass


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
    default_atoms = parse_comma_separated_options(default_atoms)

    if not default_atoms:
        default_atoms = ("H", "N")

    csv_format = csv_format.upper()

    entry = read_entry_from_file_or_stdin_or_exit_error(entry_input)

    try:
        pipe(
            entry,
            default_chain_code,
            default_atoms,
            csv_file,
            csv_file_encoding,
            csv_format,
        )
    except BadSequenceException as e:

        sequence_table = _tabulate_sequence(entry) if verbose else None
        _exit_bad_sequence(e, entry_input, sequence_table)

    print(entry)


def pipe(
    entry: Entry,
    chain_code: str,
    atoms: Tuple[str, str],
    csv_file: Path,
    csv_file_encoding: str,
    csv_format: CsvLikeFormats,
) -> Entry:

    sequence = sequence_from_entry_or_exit(entry)

    lookup = sequence_to_residue_name_lookup(sequence)

    encoding = {"encoding": csv_file_encoding}
    file_rdcs = _parse_csv(
        csv_file, encoding, chain_code, atoms, lookup, csv_file, csv_format
    )

    frame = _rdcs_to_frame(file_rdcs)

    add_frames_to_entry(entry, [frame])

    return entry


# noinspection PyUnusedLocal
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


def _parse_csv(
    csv_file, encoding, default_chain_code, atoms, lookup, file_name, csv_format
):
    column_offsets = {}
    headers = [
        CHAIN_CODE,
        *REQUIRED_HEADERS_SHORT,
        *REQUIRED_HEADERS_LONG,
        VALUE_UNCERTAINTY,
    ]
    data = []
    weight = 1.0
    with open(csv_file, **encoding) as csv_fp:

        rdc_reader = _get_csv_reader_for_format(csv_format, csv_fp, encoding)

        for i, row in enumerate(rdc_reader):

            if i == 0:
                header_row = [elem.lower() for elem in row]

                _exit_if_headers_dont_look_right(row, i + 1, header_row, file_name)

                for header in headers:
                    if header in header_row:
                        column_offsets[header] = header_row.index(header)

            else:

                if CHAIN_CODE_1 in column_offsets and CHAIN_CODE_2 in column_offsets:
                    chain_code_1 = row[column_offsets[CHAIN_CODE_1]]
                    chain_code_2 = row[column_offsets[CHAIN_CODE_2]]
                else:
                    chain_code_1 = default_chain_code
                    chain_code_2 = default_chain_code

                if (
                    SEQUENCE_CODE_1 in column_offsets
                    and SEQUENCE_CODE_2 in column_offsets
                ):
                    sequence_code_1 = row[column_offsets[SEQUENCE_CODE_1]]
                    sequence_code_2 = row[column_offsets[SEQUENCE_CODE_2]]
                else:
                    sequence_code_1 = row[column_offsets[SEQUENCE_CODE]]
                    sequence_code_2 = row[column_offsets[SEQUENCE_CODE]]

                if SEQUENCE_CODE in column_offsets:
                    msg = f"for this converter to work the {SEQUENCE_CODE} must be an integer"
                else:
                    msg = "for this converter to work the the sequence codes must be integers"

                msg_1 = msg + f", {SEQUENCE_CODE_1} wasn't"
                msg_2 = msg + f", {SEQUENCE_CODE_2} wasn't"
                _exit_error_if_value_not_type(
                    sequence_code_1, int, msg_1, row, i + 1, file_name
                )
                _exit_error_if_value_not_type(
                    sequence_code_2, int, msg_2, row, i + 1, file_name
                )

                sequence_code_1 = int(sequence_code_1)
                sequence_code_2 = int(sequence_code_2)

                value = row[column_offsets[VALUE]]
                if not is_float(value):
                    msg = f"{VALUE}s must be floats but the input wasn't"
                    _exit_error_if_value_not_type(
                        value, float, msg, row, i + 1, file_name
                    )
                value = float(value)

                if VALUE_UNCERTAINTY in column_offsets:
                    value_uncertainty = row[column_offsets[VALUE_UNCERTAINTY]]
                    if not is_float(value_uncertainty):
                        msg = (
                            f"{VALUE_UNCERTAINTY} smust be floats but the input wasn't"
                        )
                        _exit_error_if_value_not_type(
                            value_uncertainty, float, msg, row, i + 1, file_name
                        )
                    value_uncertainty = float(value_uncertainty)
                else:
                    value_uncertainty = UNUSED

                residue_name_1 = _lookup_residue_name_or_exit(
                    chain_code_1, sequence_code_1, lookup
                )
                residue_name_2 = _lookup_residue_name_or_exit(
                    chain_code_2, sequence_code_2, lookup
                )

                residue_1 = SequenceResidue(
                    chain_code_1, sequence_code_1, residue_name_1
                )
                residue_2 = SequenceResidue(
                    chain_code_2, sequence_code_2, residue_name_2
                )

                if ATOM_1 in column_offsets and ATOM_2 in column_offsets:
                    atom_1 = AtomLabel(residue_1, row[column_offsets[ATOM_1]])
                    atom_2 = AtomLabel(residue_2, row[column_offsets[ATOM_2]])
                else:
                    atom_1 = AtomLabel(residue_1, atoms[0])
                    atom_2 = AtomLabel(residue_2, atoms[1])

                rdc = RdcRestraint(
                    atom_1, atom_2, value, value_uncertainty, weight=weight
                )

                data.append(rdc)

    return data


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
            exit_error(msg)
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
        exit_error(msg)


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
