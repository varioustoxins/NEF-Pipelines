import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

help_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        help_app,
        name="help",
        help="- help on the nef pipelines tools and their usage [about & commands]",
        rich_help_panel="NEF manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.help.about  # noqa: F401
    import nef_pipelines.tools.help.commands  # noqa: F401
