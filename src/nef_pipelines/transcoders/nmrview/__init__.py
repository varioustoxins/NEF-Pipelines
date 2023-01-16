import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="nmrview",
        help="-  read and write nmrview [peaks, sequences & shifts]",
    )

    app.add_typer(
        import_app, name="import", help="-  import nmrview [peaks, sequences & shifts]"
    )
    app.add_typer(
        export_app, name="export", help="-  export nmrview [peaks, sequences & shifts]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.nmrview.exporters.peaks  # noqa: F401
    import nef_pipelines.transcoders.nmrview.exporters.sequences  # noqa: F401
    import nef_pipelines.transcoders.nmrview.exporters.shifts  # noqa: F401
    import nef_pipelines.transcoders.nmrview.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.nmrview.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.nmrview.importers.shifts  # noqa: F401
