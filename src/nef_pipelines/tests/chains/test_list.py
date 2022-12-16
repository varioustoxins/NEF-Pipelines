import typer

from nef_pipelines.lib.test_lib import (
    assert_lines_match,
    path_in_test_data,
    run_and_report,
)
from nef_pipelines.tools.chains.list import list as list_app

app = typer.Typer()
app.command()(list_app)


# noinspection PyUnusedLocal
def test_frame_basic(clear_cache):

    path = path_in_test_data(__file__, "multi_chain.nef")

    result = run_and_report(app, [], input=open(path).read())

    EXPECTED = "A B C"

    assert_lines_match(EXPECTED, result.stdout)
