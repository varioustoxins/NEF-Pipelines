import typer

from nef_pipelines import nef_app

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app, name="modelfree", help="- write modelfree [relaxation data]"
    )

    app.add_typer(
        export_app, name="export", help="- export modelfree [relaxation data]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.modelfree.exporters.data  # noqa: F401
