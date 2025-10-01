import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

peaks_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        peaks_app,
        name="peaks",
        help="- carry out operations on nef peaks [match]",
        rich_help_panel="Data analysis & manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.peaks.match  # noqa: F401
