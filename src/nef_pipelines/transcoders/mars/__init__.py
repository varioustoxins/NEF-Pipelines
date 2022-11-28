import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="mars", help="- export mars [shifts and sequences]")

    app.add_typer(
        export_app, name="export", help="- export mars [shifts and sequences]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.mars.exporters.input  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.sequence  # noqa: F401
    import nef_pipelines.transcoders.mars.exporters.shifts  # noqa: F401
