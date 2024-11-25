import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="sparky",
        help="- read sparky files [shifts]",
    )

    app.add_typer(import_app, name="import", help="- import sparky [shifts]")
    app.add_typer(export_app, name="export", help="- export sparky [peaks]")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.sparky.exporters.peaks  # noqa: F401
    import nef_pipelines.transcoders.sparky.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.sparky.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.sparky.importers.shifts  # noqa: F401
