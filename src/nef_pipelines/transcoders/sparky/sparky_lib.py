import string
import sys
from collections import namedtuple
from itertools import zip_longest
from typing import Dict, List, Tuple

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_1_3,
    MoleculeType,
    sequence_to_residue_name_lookup,
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
from nef_pipelines.lib.util import exit_error, is_float, strip_characters_left

#
# sparky docs
#
# Make peaks on a spectrum from a peak list file (rp).
#
# Peaks are read from a peak list file and placed on the selected spectrum.
# The file should contain a line for each peak. The line should have an
# assignment followed by chemical shifts for each axis. For example
#
# 	C2H5-G1H1      5.395      6.030
# The assignment can contain ? components. It can omit a group name for a component
# -- the shorthand G1H1'-H2' where the second group is omitted is equivalent to G1H1'-G1H2'.
# The residue name is separated from the atom name by looking for a residue number followed
# by one of the letters H, C, N, Q, or M (upper or lower case). Extra columns become the
# peak note. Peaks for 3-D or 4-D spectra can be read.
#
# what does sparky do with multiple chains?
#
# what does ga mean in the sparky output after a volume
#
# why does sparky sometime have ga after a volume I presume it's a gausiann peak fit?
# comment gst 19/04/2023 is ga for a gaussian peak fit?
#
#  Assignment       w1      w2      Volume     lw1 (hz)   lw2 (hz)
#
#    G16H3'-H8    4.905   8.010   7.15e+06 ga    28.6       20.0
#    G16H4'-H8    4.439   8.013   5.42e+06 ga    35.3       16.9
#  T17H6-G16H8    7.205   8.004   1.68e+06
#  T17H7-G16H8    1.459   8.008   2.09e+07 ga    27.5       24.1
#   T17H2"-H1'    2.509   5.840   4.68e+07 ga    41.2       17.6
#
# what does ta display in a sparky project
# how does sparky cope with complexes where peaks are between chains
# which it doesn't define
#

SparkyAtomLabel = namedtuple("SparkyAtomLabel", "residue_number residue_name atom_name")


def parse_single_assignment(
    assignment: str,
    previous_residue_name: str = None,
    previous_residue_number: str = None,
) -> Tuple[str, str, str]:
    """
    Parse a single sparky assignment of the form ?, G16H4', H8, T17H6, G16H8 into a tuple of residue_number,
    residue_name and atom_name. To allow for processing of abbreviated assignments of the form G16H4'-H8 a previous
    residue number and residue name may be passed in [in this casefor H8  they would be G and 16 to match G16H4']

    :param assignment: the single sparky assignments
    :param previous_residue_name: a previous residue name to use for an abbreviated assignment
    :param previous_residue_number: a previous residue number to use for an abbreviated assignment
    :return: a tuple of the form (residue_number, residue_name , atom_name)
    """

    target = assignment

    # remove a residue name or question mark
    residue_name, target = strip_characters_left(target, string.ascii_letters)
    if len(target) == 0:
        target = residue_name
        residue_name = ""

    if target[0] == "?" and len(target) > 0:
        target = target[1:]
        residue_name = ""

    # remove residue numbers or question mark
    residue_number, target = strip_characters_left(target, string.digits)

    if len(residue_number) == 0 and len(target) != 0 and target[0] == "?":
        target = target[1:]
        residue_number = ""

    if len(target) > 0:
        atom_name = target
    else:
        atom_name = ""

    # residue name is separated from the atom name by looking for a residue number followed
    # by one of the letters H, C, N, Q, or M ergo a residue name that starts with one of these
    # must be wrong, and we have split an atom (though we don't actually need this test?)
    residue_lower = residue_name.lower()
    nmr_atoms_lower = "HCNQM".lower()
    atom_starts_with_nmr_lower = False
    atom_name_lower = atom_name.lower()
    len_atom_name = len(atom_name)
    if len_atom_name > 0 and atom_name_lower[0] in nmr_atoms_lower:
        atom_starts_with_nmr_lower = True

    if (
        not atom_starts_with_nmr_lower
        and residue_name != ""
        and residue_lower in nmr_atoms_lower
    ):
        atom_name = f"{residue_name}{residue_number}{atom_name}"
        residue_name = ""
        residue_number = ""

    if (
        residue_number == ""
        and previous_residue_number is not None
        and residue_name == ""
        and previous_residue_name is not None
        and atom_name != ""
    ):
        residue_number = previous_residue_number
        residue_name = previous_residue_name

    if residue_name == "" and residue_number == "":
        for i, character in enumerate(atom_name):
            if character.lower() in "HCNQM".lower():
                if i > 0 and atom_name[i - 1] in string.digits:
                    residue_name_and_number = atom_name[:i]
                    atom_name = atom_name[i:]

                    residue_name = residue_name_and_number.rstrip(string.digits)

                    residue_number = residue_name_and_number[-len(residue_name) :]

    return SparkyAtomLabel(residue_number, residue_name, atom_name)


