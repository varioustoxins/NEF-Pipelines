import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app, name="deep", help="- read deep [peaks]", no_args_is_help=True
    )

    app.add_typer(
        import_app, name="import", help="- import deep [peaks]", no_args_is_help=True
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.deep.importers.peaks  # noqa: F401
