import functools
from textwrap import dedent

from pyparsing import Word, Forward, Suppress, Group, ZeroOrMore, ParseException, restOfLine, printables

# TODO is this a hack if so how to do this
from lib.util import exit_error


def _process_emptys_and_singles(value):

    for i, item in enumerate(value):
        if len(item) == 0:
            value[i] = ""

    if len(value) == 1:
        value = value[0]

    return value


@functools.cache
def get_tcl_parser():
    # TODO this should be printables  excluding : " {  }
    simple_word = Word(initChars=printables, excludeChars='"{}')
    simple_word.setName('simple_word')

    expression = Forward()
    expression.setName('expression')

    DBL_QUOTE = Suppress('"')
    LEFT_PAREN = Suppress("{")
    RIGHT_PAREN = Suppress("}")

    quoted_simple_word = DBL_QUOTE + simple_word + DBL_QUOTE
    quoted_simple_word.setName('quoted_simple_word')

    quoted_complex_word = Group(DBL_QUOTE + ZeroOrMore(expression) + DBL_QUOTE)
    quoted_complex_word.setName('quoted complex word')

    complex_list = Group(LEFT_PAREN + ZeroOrMore(expression) + RIGHT_PAREN)
    complex_list.setName('complex list')

    expression << (simple_word | quoted_simple_word | quoted_complex_word | complex_list)

    remainder = restOfLine()
    remainder.setName('remainder')

    top_level = ZeroOrMore(expression)
    top_level.setParseAction(_process_emptys_and_singles)
    top_level.setName('phrase') + restOfLine()


    return top_level


def parse_tcl(in_str, file_name='unknown', line_no='unknown'):

    parser = get_tcl_parser()

    result = None
    try:
        result = parser.parseString(in_str, parseAll=True)
    except ParseException as pe:
        msg = f"""\
                    Failed while parsing tcl at line: {line_no} in file: {file_name}
                  
                    Explanation:
                """
                  


        msg = dedent(msg)

        msg += pe.explain_exception(pe)

        exit_error(msg)

    return result


def parse_float_list(line, line_no):

    raw_fields = [field[0] for field in parse_tcl(line)]

    result = []
    for field_index, field in enumerate(raw_fields):
        try:
            field = float(field)
        except ValueError as e:
            msg = f"Couldn't convert sweep width {field_index} [{field}] to float for line {line} at line number {line_no}"
            exit_error(msg)
        result.append(field)

    return result
