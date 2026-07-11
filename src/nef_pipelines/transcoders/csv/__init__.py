import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
import_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="csv",
        help="- read [peaks, rdcs, loop, shifts]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import [loop, peaks, rdcs, shifts]",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.csv.importers.loop  # noqa: F401
    import nef_pipelines.transcoders.csv.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.csv.importers.rdcs  # noqa: F401
    import nef_pipelines.transcoders.csv.importers.shifts  # noqa: F401
