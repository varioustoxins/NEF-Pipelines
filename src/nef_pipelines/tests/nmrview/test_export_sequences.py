import os
from textwrap import dedent

import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrview.exporters.sequences import sequences

app = typer.Typer()
app.command()(sequences)

INPUT_MULTI_CHAIN_NEF = read_test_data("multi_chain.nef", __file__)


# noinspection PyUnusedLocal
def test_multi_chain():

    result = run_and_report(app, ["-o", "-"], input=INPUT_MULTI_CHAIN_NEF)

    EXPECTED = """\
        ------------- A.seq -------------
        his 3
        met
        ------------- B.seq -------------
        arg 5
        gln
        ------------- C.seq -------------
        pro 7
        ---------------------------------
    """

    assert_lines_match(EXPECTED, result.stdout)


def test_multi_chain_template():

    result = run_and_report(
        app, ["-o", "-test_{chain_code}.seq"], input=INPUT_MULTI_CHAIN_NEF
    )

    EXPECTED = """\
        ------------- test_A.seq -------------
        his 3
        met
        ------------- test_B.seq -------------
        arg 5
        gln
        ------------- test_C.seq -------------
        pro 7
        --------------------------------------
    """

    assert_lines_match(EXPECTED, result.stdout)


def test_multi_chain_bad_selector():

    result = run_and_report(
        app, ["-o", "-", "AAAA"], input=INPUT_MULTI_CHAIN_NEF, expected_exit_code=1
    )

    assert "the chain code" in result.stdout
    assert "not in the molecular systems chain codes" in result.stdout
    assert "AAAA" in result.stdout


def test_bad_template():

    result = run_and_report(
        app, ["-o", "test.seq", "A"], input=INPUT_MULTI_CHAIN_NEF, expected_exit_code=1
    )

    assert "the file name template" in result.stdout
    assert "does not contain the string" in result.stdout
    assert "{chain_code}" in result.stdout


def test_multiple_output_files_disk(
    tmp_path,
):

    os.chdir(tmp_path)

    run_and_report(app, [], input=INPUT_MULTI_CHAIN_NEF)

    EXPECTED_FILES = "A.seq", "B.seq", "C.seq"

    for file_name in EXPECTED_FILES:
        assert (tmp_path / file_name).is_file()

    EXPECTED = {
        "A.seq": """\
            his 3
            met
        """,
        "B.seq": """\
            arg 5
            gln
        """,
        "C.seq": """\
            pro 7
        """,
    }

    for file_name in EXPECTED_FILES:
        with open(file_name) as fp:
            text = fp.read()

            assert text == dedent(EXPECTED[file_name])
