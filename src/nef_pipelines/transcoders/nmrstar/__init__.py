import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app, name="nmrstar", help="- read NMR-STAR [sequences & shifts]"
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import NMR-STAR sequences & shifts and whole projects",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.nmrstar.importers.project  # noqa: F401
    import nef_pipelines.transcoders.nmrstar.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.nmrstar.importers.shifts  # noqa: F401
