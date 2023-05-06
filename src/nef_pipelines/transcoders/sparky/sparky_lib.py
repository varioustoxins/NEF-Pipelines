import string
from collections import namedtuple
from typing import List, Tuple

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.sequence_lib import (
    TRANSLATIONS_1_3,
    MoleculeType,
    residues_to_residue_name_lookup,
)
from nef_pipelines.lib.structures import AtomLabel, LineInfo, Residue, SequenceResidue
from nef_pipelines.lib.util import exit_error

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


def _strip_characters_left(target: str, letters: str) -> Tuple[str, str]:

    remaining = target.lstrip(letters)

    stripped = target[: len(target) - len(remaining)]

    return stripped, remaining


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
    residue_name, target = _strip_characters_left(target, string.ascii_letters)
    if len(target) == 0:
        target = residue_name
        residue_name = ""

    if target[0] == "?" and len(target) > 0:
        target = target[1:]
        residue_name = ""

    # remove residue numbers or question mark
    residue_number, target = _strip_characters_left(target, string.digits)

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
    if residue_name != "" and residue_name.lower() in "HCNQM".lower():
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
) -> List[AtomLabel]:

    """
    take a sparky assignment of the form ?, G16H4'-H8 or T17H6-G16H8 into atom labels

    :param assignments: a single assignment or a - separated assignment [including abbreviated assignments]
    :param chain_code: the chain code to use
    :param sequence: the sequence to get residue names from and to check the read residue names agains
    :param molecule_type: the type of the molecule DNA RNS protein etc.
    :param line_info: file and line  information for error reporting
    :return: a list of AtomLabels
    """

    residue_name_lookup = residues_to_residue_name_lookup(sequence)

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

        if len(sequence) > 0 and (residue_name_key not in residue_name_lookup):
            msg = f"""
                the chain code {chain_code} and sequence_code {sequence_code} from
                line {line_info.line_no} in file {line_info.file_name} were not found
                in the input sequence, the full line was

                {line_info.line}

                if you wish to input the peaks without validating against the input sequence use the
                --no-validate option of sparky import peaks
            """
            exit_error(msg)

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
