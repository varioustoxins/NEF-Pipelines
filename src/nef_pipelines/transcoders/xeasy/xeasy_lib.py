import string
from collections import OrderedDict
from typing import Dict, Iterator, List, Tuple, Union

from nef_pipelines.lib.isotope_lib import ATOM_TO_ISOTOPE
from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.sequence_lib import get_residue_name_from_lookup
from nef_pipelines.lib.structures import (
    AtomLabel,
    DimensionInfo,
    LineInfo,
    NewPeak,
    Residue,
    SequenceResidue,
    ShiftData,
)
from nef_pipelines.lib.util import (
    exit_error,
    is_float,
    is_int,
    strip_characters_right,
    strip_line_comment,
)

XEASY_PEAK_MAGIC = "FORMAT xeasy3D"


def line_info_iter(lines: Iterator[str], source="unknown") -> Iterator[LineInfo]:
    for line_no, line in enumerate(lines, start=1):
        line = line.strip()

        if len(line) == 0:
            continue

        yield LineInfo(source, line_no, line)


def parse_sequence(lines: Iterator[str], source="unknown") -> List[SequenceResidue]:
    result = []
    for line_info in line_info_iter(lines, source):

        if line_info.line_no == 1 and line_info.line.startswith("#"):
            continue

        fields = line_info.line.split()

        exit_if_wrong_field_count_sequence(fields, line_info)

        residue_name, chain_seq_code = fields

        if residue_name == "SS":
            msg = f"""
                Original xeasy sequences are not supported only those used by flya
                at line {line_info.line_no} in file {line_info.file_name} if found a residue type SS
                where as it must be a standard 3 letter amino acid code, the whole line was

                {line_info.line}
            """
            exit_error(msg)

        chain_code, sequence_code = strip_characters_right(
            chain_seq_code, string.digits
        )

        sequence_residue = SequenceResidue(chain_code, sequence_code, residue_name)

        result.append(sequence_residue)

    return result


# A peak list contains an entry for each peak. The fields describing a peak are listed in Table 3.4.1.A. In a
# 2D spectrum the fields for the w3 and w4 dimension and in a 3D spectrum those for w4 are not used. The
# peak numbers in a peaklist must be unique but not necessarily continuous.
#
# Table 3.4.1.A Peak Fields
#
# Dim.    Fields          Description
#         peak number     unique number identifying the peak                                 1
#         colour          colour in the range [1,6] used for displaying the peaks            2
#         volume          volume of the peak                                                 3
#         volume error    volume error in percent                                            4
#         integration method                                                                 5
#                         method used for the integration: d, r, e, m, a, -
#         comment         user defined comment                                               6
#         possible ass.   data structure containing possible assignments                     7
#         shift           folded w1 position in ppm                                          8
# w1      fold            number of times peak is folded in w1                               9
#         atom number     assignment in w1: reference into the atom list                     10
#         shift           folded w2 position in ppm                                          11
# w2      fold            number of times peak is folded in w2                               12
#         atom number     assignment in w2: reference into the atom list                     13
#         shift           folded w3 position in ppm                                          14
# w3      fold            number of times peak is folded in w3                               15
#         atom number     assignment in w3: reference into the atom list                     16
#         shift           folded w4 position in ppm                                          17
# w4      fold            number of times peak is folded in w4                               18
#         atom number     assignment in w4: reference into the atom list                     19
# The peak list is stored in a peak list file with extension .peaks. It can be read by the program ASNO (P.
# Güntert et al., 1993) which uses a peak list, an atom list and selected structure coordinate files to generate
# possible assignments for NOESY cross peaks which can be loaded into XEASY. The program CALIBA
# (P. Güntert et al., J. Mol. Biol. (1991) 217, 517-530) translates the peak lists containing integrated peaks
# into distance constraints which can be used by the program DIANA (P. Güntert et al., J. Mol. Biol. (1991)
# 217, 517-530). An example of the first few lines of a two dimensional peak list is given below:
# # Number of dimensions 2
#    11  7.289  10.169 1 ?          2.048e+03  0.00e+00 -   0  126  128  0
#        #  first peak
#    12  7.119   9.413 1 ?          1.280e+02  0.00e+00 -   0  517  506  0
#    3   7.106   7.497 1 ?          4.096e+03  0.00e+00 -   0  129  130  0
#    4   7.228   7.411 1 ?          4.096e+03  0.00e+00 -   0  131  127  0
#    5   7.106   7.411 1 ?          5.120e+02  0.00e+00 -   0  327  328  0
#    6   6.838   7.094 1 ?          8.192e+03  0.00e+00 -   0  489  488  0
# The number on the first line after the hash "#" indicates the dimensionality of the peak list. Subsequent
# lines, starting with a number, contain the fields for one peak. Additional lines starting with a hash "#" are
# comments for the peak on the line above. The first field for each peak is the peak number, followed by:
# the unfolded chemical shift coordinates in ppm in w1 and w2 (more numbers are listed for higher
# dimensional spectra), the color code (a number from 1 to 6), the user defined type of the spectrum where
# the peak is observed, the peak volume, the uncertainty of the volume in percent, the integration method
# ("d" for Denk integration, "r" for rectangular integration, "e" for elliptical integration, "m" for maximum
# integration, "a" for automatic integration, "-" for not integrated), an unused number, the assignments in
# w1 and w2 is given by the two following atom numbers (more numbers are listed for higher dimensional
# spectra), the last number is not used. The commands to load or write peak lists are "Load peaklist [lp]"
# and "Write peaklist [wp]".

