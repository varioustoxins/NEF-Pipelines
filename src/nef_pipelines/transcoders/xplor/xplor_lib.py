from collections import UserList
from functools import partial
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Tuple

from pynmrstar import Loop, Saveframe
from pyparsing import (
    CaselessLiteral,
    Combine,
    Forward,
    Group,
    Literal,
    OneOrMore,
    Optional,
    Or,
    ParseException,
    ParseResults,
    Regex,
    Suppress,
    Word,
    ZeroOrMore,
    alphanums,
    nums,
    rest_of_line,
)
from pyparsing.common import pyparsing_common as ppc

from nef_pipelines.lib.nef_lib import UNUSED, PotentialTypes, create_nef_save_frame
from nef_pipelines.lib.sequence_lib import ANY_CHAIN, replace_chain_in_atom_labels
from nef_pipelines.lib.structures import (
    AtomLabel,
    DihedralRestraint,
    DistanceRestraint,
    SequenceResidue,
)
from nef_pipelines.lib.util import (
    end_with_ordinal,
    exit_error,
    get_display_file_name,
    read_from_file_or_exit,
)

# trimmed [minimal set of factors supporting most restraints] EBNF for distance restraints from xplor manual
# <selection>:== ( <selection-expression> )
# <selection-expression>:==
#   <term> - selects atoms that belong to the term.
#   <term> { OR <term> } selects all atoms that belong to either one of the terms.
#
# <term>:==
#   <factor> - selects atoms that belong to the factor.
#   <factor> { AND <factor> } - selects all atoms that belong to all of the factors.
#
# <factor>:==
#   ( <selection-expression> ) - selects all atoms that are selected in selection expression.
#
#   ALL - selects all atoms.
#
#   ATOM <*segment-name*> <*residue-number*> <*atom*>
#
#   NAME <*atom*> - selects all atoms that match the specified atom name (Section 3.1.1)
#                       or a wildcard (Section 2.6) of it.
#
#   RESIdue <*residue-number*> - selects all atoms that match the specified residue number (Section 3.7)
#                                    or a wildcard (Section 2.6) of it.
#
#   SEGIdentifier <*segment-name*> selects all atoms that match the specified segment name (Section 3.7)
#                                  or a wildcard (Section 2.6) of it.

LEFT_PARENTHESIS = "("
RIGHT_PARENTHESIS = ")"

SINGLE_QUOTE = "'"
DOUBLE_QUOTE = '"'

ASSIGN = "assign"
NEF_DIHEDRAL_RESTRAINT = "nef_dihedral_restraint"
XPLOR_COMMENT_TOKEN = "!"
DISTANCE_PLUS = "d_plus"
DISTANCE_MINUS = "d_minus"
DISTANCE = "d"
EXPONENT = "exponent"
RANGE = "range"
ANGLE = "angle"
ENERGY_CONSTANT = "energy_constant"

ATOMS_4 = "atoms_4"
ATOMS_3 = "atoms_3"
ATOMS_2 = "atoms_2"
ATOMS_1 = "atoms_1"

SELECTION = "selection"
SELECTION_EXPRESSION = "selection-expression"
TERM = "term"
FACTOR = "factor"

AND = "AND"
OR = "OR"

SEGMENT_FACTOR = "segment-factor"
RESIDUE_FACTOR = "residue-factor"
ATOM_FACTOR = "atom-factor"

RESIDUE_LITERAL = "residue"
SEGMENT_IDENTIFIER_LITERAL = "segidentifier"
ATOM_NAME_LITERAL = "name"

ATOM_WILDCARDS = "*%#+"

ATOM = "atom"
SEGID = "segid"
RESID = "resid"

XPLOR_COMMENT = Regex(r"!.*").set_name("Xplor comment")

DEFAULT_PRECISION = 5
INDEX = "index"
RESTRAINT_ID = "restraint_id"
RESTRAINT_COMBINATION_ID = "restraint_combination_id"
CHAIN_CODE_1 = "chain_code_1"
SEQUENCE_CODE_1 = "sequence_code_1"
RESIDUE_NAME_1 = "residue_name_1"
ATOM_1 = "atom_name_1"
CHAIN_CODE_2 = "chain_code_2"
SEQUENCE_CODE_2 = "sequence_code_2"
RESIDUE_NAME_2 = "residue_name_2"
ATOM_2 = "atom_name_2"
CHAIN_CODE_3 = "chain_code_3"
SEQUENCE_CODE_3 = "sequence_code_3"
RESIDUE_NAME_3 = "residue_name_3"
ATOM_3 = "atom_name_3"
CHAIN_CODE_4 = "chain_code_4"
SEQUENCE_CODE_4 = "sequence_code_4"
RESIDUE_NAME_4 = "residue_name_4"
ATOM_4 = "atom_name_4"
WEIGHT = "weight"
TARGET_VALUE = "target_value"
LOWER_LIMIT = "lower_limit"
UPPER_LIMIT = "upper_limit"
EXTRA_INFO = "extra_info"
CCPN_COMMENT = "ccpn_comment"

