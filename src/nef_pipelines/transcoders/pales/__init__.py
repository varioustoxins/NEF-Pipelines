import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name="pales", help="- read and write pales/dc [rdcs]")

    app.add_typer(import_app, name="import", help="-  import pales/dc [rdc restraints]")
    app.add_typer(
        export_app,
        name="export",
        help="- export pales/dc [rdc restraints and templates]",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.pales.exporters.rdcs  # noqa: F401
    import nef_pipelines.transcoders.pales.exporters.template  # noqa: F401
    import nef_pipelines.transcoders.pales.importers.rdcs  # noqa: F401