test_peaks = """
# Number of dimensions 3
#FORMAT xeasy3D
#INAME 1 HN
#INAME 2 H
#INAME 3 N
#SPECTRUM N15TOCSY HN H N
      1    8.731    8.723  115.265 1 U   5.500000E+00  0.000000E+00 e 0 H.A2     H.A2     N.A2 #MAP    403
      2    8.731    4.610  115.275 1 U   5.500000E+00  0.000000E+00 e 0 -         -         -
      3    8.732    4.192  115.254 1 U   5.500000E+00  0.000000E+00 e 0 H.A2     HA2.A2   N.A2 #MAP    404
      3    8.732    4.192  115.254 1 U   5.500000E+00  0.000000E+00 e 0 H.A2     HA3.A2   N.A2 #MAP    405
"""
# ser  shift1   shift2 shift3  colour  ??? vol           vol-error    int-method  a-number-or-folding  ass-1     ass-2     ass-3 comment      # noqa: E501 - this is not part of the file
# 1    8.731    8.723  115.265 1       U   5.500000E+00  0.000000E+00 e           0                    H.A82     H.A82     N.A82 #MAP    403  # noqa: E501 - this is not part of the file


def _parse_xeasy_assignment(
    assignment: str,
    residue_lookup: Dict[Tuple[Union[str, int], str], str],
    line_info: LineInfo,
) -> AtomLabel:

    if is_int(assignment):
        exit_error(f"pure xeasy assignments not currently supported, {line_info.line}")

    fields = assignment.split(".")
    if len(fields) == 1 and fields[0] == "-":
        residue = SequenceResidue(UNUSED, UNUSED, UNUSED)
        atom = AtomLabel(residue, UNUSED)

    elif len(fields) not in (1, 2):
        msg = f"""
            an xeasy assignment should either be an integer or a string of the for <ATOM>.<CHAIN_CODE><SEQUENCE_CODE>
            for example 10 or HA2.A82. I got {assignment} at {line_info.line_no} in file {line_info.file_name}
            the whole line was

            {line_info.line}

        """
        exit_error(msg)
    else:
        atom_name, chain_residue = fields
        chain_code, sequence_code = strip_characters_right(chain_residue, string.digits)

        residue_name = get_residue_name_from_lookup(
            chain_code, sequence_code, residue_lookup
        )
        _exit_if_no_residue_name_in_sequence(
            residue_name, chain_code, sequence_code, line_info
        )

        residue = SequenceResidue(chain_code, sequence_code, residue_name)
        atom = AtomLabel(residue, atom_name)

    return atom


