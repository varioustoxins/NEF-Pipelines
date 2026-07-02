import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

columns_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        columns_app,
        name="columns",
        help="- manipulate columns in nef loops [list, delete, reorder, insert, extract, replace, rename]",
        rich_help_panel="NEF manipulation",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific commands must be after app creation to avoid circular imports
    import nef_pipelines.tools.columns.delete  # noqa: F401
    import nef_pipelines.tools.columns.insert  # noqa: F401
