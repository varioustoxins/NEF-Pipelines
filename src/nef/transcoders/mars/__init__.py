import typer

import nef
from nef import nef_app

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="mars", help="- export mars [shifts and sequences]")

    app.add_typer(
        export_app, name="export", help="- export mars [shifts and sequences]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef.transcoders.mars.exporters.shifts  # noqa: F401
