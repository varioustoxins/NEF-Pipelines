import pytest

from pyparsing import Word, alphanums, Suppress, ZeroOrMore
DOUBLE_QUOTE = Suppress('"')

@pytest.fixture
def parser():

    word = Word(alphanums + '.')
    word.setName('word')
    quoted_list = (DOUBLE_QUOTE + ZeroOrMore(word) + DOUBLE_QUOTE)
    quoted_list.setName('quoted list')

    phrase = word | quoted_list

    phrase.setName("tcl")


    phrase.create_diagram('tcl_diag.html')

    return phrase


def test_basic_word(parser):
    values = [
        "123",
        "abc",
        "123.abc"
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


if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
