import typer

from nef_pipelines import nef_app

entry_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        entry_app,
        name="entry",
        help="-  carry out operations on the nef file entry",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.entry.rename  # noqa: F401
