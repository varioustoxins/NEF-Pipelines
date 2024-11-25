import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(app, name="rcsb", help="- read pdb/cif [sequences]")

    app.add_typer(import_app, name="import", help="- import pdb/cif [sequences]")

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.rcsb.importers.sequence  # noqa: F401
