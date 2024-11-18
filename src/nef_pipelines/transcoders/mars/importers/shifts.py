import sys
from pathlib import Path
from typing import Iterable, List

# TODO: better support for assigned residues, improved handling of chains
import typer

from nef_pipelines.lib.nef_lib import (
    UNUSED,
    add_frames_to_entry,
    read_or_create_entry_exit_error_on_bad_file,
)
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_3_1_PROTEIN,
    BadResidue,
    get_chain_code_iter,
    get_residue_name_from_lookup,
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
    is_float,
    is_int,
    parse_comma_separated_options,
)
from nef_pipelines.transcoders.mars import import_app

DEFAULT_PSEUDO_RESIDUE_PREFIX = "PR_"
SEPARATORS = "_-"

PSEUDO_RESIDUE = "PSEUDO_RESIDUE"

H = "H"
N = "N"
HA = "HA"
CA = "CA"
CB = "CB"
C = "CO"

EXPECTED_HEADINGS = {H, N, HA, CA, f"{CA}-1", CB, f"{CB}-1", C, f"{C}-1", f"{HA}-1"}

MARS_UNDEFINED = "-"
app = typer.Typer()

PSEUDO_RESIDUE_FORMAT = "<OPTIONAL-TEXT><NUMBER><OPTIONAL-TEXT>"

# TODO: maybe we want to add some of this to comments...
RECOGNISE_RESIDUES_HELP = f"""\
    if the second string in a pseudo residue name looks like contains a a 3 letter residue parse it and add it to the
    NEF shift pseudo residue names can be of the form  {PSEUDO_RESIDUE_FORMAT}, examples:
    include

    1
    PR_4?
    PR_5GLY
    PR_5GLY?

    in the third case if this flag is set the residue is set to GLY

    currently if multiple residue codes are detected they are all ignored (with a warning)
"""


# noinspection PyUnusedLocal
@import_app.command(no_args_is_help=True)
def shifts(
    chain_codes: str = typer.Option(
        "-",
        "--chain",
        help="chain codes [default -] can be a comma separated list or can be called mutiple times",
        metavar="<CHAIN-CODE>",
    ),
    entry_name: str = typer.Option(
        "mars", "-e", "--entry-name", help="a name for the entry"
    ),
    frame_name: str = typer.Option(
        "mars", "-f", "--frame-name", help="a name for the frame"
    ),
    prefix_to_strip: str = typer.Option(
        DEFAULT_PSEUDO_RESIDUE_PREFIX,
        "-s",
        "--strip-prefix",
        help="string to strip from the start of pseudo residues if present",
    ),
    parse_residues: bool = typer.Option(
        True,
        "--parse-residues",
        help=RECOGNISE_RESIDUES_HELP,
    ),
    treat_as_unassigned: bool = typer.Option(
        False,
        "--unassigned",
        help="treat all shifts as unassigned shifts",
    ),
    input: Path = typer.Option(
        STDIN,
        "-i",
        "--input",
        metavar="|PIPE|",
        help="input to read NEF data from [- is stdin]",
    ),
    file_names: List[Path] = typer.Argument(
        ..., help="input files of type mars shifts.tab", metavar="<MARS-shifts>.tab"
    ),
):
    """- import shifts from MARS input shift file <mars-shifts>.tab"""

    entry = read_or_create_entry_exit_error_on_bad_file(input, entry_name)

    chain_codes = parse_comma_separated_options(chain_codes)

    pipe(
        entry,
        chain_codes,
        frame_name,
        file_names,
        prefix_to_strip,
        parse_residues,
        treat_as_unassigned,
    )


def pipe(
    entry,
    chain_codes,
    frame_name,
    file_names,
    prefix_to_strip=DEFAULT_PSEUDO_RESIDUE_PREFIX,
    parse_residues=True,
    treat_as_unassigned=False,
):

    sparky_frames = []

    chain_code_iter = get_chain_code_iter(chain_codes)
    for file_name, chain_code in zip(file_names, chain_code_iter):

        with open(file_name) as lines:

            sparky_shifts = _parse_shifts(
                lines,
                chain_code=chain_code,
                file_name=file_name,
                prefix_to_strip=prefix_to_strip,
                parse_residues=parse_residues,
                treat_as_unassigned=treat_as_unassigned,
            )

            frame = shifts_to_nef_frame(sparky_shifts, frame_name)

            sparky_frames.append(frame)

    entry = add_frames_to_entry(entry, sparky_frames)

    print(entry)


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
    chain_code: str = "-",
    file_name="unknown",
    prefix_to_strip=DEFAULT_PSEUDO_RESIDUE_PREFIX,
    parse_residues=True,
    treat_as_unassigned=False,
) -> ShiftList:

    heading_indices = {}

    read_shifts = []
    for i, line in enumerate(lines):
        line_info = LineInfo(file_name, i + 1, line)
        line = line.strip()

        if i == 0:
            headings = line.split()

            _exit_if_bad_header(line_info)

            heading_indices = heading_to_indices_dict(headings)

        elif not line:
            continue
        else:
            shifts = _parse_line(
                line_info,
                heading_indices,
                chain_code,
                prefix_to_strip,
                parse_residues,
                treat_as_unassigned,
            )

            read_shifts.extend(shifts)

    return ShiftList(read_shifts)


def heading_to_indices_dict(headings):
    heading_indices = {
        heading: column for column, heading in enumerate(headings, start=1)
    }

    heading_indices[PSEUDO_RESIDUE] = 0

    return heading_indices


