from textwrap import dedent
from typing import Dict, Iterable, List, Tuple

from pyparsing import (
    Forward,
    Group,
    ParseException,
    ParserElement,
    ParseResults,
    Suppress,
    Word,
    ZeroOrMore,
    printables,
    restOfLine,
)

from nef_pipelines.lib.nef_lib import UNUSED
from nef_pipelines.lib.sequence_lib import get_residue_name_from_lookup
from nef_pipelines.lib.structures import (
    AtomLabel,
    SequenceResidue,
    ShiftData,
    ShiftList,
)
from nef_pipelines.lib.util import exit_error


def _process_emptys_and_singles(value: ParseResults) -> ParseResults:
    """
    a parse action for tcl_parser that ignores empty lists and promotes lists with a single item to a single item
    Args:
        value (ParseResults): parse resultsd to be modified

    Returns:
        ParseResults: corrected parse results
    """

    for i, item in enumerate(value):
        if len(item) == 0:
            value[i] = ""

    if len(value) == 1:
        value = value[0]

    return value


# @functools.cache
def get_tcl_parser() -> ParserElement:
    """
    build a simple tcl parser suitable for nmrview files and cach it

    Returns:
        pyparsing parser

    """

    # TODO this should be printables  excluding : " {  }
    simple_word = Word(initChars=printables, excludeChars='"{}')
    simple_word.setName("simple_word")

    expression = Forward()
    expression.setName("expression")

    DBL_QUOTE = Suppress('"')
    LEFT_PAREN = Suppress("{")
    RIGHT_PAREN = Suppress("}")

    quoted_simple_word = DBL_QUOTE + simple_word + DBL_QUOTE
    quoted_simple_word.setName("quoted_simple_word")

    quoted_complex_word = Group(DBL_QUOTE + ZeroOrMore(expression) + DBL_QUOTE)
    quoted_complex_word.setName("quoted complex word")

    complex_list = Group(LEFT_PAREN + ZeroOrMore(expression) + RIGHT_PAREN)
    complex_list.setName("complex list")

    expression << (
        simple_word | quoted_simple_word | quoted_complex_word | complex_list
    )

    remainder = restOfLine()
    remainder.setName("remainder")

    top_level = ZeroOrMore(expression)
    top_level.setParseAction(_process_emptys_and_singles)
    top_level.setName("phrase") + restOfLine()

    return top_level


def parse_tcl(in_str, file_name="unknown", line_no=0) -> ParseResults:
    """
    parse a tcl data file or fragment using pyparsing

    Args:
        in_str (str):  tcl source
        file_name (str):  file name for error reporting
        line_no (str):  base line number for error reporting, the line no reported by py parsing will be added to this

    Returns:
        ParseResults: pyparsing parse result
    """

    parser = get_tcl_parser()

    result = None
    try:
        result = parser.parseString(in_str, parseAll=True)
    except ParseException as pe:
        line_no += pe.lineno
        msg = f"""\
                    Failed while parsing tcl at line: {line_no} in file: {file_name}

                    Explanation:
                """

        msg = dedent(msg)

        msg += pe.explain_exception(pe)

        exit_error(msg)

    return result


# TODO: add line info for better error handling
def parse_float_list(line: str, line_no: int) -> List[float]:
    """
     parse a tcl list into a list of floats using the tcl parser

    Args:
        line (str): the input string
        line_no: line number for error reporting

    Returns:
       List[float]: a list of floats
    """

    raw_fields = []
    parsed_tcl = parse_tcl(line)
    for field in parsed_tcl:
        if isinstance(field, ParseResults):
            raw_fields.extend(field)
        elif isinstance(field, str):
            raw_fields.append(field)
        else:
            exit_error(
                f"Error: unexpected internal error tcl failed to parse: '{line}' was not parsed properly got: \
                {parsed_tcl} field type was: {field.__class__}"
            )

    result = []
    for field_index, field in enumerate(raw_fields):
        try:
            field = float(field)
        except ValueError as e:
            msg = f"Couldn't convert sweep width {field_index} [{field}] to float for line {line} at line number \
                  {line_no}"
            exit_error(msg, e)
        result.append(field)

    return result


