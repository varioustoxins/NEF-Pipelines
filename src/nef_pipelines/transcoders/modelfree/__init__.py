import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="modelfree",
        help="- write modelfree [relaxation data]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        export_app,
        name="export",
        help="- export modelfree [relaxation data]",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.modelfree.exporters.data  # noqa: F401
