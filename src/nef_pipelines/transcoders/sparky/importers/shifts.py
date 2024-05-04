from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import typer

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_entry_from_file_or_stdin_or_exit_error,
)
from nef_pipelines.lib.sequence_lib import (
    BadResidue,
    get_chain_code_iter,
    get_residue_name_from_lookup,
    sequence_from_entry_or_exit,
    sequence_to_residue_name_lookup,
    translate_1_to_3,
)
from nef_pipelines.lib.shift_lib import shifts_to_nef_frame
from nef_pipelines.lib.structures import (
    AtomLabel,
    LineInfo,
    SequenceResidue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.util import (
    STDIN,
    exit_error,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.sparky import import_app

SHIFT = "Shift"
ATOM = "Atom"
GROUP = "Group"
NUCLEUS = "Nuc"

EXPECTED_HEADINGS = set(f"{GROUP} {ATOM} {NUCLEUS} {SHIFT} SDev Assignments".split())


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: List[str] = typer.Option(
        None,
        "--chains",
        help="chain codes as a list of names separated by commas, repeated calls will add further chains [default A]",
        metavar="<CHAIN-CODES>",
    ),
    frame_name: str = typer.Option(
        "sparky", "-f", "--frame-name", help="a name for the frame"
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type shifts.txt", metavar="<SPARKY-shifts>.txt"
    ),
):
    """- convert sparky shift file <sparky-shifts>.txt to NEF"""

    chain_codes = parse_comma_separated_options(chain_codes)

    if not chain_codes:
        chain_codes = ["A"]
    elif len(chain_codes) == 1 and len(file_names) > 1:
        chain_codes = chain_codes * len(file_names)
    else:
        _exit_if_number_chain_codes_and_file_names_dont_match(chain_codes, file_names)

    entry = read_entry_from_file_or_stdin_or_exit_error(input)

    entry = pipe(entry, chain_codes, frame_name, file_names)

    print(entry)


def _exit_if_number_chain_codes_and_file_names_dont_match(chain_codes, file_names):
    if len(chain_codes) != len(file_names):
        msg = f"""\
            the number of chains [{len(chain_codes)}] doesn't match the number of files [{len(file_names)}]
            chains were {chain_codes}
            files were {file_names}
        """
        exit_error(msg)


def pipe(entry, chain_codes, frame_name, file_names):

    sequence = sequence_from_entry_or_exit(entry)

    sparky_frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name) as lines:

            chain_seqid_to_type = sequence_to_residue_name_lookup(sequence)

            sparky_shifts = _parse_shifts(
                lines, chain_seqid_to_type, chain_code=chain_code, file_name=file_name
            )

            frame = shifts_to_nef_frame(sparky_shifts, frame_name)

            sparky_frames.append(frame)

    return add_frames_to_entry(entry, sparky_frames)


def _convert_residue_type_to_3_let_or_exit(residue_type, line_info):
    try:
        residue_type = translate_1_to_3([residue_type])[0]
    except BadResidue:
        msg = f"""\
            unknown residue name {residue_type}
            at line {line_info.line_no} in
            file {line_info.file_name}, the line had the following content
            {line_info.line}
        """
        exit_error(msg)

    return residue_type


def _exit_if_residue_doesnt_equal_sequence(residue, chain_seqid_to_type, line_info):

    chain_code = residue.chain_code
    sequence_code = residue.sequence_code
    sequence_residue_name = get_residue_name_from_lookup(
        chain_code, sequence_code, chain_seqid_to_type
    )
    if sequence_residue_name.lower() != residue.residue_name.lower():
        msg = f"""\
            for residue number {sequence_code} in chain {chain_code} the residue type read from file
            {residue.residue_name} doesn't match the one from the sequence {sequence_residue_name}
            while reading line {line_info.line_no} from file:
            {line_info.file_name}
            the value of the line was
            {line_info.line}
        """
        exit_error(msg)


