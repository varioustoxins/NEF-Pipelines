import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.transcoders.mars.exporters.sequence import sequence

app = typer.Typer()
app.command()(sequence)

INPUT_SEQ_WITH_RESIDUE_ZERO = read_test_data("seq_with_residue_zero.nef", __file__)

# Regression: sequence_code 0 is falsy and was silently dropped
EXPECTED_WITH_RESIDUE_ZERO = """\
>test_seq NEFPLS | CHAIN: A | START: -4
GPLGSMT
"""


def test_export_sequence_includes_residue_zero():
    result = run_and_report(app, ["-"], input=INPUT_SEQ_WITH_RESIDUE_ZERO)

    assert_lines_match(EXPECTED_WITH_RESIDUE_ZERO, result.stdout)
