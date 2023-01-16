import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="sparky",
        help="-  read sparky files [shifts]",
    )

    app.add_typer(import_app, name="import", help="-  import sparky [shifts]")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.sparky.importers.shifts  # noqa: F401
