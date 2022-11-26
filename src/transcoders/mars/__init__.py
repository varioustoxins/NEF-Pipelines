import typer

import nef_app

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="mars", help="- export mars [shifts and sequences]")

    app.add_typer(
        export_app, name="export", help="- export mars [shifts and sequences]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import transcoders.mars.exporters.shifts  # noqa: F401