import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="ucbshift",
        help="- read UCBShift files [shifts, sequence]",
    )

    app.add_typer(
        import_app, name="import", help="- import UCBShift CSV files [shifts, sequence]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.ucbshift.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.ucbshift.importers.shifts  # noqa: F401
