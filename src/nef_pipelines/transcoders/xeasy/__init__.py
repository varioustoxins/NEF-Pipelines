import typer

from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
# export_app = typer.Typer()


if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="xeasy",
        help="- read xeasy files [flya dialect: sequence]",
        no_args_is_help=True,
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import xeasy [sequence]",
        no_args_is_help=True,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.xeasy.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.xeasy.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.xeasy.importers.shifts  # noqa: F401
