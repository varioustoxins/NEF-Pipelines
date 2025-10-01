import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

fit_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        fit_app,
        name="fit",
        help="- carry out fitting operations [alpha]",
        rich_help_panel="Data analysis & manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.fit.exponential  # noqa: F401
    import nef_pipelines.tools.fit.mean  # noqa: F401
    import nef_pipelines.tools.fit.ratio  # noqa: F401
    import nef_pipelines.tools.fit.t1noe  # noqa: F401
