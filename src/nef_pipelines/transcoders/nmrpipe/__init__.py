import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app, name="nmrpipe", help="- read nmrpipe [peaks, shifts & sequencess]"
    )

    app.add_typer(
        import_app, name="import", help="- import nmrpipe [peaks, shifts & sequences]"
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.nmrpipe.importers.peaks  # noqa: F401
    import nef_pipelines.transcoders.nmrpipe.importers.sequence  # noqa: F401
    import nef_pipelines.transcoders.nmrpipe.importers.shifts  # noqa: F401
