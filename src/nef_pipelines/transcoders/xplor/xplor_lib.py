from dataclasses import replace
from typing import Dict, List, Tuple

from pynmrstar import Loop
from pyparsing import (
    CaselessLiteral,
    Combine,
    Forward,
    Group,
    Literal,
    OneOrMore,
    Optional,
    Or,
    ParseResults,
    Regex,
    Suppress,
    Word,
    ZeroOrMore,
    alphanums,
    nums,
)
from pyparsing.common import pyparsing_common as ppc
from tabulate import tabulate

from nef_pipelines.lib.nef_lib import UNUSED, loop_row_namespace_iter
from nef_pipelines.lib.structures import AtomLabel, DihedralRestraint, SequenceResidue

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

XPLOR_COMMENT = Regex(r"!.*").set_name("Xplor comment")

DEFAULT_PRECISION = 5
INDEX = "index"
RESTRAINT_ID = "restraint_id"
RESTRAINT_COMBINATION_ID = "restraint_combination_id"
CHAIN_CODE_1 = "chain_code_1"
SEQUENCE_CODE_1 = "sequence_code_1"
RESIDUE_NAME_1 = "residue_name_1"
ATOM_NAME_1 = "atom_name_1"
CHAIN_CODE_2 = "chain_code_2"
SEQUENCE_CODE_2 = "sequence_code_2"
RESIDUE_NAME_2 = "residue_name_2"
ATOM_NAME_2 = "atom_name_2"
CHAIN_CODE_3 = "chain_code_3"
SEQUENCE_CODE_3 = "sequence_code_3"
RESIDUE_NAME_3 = "residue_name_3"
ATOM_NAME_3 = "atom_name_3"
CHAIN_CODE_4 = "chain_code_4"
SEQUENCE_CODE_4 = "sequence_code_4"
RESIDUE_NAME_4 = "residue_name_4"
ATOM_NAME_4 = "atom_name_4"
WEIGHT = "weight"
TARGET_VALUE = "target_value"
LOWER_LIMIT = "lower_limit"
UPPER_LIMIT = "upper_limit"

DISTANCE_RESTRAINT_TAGS = [
    INDEX,
    RESTRAINT_ID,
    RESTRAINT_COMBINATION_ID,
    CHAIN_CODE_1,
    SEQUENCE_CODE_1,
    RESIDUE_NAME_1,
    ATOM_NAME_1,
    CHAIN_CODE_2,
    SEQUENCE_CODE_2,
    RESIDUE_NAME_2,
    ATOM_NAME_2,
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
    ATOM_NAME_1,
    CHAIN_CODE_2,
    SEQUENCE_CODE_2,
    RESIDUE_NAME_2,
    ATOM_NAME_2,
    CHAIN_CODE_3,
    SEQUENCE_CODE_3,
    RESIDUE_NAME_3,
    ATOM_NAME_3,
    CHAIN_CODE_4,
    SEQUENCE_CODE_4,
    RESIDUE_NAME_4,
    ATOM_NAME_4,
    WEIGHT,
    TARGET_VALUE,
    LOWER_LIMIT,
    UPPER_LIMIT,
]


class XPLORParseException(Exception):
    ...


and_op = CaselessLiteral("and")
or_op = CaselessLiteral("or")

l_paren = Suppress("(")
r_paren = Suppress(")")


def expand_literal(literal, min_length=4, case_insenitive=True):
    result = []
    for i in range(min_length, len(literal) + 1):
        elem = CaselessLiteral(literal[:i]) if case_insenitive else Literal(literal[:i])
        result.append(elem)

    result.reverse()

    return Or(result)


def convert_to_4_letter_string(string: str) -> str:
    result = string
    if string_len := len(string) < 4:
        result += " " * (4 - string_len)

    return result


# resid factor
residue_literal = Suppress(expand_literal("residue"))
residue_number = (
    Combine((Optional("-") + Word(nums)))
    .set_results_name("residue_number", list_all_matches=True)
    .setParseAction(ppc.convert_to_integer)
)
residue_factor = residue_literal + residue_number

# atom factor
atom_literal = Suppress(CaselessLiteral("name"))
atom_label = Word(alphanums + "*%#+").set_results_name(
    "atom_name", list_all_matches=True
)
atom_factor = atom_literal + atom_label

