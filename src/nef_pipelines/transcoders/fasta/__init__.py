import typer

import nef_pipelines
from nef_pipelines import nef_app
from nef_pipelines.lib.typer_lib import FilteredHelpGroup

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(
        app,
        name="fasta",
        help="- read and write fasta [sequences]",
        rich_help_panel="Transcoders",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    app.add_typer(
        import_app,
        name="import",
        help="- import fasta sequences",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )
    app.add_typer(
        export_app,
        name="export",
        help="- export fasta sequences",
        no_args_is_help=True,
        cls=FilteredHelpGroup,
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.fasta.exporters.sequence  # noqa: F401
    import nef_pipelines.transcoders.fasta.importers.sequence  # noqa: F401
