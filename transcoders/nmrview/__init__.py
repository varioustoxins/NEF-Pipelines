import typer
import nef_app
app = typer.Typer()
import_app = typer.Typer()
export_app = typer.Typer()

nef_app.app.add_typer(app, name='nmrview', help='-  read and write nmrview [peaks, sequences & shifts]')

app.add_typer(import_app, name='import', help='-  import nmrview [peaks, sequences & shifts]')
app.add_typer(export_app, name='export', help='-  export nmrview [peaks, sequences & shifts]')

# import of specific importers must be after app creation to avoid circular imports
import transcoders.nmrview.importers.sequence
import transcoders.nmrview.importers.peaks