def _exit_if_no_residue_name_in_sequence(
    residue_name, chain_code, sequence_code, line_info
):

    if residue_name == UNUSED:
        msg = f"""
                in the file {line_info.file_name} at line {line_info.line_no} the sequence of the read molecules
                doesn't define a residue for the chain code {chain_code} and the sequence code {sequence_code},
                did you read a sequence (or the correct one)
                the line was:

                {line_info.line}
            """
        exit_error(msg)


def parse_peaks(
    lines: Iterator[str], source: str, residue_name_lookup: Dict[Union[str, int], str]
) -> Tuple[str, List[DimensionInfo], List[NewPeak]]:
    have_magic = False
    number_dimensions = None
    experiment_type = None
    dimensions = OrderedDict()

    peaks = []

    for line_info in line_info_iter(lines, source):

        shifts: list[float] = []
        if line_info.line.startswith("#"):

            stripped_line = line_info.line.lstrip("#").lstrip()

            if stripped_line.startswith(XEASY_PEAK_MAGIC):
                have_magic = True
                continue

            if stripped_line.startswith("Number of dimensions"):
                fields = stripped_line.split()
                number_dimensions = fields[-1]
                check_number_dimensions_or_exit(line_info, number_dimensions)
                number_dimensions = int(number_dimensions)
                continue

            if stripped_line.startswith("INAME"):

                fields = stripped_line.split()

                _check_iname_fields_length_or_exit(fields, line_info)

                dimension_number = fields[1]
                dimension_code = fields[2]

                check_dimension_number_is_integer_or_exit(dimension_number, line_info)

                dimension_number = int(dimension_number)
                dimensions[dimension_number - 1] = dimension_code
                continue

            if stripped_line.startswith("SPECTRUM"):
                fields = stripped_line.split()
                if len(fields) > 1:
                    experiment_type = fields[1]

        else:
            _exit_if_no_magic_before_data(have_magic, line_info)
            line, comment = strip_line_comment(line_info.line)

            fields = line.split()

            serial = fields[0]
            _check_serial_is_integer_or_exit(serial, line_info)
            serial = int(serial)
            current_column = 1

            for shift_column_number in dimensions:
                target_column = current_column + shift_column_number
                shift = fields[target_column]
                _check_shift_is_float_or_exit(shift, target_column, line_info)
                shifts.append(float(shift))
            current_column += number_dimensions

            # ignore peak color and U
            current_column += 2

            volume = fields[current_column]
            _check_volume_is_float_or_exit(volume, current_column, line_info)
            volume = float(volume)
            current_column += 1

            volume_error = fields[current_column]
            _check_volume_is_percentage_or_exit(volume_error, current_column, line_info)
            volume_error = float(volume_error)
            volume_error = volume * volume_error / 100.0
            current_column += 1

            # ignore the peak integration method
            current_column += 2

            assignments = []

            for assignment_column_number in dimensions:
                target_column = current_column + assignment_column_number
                assignment = _parse_xeasy_assignment(
                    fields[target_column], residue_name_lookup, line_info
                )
                assignments.append(assignment)

            shift_data = [
                ShiftData(assignment, shift)
                for assignment, shift in zip(assignments, shifts)
            ]
            peak = NewPeak(
                shifts=shift_data,
                id=serial,
                volume=volume,
                volume_uncertainty=volume_error,
                comment=comment,
            )

            peaks.append(peak)

    dimension_names = [
        dimensions[dimension_index] for dimension_index in sorted(dimensions)
    ]
    axis_codes = [
        ATOM_TO_ISOTOPE[dimension_name[0]] for dimension_name in dimension_names
    ]
    dimension_info = [
        DimensionInfo(axis_code, dimension_name)
        for axis_code, dimension_name in zip(axis_codes, dimension_names)
    ]

    return experiment_type, dimension_info, peaks


