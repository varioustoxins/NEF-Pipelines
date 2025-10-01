import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
import_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="nmrstar",
        help="- read NMR-STAR [sequences & shifts]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import NMR-STAR sequences & shifts and whole projects",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.nmrstar.importers.project_cli  # noqa: F401
    import nef_pipelines.transcoders.nmrstar.importers.rdcs  # noqa: F401
    import nef_pipelines.transcoders.nmrstar.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.nmrstar.importers.shifts  # noqa: F401
