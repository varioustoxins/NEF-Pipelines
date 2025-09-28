import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app, name="shiftx2", help="- read shiftx2 data [shifts]", no_args_is_help=True
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import shiftx2 [shifts]",
        no_args_is_help=True,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.shiftx2.importers.shifts  # noqa: F401
