import typer

from nef_pipelines import nef_app

app = typer.Typer()
export_app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app, name="mars", help="- read and write mars [shifts and sequences]"
    )

    app.add_typer(
        export_app, name="export", help="- export mars [shifts and sequences]"
    )

    app.add_typer(
        import_app, name="import", help="- import mars [shifts, sequence & peaks]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.mars.exporters.fixed  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.fragments  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.input  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.sequence  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.shifts  # noqa: F401
    import nef_pipelines.transcoders.mars.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.mars.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.mars.importers.shifts  # noqa: F401
