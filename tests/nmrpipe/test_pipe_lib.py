from lib.test_lib import assert_lines_match
from transcoders.nmrpipe.nmrpipe_lib import print_pipe_sequence


def test_print_pipe_sequence(capsys):
    TEST_DATA = ['A'] * 110
    EXPECTED = """\
        DATA SEQUENCE AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA AAAAAAAAAA
        DATA SEQUENCE AAAAAAAAAA
    """

    print_pipe_sequence(TEST_DATA)

    assert_lines_match(capsys.readouterr().out, EXPECTED)