DISTANCE_RESTRAINT_TAGS = [
    INDEX,
    RESTRAINT_ID,
    RESTRAINT_COMBINATION_ID,
    CHAIN_CODE_1,
    SEQUENCE_CODE_1,
    RESIDUE_NAME_1,
    ATOM_1,
    CHAIN_CODE_2,
    SEQUENCE_CODE_2,
    RESIDUE_NAME_2,
    ATOM_2,
    WEIGHT,
    TARGET_VALUE,
    LOWER_LIMIT,
    UPPER_LIMIT,
]

DIHEDRAL_RESTRAINT_TAGS = [
    INDEX,
    RESTRAINT_ID,
    RESTRAINT_COMBINATION_ID,
    CHAIN_CODE_1,
    SEQUENCE_CODE_1,
    RESIDUE_NAME_1,
    ATOM_1,
    CHAIN_CODE_2,
    SEQUENCE_CODE_2,
    RESIDUE_NAME_2,
    ATOM_2,
    CHAIN_CODE_3,
    SEQUENCE_CODE_3,
    RESIDUE_NAME_3,
    ATOM_3,
    CHAIN_CODE_4,
    SEQUENCE_CODE_4,
    RESIDUE_NAME_4,
    ATOM_4,
    WEIGHT,
    TARGET_VALUE,
    LOWER_LIMIT,
    UPPER_LIMIT,
]


class XPLORParseException(Exception):
    ...


_and_op = CaselessLiteral(AND)
_or_op = CaselessLiteral(OR)

_l_paren = Suppress(LEFT_PARENTHESIS)
_r_paren = Suppress(RIGHT_PARENTHESIS)


def _expand_literal(literal, min_length=4, case_insensitive=True):
    result = []
    for i in range(min_length, len(literal) + 1):
        elem = (
            CaselessLiteral(literal[:i]) if case_insensitive else Literal(literal[:i])
        )
        result.append(elem)

    result.reverse()

    return Or(result)


def _convert_to_4_letter_string(string: str) -> str:
    result = string
    if string_len := len(string) < 4:
        result += " " * (4 - string_len)

    return result


class _NamedToken:
    def __init__(self, name, toks):
        self.name = name
        self.token = toks

    def getName(self):
        return self.name

    get_name = getName

    def __len__(self):
        return 1

    def __getitem__(self, item):
        if item == 0:
            return self.token
        else:
            raise Exception("array out of bounds")

    def __str__(self):
        return f"{self.name} : {self.token}"

    def __repr__(self):
        return f"{self.name} : {self.token}"

    def __eq__(self, other):
        result = False
        if isinstance(other, self.__class__):
            if other.name == self.name and other.token == self.token:
                result = True

        return result


class _NamedTokens(UserList):
    def __init__(self, name, toks):

        super(_NamedTokens, self).__init__(toks)

        self.name = name

    def __str__(self):
        return f"[{self.name} : {self.data}]"

    def _repr__(self):
        tok_strings = ",".join([str(tok) for tok in self.toks])
        return f"{self.name} {tok_strings}"


def _as_named_single_token(name, _, _1, toks):
    return _NamedToken(name, toks[0])


# resid factor
_residue_literal = Suppress(_expand_literal(RESIDUE_LITERAL))
_residue_number = (
    Combine((Optional("-") + Word(nums)))
    .set_results_name(RESID, list_all_matches=True)
    .setParseAction(ppc.convert_to_integer)
)(RESID)
_residue_factor = (_residue_literal + _residue_number)(RESIDUE_FACTOR)

_named_resid = partial(_as_named_single_token, RESID)
_residue_factor.set_parse_action(_named_resid)

# atom factor
_atom_literal = Suppress(CaselessLiteral(ATOM_NAME_LITERAL))
_atom_label = Word(
    alphanums + ATOM_WILDCARDS + SINGLE_QUOTE + DOUBLE_QUOTE
).set_results_name(ATOM, list_all_matches=True)
_atom_factor = (_atom_literal + _atom_label)(ATOM_FACTOR)

_named_atom = partial(_as_named_single_token, ATOM)
_atom_factor.set_parse_action(_named_atom)

# segment factor
_segid_literal = Suppress(_expand_literal(SEGMENT_IDENTIFIER_LITERAL))
_segid_label = Word(alphanums, max=4)
_segid_factor = (_segid_literal + _segid_label)(SEGMENT_FACTOR)


_named_segid = partial(_as_named_single_token, SEGID)
_segid_factor.setParseAction(_named_segid)


def _as_named_tokens(name, _, _1, toks):
    return _NamedTokens(name, toks)


_as_named_list_or = partial(_as_named_tokens, OR)
_as_named_list_and = partial(_as_named_tokens, AND)
_as_named_list_selection = partial(_as_named_tokens, SELECTION)

_selection = Forward()

_factor = (_segid_factor | _residue_factor | _atom_factor | _selection)(FACTOR)

_term = Group(_factor + ZeroOrMore(Suppress(_and_op) + _factor))(TERM)

