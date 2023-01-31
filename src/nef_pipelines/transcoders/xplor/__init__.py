import typer

import nef_pipelines
from nef_pipelines import nef_app

app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(
        app,
        name="xplor",
        help="-  read xplor [sequences, dihedral & distance restraints]",
    )

    app.add_typer(
        import_app,
        name="import",
        help="-  import xplor [sequences, dihedral & distance restraints]",
    )

    app.add_typer(
        export_app,
        name="export",
        help="-  export xplor [rdcs]",
    )

    # import of specific importers must be after app creation to avoid circular imports
    import nef_pipelines.transcoders.xplor.exporters.rdcs  # noqa: F401
    import nef_pipelines.transcoders.xplor.importers.dihedrals
    import nef_pipelines.transcoders.xplor.importers.distances  # noqa: F401
    import nef_pipelines.transcoders.xplor.importers.sequence  # noqa: F401
