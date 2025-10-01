import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

frames_app = typer.Typer()


if nef_app.app:
    nef_app.app.add_typer(
        frames_app,
        name="frames",
        help="- carry out operations on frames in nef files [delete, filter, insert, list, rename, tabulate, unassign]",
        rich_help_panel="NEF manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.tools.frames.delete  # noqa: F401
    import nef_pipelines.tools.frames.filter  # noqa: F401
    import nef_pipelines.tools.frames.insert  # noqa: F401
    import nef_pipelines.tools.frames.list  # noqa: F401
    import nef_pipelines.tools.frames.rename  # noqa: F401
    import nef_pipelines.tools.frames.tabulate  # noqa: F401
    import nef_pipelines.tools.frames.unassign  # noqa: F401