_selection_expression = Group(_term + ZeroOrMore(Suppress(_or_op) + _term))(
    SELECTION_EXPRESSION
)

_selection << (_l_paren + _selection_expression + _r_paren)(SELECTION)

_dihedral_restraint = Group(
    Suppress(_expand_literal(ASSIGN))
    + _selection.set_results_name(ATOMS_1)
    + _selection.set_results_name(ATOMS_2)
    + _selection.set_results_name(ATOMS_3)
    + _selection.set_results_name(ATOMS_4)
    + ppc.number.set_results_name(ENERGY_CONSTANT).setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name(ANGLE).setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name(RANGE).setParseAction(ppc.convertToFloat)
    + ppc.integer.set_results_name(EXPONENT).setParseAction(ppc.convertToInteger)
)
_dihedral_restraints = OneOrMore(_dihedral_restraint)

_distance_restraint = Group(
    Suppress(_expand_literal(ASSIGN))
    + _selection.set_results_name(ATOMS_1)
    + _selection.set_results_name(ATOMS_2)
    + ppc.number.set_results_name(DISTANCE).setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name(DISTANCE_MINUS).setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name(DISTANCE_PLUS).setParseAction(ppc.convertToFloat)
    + rest_of_line.set_results_name(EXTRA_INFO)
)

_distance_restraints = OneOrMore(_distance_restraint)


def _remove_xplor_comments(data_lines: List[str]) -> List[str]:
    result = []
    for data_line in data_lines:
        if XPLOR_COMMENT_TOKEN in data_line:
            comment_start = data_line.index(XPLOR_COMMENT_TOKEN)
            new_line = data_line[:comment_start]
            result.append(new_line)
        else:
            result.append(data_line)
    return result


def _get_single_atom_selection(
    parsed: ParseResults,
    residue_types: Dict[Tuple[str, str], str],
    default_chain_code: str = "A",
) -> AtomLabel:
    result = None
    valid = True
    invalid_reason = ""

    selections = _parse_result_to_atom_selections(parsed)

    selection = None
    if len(selections) != 1:
        valid = False
        invalid_reason = f"there should only be one selection i got {selections}"
    else:
        selection = selections[0]

    if valid:
        sequence_code = selection.get("resids", None)
        if sequence_code is None:
            valid = False
            invalid_reason = f"there is no sequence code in {selection}"
        elif len(sequence_code) != 1:
            valid = False
            invalid_reason = f"there is more than one sequence code in {selection}"
        else:
            sequence_code = sequence_code[0].token

    if valid:
        atom_name = selection.get("atoms", None)
        if atom_name is None:
            valid = False
            invalid_reason = f"there is no atom name in {selection}"
        elif len(atom_name) != 1:
            valid = False
            invalid_reason = f"there is more than one atom name in {selection}"
        else:
            atom_name = atom_name[0].token

    if valid:
        chain_code = selection.get("segids", None)
        if chain_code is None:
            chain_code = default_chain_code
        elif len(chain_code) > 1:
            valid = False
            invalid_reason = f"there is more than one chain code in {selection}"
        elif len(chain_code) == 1:
            chain_code = chain_code[0].token

    if valid:
        residue_type_key = chain_code, str(sequence_code)
        if residue_type_key in residue_types:
            residue_type = residue_types[residue_type_key]
        else:
            valid = False
            residue_type = None
            # TODO print out sequence...
            invalid_reason = f"""the residue type for chain code: {chain_code} sequence code {sequence_code} is not
                                 known, check this residue is present in you input sequence!"""

    if valid:
        residue = SequenceResidue(chain_code, sequence_code, residue_type)
        result = AtomLabel(residue, atom_name)

    if not valid:
        raise XPLORParseException(
            f"Couldn't get a single restraint from {parsed} \n because {invalid_reason}"
        )

    return result


def read_distance_restraints_or_exit_error(
    file_path: Path,
    residue_name_lookup: Dict[Tuple[str, str], str],
    chain_code: str,
    use_chains: bool = False,
) -> List[DihedralRestraint]:
    """
    read a list of dihedral restraints from a file or stream or exit

    :param file_path: the path of the file Path('-') indicates stdin
    :param residue_name_lookup:  a dictionary of residue names keys on chain_code, residue_code
    :param chain_code: a chain code to use if no chain code is specified or use_chains is True
    :param use_chains: use the passed in chain_code rather than any read segids
    :return: a list of dihedral restraints
    """

    restraint_text = read_from_file_or_exit(
        file_path, f"xplor distance restraints from {file_path}"
    )

    file_path_display_name = get_display_file_name(file_path)

    try:
        restraints = parse_distance_restraints(
            restraint_text,
            residue_name_lookup,
            file_path_display_name,
            chain_code,
            use_chains,
        )
    except XPLORParseException as e:
        exit_error("there was an error", e)

    return restraints


