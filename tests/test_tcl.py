import pytest

from pyparsing import Word, alphanums

@pytest.fixture
def parser():

    word = Word(alphanums + '.')

    return word


def test_basic_value(parser):
    values = [
        "123",
        "abc",
        "123.abc"
    ]

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 1
        assert parsed[0] == value




if __name__ == '__main__':
    pytest.main([__file__, '-vv'])