def read_sequence(
    sequence_lines: Iterable[str],
    chain_code: str = "A",
    sequence_file_name: str = "unknown",
) -> List[SequenceResidue]:

    """
    read an nmrview sequence from a file

    Args:
        sequence_lines (Iterable[str]): the lines for the file
        chain_code (str): a chaning code to use
        sequence_file_name (str): the file being read from for reporting errors

    Returns:
        List[SequenceResidue]: The residues as structures
    """

    start_residue = 1
    result = []
    for i, line in enumerate(sequence_lines):
        line = line.strip()
        fields = line.split()

        msg = f"""nmview sequences have one residue name per line,
                  except for the first line which can also contain a starting residue number,
                  at line {i + 1} i got {line} in file {sequence_file_name}
                  line was: {line}"""

        if len(fields) > 1 and i != 0:
            exit_error(msg)

        if i == 0 and len(fields) > 2:
            exit_error(
                f"""at the first line the should be one 3 letter code and an optional residue number
                           in file {sequence_file_name} at line {i+1} got {len(fields)} fields
                           line was: {line}"""
            )

        if i == 0 and len(fields) == 2:
            try:
                start_residue = int(fields[1])
            except ValueError:
                msg = f"""couldn't convert second field {fields[0]} to an integer
                          at line {i + 1} in file {sequence_file_name}
                          line was: {line}
                        """
                exit_error(msg)

        if len(fields) > 0:
            result.append(SequenceResidue(chain_code, start_residue + i, fields[0]))

    return result


def parse_shifts(
    lines: Iterable[str],
    chain_seqid_to_type: Dict[Tuple[str, int], str],
    chain_code: str = "A",
    file_name="unknown",
) -> ShiftList:

    shifts = []
    for i, line in enumerate(lines):

        line = line.strip()

        if len(line) == 0:
            continue

        fields = line.split()
        num_fields = len(fields)
        if num_fields != 3:
            msg = f"""An nmrview ppm.out file should have 3 fields per line
                    i got {num_fields} at line {i + 1}
                    with data: {line}"""
            exit_error(msg)

        shift, stereo_specificty_code = fields[1:]

        atom_fields = fields[0].split(".")
        num_atom_fields = len(atom_fields)
        if num_atom_fields != 2:
            msg = f"""An nmrview ppm.out file should have atom specfiers of the form '1.CA'
                                        i got{num_atom_fields} at line {i + 1}
                                        with data: {line}"""
            exit_error(msg)
        residue_code, atom = atom_fields

        try:
            residue_code = int(residue_code)
        except ValueError:
            msg = f"""An nmrview residue number should be an integer
                      i got {residue_code} at line {i + 1}"""
            exit_error(msg)

        try:
            shift = float(shift)
        except ValueError:
            msg = f"""A chemical shift should be a float
                      i got {shift} at line {i + 1}"""
            exit_error(msg)

        try:
            stereo_specificty_code = int(stereo_specificty_code)
        except ValueError:
            msg = f"""An nmrview stereo specificty code should be an integer
                      i got {stereo_specificty_code} at line {i + 1}"""
            exit_error(msg)

        if stereo_specificty_code not in [1, 2, 3]:
            msg = f"""An nmrview stereo specificty code should be an integer between 1 and 3,
                      i got {stereo_specificty_code} at line {i + 1}"""
            exit_error(msg)

        residue_name = get_residue_name_from_lookup(
            chain_code, residue_code, chain_seqid_to_type
        )

        if (residue_code != UNUSED and chain_code != UNUSED) and residue_name == UNUSED:
            msg = f"""\
            residue not defined for chain {chain_code} residue {residue_code}
            line number {i+1}
            line was |{line}|
            in file {file_name}
            did you read a sequence?"""
            msg = dedent(msg)
            exit_error(msg)

        atom = AtomLabel(SequenceResidue(chain_code, residue_code, residue_name), atom)
        shift = ShiftData(atom, shift)
        shifts.append(shift)

    result = ShiftList(shifts)

    return result