def distance_restraints_to_nef(
    restraints: List[DistanceRestraint], frame_name: str
) -> Saveframe:
    """
    convert a list of DistanceRestraints to a new distance restraint save frame
    :param restraints: the restraints
    :param frame_name: the name of the new save frame
    :return: a new save frame
    """
    loop = Loop.from_scratch(category="nef_distance_restraint")

    have_comments = False
    for restraint in restraints:
        if restraint.comment is not None:
            have_comments = True
            break

    for tag in DISTANCE_RESTRAINT_TAGS:
        loop.add_tag(tag)

    if have_comments:
        loop.add_tag(CCPN_COMMENT)

    for i, restraint in enumerate(restraints, start=1):
        selection_1 = restraint.atom_list_1[0]
        selection_2 = restraint.atom_list_2[0]
        d = restraint.target_distance
        d_minus = restraint.distance_minus
        d_plus = restraint.distance_plus
        comment = (
            restraint.comment
            if restraint.comment is not None or restraint.comment != ""
            else UNUSED
        )
        row = {
            INDEX: i,
            RESTRAINT_ID: i,
            RESTRAINT_COMBINATION_ID: UNUSED,
            CHAIN_CODE_1: selection_1.residue.chain_code,
            SEQUENCE_CODE_1: selection_1.residue.sequence_code,
            ATOM_1: selection_1.atom_name,
            CHAIN_CODE_2: selection_2.residue.chain_code,
            SEQUENCE_CODE_2: selection_2.residue.sequence_code,
            ATOM_2: selection_2.atom_name,
            WEIGHT: 1.0,
            TARGET_VALUE: round(d, DEFAULT_PRECISION),
            LOWER_LIMIT: round(d_minus, DEFAULT_PRECISION),
            UPPER_LIMIT: round(d_plus, DEFAULT_PRECISION),
        }

        if have_comments:
            row[CCPN_COMMENT] = comment

        loop.add_data([row])

    NEF_DISTANCE_RESTRAINT_LIST = "nef_distance_restraint_list"
    save_frame = create_nef_save_frame(NEF_DISTANCE_RESTRAINT_LIST, frame_name)
    save_frame.add_tag("potential_type", PotentialTypes.UNDEFINED)

    save_frame.add_loop(loop)

    return save_frame


def dihedral_restraints_to_nef(
    restraints: List[DihedralRestraint], frame_name: str
) -> Saveframe:
    """
    convert a list of DihedralRestraints to a new dihedral restraint save frame
    :param restraints: the restraints
    :param frame_name: the name of the new save frame
    :return: a new save frame
    """
    loop = Loop.from_scratch(category=NEF_DIHEDRAL_RESTRAINT)

    for tag in DIHEDRAL_RESTRAINT_TAGS:
        loop.add_tag(tag)

    for i, restraint in enumerate(restraints, start=1):
        selection_1 = restraint.atom_1
        selection_2 = restraint.atom_2
        selection_3 = restraint.atom_3
        selection_4 = restraint.atom_4
        target = restraint.target_value
        lower_limit = restraint.lower_limit
        upper_limit = restraint.upper_limit

        row = {
            INDEX: i,
            RESTRAINT_ID: i,
            RESTRAINT_COMBINATION_ID: UNUSED,
            CHAIN_CODE_1: selection_1.residue.chain_code,
            SEQUENCE_CODE_1: selection_1.residue.sequence_code,
            ATOM_1: selection_1.atom_name,
            CHAIN_CODE_2: selection_2.residue.chain_code,
            SEQUENCE_CODE_2: selection_2.residue.sequence_code,
            ATOM_2: selection_2.atom_name,
            CHAIN_CODE_3: selection_3.residue.chain_code,
            SEQUENCE_CODE_3: selection_3.residue.sequence_code,
            ATOM_3: selection_3.atom_name,
            CHAIN_CODE_4: selection_4.residue.chain_code,
            SEQUENCE_CODE_4: selection_4.residue.sequence_code,
            ATOM_4: selection_4.atom_name,
            WEIGHT: 1.0,
            TARGET_VALUE: round(target, DEFAULT_PRECISION),
            LOWER_LIMIT: round(lower_limit, DEFAULT_PRECISION),
            UPPER_LIMIT: round(upper_limit, DEFAULT_PRECISION),
        }

        loop.add_data([row])

    NEF_DIHEDRAL_RESTRAINT_LIST = "nef_dihedral_restraint_list"
    save_frame = create_nef_save_frame(NEF_DIHEDRAL_RESTRAINT_LIST, frame_name)
    save_frame.add_tag("potential_type", PotentialTypes.UNDEFINED)

    save_frame.add_loop(loop)

    return save_frame


def _get_approximate_restraint_strings(text: str) -> List[str]:

    new_lines = []
    for line in text.split("\n"):
        if XPLOR_COMMENT_TOKEN in line:
            new_line = line.split(XPLOR_COMMENT_TOKEN)[0]
            if len(new_line.strip()) > 0:
                new_lines.append(new_line)
        else:
            new_lines.append(line)

    new_lines = "\n".join(new_lines)

    restraints = list(_expand_literal(ASSIGN).split(new_lines))

    if restraints[0] == "":
        restraints = restraints[1:]

    return [f"{ASSIGN} {restraint}" for restraint in restraints]