# segment factor
segid_literal = Suppress(expand_literal("segidentifier"))
segid_label = Word(alphanums, max=4).set_results_name(
    "segment_id", list_all_matches=True
)
segid_factor = segid_literal + segid_label

# selection grammar including and + or
selectionOr = Forward()
selection = l_paren + selectionOr + r_paren
selection.set_results_name("selection")
extended_selection = Group(l_paren + selectionOr + r_paren)
extended_selection.set_results_name("extended_selection", list_all_matches=True)
selectionFactor = segid_factor | residue_factor | atom_factor | extended_selection
selectionAnd = selectionFactor + ZeroOrMore(Suppress(and_op) + selectionFactor)
selectionOr << Group(selectionAnd + ZeroOrMore(Suppress(or_op) + selectionAnd))
selectionOr.set_results_name("selection_or", list_all_matches=True)
selectionAnd.set_results_name("selection_and", list_all_matches=True)
selectionFactor.set_results_name("selection_factor", list_all_matches=True)

# name selection grammar parts
selection = selection.set_results_name("selection", list_all_matches=True)
selectionFactor = selectionFactor.set_results_name(
    "factors_and_groups", list_all_matches=True
)
selectionAnd = selectionAnd.set_results_name("and_group", list_all_matches=True)
selectionOr = selectionOr.set_results_name("or_group", list_all_matches=True)
selectionFactor.set_results_name("selection_factor", list_all_matches=True)
dihedral_restraint = Group(
    Suppress(expand_literal("assign"))
    + selection.set_results_name("atoms_1")
    + selection.set_results_name("atoms_2")
    + selection.set_results_name("atoms_3")
    + selection.set_results_name("atoms_4")
    + ppc.number.set_results_name("energy_constant").setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name("angle").setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name("range").setParseAction(ppc.convertToFloat)
    + ppc.integer.set_results_name("exponent").setParseAction(ppc.convertToInteger)
)
dihedral_restraints = OneOrMore(dihedral_restraint)

# d = Group(ppc.number).set_results_name('d')

distance_restraint = Group(
    Suppress(expand_literal("assign"))
    + selection.set_results_name("atoms_1")
    + selection.set_results_name("atoms_2")
    + ppc.number.set_results_name("d").setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name("d_minus").setParseAction(ppc.convertToFloat)
    + ppc.number.set_results_name("d_plus").setParseAction(ppc.convertToFloat)
)

distance_restraints = OneOrMore(distance_restraint)


def remove_xplor_comments(data_lines: List[str]) -> List[str]:
    result = []
    for data_line in data_lines:
        if "!" in data_line:
            comment_start = data_line.index("!")
            new_line = data_line[:comment_start]
            result.append(new_line)
        else:
            result.append(data_line)
    return result


def get_single_atom_selection(
    parsed: ParseResults,
    residue_types: Dict[Tuple[str, int], str],
    default_chain_code: str = "A",
) -> AtomLabel:
    result = None
    valid = True
    invalid_reason = ""

    if len(parsed) != 1:
        valid = False
        invalid_reason = f"there should only be one selection i got {parsed}"
    else:
        selection = parsed[0]

    if valid:
        sequence_code = selection.get("residue_number")
        if sequence_code is None:
            valid = False
            invalid_reason = f"there is no sequence code in {parsed}"
        elif len(sequence_code) != 1:
            valid = False
            invalid_reason = f"there is more than one sequence code in {parsed}"
        else:
            sequence_code = sequence_code[0]

    if valid:
        atom_name = selection.get("atom_name")
        if atom_name is None:
            valid = False
            invalid_reason = f"there is no atom name in {parsed}"
        elif len(atom_name) != 1:
            valid = False
            invalid_reason = f"there is more than one atom name in {parsed}"
        else:
            atom_name = atom_name[0]

    if valid:
        chain_code = selection.get("segment_id")
        if chain_code is None:
            chain_code = default_chain_code
        elif len(chain_code) > 1:
            valid = False
            invalid_reason = f"there is more than one chain code in {parsed}"
        elif len(chain_code) == 1:
            chain_code = chain_code[0]

    if valid:
        residue_type_key = chain_code, sequence_code
        if residue_type_key in residue_types:
            residue_type = residue_types[residue_type_key]
        else:
            valid = False
            residue_type = None
            invalid_reason = f"the residue type for chain code: {chain_code} sequence code {sequence_code} is not known"

    if valid:
        residue = SequenceResidue(chain_code, sequence_code, residue_type)
        result = AtomLabel(residue, atom_name)

    if not result:
        raise XPLORParseException(
            f"Couldn't get a single restraint from {parsed} because {invalid_reason}"
        )

    return result


