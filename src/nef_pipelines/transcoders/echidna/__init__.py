import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="echidna", help="- read echidna data [peaks]")

    app.add_typer(import_app, name="import", help="- import echidna peaks")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.echidna.importers.peaks  # noqa: F401