def read_dihedral_restraints_or_exit_error(
    file_path: Path,
    residue_name_lookup: Dict[Tuple[str, str], str],
    chain_code: str,
    use_chains: bool = False,
) -> List[DihedralRestraint]:
    """
    read a list of dihedral restraints from a file or stream or exit

    :param file_path: the path of the file Path('-') indicates stdin
    :param residue_name_lookup:  a dictionary of residue names keys on chain_code, residue_code
    :param chain_code: a chain code to use if no chain code is specified or use_chains is True
    :param use_chains: use the passed in chain_code rather than any read segids
    :return: a list of dihedral restraints
    """

    restraint_text = read_from_file_or_exit(
        file_path, f"xplor dihedral restraints from {file_path}"
    )

    file_path_display_name = get_display_file_name(file_path)

    restraints = parse_dihedral_restraints(
        restraint_text,
        residue_name_lookup,
        file_path_display_name,
        chain_code,
        use_chains,
    )

    return restraints


def parse_dihedral_restraints(
    restraint_text: str,
    residue_name_lookup: Dict[Tuple[str, str], str],
    file_path_display_name: str,
    chain_code: str,
    use_chains: bool = False,
) -> List[DihedralRestraint]:
    """
    parse xplor dihedral restraints into DihedralRestraint structures

    :param restraint_text: the text of the restraints in xplor format
    :param residue_name_lookup: a lookup for residue names from a  chain_code, residue_code key
    :param file_path_display_name: the source of the restraints for error reporting
    :param chain_code: a chain code to use for the restraints if non is provided or use_chains is true
    :param use_chains: use the passed in chain_code rather than any read segids
    :return:  a list of dihedral restraints
    """
    try:
        xplor_basic_restraints = _dihedral_restraints.ignore(XPLOR_COMMENT).parseString(
            restraint_text
        )
    except ParseException as parse_exception:
        msg = f"""\
            failed to read dihedral restraints from the file {file_path_display_name} because:
            {str(parse_exception)}
        """
        exit_error(msg)

    restraints = []
    for i, restraint in enumerate(xplor_basic_restraints, start=1):

        atom_selections = []

        for atom_index in range(1, 5):

            xplor_atoms = restraint.get(f"atoms_{atom_index}")[0]

            try:
                nef_atoms = _get_single_atom_selection(
                    xplor_atoms, residue_name_lookup, chain_code
                )

            except XPLORParseException as e:
                atom_number = end_with_ordinal(atom_index)
                approximate_restraints = _get_approximate_restraint_strings(
                    restraint_text
                )
                approximate_restraint = approximate_restraints[i - 1]
                approximate_restraint = approximate_restraint.split("\n")
                msg = f"""\
                    got a multi atom selection for the {atom_number} atom in restraint number {i}
                    in {file_path_display_name}
                    dihedral restraints require single atom selections...
                    the restraint text is most probably:
                """
                msg = dedent(msg)
                for elem in approximate_restraint:
                    msg += f"    {elem}\n"
                exit_error(msg, e)

            atom_selections.append(nef_atoms)

        if use_chains and chain_code != ANY_CHAIN:
            atom_selections = replace_chain_in_atom_labels(atom_selections, chain_code)

        target_angle = restraint.get(ANGLE)
        angle_range = restraint.get(RANGE)
        lower_limit = target_angle - angle_range
        upper_limit = target_angle + angle_range

        restraint = DihedralRestraint(
            *atom_selections,
            target_value=target_angle,
            lower_limit=lower_limit,
            upper_limit=upper_limit,
        )

        restraints.append(restraint)
    return restraints


