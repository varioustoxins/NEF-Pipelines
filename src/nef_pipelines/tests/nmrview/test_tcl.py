import pytest

from nef_pipelines.transcoders.nmrview import nmrview_lib


@pytest.fixture
def parser():

    return nmrview_lib.get_tcl_parser()


@pytest.fixture
def parse_tcl():

    return nmrview_lib.parse_tcl


def test_basic_word(parser):
    values = ["123", "abc", "123.abc", "123.abc#"]

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 1
        assert parsed[0] == value


def test_quoted_word(parser):
    values = ['"123"', '"abc"', '"123.abc"']

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 1
        assert parsed[0] == value.strip('"')


def test_quoted_word_list(parser):
    values = ['"123 456"', '"abc def"', '"123.abc 456.def"']

    for value in values:
        parsed = parser.parseString(value)

        assert len(parsed) == 2
        assert list(parsed) == value.strip('"').split()


def test_string_and_quoted_word_list(parser):
    tests_and_expecteds = {
        '"abc" "123 456"': ["abc", ["123", "456"]],
        '"" "123 456"': ["", ["123", "456"]],
    }

    for test, expected in tests_and_expecteds.items():
        parsed = parser.parseString(test)

        assert list(parsed.asList()) == expected


def test_complex_list(parser):
    tests_and_expecteds = {
        "{123 456}": ["123", "456"],
        '"" {123 456}': ["", ["123", "456"]],
        "{} {123 456}": ["", ["123", "456"]],
        "{} {{} 123 456}": ["", [[], "123", "456"]],
        "{} {{} 123 {} 456}": ["", [[], "123", [], "456"]],
        '{} "{} 123 {} 456"': ["", [[], "123", [], "456"]],
    }

    for test, expected in tests_and_expecteds.items():
        parsed = parser.parseString(test)

        assert list(parsed.asList()) == expected


def test_rest_of_line(parse_tcl, capsys):
    test = "12{3"

    with pytest.raises(SystemExit):
        parse_tcl(test, file_name="Wibble.txt", line_no=666)

    stderr = capsys.readouterr().err
    print(stderr)
    assert "Expected end of text, found '{'" in stderr
    assert "line: 667" in stderr
    assert "file: Wibble.txt" in stderr


if __name__ == "__main__":
    pytest.main([__file__, "-vv"])