def restraints_to_nef(restraints):
    loop = Loop.from_scratch(category="nef_distance_restraint")

    for tag in DISTANCE_RESTRAINT_TAGS:
        loop.add_tag(tag)

    for i, restraint in enumerate(restraints, start=1):
        selection_1 = restraint.atom_list_1[0]
        selection_2 = restraint.atom_list_2[0]
        d = restraint.distance
        d_minus = restraint.distance_minus
        d_plus = restraint.distance_plus

        row = {
            INDEX: i,
            RESTRAINT_ID: i,
            RESTRAINT_COMBINATION_ID: UNUSED,
            CHAIN_CODE_1: selection_1.residue.chain_code,
            SEQUENCE_CODE_1: selection_1.residue.sequence_code,
            ATOM_NAME_1: selection_1.atom_name,
            CHAIN_CODE_2: selection_2.residue.chain_code,
            SEQUENCE_CODE_2: selection_2.residue.sequence_code,
            ATOM_NAME_2: selection_2.atom_name,
            WEIGHT: 1.0,
            TARGET_VALUE: round(d, DEFAULT_PRECISION),
            LOWER_LIMIT: round(d - d_minus, DEFAULT_PRECISION),
            UPPER_LIMIT: round(d + d_plus, DEFAULT_PRECISION),
        }

        # print(row)
        loop.add_data([row])

    return loop


def dihedral_restraints_to_nef(restraints):
    loop = Loop.from_scratch(category="nef_ddihedral_restraint")

    for tag in DIHEDRAL_RESTRAINT_TAGS:
        loop.add_tag(tag)

    for i, restraint in enumerate(restraints, start=1):
        selection_1 = restraint.atom_list_1[0]
        selection_2 = restraint.atom_list_2[0]
        selection_3 = restraint.atom_list_3[0]
        selection_4 = restraint.atom_list_4[0]
        target = restraint.target
        lower_limit = restraint.lower_limit
        upper_limit = restraint.upper_limit

        row = {
            INDEX: i,
            RESTRAINT_ID: i,
            RESTRAINT_COMBINATION_ID: UNUSED,
            CHAIN_CODE_1: selection_1.residue.chain_code,
            SEQUENCE_CODE_1: selection_1.residue.sequence_code,
            ATOM_NAME_1: selection_1.atom_name,
            CHAIN_CODE_2: selection_2.residue.chain_code,
            SEQUENCE_CODE_2: selection_2.residue.sequence_code,
            ATOM_NAME_2: selection_2.atom_name,
            CHAIN_CODE_3: selection_3.residue.chain_code,
            SEQUENCE_CODE_3: selection_3.residue.sequence_code,
            ATOM_NAME_3: selection_3.atom_name,
            CHAIN_CODE_4: selection_4.residue.chain_code,
            SEQUENCE_CODE_4: selection_4.residue.sequence_code,
            ATOM_NAME_4: selection_4.atom_name,
            WEIGHT: 1.0,
            TARGET_VALUE: round(target, DEFAULT_PRECISION),
            LOWER_LIMIT: round(lower_limit, DEFAULT_PRECISION),
            UPPER_LIMIT: round(upper_limit, DEFAULT_PRECISION),
        }

        loop.add_data([row])

    return loop


