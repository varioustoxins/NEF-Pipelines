import typer

from nef_pipelines import nef_app

help_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        help_app, name="help", help="- help on the nef pipelines tools and their usage"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.help.about  # noqa: F401
    import nef_pipelines.tools.help.commands  # noqa: F401