def parse_assignments(
    assignments: str,
    chain_code: str,
    sequence: List[SequenceResidue],
    molecule_type: MoleculeType,
    line_info: LineInfo,
    allow_pseudo_atoms=False,
) -> List[AtomLabel]:
    """
    take a sparky assignment of the form ?, G16H4'-H8 or T17H6-G16H8 into atom labels

    :param assignments: a single assignment or a - separated assignment [including abbreviated assignments]
    :param chain_code: the chain code to use
    :param sequence: the sequence to get residue names from and to check the read residue names agains
    :param molecule_type: the type of the molecule DNA RNS protein etc.
    :param line_info: file and line  information for error reporting
    :param allow_pseudo_atoms: if true ignore residue names which aren't in the molecule_type
    :return: a list of AtomLabels
    """

    residue_name_lookup = sequence_to_residue_name_lookup(sequence)

    residue_name_translations = TRANSLATIONS_1_3[molecule_type]

    fields = assignments.split("-")

    result = []
    last_sequence_code = None
    last_residue_name = None

    for field in fields:

        sequence_code, residue_name, atom_name = parse_single_assignment(
            field,
            previous_residue_number=last_sequence_code,
            previous_residue_name=last_residue_name,
        )

        if sequence_code == "":
            sequence_code = UNUSED
        if residue_name == "":
            residue_name = UNUSED

        if residue_name_translations is not None and residue_name is not UNUSED:

            if residue_name in residue_name_translations:
                translated_residue_name = residue_name_translations[residue_name]
            elif allow_pseudo_atoms:
                translated_residue_name = residue_name
            else:
                msg = f"""
                    The residue name {residue_name} is not defined for the molecule type {molecule_type}
                    at line {line_info.line_no} in file {line_info.file_name} the line was
                    {line_info.line}
                """
                exit_error(msg)

        residue_name_key = (chain_code, sequence_code)

        if residue_name == UNUSED and residue_name_lookup is None:
            msg = f"""
                no sequence was loaded and the assignment {assignments} while it has a sequence code {sequence_code}
                and chain code {chain_code} doesn't define a residue type, please provide a sequence in the input
                stream
            """
            exit_error(msg)
        else:

            if (
                residue_name_lookup is not None
                and residue_name_key in residue_name_lookup
            ):
                translated_residue_name = residue_name_lookup[residue_name_key]

        if (
            len(sequence) > 0
            and (residue_name_key not in residue_name_lookup)
            and residue_name_key[1] != UNUSED
        ):
            msg = f"""
                the chain code {chain_code} and sequence_code {sequence_code} from
                line {line_info.line_no} in file {line_info.file_name} were not found
                in the input sequence, the full line was

                {line_info.line}

                if you wish to input the peaks without validating against the input sequence use the
                --no-validate option of sparky import peaks
            """
            exit_error(msg)

        if residue_name_key[1] == UNUSED:
            translated_residue_name = UNUSED

        residue = Residue(
            chain_code=chain_code,
            sequence_code=sequence_code,
            residue_name=translated_residue_name,
        )
        assignment = AtomLabel(residue, atom_name)

        result.append(assignment)

        last_sequence_code = sequence_code
        last_residue_name = residue_name

    return result


def parse_peaks(
    lines, file_name, molecule_type, chain_code, sequence, allow_pseudo_atoms=False
):

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

            assignments = parse_assignments(
                raw_assignment,
                chain_code,
                sequence,
                molecule_type,
                line_info,
                allow_pseudo_atoms=allow_pseudo_atoms,
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
        exit_error(msg)


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