if __name__ == "__main__":

    # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_BBBB_AAAA.tbl') as fh:
    # # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA_BBBB.tbl') as fh:
    # # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA.tbl') as fh:
    #     lines = fh.readlines()
    #
    #     lines = remove_xplor_comments(lines)
    #     lines = ''.join(lines)
    #
    #     xplor_basic_restraints = distance_restraints.parseString(lines)
    #
    #     restraints = []
    #     for restraint in xplor_basic_restraints:
    #         atoms_1 = restraint.get('atoms_1')
    #         atoms_2 = restraint.get('atoms_2')
    #         d = restraint.get('d')
    #         d_minus = restraint.get('d_minus')
    #         d_plus = restraint.get('d_plus')
    #
    #         residue_types = {('AAAA', i): 'ALA' for i in range(1, 1000)}
    #         residue_types.update({('BBBB', i): 'ALA' for i in range(1, 1000)})
    #
    #         selection_1 = get_single_atom_selection(atoms_1, residue_types)
    #         selection_2 = get_single_atom_selection(atoms_2, residue_types)
    #
    #         distance_restraint = DistanceRestraint(atom_list_1 =[selection_1], atom_list_2 =[selection_2],distance = d
    #                                                ,distance_minus=d_minus, distance_plus=d_plus)
    #
    #         restraints.append(distance_restraint)
    #
    #     offset = 44
    #     for restraint in restraints:
    #         print(restraint)
    #         selection_1 = restraint.atom_list_1[0]
    #         selection_2 = restraint.atom_list_2[0]
    #
    #         if selection_1.residue.chain_code == 'AAAA':
    #             residue_1 = replace(selection_1.residue, sequence_code=selection_1.residue.sequence_code + offset)
    #             selection_1 = replace(selection_1, residue=residue_1)
    #
    #         if selection_2.residue.chain_code == 'AAAA':
    #             residue_2 = replace(selection_2.residue, sequence_code=selection_2.residue.sequence_code + offset)
    #             selection_2 = replace(selection_2, residue=residue_2)
    #
    #         restraint.atom_list_1[0] = selection_1
    #         restraint.atom_list_2[0] = selection_2
    #
    #     loop = restraints_to_nef(restraints)
    # print(loop)
    #
    # rows = []
    # for nef_row in loop_row_namespace_iter(loop, convert=False):
    #     segid_1 = nef_row.chain_code_1
    #     resid_1 = nef_row.sequence_code_1
    #     name_1 = nef_row.atom_name_1
    #     selection_1 = '(', 'segid',  segid_1,  'and',  'resid',  resid_1, 'and', 'name',  name_1, ')'
    #
    #     segid_2 = nef_row.chain_code_2
    #     resid_2 = nef_row.sequence_code_2
    #     name_2 = nef_row.atom_name_2
    #     selection_2 = '(', 'segid',  segid_2,  'and',  'resid',  resid_2, 'and', 'name',  name_2, ')'
    #
    #     d = nef_row.target_value
    #     d_minus = d - nef_row.lower_limit
    #     d_plus = nef_row.upper_limit - d
    #
    #     row = ['assign', *selection_1, *selection_2, d, d_minus, d_plus]
    #
    #     rows.append(row)
    #
    # table = tabulate(rows, tablefmt='plain', floatfmt="7.3f")
    # table = table.replace('assign  ', 'assign ')
    # table = table.replace('(  ', '(')
    # table = table.replace('  )', ')')
    # table = table.replace('   )', ')   ')
    # table = table.replace('  )', ')  ')
    # table = table.replace(' )', ') ')
    # table = table.replace('  and  ', ' and ')
    # table = table.replace('segid  ', 'segid ')
    # table = table.replace('resid  ', 'resid ')
    # table = table.replace('name  ', 'name ')
    #
    # print(table)

    with open("src/nef_pipelines/tests/xplor/test_data/dihedrals_S135A_AAAA.tbl") as fh:
        # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA_BBBB.tbl') as fh:
        # with open('src/nef_pipelines/tests/xplor/test_data/noes_S135A_AAAA.tbl') as fh:
        lines = fh.readlines()

        lines = remove_xplor_comments(lines)
        lines = "".join(lines)

        xplor_basic_restraints = dihedral_restraints.parseString(lines)

        restraints = []

        for restraint in xplor_basic_restraints:
            atoms_1 = restraint.get("atoms_1")
            atoms_2 = restraint.get("atoms_2")
            atoms_3 = restraint.get("atoms_3")
            atoms_4 = restraint.get("atoms_4")

            target_angle = restraint.get("angle")
            angle_range = restraint.get("range")
            lower_limit = target_angle - angle_range
            upper_limit = target_angle + angle_range

            residue_types = {("AAAA", i): "ALA" for i in range(1, 1000)}
            residue_types.update({("BBBB", i): "ALA" for i in range(1, 1000)})

            selection_1 = get_single_atom_selection(atoms_1, residue_types)
            selection_2 = get_single_atom_selection(atoms_2, residue_types)
            selection_3 = get_single_atom_selection(atoms_3, residue_types)
            selection_4 = get_single_atom_selection(atoms_4, residue_types)

            dihedral_restraint = DihedralRestraint(
                atom_list_1=[selection_1],
                atom_list_2=[selection_2],
                atom_list_3=[selection_3],
                atom_list_4=[selection_4],
                target=target_angle,
                lower_limit=lower_limit,
                upper_limit=upper_limit,
            )

            restraints.append(dihedral_restraint)

        offset = 44
        for restraint in restraints:

            selection_1 = restraint.atom_list_1[0]
            selection_2 = restraint.atom_list_2[0]
            selection_3 = restraint.atom_list_3[0]
            selection_4 = restraint.atom_list_4[0]

            if selection_1.residue.chain_code == "AAAA":
                residue_1 = replace(
                    selection_1.residue,
                    sequence_code=selection_1.residue.sequence_code + offset,
                )
                selection_1 = replace(selection_1, residue=residue_1)

            if selection_2.residue.chain_code == "AAAA":
                residue_2 = replace(
                    selection_2.residue,
                    sequence_code=selection_2.residue.sequence_code + offset,
                )
                selection_2 = replace(selection_2, residue=residue_2)

            if selection_3.residue.chain_code == "AAAA":
                residue_3 = replace(
                    selection_3.residue,
                    sequence_code=selection_3.residue.sequence_code + offset,
                )
                selection_3 = replace(selection_3, residue=residue_3)

            if selection_4.residue.chain_code == "AAAA":
                residue_4 = replace(
                    selection_4.residue,
                    sequence_code=selection_4.residue.sequence_code + offset,
                )
                selection_4 = replace(selection_4, residue=residue_4)

            restraint.atom_list_1[0] = selection_1
            restraint.atom_list_2[0] = selection_2
            restraint.atom_list_3[0] = selection_3
            restraint.atom_list_4[0] = selection_4

        loop = dihedral_restraints_to_nef(restraints)
    # print(loop)
    #
    rows = []
    for nef_row in loop_row_namespace_iter(loop, convert=False):
        segid_1 = nef_row.chain_code_1
        resid_1 = nef_row.sequence_code_1
        name_1 = nef_row.atom_name_1
        selection_1 = (
            "(",
            "segid",
            segid_1,
            "and",
            "resid",
            resid_1,
            "and",
            "name",
            name_1,
            ")",
        )

        segid_2 = nef_row.chain_code_2
        resid_2 = nef_row.sequence_code_2
        name_2 = nef_row.atom_name_2
        selection_2 = (
            "(",
            "segid",
            segid_2,
            "and",
            "resid",
            resid_2,
            "and",
            "name",
            name_2,
            ")",
        )

        segid_3 = nef_row.chain_code_3
        resid_3 = nef_row.sequence_code_3
        name_3 = nef_row.atom_name_3
        selection_3 = (
            "(",
            "segid",
            segid_3,
            "and",
            "resid",
            resid_3,
            "and",
            "name",
            name_3,
            ")",
        )

        segid_4 = nef_row.chain_code_4
        resid_4 = nef_row.sequence_code_4
        name_4 = nef_row.atom_name_4
        selection_4 = (
            "(",
            "segid",
            segid_4,
            "and",
            "resid",
            resid_4,
            "and",
            "name",
            name_4,
            ")",
        )

        target = nef_row.target_value
        range_1 = round(target - nef_row.lower_limit, 5)
        range_2 = round(nef_row.upper_limit - target, 5)

        row_1 = ["assign", *selection_1, *selection_2, " ", " ", " ", " "]
        row_2 = ["     ", *selection_3, *selection_4, 1.0, target, range_1, 2]

        rows.append(row_1)
        rows.append(row_2)

    table = tabulate(rows, tablefmt="plain", floatfmt="7.3f")
    table = table.replace("assign  ", "assign ")
    table = table.replace("        (segid", "       (segid")
    table = table.replace("(  ", "(")
    table = table.replace("  )", ")")
    table = table.replace("   )", ")   ")
    table = table.replace("  )", ")  ")
    table = table.replace(" )", ") ")
    table = table.replace("  and  ", " and ")
    table = table.replace("segid  ", "segid ")
    table = table.replace("resid  ", "resid ")
    table = table.replace("name  ", "name ")
    table = table.replace("        (segid", "       (segid")

    print(table)
