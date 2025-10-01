import typer

from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="ucbshift",
        help="- read UCBShift files [shifts, sequence]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import UCBShift CSV files [shifts, sequence]",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.ucbshift.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.ucbshift.importers.shifts  # noqa: F401
