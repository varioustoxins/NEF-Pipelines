import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

loops_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        loops_app,
        name="loops",
        help="- carry out operations on loops in nef frames [trim]",
        rich_help_panel="NEF manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.loops.trim  # noqa: F401
