import typer

from nef_pipelines import nef_app

app = typer.Typer()
# import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="rpf", help="-  write rpf shifts")

    # app.add_typer(import_app, name="import", help="- import fasta sequences")
    app.add_typer(export_app, name="export", help="- export rpf shifts")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.rpf.exporters.shifts  # noqa: F401

    # import nef_pipelines.transcoders.fasta.importers.sequence  # noqa: F401
