import os
from textwrap import dedent

import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.nmrview.exporters.sequences import sequences

app = typer.Typer()
app.command()(sequences)


# noinspection PyUnusedLocal
def test_multi_chain():

    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    result = run_and_report(app, ["-o"], input=STREAM)

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

    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    result = run_and_report(app, ["-o", "--template", "test_%s.seq"], input=STREAM)

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


def test_multi_chain_file_names_one_filename():

    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    result = run_and_report(app, ["-o", "--file-names", "wibble_a.seq"], input=STREAM)

    EXPECTED = """\
        ------------- wibble_a.seq -------------
        his 3
        met
        -------------    B.seq     -------------
        arg 5
        gln
        -------------    C.seq     -------------
        pro 7
        ----------------------------------------
    """

    assert_lines_match(EXPECTED, result.stdout)


def test_multi_chain_file_names_too_many():

    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    result = run_and_report(
        app,
        ["-o", "--file-names", "wibble_a.seq,wibble_b.seq,wibble_c.seq,wibble_d.seq"],
        input=STREAM,
        expected_exit_code=1,
    )

    assert "there are more file names than chains" in result.stdout


def test_multi_chain_bad_selector():

    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    result = run_and_report(app, ["-o", "AAAA"], input=STREAM, expected_exit_code=1)

    assert "the chain code" in result.stdout
    assert "not in the molecular systems chain codes" in result.stdout
    assert "AAAA" in result.stdout


def test_multi_chain_file_names_one_filename_disk(tmp_path):
    STREAM = open(path_in_test_data(__file__, "multi_chain.nef")).read()

    os.chdir(tmp_path)

    run_and_report(app, ["--file-names", "wibble_a.seq"], input=STREAM)

    EXPECTED_FILES = "wibble_a.seq", "B.seq", "C.seq"

    for file_name in EXPECTED_FILES:
        assert (tmp_path / file_name).is_file()

    EXPECTED = {
        "wibble_a.seq": """\
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
