import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app,
        name="shifty",
        help="- write shifty [shifts]",
    )

    app.add_typer(
        export_app,
        name="export",
        help="- export shifty [shifts]",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.shifty.exporters.shifts  # noqa: F401