def parse_distance_restraints(
    restraint_text: str,
    residue_name_lookup: Dict[Tuple[str, str], str],
    file_path_display_name: str,
    chain_code: str,
    use_chains: bool = False,
) -> List[DistanceRestraint]:
    """
    parse xplor distance restraints into DistanceRestraint structures

    :param restraint_text: the text of the restraints in xplor format
    :param residue_name_lookup: a lookup for residue names from a  chain_code, residue_code key
    :param file_path_display_name: the source of the restraints for error reporting
    :param chain_code: a chain code to use for the restraints if non is provided or use_chains is true
    :param use_chains: use the passed in chain_code rather than any read segids
    :return:  a list of dihedral restraints
    """
    try:
        xplor_basic_restraints = _distance_restraints.ignore(XPLOR_COMMENT).parseString(
            restraint_text
        )
    except ParseException as parse_exception:
        msg = f"""\
            failed to read distance restraints from the file {file_path_display_name} because:
            {str(parse_exception)}
        """
        exit_error(msg)

    restraints = []
    for i, restraint in enumerate(xplor_basic_restraints, start=1):

        atom_selections = []

        for atom_index in range(1, 3):

            xplor_atoms = restraint.get(f"atoms_{atom_index}")[0]

            try:
                nef_atoms = _get_single_atom_selection(
                    xplor_atoms, residue_name_lookup, chain_code
                )

            except XPLORParseException as e:
                atom_number = end_with_ordinal(atom_index)
                approximate_restraints = _get_approximate_restraint_strings(
                    restraint_text
                )
                approximate_restraint = approximate_restraints[i - 1]
                approximate_restraint = approximate_restraint.split("\n")
                msg = f"""\
                    got a multi atom selection for the {atom_number} atom in restraint number {i}
                    in {file_path_display_name}
                    dihedral restraints require single atom selections...
                    the restraint text is most probably:
                """
                msg = dedent(msg)
                for elem in approximate_restraint:
                    msg += f"    {elem}\n"
                exit_error(msg, e)

            atom_selections.append(nef_atoms)

        if use_chains and chain_code != ANY_CHAIN:
            atom_selections = replace_chain_in_atom_labels(atom_selections, chain_code)

        target_distance = restraint.get(DISTANCE)
        distance_minus = restraint.get(DISTANCE_MINUS)
        distance_plus = restraint.get(DISTANCE_PLUS)
        comment = restraint.get(EXTRA_INFO).strip()
        if comment == "":
            comment = None

        atom_selections = [[atom_selection] for atom_selection in atom_selections]
        restraint = DistanceRestraint(
            *atom_selections,
            target_distance=target_distance,
            distance_minus=target_distance - distance_minus,
            distance_plus=target_distance + distance_plus,
            comment=comment,
        )

        restraints.append(restraint)

    return restraints


