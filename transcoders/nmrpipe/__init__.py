import typer
import nef_app
app = typer.Typer()
import_app = typer.Typer()

if nef_app.app:
    nef_app.app.add_typer(app, name='nmrpipe', help='-  read nmrpipe [peaks shifts & sequencess]')

    app.add_typer(import_app, name='import', help='-  import nmrpipe [peaks, shifts & sequences]')

    # import of specific importers must be after app creation to avoid circular imports
    import transcoders.nmrpipe.importers.sequence
    import transcoders.nmrpipe.importers.peaks
    import transcoders.nmrpipe.importers.shifts
