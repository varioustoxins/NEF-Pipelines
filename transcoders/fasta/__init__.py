import typer
import nef_app
app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:

    nef_app.app.add_typer(app, name='fasta', help='- read and write fasta sequences')

    app.add_typer(import_app, name='import', help='- import fasta sequences')

    # import of specific importers must be after app creation to avoid circular imports
    import transcoders.fasta.importers.sequence
