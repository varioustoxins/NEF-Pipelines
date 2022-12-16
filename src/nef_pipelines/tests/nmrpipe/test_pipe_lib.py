from nef_pipelines.lib.test_lib import assert_lines_match
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import print_pipe_sequence


def test_print_pipe_sequence(capsys):
    TEST_DATA = ["A"] * 110

    BLOCK = "AAAAAAAAAA"
    EXPECTED = f"""\
        DATA SEQUENCE {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK}
        DATA SEQUENCE {BLOCK}
    """

    print_pipe_sequence(TEST_DATA)

    assert_lines_match(capsys.readouterr().out, EXPECTED)
