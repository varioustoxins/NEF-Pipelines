import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app,
        name="rcsb",
        help="- read pdb/cif [sequences] & align and trim pdb/mmcif files by molecular systems",
        no_args_is_help=True,
    )

    app.add_typer(
        import_app,
        name="import",
        help=r"\- import pdb/mmcif [sequences]",
        no_args_is_help=True,
    )


# import of specific importers must be after app creation to avoid circular imports
import nef_pipelines.transcoders.rcsb.align  # noqa: F401 E402
import nef_pipelines.transcoders.rcsb.importers.sequence  # noqa: F401 E402
import nef_pipelines.transcoders.rcsb.trim  # noqa: F401 E402
