import typer
from typer.testing import CliRunner

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.fasta.exporters.sequence import sequence

runner = CliRunner()
app = typer.Typer()
app.command()(sequence)

EXPECTED_3AA = """
>test NEFPLS | CHAIN: A | START: 1

AAA
"""


# noinspection PyUnusedLocal
def test_3aa():

    path = path_in_test_data(__file__, "3aa.nef")
    result = run_and_report(app, ["--in", path, "-"])

    assert_lines_match(result.stdout, EXPECTED_3AA)


EXPECTED_3AA_2_CHAINS = """
>test NEFPLS | CHAIN: A | START: 1

AAA
>test NEFPLS | CHAIN: B | START: 1

CCC
"""


def test_3aa_2_chains():

    path = path_in_test_data(__file__, "3aa_2_chains.nef")
    result = run_and_report(app, ["--in", path, "-"])

    assert_lines_match(result.stdout, EXPECTED_3AA_2_CHAINS)


EXPECTED_THX = """
>test NEFPLS | CHAIN: thx | START: 1
AAA
"""


def test_petes_thx_chain():
    path = path_in_test_data(__file__, "3aa_thx.nef")
    result = run_and_report(app, ["--in", path, "-"])

    assert_lines_match(result.stdout, EXPECTED_THX)