#
#
# if __name__ == "__main__":
#
#     # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_BBBB_AAAA.tbl') as fh:
#     # # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA_BBBB.tbl') as fh:
#     # # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA.tbl') as fh:
#     #     lines = fh.readlines()
#     #
#     #     lines = remove_xplor_comments(lines)
#     #     lines = ''.join(lines)
#     #
#     #     xplor_basic_restraints = distance_restraints.parseString(lines)
#     #
#     #     restraints = []
#     #     for restraint in xplor_basic_restraints:
#     #         atoms_1 = restraint.get('atoms_1')
#     #         atoms_2 = restraint.get('atoms_2')
#     #         d = restraint.get('d')
#     #         d_minus = restraint.get('d_minus')
#     #         d_plus = restraint.get('d_plus')
#     #
#     #         residue_types = {('AAAA', i): 'ALA' for i in range(1, 1000)}
#     #         residue_types.update({('BBBB', i): 'ALA' for i in range(1, 1000)})
#     #
#     #         selection_1 = get_single_atom_selection(atoms_1, residue_types)
#     #         selection_2 = get_single_atom_selection(atoms_2, residue_types)
#     #
#     #         distance_restraint = DistanceRestraint(atom_list_1 =[selection_1], atom_list_2 =[selection_2],
#                                                      distance = d, distance_minus=d_minus, distance_plus=d_plus)
#     #
#     #         restraints.append(distance_restraint)
#     #
#     #     offset = 44
#     #     for restraint in restraints:
#     #         print(restraint)
#     #         selection_1 = restraint.atom_list_1[0]
#     #         selection_2 = restraint.atom_list_2[0]
#     #
#     #         if selection_1.residue.chain_code == 'AAAA':
#     #             residue_1 = replace(selection_1.residue, sequence_code=selection_1.residue.sequence_code + offset)
#     #             selection_1 = replace(selection_1, residue=residue_1)
#     #
#     #         if selection_2.residue.chain_code == 'AAAA':
#     #             residue_2 = replace(selection_2.residue, sequence_code=selection_2.residue.sequence_code + offset)
#     #             selection_2 = replace(selection_2, residue=residue_2)
#     #
#     #         restraint.atom_list_1[0] = selection_1
#     #         restraint.atom_list_2[0] = selection_2
#     #
#     #     loop = restraints_to_nef(restraints)
#     # print(loop)
#     #
#     # rows = []
#     # for nef_row in loop_row_namespace_iter(loop, convert=False):
#     #     segid_1 = nef_row.chain_code_1
#     #     resid_1 = nef_row.sequence_code_1
#     #     name_1 = nef_row.atom_name_1
#     #     selection_1 = '(', 'segid',  segid_1,  'and',  'resid',  resid_1, 'and', 'name',  name_1, ')'
#     #
#     #     segid_2 = nef_row.chain_code_2
#     #     resid_2 = nef_row.sequence_code_2
#     #     name_2 = nef_row.atom_name_2
#     #     selection_2 = '(', 'segid',  segid_2,  'and',  'resid',  resid_2, 'and', 'name',  name_2, ')'
#     #
#     #     d = nef_row.target_value
#     #     d_minus = d - nef_row.lower_limit
#     #     d_plus = nef_row.upper_limit - d
#     #
#     #     row = ['assign', *selection_1, *selection_2, d, d_minus, d_plus]
#     #
#     #     rows.append(row)
#     #
#     # table = tabulate(rows, tablefmt='plain', floatfmt="7.3f")
#     # table = table.replace('assign  ', 'assign ')
#     # table = table.replace('(  ', '(')
#     # table = table.replace('  )', ')')
#     # table = table.replace('   )', ')   ')
#     # table = table.replace('  )', ')  ')
#     # table = table.replace(' )', ') ')
#     # table = table.replace('  and  ', ' and ')
#     # table = table.replace('segid  ', 'segid ')
#     # table = table.replace('resid  ', 'resid ')
#     # table = table.replace('name  ', 'name ')
#     #
#     # print(table)
#
#     with open("src/nef_pipelines/tests/xplor/test_data/dihedrals_S135A_AAAA.tbl") as fh:
#         # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA_BBBB.tbl') as fh:
#         # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA.tbl') as fh:
#         lines = fh.readlines()
#
#         lines = remove_xplor_comments(lines)
#         lines = "".join(lines)
#
#         xplor_basic_restraints = dihedral_restraints.parseString(lines)
#
#         restraints = []
#
#         for restraint in xplor_basic_restraints:
#             atoms_1 = restraint.get("atoms_1")
#             atoms_2 = restraint.get("atoms_2")
#             atoms_3 = restraint.get("atoms_3")
#             atoms_4 = restraint.get("atoms_4")
#
#             target_angle = restraint.get("angle")
#             angle_range = restraint.get("range")
#             lower_limit = target_angle - angle_range
#             upper_limit = target_angle + angle_range
#
#             residue_types = {("AAAA", i): "ALA" for i in range(1, 1000)}
#             residue_types.update({("BBBB", i): "ALA" for i in range(1, 1000)})
#
#             selection_1 = get_single_atom_selection(atoms_1, residue_types)
#             selection_2 = get_single_atom_selection(atoms_2, residue_types)
#             selection_3 = get_single_atom_selection(atoms_3, residue_types)
#             selection_4 = get_single_atom_selection(atoms_4, residue_types)
#
#             dihedral_restraint = DihedralRestraint(
#                 atom_list_1=[selection_1],
#                 atom_list_2=[selection_2],
#                 atom_list_3=[selection_3],
#                 atom_list_4=[selection_4],
#                 target=target_angle,
#                 lower_limit=lower_limit,
#                 upper_limit=upper_limit,
#             )
#
#             restraints.append(dihedral_restraint)
#
#         offset = 44
#         for restraint in restraints:
#
#             selection_1 = restraint.atom_list_1[0]
#             selection_2 = restraint.atom_list_2[0]
#             selection_3 = restraint.atom_list_3[0]
#             selection_4 = restraint.atom_list_4[0]
#
#             if selection_1.residue.chain_code == "AAAA":
#                 residue_1 = replace(
#                     selection_1.residue,
#                     sequence_code=selection_1.residue.sequence_code + offset,
#                 )
#                 selection_1 = replace(selection_1, residue=residue_1)
#
#             if selection_2.residue.chain_code == "AAAA":
#                 residue_2 = replace(
#                     selection_2.residue,
#                     sequence_code=selection_2.residue.sequence_code + offset,
#                 )
#                 selection_2 = replace(selection_2, residue=residue_2)
#
#             if selection_3.residue.chain_code == "AAAA":
#                 residue_3 = replace(
#                     selection_3.residue,
#                     sequence_code=selection_3.residue.sequence_code + offset,
#                 )
#                 selection_3 = replace(selection_3, residue=residue_3)
#
#             if selection_4.residue.chain_code == "AAAA":
#                 residue_4 = replace(
#                     selection_4.residue,
#                     sequence_code=selection_4.residue.sequence_code + offset,
#                 )
#                 selection_4 = replace(selection_4, residue=residue_4)
#
#             restraint.atom_list_1[0] = selection_1
#             restraint.atom_list_2[0] = selection_2
#             restraint.atom_list_3[0] = selection_3
#             restraint.atom_list_4[0] = selection_4
#
#         loop = dihedral_restraints_to_nef(restraints)
#     # print(loop)
#     #
#     rows = []
#     for nef_row in loop_row_namespace_iter(loop, convert=False):
#         segid_1 = nef_row.chain_code_1
#         resid_1 = nef_row.sequence_code_1
#         name_1 = nef_row.atom_name_1
#         selection_1 = (
#             "(",
#             "segid",
#             segid_1,
#             "and",
#             "resid",
#             resid_1,
#             "and",
#             "name",
#             name_1,
#             ")",
#         )
#
#         segid_2 = nef_row.chain_code_2
#         resid_2 = nef_row.sequence_code_2
#         name_2 = nef_row.atom_name_2
#         selection_2 = (
#             "(",
#             "segid",
#             segid_2,
#             "and",
#             "resid",
#             resid_2,
#             "and",
#             "name",
#             name_2,
#             ")",
#         )
#
#         segid_3 = nef_row.chain_code_3
#         resid_3 = nef_row.sequence_code_3
#         name_3 = nef_row.atom_name_3
#         selection_3 = (
#             "(",
#             "segid",
#             segid_3,
#             "and",
#             "resid",
#             resid_3,
#             "and",
#             "name",
#             name_3,
#             ")",
#         )
#
#         segid_4 = nef_row.chain_code_4
#         resid_4 = nef_row.sequence_code_4
#         name_4 = nef_row.atom_name_4
#         selection_4 = (
#             "(",
#             "segid",
#             segid_4,
#             "and",
#             "resid",
#             resid_4,
#             "and",
#             "name",
#             name_4,
#             ")",
#         )
#
#         target = nef_row.target_value
#         range_1 = round(target - nef_row.lower_limit, 5)
#         range_2 = round(nef_row.upper_limit - target, 5)
#
#         row_1 = ["assign", *selection_1, *selection_2, " ", " ", " ", " "]
#         row_2 = ["     ", *selection_3, *selection_4, 1.0, target, range_1, 2]
#
#         rows.append(row_1)
#         rows.append(row_2)
#
#     table = tabulate(rows, tablefmt="plain", floatfmt="7.3f")
#     table = table.replace("assign  ", "assign ")
#     table = table.replace("        (segid", "       (segid")
#     table = table.replace("(  ", "(")
#     table = table.replace("  )", ")")
#     table = table.replace("   )", ")   ")
#     table = table.replace("  )", ")  ")
#     table = table.replace(" )", ") ")
#     table = table.replace("  and  ", " and ")
#     table = table.replace("segid  ", "segid ")
#     table = table.replace("resid  ", "resid ")
#     table = table.replace("name  ", "name ")
#     table = table.replace("        (segid", "       (segid")
#
#     print(table)


