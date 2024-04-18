import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    read_test_data,
    run_and_report,
)
from nef_pipelines.tools.chains.list import list as list_app

app = typer.Typer()
app.command()(list_app)


# noinspection PyUnusedLocal
def test_frame_basic():

    input_data = read_test_data("multi_chain.nef", __file__)

    result = run_and_report(app, [], input=input_data)

    EXPECTED = "A B C"

    assert_lines_match(EXPECTED, result.stdout)
