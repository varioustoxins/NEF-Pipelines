import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

shifts_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        shifts_app,
        name="shifts",
        help="- carry out operations on shifts [average]",
        rich_help_panel="Data analysis & manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.shifts.average  # noqa: F401
    import nef_pipelines.tools.shifts.correlation  # noqa: F401