# 3.4.2 Atom List
#
# The atom list contains the names and frequencies of resonances. They define the possible assignments for
# each dimension of a peak.
#
# Table 3.4.2.A - Atom Fields
#
# Fields              Description
#
# atom number         unique number identifying the atom
# shift               mean chemical shift in ppm
# shift error         deviation of the assigned peaks from the mean value
# name                atom name
# fragment number     number of the fragment to which the atom belongs
# lineshapes          data structure containing the reference lineshapes
#
#
# The fields listed in Table 3.4.2.A constitute an atom entry. They can be modified in the peak editing
# window. The atom numbers, used to reference the atoms, must be unique but not necessarily continuous.
# The number -9999 is reserved to denote invalid entries. The average chemical shift and the shift error can
# be calculated from the assigned peaks. The command is "Average chem. shift [ac]".
#
# If the chemical shift is not defined it is set to the value 999.000.
#
# A new atom list is generated each time when a fragment list is loaded. For each fragment the
# corresponding atoms are looked up in the fragment library file and added to the list. New atom entries are
# added to the atom list if a non existing atom is used with the "Assign peak [ap]" command, if the fragment
# type is changed in the peak editing window, or with the "Add new fragment [af]" command.
#
# The atom list file has the extension ".prot" originating from the old EASY format. The following line is
# taken from such a file:
#
# 32   4.370  0.004   HA  2
#
# The first number is the atom number, followed by its mean chemical shift and the deviation from the
# mean value. The atom name and the fragment number follow. The commands to read or write an atom list
# are "Load atoms (chem. shift) [lc]" and "Write atoms (chem. shift) [wc]".


def parse_shifts(
    lines: Iterator[str], source: str, residue_lookup: Dict[Union[str, int], str]
):
    shifts = []
    for line_no, line in enumerate(lines, start=1):

        line_info = LineInfo(source, line_no, line.strip())

        if len(line_info.line) == 0:
            continue

        fields = line_info.line.split()

        _check_number_fields_correct_or_exit(fields, line_info)

        column = 1
        serial = fields[column - 1]
        _check_serial_is_integer_or_exit(serial, line_info)

        column += 1
        shift = fields[column - 1]
        _check_fields_is_float_or_exit(shift, column, line_info)

        column += 1
        shift_error = fields[column - 1]
        _check_fields_is_float_or_exit(shift_error, column, line_info)

        column += 1
        atom_name = fields[column - 1]

        column += 1
        chain_residue = fields[column - 1]
        chain_code, sequence_code = strip_characters_right(chain_residue, string.digits)

        residue_name = get_residue_name_from_lookup(
            chain_code, sequence_code, residue_lookup
        )
        _exit_if_no_residue_name_in_sequence(
            residue_name, chain_code, sequence_code, line_info
        )

        residue = Residue(chain_code, sequence_code, residue_name)
        atom = AtomLabel(residue, atom_name)

        shift = ShiftData(atom=atom, value=shift, value_uncertainty=shift_error)

        shifts.append(shift)

    return shifts


def _check_fields_is_float_or_exit(value, column, line_info):
    if not is_float(value):
        msg = f"""
                column {column} of {line_info.file_name} at line {line_info.line_no} should be a floating point
                 number I got {value}, the line was

                {line_info.line}
            """
        exit_error(msg)


def _check_number_fields_correct_or_exit(fields, line_info):

    num_fields = len(fields)
    if num_fields != 5:
        msg = f"""
                in the file {line_info.file_name} at line {line_info.line_no} I expected 5 fields but got {num_fields}
                the line was

                {line_info}

                i expected something like

                32 4.370 0.004 HA A2
            """
        exit_error(msg)


def _exit_if_no_magic_before_data(have_magic, line_info):
    if not have_magic:
        msg = f"""
                    Xeasy files should have the line #{XEASY_PEAK_MAGIC} before any data is read
                    at line {line_info.line_no} in file {line_info.file_name} i appear to have data
                    before this occured. The line was

                    {line_info.line}
                """
        exit_error(msg)