def _drill_down_0(selection):
    result = []
    target = selection
    while isinstance(target, (ParseResults, _NamedToken)) and len(target) > 0:
        result.append(target.get_name())
        target = target[0]
    return result


def _get_selection_expressions_from_selection(
    selection: ParseResults, selection_text
) -> List[ParseResults]:
    drill_down = _drill_down_0(selection)

    result = []
    if len(drill_down) >= 4:
        if drill_down[0:3] == ["selection", "selection-expression", "term"]:

            term_names = set([term.get_name() for term in selection[0][0]])
            atom_selection_names = {"segid", "resid", "atom"}
            atom_selection_term_names = term_names.intersection(atom_selection_names)

            if (
                len(term_names) == 1
                and next(iter(term_names)) == "selection-expression"
            ):
                for elem in selection[0]:
                    result.append(elem[0])

            elif len(atom_selection_term_names) > 0:
                result.append(selection[0])
            else:
                msg = f"""\
                   selection error

                   selections must contain selections at the first or  second level, so they should look something
                   like this :
                       (<selection-1>)
                   or  ((<selection-1>) OR (<selection-2>)...) etc

                   where the terms  might be something like
                       segid ZZZZ resid 2 and name HA
                       segid XXXX resid 1 and name HN

                   i got a selection that wasn't in this format {selection_text}

                   value was: {_selection_expression}
                """
                raise XPLORParseException(msg)
    elif (
        len(drill_down) == 3
        and drill_down[0] == "selection-expression"
        and len(selection) == 1
    ):
        result = [selection]

    return result


def _get_atom_selections_from_selection_expression(selection_expression: ParseResults):

    if not selection_expression.get_name() == "selection-expression":
        msg = f"""\
            i expected a <selection-expression> but got a <{selection_expression.get_name()}>

            a selection expression should look something like

            (segid  AAAA and resid 1 and name HA)

            input value was: {selection_expression} [this is not what you entered but the parse result for debugging]

        """
        raise XPLORParseException(msg)

    result = {}
    for term in selection_expression:
        if term.get_name() == "term":
            for elem in term:
                elem_name = elem.get_name()

                if elem_name in ("segid", "resid", "atom"):
                    result.setdefault(f"{elem_name}s", []).append(elem)
                elif elem_name == "selection-expression":

                    sub_terms = _get_atom_selections_from_selection_expression(elem)

                    for sub_term_name, sub_term in sub_terms.items():
                        result[sub_term_name] = sub_term

        else:
            raise XPLORParseException(
                f"implementation error unexpected element type {elem_name} found in {selection_expression}"
            )

    return result


def _string_to_atom_selections(selection_text):
    parse_result = _selection.parseString(selection_text, parse_all=True)

    return _parse_result_to_atom_selections(parse_result)


def _parse_result_to_atom_selections(parse_result):
    selections = _get_selection_expressions_from_selection(
        parse_result, str(parse_result)
    )
    return [
        _get_atom_selections_from_selection_expression(selection_expression)
        for selection_expression in selections
    ]


def _exit_if_chains_and_filenames_dont_match(chains, file_names):
    num_file_names = len(file_names)
    num_chains = len(chains)
    if num_file_names != num_chains:
        msg = f"""\
            your provided {num_file_names} files and {num_chains} chains
            there must be a filename for each chain you provide
            file names were: {','.join(file_names)}
            chains were: {','.join(chains)}
        """
        msg = dedent(msg)
        exit_error(msg)
