import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(app, name="csv", help="- read [rdcs]")

    app.add_typer(import_app, name="import", help="- import [rdcs]")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.csv.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.csv.importers.rdcs  # noqa: F401
