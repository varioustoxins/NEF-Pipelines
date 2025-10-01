import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app,
        name="xcamshift",
        help="- write xcamshift for xplor [shifts]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        export_app,
        name="export",
        help="- export xcamshift for xplor [shifts]",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.xcamshift.exporters.shifts  # noqa: F401
