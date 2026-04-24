import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.util import get_aphorism, get_version


@nef_app.app.command(rich_help_panel="Housekeeping")
def version(
    verbose: bool = typer.Option(
        False, "-v", "--verbose", help="also show the release aphorism"
    ),
):
    """- display the current version of NEF-Pipelines"""
    v = get_version()
    print(f"{v} - {get_aphorism()}" if verbose else v)
