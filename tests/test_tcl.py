import pytest

from pyparsing import Word, alphanums, Suppress, ZeroOrMore, Group, Forward, alphas, nums

DOUBLE_QUOTE = Suppress('"')

# TODO is this a hack if so how to do this
def process_emptys_and_singles(value):

    for i, item in enumerate(value):
        if len(item) == 0:
            value[i] = ""

    if len(value) == 1:
        value = value[0]

    return value


@pytest.fixture
def parser():

    simple_word = Word(alphanums + '.#*')
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

    phrase = ZeroOrMore(expression)
    phrase.setParseAction(process_emptys_and_singles)
    phrase.setName('phrase')

    phrase.create_diagram('tcl_diag.html')

    return phrase


def test_basic_word(parser):
    values = [
        "123",
        "abc",
        "123.abc",
        "123.abc#"
    ]

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 1
        assert parsed[0] == value


def test_quoted_word(parser):
    values = [
        '"123"',
        '"abc"',
        '"123.abc"'
    ]

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 1
        assert parsed[0] == value.strip('"')


def test_quoted_word_list(parser):
    values = [
        '"123 456"',
        '"abc def"',
        '"123.abc 456.def"'
    ]

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 2
        assert list(parsed) == value.strip('"').split()


def test_string_and_quoted_word_list(parser):
    tests_and_expecteds = {
        '"abc" "123 456"': ['abc', ['123', '456']],
        '"" "123 456"':    ['', ['123', '456']],
    }

    for test, expected in tests_and_expecteds.items():
        parsed = parser.parseString(test)


        assert list(parsed.asList()) == expected


def test_complex_list(parser):
    tests_and_expecteds = {
        '{123 456}':          ['123', '456'],
        '"" {123 456}':       ['', ['123', '456']],
        '{} {123 456}':       ['', ['123', '456']],
        '{} {{} 123 456}':    ['', [[], '123', '456']],
        '{} {{} 123 {} 456}': ['', [[], '123', [], '456']],
        '{} "{} 123 {} 456"': ['', [[], '123', [], '456']],
    }

    for test, expected in tests_and_expecteds.items():
        parsed = parser.parseString(test)

        assert list(parsed.asList()) == expected

if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
