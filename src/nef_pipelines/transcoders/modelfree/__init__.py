import typer

from nef_pipelines import nef_app

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="modelfree",
        help="- write modelfree [relaxation data]",
        no_args_is_help=True,
    )

    app.add_typer(
        export_app,
        name="export",
        help="- export modelfree [relaxation data]",
        no_args_is_help=True,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.modelfree.exporters.data  # noqa: F401
