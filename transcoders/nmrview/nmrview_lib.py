from pyparsing import Word, Forward, Suppress, alphanums, Group, ZeroOrMore


# TODO is this a hack if so how to do this
def _process_emptys_and_singles(value):

    for i, item in enumerate(value):
        if len(item) == 0:
            value[i] = ""

    if len(value) == 1:
        value = value[0]

    return value

# TODO this should memoise the parser
def get_tcl_parser():
    # TODO this should be printables  excluding : " {  }
    simple_word = Word(alphanums + '.#*?+-./_:')
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

    top_level = ZeroOrMore(expression)
    top_level.setParseAction(_process_emptys_and_singles)
    top_level.setName('phrase')

    top_level.create_diagram('tcl_diag.html')

    return top_level


def parse_tcl(in_str):
    return get_tcl_parser().parseString(in_str)


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
