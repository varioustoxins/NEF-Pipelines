from nef_pipelines.lib.test_lib import assert_lines_match
from nef_pipelines.transcoders.nmrpipe.nmrpipe_lib import format_pipe_sequence


def test_format_pipe_sequence():
    TEST_DATA = ["A"] * 110

    BLOCK = "AAAAAAAAAA"
    EXPECTED = f"""\
        DATA SEQUENCE {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK} {BLOCK}
        DATA SEQUENCE {BLOCK}
    """

    lines = format_pipe_sequence(TEST_DATA)
    result = "\n".join(lines)

    assert_lines_match(result, EXPECTED)