def _parse_shifts(
    lines: Iterable[str],
    chain_seqid_to_type: Dict[Tuple[str, int], str],
    chain_code: str = "A",
    file_name="unknown",
) -> ShiftList:

    heading_indices = {}

    read_shifts = []
    for i, line in enumerate(lines):
        line_info = LineInfo(file_name, i + 1, line)
        line = line.strip()

        if i == 0:
            headings = line.split()

            _exit_if_bad_header(headings, EXPECTED_HEADINGS, line_info)

            heading_indices = {
                heading: column for column, heading in enumerate(headings)
            }

        elif not line:
            continue
        else:
            shift = _parse_shifts_line(
                line_info, heading_indices, chain_code, chain_seqid_to_type
            )

            read_shifts.append(shift)

    return ShiftList(read_shifts)


def _parse_shifts_line(line_info, heading_indices, chain_code, chain_seqid_to_type):
    fields = line_info.line.split()

    _exit_if_wrong_number_data_columns(fields, heading_indices, line_info)

    fields = {heading: fields[column] for heading, column in heading_indices.items()}

    group = fields[GROUP]
    atom = fields[ATOM]
    shift = float(fields[SHIFT])
    nucleus = fields[NUCLEUS]

    residue_type = _read_residue_name_from_group_or_exit(group, line_info)

    sequence_code = read_residue_number_from_group_or_exit(
        group, residue_type, line_info
    )

    residue_type = _convert_residue_type_to_3_let_or_exit(residue_type, line_info)

    residue = SequenceResidue(chain_code, sequence_code, residue_type)

    _exit_if_residue_doesnt_equal_sequence(residue, chain_seqid_to_type, line_info)

    element, isotope_number = _parse_element_and_isotope_number(nucleus)

    atom_label = AtomLabel(
        residue, atom, element=element, isotope_number=isotope_number
    )

    shift = ShiftData(atom_label, shift)
    return shift


def _exit_if_wrong_number_data_columns(fields, headings, line_info):
    num_fields = len(fields)
    num_headings = len(headings)
    if num_fields < num_headings:
        msg = f"""\
                    at line {line_info.line_no} in
                    file {line_info.file_name}
                    there weren't enough columns of data i expected {num_headings} but got {num_fields}
                    so the number of fields matched the length of the headings.
                    the headings were {headings}
                    the line was {line_info.line}
                """
        exit_error(msg)


def _exit_if_bad_header(headings, EXPECTED_HEADINGS, line_info):
    if not set(headings).issubset(EXPECTED_HEADINGS):
        msg = f"""\
                    the file {line_info.file_name} doesn't look like a sparky file"
                    line 1 should contain the the standard sparky headings:
                    {', '.join(EXPECTED_HEADINGS)}
                    i got:
                    {line_info.line}
                """
        exit_error(msg)


def read_residue_number_from_group_or_exit(group, residue_type, line_info):

    residue_number = group[len(residue_type) :]
    if not is_int(residue_number):
        msg = f"""\
            bad sequence code  {residue_number}  [should be an integer for a spark residue number]
            at line {line_info.line_no} in
            file {line_info.file_name}, the line had the following content
            {line_info.line}
        """
        exit_error(msg)

    return int(residue_number)


def _read_residue_name_from_group_or_exit(group: str, line_info: LineInfo):

    residue_type = _get_starting_alpha(group)

    if not residue_type:
        msg = f"""\
            there was no residue type for the residues specificed on line {line_info.line_no} of
            file {line_info.file_name} the line was
            {line_info.line}
        """
        exit_error(msg)

    return residue_type


def _get_starting_alpha(group):
    result = []
    for char in group:
        if char.isalpha():
            result.append(char)
        else:
            break
    return "".join(result)


def get_starting_number(group):
    result = []
    for char in group:
        if char.isdigit():
            result.append(char)
        else:
            break
    return "".join(result)


def _parse_element_and_isotope_number(nucleus):
    isotope_number = get_starting_number(nucleus)
    if not isotope_number:
        isotope_number = UNUSED

    if not isotope_number == UNUSED:
        element = nucleus[len(isotope_number) :]

    if not element:
        isotope_number = UNUSED

    return element, isotope_number