def _check_volume_is_percentage_or_exit(volume_error, column_number, line_info):
    msg = None
    if not is_float(volume_error):
        msg = f"""
            the volume error column (column {column_number}) should be a floating point number
            i got {volume_error} in the file {line_info.file_name} at line {line_info.line_no} the value of the
            line was

            {line_info.line}
        """
    volume_error = float(volume_error)
    if not (100.0 >= volume_error >= 0.0):
        msg = f"""
            the volume error column (column {column_number}) should be a nunber between 0.0 and 100.0 i got
            {volume_error} in the file {line_info.file_name} at line {line_info.line_no} the value of the line was

            {line_info.line}
        """

    if msg:
        exit_error(msg)


def _check_volume_is_float_or_exit(volume, column_number, line_info):
    if not is_float(volume):
        msg = f"""
            the volume column (column {column_number}) should be a floating point number i got {volume}
            in the file {line_info.file_name} at line {line_info.line_no} the value of the line was

            {line_info.line}
        """
        exit_error(msg)


def _check_shift_is_float_or_exit(shift, column_number, line_info):
    if not is_float(shift):
        msg = f"""
                chemical shift fields should be floating point numbers i got {shift} at column number {column_number}
                in the file {line_info.file_name} at line {line_info.line_no} the value of the line was

                {line_info.line}
                    """
        exit_error(msg)


def _check_serial_is_integer_or_exit(serial, line_info):
    if not is_int(serial):
        msg = f"""
            the first field of a xeasy peak or shift  list should be an integer serial number i got: {serial}
            in file {line_info.file_name} at line {line_info.line_no}, the line was:

            {line_info.line}
        """
        exit_error(msg)


def check_dimension_number_is_integer_or_exit(dimension_number, line_info):
    if not is_int(dimension_number):
        msg = f"""
            a #INAME line in an xeasy file must have an integer as its seconds field i got
            {dimension_number}
            the expected format is #INAME <DIMENSION-NUMBER> <AXIS-CODE> [e.g #INAME 1 HN]
            i got the following in ther file {line_info.file_name} at line {line_info.line_no}

            {line_info.line}
        """
        exit_error(msg)


def _check_iname_fields_length_or_exit(fields, line_info):
    if len(fields) != 3:
        msg = f"""
                        a #INAME line in an xeasy file must have 3 fields i got {len(fields)}
                        the expected format is #INAME <DIMENSION-NUMBER> <AXIS-CODE> [e.g #INAME 1 HN]
                        i got the following in ther file {line_info.file_name} at line {line_info.line_no}

                        {line_info.line}
                    """
        exit_error(msg)


def check_number_dimensions_or_exit(line_info, number_dimensions):
    if not is_int(number_dimensions):
        msg = f"""
                        The number of dimensions found in the file {line_info.file_name} doesn't appear to be an integer
                        I got {number_dimensions} at line {line_info.line_no} the value for the line was
                        {line_info.line}
                    """
        exit_error(msg)


def _check_for_peaks_magic_or_exit(line_info):
    if line_info.line != XEASY_PEAK_MAGIC:
        msg = f"""
                    an xeasy peak files should start with {XEASY_PEAK_MAGIC} but i got:

                    {line_info.line}

                    at line {line_info.line_no} in {line_info.file_name}
                """
        exit_error(msg)


def exit_if_wrong_field_count_sequence(fields: List[str], line_info: LineInfo):
    if len(fields) != 2:
        msg = f"""
                in file {line_info.file_name} at line {line_info.line_no} there should be 2 columns i got {len(fields)}
                the line should be of the form 'HIS A1' [<RESIDUE-NAME> <CHAIN-RESIDUE-NUMBER>] but was

                {line_info.line}
            """

        exit_error(msg)


def exit_if_wrong_field_count_peaks(fields: List[str], line_info: LineInfo):
    if len(fields) != 2:
        msg = f"""
                in file {line_info.file_name} at line {line_info.line_no} there should be 2 columns i got {len(fields)}
                the line should be of the form 'HIS A1' [<RESIDUE-NAME> <CHAIN-RESIDUE-NUMBER>] but was

                {line_info.line}
            """

        exit_error(msg)