def _get_residues_from_string(string):

    result = []
    string = string.upper()
    for residue_name in TRANSLATIONS_3_1_PROTEIN:
        if residue_name in string:
            result.append(residue_name)
    return result


# TODO: remove when python 3.8 no longer supported
def _removeprefix(target: str, prefix: str) -> str:
    if target.startswith(prefix):
        return target[len(prefix) :]
    else:
        return target


def _removesuffix(target: str, suffix: str) -> str:
    if target.endswith(suffix):
        return target[: -len(suffix)]
    else:
        return target


def _parse_line(
    line_info,
    heading_indices,
    chain_code,
    prefix_to_strip,
    parse_residues,
    treat_as_unassigned,
):
    results = []

    fields = line_info.line.strip().split()
    pseudo_residue = fields[heading_indices[PSEUDO_RESIDUE]]

    for heading, index in heading_indices.items():
        if heading != PSEUDO_RESIDUE:
            value = fields[index]
            if value != MARS_UNDEFINED:

                _exit_if_shift_is_not_float(value, line_info)

                value = float(value)

                pseudo_residue = _removeprefix(pseudo_residue, prefix_to_strip)

                (
                    pseudo_pre_chars,
                    pseudo_residue_number,
                    pseudo_post_chars,
                ) = _split_pseudo_residue(pseudo_residue)

                _exit_if_pseudo_residue_number_missing(
                    pseudo_residue_number, pseudo_residue, line_info
                )

                residue_names = []
                if parse_residues:
                    residue_names = _get_residues_from_string(pseudo_post_chars)
                    if len(residue_names) > 1:
                        _warn_multiple_residues(residue_names, line_info)

                residue_name = UNUSED if not residue_names else residue_names[0]
                atom_name, offset = _split_heading(heading)

                if pseudo_residue.startswith("AR_") and not treat_as_unassigned:
                    if offset == "":
                        residue = SequenceResidue(
                            chain_code=chain_code,
                            sequence_code=pseudo_residue_number,
                            residue_name=residue_name,
                        )
                    else:
                        continue
                else:
                    if treat_as_unassigned:
                        chain_code = "-"
                    residue = SequenceResidue(
                        chain_code=f"@{chain_code}",
                        sequence_code=f"@{pseudo_residue_number}{offset}",
                        residue_name=UNUSED,
                    )
                atom = AtomLabel(residue, atom_name=atom_name)

                shift = ShiftData(atom=atom, value=value)

                results.append(shift)

    return results


def _split_heading(heading: str):

    offset = ""
    if heading.endswith("-1"):
        heading = _removesuffix(heading, "-1")
        offset = "-1"
    return heading, offset


def _warn_multiple_residues(residue_names, line_info):
    msg = f"""\
                        WARNING: the pseudo residue on line {line_info.line_no} in file {line_info.file_name} contains
                                 more than one residue name and will be ignored, the residue names were:

                                 {' '.join(residue_names)}

                                 the complete line was:

                                 {line_info.line}
                    """
    print(msg, files=sys.stderr)


def _split_pseudo_residue(pseudo_residue):
    first_characters = _get_starting_alpha(pseudo_residue)

    first_characters = first_characters.rstrip(SEPARATORS)

    pseudo_residue = _removeprefix(pseudo_residue, first_characters)
    numbers = get_starting_number(pseudo_residue)

    last_characters = _removeprefix(pseudo_residue, numbers)
    last_characters = last_characters.lstrip(SEPARATORS)

    return first_characters, numbers, last_characters


def _exit_if_pseudo_residue_number_missing(
    pseudo_residue_number, pseudo_residue, line_info
):

    if not is_int(pseudo_residue_number):
        msg = f"""
            At line {line_info.line} in the file {line_info.file_name} the pseudo residue should include a number,
            I got {pseudo_residue_number} from the {pseudo_residue} which should have the format {PSEUDO_RESIDUE_FORMAT}
            the complete line was:

            {line_info.line}
        """
        exit_error(msg)


def _exit_if_shift_is_not_float(value, line_info):
    if not is_float(value):
        msg = f"""
                        at line {line_info.line_no} in file {line_info.file_name} i expected a chemical shift but the
                        value read {value} doesn't look like a floating point number, the complete line was
                        {line_info.line}
                    """

        exit_error(msg)


def _exit_if_wrong_number_data_columns(fields, headings, line_info):
    num_fields = len(fields)
    num_headings = len(headings)
    if num_fields < num_headings:
        msg = f"""\
                    at line {line_info.line_no} in
                    file {line_info.file_name}
                    there weren't enough columns of data i expected {num_headings} but got {num_fields}
                    so the number of fields matched the length of the headings.
                    the headings were {' '.join(headings)}
                    the line was {line_info.line}
                """
        exit_error(msg)


def _exit_if_bad_header(line_info):
    line = line_info.line
    headings = line_to_headings(line)

    if not set(headings).issubset(EXPECTED_HEADINGS):
        msg = f"""\
                    the file {line_info.file_name} doesn't look like a sparky file"
                    line 1 should contain the standard sparky heading:

                    {' '.join(EXPECTED_HEADINGS)}

                    i got:
                    {line_info.line}

                    note: the heading maybe a subset of the headings and typically should include at least H and N
                          and (typically) more than one of CA + CA-1, or CB + CB-1 or C + C-1
                """
        exit_error(msg)


def line_to_headings(line):
    return set(line.strip().split())


def _get_starting_alpha(group):
    result = []
    for char in group:
        if char.isalpha() or char in SEPARATORS:
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
