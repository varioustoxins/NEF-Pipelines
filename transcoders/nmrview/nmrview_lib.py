from dataclasses import dataclass
from typing import List


import pyparsing

def _get_tcl_parser():

    string = pyparsing.CharsNotIn("{} \t\r\n")

    group = pyparsing.Forward()
    group <<= (
            pyparsing.Group(pyparsing.Literal("{").suppress() +
                            pyparsing.ZeroOrMore(group) +
                            pyparsing.Literal("}").suppress()) |
            string

    )

    toplevel = pyparsing.OneOrMore(group)

    return toplevel


def parse_tcl(in_str):
    return _get_tcl_parser().parseString(in_str)


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
