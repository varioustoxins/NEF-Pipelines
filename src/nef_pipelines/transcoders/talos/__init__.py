import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="talos",
        help="- read and write talos files [shifts & restraints]",
    )

    app.add_typer(import_app, name="import", help="- import talos dihderal restraints ")
    app.add_typer(
        export_app, name="export", help="-  export talos [shifts (& sequence)]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.talos.exporters.shifts  # noqa: F401
    import nef_pipelines.transcoders.talos.importers.order_parameters  # noqa: F401
    import nef_pipelines.transcoders.talos.importers.restraints  # noqa: F401
    import nef_pipelines.transcoders.talos.importers.secondary_structure  # noqa: F401
    import nef_pipelines.transcoders.talos.importers.sequence  # noqa: F401
